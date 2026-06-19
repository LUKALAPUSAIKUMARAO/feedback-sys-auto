# Judges Evaluation Guide — Bilvantis Training Intelligence Platform

---

## Innovation Highlights

| What | Why It Matters |
|---|---|
| Fully automated feedback loop | No human trigger required — Celery cron detects batch completion and fires the entire campaign automatically |
| 7-agent orchestrated pipeline | Each agent has a single, well-defined responsibility; the orchestrator chains them sequentially with typed JSON handoffs |
| Triple-layer idempotency | Three independent mechanisms prevent duplicate submissions — a security property, not just a UX convenience |
| Conversational analytics on training data | HR leaders can query feedback history in plain English; the system cites sources and flags confidence |
| Zero-friction participant experience | No login, no app install — one click from email to form |

---

## Technical Complexity

### 7-Agent Pipeline Architecture

The pipeline is not a single LLM call. Each agent is a class extending `BaseAgent` with a defined contract:

```
FeedbackCollectorValidator  →  validates + cleans raw records
        │
SentimentAnalyzerAgent      →  per-record + batch sentiment scoring
        │
ThemeExtractorAgent         →  recurring themes from free-text (positive + negative)
        │
ScoringAgent                →  weighted health score formula (4 components)
        │
RecommendationAgent         →  prioritized coaching actions per dimension
        │
ExecutiveSummaryAgent       →  CLO-ready narrative paragraph
        │
ConversationalRAGAgent      →  on-demand natural language Q&A
```

- Primary model: `llama-3.3-70b-versatile` (Groq)
- Fallback model: `llama-3.1-8b-instant` (Groq)
- Algebraic fallback activates on JSON parse failure — the system never returns a 500 due to LLM output format issues

### Triple Idempotency (Feedback Submission)

The `POST /api/v1/feedback/submit` endpoint has a 10-step flow:

1. Decode and verify JWT signature + expiry
2. Check Redis JTI set (O(1) — blocks replays instantly)
3. Acquire distributed Redis lock (prevents concurrent duplicate race condition)
4. Check `feedback_submissions` table for existing row (belt-and-suspenders DB check)
5. Check `survey_tokens` ledger for used JTI
6. Look up roster record
7. Persist submission to DB
8. Mark token used in DB (`survey_tokens.is_used = True`)
9. Commit DB transaction
10. Mark JTI used in Redis (`SETEX` with expiry)

Even if Redis goes down between steps 2 and 10, the DB unique constraint (`UNIQUE(participant_id, batch_id)`) prevents a duplicate. Even if the DB is restarted, Redis still holds the invalidated JTI. Three independent systems must all fail simultaneously for a duplicate to succeed.

### Async Architecture

- All FastAPI routes are `async def` with `AsyncSession` (aiosqlite / asyncpg)
- Celery tasks bridge sync/async with `asyncio.new_event_loop().run_until_complete()`
- Redis operations (lock acquire/release, JTI check/set) are all async via `aioredis` / `fakeredis[aioredis]`
- Zero blocking I/O in request handlers

---

## AI / ML Features in Detail

### Trainer Health Score Formula

```
Health Score (0–5) =
    0.45 × AvgRating (mean of 6 dimensions, 1–5 scale)
  + 0.25 × NormalizedSentiment (sentiment_score mapped -1..+1 → 0..5)
  + 0.15 × EngagementBonus (positive_themes / total_themes × 5)
  - 0.15 × RiskPenalty (negative_theme_count × 0.3, capped at 1.5)
```

**Why this formula matters:** A trainer can score 4.8 on ratings but have highly negative free-text sentiment. The formula penalizes that. Conversely, a trainer with moderate scores but excellent engagement themes and positive sentiment can still achieve a "Strong" tier.

### Dimension Weighting

| Dimension | Weight |
|---|---|
| Technical Knowledge | 25% |
| Practical Learning | 20% |
| Session Engagement | 20% |
| Communication | 15% |
| Content Quality | 12% |
| Time Management | 8% |

Weights reflect enterprise L&D research priorities — technical competency and learning outcomes matter more than logistics.

### RAG Chat Architecture

- **Production**: pgvector `ivfflat` cosine similarity index (768 dimensions), top-8 chunks retrieved per query
- **Development**: Keyword text-search fallback (Groq does not yet offer an embeddings API)
- Response includes: prose answer, cited source batch/submission IDs, confidence score (0–1), data gaps list, follow-up question suggestions
- System prompt instructs the model to never hallucinate data not in the retrieved context

---

## Scalability Roadmap

| Layer | Current (Dev) | Production-Ready |
|---|---|---|
| Database | SQLite + aiosqlite | PostgreSQL 15 + pgvector (schema already written) |
| Cache / Idempotency | fakeredis (in-process) | Redis 7 Cluster |
| Task broker | memory:// | Redis (separate DB index) |
| Email | Simulated (log output) | SendGrid with delivery/open webhooks |
| Embeddings | Text-search fallback | sentence-transformers or OpenAI text-embedding-3-small |
| Multi-tenancy | Single org seed | Full isolation — every table has `organization_id` FK |
| Deployment | Single uvicorn process | Uvicorn + Nginx + Celery workers (horizontal) |

The PostgreSQL migration is a one-command environment variable change — the schema (`migrations/001_init.sql`) is production-ready with all indexes, triggers, and pgvector extension pre-configured.

---

## Security Features

| Feature | Implementation |
|---|---|
| Password hashing | bcrypt with cost factor 12 |
| Access tokens | HS256 JWT, 24-hour expiry, role claim enforced per route |
| Feedback tokens | HS256 JWT, 72-hour expiry, `sub="feedback"` subject check prevents access token abuse |
| JTI uniqueness | UUID4 per token; stored in `survey_tokens` table and Redis |
| Role enforcement | `require_admin` and `require_admin_or_management` FastAPI dependencies; participant role has zero portal access |
| Input validation | Pydantic v2 — ratings constrained to `[1, 5]`, all fields type-checked before handler executes |
| Injection protection | SQLAlchemy ORM with parameterized queries; no raw SQL in application code (except explicit pgvector query with bound params) |

---

## Code Quality Evidence

- **Type safety**: Pydantic v2 schemas for all API request/response models; SQLAlchemy typed column definitions
- **Structured logging**: `structlog` throughout the agent pipeline with contextual key-value pairs
- **Single Responsibility**: Each of the 7 agents is in its own file with one class and one async method
- **Fallback design**: Every agent has an algebraic fallback — the system degrades gracefully, never crashes
- **Test coverage**: 46 tests across 5 files using pytest-asyncio, httpx AsyncClient, in-memory SQLite + fakeredis — no mocking of business logic
- **No circular imports**: Clean module boundaries; agents do not import from API layer
- **Config centralization**: All environment variables defined once in `app/core/config.py` via pydantic-settings

---

## Business Impact Metrics

| Metric | Before TIP | After TIP |
|---|---|---|
| Time to insight post-training | 1–2 weeks | Under 60 seconds |
| Feedback link delivery | Manual copy-paste | Automated per participant |
| Duplicate submission rate | Undetected | Zero (triple idempotency) |
| Trainer performance queries | Quarterly Excel report | Real-time conversational query |
| Data quality | Raw, uncleaned | AI-validated, anomalies flagged |

---

## Future Roadmap (Phase 2)

1. **PDF executive report generation** — one-click export from trainer detail page
2. **Slack/Teams notification webhooks** — pipeline completion alerts to HR channels
3. **Trainer-facing coaching portal** — read-only view of their own health score and recommendations
4. **Program-level analytics** — aggregate scores across all trainers who delivered a program
5. **Predictive risk alerts** — flag trainers with declining trend before the next batch starts
6. **SSO integration** — Azure AD / Google Workspace SAML for enterprise login
