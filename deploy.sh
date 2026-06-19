#!/usr/bin/env bash
# =============================================================================
#  Bilvantis Training Intelligence Platform — Ubuntu 22.04 Deployment Script
#  Version : 2.0
#  Target  : Ubuntu 22.04 LTS (Jammy Jellyfish)
#  Stack   : Python 3.12 + FastAPI (port 8002) | Next.js 15 (port 3003)
#  DB      : SQLite embedded — no server needed
#  Queue   : Celery memory:// — no Redis needed
#
#  Usage   : sudo bash deploy.sh [OPTIONS]
#
#  Options :
#    --groq-key  <KEY>    Groq API key (overrides embedded default)
#    --smtp-user <EMAIL>  Gmail address (overrides embedded default)
#    --smtp-pass <PASS>   Gmail App Password (overrides embedded default)
#    --port-backend <N>   Backend port  (default: 8002)
#    --port-frontend <N>  Frontend port (default: 3003)
#    --no-systemd         Skip systemd setup, start manually instead
# =============================================================================
set -euo pipefail
IFS=$'\n\t'

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m';  GREEN='\033[0;32m';  YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m';  BOLD='\033[1m';  NC='\033[0m'

LOG_FILE=""
_log() {
  local lvl="$1" col="$2"; shift 2
  echo -e "${col}[${lvl}]${NC} $*"
  [[ -n "$LOG_FILE" ]] && echo "[${lvl}] $*" >> "$LOG_FILE" 2>/dev/null || true
}
info()    { _log "INFO " "$CYAN"   "$*"; }
success() { _log "OK   " "$GREEN"  "$*"; }
warn()    { _log "WARN " "$YELLOW" "$*"; }
step()    { echo -e "\n${BOLD}${BLUE}━━━ $* ━━━${NC}"; }
die()     { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Parse arguments ───────────────────────────────────────────────────────────
GROQ_KEY="";  SMTP_USER="";  SMTP_PASS=""
BACKEND_PORT=8002;  FRONTEND_PORT=3003;  SKIP_SYSTEMD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --groq-key)       GROQ_KEY="$2";       shift 2 ;;
    --smtp-user)      SMTP_USER="$2";      shift 2 ;;
    --smtp-pass)      SMTP_PASS="$2";      shift 2 ;;
    --port-backend)   BACKEND_PORT="$2";   shift 2 ;;
    --port-frontend)  FRONTEND_PORT="$2";  shift 2 ;;
    --no-systemd)     SKIP_SYSTEMD=1;      shift   ;;
    -h|--help) grep '^#  ' "$0" | sed 's/^#  //'; exit 0 ;;
    *) warn "Unknown argument: $1"; shift ;;
  esac
done

# ── Root check ────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && die "Run as root:  sudo bash deploy.sh"

# ── Resolve paths ─────────────────────────────────────────────────────────────
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$APP_DIR/logs"
PID_DIR="$APP_DIR/run"
DEPLOY_LOG="$APP_DIR/logs/deploy.log"

mkdir -p "$LOG_DIR" "$PID_DIR"
LOG_FILE="$DEPLOY_LOG"
echo "=== Deploy started $(date '+%Y-%m-%d %H:%M:%S') ===" > "$DEPLOY_LOG"

# Detect the real user (if called with sudo)
RUN_USER="${SUDO_USER:-root}"
RUN_GROUP="$(id -gn "$RUN_USER" 2>/dev/null || echo "$RUN_USER")"

# Helpers
cmd_exists()  { command -v "$1" &>/dev/null; }
get_vm_ip() {
  hostname -I 2>/dev/null | awk '{print $1}' && return
  ip route get 1.1.1.1 2>/dev/null | awk '/src/{print $7;exit}' && return
  echo "127.0.0.1"
}

# =============================================================================
echo -e "\n${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║   Bilvantis Training Intelligence Platform — Deploy v2.0            ║"
echo "║   Target: Ubuntu 22.04 LTS  •  Python 3.12  •  Node.js 20          ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
info "App directory  : $APP_DIR"
info "Backend port   : $BACKEND_PORT"
info "Frontend port  : $FRONTEND_PORT"
info "Service user   : $RUN_USER:$RUN_GROUP"
info "Deploy log     : $DEPLOY_LOG"

# =============================================================================
step "1 / 9  Fix line endings and set permissions"
# =============================================================================
for f in "$APP_DIR"/*.sh; do
  [[ -f "$f" ]] || continue
  sed -i 's/\r$//' "$f" 2>/dev/null || true
  chmod +x "$f"
done
success "All .sh scripts are executable with Unix line endings"

# =============================================================================
step "2 / 9  Install system packages (Ubuntu 22.04)"
# =============================================================================
export DEBIAN_FRONTEND=noninteractive

info "Updating apt package index..."
apt-get update -qq >> "$DEPLOY_LOG" 2>&1

SYSTEM_PKGS=(
  curl wget git unzip ca-certificates gnupg lsb-release
  software-properties-common build-essential
  libssl-dev libffi-dev libsqlite3-dev sqlite3
  procps net-tools dos2unix
)
info "Installing system packages..."
apt-get install -y -qq "${SYSTEM_PKGS[@]}" >> "$DEPLOY_LOG" 2>&1
success "System packages installed"

# ── Python 3.12 via deadsnakes PPA ───────────────────────────────────────────
if ! cmd_exists python3.12; then
  info "Adding deadsnakes PPA and installing Python 3.12..."
  add-apt-repository -y ppa:deadsnakes/ppa >> "$DEPLOY_LOG" 2>&1
  apt-get update -qq >> "$DEPLOY_LOG" 2>&1
  apt-get install -y -qq python3.12 python3.12-venv python3.12-dev >> "$DEPLOY_LOG" 2>&1
fi
# Ensure pip exists for 3.12
if ! python3.12 -m pip --version &>/dev/null 2>&1; then
  curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12 >> "$DEPLOY_LOG" 2>&1
fi
success "Python: $(python3.12 --version 2>&1)"

# ── Node.js 20 LTS via NodeSource ────────────────────────────────────────────
NEED_NODE=0
if ! cmd_exists node; then
  NEED_NODE=1
else
  NODE_MAJOR=$(node -v 2>/dev/null | cut -d. -f1 | tr -d 'v' || echo 0)
  [[ $NODE_MAJOR -lt 20 ]] && NEED_NODE=1
fi
if [[ $NEED_NODE -eq 1 ]]; then
  info "Installing Node.js 20 LTS via NodeSource..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >> "$DEPLOY_LOG" 2>&1
  apt-get install -y -qq nodejs >> "$DEPLOY_LOG" 2>&1
fi
success "Node.js: $(node --version 2>&1)  |  npm: $(npm --version 2>&1)"

# =============================================================================
step "3 / 9  Python virtual environment and pip packages"
# =============================================================================
[[ ! -f "$BACKEND_DIR/requirements.txt" ]] \
  && die "requirements.txt missing at $BACKEND_DIR/requirements.txt"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  info "Creating Python 3.12 venv at $VENV_DIR ..."
  python3.12 -m venv "$VENV_DIR" >> "$DEPLOY_LOG" 2>&1
fi

info "Upgrading pip / setuptools / wheel..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools wheel >> "$DEPLOY_LOG" 2>&1

info "Installing 25 Python packages from requirements.txt..."
"$VENV_DIR/bin/pip" install --quiet -r "$BACKEND_DIR/requirements.txt" >> "$DEPLOY_LOG" 2>&1

PKG_COUNT=$("$VENV_DIR/bin/pip" list 2>/dev/null | tail -n +3 | wc -l)
success "Python venv ready ($PKG_COUNT packages)"

# =============================================================================
step "4 / 9  Detect IP and write environment files"
# =============================================================================
VM_IP=$(get_vm_ip)
info "VM IP: $VM_IP"

BACKEND_URL="http://${VM_IP}:${BACKEND_PORT}"
FRONTEND_URL="http://${VM_IP}:${FRONTEND_PORT}"

# Generate a unique secret key for this deployment
SECRET_KEY=$(python3.12 -c "import secrets; print(secrets.token_hex(32))")

# ── backend/.env ──────────────────────────────────────────────────────────────
BACKEND_ENV="$BACKEND_DIR/.env"

# Credential resolution: CLI arg > --groq-key flag required on fresh deploy
_GROQ="${GROQ_KEY:-}"
_SMTP_USER="${SMTP_USER:-}"
_SMTP_PASS="${SMTP_PASS:-}"

# Warn if GROQ key not provided (AI chat will fail without it)
if [[ -z "$_GROQ" ]]; then
  warn "GROQ_API_KEY not provided — pass with: --groq-key gsk_..."
  warn "AI analytics chat will not work until you set it in backend/.env"
fi

if [[ ! -f "$BACKEND_ENV" ]]; then
  info "Writing backend/.env ..."
  cat > "$BACKEND_ENV" <<ENVEOF
# Bilvantis TIP — Backend Environment
# Generated: $(date '+%Y-%m-%d %H:%M:%S') on $(hostname) [${VM_IP}]
# DO NOT commit this file.

# Database (SQLite — embedded, no server)
DATABASE_URL=sqlite+aiosqlite:///./feedback_platform.db
SYNC_DATABASE_URL=sqlite:///./feedback_platform.db

# Queue (in-memory Celery — no Redis server)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=memory://
CELERY_RESULT_BACKEND=cache+memory://

# Security
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FEEDBACK_TOKEN_EXPIRE_HOURS=72

# AI — Groq (required for analytics chat)
GROQ_API_KEY=${_GROQ}
GEMINI_API_KEY=

# Email — Gmail SMTP
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=${_SMTP_USER}
SMTP_PASSWORD=${_SMTP_PASS}
SMTP_FROM_EMAIL=${_SMTP_USER}
SMTP_FROM_NAME=Bilvantis TIP

# SendGrid alternative (leave blank to use SMTP above)
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=noreply@bilvantis.io

# URLs — auto-detected from VM IP
FRONTEND_URL=${FRONTEND_URL}
BACKEND_URL=${BACKEND_URL}

# App
FEEDBACK_THRESHOLD=5
PGVECTOR_DIMENSION=768
APP_NAME=Bilvantis Training Intelligence Platform
APP_VERSION=1.0.0
DEBUG=False
ENVEOF
  chmod 600 "$BACKEND_ENV"
  success "Created backend/.env  (permissions: 600)"
else
  warn "backend/.env exists — updating URLs only (secrets preserved)"
  sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=${FRONTEND_URL}|" "$BACKEND_ENV"
  sed -i "s|^BACKEND_URL=.*|BACKEND_URL=${BACKEND_URL}|"   "$BACKEND_ENV"
  [[ -n "$GROQ_KEY"  ]] && sed -i "s|^GROQ_API_KEY=.*|GROQ_API_KEY=${GROQ_KEY}|"       "$BACKEND_ENV"
  [[ -n "$SMTP_USER" ]] && sed -i "s|^SMTP_USER=.*|SMTP_USER=${SMTP_USER}|"             "$BACKEND_ENV"
  [[ -n "$SMTP_PASS" ]] && sed -i "s|^SMTP_PASSWORD=.*|SMTP_PASSWORD=${SMTP_PASS}|"     "$BACKEND_ENV"
fi

# ── frontend/.env.local ───────────────────────────────────────────────────────
cat > "$FRONTEND_DIR/.env.local" <<FEOF
NEXT_PUBLIC_API_URL=${BACKEND_URL}
NEXTAUTH_URL=${FRONTEND_URL}
FEOF
success "Created frontend/.env.local  (API → ${BACKEND_URL})"

# =============================================================================
step "5 / 9  Build Next.js frontend for production"
# =============================================================================
[[ ! -f "$FRONTEND_DIR/package.json" ]] \
  && die "package.json not found at $FRONTEND_DIR/package.json"

info "Installing npm packages (first run: ~2-3 min)..."
cd "$FRONTEND_DIR"
npm install --legacy-peer-deps --silent >> "$DEPLOY_LOG" 2>&1 || \
  npm install --legacy-peer-deps        >> "$DEPLOY_LOG" 2>&1

info "Building Next.js production bundle (NEXT_PUBLIC_API_URL=${BACKEND_URL})..."
NEXT_PUBLIC_API_URL="$BACKEND_URL" npm run build >> "$DEPLOY_LOG" 2>&1

[[ ! -d "$FRONTEND_DIR/.next" ]] \
  && die "Next.js build failed. Details: tail -50 $DEPLOY_LOG"
success "Next.js production build complete (.next directory created)"
cd "$APP_DIR"

# =============================================================================
step "6 / 9  Validate backend configuration"
# =============================================================================
cd "$BACKEND_DIR"
info "Importing app.core.config and verifying all required variables..."
"$VENV_DIR/bin/python" - <<'PYCHECK'
import sys
sys.path.insert(0, '.')
from app.core.config import Settings
s = Settings()
errors = []
if not s.DATABASE_URL:  errors.append("DATABASE_URL is empty")
if not s.SECRET_KEY:    errors.append("SECRET_KEY is empty")
if not s.GROQ_API_KEY:  errors.append("GROQ_API_KEY is empty")
if errors:
    for e in errors: print(f"  FAIL: {e}", file=sys.stderr)
    sys.exit(1)
print(f"  DATABASE_URL  : {s.DATABASE_URL}")
print(f"  FRONTEND_URL  : {s.FRONTEND_URL}")
print(f"  BACKEND_URL   : {s.BACKEND_URL}")
print(f"  GROQ_API_KEY  : {s.GROQ_API_KEY[:12]}...")
print(f"  SMTP_USER     : {s.SMTP_USER or '(not configured)'}")
print(f"  CELERY_BROKER : {s.CELERY_BROKER_URL}")
print(f"  DEBUG         : {s.DEBUG}")
PYCHECK
success "Backend configuration is valid"
cd "$APP_DIR"

# =============================================================================
step "7 / 9  Install systemd service units"
# =============================================================================

# ── bilvantis-backend.service ─────────────────────────────────────────────────
cat > /etc/systemd/system/bilvantis-backend.service <<SVCEOF
[Unit]
Description=Bilvantis TIP — FastAPI Backend (Python 3.12 + uvicorn)
Documentation=https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}

# CRITICAL: WorkingDirectory must be backend/ for SQLite path ./feedback_platform.db
WorkingDirectory=${BACKEND_DIR}

ExecStart=${VENV_DIR}/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${BACKEND_PORT} \
    --workers 1 \
    --loop asyncio \
    --log-level info

ExecStop=/bin/kill -s SIGTERM \$MAINPID
KillSignal=SIGTERM
TimeoutStopSec=30
KillMode=mixed

Restart=on-failure
RestartSec=5s
StartLimitIntervalSec=120s
StartLimitBurst=5

Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUNBUFFERED=1

StandardOutput=append:${LOG_DIR}/backend.log
StandardError=append:${LOG_DIR}/backend.log

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SVCEOF

# ── bilvantis-frontend.service ────────────────────────────────────────────────
cat > /etc/systemd/system/bilvantis-frontend.service <<SVCEOF
[Unit]
Description=Bilvantis TIP — Next.js Frontend (Node.js 20)
Documentation=https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto
After=network.target bilvantis-backend.service
Wants=bilvantis-backend.service

[Service]
Type=simple
User=${RUN_USER}
Group=${RUN_GROUP}

WorkingDirectory=${FRONTEND_DIR}

# --port 3003 overrides package.json default of 3000
ExecStart=$(command -v node) node_modules/.bin/next start --port ${FRONTEND_PORT}

ExecStop=/bin/kill -s SIGTERM \$MAINPID
KillSignal=SIGTERM
TimeoutStopSec=30
KillMode=mixed

Restart=on-failure
RestartSec=5s
StartLimitIntervalSec=120s
StartLimitBurst=5

Environment=NODE_ENV=production
Environment=PORT=${FRONTEND_PORT}

StandardOutput=append:${LOG_DIR}/frontend.log
StandardError=append:${LOG_DIR}/frontend.log

NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SVCEOF

# Set ownership so the service user can write logs and DB
chown -R "$RUN_USER:$RUN_GROUP" "$LOG_DIR" "$PID_DIR" "$BACKEND_DIR" 2>/dev/null || true

systemctl daemon-reload

if [[ $SKIP_SYSTEMD -eq 0 ]]; then
  systemctl enable bilvantis-backend  >> "$DEPLOY_LOG" 2>&1
  systemctl enable bilvantis-frontend >> "$DEPLOY_LOG" 2>&1
  success "Systemd units installed and enabled (will auto-start on reboot)"
else
  warn "--no-systemd: services installed but NOT enabled for auto-start"
fi

# =============================================================================
step "8 / 9  Start services"
# =============================================================================
info "Stopping any previous instances..."
systemctl stop bilvantis-backend  2>/dev/null || true
systemctl stop bilvantis-frontend 2>/dev/null || true
pkill -f "uvicorn app.main:app"   2>/dev/null || true
pkill -f "next start"             2>/dev/null || true
sleep 2

# ── Start backend ─────────────────────────────────────────────────────────────
info "Starting bilvantis-backend on port ${BACKEND_PORT}..."
systemctl start bilvantis-backend

BACKEND_READY=0; WAIT_SEC=0
while [[ $WAIT_SEC -lt 45 ]]; do
  if curl -sf --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/health" &>/dev/null; then
    BACKEND_READY=1; break
  fi
  sleep 3; WAIT_SEC=$((WAIT_SEC+3)); echo -n "."
done; echo ""

if [[ $BACKEND_READY -eq 1 ]]; then
  success "Backend ready (${WAIT_SEC}s)"
else
  warn "Backend not responding — check: sudo journalctl -u bilvantis-backend -n 40 --no-pager"
fi

# ── Start frontend ────────────────────────────────────────────────────────────
info "Starting bilvantis-frontend on port ${FRONTEND_PORT}..."
systemctl start bilvantis-frontend

FRONTEND_READY=0; WAIT_SEC=0
while [[ $WAIT_SEC -lt 45 ]]; do
  HTTP=$(curl -so /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:${FRONTEND_PORT}" 2>/dev/null || echo "000")
  if [[ "$HTTP" == "200" || "$HTTP" == "302" || "$HTTP" == "308" ]]; then
    FRONTEND_READY=1; break
  fi
  sleep 3; WAIT_SEC=$((WAIT_SEC+3)); echo -n "."
done; echo ""

if [[ $FRONTEND_READY -eq 1 ]]; then
  success "Frontend ready (${WAIT_SEC}s)  HTTP ${HTTP}"
else
  warn "Frontend not responding — check: sudo journalctl -u bilvantis-frontend -n 40 --no-pager"
fi

# =============================================================================
step "9 / 9  Health check and status report"
# =============================================================================

# ── Collect live status ───────────────────────────────────────────────────────
BE_ACTIVE=$(systemctl is-active  bilvantis-backend  2>/dev/null || echo "unknown")
FE_ACTIVE=$(systemctl is-active  bilvantis-frontend 2>/dev/null || echo "unknown")
BE_ENABLED=$(systemctl is-enabled bilvantis-backend  2>/dev/null || echo "unknown")
FE_ENABLED=$(systemctl is-enabled bilvantis-frontend 2>/dev/null || echo "unknown")
BE_PID=$(systemctl show -p MainPID --value bilvantis-backend  2>/dev/null || echo "-")
FE_PID=$(systemctl show -p MainPID --value bilvantis-frontend 2>/dev/null || echo "-")

# ── Config status ─────────────────────────────────────────────────────────────
GROQ_VAL=$(grep "^GROQ_API_KEY=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
if [[ "$GROQ_VAL" == gsk_* ]]; then
  GROQ_DISP="${GROQ_VAL:0:12}... (configured)"
else
  GROQ_DISP="NOT SET — AI chat will fail"
fi

SMTP_VAL=$(grep "^SMTP_USER=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
SMTP_DISP="${SMTP_VAL:-not configured (email disabled)}"

DB_PATH="$BACKEND_DIR/feedback_platform.db"
if [[ -f "$DB_PATH" ]]; then
  DB_DISP="$(du -sh "$DB_PATH" | cut -f1)  $DB_PATH"
else
  DB_DISP="will be created on first request"
fi

# ── Health check via curl ─────────────────────────────────────────────────────
HEALTH_JSON=$(curl -sf --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || echo '{"status":"unreachable"}')
API_STATUS=$(echo "$HEALTH_JSON" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('status','?'))" 2>/dev/null || echo "?")

# ── Colour function ───────────────────────────────────────────────────────────
svc_colour() { [[ "$1" == "active" ]] && printf '%s' "${GREEN}active${NC}" || printf '%s' "${RED}${1}${NC}"; }

# ── Final report ──────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║        ✓  Bilvantis TIP — Deployment Complete                        ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║                                                                      ║"
printf "║   %-22s : %-45s║\n" "VM IP Address"      "$VM_IP"
printf "║   %-22s : %-45s║\n" "Application URL"    "$FRONTEND_URL"
printf "║   %-22s : %-45s║\n" "API Base URL"       "$BACKEND_URL"
printf "║   %-22s : %-45s║\n" "API Documentation"  "${BACKEND_URL}/api/docs"
printf "║   %-22s : %-45s║\n" "Health Endpoint"    "${BACKEND_URL}/health  → $API_STATUS"
echo "║                                                                      ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  RUNNING PORTS                                                       ║"
printf "║   %-22s : %-45s║\n" "Frontend Port"  "${FRONTEND_PORT}  (Next.js 15 + React 19)"
printf "║   %-22s : %-45s║\n" "Backend Port"   "${BACKEND_PORT}  (FastAPI 0.115.5 + uvicorn)"
echo "║                                                                      ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  SERVICE STATUS                                                      ║"
printf "║   %-22s : " "bilvantis-backend"
echo -e "$(svc_colour "$BE_ACTIVE") (${BE_ENABLED})  PID=${BE_PID}$(printf '%*s' $((20 - ${#BE_PID})) '')║"
printf "║   %-22s : " "bilvantis-frontend"
echo -e "$(svc_colour "$FE_ACTIVE") (${FE_ENABLED})  PID=${FE_PID}$(printf '%*s' $((20 - ${#FE_PID})) '')║"
echo "║                                                                      ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  CONFIGURATION                                                       ║"
printf "║   %-22s : %-45s║\n" "Groq AI"       "$GROQ_DISP"
printf "║   %-22s : %-45s║\n" "Email SMTP"    "$SMTP_DISP"
printf "║   %-22s : %-45s║\n" "Database"      "$DB_DISP"
printf "║   %-22s : %-45s║\n" "Queue Broker"  "memory:// (embedded Celery)"
echo "║                                                                      ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  ADMIN ACCESS                                                        ║"
printf "║   %-22s : %-45s║\n" "Login URL"     "${FRONTEND_URL}/admin/login"
printf "║   %-22s : %-45s║\n" "Admin Email"   "admin@bilvantis.io"
printf "║   %-22s : %-45s║\n" "Admin Password" "Admin@1234"
echo "║                                                                      ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║  USEFUL COMMANDS                                                     ║"
printf "║   %-22s : %-45s║\n" "View backend log"  "tail -f ${LOG_DIR}/backend.log"
printf "║   %-22s : %-45s║\n" "View frontend log" "tail -f ${LOG_DIR}/frontend.log"
printf "║   %-22s : %-45s║\n" "Stop services"     "bash ${APP_DIR}/stop.sh"
printf "║   %-22s : %-45s║\n" "Restart services"  "bash ${APP_DIR}/restart.sh"
printf "║   %-22s : %-45s║\n" "Health check"      "bash ${APP_DIR}/healthcheck.sh"
printf "║   %-22s : %-45s║\n" "Backend status"    "sudo systemctl status bilvantis-backend"
printf "║   %-22s : %-45s║\n" "Full logs"         "sudo journalctl -u bilvantis-backend -f"
echo "║                                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}${BOLD}ACTION REQUIRED — Open firewall ports:${NC}"
echo -e "  ${CYAN}sudo ufw allow ${FRONTEND_PORT}/tcp && sudo ufw allow ${BACKEND_PORT}/tcp && sudo ufw reload${NC}"
echo ""
echo -e "${YELLOW}${BOLD}Then open in your browser:${NC}"
echo -e "  ${BOLD}${GREEN}${FRONTEND_URL}/admin/login${NC}"
echo ""

echo "=== Deploy finished $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$DEPLOY_LOG"
