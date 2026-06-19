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

# ── Systemd fast path ─────────────────────────────────────────────────────────
USE_SYSTEMD=0
if command -v systemctl &>/dev/null && systemctl list-unit-files bilvantis-backend.service &>/dev/null 2>&1; then
  USE_SYSTEMD=1
fi

if [[ $USE_SYSTEMD -eq 1 ]]; then
  case "$TARGET" in
    backend)
      info "Restarting backend..."
      systemctl restart bilvantis-backend
      systemctl status  bilvantis-backend --no-pager -l | tail -5
      ;;
    frontend)
      info "Restarting frontend..."
      systemctl restart bilvantis-frontend
      systemctl status  bilvantis-frontend --no-pager -l | tail -5
      ;;
    all|*)
      info "Restarting all services..."
      systemctl restart bilvantis-backend bilvantis-frontend
      sleep 2
      systemctl status bilvantis-backend  --no-pager -l | tail -3
      systemctl status bilvantis-frontend --no-pager -l | tail -3
      ;;
  esac
  exit 0
fi

# ── Manual fallback ───────────────────────────────────────────────────────────
info "Restarting: $TARGET"
bash "$APP_DIR/stop.sh" "$TARGET"
sleep 2
bash "$APP_DIR/start.sh" "$TARGET"
