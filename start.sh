#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Start Services
# Usage: bash start.sh [--no-systemd]
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$SCRIPT_DIR"
BACKEND_DIR="$APP_DIR/backend"
FRONTEND_DIR="$APP_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
LOG_DIR="$APP_DIR/logs"
PID_DIR="$APP_DIR/run"

BACKEND_PORT=8002
FRONTEND_PORT=3003

mkdir -p "$LOG_DIR" "$PID_DIR"

# ── Helper: port in use? ───────────────────────────────────────────────────────
port_in_use() { ss -tlnp 2>/dev/null | grep -q ":$1 " || netstat -tlnp 2>/dev/null | grep -q ":$1 "; }

# ── Use systemd if available and running ──────────────────────────────────────
USE_SYSTEMD=0
if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
  if systemctl list-unit-files bilvantis-backend.service &>/dev/null 2>&1; then
    USE_SYSTEMD=1
  fi
fi

if [[ $USE_SYSTEMD -eq 1 && "${1:-}" != "--no-systemd" ]]; then
  info "Starting via systemd..."
  systemctl start bilvantis-backend  && success "bilvantis-backend.service started"
  systemctl start bilvantis-frontend && success "bilvantis-frontend.service started"
  sleep 3
  systemctl is-active --quiet bilvantis-backend  && success "Backend  is running" || warn "Backend  may not be running"
  systemctl is-active --quiet bilvantis-frontend && success "Frontend is running" || warn "Frontend may not be running"
  exit 0
fi

# ── Manual start (no systemd or --no-systemd) ─────────────────────────────────

[[ ! -f "$VENV_DIR/bin/activate" ]] && die "Virtual env not found at $VENV_DIR — run deploy.sh first."
[[ ! -d "$FRONTEND_DIR/.next"   ]] && die "Frontend not built at $FRONTEND_DIR/.next — run deploy.sh first."
[[ ! -f "$BACKEND_DIR/.env"     ]] && die "backend/.env missing — run deploy.sh first."

# ── Start Backend ─────────────────────────────────────────────────────────────
if port_in_use "$BACKEND_PORT"; then
  warn "Port $BACKEND_PORT already in use — backend may already be running."
else
  info "Starting FastAPI backend on port $BACKEND_PORT ..."
  cd "$BACKEND_DIR"
  source "$VENV_DIR/bin/activate"
  nohup uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$BACKEND_PORT" \
    --workers 1 \
    --loop asyncio \
    --log-level info \
    > "$LOG_DIR/backend.log" 2>&1 &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > "$PID_DIR/backend.pid"
  deactivate
  cd "$APP_DIR"

  # Wait up to 20s for backend to be ready
  for i in $(seq 1 20); do
    sleep 1
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" &>/dev/null; then
      success "Backend started (PID $BACKEND_PID) — http://0.0.0.0:${BACKEND_PORT}"
      break
    fi
    if [[ $i -eq 20 ]]; then
      warn "Backend did not respond in 20s — check $LOG_DIR/backend.log"
    fi
  done
fi

# ── Start Frontend ─────────────────────────────────────────────────────────────
if port_in_use "$FRONTEND_PORT"; then
  warn "Port $FRONTEND_PORT already in use — frontend may already be running."
else
  info "Starting Next.js frontend on port $FRONTEND_PORT ..."
  cd "$FRONTEND_DIR"
  nohup node_modules/.bin/next start --port "$FRONTEND_PORT" \
    > "$LOG_DIR/frontend.log" 2>&1 &
  FRONTEND_PID=$!
  echo "$FRONTEND_PID" > "$PID_DIR/frontend.pid"

  # Wait up to 20s for frontend to be ready
  for i in $(seq 1 20); do
    sleep 1
    if curl -sf "http://127.0.0.1:${FRONTEND_PORT}" &>/dev/null; then
      success "Frontend started (PID $FRONTEND_PID) — http://0.0.0.0:${FRONTEND_PORT}"
      break
    fi
    if [[ $i -eq 20 ]]; then
      warn "Frontend did not respond in 20s — check $LOG_DIR/frontend.log"
    fi
  done
  cd "$APP_DIR"
fi

VM_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
echo ""
echo -e "${GREEN}${BOLD}Services started:${NC}"
echo -e "  Frontend  : http://${VM_IP}:${FRONTEND_PORT}"
echo -e "  Backend   : http://${VM_IP}:${BACKEND_PORT}"
echo -e "  API Docs  : http://${VM_IP}:${BACKEND_PORT}/api/docs"
echo -e "  Logs      : tail -f ${LOG_DIR}/backend.log"
echo ""
