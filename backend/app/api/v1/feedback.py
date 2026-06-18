from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from jose import JWTError

from app.core.database import get_db
from app.core.security import decode_feedback_token
from app.core.redis_client import (
    acquire_submission_lock, release_submission_lock,
    mark_token_used, is_token_used
)
from app.models.db_models import (
    FeedbackSubmission, BatchRoster, SurveyToken,
    TrainingBatch, Participant
)
from app.schemas.pydantic_schemas import (
    FeedbackSubmitRequest, FeedbackSubmitResponse, FeedbackTokenValidation
)

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.get("/validate/{token}", response_model=FeedbackTokenValidation)
async def validate_token(token: str, db: AsyncSession = Depends(get_db)):
    """Validate a feedback token before showing the form."""
    try:
        payload = decode_feedback_token(token)
    except JWTError:
        return FeedbackTokenValidation(valid=False, expired=True)

    jti = payload["jti"]
    participant_id = payload["participant_id"]
    batch_id = payload["batch_id"]

    # Check Redis token invalidation
    if await is_token_used(jti):
        return FeedbackTokenValidation(valid=False, already_submitted=True)

    # Check DB token ledger
    token_record = (await db.execute(
        select(SurveyToken).where(SurveyToken.jti == jti)
    )).scalar_one_or_none()
    if token_record and token_record.is_used:
        return FeedbackTokenValidation(valid=False, already_submitted=True)

    # Check if submission already exists (belt-and-suspenders)
    existing = (await db.execute(
        select(FeedbackSubmission).where(
            FeedbackSubmission.participant_id == participant_id,
            FeedbackSubmission.batch_id == batch_id,
        )
    )).scalar_one_or_none()
    if existing:
        return FeedbackTokenValidation(valid=False, already_submitted=True)

    # Load context for UI display
    batch = (await db.execute(
        select(TrainingBatch)
        .options(
            selectinload(TrainingBatch.trainer),
            selectinload(TrainingBatch.program),
        )
        .where(TrainingBatch.id == batch_id)
    )).scalar_one_or_none()

    participant = (await db.execute(
        select(Participant).where(Participant.id == participant_id)
    )).scalar_one_or_none()

    if not batch or not participant:
        return FeedbackTokenValidation(valid=False)

    return FeedbackTokenValidation(
        valid=True,
        participant_name=participant.full_name,
        batch_title=batch.title or (batch.program.title if batch.program else ""),
        trainer_name=batch.trainer.full_name if batch.trainer else "",
        program_title=batch.program.title if batch.program else "",
        already_submitted=False,
        expired=False,
    )


@router.post("/submit", response_model=FeedbackSubmitResponse)
async def submit_feedback(
    payload: FeedbackSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # ── Step 1: Decode and validate JWT ──────────────────────────────────────
    try:
        token_payload = decode_feedback_token(payload.token)
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired feedback token")

    jti = token_payload["jti"]
    participant_id = token_payload["participant_id"]
    batch_id = token_payload["batch_id"]

    # ── Step 2: Redis token invalidation check ────────────────────────────────
    if await is_token_used(jti):
        raise HTTPException(status_code=409, detail="This feedback token has already been used")

    # ── Step 3: Distributed lock to prevent concurrent submissions ────────────
    lock_acquired = await acquire_submission_lock(participant_id, batch_id)
    if not lock_acquired:
        raise HTTPException(status_code=429, detail="Submission in progress, please wait")

    try:
        # ── Step 4: DB-level idempotency check ────────────────────────────────
        existing = (await db.execute(
            select(FeedbackSubmission).where(
                FeedbackSubmission.participant_id == participant_id,
                FeedbackSubmission.batch_id == batch_id,
            )
        )).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="Feedback already submitted for this batch")

        # ── Step 5: DB token ledger check ─────────────────────────────────────
        token_record = (await db.execute(
            select(SurveyToken).where(SurveyToken.jti == jti)
        )).scalar_one_or_none()
        if token_record and token_record.is_used:
            raise HTTPException(status_code=409, detail="This feedback link has already been used")

        # ── Step 6: Get roster record ─────────────────────────────────────────
        roster = (await db.execute(
            select(BatchRoster).where(
                BatchRoster.batch_id == batch_id,
                BatchRoster.participant_id == participant_id,
            )
        )).scalar_one_or_none()

        # ── Step 7: Persist submission ────────────────────────────────────────
        submission = FeedbackSubmission(
            batch_id=batch_id,
            participant_id=participant_id,
            roster_id=roster.id if roster else None,
            rating_technical_knowledge=payload.rating_technical_knowledge,
            rating_communication=payload.rating_communication,
            rating_session_engagement=payload.rating_session_engagement,
            rating_time_management=payload.rating_time_management,
            rating_practical_learning=payload.rating_practical_learning,
            rating_content_quality=payload.rating_content_quality,
            free_text_positive=payload.free_text_positive,
            free_text_improve=payload.free_text_improve,
            free_text_overall=payload.free_text_overall,
            is_anonymous=payload.is_anonymous,
            token_jti=jti,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(submission)

        # ── Step 8: Invalidate token in DB ────────────────────────────────────
        now = datetime.now(timezone.utc)
        if token_record:
            token_record.is_used = True
            token_record.used_at = now

        await db.commit()
        await db.refresh(submission)

        # ── Step 9: Invalidate token in Redis ─────────────────────────────────
        await mark_token_used(jti)

        # ── Step 10: Check if pipeline threshold met ──────────────────────────
        from sqlalchemy import func as sqlfunc
        response_count = (await db.execute(
            select(sqlfunc.count(FeedbackSubmission.id)).where(
                FeedbackSubmission.batch_id == batch_id
            )
        )).scalar()

        batch = (await db.execute(
            select(TrainingBatch).where(TrainingBatch.id == batch_id)
        )).scalar_one_or_none()

        if batch and response_count >= batch.feedback_threshold:
            from app.tasks.celery_tasks import run_agent_pipeline
            run_agent_pipeline.delay(str(batch_id))

        return FeedbackSubmitResponse(
            success=True,
            submission_id=str(submission.id),
            message="Thank you! Your feedback has been recorded successfully.",
        )

    finally:
        await release_submission_lock(participant_id, batch_id)
