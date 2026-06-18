-- AI-Powered Training Intelligence Platform
-- Full Database Schema with pgvector, RBAC, strict idempotency constraints
-- PostgreSQL 15+ required

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- ORGANIZATIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255) NOT NULL,
    domain      VARCHAR(255) UNIQUE,
    logo_url    TEXT,
    settings    JSONB DEFAULT '{}',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- USERS  (RBAC: admin | management | participant)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(320) NOT NULL,
    hashed_password TEXT,
    full_name       VARCHAR(255) NOT NULL,
    employee_id     VARCHAR(100),
    role            VARCHAR(50) NOT NULL CHECK (role IN ('admin','management','participant')),
    department      VARCHAR(150),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_users_email_org UNIQUE (email, organization_id),
    CONSTRAINT uq_users_employee_id_org UNIQUE (employee_id, organization_id)
);

CREATE INDEX idx_users_org_role ON users(organization_id, role);
CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- TRAINERS  (data viewed only by Admin/Management – no login)
-- ============================================================
CREATE TABLE IF NOT EXISTS trainers (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id     UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    full_name           VARCHAR(255) NOT NULL,
    employee_id         VARCHAR(100) NOT NULL,
    email               VARCHAR(320) NOT NULL,
    designation         VARCHAR(255),
    department          VARCHAR(150),
    skills              TEXT[] DEFAULT '{}',
    certifications      JSONB DEFAULT '[]',
    bio                 TEXT,
    profile_photo_url   TEXT,
    overall_health_score DECIMAL(5,2) DEFAULT 0.00,
    total_sessions      INTEGER DEFAULT 0,
    avg_rating          DECIMAL(4,2) DEFAULT 0.00,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_trainers_employee_id_org UNIQUE (employee_id, organization_id)
);

CREATE INDEX idx_trainers_org ON trainers(organization_id);
CREATE INDEX idx_trainers_health_score ON trainers(overall_health_score DESC);

-- ============================================================
-- TRAINING PROGRAMS
-- ============================================================
CREATE TABLE IF NOT EXISTS training_programs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    title           VARCHAR(500) NOT NULL,
    description     TEXT,
    skills_covered  TEXT[] DEFAULT '{}',
    competency_tags TEXT[] DEFAULT '{}',
    duration_hours  DECIMAL(6,2),
    level           VARCHAR(50) CHECK (level IN ('beginner','intermediate','advanced','expert')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_programs_org ON training_programs(organization_id);

-- ============================================================
-- TRAINING BATCHES
-- ============================================================
CREATE TABLE IF NOT EXISTS training_batches (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    program_id      UUID NOT NULL REFERENCES training_programs(id) ON DELETE RESTRICT,
    trainer_id      UUID NOT NULL REFERENCES trainers(id) ON DELETE RESTRICT,
    batch_code      VARCHAR(100) NOT NULL,
    title           VARCHAR(500),
    start_datetime  TIMESTAMPTZ NOT NULL,
    end_datetime    TIMESTAMPTZ NOT NULL,
    max_capacity    INTEGER NOT NULL DEFAULT 30,
    actual_enrolled INTEGER NOT NULL DEFAULT 0,
    venue           VARCHAR(500),
    mode            VARCHAR(50) CHECK (mode IN ('online','offline','hybrid')) DEFAULT 'online',
    status          VARCHAR(50) NOT NULL DEFAULT 'scheduled'
                    CHECK (status IN ('scheduled','ongoing','completed','cancelled','survey_open','survey_closed','processed')),
    survey_deadline TIMESTAMPTZ,
    feedback_threshold INTEGER NOT NULL DEFAULT 5,
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_batch_code_org UNIQUE (batch_code, organization_id)
);

CREATE INDEX idx_batches_org_status ON training_batches(organization_id, status);
CREATE INDEX idx_batches_end_datetime ON training_batches(end_datetime);
CREATE INDEX idx_batches_trainer ON training_batches(trainer_id);

-- ============================================================
-- PARTICIPANTS
-- ============================================================
CREATE TABLE IF NOT EXISTS participants (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    full_name       VARCHAR(255) NOT NULL,
    email           VARCHAR(320) NOT NULL,
    employee_id     VARCHAR(100) NOT NULL,
    department      VARCHAR(150),
    designation     VARCHAR(255),
    user_id         UUID REFERENCES users(id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_participants_employee_id_org UNIQUE (employee_id, organization_id)
);

CREATE INDEX idx_participants_org ON participants(organization_id);
CREATE INDEX idx_participants_email ON participants(email);

-- ============================================================
-- BATCH ROSTERS  (junction: participants ↔ batches)
-- ============================================================
CREATE TABLE IF NOT EXISTS batch_rosters (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id        UUID NOT NULL REFERENCES training_batches(id) ON DELETE CASCADE,
    participant_id  UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    enrolled_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attendance      VARCHAR(50) DEFAULT 'enrolled'
                    CHECK (attendance IN ('enrolled','attended','absent','partial')),
    feedback_link_sent  BOOLEAN NOT NULL DEFAULT FALSE,
    feedback_link_sent_at TIMESTAMPTZ,
    feedback_token      TEXT,
    CONSTRAINT uq_batch_participant UNIQUE (batch_id, participant_id)
);

CREATE INDEX idx_rosters_batch ON batch_rosters(batch_id);
CREATE INDEX idx_rosters_participant ON batch_rosters(participant_id);

-- ============================================================
-- FEEDBACK SUBMISSIONS  (strict idempotency: one row per participant+batch)
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback_submissions (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id            UUID NOT NULL REFERENCES training_batches(id) ON DELETE CASCADE,
    participant_id      UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    roster_id           UUID REFERENCES batch_rosters(id),

    -- Quantitative ratings (1-5 scale)
    rating_technical_knowledge   SMALLINT CHECK (rating_technical_knowledge BETWEEN 1 AND 5),
    rating_communication         SMALLINT CHECK (rating_communication BETWEEN 1 AND 5),
    rating_session_engagement    SMALLINT CHECK (rating_session_engagement BETWEEN 1 AND 5),
    rating_time_management       SMALLINT CHECK (rating_time_management BETWEEN 1 AND 5),
    rating_practical_learning    SMALLINT CHECK (rating_practical_learning BETWEEN 1 AND 5),
    rating_content_quality       SMALLINT CHECK (rating_content_quality BETWEEN 1 AND 5),

    -- Computed composite
    overall_rating      DECIMAL(4,2) GENERATED ALWAYS AS (
        (rating_technical_knowledge + rating_communication + rating_session_engagement +
         rating_time_management + rating_practical_learning + rating_content_quality)::DECIMAL / 6
    ) STORED,

    -- Qualitative free-text
    free_text_positive  TEXT,
    free_text_improve   TEXT,
    free_text_overall   TEXT,

    -- Anonymity flag
    is_anonymous        BOOLEAN NOT NULL DEFAULT FALSE,

    -- AI-processed fields (populated after agent pipeline)
    sentiment_score     DECIMAL(5,4),
    sentiment_label     VARCHAR(20),
    extracted_themes    TEXT[],
    ai_processed        BOOLEAN NOT NULL DEFAULT FALSE,
    ai_processed_at     TIMESTAMPTZ,

    -- Submission metadata
    submitted_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address          INET,
    user_agent          TEXT,
    token_jti           VARCHAR(255) NOT NULL,

    -- THE KEY IDEMPOTENCY CONSTRAINT: one submission per participant per batch
    CONSTRAINT uq_feedback_participant_batch UNIQUE (participant_id, batch_id)
);

CREATE INDEX idx_feedback_batch ON feedback_submissions(batch_id);
CREATE INDEX idx_feedback_participant ON feedback_submissions(participant_id);
CREATE INDEX idx_feedback_ai_processed ON feedback_submissions(ai_processed) WHERE ai_processed = FALSE;
CREATE INDEX idx_feedback_submitted_at ON feedback_submissions(submitted_at DESC);

-- ============================================================
-- FEEDBACK EMBEDDINGS  (pgvector for RAG queries)
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback_embeddings (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id   UUID NOT NULL REFERENCES feedback_submissions(id) ON DELETE CASCADE,
    batch_id        UUID NOT NULL REFERENCES training_batches(id) ON DELETE CASCADE,
    trainer_id      UUID NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
    chunk_text      TEXT NOT NULL,
    chunk_index     SMALLINT NOT NULL DEFAULT 0,
    embedding       vector(768),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_embeddings_submission ON feedback_embeddings(submission_id);
CREATE INDEX idx_embeddings_trainer ON feedback_embeddings(trainer_id);
CREATE INDEX idx_embeddings_vector ON feedback_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- PIPELINE RUN LOG  (agent execution audit trail)
-- ============================================================
CREATE TABLE IF NOT EXISTS pipeline_run_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    batch_id        UUID NOT NULL REFERENCES training_batches(id) ON DELETE CASCADE,
    run_status      VARCHAR(50) NOT NULL DEFAULT 'pending'
                    CHECK (run_status IN ('pending','running','completed','failed','partial')),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    duration_ms     INTEGER,
    agents_run      TEXT[] DEFAULT '{}',
    submission_count INTEGER DEFAULT 0,
    raw_input_payload   JSONB DEFAULT '{}',
    raw_output_payload  JSONB DEFAULT '{}',
    error_details   TEXT,
    triggered_by    VARCHAR(100) DEFAULT 'cron',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pipeline_batch ON pipeline_run_log(batch_id);
CREATE INDEX idx_pipeline_status ON pipeline_run_log(run_status);

-- ============================================================
-- TRAINER METRICS SNAPSHOTS  (historical aggregates per batch)
-- ============================================================
CREATE TABLE IF NOT EXISTS trainer_metrics_snapshots (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trainer_id          UUID NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
    batch_id            UUID NOT NULL REFERENCES training_batches(id) ON DELETE CASCADE,
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    avg_technical       DECIMAL(4,2),
    avg_communication   DECIMAL(4,2),
    avg_engagement      DECIMAL(4,2),
    avg_time_mgmt       DECIMAL(4,2),
    avg_practical       DECIMAL(4,2),
    avg_content         DECIMAL(4,2),
    overall_avg         DECIMAL(4,2),
    health_score        DECIMAL(5,2),
    sentiment_positive  DECIMAL(5,2),
    sentiment_negative  DECIMAL(5,2),
    sentiment_neutral   DECIMAL(5,2),
    response_count      INTEGER DEFAULT 0,
    top_themes          TEXT[] DEFAULT '{}',
    recommendations     JSONB DEFAULT '[]',
    executive_summary   TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_trainer_batch_snapshot UNIQUE (trainer_id, batch_id)
);

CREATE INDEX idx_metrics_trainer ON trainer_metrics_snapshots(trainer_id);
CREATE INDEX idx_metrics_snapshot_date ON trainer_metrics_snapshots(snapshot_date DESC);

-- ============================================================
-- SURVEY TOKENS  (token ledger for idempotency bookkeeping)
-- ============================================================
CREATE TABLE IF NOT EXISTS survey_tokens (
    jti             VARCHAR(255) PRIMARY KEY,
    participant_id  UUID NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
    batch_id        UUID NOT NULL REFERENCES training_batches(id) ON DELETE CASCADE,
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ,
    is_used         BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_token_participant_batch UNIQUE (participant_id, batch_id)
);

CREATE INDEX idx_tokens_participant_batch ON survey_tokens(participant_id, batch_id);
CREATE INDEX idx_tokens_expires ON survey_tokens(expires_at);

-- ============================================================
-- TRIGGER: auto-update updated_at columns
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY['organizations','users','trainers','training_programs','training_batches','participants']
    LOOP
        EXECUTE format('
            CREATE TRIGGER trg_%s_updated_at
            BEFORE UPDATE ON %s
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()',
            tbl, tbl);
    END LOOP;
END $$;

-- ============================================================
-- SEED: default org + admin user  (password: Admin@1234)
-- ============================================================
INSERT INTO organizations (id, name, domain) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Bilvantis Technologies', 'bilvantis.io')
ON CONFLICT DO NOTHING;

INSERT INTO users (organization_id, email, hashed_password, full_name, role) VALUES
    ('00000000-0000-0000-0000-000000000001',
     'admin@bilvantis.io',
     '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/lewFObVxCm.xV1qAO',
     'Platform Admin',
     'admin')
ON CONFLICT DO NOTHING;
