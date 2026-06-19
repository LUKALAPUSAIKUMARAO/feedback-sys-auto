# Bilvantis Training Intelligence Platform (TIP)

> AI-powered training feedback automation — from survey distribution to executive insights in under 60 seconds.

---

## Problem Statement

Enterprise L&D teams collect post-training feedback through manual Google Forms or paper surveys. The result:

- Reports take days to compile; insights arrive too late to act
- Trainer performance data is siloed per session, never aggregated over time
- Duplicate submissions and replay attacks go undetected
- HR and management cannot ask natural language questions about trainer quality trends

**TIP solves this end-to-end** — from automated feedback distribution to a 7-agent AI pipeline that produces health scores, themes, and conversational analytics.

---

## Architecture Overview

```
Participants ──► Email (SendGrid) ──► Unique JWT Feedback Link
                                                 │
                                         [Next.js 15 Form]
                                                 │
                               ┌─────────────────▼──────────────┐
                               │   FastAPI Async Backend          │
                               │   Triple Idempotency:            │
                               │   Redis JTI → Dist. Lock →      │
                               │   DB UNIQUE constraint           │
                               └─────────────────┬──────────────┘
                                                 │  Celery task (threshold met)
                               ┌─────────────────▼──────────────┐
                               │   7-Agent AI Pipeline (Groq)    │
                               │   1. FeedbackCollectorValidator  │
                               │   2. SentimentAnalyzerAgent      │
                               │   3. ThemeExtractorAgent         │
                               │   4. ScoringAgent                │
                               │   5. RecommendationAgent         │
                               │   6. ExecutiveSummaryAgent       │
                               │   7. ConversationalRAGAgent      │
                               └─────────────────┬──────────────┘
                                                 │
                               ┌─────────────────▼──────────────┐
                               │   Next.js 15 Admin Dashboard    │
                               │   Health Scores · RAG Chat       │
                               └────────────────────────────────┘
```

---

## Key Features

| Feature | Details |
|---|---|
| Automated feedback campaigns | Celery cron detects completed batches; sends personalized JWT links via SendGrid |
| Triple idempotency | Redis JTI invalidation + distributed lock + DB UNIQUE(participant, batch) |
| 7-agent AI pipeline | Groq llama-3.3-70b-versatile with llama-3.1-8b-instant fallback |
| Trainer Health Score | Weighted formula: ratings 45% + sentiment 25% + engagement 15% + risk penalty 15% |
| RAG chat | Natural language queries over feedback corpus (pgvector in prod; text-search fallback in dev) |
| RBAC | Admin and Management roles with JWT access tokens (24-hour expiry) |
| Survey reminders | Daily Celery task re-sends links to participants who have not submitted |
| Scalability path | SQLite + fakeredis in dev → PostgreSQL 15 + pgvector + Redis in prod |

---

## Quick Start

**Prerequisites:** Python 3.11+, Node.js 18+, Groq API key

```bash
# 1. Install Python dependencies
cd backend
python -m venv .venv && .\.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # Set GROQ_API_KEY and SECRET_KEY

# 2. Initialize database (SQLite — no PostgreSQL needed for dev)
python seed.py

# 3. Start backend on port 8000
uvicorn app.main:app --reload --port 8000

# 4. Install and start frontend on port 3003
cd ../frontend
npm install --legacy-peer-deps
npm run dev -- --port 3003

# 5. Open http://localhost:3003/admin/login
#    Email: admin@bilvantis.io  |  Password: Admin@1234
```

---

## API Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/api/v1/auth/login` | Admin/Management login | Public |
| GET | `/api/v1/auth/me` | Current user profile | Bearer |
| POST | `/api/v1/admin/trainers` | Create trainer | Admin |
| GET | `/api/v1/admin/trainers` | List trainers (paginated) | Admin/Mgmt |
| POST | `/api/v1/admin/programs` | Create training program | Admin |
| POST | `/api/v1/admin/batches` | Create training batch | Admin |
| POST | `/api/v1/admin/batches/{id}/participants` | Bulk upload participants | Admin |
| GET | `/api/v1/admin/batches/{id}/roster` | Roster with feedback URLs | Admin/Mgmt |
| POST | `/api/v1/admin/batches/{id}/send-links` | Trigger feedback campaign | Admin |
| GET | `/api/v1/feedback/validate/{token}` | Validate JWT feedback token | Public |
| POST | `/api/v1/feedback/submit` | Submit feedback (idempotent) | Public (JWT) |
| GET | `/api/v1/analytics/trainer/{id}` | Trainer analytics + health score | Admin/Mgmt |
| GET | `/api/v1/analytics/dashboard` | Org-wide dashboard stats | Admin/Mgmt |
| POST | `/api/v1/analytics/chat` | RAG conversational query | Admin/Mgmt |
| POST | `/api/v1/analytics/pipeline/trigger` | Manually trigger AI pipeline | Admin |

---

## Default Credentials

| Role | Email | Password |
|---|---|---|
| Admin | admin@bilvantis.io | Admin@1234 |

---

## Demo Flow

1. **Login** at `/admin/login` with admin credentials
2. **Create a Trainer** — Admin > Trainers > Add Trainer
3. **Create a Program** — Admin > Programs > New Program (e.g., "Python for Data Engineering")
4. **Create a Batch** — Admin > Batches > New Batch (link trainer + program, set dates)
5. **Upload Participants** — Batch detail > Upload Participants (JSON or CSV)
6. **Send Feedback Links** — Click "Send Feedback Links"; each participant gets a unique JWT URL
7. **Submit Feedback** — Open a feedback URL from the roster as a participant; fill the 6-dimension form
8. **Trigger AI Pipeline** — Auto-triggers when response threshold is met; or use manual trigger
9. **View Dashboard** — Admin > Dashboard shows health scores, sentiment distribution, and themes
10. **RAG Chat** — Trainer detail page > "Ask AI" — e.g., *"What are the top improvement themes for this trainer?"*

---

## Project Structure

```
feedback-system-auto/
├── backend/
│   ├── app/
│   │   ├── agents/          # 7 AI agents + orchestrator
│   │   ├── api/v1/          # FastAPI routes (auth, admin, feedback, analytics)
│   │   ├── core/            # Config, DB, security, Redis client
│   │   ├── models/          # SQLAlchemy ORM models (9 tables)
│   │   ├── schemas/         # Pydantic v2 request/response schemas
│   │   └── tasks/           # Celery tasks + Celery Beat scheduler
│   ├── migrations/          # PostgreSQL DDL (001_init.sql)
│   └── tests/               # 46 tests across 5 test files
├── frontend/
│   ├── app/admin/           # Dashboard, Trainers, Programs, Batches pages
│   ├── app/feedback/[token] # Participant feedback form
│   └── components/dashboard/ # Modals and reusable components
└── scripts/                 # PowerShell setup and start scripts
```
