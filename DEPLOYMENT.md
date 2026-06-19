# Bilvantis Training Intelligence Platform — Deployment Guide

## Application Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│              Bilvantis TIP — Production Stack                          │
├───────────────────────────┬────────────────────────────────────────────┤
│  FRONTEND                 │  BACKEND                                   │
│  Next.js 15 + React 19    │  Python 3.12 + FastAPI 0.115.5            │
│  TypeScript + Tailwind    │  SQLAlchemy 2.0 async + aiosqlite          │
│  Port: 3003               │  Port: 8002                                │
│  Systemd: frontend svc    │  Systemd: backend svc                      │
├───────────────────────────┴────────────────────────────────────────────┤
│  DATABASE   : SQLite — embedded, no server, auto-created               │
│    File     : backend/feedback_platform.db                             │
│  QUEUE      : Celery memory:// — embedded, no Redis server             │
│  AI         : Groq API (llama-3.3-70b-versatile) — external HTTPS     │
│  EMAIL      : Gmail SMTP via App Password — external, optional         │
├────────────────────────────────────────────────────────────────────────┤
│  PORTS : 3003 (frontend)  8002 (backend)                               │
│  OS    : Ubuntu 22.04 LTS                                              │
│  Admin : admin@bilvantis.io / Admin@1234 (seeded on first boot)        │
└────────────────────────────────────────────────────────────────────────┘
```

**Zero external infrastructure** — no PostgreSQL, no Redis, no Docker required.

---

## What You Need Before Starting

| Item | Where to get it |
|------|-----------------|
| Ubuntu 22.04 LTS VM | Any cloud provider (AWS, Azure, GCP, DigitalOcean) |
| Groq API key | [console.groq.com/keys](https://console.groq.com/keys) — free tier available |
| Gmail App Password | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) — optional |
| 2+ GB RAM, 10+ GB disk | Recommended: 4 GB RAM, 20 GB disk |
| Outbound HTTPS (443) | For Groq API and Gmail SMTP |
| Root or sudo access | Required to install packages and create systemd services |

---

## COMPLETE STEP-BY-STEP DEPLOYMENT

### STEP 1 — SSH into the new Ubuntu 22.04 VM

```bash
ssh ubuntu@<YOUR_NEW_VM_IP>
```

---

### STEP 2 — Install prerequisites on the VM

```bash
sudo apt-get update
sudo apt-get install -y unzip curl git
```

---

### STEP 3 — Get the application onto the VM

**Option A — Download from GitHub** *(recommended)*

```bash
# Download the pre-built deployment ZIP from GitHub
curl -L -o bilvantis-tip.zip \
  https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto/archive/refs/heads/main.zip
```

**Option B — SCP from your source machine** *(if you have the ZIP locally)*

```bash
# Run this on your SOURCE machine (not the VM):
scp bilvantis-tip-*.zip ubuntu@<NEW_VM_IP>:/home/ubuntu/
```

**Option C — Clone directly from GitHub**

```bash
git clone https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto.git bilvantis-tip
# Skip STEP 4 — go straight to STEP 5
cd bilvantis-tip
```

---

### STEP 4 — Unzip the application

```bash
# Create the install directory
sudo mkdir -p /opt/bilvantis-tip
sudo chown ubuntu:ubuntu /opt/bilvantis-tip

# Unzip
unzip bilvantis-tip.zip -d /opt/bilvantis-tip

# If GitHub download creates a nested subfolder (feedback-sys-auto-main/), flatten it:
ls /opt/bilvantis-tip/
# If you see a single subdirectory like "feedback-sys-auto-main", run:
# shopt -s dotglob && mv /opt/bilvantis-tip/feedback-sys-auto-main/* /opt/bilvantis-tip/ && shopt -u dotglob
# rm -rf /opt/bilvantis-tip/feedback-sys-auto-main

# Enter the directory
cd /opt/bilvantis-tip

# Confirm the scripts are present
ls -la deploy.sh start.sh stop.sh restart.sh healthcheck.sh
```

---

### STEP 5 — Run the deployment script

```bash
# Full automated deploy (installs Python 3.12, Node.js 20, builds frontend,
# creates systemd services, starts everything, runs health check)
sudo bash deploy.sh
```

**The script embeds default credentials from the source VM.** You may override them:

```bash
# Override AI key and/or email credentials:
sudo bash deploy.sh \
  --groq-key  gsk_YOUR_DIFFERENT_GROQ_KEY \
  --smtp-user your.email@gmail.com \
  --smtp-pass your_16_char_app_password
```

**What `deploy.sh` does automatically (no interaction required):**

| Step | Action | Duration |
|------|--------|----------|
| 1 | Fix line endings on all .sh scripts | < 1s |
| 2 | Install system packages (curl, build-essential, sqlite3…) | ~1 min |
| 2 | Install **Python 3.12** via deadsnakes PPA | ~2 min |
| 2 | Install **Node.js 20 LTS** via NodeSource | ~1 min |
| 3 | Create Python venv + install 25 pip packages | ~2 min |
| 4 | Auto-detect VM IP, generate SECRET_KEY | < 1s |
| 4 | Write `backend/.env` with all credentials | < 1s |
| 4 | Write `frontend/.env.local` with correct API URL | < 1s |
| 5 | `npm install` (frontend packages) | ~2 min |
| 5 | `npm run build` (Next.js production bundle) | ~1 min |
| 6 | Validate backend Python imports | < 5s |
| 7 | Write + enable **systemd service units** | < 5s |
| 8 | Start both services, wait for readiness | ~30s |
| 9 | Run health check, print status report | < 5s |

**Total: approximately 10–15 minutes**

---

### STEP 6 — Open firewall ports

```bash
# Allow access from outside the VM
sudo ufw allow 3003/tcp comment "Bilvantis Frontend"
sudo ufw allow 8002/tcp comment "Bilvantis Backend API"
sudo ufw reload
sudo ufw status
```

For cloud provider security groups (AWS/Azure/GCP) — add inbound rules for TCP ports **3003** and **8002**.

---

### STEP 7 — Verify the deployment

The deploy script runs this automatically, but you can re-run anytime:

```bash
# Full health check with output
bash /opt/bilvantis-tip/healthcheck.sh

# Quick API ping
curl http://localhost:8002/health

# Service status
sudo systemctl status bilvantis-backend
sudo systemctl status bilvantis-frontend

# Live logs
tail -f /opt/bilvantis-tip/logs/backend.log
```

---

### STEP 8 — Open in browser

| URL | Description |
|-----|-------------|
| `http://<VM_IP>:3003/admin/login` | **Application — Admin Login** |
| `http://<VM_IP>:3003` | Application home |
| `http://<VM_IP>:8002/health` | Backend health JSON |
| `http://<VM_IP>:8002/api/docs` | Swagger API documentation |

**Admin credentials:**

| Field | Value |
|-------|-------|
| Email | `admin@bilvantis.io` |
| Password | `Admin@1234` |

> The admin account is seeded automatically by the backend on its first startup.

---

## All Commands — Copy-Paste Reference

```bash
# ── 1. SSH into VM ─────────────────────────────────────────────────────
ssh ubuntu@NEW_VM_IP

# ── 2. Install prerequisites ────────────────────────────────────────────
sudo apt-get update && sudo apt-get install -y unzip curl git

# ── 3. Get the application ──────────────────────────────────────────────
curl -L -o bilvantis-tip.zip \
  https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto/archive/refs/heads/main.zip

# ── 4. Set up directory ─────────────────────────────────────────────────
sudo mkdir -p /opt/bilvantis-tip
sudo chown ubuntu:ubuntu /opt/bilvantis-tip
unzip bilvantis-tip.zip -d /opt/bilvantis-tip
cd /opt/bilvantis-tip
# Flatten if nested (GitHub downloads create a subfolder):
# shopt -s dotglob && mv feedback-sys-auto-main/* . && shopt -u dotglob && rm -rf feedback-sys-auto-main

# ── 5. Deploy ───────────────────────────────────────────────────────────
sudo bash deploy.sh

# ── 6. Open firewall ────────────────────────────────────────────────────
sudo ufw allow 3003/tcp && sudo ufw allow 8002/tcp && sudo ufw reload

# ── 7. Verify ───────────────────────────────────────────────────────────
bash healthcheck.sh
curl http://localhost:8002/health

# ── 8. Open in browser ──────────────────────────────────────────────────
# http://NEW_VM_IP:3003/admin/login
# Login: admin@bilvantis.io / Admin@1234
```

---

## Ports and URLs

| Service | Port | URL |
|---------|------|-----|
| Frontend (Next.js) | **3003** | `http://VM_IP:3003` |
| Admin Login | **3003** | `http://VM_IP:3003/admin/login` |
| Backend (FastAPI) | **8002** | `http://VM_IP:8002` |
| API Docs (Swagger) | **8002** | `http://VM_IP:8002/api/docs` |
| Health Endpoint | **8002** | `http://VM_IP:8002/health` |

---

## Service Management

```bash
# ── Status ──────────────────────────────────────────────────────────────
sudo systemctl status bilvantis-backend
sudo systemctl status bilvantis-frontend

# ── Start / Stop / Restart ──────────────────────────────────────────────
bash /opt/bilvantis-tip/start.sh
bash /opt/bilvantis-tip/stop.sh
bash /opt/bilvantis-tip/restart.sh
bash /opt/bilvantis-tip/restart.sh backend    # backend only
bash /opt/bilvantis-tip/restart.sh frontend   # frontend only

# Using systemd directly
sudo systemctl start   bilvantis-backend bilvantis-frontend
sudo systemctl stop    bilvantis-backend bilvantis-frontend
sudo systemctl restart bilvantis-backend bilvantis-frontend
sudo systemctl enable  bilvantis-backend bilvantis-frontend   # auto-start on reboot
sudo systemctl disable bilvantis-backend bilvantis-frontend

# ── Logs ────────────────────────────────────────────────────────────────
tail -f /opt/bilvantis-tip/logs/backend.log
tail -f /opt/bilvantis-tip/logs/frontend.log
sudo journalctl -u bilvantis-backend  -f --no-pager
sudo journalctl -u bilvantis-frontend -f --no-pager
sudo journalctl -u bilvantis-backend  -n 50 --no-pager     # last 50 lines

# ── Health check ────────────────────────────────────────────────────────
bash /opt/bilvantis-tip/healthcheck.sh
bash /opt/bilvantis-tip/healthcheck.sh --json     # machine-readable JSON
bash /opt/bilvantis-tip/healthcheck.sh --quiet    # silent, exit 0/1

# ── Database backup ─────────────────────────────────────────────────────
sqlite3 /opt/bilvantis-tip/backend/feedback_platform.db \
  ".backup '/tmp/tip-$(date +%Y%m%d-%H%M%S).db'"
```

---

## File Structure After Deployment

```
/opt/bilvantis-tip/               ← application root
├── deploy.sh                     ← main deploy script (idempotent)
├── start.sh                      ← start both services
├── stop.sh                       ← stop both services
├── restart.sh                    ← restart all or one service
├── healthcheck.sh                ← health check (exit 0/1)
├── package.sh                    ← create new ZIP for transfer
├── .env.example                  ← env var template
├── DEPLOYMENT.md                 ← this guide
│
├── backend/
│   ├── .env                      ← secrets (created by deploy.sh, 600 perms)
│   ├── .venv/                    ← Python 3.12 venv (created by deploy.sh)
│   ├── feedback_platform.db      ← SQLite DB (created on first backend start)
│   ├── requirements.txt          ← 25 Python packages
│   └── app/
│       ├── main.py               ← FastAPI entrypoint + lifespan (seed + tables)
│       ├── core/
│       │   ├── config.py         ← Settings class (absolute .env path)
│       │   └── email.py          ← SMTP / SendGrid
│       ├── api/v1/               ← 7 REST endpoint modules
│       ├── agents/               ← 7 Groq AI agent pipeline
│       ├── models/               ← SQLAlchemy ORM (9 tables)
│       └── tasks/celery_app.py   ← Celery (memory://, task_always_eager)
│
├── frontend/
│   ├── .env.local                ← NEXT_PUBLIC_API_URL (created by deploy.sh)
│   ├── .next/                    ← production build (created by deploy.sh)
│   └── src/app/                  ← Next.js App Router pages
│
└── logs/
    ├── deploy.log                ← full deploy output
    ├── backend.log               ← uvicorn / FastAPI
    └── frontend.log              ← Next.js production
```

---

## AI Analytics Pipeline

7 chained agents powered by Groq `llama-3.3-70b-versatile`:

| Agent | Role |
|-------|------|
| FeedbackCollectorValidator | Validates and normalises raw feedback data |
| SentimentAnalyzer | Sentiment scoring per submission (−1 to +1) |
| ThemeExtractor | Clusters feedback into recurring themes |
| ScoringAgent | Trainer performance scores by dimension |
| RecommendationAgent | Actionable improvement suggestions |
| ExecutiveSummary | 3–5 sentence summary paragraph |
| ConversationalRAG | Natural-language Q&A over trainer/batch data |

POST `/api/v1/analytics/chat` — requires Bearer JWT token.

---

## Background Tasks

Celery runs embedded (`memory://` broker). Tasks are synchronous — no separate worker process needed.

| Task | Schedule |
|------|----------|
| `check_completed_batches` | Every 5 minutes |
| `send_survey_reminders` | 09:00 UTC daily |
| `cleanup_expired_tokens` | 02:00 UTC daily |

---

## Troubleshooting

### Backend does not start

```bash
# Test imports manually
cd /opt/bilvantis-tip/backend
source .venv/bin/activate
python -c "from app.main import app; print('OK')"
deactivate

# Check full logs
sudo journalctl -u bilvantis-backend -n 60 --no-pager
tail -60 /opt/bilvantis-tip/logs/backend.log
```

### Email shows "no provider" in System Health

```bash
# Check values
grep SMTP /opt/bilvantis-tip/backend/.env

# Edit
nano /opt/bilvantis-tip/backend/.env

# Restart backend to pick up changes
bash /opt/bilvantis-tip/restart.sh backend
```

### AI chat fails

```bash
# Check key
grep GROQ_API_KEY /opt/bilvantis-tip/backend/.env

# Test Groq connectivity
KEY=$(grep GROQ_API_KEY /opt/bilvantis-tip/backend/.env | cut -d= -f2-)
curl -s -H "Authorization: Bearer $KEY" \
  https://api.groq.com/openai/v1/models | python3 -m json.tool | head -10
```

### Port already in use

```bash
sudo ss -tlnp | grep -E ':3003|:8002'
sudo fuser -k 8002/tcp 2>/dev/null || true
sudo fuser -k 3003/tcp 2>/dev/null || true
bash /opt/bilvantis-tip/start.sh
```

### VM IP changed — must rebuild frontend

```bash
NEW_IP=$(hostname -I | awk '{print $1}')
sed -i "s|^FRONTEND_URL=.*|FRONTEND_URL=http://${NEW_IP}:3003|" /opt/bilvantis-tip/backend/.env
sed -i "s|^BACKEND_URL=.*|BACKEND_URL=http://${NEW_IP}:8002|"   /opt/bilvantis-tip/backend/.env
echo "NEXT_PUBLIC_API_URL=http://${NEW_IP}:8002" > /opt/bilvantis-tip/frontend/.env.local
cd /opt/bilvantis-tip/frontend && NEXT_PUBLIC_API_URL="http://${NEW_IP}:8002" npm run build && cd ..
bash /opt/bilvantis-tip/restart.sh
```

### Services don't auto-start after reboot

```bash
sudo systemctl enable bilvantis-backend bilvantis-frontend
sudo systemctl daemon-reload
```

### Permission errors

```bash
sudo chown -R ubuntu:ubuntu /opt/bilvantis-tip/logs
sudo chown -R ubuntu:ubuntu /opt/bilvantis-tip/run
sudo chown -R ubuntu:ubuntu /opt/bilvantis-tip/backend
```

---

## Updating the Application

```bash
# Pull latest code
cd /opt/bilvantis-tip
git pull origin main

# Backend update only (Python changes)
bash restart.sh backend

# Frontend update (UI changes — must rebuild)
cd frontend && NEXT_PUBLIC_API_URL="$(grep BACKEND_URL backend/.env | cut -d= -f2-)" npm run build && cd ..
bash restart.sh frontend

# Full redeploy (new packages, schema changes)
sudo bash deploy.sh     # idempotent — preserves existing backend/.env
```

---

## Security Notes

- `backend/.env` — permissions 600, excluded from ZIP and `.gitignore`
- `*.db` files — excluded from ZIP; target VM gets a fresh seeded database
- `SECRET_KEY` — randomly generated by `deploy.sh` per deployment (unique per VM)
- JWT access tokens expire in 24 hours; feedback survey tokens in 72 hours
- Gmail App Passwords cannot access your Google account — safe to store
- Services run as the deploying user (not root) — `NoNewPrivileges=true`

---

*Bilvantis TIP v1.0.0 — Python 3.12 + FastAPI 0.115.5 + Next.js 15 + SQLite — Ubuntu 22.04 LTS*
