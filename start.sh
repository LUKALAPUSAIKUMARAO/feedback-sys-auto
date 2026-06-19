#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Start Services
# Usage: bash start.sh [backend|frontend|all]
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[ERR]${NC}   $*" >&2; exit 1; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$APP_DIR/logs"
PID_DIR="$APP_DIR/run"
BACKEND_PORT=8002
FRONTEND_PORT=3003
TARGET="${1:-all}"

mkdir -p "$LOG_DIR" "$PID_DIR"

# Fix line endings if needed
sed -i 's/\r$//' "$0" 2>/dev/null || true

# ── Systemd detection ─────────────────────────────────────────────────────────
USE_SYSTEMD=0
if command -v systemctl &>/dev/null && systemctl list-unit-files bilvantis-backend.service &>/dev/null 2>&1; then
  USE_SYSTEMD=1
fi

start_backend() {
  if [[ $USE_SYSTEMD -eq 1 ]]; then
    info "Starting backend via systemd..."
    sudo systemctl start bilvantis-backend 2>/dev/null || systemctl start bilvantis-backend
    sleep 3
    systemctl is-active --quiet bilvantis-backend && success "bilvantis-backend is active" || warn "bilvantis-backend failed to start"
    return
  fi
  # Manual start
  [[ ! -f "$VENV_DIR/bin/activate" ]] && die "venv not found — run deploy.sh first"
  [[ ! -f "$BACKEND_DIR/.env"      ]] && die "backend/.env not found — run deploy.sh first"

  if ss -tlnp 2>/dev/null | grep -q ":${BACKEND_PORT} "; then
    warn "Port ${BACKEND_PORT} already in use — backend may already be running"
    return
  fi

  info "Starting backend (port ${BACKEND_PORT})..."
  cd "$BACKEND_DIR"
  source "$VENV_DIR/bin/activate"
  nohup uvicorn app.main:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" \
    --workers 1 --loop asyncio --log-level info \
    >> "$LOG_DIR/backend.log" 2>&1 &
  echo $! > "$PID_DIR/backend.pid"
  deactivate; cd "$APP_DIR"

  for i in $(seq 1 20); do
    sleep 2
    curl -sf --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/health" &>/dev/null && \
      { success "Backend started (PID $(cat "$PID_DIR/backend.pid"))"; return; }
  done
  warn "Backend did not respond in 40s — check $LOG_DIR/backend.log"
}

start_frontend() {
  if [[ $USE_SYSTEMD -eq 1 ]]; then
    info "Starting frontend via systemd..."
    sudo systemctl start bilvantis-frontend 2>/dev/null || systemctl start bilvantis-frontend
    sleep 5
    systemctl is-active --quiet bilvantis-frontend && success "bilvantis-frontend is active" || warn "bilvantis-frontend failed to start"
    return
  fi
  [[ ! -d "$FRONTEND_DIR/.next" ]] && die ".next build not found — run deploy.sh first"

  if ss -tlnp 2>/dev/null | grep -q ":${FRONTEND_PORT} "; then
    warn "Port ${FRONTEND_PORT} already in use — frontend may already be running"
    return
  fi

  info "Starting frontend (port ${FRONTEND_PORT})..."
  cd "$FRONTEND_DIR"
  nohup node_modules/.bin/next start --port "$FRONTEND_PORT" \
    >> "$LOG_DIR/frontend.log" 2>&1 &
  echo $! > "$PID_DIR/frontend.pid"
  cd "$APP_DIR"

  for i in $(seq 1 20); do
    sleep 2
    HTTP=$(curl -so /dev/null -w "%{http_code}" --max-time 2 "http://127.0.0.1:${FRONTEND_PORT}" 2>/dev/null || echo "000")
    [[ "$HTTP" == "200" || "$HTTP" == "302" || "$HTTP" == "308" ]] && \
      { success "Frontend started (PID $(cat "$PID_DIR/frontend.pid"))"; return; }
  done
  warn "Frontend did not respond in 40s — check $LOG_DIR/frontend.log"
}

case "$TARGET" in
  backend)  start_backend ;;
  frontend) start_frontend ;;
  all|*)    start_backend; start_frontend ;;
esac

VM_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
echo ""
echo -e "${GREEN}${BOLD}Services running:${NC}"
echo -e "  Application : http://${VM_IP}:${FRONTEND_PORT}/admin/login"
echo -e "  Backend     : http://${VM_IP}:${BACKEND_PORT}"
echo -e "  API Docs    : http://${VM_IP}:${BACKEND_PORT}/api/docs"
echo -e "  Logs        : tail -f ${LOG_DIR}/backend.log"
echo ""
