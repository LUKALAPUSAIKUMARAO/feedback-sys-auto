"""Multi-Agent Orchestrator: coordinates all 7 agents sequentially."""
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.agents.collector_validator import FeedbackCollectorValidator
from app.agents.sentiment_analyzer import SentimentAnalyzerAgent
from app.agents.theme_extractor import ThemeExtractorAgent
from app.agents.scoring_agent import ScoringAgent
from app.agents.recommendation_agent import RecommendationAgent
from app.agents.executive_summary import ExecutiveSummaryAgent
from app.models.db_models import (
    FeedbackSubmission, TrainingBatch, Trainer, TrainerMetricsSnapshot,
    PipelineRunLog, FeedbackEmbedding
)
from app.core.database import AsyncSessionLocal
import structlog

log = structlog.get_logger()


class AgentOrchestrator:

    def __init__(self):
        self.validator = FeedbackCollectorValidator()
        self.sentiment = SentimentAnalyzerAgent()
        self.theme = ThemeExtractorAgent()
        self.scorer = ScoringAgent()
        self.recommender = RecommendationAgent()
        self.exec_summary = ExecutiveSummaryAgent()

    async def run_pipeline(self, batch_id: str, force: bool = False) -> dict:
        start_time = datetime.now(timezone.utc)
        log.info("orchestrator.pipeline_start", batch_id=batch_id)

        async with AsyncSessionLocal() as db:
            # Find or create pipeline run log
            run_log = (await db.execute(
                select(PipelineRunLog)
                .where(PipelineRunLog.batch_id == batch_id, PipelineRunLog.run_status == "pending")
                .order_by(PipelineRunLog.created_at.desc())
                .limit(1)
            )).scalars().first()

            if not run_log:
                run_log = PipelineRunLog(batch_id=batch_id, run_status="pending", triggered_by="celery")
                db.add(run_log)
                await db.commit()
                await db.refresh(run_log)

            await db.execute(
                update(PipelineRunLog)
                .where(PipelineRunLog.id == run_log.id)
                .values(run_status="running", started_at=start_time)
            )
            await db.commit()

            try:
                result = await self._execute_pipeline(db, batch_id, run_log.id, force)

                elapsed = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                await db.execute(
                    update(PipelineRunLog)
                    .where(PipelineRunLog.id == run_log.id)
                    .values(
                        run_status="completed",
                        completed_at=datetime.now(timezone.utc),
                        duration_ms=elapsed,
                        agents_run=result.get("agents_run", []),
                        submission_count=result.get("submission_count", 0),
                        raw_output_payload=result,
                    )
                )
                await db.commit()
                log.info("orchestrator.pipeline_complete", batch_id=batch_id, duration_ms=elapsed)
                return result

            except Exception as e:
                log.error("orchestrator.pipeline_failed", batch_id=batch_id, error=str(e))
                await db.execute(
                    update(PipelineRunLog)
                    .where(PipelineRunLog.id == run_log.id)
                    .values(run_status="failed", error_details=str(e), completed_at=datetime.now(timezone.utc))
                )
                await db.commit()
                raise

    async def _execute_pipeline(self, db: AsyncSession, batch_id: str, run_log_id: str, force: bool) -> dict:
        # ── Fetch batch and trainer ──────────────────────────────────────────
        batch = (await db.execute(
            select(TrainingBatch)
            .options(selectinload(TrainingBatch.trainer), selectinload(TrainingBatch.program))
            .where(TrainingBatch.id == batch_id)
        )).scalar_one_or_none()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")

        trainer = batch.trainer

        # ── Fetch all unprocessed submissions ─────────────────────────────────
        submissions_q = select(FeedbackSubmission).where(FeedbackSubmission.batch_id == batch_id)
        if not force:
            submissions_q = submissions_q.where(FeedbackSubmission.ai_processed == False)
        submissions = (await db.execute(submissions_q)).scalars().all()

        if not submissions:
            log.info("orchestrator.no_submissions", batch_id=batch_id)
            return {"agents_run": [], "submission_count": 0, "message": "No submissions to process"}

        raw_records = [
            {
                "id": str(s.id),
                "participant_id": str(s.participant_id),
                "rating_technical_knowledge": s.rating_technical_knowledge,
                "rating_communication": s.rating_communication,
                "rating_session_engagement": s.rating_session_engagement,
                "rating_time_management": s.rating_time_management,
                "rating_practical_learning": s.rating_practical_learning,
                "rating_content_quality": s.rating_content_quality,
                "free_text_positive": s.free_text_positive,
                "free_text_improve": s.free_text_improve,
                "free_text_overall": s.free_text_overall,
                "is_anonymous": s.is_anonymous,
            }
            for s in submissions
        ]

        agents_run = []

        # ── Agent 1: Validate ─────────────────────────────────────────────────
        log.info("orchestrator.agent1_start")
        validation_result = await self.validator.run(raw_records)
        valid_records = validation_result.get("valid_records", raw_records)
        agents_run.append("FeedbackCollectorValidator")

        # ── Agent 2: Sentiment ────────────────────────────────────────────────
        log.info("orchestrator.agent2_start")
        sentiment_result = await self.sentiment.run(valid_records)
        agents_run.append("SentimentAnalyzer")

        # ── Agent 3: Themes ───────────────────────────────────────────────────
        log.info("orchestrator.agent3_start")
        theme_result = await self.theme.run(valid_records)
        agents_run.append("ThemeExtractor")

        # ── Agent 4: Scoring ──────────────────────────────────────────────────
        log.info("orchestrator.agent4_start")
        historical_avg = float(trainer.avg_rating) if trainer.avg_rating else 0.0
        scoring_result = await self.scorer.run(valid_records, sentiment_result, theme_result, historical_avg)
        agents_run.append("ScoringAgent")

        # ── Agent 5: Recommendations ──────────────────────────────────────────
        log.info("orchestrator.agent5_start")
        recommendation_result = await self.recommender.run(
            scoring_result, theme_result, sentiment_result,
            trainer_name=trainer.full_name if trainer else "Trainer"
        )
        agents_run.append("RecommendationAgent")

        # ── Agent 6: Executive Summary ────────────────────────────────────────
        log.info("orchestrator.agent6_start")
        batch_title = batch.title or (batch.program.title if batch.program else f"Batch {batch_id[:8]}")
        exec_result = await self.exec_summary.run(
            scoring_result=scoring_result,
            theme_result=theme_result,
            recommendation_result=recommendation_result,
            sentiment_result=sentiment_result,
            trainer_name=trainer.full_name if trainer else "Trainer",
            batch_title=batch_title,
            response_count=len(valid_records),
            total_enrolled=batch.actual_enrolled or len(valid_records),
        )
        agents_run.append("ExecutiveSummaryAgent")

        # ── Persist results back to DB ────────────────────────────────────────
        await self._persist_results(
            db=db,
            batch=batch,
            trainer=trainer,
            submissions=submissions,
            sentiment_result=sentiment_result,
            scoring_result=scoring_result,
            theme_result=theme_result,
            recommendation_result=recommendation_result,
            exec_result=exec_result,
        )
        agents_run.append("DataPersistence")

        return {
            "agents_run": agents_run,
            "submission_count": len(valid_records),
            "health_score": scoring_result.get("trainer_health_score"),
            "benchmark_tier": scoring_result.get("benchmark_tier"),
            "executive_summary": exec_result.get("executive_summary"),
            "recommendation_count": len(recommendation_result.get("recommendations", [])),
        }

    async def _persist_results(
        self, db, batch, trainer, submissions,
        sentiment_result, scoring_result, theme_result,
        recommendation_result, exec_result
    ):
        now = datetime.now(timezone.utc)
        batch_id = str(batch.id)

        # Map sentiment back to individual submissions
        sentiment_map = {
            r.get("submission_id"): r
            for r in sentiment_result.get("analyzed_records", [])
        }

        for sub in submissions:
            sid = str(sub.id)
            if sid in sentiment_map:
                s_data = sentiment_map[sid]
                sub.sentiment_score = s_data.get("sentiment_score")
                sub.sentiment_label = s_data.get("sentiment_label")
                sub.extracted_themes = [t.get("theme_name") for t in theme_result.get("themes", [])][:5]
            sub.ai_processed = True
            sub.ai_processed_at = now

        # Upsert trainer metrics snapshot
        existing_snapshot = (await db.execute(
            select(TrainerMetricsSnapshot).where(
                TrainerMetricsSnapshot.trainer_id == trainer.id,
                TrainerMetricsSnapshot.batch_id == batch.id,
            )
        )).scalar_one_or_none()

        dim_scores = scoring_result.get("weighted_dimension_scores", {})
        health_score = float(scoring_result.get("trainer_health_score", 0))
        overall_avg = float(scoring_result.get("trainer_health_score", 0))
        sentiment_summary = sentiment_result.get("batch_sentiment_summary", {})
        top_themes = [t.get("theme_name", "") for t in theme_result.get("themes", [])[:5]]
        recs = recommendation_result.get("recommendations", [])
        exec_summary_text = exec_result.get("executive_summary", "")

        snapshot_data = dict(
            avg_technical=dim_scores.get("rating_technical_knowledge", dim_scores.get("technical_knowledge")),
            avg_communication=dim_scores.get("rating_communication", dim_scores.get("communication")),
            avg_engagement=dim_scores.get("rating_session_engagement", dim_scores.get("session_engagement")),
            avg_time_mgmt=dim_scores.get("rating_time_management", dim_scores.get("time_management")),
            avg_practical=dim_scores.get("rating_practical_learning", dim_scores.get("practical_learning")),
            avg_content=dim_scores.get("rating_content_quality", dim_scores.get("content_quality")),
            overall_avg=overall_avg,
            health_score=health_score,
            sentiment_positive=sentiment_summary.get("overall_positive_pct", 0),
            sentiment_negative=sentiment_summary.get("overall_negative_pct", 0),
            sentiment_neutral=sentiment_summary.get("overall_neutral_pct", 100),
            response_count=len(submissions),
            top_themes=top_themes,
            recommendations=recs,
            executive_summary=exec_summary_text,
        )

        if existing_snapshot:
            for k, v in snapshot_data.items():
                setattr(existing_snapshot, k, v)
        else:
            snapshot = TrainerMetricsSnapshot(
                trainer_id=trainer.id,
                batch_id=batch.id,
                **snapshot_data,
            )
            db.add(snapshot)

        # Update trainer overall scores
        all_snapshots = (await db.execute(
            select(TrainerMetricsSnapshot).where(TrainerMetricsSnapshot.trainer_id == trainer.id)
        )).scalars().all()
        all_scores = [float(s.health_score) for s in all_snapshots if s.health_score]
        # Include the current one
        all_scores.append(health_score)
        new_avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else health_score
        total_sessions = len(all_scores)

        await db.execute(
            update(Trainer)
            .where(Trainer.id == trainer.id)
            .values(
                overall_health_score=health_score,
                avg_rating=new_avg,
                total_sessions=total_sessions,
            )
        )

        # Update batch status to processed
        await db.execute(
            update(TrainingBatch)
            .where(TrainingBatch.id == batch.id)
            .values(status="processed")
        )

        await db.commit()
        log.info("orchestrator.results_persisted", batch_id=batch_id, health_score=health_score)
