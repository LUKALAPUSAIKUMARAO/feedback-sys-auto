import asyncio
from datetime import datetime, timezone, timedelta
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.tasks.celery_app import celery_app
from app.core.database import AsyncSessionLocal
from app.models.db_models import TrainingBatch, BatchRoster, SurveyToken

logger = get_task_logger(__name__)


def run_async(coro):
    """Run an async coroutine from a synchronous Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="app.tasks.celery_tasks.run_agent_pipeline", max_retries=3)
def run_agent_pipeline(self, batch_id: str, force: bool = False):
    """Trigger the 7-agent analysis pipeline for a completed batch."""
    logger.info(f"Starting agent pipeline for batch {batch_id}")
    try:
        from app.agents.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        result = run_async(orchestrator.run_pipeline(batch_id, force=force))
        logger.info(f"Pipeline completed for batch {batch_id}: {result}")
        return result
    except Exception as exc:
        logger.error(f"Pipeline failed for batch {batch_id}: {exc}")
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


@celery_app.task(name="app.tasks.celery_tasks.check_completed_batches")
def check_completed_batches():
    """Cron: detect batches past end_datetime, trigger feedback campaigns."""
    async def _check():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            # Find batches that completed but are still in 'scheduled'/'ongoing' status
            completed_batches = (await db.execute(
                select(TrainingBatch)
                .options(selectinload(TrainingBatch.trainer), selectinload(TrainingBatch.program))
                .where(
                    TrainingBatch.end_datetime <= now,
                    TrainingBatch.status.in_(["scheduled", "ongoing"]),
                )
            )).scalars().all()

            triggered = 0
            for batch in completed_batches:
                logger.info(f"Batch {batch.id} completed, triggering feedback campaign")
                await db.execute(
                    update(TrainingBatch)
                    .where(TrainingBatch.id == batch.id)
                    .values(status="completed")
                )
                # Auto-send feedback links
                send_feedback_campaign.delay(str(batch.id))
                triggered += 1

            await db.commit()
            logger.info(f"check_completed_batches: triggered {triggered} campaigns")
            return {"triggered": triggered}

    return run_async(_check())


@celery_app.task(name="app.tasks.celery_tasks.send_feedback_campaign")
def send_feedback_campaign(batch_id: str):
    """Send personalized feedback links to all participants in a batch."""
    async def _send():
        from app.core.email import send_feedback_email
        from app.core.config import settings

        async with AsyncSessionLocal() as db:
            batch = (await db.execute(
                select(TrainingBatch)
                .options(
                    selectinload(TrainingBatch.trainer),
                    selectinload(TrainingBatch.program),
                )
                .where(TrainingBatch.id == batch_id)
            )).scalar_one_or_none()

            if not batch:
                logger.error(f"Batch {batch_id} not found")
                return

            rosters = (await db.execute(
                select(BatchRoster)
                .options(selectinload(BatchRoster.participant))
                .where(
                    BatchRoster.batch_id == batch_id,
                    BatchRoster.feedback_link_sent == False,
                )
            )).scalars().all()

            sent = 0
            for roster in rosters:
                try:
                    feedback_url = f"{settings.FRONTEND_URL}/feedback/{roster.feedback_token}"
                    batch_title = batch.title or (batch.program.title if batch.program else "Training Session")
                    await send_feedback_email(
                        to_email=roster.participant.email,
                        to_name=roster.participant.full_name,
                        feedback_url=feedback_url,
                        batch_title=batch_title,
                        trainer_name=batch.trainer.full_name if batch.trainer else "Trainer",
                    )
                    roster.feedback_link_sent = True
                    roster.feedback_link_sent_at = datetime.now(timezone.utc)
                    sent += 1
                except Exception as e:
                    logger.warning(f"Failed to send email to {roster.participant.email}: {e}")

            await db.execute(
                update(TrainingBatch)
                .where(TrainingBatch.id == batch_id)
                .values(status="survey_open")
            )
            await db.commit()
            logger.info(f"send_feedback_campaign: sent {sent} links for batch {batch_id}")
            return {"sent": sent}

    return run_async(_send())


@celery_app.task(name="app.tasks.celery_tasks.send_survey_reminders")
def send_survey_reminders():
    """Daily: send reminder to participants who haven't submitted yet."""
    async def _remind():
        from app.core.config import settings
        from app.core.email import send_feedback_email
        from app.models.db_models import FeedbackSubmission

        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            open_batches = (await db.execute(
                select(TrainingBatch)
                .options(selectinload(TrainingBatch.trainer), selectinload(TrainingBatch.program))
                .where(
                    TrainingBatch.status == "survey_open",
                    TrainingBatch.survey_deadline > now,
                )
            )).scalars().all()

            reminded = 0
            for batch in open_batches:
                submitted_participant_ids = {
                    str(r.participant_id)
                    for r in (await db.execute(
                        select(FeedbackSubmission.participant_id)
                        .where(FeedbackSubmission.batch_id == batch.id)
                    )).all()
                }

                pending_rosters = (await db.execute(
                    select(BatchRoster)
                    .options(selectinload(BatchRoster.participant))
                    .where(
                        BatchRoster.batch_id == batch.id,
                        BatchRoster.feedback_link_sent == True,
                    )
                )).scalars().all()

                for roster in pending_rosters:
                    if str(roster.participant_id) not in submitted_participant_ids:
                        try:
                            feedback_url = f"{settings.FRONTEND_URL}/feedback/{roster.feedback_token}"
                            batch_title = batch.title or (batch.program.title if batch.program else "Training Session")
                            await send_feedback_email(
                                to_email=roster.participant.email,
                                to_name=roster.participant.full_name,
                                feedback_url=feedback_url,
                                batch_title=batch_title,
                                trainer_name=batch.trainer.full_name if batch.trainer else "",
                                is_reminder=True,
                            )
                            reminded += 1
                        except Exception:
                            pass

            logger.info(f"send_survey_reminders: sent {reminded} reminders")
            return {"reminded": reminded}

    return run_async(_remind())


@celery_app.task(name="app.tasks.celery_tasks.cleanup_expired_tokens")
def cleanup_expired_tokens():
    """Daily: mark expired tokens and close expired surveys."""
    async def _cleanup():
        async with AsyncSessionLocal() as db:
            now = datetime.now(timezone.utc)
            await db.execute(
                update(SurveyToken)
                .where(SurveyToken.expires_at <= now, SurveyToken.is_used == False)
                .values(is_used=True)
            )
            # Close surveys past deadline
            await db.execute(
                update(TrainingBatch)
                .where(
                    TrainingBatch.survey_deadline <= now,
                    TrainingBatch.status == "survey_open",
                )
                .values(status="survey_closed")
            )
            await db.commit()
            # Trigger pipeline for closed surveys with enough responses
            closed_batches = (await db.execute(
                select(TrainingBatch).where(TrainingBatch.status == "survey_closed")
            )).scalars().all()
            for batch in closed_batches:
                from app.models.db_models import FeedbackSubmission
                from sqlalchemy import func
                count = (await db.execute(
                    select(func.count(FeedbackSubmission.id)).where(FeedbackSubmission.batch_id == batch.id)
                )).scalar()
                if count >= batch.feedback_threshold:
                    run_agent_pipeline.delay(str(batch.id))

    return run_async(_cleanup())
