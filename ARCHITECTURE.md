# Technical Architecture — Bilvantis Training Intelligence Platform

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  CLIENT LAYER                                 │
│  Next.js 15 (App Router)  ·  Port 3003                       │
│  Admin Portal · Feedback Form · Dashboard · RAG Chat UI      │
└───────────────────────────┬──────────────────────────────────┘
                            │ HTTPS REST (JSON)
┌───────────────────────────▼──────────────────────────────────┐
│                 FASTAPI BACKEND  (Python 3.11)                │
│  Async SQLAlchemy + aiosqlite (dev) / asyncpg (prod)         │
│  Pydantic v2 · python-jose · structlog                       │
│  Routes: /auth  /admin  /feedback  /analytics                │
└────────┬────────────────────────────┬────────────────────────┘
         │                            │
┌────────▼──────────┐   ┌────────────▼──────────────────────┐
│  DATABASE LAYER   │   │   ASYNC TASK LAYER                  │
│  Dev:  SQLite     │   │   Celery 5 + fakeredis (dev)        │
│  Prod: PostgreSQL │   │   Celery + Redis 7 (prod)           │
│        + pgvector │   │   Tasks:                            │
│  9 tables         │   │   · check_completed_batches (cron)  │
│  13 indexes       │   │   · send_feedback_campaign          │
│  5 DB triggers    │   │   · send_survey_reminders (daily)   │
└───────────────────┘   │   · run_agent_pipeline              │
                        │   · cleanup_expired_tokens (daily)  │
                        └────────────────┬──────────────────┘
                                         │
                        ┌────────────────▼──────────────────┐
                        │   7-AGENT AI PIPELINE              │
                        │   Groq API · llama-3.3-70b /       │
                        │   llama-3.1-8b-instant (fallback)  │
                        └───────────────────────────────────┘
```

---

## Component Breakdown

### Frontend (Next.js 15 App Router)

| Page | Route | Description |
|---|---|---|
| Login | `/admin/login` | JWT-based admin authentication |
| Dashboard | `/admin/dashboard` | Org-wide KPIs, trainer leaderboard |
| Trainers | `/admin/trainers` | Create/list/view trainer profiles |
| Programs | `/admin/programs` | Manage training program catalog |
| Batches | `/admin/batches` | Batch lifecycle management |
| Participants | `/admin/participants` | Global participant registry |
| Feedback Form | `/feedback/[token]` | Token-validated participant form |

### Backend (FastAPI)

- `app/api/v1/auth.py` — Login, `/me`, RBAC dependency (`require_admin`, `require_admin_or_management`)
- `app/api/v1/admin.py` — Full CRUD for trainers, programs, batches, bulk participant upload, roster management
- `app/api/v1/feedback.py` — Token validation, submission with 10-step idempotency flow
- `app/api/v1/analytics.py` — Trainer analytics, org dashboard, RAG chat, pipeline trigger
- `app/api/v1/admin_participants.py` — Global participant management

### AI Pipeline (7 Agents)

| # | Agent | Model | Role |
|---|---|---|---|
| 1 | FeedbackCollectorValidator | llama-3.1-8b-instant | Validate, clean, flag anomalies and spam |
| 2 | SentimentAnalyzerAgent | llama-3.3-70b-versatile | Per-record and batch-level sentiment scoring |
| 3 | ThemeExtractorAgent | llama-3.3-70b-versatile | Identify recurring themes from free-text |
| 4 | ScoringAgent | llama-3.3-70b-versatile | Compute weighted Trainer Health Score |
| 5 | RecommendationAgent | llama-3.3-70b-versatile | Generate prioritized coaching recommendations |
| 6 | ExecutiveSummaryAgent | llama-3.3-70b-versatile | Produce CLO-ready narrative summary |
| 7 | ConversationalRAGAgent | llama-3.3-70b-versatile | Answer natural language questions over feedback |

All agents extend `BaseAgent` which implements `_call_with_fallback`: tries primary model; on error retries with `llama-3.1-8b-instant`. Each agent returns strict JSON; algebraic fallback activates on parse failure.

### Security Layer

- **Access tokens**: HS256 JWT, 24-hour expiry, `sub` = user UUID, `role` claim
- **Feedback tokens**: HS256 JWT, 72-hour expiry, `sub` = `"feedback"`, `jti` = unique UUID, payload encodes `participant_id` + `batch_id`
- **Triple idempotency** on every submission:
  1. Redis JTI check — O(1) lookup, blocks replays in microseconds
  2. Distributed lock — `asyncio`-compatible Redis lock prevents concurrent duplicate race
  3. DB UNIQUE constraint — `UNIQUE(participant_id, batch_id)` on `feedback_submissions`

### Data Layer

- Dev: `aiosqlite` + `fakeredis` — zero external dependencies, all tests run in-memory
- Prod: `asyncpg` (async) + `psycopg2` (sync/Celery) + `Redis 7` + `pgvector` for embedding search

---

## Database Schema (9 Tables)

| Table | Purpose | Key Constraints |
|---|---|---|
| `organizations` | Multi-tenant root | `domain` UNIQUE |
| `users` | Admin/Management accounts | `UNIQUE(email, org_id)` |
| `trainers` | Trainer profiles + aggregate scores | `UNIQUE(employee_id, org_id)` |
| `training_programs` | Program catalog | Skills + competency tags arrays |
| `training_batches` | Session instances | Status enum (7 states), `UNIQUE(batch_code, org_id)` |
| `participants` | Participant registry | `UNIQUE(employee_id, org_id)` |
| `batch_rosters` | Participant enrollment junction | `UNIQUE(batch_id, participant_id)`, stores JWT token |
| `feedback_submissions` | Raw feedback + AI results | `UNIQUE(participant_id, batch_id)`, computed `overall_rating` column |
| `feedback_embeddings` | pgvector chunks for RAG | `ivfflat` cosine index (768 dimensions) |
| `pipeline_run_log` | Agent execution audit trail | Status enum, duration, per-agent log |
| `trainer_metrics_snapshots` | Historical aggregates per batch | `UNIQUE(trainer_id, batch_id)` |
| `survey_tokens` | JTI ledger for idempotency bookkeeping | `UNIQUE(participant_id, batch_id)` |

---

## Automation Workflow

```
[Cron: check_completed_batches every 5 min]
        │
        ├── Batch end_datetime <= now AND status = 'scheduled'/'ongoing'
        │         │
        │    Update status → 'completed'
        │    Trigger: send_feedback_campaign.delay(batch_id)
        │         │
        │    For each roster entry:
        │         Generate JWT feedback token
        │         Send email via SendGrid
        │         Mark feedback_link_sent = True
        │    Update batch status → 'survey_open'
        │
[Cron: send_survey_reminders daily]
        │
        └── For each 'survey_open' batch before deadline:
              Re-send to participants who have not submitted

[On feedback submit: response_count >= feedback_threshold]
        │
        └── run_agent_pipeline.delay(batch_id)
              │
              Agents 1–6 run sequentially
              Results persisted to trainer_metrics_snapshots
              trainer.overall_health_score updated
              Batch status → 'processed'

[Cron: cleanup_expired_tokens daily]
        └── Mark expired JTIs as used; close surveys past deadline
```

---

## Groq AI Integration

- **Primary model**: `llama-3.3-70b-versatile` — used for all analytical reasoning agents
- **Fast model**: `llama-3.1-8b-instant` — used for validation (Agent 1) and as fallback
- **Temperature**: 0.0 for scoring/validation (deterministic), 0.2–0.3 for summaries and RAG
- **Retry strategy**: Each agent calls `_call_with_fallback`; on Groq API error or parse failure, retries with fast model then falls back to algebraic computation
- **RAG**: pgvector cosine similarity in prod (`ivfflat` index, 768-dim); keyword text-search fallback in dev (Groq does not yet offer an embeddings API)

---

## Health Score Formula

```
Health Score = (0.45 × AvgRating)
             + (0.25 × NormalizedSentiment)   # map -1..+1 → 0..5
             + (0.15 × EngagementBonus)        # positive_themes / total_themes × 5
             - (0.15 × RiskPenalty)            # negative_theme_count × 0.3, capped at 1.5

Tiers:  Elite ≥ 4.5  |  Strong ≥ 4.0  |  Satisfactory ≥ 3.5
        Needs Improvement ≥ 3.0  |  At Risk < 3.0
```

---

## Scalability Notes

| Dimension | Dev | Production |
|---|---|---|
| Database | SQLite (aiosqlite) | PostgreSQL 15 + pgvector |
| Cache / lock | fakeredis (in-process) | Redis 7 Cluster |
| Celery broker | memory:// | Redis (separate DB) |
| Embeddings | Text-search fallback | sentence-transformers or OpenAI |
| Email | Simulated (log only) | SendGrid with delivery webhooks |
| Deployment | Single process | FastAPI behind Uvicorn + Nginx; Celery workers horizontal |
| Multi-tenancy | Single org seed | Full org isolation via `organization_id` FK on every table |
