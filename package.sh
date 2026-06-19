#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Package for Deployment
# Creates a ZIP of the application, excluding build artefacts and secrets.
# Usage: bash package.sh [output-filename]
# Output: bilvantis-tip-YYYYMMDD-HHMMSS.zip (or custom name)
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME=$(basename "$SCRIPT_DIR")
TIMESTAMP=$(date +%Y%m%d-%H%M%S 2>/dev/null || date +%s)
OUTPUT="${1:-${APP_NAME}-${TIMESTAMP}.zip}"

# Ensure output is an absolute path
[[ "$OUTPUT" != /* ]] && OUTPUT="$SCRIPT_DIR/$OUTPUT"

info "Packaging: $SCRIPT_DIR"
info "Output:    $OUTPUT"

# ── Verify zip is available ───────────────────────────────────────────────────
if ! command -v zip &>/dev/null; then
  echo "zip not found. Installing..."
  apt-get install -y -qq zip 2>/dev/null || \
  dnf install -y zip 2>/dev/null || \
  yum install -y zip 2>/dev/null || \
  die "Could not install zip. Please install it manually."
fi

# ── Build exclusion list ──────────────────────────────────────────────────────
EXCLUDES=(
  # VCS
  "*.git*"
  "*/.git/*"
  # Python
  "*/__pycache__/*"
  "*/*.pyc"
  "*/*.pyo"
  "*/.pytest_cache/*"
  "*/.mypy_cache/*"
  "*/backend/.venv/*"
  "*/backend/venv/*"
  "*/.eggs/*"
  "*/dist/*"
  "*/build/*"
  "*.egg-info/*"
  # Node
  "*/node_modules/*"
  "*/.next/*"
  "*/.turbo/*"
  "*/.vercel/*"
  "*/out/*"
  # Secrets
  "*/backend/.env"
  "*/frontend/.env.local"
  "*.env.local"
  # Database (may contain PII — target VM gets a fresh DB)
  "*/backend/*.db"
  "*/backend/*.db-shm"
  "*/backend/*.db-wal"
  # Logs
  "*/logs/*.log"
  "*/run/*.pid"
  # IDE / OS
  "*.DS_Store"
  "*Thumbs.db"
  "*/.idea/*"
  "*/.vscode/*"
  # Temp / package output
  "*.zip"
  "*.tar.gz"
)

# Build zip -x arguments
EXCLUDE_ARGS=()
for pat in "${EXCLUDES[@]}"; do
  EXCLUDE_ARGS+=("-x" "$pat")
done

# Remove old output if it exists
rm -f "$OUTPUT"

cd "$SCRIPT_DIR"
info "Creating ZIP archive (excluding build artifacts, secrets, database)..."

zip -r "$OUTPUT" . "${EXCLUDE_ARGS[@]}" 2>/dev/null

ZIP_SIZE=$(du -sh "$OUTPUT" 2>/dev/null | cut -f1)
FILE_COUNT=$(unzip -l "$OUTPUT" 2>/dev/null | tail -1 | awk '{print $2}')

echo ""
echo -e "${GREEN}${BOLD}Package created successfully!${NC}"
echo -e "  File  : $OUTPUT"
echo -e "  Size  : $ZIP_SIZE"
echo -e "  Files : $FILE_COUNT"
echo ""
echo -e "${BOLD}Deploy to a new VM:${NC}"
echo -e "  scp $OUTPUT user@<VM_IP>:/opt/"
echo -e "  ssh user@<VM_IP>"
echo -e "  cd /opt && unzip $(basename "$OUTPUT") -d feedback-system-auto"
echo -e "  cd feedback-system-auto"
echo -e "  sudo bash deploy.sh --groq-key <YOUR_GROQ_KEY> --smtp-user <EMAIL> --smtp-pass <APPPASS>"
echo ""
