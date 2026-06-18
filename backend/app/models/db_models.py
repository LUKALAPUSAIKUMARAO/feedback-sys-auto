from sqlalchemy import (
    Column, String, Boolean, Integer, SmallInteger, Text, DECIMAL,
    DateTime, ForeignKey, CheckConstraint, UniqueConstraint, Index,
    ARRAY, func, INET
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.core.database import Base
import uuid


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    domain = Column(String(255), unique=True)
    logo_url = Column(Text)
    settings = Column(JSONB, default={})
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="organization", lazy="dynamic")
    trainers = relationship("Trainer", back_populates="organization", lazy="dynamic")
    training_programs = relationship("TrainingProgram", back_populates="organization", lazy="dynamic")
    training_batches = relationship("TrainingBatch", back_populates="organization", lazy="dynamic")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "organization_id", name="uq_users_email_org"),
        UniqueConstraint("employee_id", "organization_id", name="uq_users_employee_id_org"),
        CheckConstraint("role IN ('admin','management','participant')", name="ck_users_role"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(320), nullable=False)
    hashed_password = Column(Text)
    full_name = Column(String(255), nullable=False)
    employee_id = Column(String(100))
    role = Column(String(50), nullable=False)
    department = Column(String(150))
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="users")


class Trainer(Base):
    __tablename__ = "trainers"
    __table_args__ = (
        UniqueConstraint("employee_id", "organization_id", name="uq_trainers_employee_id_org"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(255), nullable=False)
    employee_id = Column(String(100), nullable=False)
    email = Column(String(320), nullable=False)
    designation = Column(String(255))
    department = Column(String(150))
    skills = Column(ARRAY(Text), default=[])
    certifications = Column(JSONB, default=[])
    bio = Column(Text)
    profile_photo_url = Column(Text)
    overall_health_score = Column(DECIMAL(5, 2), default=0.00)
    total_sessions = Column(Integer, default=0)
    avg_rating = Column(DECIMAL(4, 2), default=0.00)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="trainers")
    training_batches = relationship("TrainingBatch", back_populates="trainer", lazy="dynamic")
    metrics_snapshots = relationship("TrainerMetricsSnapshot", back_populates="trainer", lazy="dynamic")


class TrainingProgram(Base):
    __tablename__ = "training_programs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    skills_covered = Column(ARRAY(Text), default=[])
    competency_tags = Column(ARRAY(Text), default=[])
    duration_hours = Column(DECIMAL(6, 2))
    level = Column(String(50))
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="training_programs")
    batches = relationship("TrainingBatch", back_populates="program", lazy="dynamic")


class TrainingBatch(Base):
    __tablename__ = "training_batches"
    __table_args__ = (
        UniqueConstraint("batch_code", "organization_id", name="uq_batch_code_org"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    program_id = Column(UUID(as_uuid=True), ForeignKey("training_programs.id", ondelete="RESTRICT"), nullable=False)
    trainer_id = Column(UUID(as_uuid=True), ForeignKey("trainers.id", ondelete="RESTRICT"), nullable=False)
    batch_code = Column(String(100), nullable=False)
    title = Column(String(500))
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)
    max_capacity = Column(Integer, nullable=False, default=30)
    actual_enrolled = Column(Integer, nullable=False, default=0)
    venue = Column(String(500))
    mode = Column(String(50), default="online")
    status = Column(String(50), nullable=False, default="scheduled")
    survey_deadline = Column(DateTime(timezone=True))
    feedback_threshold = Column(Integer, nullable=False, default=5)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="training_batches")
    program = relationship("TrainingProgram", back_populates="batches")
    trainer = relationship("Trainer", back_populates="training_batches")
    rosters = relationship("BatchRoster", back_populates="batch", lazy="dynamic")
    feedback_submissions = relationship("FeedbackSubmission", back_populates="batch", lazy="dynamic")
    pipeline_runs = relationship("PipelineRunLog", back_populates="batch", lazy="dynamic")


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (
        UniqueConstraint("employee_id", "organization_id", name="uq_participants_employee_id_org"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    full_name = Column(String(255), nullable=False)
    email = Column(String(320), nullable=False)
    employee_id = Column(String(100), nullable=False)
    department = Column(String(150))
    designation = Column(String(255))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    rosters = relationship("BatchRoster", back_populates="participant", lazy="dynamic")
    feedback_submissions = relationship("FeedbackSubmission", back_populates="participant", lazy="dynamic")


class BatchRoster(Base):
    __tablename__ = "batch_rosters"
    __table_args__ = (
        UniqueConstraint("batch_id", "participant_id", name="uq_batch_participant"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    enrolled_at = Column(DateTime(timezone=True), server_default=func.now())
    attendance = Column(String(50), default="enrolled")
    feedback_link_sent = Column(Boolean, nullable=False, default=False)
    feedback_link_sent_at = Column(DateTime(timezone=True))
    feedback_token = Column(Text)

    batch = relationship("TrainingBatch", back_populates="rosters")
    participant = relationship("Participant", back_populates="rosters")


class FeedbackSubmission(Base):
    __tablename__ = "feedback_submissions"
    __table_args__ = (
        UniqueConstraint("participant_id", "batch_id", name="uq_feedback_participant_batch"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    roster_id = Column(UUID(as_uuid=True), ForeignKey("batch_rosters.id"))

    rating_technical_knowledge = Column(SmallInteger)
    rating_communication = Column(SmallInteger)
    rating_session_engagement = Column(SmallInteger)
    rating_time_management = Column(SmallInteger)
    rating_practical_learning = Column(SmallInteger)
    rating_content_quality = Column(SmallInteger)

    free_text_positive = Column(Text)
    free_text_improve = Column(Text)
    free_text_overall = Column(Text)
    is_anonymous = Column(Boolean, nullable=False, default=False)

    sentiment_score = Column(DECIMAL(5, 4))
    sentiment_label = Column(String(20))
    extracted_themes = Column(ARRAY(Text))
    ai_processed = Column(Boolean, nullable=False, default=False)
    ai_processed_at = Column(DateTime(timezone=True))

    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(INET)
    user_agent = Column(Text)
    token_jti = Column(String(255), nullable=False)

    batch = relationship("TrainingBatch", back_populates="feedback_submissions")
    participant = relationship("Participant", back_populates="feedback_submissions")
    embeddings = relationship("FeedbackEmbedding", back_populates="submission", lazy="dynamic")


class FeedbackEmbedding(Base):
    __tablename__ = "feedback_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("feedback_submissions.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    trainer_id = Column(UUID(as_uuid=True), ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(SmallInteger, nullable=False, default=0)
    embedding = Column(Vector(768))
    metadata_ = Column("metadata", JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    submission = relationship("FeedbackSubmission", back_populates="embeddings")


class PipelineRunLog(Base):
    __tablename__ = "pipeline_run_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    run_status = Column(String(50), nullable=False, default="pending")
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    agents_run = Column(ARRAY(Text), default=[])
    submission_count = Column(Integer, default=0)
    raw_input_payload = Column(JSONB, default={})
    raw_output_payload = Column(JSONB, default={})
    error_details = Column(Text)
    triggered_by = Column(String(100), default="cron")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    batch = relationship("TrainingBatch", back_populates="pipeline_runs")


class TrainerMetricsSnapshot(Base):
    __tablename__ = "trainer_metrics_snapshots"
    __table_args__ = (
        UniqueConstraint("trainer_id", "batch_id", name="uq_trainer_batch_snapshot"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trainer_id = Column(UUID(as_uuid=True), ForeignKey("trainers.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    snapshot_date = Column(DateTime(timezone=True), server_default=func.now())
    avg_technical = Column(DECIMAL(4, 2))
    avg_communication = Column(DECIMAL(4, 2))
    avg_engagement = Column(DECIMAL(4, 2))
    avg_time_mgmt = Column(DECIMAL(4, 2))
    avg_practical = Column(DECIMAL(4, 2))
    avg_content = Column(DECIMAL(4, 2))
    overall_avg = Column(DECIMAL(4, 2))
    health_score = Column(DECIMAL(5, 2))
    sentiment_positive = Column(DECIMAL(5, 2))
    sentiment_negative = Column(DECIMAL(5, 2))
    sentiment_neutral = Column(DECIMAL(5, 2))
    response_count = Column(Integer, default=0)
    top_themes = Column(ARRAY(Text), default=[])
    recommendations = Column(JSONB, default=[])
    executive_summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    trainer = relationship("Trainer", back_populates="metrics_snapshots")


class SurveyToken(Base):
    __tablename__ = "survey_tokens"
    __table_args__ = (
        UniqueConstraint("participant_id", "batch_id", name="uq_token_participant_batch"),
    )

    jti = Column(String(255), primary_key=True)
    participant_id = Column(UUID(as_uuid=True), ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(UUID(as_uuid=True), ForeignKey("training_batches.id", ondelete="CASCADE"), nullable=False)
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))
    is_used = Column(Boolean, nullable=False, default=False)
