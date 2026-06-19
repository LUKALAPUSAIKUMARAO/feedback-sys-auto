#!/usr/bin/env bash
# =============================================================================
# Bilvantis TIP — Health Check
# Usage: bash healthcheck.sh [--json] [--quiet]
# Exit: 0 if all healthy, 1 if any check fails
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ok()   { echo -e "${GREEN}  ✓${NC} $*"; }
fail() { echo -e "${RED}  ✗${NC} $*"; FAILURES=$((FAILURES + 1)); }
warn() { echo -e "${YELLOW}  !${NC} $*"; }
info() { echo -e "${CYAN}    ${NC} $*"; }

BACKEND_PORT=8002
FRONTEND_PORT=3003
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_DIR="$SCRIPT_DIR/run"
LOG_DIR="$SCRIPT_DIR/logs"
JSON_MODE=0
QUIET_MODE=0
FAILURES=0

for arg in "$@"; do
  [[ "$arg" == "--json"  ]] && JSON_MODE=1
  [[ "$arg" == "--quiet" ]] && QUIET_MODE=1
done

if [[ $QUIET_MODE -eq 0 ]]; then
  echo ""
  echo -e "${BOLD}${CYAN}═══ Bilvantis TIP Health Check ═══${NC}"
fi

# ── Helper: HTTP check ────────────────────────────────────────────────────────
http_check() {
  local url="$1" label="$2" expected_status="${3:-200}"
  local status; status=$(curl -so /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
  if [[ "$status" == "$expected_status" || "$status" == "200" || "$status" == "302" ]]; then
    [[ $QUIET_MODE -eq 0 ]] && ok "$label (HTTP $status)"
    return 0
  else
    [[ $QUIET_MODE -eq 0 ]] && fail "$label (HTTP $status — expected $expected_status)"
    return 1
  fi
}

# ── Helper: port check ────────────────────────────────────────────────────────
port_open() {
  local port="$1" label="$2"
  if ss -tlnp 2>/dev/null | grep -q ":${port} " || \
     netstat -tlnp 2>/dev/null | grep -q ":${port} " || \
     (command -v nc &>/dev/null && nc -z 127.0.0.1 "$port" 2>/dev/null); then
    [[ $QUIET_MODE -eq 0 ]] && ok "$label — port $port is OPEN"
    return 0
  else
    [[ $QUIET_MODE -eq 0 ]] && fail "$label — port $port is CLOSED"
    return 1
  fi
}

# ── Helper: process check ─────────────────────────────────────────────────────
proc_running() {
  local pattern="$1" label="$2"
  if pgrep -f "$pattern" &>/dev/null; then
    local pid; pid=$(pgrep -f "$pattern" | head -1)
    [[ $QUIET_MODE -eq 0 ]] && ok "$label (PID $pid)"
    return 0
  else
    [[ $QUIET_MODE -eq 0 ]] && fail "$label — process not found"
    return 1
  fi
}

# ── 1. Process checks ─────────────────────────────────────────────────────────
[[ $QUIET_MODE -eq 0 ]] && echo -e "\n${BOLD}Processes:${NC}"
proc_running "uvicorn app.main:app" "Backend process (uvicorn)"   || FAILURES=$((FAILURES + 1))
proc_running "next start"           "Frontend process (next start)" || FAILURES=$((FAILURES + 1))

# ── 2. Port checks ────────────────────────────────────────────────────────────
[[ $QUIET_MODE -eq 0 ]] && echo -e "\n${BOLD}Ports:${NC}"
port_open "$BACKEND_PORT"  "Backend"  || FAILURES=$((FAILURES + 1))
port_open "$FRONTEND_PORT" "Frontend" || FAILURES=$((FAILURES + 1))

# ── 3. HTTP endpoint checks ───────────────────────────────────────────────────
[[ $QUIET_MODE -eq 0 ]] && echo -e "\n${BOLD}HTTP Endpoints:${NC}"

# Backend /health
HEALTH_JSON=$(curl -sf --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null || echo "{}")
if echo "$HEALTH_JSON" | grep -q '"status"'; then
  [[ $QUIET_MODE -eq 0 ]] && ok "Backend /health responds"
  BACKEND_STATUS=$(echo "$HEALTH_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "?")
  [[ $QUIET_MODE -eq 0 ]] && info "status: $BACKEND_STATUS"
else
  [[ $QUIET_MODE -eq 0 ]] && fail "Backend /health not responding"
  FAILURES=$((FAILURES + 1))
fi

# Backend /api/v1/analytics/health (system health — authenticated, just check it's up)
HTTP_STATUS=$(curl -so /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:${BACKEND_PORT}/api/docs" 2>/dev/null || echo "000")
if [[ "$HTTP_STATUS" == "200" ]]; then
  [[ $QUIET_MODE -eq 0 ]] && ok "Backend /api/docs (Swagger UI)"
else
  [[ $QUIET_MODE -eq 0 ]] && warn "Backend /api/docs HTTP $HTTP_STATUS (non-critical)"
fi

# Frontend
http_check "http://127.0.0.1:${FRONTEND_PORT}" "Frontend / (homepage)" || FAILURES=$((FAILURES + 1))
http_check "http://127.0.0.1:${FRONTEND_PORT}/admin/login" "Frontend /admin/login" || FAILURES=$((FAILURES + 1))

# ── 4. Database check ─────────────────────────────────────────────────────────
[[ $QUIET_MODE -eq 0 ]] && echo -e "\n${BOLD}Database:${NC}"
DB_PATH="$SCRIPT_DIR/backend/feedback_platform.db"
if [[ -f "$DB_PATH" ]]; then
  DB_SIZE=$(du -sh "$DB_PATH" 2>/dev/null | cut -f1)
  USER_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM users;" 2>/dev/null || echo "?")
  [[ $QUIET_MODE -eq 0 ]] && ok "SQLite DB exists ($DB_SIZE, $USER_COUNT users)"
else
  [[ $QUIET_MODE -eq 0 ]] && warn "DB not found at $DB_PATH (will be created on first startup)"
fi

# ── 5. Config / env check ─────────────────────────────────────────────────────
[[ $QUIET_MODE -eq 0 ]] && echo -e "\n${BOLD}Configuration:${NC}"
BACKEND_ENV="$SCRIPT_DIR/backend/.env"
if [[ -f "$BACKEND_ENV" ]]; then
  GROQ_KEY=$(grep "^GROQ_API_KEY=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
  if [[ -n "$GROQ_KEY" && "$GROQ_KEY" != "REPLACE_WITH_YOUR_GROQ_API_KEY" ]]; then
    [[ $QUIET_MODE -eq 0 ]] && ok "GROQ_API_KEY is set"
  else
    [[ $QUIET_MODE -eq 0 ]] && warn "GROQ_API_KEY not set — AI chat disabled"
  fi

  SMTP_USER=$(grep "^SMTP_USER=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
  SMTP_PASS=$(grep "^SMTP_PASSWORD=" "$BACKEND_ENV" 2>/dev/null | cut -d= -f2- || echo "")
  if [[ -n "$SMTP_USER" && -n "$SMTP_PASS" ]]; then
    [[ $QUIET_MODE -eq 0 ]] && ok "SMTP configured ($SMTP_USER)"
  else
    [[ $QUIET_MODE -eq 0 ]] && warn "SMTP not configured — emails disabled"
  fi
else
  [[ $QUIET_MODE -eq 0 ]] && fail "backend/.env missing"
  FAILURES=$((FAILURES + 1))
fi

# ── 6. Log tails ─────────────────────────────────────────────────────────────
if [[ $QUIET_MODE -eq 0 ]]; then
  echo -e "\n${BOLD}Recent log entries (backend):${NC}"
  if [[ -f "$LOG_DIR/backend.log" ]]; then
    tail -5 "$LOG_DIR/backend.log" 2>/dev/null | while IFS= read -r line; do
      echo "    $line"
    done
  else
    echo "    (no log file yet)"
  fi
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
if [[ $FAILURES -eq 0 ]]; then
  VM_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "127.0.0.1")
  echo -e "${GREEN}${BOLD}All checks passed.${NC}"
  echo -e "  Frontend : http://${VM_IP}:${FRONTEND_PORT}"
  echo -e "  Backend  : http://${VM_IP}:${BACKEND_PORT}"
  [[ $JSON_MODE -eq 1 ]] && echo '{"status":"healthy","failures":0}'
  exit 0
else
  echo -e "${RED}${BOLD}${FAILURES} check(s) failed.${NC}"
  echo "  Run 'bash restart.sh' to attempt recovery."
  echo "  Check logs: tail -f $LOG_DIR/backend.log"
  [[ $JSON_MODE -eq 1 ]] && echo "{\"status\":\"unhealthy\",\"failures\":${FAILURES}}"
  exit 1
fi
