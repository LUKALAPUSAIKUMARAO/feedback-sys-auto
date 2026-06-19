# Demo Script — Bilvantis Training Intelligence Platform

**Duration:** 7 minutes  
**Presenter setup:** Backend running on port 8000, frontend on port 3003, admin tab open at login page, participant feedback URL pre-copied from a seeded batch roster.

---

## Minute 1 — Problem Statement

**Say:**
> "Every enterprise runs training programs. After each session, someone sends out a Google Form. Two weeks later, HR exports a spreadsheet, calculates averages manually, and emails a report that nobody reads — because it arrived too late to change anything.

> There is no trainer health score. No trend analysis. No way for a CLO to ask 'Which trainers need coaching this quarter?' and get a real answer in seconds.

> Bilvantis TIP automates the entire loop — from feedback collection to AI-generated insights — and adds a conversational layer so leaders can actually query their training data."

**Show:** Keep login screen visible. No clicks yet.

---

## Minute 2 — Solution Architecture Overview

**Say:**
> "Here is what we built. When a training batch ends, a Celery cron job detects it automatically and fires personalized feedback emails to every participant — each with a cryptographically unique JWT link tied to that specific person and batch.

> When enough responses come in, a 7-agent AI pipeline triggers automatically on Groq's Llama 3.3-70B. The agents validate data quality, score sentiment, extract themes, compute a weighted Trainer Health Score, and produce an executive summary — all within 60 seconds.

> The admin dashboard shows health scores, radar charts, and a conversational RAG interface. Let me show you."

**Show:** Point to the architecture slide or README diagram if available.

---

## Minutes 3–5 — Live Demo Walkthrough

### Step 1 — Admin Login (30 seconds)

1. Navigate to `http://localhost:3003/admin/login`
2. Enter `admin@bilvantis.io` / `Admin@1234`
3. Click **Login**

**Say:** "Admin and Management users log in here. Participants never log in — they receive a direct link."

### Step 2 — Create a Trainer (30 seconds)

1. Click **Trainers** in the sidebar
2. Click **Add Trainer**
3. Fill: Name = "Ravi Kumar", Employee ID = "TR-001", Email = "ravi@bilvantis.io", Skills = "python, data engineering"
4. Click **Save**

**Say:** "Trainers are data entities — they don't have portal access. Separation of concerns."

### Step 3 — Create a Batch (45 seconds)

1. Click **Batches** > **New Batch**
2. Select the trainer just created, select a program (e.g., "Python for Data Engineering")
3. Set start/end dates, mode = Online, capacity = 30
4. Click **Create Batch**

**Say:** "The batch links a trainer, a program, and a cohort of participants. The system tracks it through its full lifecycle — from scheduled through completed to processed."

### Step 4 — Upload Participants (45 seconds)

1. Click into the batch
2. Click **Upload Participants**
3. Add 5–10 participants manually or upload the sample CSV
4. Click **Save**

**Say:** "The upload endpoint is idempotent. Upload the same CSV twice — no duplicates. Each participant gets a unique feedback token generated and stored immediately."

### Step 5 — Send Feedback Links (30 seconds)

1. Click **Send Feedback Links** on the batch page
2. Show the roster — each row has a `feedback_url` column

**Say:** "In production with a SendGrid key, each participant receives a branded email. In demo mode the URL is visible in the roster. The token is a signed JWT — it encodes the participant ID and batch ID and expires in 72 hours."

### Step 6 — Submit Feedback as a Participant (60 seconds)

1. Copy one feedback URL from the roster
2. Open it in an incognito window (or new tab)
3. Show the form pre-populated with the participant's name and batch title
4. Fill in all 6 rating dimensions (Technical Knowledge, Communication, Session Engagement, Time Management, Practical Learning, Content Quality)
5. Add free-text comments
6. Click **Submit Feedback**

**Say:** "Six quantitative dimensions plus three free-text fields. Anonymous option available. Try submitting the same link again — the system returns a 409 and tells you the feedback has already been recorded. That is the triple idempotency guard: Redis token invalidation, a distributed lock, and a database unique constraint."

### Step 7 — Trigger AI Pipeline (30 seconds)

1. Go back to the batch in the admin portal
2. Click **Run AI Analysis** (or show that it auto-triggered)
3. Show the Pipeline Run Log — agents listed: Validator, Sentiment, Theme, Scoring, Recommendation, Executive Summary

**Say:** "The pipeline auto-triggers when the response threshold is met — default is 5 responses. Here we trigger it manually for the demo. Seven agents run in sequence on Groq's API."

---

## Minute 6 — AI Analytics Demo

### Trainer Detail Page

1. Navigate to **Trainers** > click the trainer
2. Show the **Trainer Health Score** (e.g., 4.2 / 5.0 — Strong tier)
3. Show the **radar chart** — 6 dimensions plotted
4. Show **extracted themes** (e.g., "excellent practical examples", "needs more Q&A time")
5. Show **recommendations** from Agent 5 (e.g., "Allocate 10 more minutes for hands-on exercises")
6. Show the **Executive Summary** paragraph

**Say:** "The health score uses a weighted formula — ratings account for 45%, sentiment for 25%, engagement bonus 15%, and risk penalty 15%. A trainer could score 4.8 on ratings but have consistently negative sentiment in free text — the formula catches that."

### RAG Chat

1. On the trainer page, open the **Ask AI** chat panel
2. Type: *"What are the most common complaints about this trainer?"*
3. Show the response with cited sources

**Say:** "In production this uses pgvector cosine similarity over embedded feedback chunks. In dev it falls back to keyword search. The response cites which submissions it drew from and flags its confidence level."

---

## Minute 7 — Business Impact + Q&A Prep

**Say:**
> "What does this deliver commercially?

> First, time-to-insight drops from two weeks to under 60 seconds. Second, HR leaders can now ask natural language questions about their training portfolio instead of waiting for a quarterly report.

> Third — and this is the engineering differentiator — the system is fully tamper-resistant. Each feedback link is cryptographically bound to one participant and one batch. It can only be used once. Three independent mechanisms enforce this.

> The scalability path is built in: SQLite and fakeredis in dev, PostgreSQL 15 with pgvector and Redis in production. The schema is already multi-tenant — every table has an organization_id. Adding a second client is a seed record, not a re-architecture.

> The roadmap for Phase 2 includes PDF report generation, Slack/Teams notifications, a trainer-facing coaching portal, program-level analytics, predictive risk alerts, and SSO integration."

**Transition:** "Happy to take questions — on the AI pipeline design, the idempotency architecture, or the scalability plan."

---

## Presenter Notes

| Scenario | What to say |
|---|---|
| Pipeline takes >10 seconds | "Groq cold-start. In production we keep workers warm. The pipeline itself completes in under 5 seconds once the first token returns." |
| Judge asks about pgvector in dev | "Dev uses text-search fallback because Groq does not yet have an embeddings API. In production we swap in sentence-transformers or OpenAI embeddings — one line of config." |
| Judge asks about multi-tenancy | "Every table has organization_id. The default seed creates Bilvantis Technologies. Adding a second org is a single INSERT." |
| Judge asks about Celery on Windows | "We use the threads pool (-P threads). Gevent is not stable on Windows. In Linux production, gevent or prefork." |
