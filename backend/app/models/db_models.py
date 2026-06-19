from sqlalchemy import (
    Column, String, Boolean, Integer, SmallInteger, Text, Numeric,
    DateTime, ForeignKey, CheckConstraint, UniqueConstraint, JSON, func
)
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime, timezone
import uuid


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True)
    logo_url = Column(Text)
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    users = relationship("User", back_populates="organization", lazy="dynamic")
    trainers = relationship("Trainer", back_populates="organization", lazy="dynamic")
    training_programs = relationship("TrainingProgram", back_populates="organization", lazy="dynamic")
    training_batches = relationship("TrainingBatch", back_populates="organization", lazy="dynamic")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "organization_id", name="uq_users_email_org"),
        UniqueConstraint("employee_id", "organization_id", name="uq_users_employee_id_org"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(320), nullable=False)
    hashed_password = Column(Text)
    full_name = Column(String(255), nullable=False)
    employee_id = Column(String(100))
    role = Column(String(50), nullable=False)
    department = Column(String(150))
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    organization = relationship("Organization", back_populates="users")


class Trainer(Base):
    __tablename__ = "trainers"
    __table_args__ = (
        UniqueConstraint("employee_id", "organization_id", name="uq_trainers_employee_id_org"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(255), nullable=False)
    employee_id = Column(String(100), nullable=False)
    email = Column(String(320), nullable=False)
    designation = Column(String(255))
    department = Column(String(150))
    skills = Column(JSON, default=list)
    certifications = Column(JSON, default=list)
    bio = Column(Text)
    profile_photo_url = Column(Text)
    overall_health_score = Column(Numeric(5, 2), default=0.00)
    total_sessions = Column(Integer, default=0)
    avg_rating = Column(Numeric(4, 2), default=0.00)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    organization = relationship("Organization", back_populates="trainers")
    training_batches = relationship("TrainingBatch", back_populates="trainer", lazy="dynamic")
    metrics_snapshots = relationship("TrainerMetricsSnapshot", back_populates="trainer", lazy="dynamic")
    google_forms = relationship("GoogleForm", back_populates="trainer", lazy="dynamic")


class TrainingProgram(Base):
    __tablename__ = "training_programs"

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    skills_covered = Column(JSON, default=list)
    competency_tags = Column(JSON, default=list)
    duration_hours = Column(Numeric(6, 2))
    level = Column(String(50))
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    organization = relationship("Organization", back_populates="training_programs")
    batches = relationship("TrainingBatch", back_populates="program", lazy="dynamic")


class TrainingBatch(Base):
    __tablename__ = "training_batches"
    __table_args__ = (
        UniqueConstraint("batch_code", "organization_id", name="uq_batch_code_org"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    program_id = Column(String(36), ForeignKey("training_programs.id", ondelete="RESTRICT"), nullable=False)
    trainer_id = Column(String(36), ForeignKey("trainers.id", ondelete="RESTRICT"), nullable=False)
    batch_code = Column(String(100), nullable=False)
    title = Column(String(500))
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    max_capacity = Column(Integer, nullable=False, default=30)
    actual_enrolled = Column(Integer, nullable=False, default=0)
    venue = Column(String(500))
    mode = Column(String(50), default="online")
    status = Column(String(50), nullable=False, default="scheduled")
    survey_deadline = Column(DateTime)
    feedback_threshold = Column(Integer, nullable=False, default=5)
    google_form_url = Column(Text)  # Google Form link for this batch
    created_by = Column(String(36), ForeignKey("users.id"))
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    organization = relationship("Organization", back_populates="training_batches")
    program = relationship("TrainingProgram", back_populates="batches")
    trainer = relationship("Trainer", back_populates="training_batches")
    rosters = relationship("BatchRoster", back_populates="batch", lazy="dynamic")
    feedback_submissions = relationship("FeedbackSubmission", back_populates="batch", lazy="dynamic")
    pipeline_runs = relationship("PipelineRunLog", back_populates="batch", lazy="dynamic")
    google_forms = relationship("GoogleForm", back_populates="batch", lazy="dynamic")


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("employee_id", "organization_id", name="uq_participants_employee_id_org"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(255), nullable=False)
    email = Column(String(320), nullable=False)
    employee_id = Column(String(100), nullable=False)
    department = Column(String(150))
    designation = Column(String(255))
    user_id = Column(String(36), ForeignKey("users.id"))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    rosters = relationship("BatchRoster", back_populates="participant", lazy="dynamic")
    feedback_submissions = relationship("FeedbackSubmission", back_populates="participant", lazy="dynamic")


class BatchRoster(Base):
    __tablename__ = "batch_rosters"
    __table_args__ = (
        UniqueConstraint("batch_id", "participant_id", name="uq_batch_participant"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    batch_id = Column(String(36), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(String(36), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    enrolled_at = Column(DateTime, default=_now)
    attendance = Column(String(50), default="enrolled")
    feedback_link_sent = Column(Boolean, nullable=False, default=False)
    feedback_link_sent_at = Column(DateTime)
    feedback_token = Column(Text)

    batch = relationship("TrainingBatch", back_populates="rosters")
    participant = relationship("Participant", back_populates="rosters")


class FeedbackSubmission(Base):
    """
    Stores one feedback submission per participant per batch.
    Source can be Google Forms (google_response_id set) or custom form (token_jti set).
    """
    __tablename__ = "feedback_submissions"

    id = Column(String(36), primary_key=True, default=_uuid)
    batch_id = Column(String(36), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(String(36), ForeignKey("participants.id", ondelete="SET NULL"), nullable=True)
    roster_id = Column(String(36), ForeignKey("batch_rosters.id"), nullable=True)

    # Numeric ratings (1-5, from Google Form or custom form)
    rating_technical_knowledge = Column(SmallInteger)
    rating_communication = Column(SmallInteger)
    rating_session_engagement = Column(SmallInteger)
    rating_time_management = Column(SmallInteger)
    rating_practical_learning = Column(SmallInteger)
    rating_content_quality = Column(SmallInteger)

    # Free-text answers
    free_text_positive = Column(Text)
    free_text_improve = Column(Text)
    free_text_overall = Column(Text)
    is_anonymous = Column(Boolean, nullable=False, default=True)

    # Respondent info (from Google Forms, may differ from enrolled participant)
    respondent_email = Column(String(320))
    respondent_name = Column(String(255))
    is_duplicate = Column(Boolean, nullable=False, default=False)  # flagged if same email submits twice

    # Source tracking
    source = Column(String(50), default="google_forms")  # 'google_forms' or 'custom_form'
    google_response_id = Column(String(255), unique=True)  # dedup key for Google Forms
    token_jti = Column(String(255))  # kept for custom form backward compatibility

    # AI analysis (from per-submission Groq analysis)
    processing_status = Column(String(50), nullable=False, default="pending")  # pending/processing/completed/failed
    groq_retry_count = Column(SmallInteger, nullable=False, default=0)
    groq_trainer_rating = Column(Numeric(4, 2))
    groq_strengths = Column(JSON, default=list)
    groq_improvements = Column(JSON, default=list)
    groq_summary = Column(Text)
    groq_recommendation = Column(Text)

    # Legacy AI fields (from batch-level pipeline)
    sentiment_score = Column(Numeric(5, 4))
    sentiment_label = Column(String(20))
    extracted_themes = Column(JSON, default=list)
    ai_processed = Column(Boolean, nullable=False, default=False)
    ai_processed_at = Column(DateTime)

    submitted_at = Column(DateTime, default=_now)
    ip_address = Column(String(45))
    user_agent = Column(Text)

    batch = relationship("TrainingBatch", back_populates="feedback_submissions")
    participant = relationship("Participant", back_populates="feedback_submissions")
    embeddings = relationship("FeedbackEmbedding", back_populates="submission", lazy="select")


class FeedbackEmbedding(Base):
    __tablename__ = "feedback_embeddings"

    id = Column(String(36), primary_key=True, default=_uuid)
    submission_id = Column(String(36), ForeignKey("feedback_submissions.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(String(36), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    trainer_id = Column(String(36), ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(SmallInteger, nullable=False, default=0)
    embedding = Column(Text)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=_now)

    submission = relationship("FeedbackSubmission", back_populates="embeddings")


class PipelineRunLog(Base):
    __tablename__ = "pipeline_run_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    batch_id = Column(String(36), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    run_status = Column(String(50), nullable=False, default="pending")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_ms = Column(Integer)
    agents_run = Column(JSON, default=list)
    submission_count = Column(Integer, default=0)
    raw_input_payload = Column(JSON, default=dict)
    raw_output_payload = Column(JSON, default=dict)
    error_details = Column(Text)
    triggered_by = Column(String(100), default="cron")
    created_at = Column(DateTime, default=_now)

    batch = relationship("TrainingBatch", back_populates="pipeline_runs")


class TrainerMetricsSnapshot(Base):
    __tablename__ = "trainer_metrics_snapshots"
    __table_args__ = (
        UniqueConstraint("trainer_id", "batch_id", name="uq_trainer_batch_snapshot"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    trainer_id = Column(String(36), ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(String(36), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    snapshot_date = Column(DateTime, default=_now)
    avg_technical = Column(Numeric(4, 2))
    avg_communication = Column(Numeric(4, 2))
    avg_engagement = Column(Numeric(4, 2))
    avg_time_mgmt = Column(Numeric(4, 2))
    avg_practical = Column(Numeric(4, 2))
    avg_content = Column(Numeric(4, 2))
    overall_avg = Column(Numeric(4, 2))
    health_score = Column(Numeric(5, 2))
    sentiment_positive = Column(Numeric(5, 2))
    sentiment_negative = Column(Numeric(5, 2))
    sentiment_neutral = Column(Numeric(5, 2))
    response_count = Column(Integer, default=0)
    top_themes = Column(JSON, default=list)
    recommendations = Column(JSON, default=list)
    executive_summary = Column(Text)
    created_at = Column(DateTime, default=_now)

    trainer = relationship("Trainer", back_populates="metrics_snapshots")


class SurveyToken(Base):
    __tablename__ = "survey_tokens"
    __table_args__ = (
        UniqueConstraint("participant_id", "batch_id", name="uq_token_participant_batch"),
    )

    jti = Column(String(255), primary_key=True)
    participant_id = Column(String(36), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(String(36), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    issued_at = Column(DateTime, default=_now)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime)
    is_used = Column(Boolean, nullable=False, default=False)


# ─── Google Forms Integration ─────────────────────────────────────────────────

class GoogleForm(Base):
    """
    Registry of Google Forms linked to training batches.
    One form per batch; all post to the same webhook endpoint.
    """
    __tablename__ = "google_forms"
    __table_args__ = (
        UniqueConstraint("batch_id", name="uq_google_form_batch"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(String(36), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    trainer_id = Column(String(36), ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False)
    training_program_id = Column(String(36), ForeignKey("training_programs.id", ondelete="SET NULL"), nullable=True)
    form_url = Column(Text, nullable=False)        # Google Form URL (public sharing link)
    form_id = Column(String(255))                  # Google Form ID (extracted from URL)
    sheet_id = Column(String(255))                 # Google Sheet ID linked to the form
    sheet_url = Column(Text)                       # Google Sheet URL for manual access
    status = Column(String(50), nullable=False, default="active")  # active / closed / archived
    webhook_secret = Column(String(255))           # optional HMAC secret for Apps Script auth
    last_synced_at = Column(DateTime)              # last time responses were fetched
    last_synced_row = Column(Integer, default=1)   # checkpoint: last processed sheet row
    total_responses = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    batch = relationship("TrainingBatch", back_populates="google_forms")
    trainer = relationship("Trainer", back_populates="google_forms")
    sync_logs = relationship("GoogleFormSyncLog", back_populates="google_form", lazy="dynamic")


class GoogleFormSyncLog(Base):
    """
    Audit log for every Google Form response processing attempt.
    Enables idempotency, retry tracking, and monitoring.
    """
    __tablename__ = "google_form_sync_log"

    id = Column(String(36), primary_key=True, default=_uuid)
    google_form_id = Column(String(36), ForeignKey("google_forms.id", ondelete="CASCADE"), nullable=True)
    batch_id = Column(String(36), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    google_response_id = Column(String(255), nullable=False)  # unique per Google Form response
    submission_id = Column(String(36), ForeignKey("feedback_submissions.id"), nullable=True)
    status = Column(String(50), nullable=False, default="received")
    # received → processing → completed | failed | duplicate | skipped
    received_at = Column(DateTime, default=_now)
    processed_at = Column(DateTime)
    retry_count = Column(SmallInteger, nullable=False, default=0)
    error_message = Column(Text)
    raw_payload = Column(JSON, default=dict)
    respondent_email = Column(String(320))

    google_form = relationship("GoogleForm", back_populates="sync_logs")
