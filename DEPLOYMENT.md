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
│  next start --port 3003│  uvicorn (1 worker, asyncio loop)          │
│                        │  Celery (memory:// — no Redis needed)      │
├────────────────────────┴────────────────────────────────────────────┤
│  Database : SQLite (embedded — no server)                           │
│    Path   : backend/feedback_platform.db                            │
│  Queue    : fakeredis + memory:// (embedded — no Redis)             │
│  AI       : Groq API — llama-3.3-70b-versatile (external HTTPS)    │
│  Email    : Gmail SMTP via App Password (optional, external)        │
└─────────────────────────────────────────────────────────────────────┘
```

**No external infrastructure required** — no PostgreSQL, no Redis, no Docker.

---

## VM Requirements

| Item | Minimum | Recommended |
|------|---------|-------------|
| OS | Ubuntu 20.04 / 22.04 / 24.04 | Ubuntu 22.04 LTS |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 2 GB | 4 GB |
| Disk | 10 GB free | 20 GB |
| Network | Outbound HTTPS (443) | — |
| Root | Required | — |

Python 3.12 and Node.js 20 are **installed automatically** by `deploy.sh`.

---

## What You Need Before Starting

1. **The ZIP file** — already in GitHub or copy from source VM
2. **Groq API key** — get free at [console.groq.com/keys](https://console.groq.com/keys)
3. **Gmail App Password** (optional, for email) — [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)

---

## Complete Step-by-Step Deployment

### PHASE 1 — Get the ZIP onto the VM

**Option A — Download directly from GitHub (recommended)**
```bash
# SSH into the VM first
ssh ubuntu@YOUR_VM_IP

# Install unzip if needed
sudo apt-get install -y unzip curl

# Download the ZIP from GitHub
curl -L -o bilvantis-tip.zip \
  https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto/archive/refs/heads/main.zip

# OR download a specific release ZIP (replace filename if different)
# curl -L -o bilvantis-tip.zip \
#   https://raw.githubusercontent.com/LUKALAPUSAIKUMARAO/feedback-sys-auto/main/bilvantis-tip-20260619-131906.zip
```

**Option B — Copy from source VM via SCP**
```bash
# Run this on your SOURCE machine (not the target VM)
scp bilvantis-tip-*.zip ubuntu@TARGET_VM_IP:/home/ubuntu/
```

**Option C — Clone the repo directly**
```bash
# SSH into the VM
ssh ubuntu@YOUR_VM_IP

# Install git
sudo apt-get install -y git

# Clone (no need to unzip)
git clone https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto.git feedback-system-auto
cd feedback-system-auto

# Skip PHASE 2 and go straight to PHASE 3
```

---

### PHASE 2 — Unzip and Enter the Directory

```bash
# Create a clean deployment directory
sudo mkdir -p /opt/feedback-system-auto
sudo chown $USER:$USER /opt/feedback-system-auto

# Unzip into it
unzip bilvantis-tip.zip -d /opt/feedback-system-auto

# If the zip created a nested folder (e.g. feedback-sys-auto-main/), move contents up
# Check first:
ls /opt/feedback-system-auto/

# If you see a subfolder like "feedback-sys-auto-main", run:
# mv /opt/feedback-system-auto/feedback-sys-auto-main/* /opt/feedback-system-auto/
# rm -rf /opt/feedback-system-auto/feedback-sys-auto-main

# Enter the directory
cd /opt/feedback-system-auto

# Verify the scripts are present
ls -la deploy.sh start.sh stop.sh restart.sh healthcheck.sh
```

---

### PHASE 3 — Run the Deployment Script (Single Command)

```bash
# Make sure you are inside /opt/feedback-system-auto
pwd
# Should print: /opt/feedback-system-auto

# Run deploy.sh with your credentials
sudo bash deploy.sh \
  --groq-key  gsk_YOUR_GROQ_API_KEY_HERE \
  --smtp-user lukalapusaikumar1@gmail.com \
  --smtp-pass tjwwmcpvhwtkdnlg
```

> **If you do not have SMTP credentials**, run without them (email will be disabled):
> ```bash
> sudo bash deploy.sh --groq-key gsk_YOUR_GROQ_API_KEY_HERE
> ```

**What deploy.sh does automatically (no input required):**

| Step | Action |
|------|--------|
| 1 | Installs Python 3.12 via deadsnakes PPA |
| 2 | Installs Node.js 20 LTS via NodeSource |
| 3 | Creates Python virtual environment at `backend/.venv` |
| 4 | Installs all pip packages from `backend/requirements.txt` |
| 5 | Auto-detects VM IP address |
| 6 | Creates `backend/.env` with all settings |
| 7 | Creates `frontend/.env.local` with correct API URL |
| 8 | Runs `npm install` in the frontend |
| 9 | Builds Next.js for production (`npm run build`) |
| 10 | Installs systemd service files |
| 11 | Enables services to auto-start on reboot |
| 12 | Starts backend (port 8002) and frontend (port 3003) |
| 13 | Runs health check and prints the access URLs |

**Total time: ~10–15 minutes** (mostly downloading packages)

---

### PHASE 4 — Open Firewall Ports

After deployment, open ports 3003 and 8002 so they are accessible from outside the VM:

```bash
# Ubuntu UFW firewall
sudo ufw allow 3003/tcp comment "Bilvantis Frontend"
sudo ufw allow 8002/tcp comment "Bilvantis Backend"
sudo ufw reload
sudo ufw status

# OR — RHEL / CentOS firewalld
sudo firewall-cmd --permanent --add-port=3003/tcp
sudo firewall-cmd --permanent --add-port=8002/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports

# OR — AWS / Azure / GCP: add inbound rules in the console for ports 3003 and 8002
```

---

### PHASE 5 — Verify Everything Is Running

```bash
# Run the built-in health check
bash /opt/feedback-system-auto/healthcheck.sh

# Manual checks
curl http://localhost:8002/health          # should return {"status":"healthy",...}
curl -I http://localhost:3003             # should return HTTP 200 or 302
curl http://localhost:8002/api/docs       # Swagger UI

# Check service status (if systemd is available)
sudo systemctl status bilvantis-backend
sudo systemctl status bilvantis-frontend

# View live logs
tail -f /opt/feedback-system-auto/logs/backend.log
tail -f /opt/feedback-system-auto/logs/frontend.log
```

---

### PHASE 6 — Open in Browser

Replace `YOUR_VM_IP` with the actual IP of your VM:

| URL | What you see |
|-----|-------------|
| `http://YOUR_VM_IP:3003` | Application home page |
| `http://YOUR_VM_IP:3003/admin/login` | Admin login page |
| `http://YOUR_VM_IP:8002/health` | Backend health JSON |
| `http://YOUR_VM_IP:8002/api/docs` | Swagger API documentation |

**Login credentials:**

| Field | Value |
|-------|-------|
| Email | `admin@bilvantis.io` |
| Password | `Admin@1234` |

---

## All Commands — Quick Reference

```bash
# ── 1. SSH into VM ──────────────────────────────────────────────────
ssh ubuntu@YOUR_VM_IP

# ── 2. Prepare directory ────────────────────────────────────────────
sudo apt-get install -y unzip curl
sudo mkdir -p /opt/feedback-system-auto
sudo chown $USER:$USER /opt/feedback-system-auto

# ── 3. Get the application ──────────────────────────────────────────
# Option A: from GitHub ZIP
curl -L -o bilvantis-tip.zip \
  https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto/archive/refs/heads/main.zip
unzip bilvantis-tip.zip -d /opt/feedback-system-auto

# Option B: git clone
# git clone https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto.git \
#           /opt/feedback-system-auto

# ── 4. Enter the directory ──────────────────────────────────────────
cd /opt/feedback-system-auto

# ── 5. Deploy ───────────────────────────────────────────────────────
sudo bash deploy.sh \
  --groq-key  gsk_YOUR_GROQ_KEY \
  --smtp-user your@gmail.com \
  --smtp-pass your_app_password

# ── 6. Open firewall ports ──────────────────────────────────────────
sudo ufw allow 3003/tcp
sudo ufw allow 8002/tcp
sudo ufw reload

# ── 7. Health check ─────────────────────────────────────────────────
bash healthcheck.sh

# ── 8. Access the app ───────────────────────────────────────────────
# Open browser: http://YOUR_VM_IP:3003
# Admin login:  admin@bilvantis.io / Admin@1234
```

---

## After Deployment — Day-to-Day Commands

### Start / Stop / Restart
```bash
# Using provided scripts (works with or without systemd)
bash /opt/feedback-system-auto/start.sh
bash /opt/feedback-system-auto/stop.sh
bash /opt/feedback-system-auto/restart.sh

# Restart one service only
bash /opt/feedback-system-auto/restart.sh backend
bash /opt/feedback-system-auto/restart.sh frontend

# Using systemd directly
sudo systemctl start   bilvantis-backend bilvantis-frontend
sudo systemctl stop    bilvantis-backend bilvantis-frontend
sudo systemctl restart bilvantis-backend bilvantis-frontend
sudo systemctl status  bilvantis-backend bilvantis-frontend
```

### View Logs
```bash
# Live log tails
tail -f /opt/feedback-system-auto/logs/backend.log
tail -f /opt/feedback-system-auto/logs/frontend.log

# Via systemd journal
sudo journalctl -u bilvantis-backend  -f --no-pager
sudo journalctl -u bilvantis-frontend -f --no-pager

# Last 50 lines
sudo journalctl -u bilvantis-backend  -n 50 --no-pager
```

### Health Check
```bash
bash /opt/feedback-system-auto/healthcheck.sh

# Machine-readable (for monitoring scripts)
bash /opt/feedback-system-auto/healthcheck.sh --json

# Silent (exit 0 = healthy, exit 1 = unhealthy)
bash /opt/feedback-system-auto/healthcheck.sh --quiet && echo "UP" || echo "DOWN"
```

### Backup the Database
```bash
# Snapshot the SQLite database
sqlite3 /opt/feedback-system-auto/backend/feedback_platform.db \
  ".backup '/backup/tip-$(date +%Y%m%d-%H%M%S).db'"
```

---

## Ports Reference

| Service | Port | URL |
|---------|------|-----|
| Frontend (Next.js) | **3003** | `http://VM_IP:3003` |
| Backend (FastAPI) | **8002** | `http://VM_IP:8002` |
| API Docs (Swagger) | **8002** | `http://VM_IP:8002/api/docs` |
| Health endpoint | **8002** | `http://VM_IP:8002/health` |

---

## Environment Variables (backend/.env)

Created automatically by `deploy.sh`. Edit with `nano /opt/feedback-system-auto/backend/.env`.

### Required

| Variable | Notes |
|----------|-------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./feedback_platform.db` |
| `SYNC_DATABASE_URL` | `sqlite:///./feedback_platform.db` |
| `SECRET_KEY` | Auto-generated 64-char hex string |
| `GROQ_API_KEY` | Set via `--groq-key` flag — required for AI chat |

### Optional (email)

| Variable | Notes |
|----------|-------|
| `SMTP_USER` | Gmail address |
| `SMTP_PASSWORD` | 16-char Gmail App Password |
| `SMTP_FROM_EMAIL` | Same as `SMTP_USER` |
| `SMTP_FROM_NAME` | Display name (default: `Bilvantis TIP`) |

### Auto-detected

| Variable | Value |
|----------|-------|
| `FRONTEND_URL` | `http://<VM_IP>:3003` |
| `BACKEND_URL` | `http://<VM_IP>:8002` |
| `CELERY_BROKER_URL` | `memory://` |
| `CELERY_RESULT_BACKEND` | `cache+memory://` |

After editing `.env`, restart the backend:
```bash
bash /opt/feedback-system-auto/restart.sh backend
```

---

## File Structure (after deployment)

```
/opt/feedback-system-auto/
├── deploy.sh                   ← Run once on fresh VM
├── start.sh                    ← Start both services
├── stop.sh                     ← Stop both services
├── restart.sh                  ← Restart all or one service
├── healthcheck.sh              ← Health check (exit 0/1)
├── package.sh                  ← Create ZIP for next deployment
├── .env.example                ← Template for backend/.env
├── bilvantis-backend.service   ← systemd unit (FastAPI)
├── bilvantis-frontend.service  ← systemd unit (Next.js)
├── DEPLOYMENT.md               ← This document
│
├── backend/
│   ├── .env                    ← Secrets (auto-created, never commit)
│   ├── .venv/                  ← Python 3.12 virtualenv (auto-created)
│   ├── feedback_platform.db    ← SQLite DB (auto-created at startup)
│   ├── requirements.txt
│   └── app/
│       ├── main.py             ← FastAPI entry point
│       ├── core/config.py      ← Settings loader (absolute .env path)
│       ├── core/email.py       ← SMTP / SendGrid email service
│       ├── api/v1/             ← REST API endpoints
│       ├── agents/             ← 7 Groq AI agent pipeline
│       ├── models/             ← SQLAlchemy ORM
│       └── tasks/              ← Celery background tasks
│
├── frontend/
│   ├── .env.local              ← NEXT_PUBLIC_API_URL (auto-created)
│   ├── .next/                  ← Production build (auto-created)
│   ├── package.json
│   └── src/app/                ← Next.js App Router pages
│
├── logs/
│   ├── backend.log             ← uvicorn / FastAPI logs
│   └── frontend.log            ← Next.js logs
└── run/
    ├── backend.pid             ← PID file (manual start mode)
    └── frontend.pid
```

---

## Troubleshooting

### Backend won't start
```bash
cd /opt/feedback-system-auto/backend
source .venv/bin/activate
python -c "from app.main import app; print('Import OK')"
# Fix any errors shown, then:
deactivate
bash /opt/feedback-system-auto/restart.sh backend
```

### "Email: no provider" in System Health
```bash
# 1. Check .env has SMTP values
grep SMTP /opt/feedback-system-auto/backend/.env

# 2. Edit if needed
nano /opt/feedback-system-auto/backend/.env

# 3. Restart backend so it picks up the new values
bash /opt/feedback-system-auto/restart.sh backend

# 4. Test via curl
curl -s -X POST http://localhost:8002/api/v1/settings/test-email \
  -H "Authorization: Bearer YOUR_JWT" \
  -H "Content-Type: application/json" \
  -d '{"to_email":"test@example.com"}'
```

### AI chat returns errors
```bash
# Check the key is set
grep GROQ_API_KEY /opt/feedback-system-auto/backend/.env

# Test Groq connectivity
GROQ_KEY=$(grep GROQ_API_KEY /opt/feedback-system-auto/backend/.env | cut -d= -f2-)
curl -s -H "Authorization: Bearer $GROQ_KEY" \
  https://api.groq.com/openai/v1/models | python3 -m json.tool | head -20
```

### Port already in use
```bash
# Find what's using the port
sudo ss -tlnp | grep -E ':8002|:3003'

# Kill by port
sudo kill $(sudo lsof -ti:8002) 2>/dev/null || true
sudo kill $(sudo lsof -ti:3003) 2>/dev/null || true

# Restart
bash /opt/feedback-system-auto/start.sh
```

### VM IP changed (must rebuild frontend)
```bash
NEW_IP=$(hostname -I | awk '{print $1}')
# Update backend .env
sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=http://${NEW_IP}:3003|" /opt/feedback-system-auto/backend/.env
sed -i "s|^BACKEND_URL=.*|BACKEND_URL=http://${NEW_IP}:8002|"   /opt/feedback-system-auto/backend/.env
# Update frontend env (NEXT_PUBLIC vars are baked into the bundle — must rebuild)
echo "NEXT_PUBLIC_API_URL=http://${NEW_IP}:8002" > /opt/feedback-system-auto/frontend/.env.local
cd /opt/feedback-system-auto/frontend && npm run build && cd ..
bash /opt/feedback-system-auto/restart.sh
```

### Services not starting on reboot
```bash
sudo systemctl enable bilvantis-backend bilvantis-frontend
sudo systemctl daemon-reload
```

### Permission errors on logs or database
```bash
sudo chown -R $USER:$USER /opt/feedback-system-auto/logs
sudo chown -R $USER:$USER /opt/feedback-system-auto/run
sudo chown -R $USER:$USER /opt/feedback-system-auto/backend
```

---

## Updating the Application

### Pull latest code and restart
```bash
cd /opt/feedback-system-auto
git pull origin main
bash restart.sh backend

# If frontend files changed, rebuild first:
cd frontend && npm run build && cd ..
bash restart.sh frontend
```

### Full redeploy (after package changes)
```bash
cd /opt/feedback-system-auto
git pull origin main
sudo bash deploy.sh   # idempotent — skips already-completed steps, preserves .env
```

---

## Security Notes

- `backend/.env` is excluded from ZIP and `.gitignore` — never commit it
- `*.db` files are excluded from ZIP — target VM gets a fresh database seeded with admin user
- `SECRET_KEY` is randomly generated per deployment by `deploy.sh`
- Access tokens expire in 24 hours; feedback survey tokens expire in 72 hours
- Gmail App Passwords cannot access your Google account — safe to use here

---

*Bilvantis TIP v1.0.0 — Python 3.12 + FastAPI 0.115.5 + Next.js 15 + SQLite*
