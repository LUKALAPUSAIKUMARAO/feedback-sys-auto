#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Stop Services
# Usage: bash stop.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/run"

BACKEND_PORT=8002
FRONTEND_PORT=3003

# ── Use systemd if available ────────────────────────────────────────────────────
USE_SYSTEMD=0
if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
  if systemctl list-unit-files bilvantis-backend.service &>/dev/null 2>&1; then
    USE_SYSTEMD=1
  fi
fi

if [[ $USE_SYSTEMD -eq 1 ]]; then
  info "Stopping via systemd..."
  systemctl stop bilvantis-frontend 2>/dev/null && success "bilvantis-frontend stopped" || warn "Frontend was not running"
  systemctl stop bilvantis-backend  2>/dev/null && success "bilvantis-backend stopped"  || warn "Backend was not running"
  exit 0
fi

# ── Stop by PID file ──────────────────────────────────────────────────────────
kill_pid_file() {
  local name="$1" pid_file="$2"
  if [[ -f "$pid_file" ]]; then
    local pid; pid=$(cat "$pid_file" 2>/dev/null || echo "")
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && success "$name (PID $pid) stopped"
      sleep 1
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
    else
      warn "$name PID file found but process $pid is not running"
    fi
    rm -f "$pid_file"
  fi
}

kill_pid_file "Backend"  "$PID_DIR/backend.pid"
kill_pid_file "Frontend" "$PID_DIR/frontend.pid"

# ── Kill by port as fallback ──────────────────────────────────────────────────
kill_port() {
  local port="$1" name="$2"
  local pids; pids=$(ss -tlnp 2>/dev/null | grep ":${port} " | grep -o 'pid=[0-9]*' | cut -d= -f2 || true)
  if [[ -z "$pids" ]]; then
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
  fi
  if [[ -n "$pids" ]]; then
    echo "$pids" | xargs -r kill 2>/dev/null && success "$name on port $port killed"
    sleep 1
    echo "$pids" | xargs -r kill -9 2>/dev/null || true
  fi
}

kill_port "$BACKEND_PORT"  "Backend"
kill_port "$FRONTEND_PORT" "Frontend"

# ── Kill any remaining uvicorn / next processes ───────────────────────────────
pkill -f "uvicorn app.main:app" 2>/dev/null && warn "Killed lingering uvicorn" || true
pkill -f "next start"           2>/dev/null && warn "Killed lingering next start" || true

success "All services stopped."
