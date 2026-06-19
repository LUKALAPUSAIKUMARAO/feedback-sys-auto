#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Restart Services
# Usage: bash restart.sh [backend|frontend]
# =============================================================================
set -euo pipefail

CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info() { echo -e "${CYAN}[INFO]${NC}  $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-all}"

info "Restarting: $TARGET"

case "$TARGET" in
  backend)
    # Only restart backend (leave frontend running)
    USE_SYSTEMD=0
    if command -v systemctl &>/dev/null && systemctl list-unit-files bilvantis-backend.service &>/dev/null 2>&1; then
      USE_SYSTEMD=1
    fi
    if [[ $USE_SYSTEMD -eq 1 ]]; then
      systemctl restart bilvantis-backend
    else
      PID_FILE="$SCRIPT_DIR/run/backend.pid"
      VENV="$SCRIPT_DIR/backend/.venv/bin/activate"
      LOG="$SCRIPT_DIR/logs/backend.log"
      PID_DIR="$SCRIPT_DIR/run"
      if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        kill "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        sleep 2
      fi
      cd "$SCRIPT_DIR/backend"
      source "$VENV"
      nohup uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1 --loop asyncio --log-level info \
        > "$LOG" 2>&1 &
      echo $! > "$PID_FILE"
      deactivate
      cd "$SCRIPT_DIR"
      echo -e "\033[0;32m[OK]\033[0m    Backend restarted"
    fi
    ;;
  frontend)
    # Only restart frontend (leave backend running)
    USE_SYSTEMD=0
    if command -v systemctl &>/dev/null && systemctl list-unit-files bilvantis-frontend.service &>/dev/null 2>&1; then
      USE_SYSTEMD=1
    fi
    if [[ $USE_SYSTEMD -eq 1 ]]; then
      systemctl restart bilvantis-frontend
    else
      PID_FILE="$SCRIPT_DIR/run/frontend.pid"
      LOG="$SCRIPT_DIR/logs/frontend.log"
      if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        kill "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
        sleep 2
      fi
      cd "$SCRIPT_DIR/frontend"
      nohup node_modules/.bin/next start --port 3003 > "$LOG" 2>&1 &
      echo $! > "$PID_FILE"
      cd "$SCRIPT_DIR"
      echo -e "\033[0;32m[OK]\033[0m    Frontend restarted"
    fi
    ;;
  all|*)
    bash "$SCRIPT_DIR/stop.sh"
    sleep 2
    bash "$SCRIPT_DIR/start.sh"
    ;;
esac
