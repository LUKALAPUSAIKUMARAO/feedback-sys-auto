# Bilvantis Training Intelligence Platform (TIP)

AI-Powered enterprise training feedback analysis using a 7-agent orchestration pipeline built on Groq + Llama 3.3/4 with Gemini 2.0 Flash fallback.

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              ADMIN PORTAL (Next.js 15)               │
│  Dashboard · Trainers · Programs · Batches · Uploads │
└────────────────────┬────────────────────────────────-┘
                     │ REST API
┌────────────────────▼────────────────────────────────-┐
│               FastAPI Backend (Python 3.11)           │
│  Auth · Admin CRUD · Idempotent Feedback · Analytics  │
└────────┬────────────────────────┬────────────────────-┘
         │                        │
┌────────▼──────┐      ┌──────────▼──────────────────-─┐
│  PostgreSQL   │      │   Celery + Redis               │
│  + pgvector   │      │   Cron · Campaign · Pipeline   │
└───────────────┘      └──────────┬──────────────────-──┘
                                  │
                     ┌────────────▼─────────────────────┐
                     │      7-Agent AI Pipeline          │
                     │  1. Validator  2. Sentiment       │
                     │  3. Theme      4. Scorer          │
                     │  5. Recommender 6. Exec Summary   │
                     │  7. RAG Chat (pgvector)           │
                     │  Primary: Groq + Llama 3.3-70B   │
                     │  Fallback: Gemini 2.0 Flash       │
                     └──────────────────────────────────┘
```

## Prerequisites

| Service | Version | Install |
|---------|---------|---------|
| Python | 3.11+ | https://python.org |
| Node.js | 20+ | https://nodejs.org |
| PostgreSQL | 15+ | https://postgresql.org |
| pgvector | latest | `CREATE EXTENSION pgvector;` |
| Redis | 7+ | `winget install Redis.Redis` |

## Quick Start

### 1. Setup

```powershell
.\scripts\setup.ps1
```

This creates the Python venv, installs all dependencies, and copies `.env.example` → `.env`.

### 2. Configure Environment

Edit `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/feedback_platform
SYNC_DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/feedback_platform
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=change-this-to-a-secure-32-char-minimum-key
GROQ_API_KEY=your-groq-api-key-from-console.groq.com
GEMINI_API_KEY=your-gemini-api-key-optional
SENDGRID_API_KEY=your-sendgrid-api-key-optional
FRONTEND_URL=http://localhost:3000
```

### 3. Create Database & Run Migrations

```powershell
# Create the database first:
psql -U postgres -c "CREATE DATABASE feedback_platform;"
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS pgvector;" -d feedback_platform

# Run schema migrations:
.\scripts\migrate.ps1
```

### 4. Start All Services

```powershell
.\scripts\start.ps1
```

Opens 4 terminal windows:
- **FastAPI** on http://localhost:8000
- **Celery Worker** (background processing)
- **Celery Beat** (cron scheduler)
- **Next.js** on http://localhost:3000

## Default Credentials

| Role | Email | Password |
|------|-------|---------|
| Admin | admin@bilvantis.io | Admin@1234 |

## API Documentation

FastAPI auto-generated docs: http://localhost:8000/api/docs

## 3-Day Hackathon Roadmap

### Day 1 (Hours 1–24): Infrastructure + Core
- [x] PostgreSQL schema with pgvector, idempotency constraints
- [x] FastAPI backend: auth, admin CRUD, feedback submit
- [x] JWT tokenized feedback links + Redis locks
- [x] Celery task queue + cron polling

### Day 2 (Hours 25–48): AI Pipeline + Frontend
- [x] 7-agent pipeline: Validator → Sentiment → Themes → Scorer → Recommender → Exec Summary → RAG
- [x] Admin dashboard with KPIs, charts, risk indicators
- [x] Trainer detail pages with radar charts
- [x] Batch management with participant upload (CSV + manual)
- [x] Idempotent feedback submission form

### Day 3 (Hours 49–72): Polish + Demo
- [ ] SendGrid email integration (configure API key)
- [ ] End-to-end demo run
- [ ] Performance tuning
- [ ] Executive summary PDF generation

## Demo Script

1. **Admin Login** → http://localhost:3000 → admin@bilvantis.io / Admin@1234
2. **Create Trainer** → Admin → Trainers → Add Trainer
3. **Create Program** → Admin → Programs → New Program
4. **Create Batch** → Admin → Batches → Create Batch (set end time to 5 min from now for demo)
5. **Upload Participants** → Click the batch → Upload Participants → Manual Entry (add 5 rows)
6. **Wait for cron** (or manually trigger): → Batches → Run AI Analysis
7. **Watch pipeline** → Pipeline Run History shows agents executing
8. **View results** → Admin → Trainers → Click trainer → See health score, charts, recommendations
9. **Chat analytics** → Dashboard → Ask: "What are the top themes for this trainer?"
10. **Submit feedback** (as participant) → Copy feedback token from batch roster → Visit `/feedback/{token}`

## Key Design Decisions

- **Idempotency**: Triple-layered — JWT JTI Redis invalidation + DB unique constraint + distributed lock
- **No Trainer Portal**: Trainer data is admin-only — zero trainer authentication surface
- **No Docker**: Pure process management via PowerShell scripts
- **Dual AI**: Groq + Llama 3.3-70B (primary) with automatic Gemini 2.0 Flash fallback
- **Celery on Windows**: `-P threads` flag required (gevent not stable on Windows)

## Project Structure

```
feedback-system-auto/
├── backend/
│   ├── app/
│   │   ├── agents/          # 7 AI agents + orchestrator
│   │   ├── api/v1/          # FastAPI routes
│   │   ├── core/            # Config, DB, security, Redis
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic v2 schemas
│   │   └── tasks/           # Celery tasks + scheduler
│   └── migrations/          # PostgreSQL DDL
├── frontend/
│   ├── app/
│   │   ├── admin/           # Admin portal pages
│   │   └── feedback/[token] # Participant feedback form
│   ├── components/dashboard/ # Modals, charts
│   └── lib/                 # API client, utilities
└── scripts/                 # PowerShell process management
```
