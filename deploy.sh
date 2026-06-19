#!/usr/bin/env bash
# =============================================================================
#  Bilvantis Training Intelligence Platform — Cross-Platform Deploy Script
#  Version : 3.0
#  Supports: Ubuntu · Debian · CentOS · RHEL · Rocky · AlmaLinux · Fedora
#            Amazon Linux 2/2023 · openSUSE · Alpine · Arch/Manjaro
#  Stack   : Python 3.12 + FastAPI (port 8002) | Next.js 15 (port 3003)
#  DB      : SQLite embedded — no external server needed
#  Queue   : Celery memory:// — no Redis needed
#
#  Usage   : sudo bash deploy.sh [OPTIONS]
#  Options :
#    --groq-key  <KEY>    Groq API key (required for AI chat)
#    --smtp-user <EMAIL>  Gmail address for email notifications
#    --smtp-pass <PASS>   Gmail App Password (16-char)
#    --port-backend  <N>  Backend API port  (default: 8002)
#    --port-frontend <N>  Frontend port     (default: 3003)
#    --no-systemd         Use PID-file management instead of systemd
# =============================================================================
set -euo pipefail
IFS=$'\n\t'

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

LOG_FILE=""
_log() { local l="$1" c="$2"; shift 2
         echo -e "${c}[${l}]${NC} $*"
         [[ -n "$LOG_FILE" ]] && echo "[${l}] $*" >> "$LOG_FILE" 2>/dev/null || true; }
info()    { _log "INFO " "$CYAN"   "$*"; }
success() { _log "OK   " "$GREEN"  "$*"; }
warn()    { _log "WARN " "$YELLOW" "$*"; }
step()    { echo -e "\n${BOLD}${BLUE}━━━ $* ━━━${NC}"; }
die()     { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ── Arguments ─────────────────────────────────────────────────────────────────
GROQ_KEY=""; SMTP_USER=""; SMTP_PASS=""
BACKEND_PORT=8002; FRONTEND_PORT=3003; SKIP_SYSTEMD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --groq-key)       GROQ_KEY="$2";       shift 2 ;;
    --smtp-user)      SMTP_USER="$2";      shift 2 ;;
    --smtp-pass)      SMTP_PASS="$2";      shift 2 ;;
    --port-backend)   BACKEND_PORT="$2";   shift 2 ;;
    --port-frontend)  FRONTEND_PORT="$2";  shift 2 ;;
    --no-systemd)     SKIP_SYSTEMD=1;      shift   ;;
    -h|--help)        grep '^#  ' "$0" | sed 's/^#  //'; exit 0 ;;
    *) warn "Unknown argument: $1"; shift ;;
  esac
done

[[ $EUID -ne 0 ]] && die "Run as root: sudo bash deploy.sh"

# ── Paths ─────────────────────────────────────────────────────────────────────
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

RUN_USER="${SUDO_USER:-root}"
RUN_GROUP="$(id -gn "$RUN_USER" 2>/dev/null || echo "$RUN_USER")"
PYTHON_BIN=""      # resolved after installation
INIT_SYSTEM="none" # systemd | openrc | none

# ── OS Detection ──────────────────────────────────────────────────────────────
detect_os() {
  [[ ! -f /etc/os-release ]] && die "/etc/os-release not found. Unsupported OS."
  # shellcheck source=/dev/null
  . /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_VER="${VERSION_ID:-0}"
  OS_LIKE="${ID_LIKE:-}"

  case "$OS_ID" in
    ubuntu|debian|raspbian|linuxmint|pop) DISTRO="debian" ;;
    centos|rhel|ol)                        DISTRO="rhel"   ;;
    rocky|almalinux)                       DISTRO="rhel"   ;;
    fedora)                                DISTRO="fedora" ;;
    amzn)                                  DISTRO="amazon" ;;
    opensuse*|sles)                        DISTRO="suse"   ;;
    alpine)                                DISTRO="alpine" ;;
    arch|manjaro|endeavouros)              DISTRO="arch"   ;;
    *)
      if   [[ "$OS_LIKE" == *"debian"* ]]; then DISTRO="debian"
      elif [[ "$OS_LIKE" == *"rhel"*   || "$OS_LIKE" == *"fedora"* ]]; then DISTRO="rhel"
      else DISTRO="unknown"; fi
      ;;
  esac

  # Detect package manager
  if   command -v apt-get  &>/dev/null; then PKG_MGR="apt"
  elif command -v dnf      &>/dev/null; then PKG_MGR="dnf"
  elif command -v yum      &>/dev/null; then PKG_MGR="yum"
  elif command -v zypper   &>/dev/null; then PKG_MGR="zypper"
  elif command -v apk      &>/dev/null; then PKG_MGR="apk"
  elif command -v pacman   &>/dev/null; then PKG_MGR="pacman"
  else PKG_MGR="unknown"; fi

  # Detect init system
  if   command -v systemctl &>/dev/null && systemctl --version &>/dev/null 2>&1; then INIT_SYSTEM="systemd"
  elif command -v rc-service &>/dev/null;                                          then INIT_SYSTEM="openrc"
  fi

  info "OS: ${OS_ID} ${OS_VER} (family: ${DISTRO}, pkg: ${PKG_MGR}, init: ${INIT_SYSTEM})"
}

# ── System package installation (cross-distro) ────────────────────────────────
install_base_packages() {
  info "Installing base system packages..."
  case "$PKG_MGR" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -qq >> "$DEPLOY_LOG" 2>&1
      apt-get install -y -qq \
        curl wget git unzip ca-certificates gnupg build-essential \
        libssl-dev libffi-dev libsqlite3-dev sqlite3 procps \
        >> "$DEPLOY_LOG" 2>&1
      ;;
    dnf|yum)
      $PKG_MGR install -y \
        curl wget git unzip ca-certificates gnupg2 gcc gcc-c++ make \
        openssl-devel libffi-devel sqlite sqlite-devel procps-ng \
        >> "$DEPLOY_LOG" 2>&1
      ;;
    zypper)
      zypper install -y --no-recommends \
        curl wget git unzip ca-certificates gpg2 gcc make \
        libopenssl-devel libffi-devel sqlite3 sqlite3-devel procps \
        >> "$DEPLOY_LOG" 2>&1
      ;;
    apk)
      apk add --no-cache \
        curl wget git unzip ca-certificates gnupg build-base \
        openssl-dev libffi-dev sqlite sqlite-dev procps \
        >> "$DEPLOY_LOG" 2>&1
      ;;
    pacman)
      pacman -Syu --noconfirm \
        curl wget git unzip ca-certificates gnupg base-devel \
        openssl libffi sqlite procps-ng \
        >> "$DEPLOY_LOG" 2>&1
      ;;
    *) warn "Unknown package manager; skipping base package install" ;;
  esac
  success "Base packages installed"
}

# ── Python 3.12 installation ──────────────────────────────────────────────────
find_python312() {
  for bin in python3.12 python3 python; do
    if command -v "$bin" &>/dev/null; then
      local v; v=$("$bin" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || echo "0.0")
      if [[ "$v" == "3.12" ]]; then
        PYTHON_BIN="$(command -v "$bin")"
        return 0
      fi
    fi
  done
  return 1
}

install_python312_from_source() {
  local PYVER="3.12.7"
  info "Compiling Python ${PYVER} from source (5-10 min)..."

  # Build dependencies by distro
  case "$PKG_MGR" in
    apt)    apt-get install -y -qq make gcc libssl-dev zlib1g-dev libbz2-dev \
              libreadline-dev libsqlite3-dev libncurses5-dev libffi-dev xz-utils \
              >> "$DEPLOY_LOG" 2>&1 ;;
    dnf|yum) $PKG_MGR install -y make gcc openssl-devel zlib-devel bzip2-devel \
              readline-devel sqlite-devel ncurses-devel libffi-devel xz \
              >> "$DEPLOY_LOG" 2>&1 ;;
    zypper) zypper install -y --no-recommends make gcc libopenssl-devel zlib-devel \
              libbz2-devel readline-devel sqlite3-devel ncurses-devel libffi-devel xz \
              >> "$DEPLOY_LOG" 2>&1 ;;
    apk)    apk add --no-cache make gcc musl-dev openssl-dev zlib-dev bzip2-dev \
              readline-dev sqlite-dev ncurses-dev libffi-dev xz-dev \
              >> "$DEPLOY_LOG" 2>&1 ;;
  esac

  local BUILD="/tmp/py-build-$$"
  mkdir -p "$BUILD"
  curl -sL "https://www.python.org/ftp/python/${PYVER}/Python-${PYVER}.tgz" \
       -o "$BUILD/py.tgz" >> "$DEPLOY_LOG" 2>&1
  tar -xf "$BUILD/py.tgz" -C "$BUILD" >> "$DEPLOY_LOG" 2>&1
  cd "$BUILD/Python-${PYVER}"
  ./configure --enable-optimizations --with-ensurepip=install \
              --prefix=/usr/local --enable-shared \
              LDFLAGS="-Wl,-rpath /usr/local/lib" \
              >> "$DEPLOY_LOG" 2>&1
  make -j"$(nproc 2>/dev/null || echo 2)" >> "$DEPLOY_LOG" 2>&1
  make altinstall >> "$DEPLOY_LOG" 2>&1
  cd "$APP_DIR"
  rm -rf "$BUILD"
  ldconfig 2>/dev/null || true
  PYTHON_BIN=$(command -v python3.12 || echo "/usr/local/bin/python3.12")
}

install_python312() {
  find_python312 && { success "Python 3.12 already available: $PYTHON_BIN"; return; }

  info "Installing Python 3.12..."
  case "$DISTRO" in
    debian)
      if [[ "$OS_ID" == "ubuntu" ]]; then
        apt-get install -y -qq software-properties-common >> "$DEPLOY_LOG" 2>&1
        add-apt-repository -y ppa:deadsnakes/ppa          >> "$DEPLOY_LOG" 2>&1
        apt-get update -qq                                 >> "$DEPLOY_LOG" 2>&1
        apt-get install -y -qq python3.12 python3.12-venv python3.12-dev >> "$DEPLOY_LOG" 2>&1
      else
        # Debian Bookworm+ has 3.11; try native then source
        apt-get install -y -qq python3.12 python3.12-venv python3.12-dev >> "$DEPLOY_LOG" 2>&1 || \
          install_python312_from_source
      fi ;;
    rhel|fedora)
      # RHEL/CentOS 9+ and Fedora 38+ have python3.12 in AppStream / default repos
      # RHEL/CentOS 8: EPEL may be needed
      if [[ "$PKG_MGR" == "dnf" ]]; then
        # Try enabling EPEL for RHEL/CentOS 8 family
        if [[ "${OS_VER%%.*}" -le 8 ]] && command -v subscription-manager &>/dev/null 2>/dev/null; then
          dnf install -y epel-release >> "$DEPLOY_LOG" 2>&1 || true
        fi
        dnf install -y python3.12 python3.12-devel >> "$DEPLOY_LOG" 2>&1 || \
          install_python312_from_source
      else
        yum install -y python3.12 python3.12-devel >> "$DEPLOY_LOG" 2>&1 || \
          install_python312_from_source
      fi ;;
    amazon)
      # Amazon Linux 2023: python3.12 available
      # Amazon Linux 2: must compile
      if [[ "$OS_VER" == "2023"* ]]; then
        dnf install -y python3.12 python3.12-devel >> "$DEPLOY_LOG" 2>&1 || \
          install_python312_from_source
      else
        install_python312_from_source
      fi ;;
    suse)
      zypper install -y python312 python312-devel >> "$DEPLOY_LOG" 2>&1 || \
        install_python312_from_source ;;
    alpine)
      # Alpine 3.19+ has python 3.12 in community
      apk add --no-cache python3 python3-dev py3-pip >> "$DEPLOY_LOG" 2>&1
      # Verify version; compile if < 3.12
      find_python312 || install_python312_from_source ;;
    arch)
      # Arch always has the latest Python
      pacman -S --noconfirm python >> "$DEPLOY_LOG" 2>&1 ;;
    *)
      warn "Unknown distro — attempting source compile"
      install_python312_from_source ;;
  esac

  # Ensure pip works
  find_python312 || die "Python 3.12 installation failed. Check $DEPLOY_LOG"
  if ! "$PYTHON_BIN" -m pip --version &>/dev/null 2>&1; then
    curl -sS https://bootstrap.pypa.io/get-pip.py | "$PYTHON_BIN" >> "$DEPLOY_LOG" 2>&1
  fi
  success "Python: $($PYTHON_BIN --version 2>&1)  [$PYTHON_BIN]"
}

# ── Node.js 20 installation ───────────────────────────────────────────────────
find_node20() {
  command -v node &>/dev/null || return 1
  local major; major=$(node -v 2>/dev/null | cut -d. -f1 | tr -d 'v')
  [[ "${major:-0}" -ge 20 ]]
}

install_nodejs_nvm() {
  info "Installing Node.js 20 via nvm (fallback)..."
  export NVM_DIR="/usr/local/nvm"
  mkdir -p "$NVM_DIR"
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh \
    | NVM_DIR="$NVM_DIR" bash >> "$DEPLOY_LOG" 2>&1
  # shellcheck source=/dev/null
  . "$NVM_DIR/nvm.sh"
  nvm install 20 >> "$DEPLOY_LOG" 2>&1
  nvm use 20     >> "$DEPLOY_LOG" 2>&1
  nvm alias default 20 >> "$DEPLOY_LOG" 2>&1
  # Symlink into PATH
  local NODE_PATH; NODE_PATH=$(nvm which current 2>/dev/null)
  ln -sf "$NODE_PATH"             /usr/local/bin/node 2>/dev/null || true
  ln -sf "$(dirname "$NODE_PATH")/npm"  /usr/local/bin/npm  2>/dev/null || true
  ln -sf "$(dirname "$NODE_PATH")/npx"  /usr/local/bin/npx  2>/dev/null || true
}

install_nodejs20() {
  find_node20 && { success "Node.js $(node --version) already installed"; return; }
  info "Installing Node.js 20 LTS..."
  case "$DISTRO" in
    debian)
      curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >> "$DEPLOY_LOG" 2>&1
      apt-get install -y -qq nodejs >> "$DEPLOY_LOG" 2>&1 ;;
    rhel|fedora|amazon)
      curl -fsSL https://rpm.nodesource.com/setup_20.x | bash - >> "$DEPLOY_LOG" 2>&1
      ${PKG_MGR} install -y nodejs >> "$DEPLOY_LOG" 2>&1 ;;
    suse)
      # Try zypper; fall back to nvm
      zypper install -y nodejs20 npm20 >> "$DEPLOY_LOG" 2>&1 || install_nodejs_nvm ;;
    alpine)
      apk add --no-cache nodejs npm >> "$DEPLOY_LOG" 2>&1 ;;
    arch)
      pacman -S --noconfirm nodejs npm >> "$DEPLOY_LOG" 2>&1 ;;
    *)
      install_nodejs_nvm ;;
  esac
  find_node20 || die "Node.js 20 installation failed. Check $DEPLOY_LOG"
  success "Node.js: $(node --version)  |  npm: $(npm --version)"
}

# ── Network helpers ───────────────────────────────────────────────────────────
get_vm_ip() {
  hostname -I 2>/dev/null | awk '{print $1}' && return
  ip route get 1.1.1.1 2>/dev/null | awk '/src/{print $7; exit}' && return
  ip addr show 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1 | grep -v 127 | head -1 && return
  echo "127.0.0.1"
}

port_in_use() { ss -tlnp 2>/dev/null | grep -q ":$1 " || netstat -tlnp 2>/dev/null | grep -q ":$1 "; }

# =============================================================================
# ── Banner ────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${BLUE}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║   Bilvantis Training Intelligence Platform — Deploy v3.0            ║"
echo "║   Cross-platform Linux  •  Python 3.12  •  Node.js 20              ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
info "App dir        : $APP_DIR"
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
success "Shell scripts: Unix line endings + executable"

# =============================================================================
step "2 / 9  Detect OS and install system packages"
# =============================================================================
detect_os
install_base_packages
install_python312
install_nodejs20

# =============================================================================
step "3 / 9  Python virtual environment and pip packages"
# =============================================================================
[[ ! -f "$BACKEND_DIR/requirements.txt" ]] && die "requirements.txt missing at $BACKEND_DIR"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  info "Creating Python venv at $VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR" >> "$DEPLOY_LOG" 2>&1
fi

info "Upgrading pip / setuptools / wheel..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip setuptools wheel >> "$DEPLOY_LOG" 2>&1

info "Installing Python packages (25 packages from requirements.txt)..."
"$VENV_DIR/bin/pip" install --quiet --timeout 300 \
  -r "$BACKEND_DIR/requirements.txt" >> "$DEPLOY_LOG" 2>&1

PKG_COUNT=$("$VENV_DIR/bin/pip" list 2>/dev/null | tail -n +3 | wc -l)
success "Python venv ready ($PKG_COUNT packages)"

# =============================================================================
step "4 / 9  Detect IP and configure environment"
# =============================================================================
VM_IP=$(get_vm_ip)
info "VM IP : $VM_IP"
BACKEND_URL="http://${VM_IP}:${BACKEND_PORT}"
FRONTEND_URL="http://${VM_IP}:${FRONTEND_PORT}"
SECRET_KEY=$("$PYTHON_BIN" -c "import secrets; print(secrets.token_hex(32))")

BACKEND_ENV="$BACKEND_DIR/.env"

[[ -z "$GROQ_KEY" ]] && warn "No --groq-key provided. AI analytics chat will be disabled until you set GROQ_API_KEY in backend/.env"

if [[ ! -f "$BACKEND_ENV" ]]; then
  info "Writing backend/.env ..."
  cat > "$BACKEND_ENV" <<ENVEOF
# Bilvantis TIP — Backend Environment
# Generated: $(date '+%Y-%m-%d %H:%M:%S')  Host: $(hostname)  IP: ${VM_IP}
# DO NOT commit this file — it contains secrets.

# Database (SQLite — embedded, no server)
DATABASE_URL=sqlite+aiosqlite:///./feedback_platform.db
SYNC_DATABASE_URL=sqlite:///./feedback_platform.db

# Queue (Celery in-memory — no Redis server required)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=memory://
CELERY_RESULT_BACKEND=cache+memory://

# Security
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FEEDBACK_TOKEN_EXPIRE_HOURS=72

# AI — Groq (required for analytics chat)
# Get a free key at https://console.groq.com/keys
GROQ_API_KEY=${GROQ_KEY}
GEMINI_API_KEY=

# Email — Gmail SMTP (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=${SMTP_USER}
SMTP_PASSWORD=${SMTP_PASS}
SMTP_FROM_EMAIL=${SMTP_USER}
SMTP_FROM_NAME=Bilvantis TIP

# SendGrid alternative (leave blank to use SMTP)
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=noreply@bilvantis.io

# Application URLs (auto-detected)
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
  success "Created backend/.env (permissions: 600)"
else
  warn "backend/.env exists — updating URLs only (secrets preserved)"
  sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=${FRONTEND_URL}|" "$BACKEND_ENV"
  sed -i "s|^BACKEND_URL=.*|BACKEND_URL=${BACKEND_URL}|"   "$BACKEND_ENV"
  [[ -n "$GROQ_KEY"  ]] && sed -i "s|^GROQ_API_KEY=.*|GROQ_API_KEY=${GROQ_KEY}|"     "$BACKEND_ENV"
  [[ -n "$SMTP_USER" ]] && sed -i "s|^SMTP_USER=.*|SMTP_USER=${SMTP_USER}|"           "$BACKEND_ENV"
  [[ -n "$SMTP_PASS" ]] && sed -i "s|^SMTP_PASSWORD=.*|SMTP_PASSWORD=${SMTP_PASS}|"   "$BACKEND_ENV"
fi

cat > "$FRONTEND_DIR/.env.local" <<FEOF
NEXT_PUBLIC_API_URL=${BACKEND_URL}
NEXTAUTH_URL=${FRONTEND_URL}
FEOF
success "Created frontend/.env.local  (API → ${BACKEND_URL})"

# =============================================================================
step "5 / 9  Build Next.js frontend for production"
# =============================================================================
[[ ! -f "$FRONTEND_DIR/package.json" ]] && die "package.json missing at $FRONTEND_DIR"

info "npm install (may take 2-3 min on first run)..."
cd "$FRONTEND_DIR"
npm install --legacy-peer-deps --silent >> "$DEPLOY_LOG" 2>&1 || \
  npm install --legacy-peer-deps        >> "$DEPLOY_LOG" 2>&1

info "npm run build (NEXT_PUBLIC_API_URL=${BACKEND_URL})..."
NEXT_PUBLIC_API_URL="$BACKEND_URL" npm run build >> "$DEPLOY_LOG" 2>&1

[[ ! -d "$FRONTEND_DIR/.next" ]] && die "Next.js build failed — check: tail -50 $DEPLOY_LOG"
success "Next.js production build complete"
cd "$APP_DIR"

# =============================================================================
step "6 / 9  Validate backend configuration"
# =============================================================================
cd "$BACKEND_DIR"
"$VENV_DIR/bin/python" - <<'PYCHECK'
import sys
sys.path.insert(0, '.')
from app.core.config import Settings
s = Settings()
errors = []
if not s.DATABASE_URL: errors.append("DATABASE_URL is empty")
if not s.SECRET_KEY:   errors.append("SECRET_KEY is empty")
if errors:
    for e in errors: print(f"  FAIL: {e}", file=sys.stderr)
    sys.exit(1)
print(f"  DATABASE_URL  : {s.DATABASE_URL}")
print(f"  FRONTEND_URL  : {s.FRONTEND_URL}")
print(f"  BACKEND_URL   : {s.BACKEND_URL}")
groq = s.GROQ_API_KEY
print(f"  GROQ_API_KEY  : {(groq[:12]+'...') if groq else 'NOT SET (AI disabled)'}")
print(f"  SMTP_USER     : {s.SMTP_USER or '(not configured)'}")
print(f"  CELERY_BROKER : {s.CELERY_BROKER_URL}")
PYCHECK
success "Backend configuration valid"
cd "$APP_DIR"

# =============================================================================
step "7 / 9  Install and enable services"
# =============================================================================
NODE_BIN=$(command -v node)
chown -R "$RUN_USER:$RUN_GROUP" "$LOG_DIR" "$PID_DIR" "$BACKEND_DIR" 2>/dev/null || true

if [[ $SKIP_SYSTEMD -eq 0 && "$INIT_SYSTEM" == "systemd" ]]; then
  # ── systemd ─────────────────────────────────────────────────────────────────
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
WorkingDirectory=${BACKEND_DIR}
ExecStart=${VENV_DIR}/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port ${BACKEND_PORT} \
    --workers 1 --loop asyncio --log-level info
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
ExecStart=${NODE_BIN} node_modules/.bin/next start --port ${FRONTEND_PORT}
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

  systemctl daemon-reload
  systemctl enable bilvantis-backend bilvantis-frontend >> "$DEPLOY_LOG" 2>&1
  success "Systemd units installed + enabled (auto-start on reboot)"

elif [[ $SKIP_SYSTEMD -eq 0 && "$INIT_SYSTEM" == "openrc" ]]; then
  # ── OpenRC (Alpine) ──────────────────────────────────────────────────────────
  cat > /etc/init.d/bilvantis-backend <<RCEOF
#!/sbin/openrc-run
name="bilvantis-backend"
description="Bilvantis TIP FastAPI Backend"
command="${VENV_DIR}/bin/uvicorn"
command_args="app.main:app --host 0.0.0.0 --port ${BACKEND_PORT} --workers 1 --loop asyncio"
command_background=true
directory="${BACKEND_DIR}"
pidfile="${PID_DIR}/backend.pid"
logfile="${LOG_DIR}/backend.log"
command_user="${RUN_USER}"
start_pre() { mkdir -p "${LOG_DIR}" "${PID_DIR}"; }
RCEOF
  chmod +x /etc/init.d/bilvantis-backend

  cat > /etc/init.d/bilvantis-frontend <<RCEOF
#!/sbin/openrc-run
name="bilvantis-frontend"
description="Bilvantis TIP Next.js Frontend"
command="${NODE_BIN}"
command_args="${FRONTEND_DIR}/node_modules/.bin/next start --port ${FRONTEND_PORT}"
command_background=true
directory="${FRONTEND_DIR}"
pidfile="${PID_DIR}/frontend.pid"
logfile="${LOG_DIR}/frontend.log"
command_user="${RUN_USER}"
depend() { need bilvantis-backend; }
RCEOF
  chmod +x /etc/init.d/bilvantis-frontend

  rc-update add bilvantis-backend  default >> "$DEPLOY_LOG" 2>&1
  rc-update add bilvantis-frontend default >> "$DEPLOY_LOG" 2>&1
  success "OpenRC services installed + enabled"

else
  warn "No init system or --no-systemd: using PID-file management"
fi

# =============================================================================
step "8 / 9  Start services"
# =============================================================================
_stop_existing() {
  if [[ "$INIT_SYSTEM" == "systemd" && $SKIP_SYSTEMD -eq 0 ]]; then
    systemctl stop bilvantis-backend  2>/dev/null || true
    systemctl stop bilvantis-frontend 2>/dev/null || true
  elif [[ "$INIT_SYSTEM" == "openrc" && $SKIP_SYSTEMD -eq 0 ]]; then
    rc-service bilvantis-backend  stop 2>/dev/null || true
    rc-service bilvantis-frontend stop 2>/dev/null || true
  fi
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -f "next start"           2>/dev/null || true
  sleep 2
}
_stop_existing

_start_backend() {
  if [[ "$INIT_SYSTEM" == "systemd" && $SKIP_SYSTEMD -eq 0 ]]; then
    systemctl start bilvantis-backend
  elif [[ "$INIT_SYSTEM" == "openrc" && $SKIP_SYSTEMD -eq 0 ]]; then
    rc-service bilvantis-backend start
  else
    cd "$BACKEND_DIR"
    nohup "$VENV_DIR/bin/uvicorn" app.main:app \
      --host 0.0.0.0 --port "$BACKEND_PORT" \
      --workers 1 --loop asyncio --log-level info \
      >> "$LOG_DIR/backend.log" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"
    cd "$APP_DIR"
  fi
}

_start_frontend() {
  if [[ "$INIT_SYSTEM" == "systemd" && $SKIP_SYSTEMD -eq 0 ]]; then
    systemctl start bilvantis-frontend
  elif [[ "$INIT_SYSTEM" == "openrc" && $SKIP_SYSTEMD -eq 0 ]]; then
    rc-service bilvantis-frontend start
  else
    cd "$FRONTEND_DIR"
    nohup "$NODE_BIN" node_modules/.bin/next start --port "$FRONTEND_PORT" \
      >> "$LOG_DIR/frontend.log" 2>&1 &
    echo $! > "$PID_DIR/frontend.pid"
    cd "$APP_DIR"
  fi
}

info "Starting backend on port ${BACKEND_PORT}..."
_start_backend

BACKEND_READY=0; WSEC=0
while [[ $WSEC -lt 45 ]]; do
  curl -sf --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/health" &>/dev/null && { BACKEND_READY=1; break; }
  sleep 3; WSEC=$((WSEC+3)); echo -n "."
done; echo ""
[[ $BACKEND_READY -eq 1 ]] && success "Backend ready (${WSEC}s)" || warn "Backend not responding — check $LOG_DIR/backend.log"

info "Starting frontend on port ${FRONTEND_PORT}..."
_start_frontend

FRONTEND_READY=0; WSEC=0
while [[ $WSEC -lt 45 ]]; do
  HC=$(curl -so /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:${FRONTEND_PORT}" 2>/dev/null || echo "000")
  [[ "$HC" == "200" || "$HC" == "302" || "$HC" == "308" ]] && { FRONTEND_READY=1; break; }
  sleep 3; WSEC=$((WSEC+3)); echo -n "."
done; echo ""
[[ $FRONTEND_READY -eq 1 ]] && success "Frontend ready (${WSEC}s)" || warn "Frontend not responding — check $LOG_DIR/frontend.log"

# =============================================================================
step "9 / 9  Health check and status report"
# =============================================================================
bash "$APP_DIR/healthcheck.sh" 2>/dev/null || true

# ── Collect status ────────────────────────────────────────────────────────────
if [[ "$INIT_SYSTEM" == "systemd" && $SKIP_SYSTEMD -eq 0 ]]; then
  BE_ACTIVE=$(systemctl is-active  bilvantis-backend  2>/dev/null || echo "unknown")
  FE_ACTIVE=$(systemctl is-active  bilvantis-frontend 2>/dev/null || echo "unknown")
  BE_ENABLED=$(systemctl is-enabled bilvantis-backend  2>/dev/null || echo "unknown")
  FE_ENABLED=$(systemctl is-enabled bilvantis-frontend 2>/dev/null || echo "unknown")
  BE_PID=$(systemctl show -p MainPID --value bilvantis-backend  2>/dev/null | tr -d '\n' || echo "-")
  FE_PID=$(systemctl show -p MainPID --value bilvantis-frontend 2>/dev/null | tr -d '\n' || echo "-")
elif [[ "$INIT_SYSTEM" == "openrc" && $SKIP_SYSTEMD -eq 0 ]]; then
  BE_ACTIVE=$(rc-service bilvantis-backend  status 2>/dev/null | grep -q started && echo "active" || echo "stopped")
  FE_ACTIVE=$(rc-service bilvantis-frontend status 2>/dev/null | grep -q started && echo "active" || echo "stopped")
  BE_ENABLED="enabled"; FE_ENABLED="enabled"
  BE_PID=$(cat "$PID_DIR/backend.pid"  2>/dev/null || echo "-")
  FE_PID=$(cat "$PID_DIR/frontend.pid" 2>/dev/null || echo "-")
else
  BE_PID=$(cat "$PID_DIR/backend.pid"  2>/dev/null || pgrep -f "uvicorn app.main:app" | head -1 || echo "-")
  FE_PID=$(cat "$PID_DIR/frontend.pid" 2>/dev/null || pgrep -f "next start" | head -1 || echo "-")
  BE_ACTIVE=$([[ "$BE_PID" != "-" ]] && kill -0 "$BE_PID" 2>/dev/null && echo "active" || echo "stopped")
  FE_ACTIVE=$([[ "$FE_PID" != "-" ]] && kill -0 "$FE_PID" 2>/dev/null && echo "active" || echo "stopped")
  BE_ENABLED="manual"; FE_ENABLED="manual"
fi

GROQ_VAL=$(grep "^GROQ_API_KEY=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
GROQ_DISP=$([[ "$GROQ_VAL" == gsk_* ]] && echo "${GROQ_VAL:0:12}... ✓" || echo "NOT SET — AI chat disabled")
SMTP_VAL=$(grep "^SMTP_USER=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
SMTP_DISP="${SMTP_VAL:-not configured}"
HEALTH_JSON=$(curl -sf --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || echo '{"status":"unreachable"}')
API_STATUS=$("$VENV_DIR/bin/python" -c "import sys,json; d=json.loads('$HEALTH_JSON'); print(d.get('status','?'))" 2>/dev/null || echo "?")
DB_PATH="$BACKEND_DIR/feedback_platform.db"
DB_DISP=$([[ -f "$DB_PATH" ]] && echo "$(du -sh "$DB_PATH" | cut -f1) at $DB_PATH" || echo "will be created on first start")

sc() { [[ "$1" == "active" ]] && printf '%s' "${GREEN}active${NC}" || printf '%s' "${RED}${1}${NC}"; }

echo ""
echo -e "${BOLD}${GREEN}"
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║   ✓  Bilvantis TIP — Deployment Complete                            ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
printf "║  %-24s : %-43s║\n" "VM IP Address"     "$VM_IP"
printf "║  %-24s : %-43s║\n" "Application URL"   "$FRONTEND_URL/admin/login"
printf "║  %-24s : %-43s║\n" "Backend API URL"   "$BACKEND_URL"
printf "║  %-24s : %-43s║\n" "API Docs"          "$BACKEND_URL/api/docs"
printf "║  %-24s : %-43s║\n" "Health Check"      "$BACKEND_URL/health  → $API_STATUS"
echo "╠══════════════════════════════════════════════════════════════════════╣"
printf "║  %-24s : %-43s║\n" "Frontend Port"     "$FRONTEND_PORT  (Next.js 15)"
printf "║  %-24s : %-43s║\n" "Backend Port"      "$BACKEND_PORT  (FastAPI + uvicorn)"
printf "║  %-24s : %-43s║\n" "OS / Init"         "${OS_ID} ${OS_VER} / ${INIT_SYSTEM}"
echo "╠══════════════════════════════════════════════════════════════════════╣"
printf "║  %-24s : " "bilvantis-backend"
echo -e "$(sc "$BE_ACTIVE") (${BE_ENABLED})  PID=${BE_PID}$(printf '%*s' $((18-${#BE_PID})) '')║"
printf "║  %-24s : " "bilvantis-frontend"
echo -e "$(sc "$FE_ACTIVE") (${FE_ENABLED})  PID=${FE_PID}$(printf '%*s' $((18-${#FE_PID})) '')║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
printf "║  %-24s : %-43s║\n" "Groq AI"           "$GROQ_DISP"
printf "║  %-24s : %-43s║\n" "Email SMTP"        "$SMTP_DISP"
printf "║  %-24s : %-43s║\n" "Database"          "$DB_DISP"
printf "║  %-24s : %-43s║\n" "Queue"             "Celery memory:// (embedded)"
echo "╠══════════════════════════════════════════════════════════════════════╣"
printf "║  %-24s : %-43s║\n" "Admin Login"       "$FRONTEND_URL/admin/login"
printf "║  %-24s : %-43s║\n" "Admin Email"       "admin@bilvantis.io"
printf "║  %-24s : %-43s║\n" "Admin Password"    "Admin@1234"
echo "╠══════════════════════════════════════════════════════════════════════╣"
printf "║  %-24s : %-43s║\n" "Logs"              "tail -f $LOG_DIR/backend.log"
printf "║  %-24s : %-43s║\n" "Stop"              "bash $APP_DIR/stop.sh"
printf "║  %-24s : %-43s║\n" "Restart"           "bash $APP_DIR/restart.sh"
printf "║  %-24s : %-43s║\n" "Health"            "bash $APP_DIR/healthcheck.sh"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${YELLOW}${BOLD}Open firewall ports (if needed):${NC}"
case "$PKG_MGR" in
  apt)     echo -e "  ${CYAN}sudo ufw allow ${FRONTEND_PORT}/tcp && sudo ufw allow ${BACKEND_PORT}/tcp && sudo ufw reload${NC}" ;;
  dnf|yum) echo -e "  ${CYAN}sudo firewall-cmd --permanent --add-port=${FRONTEND_PORT}/tcp --add-port=${BACKEND_PORT}/tcp && sudo firewall-cmd --reload${NC}" ;;
  apk)     echo -e "  ${CYAN}iptables -A INPUT -p tcp --dport ${FRONTEND_PORT} -j ACCEPT && iptables -A INPUT -p tcp --dport ${BACKEND_PORT} -j ACCEPT${NC}" ;;
  *)       echo -e "  Open ports ${FRONTEND_PORT} and ${BACKEND_PORT} in your firewall." ;;
esac
echo ""
echo -e "${GREEN}${BOLD}Open in browser: ${FRONTEND_URL}/admin/login${NC}"
echo ""
echo "=== Deploy finished $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$DEPLOY_LOG"
