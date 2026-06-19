#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Stop Services
# Usage  : bash stop.sh [backend|frontend|all]
# Compat : systemd · OpenRC (Alpine) · PID-file fallback (any Linux)
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$APP_DIR/run"
BACKEND_PORT=8002
FRONTEND_PORT=3003
TARGET="${1:-all}"

sed -i 's/\r$//' "$0" 2>/dev/null || true

# ── Init system detection ─────────────────────────────────────────────────────
USE_SYSTEMD=0; USE_OPENRC=0
if command -v systemctl &>/dev/null && systemctl list-unit-files bilvantis-backend.service &>/dev/null 2>&1; then
  USE_SYSTEMD=1
elif command -v rc-service &>/dev/null && [[ -f /etc/init.d/bilvantis-backend ]]; then
  USE_OPENRC=1
fi

# ── Helpers ───────────────────────────────────────────────────────────────────
kill_pid_file() {
  local name="$1" file="$2"
  [[ ! -f "$file" ]] && return
  local pid; pid=$(cat "$file" 2>/dev/null || echo "")
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null && success "$name (PID $pid) stopped"
    sleep 1
    kill -0 "$pid" 2>/dev/null && kill -KILL "$pid" 2>/dev/null || true
  else
    warn "$name PID file exists but process $pid is not running"
  fi
  rm -f "$file"
}

pids_on_port() {
  local port="$1" pids=""
  # ss method (iproute2)
  pids=$(ss -tlnp 2>/dev/null | grep ":${port} " | grep -oP 'pid=\K[0-9]+' || true)
  # netstat method (net-tools)
  [[ -z "$pids" ]] && pids=$(netstat -tlnp 2>/dev/null | grep ":${port} " | \
    awk '{print $7}' | cut -d/ -f1 | grep -E '^[0-9]+$' || true)
  # fuser method (psmisc)
  [[ -z "$pids" ]] && pids=$(fuser "${port}/tcp" 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+$' || true)
  # lsof method (lsof)
  [[ -z "$pids" ]] && pids=$(lsof -ti :"${port}" 2>/dev/null || true)
  echo "$pids"
}

kill_port() {
  local port="$1" name="$2"
  local pids; pids=$(pids_on_port "$port")
  if [[ -n "$pids" ]]; then
    echo "$pids" | xargs -r kill -TERM 2>/dev/null || true
    sleep 1
    echo "$pids" | xargs -r kill -KILL 2>/dev/null || true
    success "$name port $port cleared"
  fi
}

# ── Stop functions ────────────────────────────────────────────────────────────
stop_backend() {
  if [[ $USE_SYSTEMD -eq 1 ]]; then
    systemctl stop bilvantis-backend 2>/dev/null \
      && success "bilvantis-backend stopped" \
      || warn "Backend was not running"
    return
  fi
  if [[ $USE_OPENRC -eq 1 ]]; then
    rc-service bilvantis-backend stop 2>/dev/null \
      && success "bilvantis-backend stopped" \
      || warn "Backend was not running"
    return
  fi
  kill_pid_file "Backend" "$PID_DIR/backend.pid"
  kill_port "$BACKEND_PORT" "Backend"
  pkill -f "uvicorn app.main:app" 2>/dev/null && warn "Killed lingering uvicorn process" || true
}

stop_frontend() {
  if [[ $USE_SYSTEMD -eq 1 ]]; then
    systemctl stop bilvantis-frontend 2>/dev/null \
      && success "bilvantis-frontend stopped" \
      || warn "Frontend was not running"
    return
  fi
  if [[ $USE_OPENRC -eq 1 ]]; then
    rc-service bilvantis-frontend stop 2>/dev/null \
      && success "bilvantis-frontend stopped" \
      || warn "Frontend was not running"
    return
  fi
  kill_pid_file "Frontend" "$PID_DIR/frontend.pid"
  kill_port "$FRONTEND_PORT" "Frontend"
  pkill -f "next start" 2>/dev/null && warn "Killed lingering next process" || true
}

case "$TARGET" in
  backend)  stop_backend ;;
  frontend) stop_frontend ;;
  all|*)    stop_frontend; stop_backend ;;
esac

success "Done."
