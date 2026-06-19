from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, timezone, timedelta
import uuid, json

from app.core.database import get_db
from app.core.redis_client import cache_get, cache_set
from app.models.db_models import (
    Trainer, TrainingBatch, FeedbackSubmission, TrainerMetricsSnapshot,
    Participant, TrainingProgram, PipelineRunLog
)
from app.schemas.pydantic_schemas import (
    TrainerAnalyticsResponse, OrgDashboardResponse,
    ChatAnalyticsRequest, ChatAnalyticsResponse,
    RatingBreakdown, SentimentDistribution,
    PipelineTriggerRequest, PipelineRunOut,
    ProgramAnalyticsResponse, ProgramBatchSummary,
    TrainerHistoryResponse, TrainerHistoryPoint,
)
from app.api.v1.auth import require_admin_or_management, require_admin
from app.models.db_models import User

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/trainer/{trainer_id}", response_model=TrainerAnalyticsResponse)
async def get_trainer_analytics(
    trainer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    cache_key = f"analytics:trainer:{trainer_id}"
    cached = await cache_get(cache_key)
    if cached:
        return TrainerAnalyticsResponse.model_validate_json(cached)

    trainer = (await db.execute(
        select(Trainer).where(
            Trainer.id == trainer_id,
            Trainer.organization_id == current_user.organization_id,
        )
    )).scalar_one_or_none()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    # Aggregate ratings from all feedback submissions for this trainer's batches
    ratings_result = (await db.execute(
        select(
            func.avg(FeedbackSubmission.rating_technical_knowledge).label("avg_technical"),
            func.avg(FeedbackSubmission.rating_communication).label("avg_comm"),
            func.avg(FeedbackSubmission.rating_session_engagement).label("avg_engagement"),
            func.avg(FeedbackSubmission.rating_time_management).label("avg_time"),
            func.avg(FeedbackSubmission.rating_practical_learning).label("avg_practical"),
            func.avg(FeedbackSubmission.rating_content_quality).label("avg_content"),
            func.count(FeedbackSubmission.id).label("total"),
        )
        .join(TrainingBatch, TrainingBatch.id == FeedbackSubmission.batch_id)
        .where(TrainingBatch.trainer_id == trainer_id)
    )).one()

    def safe_float(v, default=0.0):
        return round(float(v), 2) if v is not None else default

    avg_technical = safe_float(ratings_result.avg_technical)
    avg_comm = safe_float(ratings_result.avg_comm)
    avg_engagement = safe_float(ratings_result.avg_engagement)
    avg_time = safe_float(ratings_result.avg_time)
    avg_practical = safe_float(ratings_result.avg_practical)
    avg_content = safe_float(ratings_result.avg_content)
    overall = round((avg_technical + avg_comm + avg_engagement + avg_time + avg_practical + avg_content) / 6, 2)
    total_responses = ratings_result.total or 0

    # Sentiment distribution
    sentiment_result = (await db.execute(
        select(
            FeedbackSubmission.sentiment_label,
            func.count(FeedbackSubmission.id).label("cnt"),
        )
        .join(TrainingBatch, TrainingBatch.id == FeedbackSubmission.batch_id)
        .where(
            TrainingBatch.trainer_id == trainer_id,
            FeedbackSubmission.sentiment_label.isnot(None),
        )
        .group_by(FeedbackSubmission.sentiment_label)
    )).all()

    total_with_sentiment = sum(r.cnt for r in sentiment_result) or 1
    sentiment_map = {r.sentiment_label: r.cnt for r in sentiment_result}
    sentiment = SentimentDistribution(
        positive=round(sentiment_map.get("positive", 0) / total_with_sentiment * 100, 1),
        negative=round(sentiment_map.get("negative", 0) / total_with_sentiment * 100, 1),
        neutral=round(sentiment_map.get("neutral", 0) / total_with_sentiment * 100, 1),
    )

    # Recent snapshots
    snapshots = (await db.execute(
        select(TrainerMetricsSnapshot)
        .where(TrainerMetricsSnapshot.trainer_id == trainer_id)
        .order_by(desc(TrainerMetricsSnapshot.snapshot_date))
        .limit(10)
    )).scalars().all()

    # Latest themes & recommendations
    latest_snapshot = snapshots[0] if snapshots else None
    top_themes = latest_snapshot.top_themes if latest_snapshot else []
    recommendations = latest_snapshot.recommendations if latest_snapshot else []
    if isinstance(recommendations, str):
        recommendations = json.loads(recommendations)

    health_score = safe_float(trainer.overall_health_score)
    risk_flag = health_score < 3.0

    response = TrainerAnalyticsResponse(
        trainer_id=trainer_id,
        trainer_name=trainer.full_name,
        overall_health_score=health_score,
        avg_rating=safe_float(trainer.avg_rating),
        total_sessions=trainer.total_sessions,
        total_responses=total_responses,
        ratings=RatingBreakdown(
            technical_knowledge=avg_technical,
            communication=avg_comm,
            session_engagement=avg_engagement,
            time_management=avg_time,
            practical_learning=avg_practical,
            content_quality=avg_content,
            overall=overall,
        ),
        sentiment=sentiment,
        top_themes=top_themes,
        recommendations=recommendations,
        recent_snapshots=[
            {
                "batch_id": str(s.batch_id),
                "date": s.snapshot_date.isoformat() if s.snapshot_date else None,
                "overall_avg": safe_float(s.overall_avg),
                "health_score": safe_float(s.health_score),
                "response_count": s.response_count,
            }
            for s in snapshots
        ],
        risk_flag=risk_flag,
        risk_reason="Health score below 3.0 threshold" if risk_flag else None,
    )

    await cache_set(cache_key, response.model_dump_json(), ttl=300)
    return response


@router.get("/dashboard", response_model=OrgDashboardResponse)
async def get_org_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    org_id = current_user.organization_id
    cache_key = f"analytics:dashboard:{org_id}"
    cached = await cache_get(cache_key)
    if cached:
        return OrgDashboardResponse.model_validate_json(cached)

    total_trainers = (await db.execute(
        select(func.count(Trainer.id)).where(Trainer.organization_id == org_id, Trainer.is_active == True)
    )).scalar()

    total_batches = (await db.execute(
        select(func.count(TrainingBatch.id)).where(TrainingBatch.organization_id == org_id)
    )).scalar()

    total_participants = (await db.execute(
        select(func.count(Participant.id)).where(Participant.organization_id == org_id)
    )).scalar()

    total_feedback = (await db.execute(
        select(func.count(FeedbackSubmission.id))
        .join(TrainingBatch, TrainingBatch.id == FeedbackSubmission.batch_id)
        .where(TrainingBatch.organization_id == org_id)
    )).scalar()

    avg_health = (await db.execute(
        select(func.avg(Trainer.overall_health_score)).where(
            Trainer.organization_id == org_id, Trainer.is_active == True
        )
    )).scalar()

    # Top trainers
    top_trainers_rows = (await db.execute(
        select(Trainer)
        .where(Trainer.organization_id == org_id, Trainer.is_active == True, Trainer.total_sessions > 0)
        .order_by(desc(Trainer.overall_health_score))
        .limit(5)
    )).scalars().all()

    # At-risk trainers (health score < 3.0)
    at_risk_rows = (await db.execute(
        select(Trainer)
        .where(
            Trainer.organization_id == org_id,
            Trainer.is_active == True,
            Trainer.overall_health_score < 3.0,
            Trainer.total_sessions > 0,
        )
        .order_by(Trainer.overall_health_score)
        .limit(5)
    )).scalars().all()

    # Recent batches
    recent_batches_rows = (await db.execute(
        select(TrainingBatch)
        .options(selectinload(TrainingBatch.trainer), selectinload(TrainingBatch.program))
        .where(TrainingBatch.organization_id == org_id)
        .order_by(desc(TrainingBatch.created_at))
        .limit(5)
    )).scalars().all()

    # Monthly trend (last 6 months avg health score)
    monthly_trend = []
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        month_start = (now.replace(day=1) - timedelta(days=i * 30)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        month_end = month_start + timedelta(days=31)
        avg = (await db.execute(
            select(func.avg(TrainerMetricsSnapshot.health_score))
            .where(
                TrainerMetricsSnapshot.snapshot_date >= month_start,
                TrainerMetricsSnapshot.snapshot_date < month_end,
            )
        )).scalar()
        monthly_trend.append({
            "month": month_start.strftime("%b %Y"),
            "avg_health_score": round(float(avg), 2) if avg else 0.0,
        })

    response = OrgDashboardResponse(
        total_trainers=total_trainers or 0,
        total_batches=total_batches or 0,
        total_participants=total_participants or 0,
        total_feedback_responses=total_feedback or 0,
        avg_org_health_score=round(float(avg_health), 2) if avg_health else 0.0,
        top_trainers=[
            {"id": str(t.id), "name": t.full_name, "health_score": float(t.overall_health_score), "sessions": t.total_sessions}
            for t in top_trainers_rows
        ],
        at_risk_trainers=[
            {"id": str(t.id), "name": t.full_name, "health_score": float(t.overall_health_score), "sessions": t.total_sessions}
            for t in at_risk_rows
        ],
        recent_batches=[
            {
                "id": str(b.id),
                "title": b.title or (b.program.title if b.program else ""),
                "trainer": b.trainer.full_name if b.trainer else "",
                "status": b.status,
                "enrolled": b.actual_enrolled,
                "start": b.start_datetime.isoformat(),
            }
            for b in recent_batches_rows
        ],
        department_benchmarks=[],
        monthly_trend=monthly_trend,
    )

    await cache_set(cache_key, response.model_dump_json(), ttl=120)
    return response


@router.post("/chat", response_model=ChatAnalyticsResponse)
async def chat_analytics(
    payload: ChatAnalyticsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    from app.agents.conversational_rag import ConversationalRAGAgent
    agent = ConversationalRAGAgent()
    answer, sources, confidence = await agent.query(
        question=payload.question,
        trainer_id=str(payload.trainer_id) if payload.trainer_id else None,
        batch_id=str(payload.batch_id) if payload.batch_id else None,
        time_range_days=payload.time_range_days,
        db=db,
        org_id=str(current_user.organization_id),
    )
    return ChatAnalyticsResponse(
        question=payload.question,
        answer=answer,
        sources=sources,
        confidence=confidence,
    )


@router.post("/pipeline/trigger", response_model=PipelineRunOut)
async def trigger_pipeline(
    payload: PipelineTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    batch = (await db.execute(
        select(TrainingBatch).where(
            TrainingBatch.id == payload.batch_id,
            TrainingBatch.organization_id == current_user.organization_id,
        )
    )).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    run_log = PipelineRunLog(
        batch_id=payload.batch_id,
        run_status="pending",
        triggered_by=f"manual:{current_user.id}",
    )
    db.add(run_log)
    await db.commit()
    await db.refresh(run_log)

    from app.agents.orchestrator import AgentOrchestrator
    orchestrator = AgentOrchestrator()
    background_tasks.add_task(orchestrator.run_pipeline, str(payload.batch_id), force=payload.force)

    return run_log


@router.get("/pipeline/runs/{batch_id}", response_model=list[PipelineRunOut])
async def get_pipeline_runs(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    runs = (await db.execute(
        select(PipelineRunLog)
        .where(PipelineRunLog.batch_id == batch_id)
        .order_by(desc(PipelineRunLog.created_at))
        .limit(10)
    )).scalars().all()
    return runs


# ─── Program Analytics ────────────────────────────────────────────────────────

@router.get("/program/{program_id}", response_model=ProgramAnalyticsResponse)
async def get_program_analytics(
    program_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    cache_key = f"analytics:program:{program_id}"
    cached = await cache_get(cache_key)
    if cached:
        return ProgramAnalyticsResponse.model_validate_json(cached)

    program = (await db.execute(
        select(TrainingProgram).where(
            TrainingProgram.id == program_id,
            TrainingProgram.organization_id == current_user.organization_id,
        )
    )).scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Program not found")

    batches = (await db.execute(
        select(TrainingBatch)
        .options(selectinload(TrainingBatch.trainer))
        .where(
            TrainingBatch.program_id == program_id,
            TrainingBatch.organization_id == current_user.organization_id,
        )
        .order_by(desc(TrainingBatch.start_datetime))
    )).scalars().all()

    def safe_float(v, default=0.0):
        return round(float(v), 2) if v is not None else default

    batch_summaries = []
    total_participants = 0
    total_responses = 0
    all_ratings = []
    all_health_scores = []
    positive_sum = neutral_sum = negative_sum = 0
    sentiment_count = 0
    all_themes: list = []
    monthly_data: dict = {}

    for batch in batches:
        batch_id = str(batch.id)

        # Enrolled count
        enrolled = batch.actual_enrolled

        # Aggregate ratings for this batch
        agg = (await db.execute(
            select(
                func.avg(FeedbackSubmission.rating_technical_knowledge).label("avg_technical"),
                func.avg(FeedbackSubmission.rating_communication).label("avg_comm"),
                func.avg(FeedbackSubmission.rating_session_engagement).label("avg_engagement"),
                func.avg(FeedbackSubmission.rating_time_management).label("avg_time"),
                func.avg(FeedbackSubmission.rating_practical_learning).label("avg_practical"),
                func.avg(FeedbackSubmission.rating_content_quality).label("avg_content"),
                func.count(FeedbackSubmission.id).label("cnt"),
            ).where(FeedbackSubmission.batch_id == batch_id)
        )).one()
        r_count = agg.cnt or 0
        avg_fields = [agg.avg_technical, agg.avg_comm, agg.avg_engagement,
                      agg.avg_time, agg.avg_practical, agg.avg_content]
        batch_avg = round(sum(safe_float(f) for f in avg_fields) / 6, 2) if r_count else 0.0

        # Sentiment for batch
        sent = (await db.execute(
            select(
                FeedbackSubmission.sentiment_label,
                func.count(FeedbackSubmission.id).label("cnt"),
            )
            .where(FeedbackSubmission.batch_id == batch_id, FeedbackSubmission.sentiment_label.isnot(None))
            .group_by(FeedbackSubmission.sentiment_label)
        )).all()
        sent_map = {r.sentiment_label: r.cnt for r in sent}
        sent_total = sum(sent_map.values()) or 1
        batch_pos = round(sent_map.get("positive", 0) / sent_total * 100, 1)

        # Latest snapshot for health score
        snap = (await db.execute(
            select(TrainerMetricsSnapshot)
            .where(TrainerMetricsSnapshot.batch_id == batch_id)
            .order_by(desc(TrainerMetricsSnapshot.created_at))
            .limit(1)
        )).scalars().first()
        health = safe_float(snap.health_score) if snap else 0.0
        themes = snap.top_themes if snap else []
        all_themes.extend(themes)

        total_participants += enrolled
        total_responses += r_count
        if batch_avg > 0:
            all_ratings.append(batch_avg)
        if health > 0:
            all_health_scores.append(health)
        positive_sum += sent_map.get("positive", 0)
        neutral_sum += sent_map.get("neutral", 0)
        negative_sum += sent_map.get("negative", 0)
        sentiment_count += sum(sent_map.values())

        # Monthly trend bucket
        month_key = batch.start_datetime.strftime("%b %Y")
        if month_key not in monthly_data:
            monthly_data[month_key] = {"ratings": [], "health": []}
        if batch_avg > 0:
            monthly_data[month_key]["ratings"].append(batch_avg)
        if health > 0:
            monthly_data[month_key]["health"].append(health)

        batch_summaries.append(ProgramBatchSummary(
            batch_id=batch_id,
            batch_code=batch.batch_code,
            title=batch.title,
            trainer_name=batch.trainer.full_name if batch.trainer else "—",
            start_datetime=batch.start_datetime,
            end_datetime=batch.end_datetime,
            status=batch.status,
            enrolled=enrolled,
            responses=r_count,
            avg_rating=batch_avg,
            health_score=health,
            sentiment_positive=batch_pos,
        ))

    # Overall aggregates
    total_sent = total_participants if total_participants else 1
    completion_rate = round(total_responses / total_sent * 100, 1) if total_participants else 0.0
    avg_rating = round(sum(all_ratings) / len(all_ratings), 2) if all_ratings else 0.0
    avg_health = round(sum(all_health_scores) / len(all_health_scores), 2) if all_health_scores else 0.0

    st = sentiment_count or 1
    positive_pct = round(positive_sum / st * 100, 1)
    negative_pct = round(negative_sum / st * 100, 1)
    neutral_pct = round(neutral_sum / st * 100, 1)

    # NPS: % promoters (5-star) minus % detractors (1-2 star) from raw feedback
    nps_result = (await db.execute(
        select(
            FeedbackSubmission.rating_technical_knowledge,
            FeedbackSubmission.rating_communication,
            FeedbackSubmission.rating_session_engagement,
            FeedbackSubmission.rating_time_management,
            FeedbackSubmission.rating_practical_learning,
            FeedbackSubmission.rating_content_quality,
        )
        .join(TrainingBatch, TrainingBatch.id == FeedbackSubmission.batch_id)
        .where(TrainingBatch.program_id == program_id)
    )).all()
    if nps_result:
        promoters = detractors = 0
        for row in nps_result:
            avg_r = sum(v for v in row if v) / 6 if any(row) else 0
            if avg_r >= 4.5:
                promoters += 1
            elif avg_r <= 2.5:
                detractors += 1
        nps = round((promoters - detractors) / len(nps_result) * 100, 1)
    else:
        nps = 0.0

    # Dedupe themes
    seen_themes: set = set()
    unique_themes = []
    for t in all_themes:
        key = str(t).lower()[:40]
        if key not in seen_themes:
            seen_themes.add(key)
            unique_themes.append(t)

    monthly_trend = [
        {
            "month": k,
            "avg_rating": round(sum(v["ratings"]) / len(v["ratings"]), 2) if v["ratings"] else 0.0,
            "avg_health": round(sum(v["health"]) / len(v["health"]), 2) if v["health"] else 0.0,
        }
        for k, v in monthly_data.items()
    ]

    response = ProgramAnalyticsResponse(
        program_id=program_id,
        program_title=program.title,
        description=program.description,
        total_batches=len(batches),
        total_participants=total_participants,
        total_responses=total_responses,
        completion_rate=completion_rate,
        avg_rating=avg_rating,
        avg_health_score=avg_health,
        nps=nps,
        sentiment_positive=positive_pct,
        sentiment_negative=negative_pct,
        sentiment_neutral=neutral_pct,
        top_themes=unique_themes[:10],
        batches=batch_summaries,
        monthly_trend=monthly_trend,
    )
    await cache_set(cache_key, response.model_dump_json(), ttl=300)
    return response


# ─── Trainer History ──────────────────────────────────────────────────────────

@router.get("/trainer/{trainer_id}/history", response_model=TrainerHistoryResponse)
async def get_trainer_history(
    trainer_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    trainer = (await db.execute(
        select(Trainer).where(
            Trainer.id == trainer_id,
            Trainer.organization_id == current_user.organization_id,
        )
    )).scalar_one_or_none()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    def safe_float(v, default=0.0):
        return round(float(v), 2) if v is not None else default

    snapshots = (await db.execute(
        select(TrainerMetricsSnapshot)
        .options(selectinload(TrainerMetricsSnapshot.trainer))
        .where(TrainerMetricsSnapshot.trainer_id == trainer_id)
        .order_by(TrainerMetricsSnapshot.snapshot_date)
    )).scalars().all()

    history = []
    health_scores = []
    monthly_data: dict = {}

    for snap in snapshots:
        batch = (await db.execute(
            select(TrainingBatch)
            .options(selectinload(TrainingBatch.program))
            .where(TrainingBatch.id == snap.batch_id)
        )).scalar_one_or_none()

        hs = safe_float(snap.health_score)
        health_scores.append(hs)
        month_key = snap.snapshot_date.strftime("%b %Y") if snap.snapshot_date else "Unknown"
        monthly_data.setdefault(month_key, []).append(hs)

        history.append(TrainerHistoryPoint(
            batch_id=str(snap.batch_id),
            batch_code=batch.batch_code if batch else "—",
            program_title=batch.program.title if batch and batch.program else "—",
            snapshot_date=snap.snapshot_date,
            health_score=hs,
            overall_avg=safe_float(snap.overall_avg),
            response_count=snap.response_count or 0,
            sentiment_positive=safe_float(snap.sentiment_positive),
            top_themes=snap.top_themes or [],
        ))

    # Consistency: low std dev = high consistency
    if len(health_scores) >= 2:
        mean = sum(health_scores) / len(health_scores)
        variance = sum((x - mean) ** 2 for x in health_scores) / len(health_scores)
        std_dev = variance ** 0.5
        consistency = round(max(0.0, 5.0 - std_dev * 2), 2)
    elif health_scores:
        consistency = health_scores[0]
    else:
        consistency = 0.0

    # Growth: slope of health score over time
    if len(health_scores) >= 2:
        growth = round((health_scores[-1] - health_scores[0]) / len(health_scores), 2)
    else:
        growth = 0.0

    best = max(snapshots, key=lambda s: safe_float(s.health_score)) if snapshots else None
    worst = min(snapshots, key=lambda s: safe_float(s.health_score)) if snapshots else None

    best_batch = (await db.execute(
        select(TrainingBatch).where(TrainingBatch.id == best.batch_id)
    )).scalar_one_or_none() if best else None

    monthly_trend = [
        {"month": k, "avg_health": round(sum(v) / len(v), 2)}
        for k, v in monthly_data.items()
    ]

    return TrainerHistoryResponse(
        trainer_id=trainer_id,
        trainer_name=trainer.full_name,
        total_batches=len(snapshots),
        history=history,
        monthly_trend=monthly_trend,
        consistency_score=consistency,
        growth_score=growth,
        best_batch_id=str(best.batch_id) if best else None,
        best_batch_title=best_batch.title or best_batch.batch_code if best_batch else None,
        best_health_score=safe_float(best.health_score) if best else 0.0,
        worst_health_score=safe_float(worst.health_score) if worst else 0.0,
    )
