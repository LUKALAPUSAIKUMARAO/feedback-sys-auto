"""
Google Forms Webhook — receives POST from Google Apps Script on form submit.
Single endpoint handles ALL registered forms; batch is identified by batch_id in payload.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from app.core.database import get_db
from app.models.db_models import (
    TrainingBatch, FeedbackSubmission, Participant, BatchRoster,
    GoogleForm, GoogleFormSyncLog
)
import structlog

log = structlog.get_logger()

router = APIRouter(prefix="/webhook", tags=["Webhook"])

DEFAULT_ORG = "00000000-0000-0000-0000-000000000001"


# ─── Request Schema ───────────────────────────────────────────────────────────

class GoogleFormPayload(BaseModel):
    """
    Payload sent by Google Apps Script on each form submission.
    batch_id is hardcoded per-form in the Apps Script.
    google_response_id is the unique ID from Google Forms (e.ResponseId).
    """
    batch_id: str
    google_response_id: str
    timestamp: Optional[str] = None
    respondent_email: Optional[str] = None
    respondent_name: Optional[str] = None

    # Rating questions (1–5 linear scale from Google Form)
    rating_technical_knowledge: Optional[int] = None
    rating_communication: Optional[int] = None
    rating_session_engagement: Optional[int] = None
    rating_time_management: Optional[int] = None
    rating_practical_learning: Optional[int] = None
    rating_content_quality: Optional[int] = None

    # Free-text questions
    free_text_positive: Optional[str] = None
    free_text_improve: Optional[str] = None
    free_text_overall: Optional[str] = None


# ─── Background: Groq analysis + DB update ───────────────────────────────────

async def _run_groq_analysis(submission_id: str, payload: dict, sync_log_id: str):
    """Fire-and-forget: analyze one submission with Groq and persist results."""
    from app.core.database import AsyncSessionLocal
    from app.services.groq_feedback_analyzer import analyze_feedback

    async with AsyncSessionLocal() as db:
        try:
            # Mark processing
            await db.execute(
                update(FeedbackSubmission)
                .where(FeedbackSubmission.id == submission_id)
                .values(processing_status="processing")
            )
            await db.execute(
                update(GoogleFormSyncLog)
                .where(GoogleFormSyncLog.id == sync_log_id)
                .values(status="processing")
            )
            await db.commit()

            result = await analyze_feedback(
                rating_technical=payload.get("rating_technical_knowledge"),
                rating_communication=payload.get("rating_communication"),
                rating_engagement=payload.get("rating_session_engagement"),
                rating_time=payload.get("rating_time_management"),
                rating_practical=payload.get("rating_practical_learning"),
                rating_content=payload.get("rating_content_quality"),
                free_text_positive=payload.get("free_text_positive"),
                free_text_improve=payload.get("free_text_improve"),
                free_text_overall=payload.get("free_text_overall"),
            )

            sentiment_map = {"Positive": "positive", "Negative": "negative", "Neutral": "neutral"}
            sentiment_label = sentiment_map.get(result["sentiment"], "neutral")

            await db.execute(
                update(FeedbackSubmission)
                .where(FeedbackSubmission.id == submission_id)
                .values(
                    processing_status="completed",
                    groq_trainer_rating=result["trainer_rating"],
                    groq_strengths=result["strengths"],
                    groq_improvements=result["improvements"],
                    groq_summary=result["summary"],
                    groq_recommendation=result["recommendation"],
                    sentiment_label=sentiment_label,
                    sentiment_score=result["sentiment_score"] / 10.0,
                    ai_processed=True,
                    ai_processed_at=datetime.now(timezone.utc),
                )
            )
            await db.execute(
                update(GoogleFormSyncLog)
                .where(GoogleFormSyncLog.id == sync_log_id)
                .values(status="completed", processed_at=datetime.now(timezone.utc))
            )
            await db.commit()
            log.info("webhook.groq_completed", submission_id=submission_id)

        except Exception as exc:
            log.error("webhook.groq_failed", submission_id=submission_id, error=str(exc))
            try:
                sub = await db.get(FeedbackSubmission, submission_id)
                retry_count = (sub.groq_retry_count or 0) + 1
                await db.execute(
                    update(FeedbackSubmission)
                    .where(FeedbackSubmission.id == submission_id)
                    .values(
                        processing_status="failed",
                        groq_retry_count=retry_count,
                    )
                )
                await db.execute(
                    update(GoogleFormSyncLog)
                    .where(GoogleFormSyncLog.id == sync_log_id)
                    .values(
                        status="failed",
                        error_message=str(exc),
                        retry_count=retry_count,
                    )
                )
                await db.commit()
            except Exception:
                pass


# ─── POST /webhook/feedback ───────────────────────────────────────────────────

@router.post("/feedback")
async def receive_google_form_response(
    payload: GoogleFormPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Single webhook endpoint for ALL Google Forms.
    Google Apps Script POSTs here on every form submission.

    Idempotency: google_response_id is globally unique — same response ID
    is safely ignored on repeated calls (Apps Script may retry on failure).
    """
    log.info("webhook.received", batch_id=payload.batch_id, response_id=payload.google_response_id)

    # ── 1. Validate batch ──────────────────────────────────────────────────────
    batch = (await db.execute(
        select(TrainingBatch)
        .where(TrainingBatch.id == payload.batch_id)
    )).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {payload.batch_id} not found")

    # ── 2. Idempotency: check google_response_id ───────────────────────────────
    existing = (await db.execute(
        select(FeedbackSubmission)
        .where(FeedbackSubmission.google_response_id == payload.google_response_id)
    )).scalar_one_or_none()
    if existing:
        log.info("webhook.duplicate_skipped", response_id=payload.google_response_id)
        return {"status": "already_processed", "submission_id": str(existing.id)}

    # ── 3. Check for duplicate respondent email in this batch ──────────────────
    is_duplicate = False
    participant = None
    if payload.respondent_email:
        # Find known participant
        participant = (await db.execute(
            select(Participant).where(
                Participant.email == payload.respondent_email,
                Participant.organization_id == DEFAULT_ORG,
            )
        )).scalar_one_or_none()

        # Check if same email already submitted for this batch
        if participant:
            prior = (await db.execute(
                select(FeedbackSubmission).where(
                    FeedbackSubmission.participant_id == str(participant.id),
                    FeedbackSubmission.batch_id == payload.batch_id,
                    FeedbackSubmission.is_duplicate == False,
                )
            )).scalar_one_or_none()
            if prior:
                is_duplicate = True
                log.warning("webhook.duplicate_email", email=payload.respondent_email, batch=payload.batch_id)
        else:
            # Check by email in free-form respondent_email field
            prior_by_email = (await db.execute(
                select(FeedbackSubmission).where(
                    FeedbackSubmission.respondent_email == payload.respondent_email,
                    FeedbackSubmission.batch_id == payload.batch_id,
                    FeedbackSubmission.is_duplicate == False,
                )
            )).scalar_one_or_none()
            if prior_by_email:
                is_duplicate = True

    # ── 4. Find BatchRoster entry ──────────────────────────────────────────────
    roster = None
    if participant:
        roster = (await db.execute(
            select(BatchRoster).where(
                BatchRoster.batch_id == payload.batch_id,
                BatchRoster.participant_id == str(participant.id),
            )
        )).scalar_one_or_none()

    # ── 5. Create audit log entry first ───────────────────────────────────────
    gform = (await db.execute(
        select(GoogleForm).where(GoogleForm.batch_id == payload.batch_id)
    )).scalar_one_or_none()

    sync_log = GoogleFormSyncLog(
        google_form_id=str(gform.id) if gform else None,
        batch_id=payload.batch_id,
        google_response_id=payload.google_response_id,
        status="received" if not is_duplicate else "duplicate",
        respondent_email=payload.respondent_email,
        raw_payload=payload.model_dump(),
    )
    db.add(sync_log)
    await db.flush()

    # ── 6. Persist FeedbackSubmission ──────────────────────────────────────────
    submission = FeedbackSubmission(
        batch_id=payload.batch_id,
        participant_id=str(participant.id) if participant else None,
        roster_id=str(roster.id) if roster else None,
        rating_technical_knowledge=payload.rating_technical_knowledge,
        rating_communication=payload.rating_communication,
        rating_session_engagement=payload.rating_session_engagement,
        rating_time_management=payload.rating_time_management,
        rating_practical_learning=payload.rating_practical_learning,
        rating_content_quality=payload.rating_content_quality,
        free_text_positive=payload.free_text_positive,
        free_text_improve=payload.free_text_improve,
        free_text_overall=payload.free_text_overall,
        is_anonymous=not bool(payload.respondent_email),
        respondent_email=payload.respondent_email,
        respondent_name=payload.respondent_name,
        source="google_forms",
        google_response_id=payload.google_response_id,
        is_duplicate=is_duplicate,
        processing_status="pending" if not is_duplicate else "skipped",
    )
    db.add(submission)
    await db.flush()

    # Link sync log to submission
    sync_log.submission_id = str(submission.id)

    # Update google_form stats
    if gform:
        gform.total_responses = (gform.total_responses or 0) + 1
        gform.last_synced_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(submission)

    # ── 7. Trigger Groq analysis in background (skip duplicates) ───────────────
    if not is_duplicate:
        background_tasks.add_task(
            _run_groq_analysis,
            str(submission.id),
            payload.model_dump(),
            str(sync_log.id),
        )

    log.info("webhook.accepted", submission_id=str(submission.id), is_duplicate=is_duplicate)
    return {
        "status": "accepted" if not is_duplicate else "duplicate_flagged",
        "submission_id": str(submission.id),
        "groq_analysis": "queued" if not is_duplicate else "skipped",
    }


# ─── GET /webhook/status/{batch_id} ──────────────────────────────────────────

@router.get("/status/{batch_id}")
async def get_webhook_status(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Returns sync log entries for a batch — for monitoring."""
    logs = (await db.execute(
        select(GoogleFormSyncLog)
        .where(GoogleFormSyncLog.batch_id == batch_id)
        .order_by(GoogleFormSyncLog.received_at.desc())
        .limit(50)
    )).scalars().all()

    return [
        {
            "id": str(l.id),
            "google_response_id": l.google_response_id,
            "status": l.status,
            "respondent_email": l.respondent_email,
            "received_at": l.received_at.isoformat() if l.received_at else None,
            "processed_at": l.processed_at.isoformat() if l.processed_at else None,
            "retry_count": l.retry_count,
            "error_message": l.error_message,
        }
        for l in logs
    ]
