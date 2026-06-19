#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Restart Services
# Usage: bash restart.sh [backend|frontend|all]
# =============================================================================
set -euo pipefail

CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info() { echo -e "${CYAN}[INFO]${NC}  $*"; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-all}"

sed -i 's/\r$//' "$0" 2>/dev/null || true

# ── Init system detection ─────────────────────────────────────────────────────
USE_SYSTEMD=0; USE_OPENRC=0
if command -v systemctl &>/dev/null && systemctl list-unit-files bilvantis-backend.service &>/dev/null 2>&1; then
  USE_SYSTEMD=1
elif command -v rc-service &>/dev/null && [[ -f /etc/init.d/bilvantis-backend ]]; then
  USE_OPENRC=1
fi

# ── systemd fast path ─────────────────────────────────────────────────────────
if [[ $USE_SYSTEMD -eq 1 ]]; then
  case "$TARGET" in
    backend)
      info "Restarting backend (systemd)..."
      systemctl restart bilvantis-backend
      systemctl status  bilvantis-backend --no-pager -l | tail -5
      ;;
    frontend)
      info "Restarting frontend (systemd)..."
      systemctl restart bilvantis-frontend
      systemctl status  bilvantis-frontend --no-pager -l | tail -5
      ;;
    all|*)
      info "Restarting all services (systemd)..."
      systemctl restart bilvantis-backend bilvantis-frontend
      sleep 2
      systemctl status bilvantis-backend  --no-pager -l | tail -3
      systemctl status bilvantis-frontend --no-pager -l | tail -3
      ;;
  esac
  exit 0
fi

# ── OpenRC fast path (Alpine) ─────────────────────────────────────────────────
if [[ $USE_OPENRC -eq 1 ]]; then
  case "$TARGET" in
    backend)  info "Restarting backend (OpenRC)...";  rc-service bilvantis-backend  restart ;;
    frontend) info "Restarting frontend (OpenRC)..."; rc-service bilvantis-frontend restart ;;
    all|*)    info "Restarting all services (OpenRC)..."
              rc-service bilvantis-backend  restart
              rc-service bilvantis-frontend restart ;;
  esac
  exit 0
fi

# ── Manual fallback (PID-file) ────────────────────────────────────────────────
info "Restarting: $TARGET"
bash "$APP_DIR/stop.sh"  "$TARGET"
sleep 2
bash "$APP_DIR/start.sh" "$TARGET"
