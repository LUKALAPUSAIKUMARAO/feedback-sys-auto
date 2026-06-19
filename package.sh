#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Create Deployment ZIP
# Usage  : bash package.sh [output-name.zip]
# Creates: bilvantis-tip-YYYYMMDD-HHMMSS.zip ready for transfer to new VM
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
die()     { echo -e "\033[0;31m[ERR]${NC}   $*" >&2; exit 1; }

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="bilvantis-tip"
TIMESTAMP=$(date +%Y%m%d-%H%M%S 2>/dev/null || date +%s)
OUTPUT="${1:-${APP_DIR}/${APP_NAME}-${TIMESTAMP}.zip}"
[[ "$OUTPUT" != /* ]] && OUTPUT="$APP_DIR/$OUTPUT"

command -v zip &>/dev/null || {
  info "Installing zip..."
  apt-get install -y -qq zip 2>/dev/null || \
  dnf install -y zip 2>/dev/null || \
  yum install -y zip 2>/dev/null || \
  zypper install -y zip 2>/dev/null || \
  apk add --no-cache zip 2>/dev/null || \
  die "Cannot install zip — please install it manually"
}

info "Source  : $APP_DIR"
info "Output  : $OUTPUT"

# ── Exclusion patterns ────────────────────────────────────────────────────────
EXCLUDES=(
  ".git/*"  ".git"
  "*/__pycache__/*"  "*/.pytest_cache/*"  "*/.mypy_cache/*"
  "*.pyc"  "*.pyo"  "*.pyd"
  "*/backend/.venv/*"  "*/backend/venv/*"
  "*/.eggs/*"
  "*/node_modules/*"
  "*/.next/*"  "*/.turbo/*"  "*/out/*"
  "*/backend/.env"
  "*/frontend/.env.local"
  "*/backend/*.db"  "*/backend/*.db-shm"  "*/backend/*.db-wal"
  "*/backend/feedback.db"  "*/backend/test.db"
  "*/logs/*.log"
  "*/run/*.pid"
  "*.DS_Store"  "*Thumbs.db"
  "*/.idea/*"  "*/.vscode/*"
  "*/.claude/*"
  "*.zip"  "*.tar.gz"
  "*/backend/check_db.py"  "*/backend/test_endpoint.py"  "*/backend/test_login.py"
)

EXCL_ARGS=()
for pat in "${EXCLUDES[@]}"; do EXCL_ARGS+=("-x" "$pat"); done

cd "$APP_DIR"
rm -f "$OUTPUT"
zip -r "$OUTPUT" . "${EXCL_ARGS[@]}" 2>/dev/null

ZIP_SIZE=$(du -sh "$OUTPUT" 2>/dev/null | cut -f1)
FILE_COUNT=$(unzip -l "$OUTPUT" 2>/dev/null | tail -1 | awk '{print $2}' || echo "?")

echo ""
echo -e "${GREEN}${BOLD}Deployment package ready:${NC}"
echo -e "  File  : $OUTPUT"
echo -e "  Size  : $ZIP_SIZE"
echo -e "  Files : $FILE_COUNT"
echo ""
echo -e "${BOLD}Transfer and deploy to any Linux VM:${NC}"
echo ""
echo -e "  # On this machine:"
echo -e "  scp $(basename "$OUTPUT") <user>@<NEW_VM_IP>:/home/<user>/"
echo ""
echo -e "  # On the new VM (any distro):"
echo -e "  ssh <user>@<NEW_VM_IP>"
echo -e "  # Install unzip if needed:"
echo -e "  #   Ubuntu/Debian: sudo apt-get install -y unzip"
echo -e "  #   RHEL/CentOS/Fedora: sudo dnf install -y unzip"
echo -e "  #   Alpine: sudo apk add unzip"
echo -e "  mkdir -p /opt/bilvantis-tip"
echo -e "  unzip $(basename "$OUTPUT") -d /opt/bilvantis-tip"
echo -e "  cd /opt/bilvantis-tip"
echo -e "  sudo bash deploy.sh"
echo ""
