# Bilvantis Training Intelligence Platform — Deployment Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Bilvantis TIP Stack                             │
├────────────────────────┬────────────────────────────────────────────┤
│  Frontend              │  Backend                                   │
│  Next.js 15 + React 19 │  Python 3.12 + FastAPI 0.115.5            │
│  TypeScript + Tailwind │  SQLAlchemy 2.0 async + aiosqlite          │
│  Port: 3003            │  Port: 8002                                │
│  node_modules/.bin/    │  uvicorn (1 worker, asyncio)               │
│  next start --port 3003│  Celery (memory:// — no Redis needed)      │
├────────────────────────┴────────────────────────────────────────────┤
│  Database: SQLite (embedded, no server)                             │
│    Path:   backend/feedback_platform.db                             │
│  Queue:    fakeredis + memory:// (embedded, no Redis)               │
│  AI:       Groq API — llama-3.3-70b-versatile (external HTTPS)     │
│  Email:    Gmail SMTP (optional, external)                          │
└─────────────────────────────────────────────────────────────────────┘
```

### No External Infrastructure Required
- **No PostgreSQL** — SQLite is embedded and created automatically
- **No Redis** — Celery uses `memory://` broker with `task_always_eager=True`
- **No Docker** — native Python venv + Node.js installation
- External: Groq API (AI chat), Gmail SMTP (email notifications)

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Linux OS | Ubuntu 20.04/22.04/24.04 or CentOS/RHEL 8+ | Debian-based preferred |
| Python | 3.12 | Installed by deploy.sh via deadsnakes PPA |
| Node.js | 20 LTS | Installed by deploy.sh via NodeSource |
| RAM | 2 GB minimum | 4 GB recommended |
| Disk | 5 GB free | For packages, build, logs |
| Network | Outbound HTTPS | For Groq API + Gmail SMTP |
| Root access | Required for deploy | Package install + systemd |

---

## Quick Deployment (Fresh VM)

### Step 1 — Copy the application ZIP to the VM
```bash
# On your source machine:
bash package.sh                           # creates bilvantis-tip-YYYYMMDD.zip
scp bilvantis-tip-*.zip user@VM_IP:/opt/ # copy to VM
```

### Step 2 — SSH into the VM and unzip
```bash
ssh user@VM_IP
cd /opt
unzip bilvantis-tip-*.zip -d feedback-system-auto
cd feedback-system-auto
```

### Step 3 — Run the single deployment script
```bash
sudo bash deploy.sh \
  --groq-key  gsk_YOUR_GROQ_KEY_HERE \
  --smtp-user your.email@gmail.com \
  --smtp-pass your_16_char_app_password
```

The script handles everything:
1. Installs Python 3.12 (deadsnakes PPA) and Node.js 20 (NodeSource)
2. Creates Python virtual environment and installs all pip packages
3. Generates `backend/.env` and `frontend/.env.local` with the VM's IP
4. Builds the Next.js frontend for production
5. Installs and enables systemd services for auto-start on reboot
6. Starts both services and runs health checks

**Total time: ~10–15 minutes** (mostly package downloads)

---

## Ports

| Service | Port | URL |
|---------|------|-----|
| Frontend (Next.js) | **3003** | `http://VM_IP:3003` |
| Backend (FastAPI) | **8002** | `http://VM_IP:8002` |
| API Documentation | **8002** | `http://VM_IP:8002/api/docs` |
| API Health | **8002** | `http://VM_IP:8002/health` |

Open these ports in your firewall/security group:
```bash
# Ubuntu UFW
sudo ufw allow 3003/tcp
sudo ufw allow 8002/tcp

# RHEL/CentOS firewalld
sudo firewall-cmd --permanent --add-port=3003/tcp
sudo firewall-cmd --permanent --add-port=8002/tcp
sudo firewall-cmd --reload
```

---

## Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@bilvantis.io` | `Admin@1234` |

> Change the admin password after first login via Settings > Profile.

---

## File Structure

```
feedback-system-auto/
├── deploy.sh                 # Main deployment script (run once on fresh VM)
├── start.sh                  # Start backend + frontend
├── stop.sh                   # Stop backend + frontend
├── restart.sh                # Restart all (or: restart.sh backend/frontend)
├── healthcheck.sh            # Health check with exit code 0/1
├── package.sh                # Create ZIP for deployment
├── .env.example              # Template for backend/.env
├── bilvantis-backend.service # systemd unit for FastAPI
├── bilvantis-frontend.service# systemd unit for Next.js
├── DEPLOYMENT.md             # This document
│
├── backend/
│   ├── .env                  # Created by deploy.sh — NEVER commit this
│   ├── .venv/                # Python virtualenv (created by deploy.sh)
│   ├── feedback_platform.db  # SQLite database (created at first startup)
│   ├── requirements.txt      # Python dependencies
│   └── app/
│       ├── main.py           # FastAPI application entry point
│       ├── core/
│       │   ├── config.py     # Settings (reads backend/.env via absolute path)
│       │   └── email.py      # SMTP / SendGrid email service
│       ├── api/v1/           # REST API endpoints
│       ├── agents/           # 7 AI agent pipeline (Groq / LLM)
│       ├── models/           # SQLAlchemy ORM models
│       └── tasks/            # Celery background tasks
│
├── frontend/
│   ├── .env.local            # Created by deploy.sh — NEVER commit this
│   ├── .next/                # Next.js production build (created by deploy.sh)
│   ├── package.json
│   └── src/app/              # Next.js App Router pages
│
└── logs/
    ├── backend.log           # FastAPI / uvicorn logs
    └── frontend.log          # Next.js production logs
```

---

## Environment Variables Reference

All variables live in `backend/.env`. The config module resolves this file using an **absolute path** derived from `config.py`'s location — so the working directory of the uvicorn process does not matter for `.env` resolution.

### Required

| Variable | Example | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./feedback_platform.db` | Async SQLite URL |
| `SYNC_DATABASE_URL` | `sqlite:///./feedback_platform.db` | Sync SQLite URL (migrations) |
| `SECRET_KEY` | `<64 hex chars>` | JWT signing key — generate once |
| `GROQ_API_KEY` | `gsk_...` | AI analytics — get at console.groq.com |

### Optional (email — at least one provider recommended)

| Variable | Example | Description |
|----------|---------|-------------|
| `SMTP_USER` | `you@gmail.com` | Gmail username |
| `SMTP_PASSWORD` | `xxxx xxxx xxxx xxxx` | Gmail App Password (not account password) |
| `SMTP_FROM_EMAIL` | `you@gmail.com` | From address |
| `SMTP_FROM_NAME` | `Bilvantis TIP` | Display name |
| `SENDGRID_API_KEY` | `SG...` | Alternative to SMTP |

### Auto-configured by deploy.sh

| Variable | Value |
|----------|-------|
| `FRONTEND_URL` | `http://<VM_IP>:3003` |
| `BACKEND_URL` | `http://<VM_IP>:8002` |
| `CELERY_BROKER_URL` | `memory://` |
| `CELERY_RESULT_BACKEND` | `cache+memory://` |

---

## Service Management

### Using systemd (after deploy.sh — recommended)
```bash
# Status
sudo systemctl status bilvantis-backend
sudo systemctl status bilvantis-frontend

# Start / Stop / Restart
sudo systemctl start   bilvantis-backend bilvantis-frontend
sudo systemctl stop    bilvantis-backend bilvantis-frontend
sudo systemctl restart bilvantis-backend bilvantis-frontend

# View live logs
sudo journalctl -u bilvantis-backend  -f
sudo journalctl -u bilvantis-frontend -f

# Enable / disable auto-start on boot
sudo systemctl enable  bilvantis-backend bilvantis-frontend
sudo systemctl disable bilvantis-backend bilvantis-frontend
```

### Using the provided scripts (no systemd / manual)
```bash
bash start.sh       # start both services
bash stop.sh        # stop both services
bash restart.sh     # restart both
bash restart.sh backend   # restart backend only
bash restart.sh frontend  # restart frontend only
bash healthcheck.sh       # check all services + endpoints
```

---

## Logs

```bash
# Live tail
tail -f logs/backend.log
tail -f logs/frontend.log

# Or via journald after systemd install
journalctl -u bilvantis-backend  -f --no-pager
journalctl -u bilvantis-frontend -f --no-pager
```

Backend logs use structured JSON (structlog). Key fields: `event`, `level`, `timestamp`.

---

## AI Analytics Pipeline

7 sequential agents powered by Groq `llama-3.3-70b-versatile`:

1. **FeedbackCollectorValidator** — validates and normalises raw feedback
2. **SentimentAnalyzer** — per-submission sentiment scoring (−1 to +1)
3. **ThemeExtractor** — clusters feedback into recurring themes
4. **Scoring** — computes trainer performance scores by dimension
5. **Recommendation** — generates actionable improvement suggestions
6. **ExecutiveSummary** — produces a 3–5 sentence summary paragraph
7. **ConversationalRAG** — answers natural-language questions about any trainer/batch

The chat endpoint is `/api/v1/analytics/chat` (POST, requires auth JWT).

---

## Background Tasks (Celery Beat)

Celery runs embedded (`memory://` broker, `task_always_eager=True` in development). Tasks run synchronously as part of the API process — no separate worker is needed.

| Task | Schedule | Description |
|------|----------|-------------|
| `check-completed-batches` | Every 5 min | Auto-closes batches whose end date has passed |
| `send-survey-reminders` | 09:00 daily | Emails participants with unfilled feedback |
| `cleanup-expired-tokens` | 02:00 daily | Removes tokens older than 72 hours |

---

## Database

SQLite database is created automatically at `backend/feedback_platform.db` when the backend first starts (via `create_all_tables()` + `seed_database()` in `app/main.py`).

**Seeded on first startup:**
- Admin user: `admin@bilvantis.io` / `Admin@1234`
- Default organization: Bilvantis

**Tables:**
`organizations`, `users`, `trainers`, `training_programs`, `training_batches`, `batch_rosters`, `feedback_submissions`, `trainer_metrics_snapshots`, `google_forms`

**Backup:**
```bash
sqlite3 backend/feedback_platform.db ".backup '/backup/tip-$(date +%Y%m%d).db'"
```

---

## Updating the Application

### Code-only update (no new dependencies)
```bash
git pull
bash restart.sh backend  # backend only
# If frontend changed:
cd frontend && npm run build && cd ..
bash restart.sh frontend
```

### Full redeploy (new packages or schema changes)
```bash
git pull
bash deploy.sh  # re-runs all steps idempotently
```

`deploy.sh` is idempotent — it skips steps that are already done (e.g., won't overwrite an existing `backend/.env`).

### VM IP changed
If the VM gets a new IP, the frontend API URL needs rebuilding:
```bash
# Edit both env files
nano backend/.env       # update FRONTEND_URL and BACKEND_URL
echo "NEXT_PUBLIC_API_URL=http://NEW_IP:8002" > frontend/.env.local
# Rebuild frontend (NEXT_PUBLIC vars are baked into the bundle at build time)
cd frontend && npm run build && cd ..
bash restart.sh
```

---

## Troubleshooting

### Backend won't start — "Cannot find module" or import error
```bash
cd backend
source .venv/bin/activate
python -c "from app.main import app; print('OK')"
# Fix any import errors, then:
deactivate
bash restart.sh backend
```

### Email shows "no provider" in System Health
1. Check `backend/.env` has `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` all set
2. The backend must be restarted after editing `.env` (settings are read at startup)
3. Test via admin panel: Settings > Email Configuration > Send Test Email

### AI chat returns errors
1. Verify `GROQ_API_KEY` in `backend/.env` is valid and starts with `gsk_`
2. Check `logs/backend.log` for the specific Groq API error message
3. Test connectivity: `curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models`

### Port already in use
```bash
# Find what's using the port
ss -tlnp | grep :8002
ss -tlnp | grep :3003
# Kill it
sudo kill $(lsof -ti:8002)
# Then restart
bash start.sh
```

### Frontend login redirects to wrong URL
The `NEXT_PUBLIC_API_URL` is baked into the Next.js bundle at build time. If the backend URL changes, rebuild:
```bash
echo "NEXT_PUBLIC_API_URL=http://CORRECT_IP:8002" > frontend/.env.local
cd frontend && npm run build && cd ..
bash restart.sh frontend
```

### Permission denied on service files
```bash
sudo chown -R www-data:www-data /opt/feedback-system-auto/logs
sudo chown -R www-data:www-data /opt/feedback-system-auto/run
sudo chown -R www-data:www-data /opt/feedback-system-auto/backend
```

---

## Security Notes

- `backend/.env` contains secrets — it is in `.gitignore` and excluded from `package.sh`
- The SQLite database file (`*.db`) is also excluded from the ZIP — the target VM gets a fresh database with the seeded admin user
- Run as a non-root user in production (systemd `User=www-data`)
- The `SECRET_KEY` is generated randomly by `deploy.sh` — each deployment has a unique key
- All JWTs are HS256 signed; feedback tokens expire in 72 hours, access tokens in 24 hours
- SMTP App Passwords are Gmail-specific credentials — they cannot access your Google account

---

*Generated for Bilvantis TIP v1.0.0 — Python 3.12 + FastAPI 0.115.5 + Next.js 15*
