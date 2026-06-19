#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Health Check
# Usage  : bash healthcheck.sh [--json] [--quiet]
# Exit   : 0 = all healthy | 1 = one or more checks failed
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

PASS=0; WARN=0; FAIL=0
JSON_MODE=0; QUIET=0
RESULTS=()

for arg in "$@"; do
  [[ "$arg" == "--json"  ]] && JSON_MODE=1
  [[ "$arg" == "--quiet" ]] && QUIET=1
done

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$APP_DIR/backend"
LOG_DIR="$APP_DIR/logs"
BACKEND_PORT=8002
FRONTEND_PORT=3003
VM_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")

sed -i 's/\r$//' "$0" 2>/dev/null || true

chk_pass() { PASS=$((PASS+1)); RESULTS+=("PASS|$1"); [[ $QUIET -eq 0 ]] && echo -e "  ${GREEN}✓${NC} $1"; }
chk_fail() { FAIL=$((FAIL+1)); RESULTS+=("FAIL|$1"); [[ $QUIET -eq 0 ]] && echo -e "  ${RED}✗${NC} $1"; }
chk_warn() { WARN=$((WARN+1)); RESULTS+=("WARN|$1"); [[ $QUIET -eq 0 ]] && echo -e "  ${YELLOW}!${NC} $1"; }

[[ $QUIET -eq 0 ]] && echo -e "\n${BOLD}${CYAN}══ Bilvantis TIP Health Check ══${NC}\n"

# ── 1. Process checks ─────────────────────────────────────────────────────────
[[ $QUIET -eq 0 ]] && echo -e "${BOLD}Processes:${NC}"

if pgrep -f "uvicorn app.main:app" &>/dev/null; then
  BE_PID=$(pgrep -f "uvicorn app.main:app" | head -1)
  chk_pass "Backend process running (PID $BE_PID)"
else
  chk_fail "Backend process NOT found"
fi

if pgrep -f "next start" &>/dev/null; then
  FE_PID=$(pgrep -f "next start" | head -1)
  chk_pass "Frontend process running (PID $FE_PID)"
else
  chk_fail "Frontend process NOT found"
fi

# ── 2. Port checks ────────────────────────────────────────────────────────────
[[ $QUIET -eq 0 ]] && echo -e "\n${BOLD}Ports:${NC}"

if ss -tlnp 2>/dev/null | grep -q ":${BACKEND_PORT} "; then
  chk_pass "Port ${BACKEND_PORT} is OPEN (backend)"
else
  chk_fail "Port ${BACKEND_PORT} is CLOSED (backend)"
fi

if ss -tlnp 2>/dev/null | grep -q ":${FRONTEND_PORT} "; then
  chk_pass "Port ${FRONTEND_PORT} is OPEN (frontend)"
else
  chk_fail "Port ${FRONTEND_PORT} is CLOSED (frontend)"
fi

# ── 3. HTTP endpoint checks ───────────────────────────────────────────────────
[[ $QUIET -eq 0 ]] && echo -e "\n${BOLD}HTTP Endpoints:${NC}"

# /health
HEALTH_BODY=$(curl -sf --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || echo "")
if [[ -n "$HEALTH_BODY" ]]; then
  API_STATUS=$(echo "$HEALTH_BODY" | python3 -c "import sys,json;print(json.load(sys.stdin).get('status','?'))" 2>/dev/null || echo "?")
  API_VER=$(echo "$HEALTH_BODY" | python3 -c "import sys,json;print(json.load(sys.stdin).get('version','?'))" 2>/dev/null || echo "?")
  chk_pass "GET /health → status=${API_STATUS}  version=${API_VER}"
else
  chk_fail "GET /health → no response"
fi

# /api/docs
DOCS_CODE=$(curl -so /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/api/docs" 2>/dev/null || echo "000")
if [[ "$DOCS_CODE" == "200" ]]; then
  chk_pass "GET /api/docs → HTTP ${DOCS_CODE}"
else
  chk_warn "GET /api/docs → HTTP ${DOCS_CODE}"
fi

# Frontend homepage
FE_CODE=$(curl -so /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:${FRONTEND_PORT}" 2>/dev/null || echo "000")
if [[ "$FE_CODE" == "200" || "$FE_CODE" == "302" || "$FE_CODE" == "308" ]]; then
  chk_pass "GET frontend / → HTTP ${FE_CODE}"
else
  chk_fail "GET frontend / → HTTP ${FE_CODE}"
fi

# Admin login page
LOGIN_CODE=$(curl -so /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:${FRONTEND_PORT}/admin/login" 2>/dev/null || echo "000")
if [[ "$LOGIN_CODE" == "200" || "$LOGIN_CODE" == "302" ]]; then
  chk_pass "GET /admin/login → HTTP ${LOGIN_CODE}"
else
  chk_warn "GET /admin/login → HTTP ${LOGIN_CODE}"
fi

# ── 4. Systemd service status ─────────────────────────────────────────────────
[[ $QUIET -eq 0 ]] && echo -e "\n${BOLD}Systemd Services:${NC}"
if command -v systemctl &>/dev/null && systemctl list-unit-files bilvantis-backend.service &>/dev/null 2>&1; then
  BE_ACTIVE=$(systemctl is-active bilvantis-backend  2>/dev/null || echo "unknown")
  FE_ACTIVE=$(systemctl is-active bilvantis-frontend 2>/dev/null || echo "unknown")
  BE_ENABLED=$(systemctl is-enabled bilvantis-backend  2>/dev/null || echo "unknown")
  FE_ENABLED=$(systemctl is-enabled bilvantis-frontend 2>/dev/null || echo "unknown")

  [[ "$BE_ACTIVE" == "active" ]] && chk_pass "bilvantis-backend: $BE_ACTIVE ($BE_ENABLED)" || chk_fail "bilvantis-backend: $BE_ACTIVE ($BE_ENABLED)"
  [[ "$FE_ACTIVE" == "active" ]] && chk_pass "bilvantis-frontend: $FE_ACTIVE ($FE_ENABLED)" || chk_fail "bilvantis-frontend: $FE_ACTIVE ($FE_ENABLED)"
else
  chk_warn "Systemd not configured — services managed manually"
fi

# ── 5. Database ───────────────────────────────────────────────────────────────
[[ $QUIET -eq 0 ]] && echo -e "\n${BOLD}Database:${NC}"
DB_PATH="$BACKEND_DIR/feedback_platform.db"
if [[ -f "$DB_PATH" ]]; then
  DB_SIZE=$(du -sh "$DB_PATH" 2>/dev/null | cut -f1)
  USER_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "?")
  BATCH_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM training_batches;" 2>/dev/null || echo "?")
  chk_pass "SQLite DB: ${DB_SIZE} | users=${USER_COUNT} | batches=${BATCH_COUNT}"
else
  chk_warn "DB not yet created (will appear after first backend startup)"
fi

# ── 6. Configuration ──────────────────────────────────────────────────────────
[[ $QUIET -eq 0 ]] && echo -e "\n${BOLD}Configuration:${NC}"
BACKEND_ENV="$BACKEND_DIR/.env"
if [[ -f "$BACKEND_ENV" ]]; then
  chk_pass "backend/.env exists"
  GROQ_VAL=$(grep "^GROQ_API_KEY=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
  if [[ "$GROQ_VAL" == gsk_* ]]; then chk_pass "GROQ_API_KEY set (${GROQ_VAL:0:12}...)"
  else chk_warn "GROQ_API_KEY not set — AI chat disabled"; fi

  SMTP_VAL=$(grep "^SMTP_USER=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
  if [[ -n "$SMTP_VAL" ]]; then chk_pass "SMTP_USER: $SMTP_VAL"
  else chk_warn "SMTP_USER not set — email disabled"; fi
else
  chk_fail "backend/.env missing"
fi

# ── 7. Recent log tail ────────────────────────────────────────────────────────
if [[ $QUIET -eq 0 && -f "$LOG_DIR/backend.log" ]]; then
  echo -e "\n${BOLD}Recent backend log (last 5 lines):${NC}"
  tail -5 "$LOG_DIR/backend.log" 2>/dev/null | while IFS= read -r line; do echo "  $line"; done
fi

# ── Summary ───────────────────────────────────────────────────────────────────
TOTAL=$((PASS + WARN + FAIL))
echo ""

if [[ $JSON_MODE -eq 1 ]]; then
  STATUS=$([[ $FAIL -eq 0 ]] && echo "healthy" || echo "unhealthy")
  echo "{\"status\":\"$STATUS\",\"pass\":$PASS,\"warn\":$WARN,\"fail\":$FAIL,\"total\":$TOTAL,\"vm_ip\":\"$VM_IP\",\"frontend_url\":\"http://${VM_IP}:${FRONTEND_PORT}\",\"backend_url\":\"http://${VM_IP}:${BACKEND_PORT}\"}"
fi

if [[ $FAIL -eq 0 ]]; then
  [[ $QUIET -eq 0 ]] && echo -e "${GREEN}${BOLD}All critical checks passed  (pass=${PASS} warn=${WARN} fail=0)${NC}"
  [[ $QUIET -eq 0 ]] && echo ""
  [[ $QUIET -eq 0 ]] && echo -e "  ${BOLD}VM IP       :${NC} $VM_IP"
  [[ $QUIET -eq 0 ]] && echo -e "  ${BOLD}Application :${NC} http://${VM_IP}:${FRONTEND_PORT}/admin/login"
  [[ $QUIET -eq 0 ]] && echo -e "  ${BOLD}Backend     :${NC} http://${VM_IP}:${BACKEND_PORT}"
  [[ $QUIET -eq 0 ]] && echo -e "  ${BOLD}API Docs    :${NC} http://${VM_IP}:${BACKEND_PORT}/api/docs"
  [[ $QUIET -eq 0 ]] && echo ""
  exit 0
else
  [[ $QUIET -eq 0 ]] && echo -e "${RED}${BOLD}${FAIL} check(s) failed  (pass=${PASS} warn=${WARN} fail=${FAIL})${NC}"
  [[ $QUIET -eq 0 ]] && echo ""
  [[ $QUIET -eq 0 ]] && echo -e "  Logs    : tail -f ${LOG_DIR}/backend.log"
  [[ $QUIET -eq 0 ]] && echo -e "  Restart : bash ${APP_DIR}/restart.sh"
  [[ $QUIET -eq 0 ]] && echo -e "  Journal : sudo journalctl -u bilvantis-backend -n 50 --no-pager"
  [[ $QUIET -eq 0 ]] && echo ""
  exit 1
fi
