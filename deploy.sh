#!/usr/bin/env bash
# =============================================================================
# Bilvantis Training Intelligence Platform — Full Deployment Script
# =============================================================================
# Stack : Python 3.12 + FastAPI (port 8002) + Next.js 15 (port 3003)
# DB    : SQLite (embedded — no server required)
# Queue : fakeredis / memory:// (no Redis server required)
# AI    : Groq API (external)
# Run   : sudo bash deploy.sh [--groq-key <KEY>] [--smtp-user <EMAIL>] [--smtp-pass <PASS>]
# =============================================================================

set -euo pipefail

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
step()    { echo -e "\n${BOLD}${BLUE}══ $* ══${NC}"; }
die()     { error "$*"; exit 1; }

# ── Parse CLI args ─────────────────────────────────────────────────────────────
GROQ_API_KEY_ARG=""
SMTP_USER_ARG=""
SMTP_PASS_ARG=""
SKIP_SYSTEMD=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --groq-key)   GROQ_API_KEY_ARG="$2"; shift 2 ;;
    --smtp-user)  SMTP_USER_ARG="$2";    shift 2 ;;
    --smtp-pass)  SMTP_PASS_ARG="$2";    shift 2 ;;
    --no-systemd) SKIP_SYSTEMD=1;        shift   ;;
    *)            shift ;;
  esac
done

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$APP_DIR/logs"
PID_DIR="$APP_DIR/run"

BACKEND_PORT=8002
FRONTEND_PORT=3003
PYTHON_VERSION="3.12"
NODE_VERSION="20"

BANNER="
╔══════════════════════════════════════════════════════════════════╗
║   Bilvantis Training Intelligence Platform — Deployment          ║
║   Backend  : http://\$(hostname -I | awk '{print \$1}'):${BACKEND_PORT}        ║
║   Frontend : http://\$(hostname -I | awk '{print \$1}'):${FRONTEND_PORT}       ║
║   API Docs : http://\$(hostname -I | awk '{print \$1}'):${BACKEND_PORT}/api/docs ║
╚══════════════════════════════════════════════════════════════════╝"

# ── Root check ─────────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  die "This script must be run as root: sudo bash deploy.sh"
fi

# ── OS detection ───────────────────────────────────────────────────────────────
detect_os() {
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_VERSION="${VERSION_ID:-0}"
    OS_LIKE="${ID_LIKE:-}"
  else
    die "Cannot detect OS. /etc/os-release not found."
  fi

  if [[ "$OS_ID" == "ubuntu" || "$OS_ID" == "debian" || "$OS_LIKE" == *"debian"* ]]; then
    PKG_MGR="apt"
  elif [[ "$OS_ID" == "centos" || "$OS_ID" == "rhel" || "$OS_ID" == "fedora" || "$OS_LIKE" == *"rhel"* ]]; then
    PKG_MGR="dnf"
  else
    warn "Unrecognised OS: $OS_ID. Attempting apt-based install."
    PKG_MGR="apt"
  fi

  info "Detected OS: ${OS_ID} ${OS_VERSION} (pkg manager: ${PKG_MGR})"
}

# ── Helpers ────────────────────────────────────────────────────────────────────
cmd_exists() { command -v "$1" &>/dev/null; }

check_python_version() {
  local py="$1"
  if cmd_exists "$py"; then
    local ver; ver=$("$py" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null)
    [[ "$ver" == "$PYTHON_VERSION" ]]
  else
    return 1
  fi
}

get_vm_ip() {
  hostname -I 2>/dev/null | awk '{print $1}' || \
  ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}' || \
  echo "127.0.0.1"
}

# =============================================================================
# STEP 1 — System packages
# =============================================================================
step "1/9 Installing system packages"

if [[ "$PKG_MGR" == "apt" ]]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq

  # Base tools
  apt-get install -y -qq \
    curl wget git unzip build-essential \
    ca-certificates gnupg lsb-release software-properties-common \
    libssl-dev libffi-dev libsqlite3-dev \
    sqlite3 \
    procps net-tools \
    2>/dev/null

  success "Base packages installed"

  # ── Python 3.12 ──
  if ! check_python_version python3.12; then
    info "Installing Python 3.12 via deadsnakes PPA..."
    add-apt-repository -y ppa:deadsnakes/python 2>/dev/null || \
    add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
    apt-get update -qq
    apt-get install -y -qq python3.12 python3.12-venv python3.12-dev python3.12-distutils 2>/dev/null || \
    apt-get install -y -qq python3.12 python3.12-venv python3.12-dev 2>/dev/null
  fi

  if ! check_python_version python3.12; then
    # Try compiling from source as last resort
    warn "PPA install failed — compiling Python 3.12 from source (this takes ~5 min)..."
    apt-get install -y -qq zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
      libncurses5-dev libxml2-dev libxmlsec1-dev xz-utils tk-dev liblzma-dev 2>/dev/null
    cd /tmp
    rm -rf Python-3.12.7
    wget -q "https://www.python.org/ftp/python/3.12.7/Python-3.12.7.tgz"
    tar -xf Python-3.12.7.tgz
    cd Python-3.12.7
    ./configure --enable-optimizations --with-ensurepip=install --prefix=/usr/local 2>/dev/null
    make -j"$(nproc)" 2>/dev/null
    make altinstall 2>/dev/null
    cd "$APP_DIR"
  fi

  # ── pip for Python 3.12 ──
  if ! python3.12 -m pip --version &>/dev/null; then
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.12
  fi

  # ── Node.js 20 LTS ──
  if ! cmd_exists node || [[ $(node -v 2>/dev/null | cut -d. -f1 | tr -d 'v') -lt $NODE_VERSION ]]; then
    info "Installing Node.js ${NODE_VERSION} LTS..."
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_VERSION}.x" | bash - 2>/dev/null
    apt-get install -y -qq nodejs
  fi

else
  # ── RHEL/CentOS/Fedora ──
  dnf update -y -q 2>/dev/null || yum update -y -q 2>/dev/null

  dnf install -y -q \
    curl wget git unzip gcc gcc-c++ make \
    openssl-devel libffi-devel sqlite sqlite-devel \
    procps net-tools \
    2>/dev/null || \
  yum install -y -q \
    curl wget git unzip gcc gcc-c++ make \
    openssl-devel libffi-devel sqlite sqlite-devel \
    procps net-tools \
    2>/dev/null

  success "Base packages installed"

  # Python 3.12 on RHEL
  if ! check_python_version python3.12; then
    info "Installing Python 3.12..."
    dnf install -y python3.12 python3.12-devel 2>/dev/null || {
      # CentOS 7/8 fallback: compile from source
      warn "Building Python 3.12 from source..."
      dnf install -y bzip2-devel readline-devel ncurses-devel \
        tk-devel libxml2-devel xz-devel 2>/dev/null || true
      cd /tmp
      rm -rf Python-3.12.7
      wget -q "https://www.python.org/ftp/python/3.12.7/Python-3.12.7.tgz"
      tar -xf Python-3.12.7.tgz
      cd Python-3.12.7
      ./configure --enable-optimizations --with-ensurepip=install --prefix=/usr/local 2>/dev/null
      make -j"$(nproc)" 2>/dev/null
      make altinstall 2>/dev/null
      cd "$APP_DIR"
    }
  fi

  # Node.js 20
  if ! cmd_exists node || [[ $(node -v 2>/dev/null | cut -d. -f1 | tr -d 'v') -lt $NODE_VERSION ]]; then
    info "Installing Node.js ${NODE_VERSION} LTS..."
    curl -fsSL "https://rpm.nodesource.com/setup_${NODE_VERSION}.x" | bash - 2>/dev/null
    dnf install -y nodejs 2>/dev/null || yum install -y nodejs 2>/dev/null
  fi
fi

# Verify
PYTHON_BIN=$(command -v python3.12 || command -v python3 || echo "")
[[ -z "$PYTHON_BIN" ]] && die "Python 3.12 not found after install."
NODE_BIN=$(command -v node || echo "")
[[ -z "$NODE_BIN" ]] && die "Node.js not found after install."
NPM_BIN=$(command -v npm || echo "")
[[ -z "$NPM_BIN" ]] && die "npm not found after install."

PYTHON_VER=$("$PYTHON_BIN" --version 2>&1)
NODE_VER=$("$NODE_BIN" --version 2>&1)
success "Python: $PYTHON_VER"
success "Node:   $NODE_VER"
success "npm:    $(npm --version)"

# =============================================================================
# STEP 2 — Create directories
# =============================================================================
step "2/9 Creating directories"

mkdir -p "$LOG_DIR" "$PID_DIR"
chmod 755 "$LOG_DIR" "$PID_DIR"
success "Created: logs/, run/"

# =============================================================================
# STEP 3 — Python virtual environment + pip packages
# =============================================================================
step "3/9 Setting up Python virtual environment"

cd "$BACKEND_DIR"

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
  info "Creating venv at $VENV_DIR ..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

info "Upgrading pip/setuptools/wheel..."
pip install --quiet --upgrade pip setuptools wheel 2>/dev/null

info "Installing Python packages from requirements.txt ..."
pip install --quiet -r requirements.txt

success "Python dependencies installed ($(pip list 2>/dev/null | wc -l) packages)"
deactivate
cd "$APP_DIR"

# =============================================================================
# STEP 4 — Environment configuration
# =============================================================================
step "4/9 Configuring environment"

VM_IP=$(get_vm_ip)
info "Detected VM IP: $VM_IP"

# ── Generate secret key ──
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || \
             openssl rand -hex 32 2>/dev/null || \
             echo "bilvantis-tip-$(date +%s)-$(hostname | md5sum | cut -c1-16)")

BACKEND_URL="http://${VM_IP}:${BACKEND_PORT}"
FRONTEND_URL="http://${VM_IP}:${FRONTEND_PORT}"

# ── Write backend .env ──
BACKEND_ENV="$BACKEND_DIR/.env"
if [[ ! -f "$BACKEND_ENV" ]]; then
  info "Creating backend/.env ..."
  cat > "$BACKEND_ENV" <<ENVEOF
# ── Database ── (SQLite, no server required)
DATABASE_URL=sqlite+aiosqlite:///./feedback_platform.db
SYNC_DATABASE_URL=sqlite:///./feedback_platform.db

# ── Cache/Queue ── (in-memory, no Redis required)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=memory://
CELERY_RESULT_BACKEND=cache+memory://

# ── Security ──
SECRET_KEY=${SECRET_KEY}
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FEEDBACK_TOKEN_EXPIRE_HOURS=72

# ── AI ── (Required: get key from console.groq.com)
GROQ_API_KEY=${GROQ_API_KEY_ARG:-REPLACE_WITH_YOUR_GROQ_API_KEY}
GEMINI_API_KEY=

# ── Email ── (optional: Gmail App Password)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=${SMTP_USER_ARG:-}
SMTP_PASSWORD=${SMTP_PASS_ARG:-}
SMTP_FROM_EMAIL=${SMTP_USER_ARG:-}
SMTP_FROM_NAME=Bilvantis TIP
SENDGRID_API_KEY=

# ── URLs ── (auto-detected from VM IP)
FRONTEND_URL=${FRONTEND_URL}
BACKEND_URL=${BACKEND_URL}

# ── App settings ──
FEEDBACK_THRESHOLD=5
PGVECTOR_DIMENSION=768
APP_NAME=Bilvantis Training Intelligence Platform
APP_VERSION=1.0.0
DEBUG=False
ENVEOF
  success "Created backend/.env"
else
  warn "backend/.env already exists — skipping (delete it to regenerate)"
  # Update URLs in existing .env
  sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=${FRONTEND_URL}|" "$BACKEND_ENV"
  sed -i "s|^BACKEND_URL=.*|BACKEND_URL=${BACKEND_URL}|"   "$BACKEND_ENV"
  # Inject CLI-supplied keys if not already set
  [[ -n "$GROQ_API_KEY_ARG" ]] && sed -i "s|^GROQ_API_KEY=.*|GROQ_API_KEY=${GROQ_API_KEY_ARG}|" "$BACKEND_ENV"
  [[ -n "$SMTP_USER_ARG"   ]] && sed -i "s|^SMTP_USER=.*|SMTP_USER=${SMTP_USER_ARG}|"           "$BACKEND_ENV"
  [[ -n "$SMTP_PASS_ARG"   ]] && sed -i "s|^SMTP_PASSWORD=.*|SMTP_PASSWORD=${SMTP_PASS_ARG}|"   "$BACKEND_ENV"
  success "Updated URLs in existing backend/.env"
fi

# ── Write frontend .env.local ──
FRONTEND_ENV="$FRONTEND_DIR/.env.local"
cat > "$FRONTEND_ENV" <<ENVEOF
NEXT_PUBLIC_API_URL=${BACKEND_URL}
NEXTAUTH_URL=${FRONTEND_URL}
ENVEOF
success "Created frontend/.env.local (API URL: ${BACKEND_URL})"

# ── GROQ key check ──
GROQ_KEY=$(grep "^GROQ_API_KEY=" "$BACKEND_ENV" | cut -d= -f2-)
if [[ -z "$GROQ_KEY" || "$GROQ_KEY" == "REPLACE_WITH_YOUR_GROQ_API_KEY" ]]; then
  warn "GROQ_API_KEY is not set. AI analytics chat will not work."
  warn "Set it in backend/.env or re-run: sudo bash deploy.sh --groq-key <KEY>"
fi

# =============================================================================
# STEP 5 — Frontend: install packages + build
# =============================================================================
step "5/9 Building Next.js frontend"

cd "$FRONTEND_DIR"

info "Installing npm packages (this may take a few minutes)..."
npm install --legacy-peer-deps --silent 2>/dev/null || \
npm install --legacy-peer-deps

info "Building Next.js for production..."
NEXT_PUBLIC_API_URL="$BACKEND_URL" npm run build 2>&1 | tail -20

if [[ ! -d "$FRONTEND_DIR/.next" ]]; then
  die "Next.js build failed — check $LOG_DIR/frontend-build.log"
fi

success "Next.js build complete"
cd "$APP_DIR"

# =============================================================================
# STEP 6 — Validate backend imports
# =============================================================================
step "6/9 Validating backend configuration"

cd "$BACKEND_DIR"
source "$VENV_DIR/bin/activate"

info "Checking backend imports..."
python3 -c "
import sys, os
sys.path.insert(0, '.')
from app.core.config import settings
print(f'  DATABASE_URL : {settings.DATABASE_URL}')
print(f'  FRONTEND_URL : {settings.FRONTEND_URL}')
print(f'  BACKEND_URL  : {settings.BACKEND_URL}')
print(f'  SECRET_KEY   : {settings.SECRET_KEY[:12]}...')
groq_ok = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY != 'REPLACE_WITH_YOUR_GROQ_API_KEY')
print(f'  GROQ_API_KEY : {\"set\" if groq_ok else \"NOT SET\"}')
smtp_ok = bool(settings.SMTP_USER and settings.SMTP_PASSWORD)
print(f'  SMTP         : {\"configured\" if smtp_ok else \"not configured (email disabled)\"}')
" 2>&1 | while read line; do info "$line"; done

deactivate
cd "$APP_DIR"

# =============================================================================
# STEP 7 — Make scripts executable
# =============================================================================
step "7/9 Setting permissions"

chmod +x "$APP_DIR/deploy.sh"   2>/dev/null || true
chmod +x "$APP_DIR/start.sh"    2>/dev/null || true
chmod +x "$APP_DIR/stop.sh"     2>/dev/null || true
chmod +x "$APP_DIR/restart.sh"  2>/dev/null || true
chmod +x "$APP_DIR/healthcheck.sh" 2>/dev/null || true
chmod +x "$APP_DIR/package.sh"  2>/dev/null || true
success "Scripts are executable"

# =============================================================================
# STEP 8 — Systemd services
# =============================================================================
step "8/9 Installing systemd services"

if [[ $SKIP_SYSTEMD -eq 1 ]]; then
  warn "Skipping systemd setup (--no-systemd flag)"
else
  BACKEND_SERVICE_SRC="$APP_DIR/bilvantis-backend.service"
  FRONTEND_SERVICE_SRC="$APP_DIR/bilvantis-frontend.service"

  # Patch ExecStart paths into service files
  if [[ -f "$BACKEND_SERVICE_SRC" ]]; then
    sed -i "s|APP_DIR_PLACEHOLDER|${APP_DIR}|g" "$BACKEND_SERVICE_SRC" 2>/dev/null || true
    sed -i "s|VENV_DIR_PLACEHOLDER|${VENV_DIR}|g" "$BACKEND_SERVICE_SRC" 2>/dev/null || true
    cp "$BACKEND_SERVICE_SRC" /etc/systemd/system/bilvantis-backend.service
    success "Installed bilvantis-backend.service"
  fi

  if [[ -f "$FRONTEND_SERVICE_SRC" ]]; then
    sed -i "s|APP_DIR_PLACEHOLDER|${APP_DIR}|g" "$FRONTEND_SERVICE_SRC" 2>/dev/null || true
    cp "$FRONTEND_SERVICE_SRC" /etc/systemd/system/bilvantis-frontend.service
    success "Installed bilvantis-frontend.service"
  fi

  systemctl daemon-reload
  systemctl enable bilvantis-backend bilvantis-frontend 2>/dev/null || true
  success "Services enabled for auto-start on boot"
fi

# =============================================================================
# STEP 9 — Start the application
# =============================================================================
step "9/9 Starting application"

"$APP_DIR/stop.sh" 2>/dev/null || true
sleep 2
"$APP_DIR/start.sh"

# Wait for services to be ready
info "Waiting for services to start..."
TIMEOUT=60
ELAPSED=0
while [[ $ELAPSED -lt $TIMEOUT ]]; do
  BACKEND_UP=$(curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null && echo "yes" || echo "no")
  FRONTEND_UP=$(curl -sf "http://127.0.0.1:${FRONTEND_PORT}" 2>/dev/null && echo "yes" || echo "no")
  [[ "$BACKEND_UP" == "yes" && "$FRONTEND_UP" == "yes" ]] && break
  sleep 3; ELAPSED=$((ELAPSED + 3))
  echo -n "."
done
echo ""

# Run health check
"$APP_DIR/healthcheck.sh"

# =============================================================================
# Done
# =============================================================================
VM_IP=$(get_vm_ip)
echo ""
echo -e "${GREEN}${BOLD}"
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║   ✓  Bilvantis TIP Deployment Complete                           ║"
echo "╠══════════════════════════════════════════════════════════════════╣"
echo "║                                                                  ║"
printf "║   Frontend  : %-51s║\n" "http://${VM_IP}:${FRONTEND_PORT}"
printf "║   Backend   : %-51s║\n" "http://${VM_IP}:${BACKEND_PORT}"
printf "║   API Docs  : %-51s║\n" "http://${VM_IP}:${BACKEND_PORT}/api/docs"
echo "║                                                                  ║"
echo "║   Admin Login: admin@bilvantis.io / Admin@1234                  ║"
echo "║                                                                  ║"
echo "║   Logs       : ./logs/backend.log  ./logs/frontend.log          ║"
echo "║   Stop       : bash stop.sh                                     ║"
echo "║   Restart    : bash restart.sh                                  ║"
echo "║   Health     : bash healthcheck.sh                              ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
