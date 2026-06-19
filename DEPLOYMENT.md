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
│  Service: bilvantis-frontend │ Service: bilvantis-backend              │
├───────────────────────────┴────────────────────────────────────────────┤
│  DATABASE   : SQLite — embedded, no server, auto-created               │
│  QUEUE      : Celery memory:// — embedded, no Redis server             │
│  AI         : Groq API (llama-3.3-70b-versatile) — external HTTPS     │
│  EMAIL      : Gmail SMTP via App Password — external, optional         │
├────────────────────────────────────────────────────────────────────────┤
│  SUPPORTED OS : Ubuntu · Debian · CentOS · RHEL · Rocky · AlmaLinux  │
│                 Fedora · Amazon Linux 2/2023 · openSUSE · Alpine       │
│  Admin : admin@bilvantis.io / Admin@1234 (seeded on first boot)        │
└────────────────────────────────────────────────────────────────────────┘
```

**Zero external infrastructure** — no PostgreSQL, no Redis, no Docker required.

---

## What You Need Before Starting

| Item | Details |
|------|---------|
| Linux VM (any major distro) | AWS, Azure, GCP, DigitalOcean, on-prem — see Supported OS above |
| Groq API key | [console.groq.com/keys](https://console.groq.com/keys) — free tier available |
| Gmail App Password | [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) — optional |
| 2+ GB RAM, 10+ GB disk | Recommended: 4 GB RAM, 20 GB disk |
| Outbound HTTPS (port 443) | For Groq API calls and Gmail SMTP |
| Root or sudo access | To install packages and create system services |

---

## COMPLETE STEP-BY-STEP DEPLOYMENT

### STEP 1 — SSH into the VM

```bash
ssh <user>@<VM_IP>
# Examples: ubuntu@10.0.0.5  |  ec2-user@10.0.0.5  |  root@10.0.0.5
```

---

### STEP 2 — Install prerequisites (one command per distro)

**Ubuntu / Debian:**
```bash
sudo apt-get update && sudo apt-get install -y unzip curl git
```

**CentOS / RHEL / Rocky / AlmaLinux / Fedora / Amazon Linux:**
```bash
sudo dnf install -y unzip curl git || sudo yum install -y unzip curl git
```

**openSUSE:**
```bash
sudo zypper install -y unzip curl git
```

**Alpine Linux:**
```bash
sudo apk add --no-cache unzip curl git bash
```

> `deploy.sh` auto-detects your distro and installs Python 3.12 and Node.js 20 automatically.

---

### STEP 3 — Get the application onto the VM

**Option A — Clone directly from GitHub** *(simplest)*

```bash
git clone https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto.git bilvantis-tip
cd bilvantis-tip
# Skip STEP 4 — go to STEP 5
```

**Option B — Download ZIP from GitHub**

```bash
curl -L -o bilvantis-tip.zip \
  https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto/archive/refs/heads/main.zip
```

**Option C — SCP from your local machine**

```bash
# Run this on your LOCAL machine (not the VM):
scp bilvantis-tip-*.zip <user>@<VM_IP>:/home/<user>/
```

---

### STEP 4 — Unzip the application

```bash
# Create install directory
sudo mkdir -p /opt/bilvantis-tip
sudo chown $(whoami):$(whoami) /opt/bilvantis-tip

# Unzip
unzip bilvantis-tip.zip -d /opt/bilvantis-tip

# GitHub archive creates a nested subfolder — flatten it:
ls /opt/bilvantis-tip/
# If you see a single subdirectory (e.g. feedback-sys-auto-main), run:
cd /opt/bilvantis-tip
shopt -s dotglob
mv feedback-sys-auto-main/* .
shopt -u dotglob
rm -rf feedback-sys-auto-main

cd /opt/bilvantis-tip
ls -la deploy.sh start.sh stop.sh restart.sh healthcheck.sh
```

---

### STEP 5 — Run the deployment script

```bash
# Full automated deploy — works on any supported Linux distro
sudo bash deploy.sh
```

To supply credentials at deploy time:

```bash
sudo bash deploy.sh \
  --groq-key  gsk_YOUR_GROQ_API_KEY \
  --smtp-user your.email@gmail.com \
  --smtp-pass your_16_char_app_password
```

**What `deploy.sh` does automatically (no user interaction required):**

| Step | Action | Duration |
|------|--------|----------|
| 1 | Fix line endings on all .sh scripts | < 1s |
| 2 | **Auto-detect OS** (Ubuntu/Debian/RHEL/Alpine…) | < 1s |
| 2 | Install system packages (curl, gcc, sqlite3, …) | ~1 min |
| 2 | Install **Python 3.12** (method varies by distro) | 1–10 min |
| 2 | Install **Node.js 20 LTS** (method varies by distro) | ~1 min |
| 3 | Create Python venv + install pip packages | ~2 min |
| 4 | Auto-detect VM IP, generate SECRET_KEY | < 1s |
| 4 | Write `backend/.env` + `frontend/.env.local` | < 1s |
| 5 | `npm install` + `npm run build` (Next.js) | ~3 min |
| 6 | Validate backend Python config | < 5s |
| 7 | Install + enable **system service** (systemd or OpenRC) | < 5s |
| 8 | Start both services, wait for readiness | ~30s |
| 9 | Health check + full status report with URLs | < 5s |

**Total: approximately 10–15 minutes** (first run). Re-runs are faster (~5 min).

**Python 3.12 installation by distro:**

| Distro | Method |
|--------|--------|
| Ubuntu | deadsnakes PPA (`add-apt-repository ppa:deadsnakes/ppa`) |
| Debian | native apt or source compile |
| RHEL/CentOS/Rocky/Alma 9+ | `dnf install python3.12` |
| RHEL/CentOS 8 | dnf (EPEL) or source compile |
| Fedora 38+ / Amazon Linux 2023 | `dnf install python3.12` |
| Amazon Linux 2 | compile from source (~8 min) |
| openSUSE | `zypper install python312` |
| Alpine 3.19+ | `apk add python3` |
| Arch / Manjaro | `pacman -S python` |
| Fallback (any) | compile Python 3.12.7 from python.org |

---

### STEP 6 — Open firewall ports

**Ubuntu / Debian (ufw):**
```bash
sudo ufw allow 3003/tcp && sudo ufw allow 8002/tcp && sudo ufw reload
```

**CentOS / RHEL / Rocky / Fedora (firewall-cmd):**
```bash
sudo firewall-cmd --permanent --add-port=3003/tcp --add-port=8002/tcp
sudo firewall-cmd --reload
```

**Alpine (iptables):**
```bash
sudo iptables -A INPUT -p tcp --dport 3003 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8002 -j ACCEPT
```

**Cloud security groups** (AWS/Azure/GCP): add inbound rules for TCP **3003** and **8002**.

---

### STEP 7 — Verify the deployment

```bash
# Full health check (run from app directory)
bash /opt/bilvantis-tip/healthcheck.sh

# Quick API ping
curl http://localhost:8002/health

# Service status (systemd distros)
sudo systemctl status bilvantis-backend
sudo systemctl status bilvantis-frontend

# Live backend log
tail -f /opt/bilvantis-tip/logs/backend.log
```

---

### STEP 8 — Open in browser

| URL | Description |
|-----|-------------|
| `http://<VM_IP>:3003/admin/login` | **Admin login — start here** |
| `http://<VM_IP>:3003` | Application home |
| `http://<VM_IP>:8002/health` | Backend health JSON |
| `http://<VM_IP>:8002/api/docs` | Swagger API documentation |

**Admin credentials (seeded automatically on first boot):**

| Field | Value |
|-------|-------|
| Email | `admin@bilvantis.io` |
| Password | `Admin@1234` |

---

## All Commands — Copy-Paste Reference

```bash
# ── 1. SSH ──────────────────────────────────────────────────────────────
ssh <user>@<VM_IP>

# ── 2. Prerequisites (pick your distro) ────────────────────────────────
sudo apt-get update && sudo apt-get install -y unzip curl git    # Debian/Ubuntu
sudo dnf install -y unzip curl git                               # RHEL/CentOS/Fedora/Amazon
sudo zypper install -y unzip curl git                            # openSUSE
sudo apk add --no-cache unzip curl git bash                      # Alpine

# ── 3A. Clone from GitHub ───────────────────────────────────────────────
git clone https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto.git bilvantis-tip
cd bilvantis-tip

# ── 3B. Download ZIP ────────────────────────────────────────────────────
curl -L -o bilvantis-tip.zip \
  https://github.com/LUKALAPUSAIKUMARAO/feedback-sys-auto/archive/refs/heads/main.zip

# ── 4. Set up directory (if using ZIP) ─────────────────────────────────
sudo mkdir -p /opt/bilvantis-tip
sudo chown $(whoami):$(whoami) /opt/bilvantis-tip
unzip bilvantis-tip.zip -d /opt/bilvantis-tip
cd /opt/bilvantis-tip
# Flatten nested GitHub archive subfolder:
shopt -s dotglob; mv feedback-sys-auto-main/* . 2>/dev/null; shopt -u dotglob
rm -rf feedback-sys-auto-main 2>/dev/null; true

# ── 5. Deploy ───────────────────────────────────────────────────────────
sudo bash deploy.sh
# With credentials:
# sudo bash deploy.sh --groq-key gsk_... --smtp-user you@gmail.com --smtp-pass xxxx

# ── 6. Open firewall ────────────────────────────────────────────────────
sudo ufw allow 3003/tcp && sudo ufw allow 8002/tcp && sudo ufw reload   # ufw
# sudo firewall-cmd --permanent --add-port=3003/tcp --add-port=8002/tcp && sudo firewall-cmd --reload  # firewalld

# ── 7. Verify ───────────────────────────────────────────────────────────
bash healthcheck.sh
curl http://localhost:8002/health

# ── 8. Open in browser ──────────────────────────────────────────────────
# http://<VM_IP>:3003/admin/login
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
sudo systemctl status bilvantis-backend bilvantis-frontend   # systemd
rc-service bilvantis-backend status                          # OpenRC (Alpine)

# ── Start / Stop / Restart (works on all distros) ───────────────────────
bash /opt/bilvantis-tip/start.sh
bash /opt/bilvantis-tip/stop.sh
bash /opt/bilvantis-tip/restart.sh
bash /opt/bilvantis-tip/restart.sh backend     # backend only
bash /opt/bilvantis-tip/restart.sh frontend    # frontend only

# ── systemd directly ─────────────────────────────────────────────────────
sudo systemctl start   bilvantis-backend bilvantis-frontend
sudo systemctl stop    bilvantis-backend bilvantis-frontend
sudo systemctl restart bilvantis-backend bilvantis-frontend
sudo systemctl enable  bilvantis-backend bilvantis-frontend   # auto-start on reboot

# ── Logs ─────────────────────────────────────────────────────────────────
tail -f /opt/bilvantis-tip/logs/backend.log
tail -f /opt/bilvantis-tip/logs/frontend.log
sudo journalctl -u bilvantis-backend  -f --no-pager     # systemd only
sudo journalctl -u bilvantis-backend  -n 50 --no-pager  # last 50 lines

# ── Health check ──────────────────────────────────────────────────────────
bash /opt/bilvantis-tip/healthcheck.sh
bash /opt/bilvantis-tip/healthcheck.sh --json    # machine-readable
bash /opt/bilvantis-tip/healthcheck.sh --quiet   # silent, exit 0/1

# ── Database backup ───────────────────────────────────────────────────────
sqlite3 /opt/bilvantis-tip/backend/feedback_platform.db \
  ".backup '/tmp/tip-$(date +%Y%m%d-%H%M%S).db'"
```

---

## File Structure After Deployment

```
/opt/bilvantis-tip/               ← application root
├── deploy.sh                     ← cross-platform deploy (idempotent)
├── start.sh                      ← start both services
├── stop.sh                       ← stop both services
├── restart.sh                    ← restart all or one service
├── healthcheck.sh                ← health check (exit 0/1)
├── package.sh                    ← create ZIP for transfer
├── .env.example                  ← env var template
├── DEPLOYMENT.md                 ← this guide
│
├── backend/
│   ├── .env                      ← secrets (created by deploy.sh, chmod 600)
│   ├── .venv/                    ← Python 3.12 venv
│   ├── feedback_platform.db      ← SQLite DB (auto-created on first start)
│   ├── requirements.txt          ← Python packages
│   └── app/
│       ├── main.py               ← FastAPI entrypoint (seed + tables on startup)
│       ├── core/config.py        ← Settings with absolute .env path
│       ├── api/v1/               ← 7 REST routers
│       ├── agents/               ← 7 Groq AI agents
│       └── models/               ← SQLAlchemy ORM (9 tables)
│
├── frontend/
│   ├── .env.local                ← NEXT_PUBLIC_API_URL (set by deploy.sh)
│   ├── .next/                    ← production build
│   └── src/app/                  ← Next.js App Router pages
│
└── logs/
    ├── deploy.log                ← full deploy output
    ├── backend.log               ← uvicorn / FastAPI
    └── frontend.log              ← Next.js production
```

---

## Troubleshooting

### Backend does not start

```bash
cd /opt/bilvantis-tip/backend
source .venv/bin/activate
python -c "from app.main import app; print('OK')"
deactivate

sudo journalctl -u bilvantis-backend -n 60 --no-pager
tail -60 /opt/bilvantis-tip/logs/backend.log
```

### Email shows "no provider" in System Health

```bash
grep SMTP /opt/bilvantis-tip/backend/.env
nano /opt/bilvantis-tip/backend/.env
bash /opt/bilvantis-tip/restart.sh backend
```

### AI chat fails

```bash
grep GROQ_API_KEY /opt/bilvantis-tip/backend/.env
KEY=$(grep GROQ_API_KEY /opt/bilvantis-tip/backend/.env | cut -d= -f2-)
curl -s -H "Authorization: Bearer $KEY" \
  https://api.groq.com/openai/v1/models | python3 -m json.tool | head -10
```

### Port already in use

```bash
# Check what's on the ports
ss -tlnp | grep -E ':3003|:8002' || netstat -tlnp | grep -E ':3003|:8002'
# Kill them
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
cd /opt/bilvantis-tip/frontend
NEXT_PUBLIC_API_URL="http://${NEW_IP}:8002" npm run build
cd ..
bash /opt/bilvantis-tip/restart.sh
```

### Services don't auto-start after reboot

```bash
# systemd
sudo systemctl enable bilvantis-backend bilvantis-frontend
# OpenRC (Alpine)
rc-update add bilvantis-backend  default
rc-update add bilvantis-frontend default
```

### Python 3.12 compile takes too long (Amazon Linux 2 / old systems)

Source compilation takes 5–10 minutes on 2-core machines. This is expected — the script handles it automatically. Watch progress with:
```bash
tail -f /opt/bilvantis-tip/logs/deploy.log
```

### Permission errors

```bash
sudo chown -R $(whoami):$(whoami) /opt/bilvantis-tip/logs
sudo chown -R $(whoami):$(whoami) /opt/bilvantis-tip/run
sudo chown -R $(whoami):$(whoami) /opt/bilvantis-tip/backend
```

---

## Updating the Application

```bash
cd /opt/bilvantis-tip
git pull origin main

# Backend-only update (Python changes, no dependency change)
bash restart.sh backend

# Frontend update (UI changes — rebuild required)
cd frontend
NEXT_PUBLIC_API_URL="$(grep BACKEND_URL backend/.env | cut -d= -f2-)" npm run build
cd ..
bash restart.sh frontend

# Full redeploy (new packages, schema changes, IP changed)
sudo bash deploy.sh     # idempotent — preserves existing backend/.env secrets
```

---

## Security Notes

- `backend/.env` — permissions 600, excluded from ZIP and `.gitignore`
- `*.db` files — excluded from ZIP; target VM gets a fresh seeded database
- `SECRET_KEY` — randomly generated by `deploy.sh` per VM (not shared between deployments)
- JWT access tokens expire in 24 h; feedback survey tokens in 72 h
- Gmail App Passwords cannot access your Google account — safe to store
- Services run as the deploying user (not root) — `NoNewPrivileges=true`

---

*Bilvantis TIP v1.0.0 — Python 3.12 + FastAPI 0.115.5 + Next.js 15 + SQLite*
*Supported: Ubuntu · Debian · CentOS · RHEL · Rocky · Alma · Fedora · Amazon Linux · openSUSE · Alpine*
