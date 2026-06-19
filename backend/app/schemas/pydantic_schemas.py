from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum


# ─── Enums ──────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    admin = "admin"
    management = "management"
    participant = "participant"

class BatchStatus(str, Enum):
    scheduled = "scheduled"
    ongoing = "ongoing"
    completed = "completed"
    cancelled = "cancelled"
    survey_open = "survey_open"
    survey_closed = "survey_closed"
    processed = "processed"

class TrainingMode(str, Enum):
    online = "online"
    offline = "offline"
    hybrid = "hybrid"

class TrainingLevel(str, Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"
    expert = "expert"

class SentimentLabel(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


# ─── Auth ────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    role: str
    full_name: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None


# ─── Organization ─────────────────────────────────────────────────────────────

class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    domain: Optional[str] = None
    logo_url: Optional[str] = None

class OrganizationOut(BaseModel):
    id: str
    name: str
    domain: Optional[str]
    logo_url: Optional[str]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Trainer ─────────────────────────────────────────────────────────────────

class TrainerCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    employee_id: str = Field(min_length=1, max_length=100)
    email: EmailStr
    designation: Optional[str] = None
    department: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    certifications: List[dict] = Field(default_factory=list)
    bio: Optional[str] = None

class TrainerUpdate(BaseModel):
    full_name: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    skills: Optional[List[str]] = None
    certifications: Optional[List[dict]] = None
    bio: Optional[str] = None
    is_active: Optional[bool] = None

class TrainerOut(BaseModel):
    id: str
    full_name: str
    employee_id: str
    email: str
    designation: Optional[str]
    department: Optional[str]
    skills: List[str]
    certifications: List[Any]
    overall_health_score: float
    total_sessions: int
    avg_rating: float
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Training Program ─────────────────────────────────────────────────────────

class TrainingProgramCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    description: Optional[str] = None
    skills_covered: List[str] = Field(default_factory=list)
    competency_tags: List[str] = Field(default_factory=list)
    duration_hours: Optional[float] = Field(None, gt=0)
    level: Optional[TrainingLevel] = None

class TrainingProgramOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    skills_covered: List[str]
    competency_tags: List[str]
    duration_hours: Optional[float]
    level: Optional[str]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Training Batch ───────────────────────────────────────────────────────────

class TrainingBatchCreate(BaseModel):
    program_id: str
    trainer_id: str
    batch_code: str = Field(min_length=2, max_length=100)
    title: Optional[str] = None
    start_datetime: datetime
    end_datetime: datetime
    max_capacity: int = Field(default=30, ge=1, le=1000)
    venue: Optional[str] = None
    mode: TrainingMode = TrainingMode.online
    feedback_threshold: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_datetime <= self.start_datetime:
            raise ValueError("end_datetime must be after start_datetime")
        return self

class TrainingBatchOut(BaseModel):
    id: str
    program_id: str
    trainer_id: str
    batch_code: str
    title: Optional[str]
    start_datetime: datetime
    end_datetime: datetime
    max_capacity: int
    actual_enrolled: int
    venue: Optional[str]
    mode: str
    status: str
    survey_deadline: Optional[datetime]
    feedback_threshold: int
    created_at: datetime
    model_config = {"from_attributes": True}

class TrainingBatchWithRelations(TrainingBatchOut):
    trainer: Optional[TrainerOut] = None
    program: Optional[TrainingProgramOut] = None


# ─── Participant ──────────────────────────────────────────────────────────────

class ParticipantCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    employee_id: str = Field(min_length=1, max_length=100)
    department: Optional[str] = None
    designation: Optional[str] = None

class ParticipantOut(BaseModel):
    id: str
    full_name: str
    email: str
    employee_id: str
    department: Optional[str]
    designation: Optional[str]
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}

class ParticipantCSVRow(BaseModel):
    full_name: str
    email: EmailStr
    employee_id: str
    department: Optional[str] = None
    designation: Optional[str] = None


# ─── Batch Roster ─────────────────────────────────────────────────────────────

class BulkParticipantUpload(BaseModel):
    participants: List[ParticipantCreate] = Field(min_length=1, max_length=500)

class BulkUploadResult(BaseModel):
    created: int
    updated: int
    errors: List[dict]
    enrolled: int


# ─── Feedback Submission ──────────────────────────────────────────────────────

class FeedbackSubmitRequest(BaseModel):
    token: str = Field(min_length=10)
    rating_technical_knowledge: int = Field(ge=1, le=5)
    rating_communication: int = Field(ge=1, le=5)
    rating_session_engagement: int = Field(ge=1, le=5)
    rating_time_management: int = Field(ge=1, le=5)
    rating_practical_learning: int = Field(ge=1, le=5)
    rating_content_quality: int = Field(ge=1, le=5)
    free_text_positive: Optional[str] = Field(None, max_length=2000)
    free_text_improve: Optional[str] = Field(None, max_length=2000)
    free_text_overall: Optional[str] = Field(None, max_length=2000)
    is_anonymous: bool = False

    @field_validator("free_text_positive", "free_text_improve", "free_text_overall", mode="before")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) and v.strip() else None

class FeedbackSubmitResponse(BaseModel):
    success: bool
    submission_id: Optional[str] = None
    message: str

class FeedbackTokenValidation(BaseModel):
    valid: bool
    participant_name: Optional[str] = None
    batch_title: Optional[str] = None
    trainer_name: Optional[str] = None
    program_title: Optional[str] = None
    already_submitted: bool = False
    expired: bool = False


# ─── Analytics ───────────────────────────────────────────────────────────────

class RatingBreakdown(BaseModel):
    technical_knowledge: float
    communication: float
    session_engagement: float
    time_management: float
    practical_learning: float
    content_quality: float
    overall: float

class SentimentDistribution(BaseModel):
    positive: float
    negative: float
    neutral: float

class TrainerAnalyticsResponse(BaseModel):
    trainer_id: str
    trainer_name: str
    overall_health_score: float
    avg_rating: float
    total_sessions: int
    total_responses: int
    ratings: RatingBreakdown
    sentiment: SentimentDistribution
    top_themes: List[Any]
    recommendations: List[Any]
    recent_snapshots: List[dict]
    risk_flag: bool
    risk_reason: Optional[str] = None

class OrgDashboardResponse(BaseModel):
    total_trainers: int
    total_batches: int
    total_participants: int
    total_feedback_responses: int
    avg_org_health_score: float
    top_trainers: List[dict]
    at_risk_trainers: List[dict]
    recent_batches: List[dict]
    department_benchmarks: List[dict]
    monthly_trend: List[dict]

class ChatAnalyticsRequest(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    trainer_id: Optional[str] = None
    batch_id: Optional[str] = None
    time_range_days: int = Field(default=90, ge=7, le=365)

class ChatAnalyticsResponse(BaseModel):
    question: str
    answer: str
    sources: List[dict]
    confidence: float


# ─── Pipeline ─────────────────────────────────────────────────────────────────

class PipelineTriggerRequest(BaseModel):
    batch_id: str
    force: bool = False

class PipelineRunOut(BaseModel):
    id: str
    batch_id: str
    run_status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    agents_run: List[str]
    submission_count: int
    triggered_by: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ─── Program Analytics ───────────────────────────────────────────────────────

class ProgramBatchSummary(BaseModel):
    batch_id: str
    batch_code: str
    title: Optional[str]
    trainer_name: str
    start_datetime: datetime
    end_datetime: datetime
    status: str
    enrolled: int
    responses: int
    avg_rating: float
    health_score: float
    sentiment_positive: float

class ProgramAnalyticsResponse(BaseModel):
    program_id: str
    program_title: str
    description: Optional[str]
    total_batches: int
    total_participants: int
    total_responses: int
    completion_rate: float
    avg_rating: float
    avg_health_score: float
    nps: float
    sentiment_positive: float
    sentiment_negative: float
    sentiment_neutral: float
    top_themes: List[Any]
    batches: List[ProgramBatchSummary]
    monthly_trend: List[dict]


# ─── Trainer History ──────────────────────────────────────────────────────────

class TrainerHistoryPoint(BaseModel):
    batch_id: str
    batch_code: str
    program_title: str
    snapshot_date: Optional[datetime]
    health_score: float
    overall_avg: float
    response_count: int
    sentiment_positive: float
    top_themes: List[Any]

class TrainerHistoryResponse(BaseModel):
    trainer_id: str
    trainer_name: str
    total_batches: int
    history: List[TrainerHistoryPoint]
    monthly_trend: List[dict]
    consistency_score: float
    growth_score: float
    best_batch_id: Optional[str]
    best_batch_title: Optional[str]
    best_health_score: float
    worst_health_score: float


# ─── Roster ──────────────────────────────────────────────────────────────────

class RosterParticipantOut(BaseModel):
    roster_id: str
    participant_id: str
    full_name: str
    email: str
    employee_id: str
    department: Optional[str]
    feedback_link_sent: bool
    feedback_link_sent_at: Optional[datetime]
    feedback_token: Optional[str]
    feedback_url: Optional[str]
    has_submitted: bool
    submitted_at: Optional[datetime]
    model_config = {"from_attributes": True}


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
