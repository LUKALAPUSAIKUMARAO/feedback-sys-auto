from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import csv, io, uuid

from app.core.database import get_db
from app.core.config import settings
from app.core.security import create_feedback_token
from app.models.db_models import (
    Trainer, TrainingProgram, TrainingBatch, Participant,
    BatchRoster, User, SurveyToken
)
from app.schemas.pydantic_schemas import (
    TrainerCreate, TrainerUpdate, TrainerOut,
    TrainingProgramCreate, TrainingProgramOut,
    TrainingBatchCreate, TrainingBatchOut, TrainingBatchWithRelations,
    ParticipantCreate, ParticipantOut,
    BulkParticipantUpload, BulkUploadResult,
    PaginatedResponse
)
from app.api.v1.auth import require_admin, require_admin_or_management

router = APIRouter(prefix="/admin", tags=["Admin"])

DEFAULT_ORG = uuid.UUID("00000000-0000-0000-0000-000000000001")


# ─── Trainer CRUD ─────────────────────────────────────────────────────────────

@router.post("/trainers", response_model=TrainerOut, status_code=201)
async def create_trainer(
    payload: TrainerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = await db.execute(
        select(Trainer).where(
            Trainer.employee_id == payload.employee_id,
            Trainer.organization_id == current_user.organization_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Trainer with this employee ID already exists")

    trainer = Trainer(
        organization_id=current_user.organization_id,
        **payload.model_dump(),
    )
    db.add(trainer)
    await db.commit()
    await db.refresh(trainer)
    return trainer


@router.get("/trainers", response_model=PaginatedResponse)
async def list_trainers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    q = select(Trainer).where(Trainer.organization_id == current_user.organization_id)
    if search:
        q = q.where(Trainer.full_name.ilike(f"%{search}%"))
    if is_active is not None:
        q = q.where(Trainer.is_active == is_active)

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar()

    q = q.offset((page - 1) * page_size).limit(page_size).order_by(Trainer.full_name)
    rows = (await db.execute(q)).scalars().all()

    return PaginatedResponse(
        items=[TrainerOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/trainers/{trainer_id}", response_model=TrainerOut)
async def get_trainer(
    trainer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    result = await db.execute(
        select(Trainer).where(
            Trainer.id == trainer_id,
            Trainer.organization_id == current_user.organization_id,
        )
    )
    trainer = result.scalar_one_or_none()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")
    return trainer


@router.patch("/trainers/{trainer_id}", response_model=TrainerOut)
async def update_trainer(
    trainer_id: uuid.UUID,
    payload: TrainerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(
        select(Trainer).where(Trainer.id == trainer_id, Trainer.organization_id == current_user.organization_id)
    )
    trainer = result.scalar_one_or_none()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(trainer, field, value)
    await db.commit()
    await db.refresh(trainer)
    return trainer


# ─── Training Programs ────────────────────────────────────────────────────────

@router.post("/programs", response_model=TrainingProgramOut, status_code=201)
async def create_program(
    payload: TrainingProgramCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    program = TrainingProgram(
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(program)
    await db.commit()
    await db.refresh(program)
    return program


@router.get("/programs", response_model=PaginatedResponse)
async def list_programs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    q = select(TrainingProgram).where(
        TrainingProgram.organization_id == current_user.organization_id,
        TrainingProgram.is_active == True,
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return PaginatedResponse(
        items=[TrainingProgramOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


# ─── Training Batches ─────────────────────────────────────────────────────────

@router.post("/batches", response_model=TrainingBatchOut, status_code=201)
async def create_batch(
    payload: TrainingBatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Validate trainer belongs to org
    trainer = (await db.execute(
        select(Trainer).where(Trainer.id == payload.trainer_id, Trainer.organization_id == current_user.organization_id)
    )).scalar_one_or_none()
    if not trainer:
        raise HTTPException(status_code=404, detail="Trainer not found")

    # Validate program belongs to org
    program = (await db.execute(
        select(TrainingProgram).where(
            TrainingProgram.id == payload.program_id,
            TrainingProgram.organization_id == current_user.organization_id,
        )
    )).scalar_one_or_none()
    if not program:
        raise HTTPException(status_code=404, detail="Training program not found")

    # Check batch code uniqueness
    existing = (await db.execute(
        select(TrainingBatch).where(
            TrainingBatch.batch_code == payload.batch_code,
            TrainingBatch.organization_id == current_user.organization_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Batch code already exists in this organization")

    survey_deadline = payload.end_datetime + timedelta(hours=72)
    batch = TrainingBatch(
        organization_id=current_user.organization_id,
        created_by=current_user.id,
        survey_deadline=survey_deadline,
        **payload.model_dump(),
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return batch


@router.get("/batches", response_model=PaginatedResponse)
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    trainer_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    q = select(TrainingBatch).where(TrainingBatch.organization_id == current_user.organization_id)
    if status:
        q = q.where(TrainingBatch.status == status)
    if trainer_id:
        q = q.where(TrainingBatch.trainer_id == trainer_id)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    rows = (await db.execute(
        q.order_by(TrainingBatch.start_datetime.desc()).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return PaginatedResponse(
        items=[TrainingBatchOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/batches/{batch_id}", response_model=TrainingBatchWithRelations)
async def get_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    result = await db.execute(
        select(TrainingBatch)
        .options(selectinload(TrainingBatch.trainer), selectinload(TrainingBatch.program))
        .where(TrainingBatch.id == batch_id, TrainingBatch.organization_id == current_user.organization_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


# ─── Participants ─────────────────────────────────────────────────────────────

@router.post("/batches/{batch_id}/participants", response_model=BulkUploadResult, status_code=201)
async def upload_participants(
    batch_id: uuid.UUID,
    payload: BulkParticipantUpload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    batch = (await db.execute(
        select(TrainingBatch).where(
            TrainingBatch.id == batch_id,
            TrainingBatch.organization_id == current_user.organization_id,
        )
    )).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    created, updated, errors, enrolled = 0, 0, [], 0
    for p_data in payload.participants:
        try:
            existing_p = (await db.execute(
                select(Participant).where(
                    Participant.employee_id == p_data.employee_id,
                    Participant.organization_id == current_user.organization_id,
                )
            )).scalar_one_or_none()

            if existing_p:
                for k, v in p_data.model_dump(exclude_none=True).items():
                    setattr(existing_p, k, v)
                participant = existing_p
                updated += 1
            else:
                participant = Participant(
                    organization_id=current_user.organization_id,
                    **p_data.model_dump(),
                )
                db.add(participant)
                await db.flush()
                created += 1

            # Enroll in batch (idempotent)
            existing_roster = (await db.execute(
                select(BatchRoster).where(
                    BatchRoster.batch_id == batch_id,
                    BatchRoster.participant_id == participant.id,
                )
            )).scalar_one_or_none()

            if not existing_roster:
                # Generate feedback token
                token = create_feedback_token(str(participant.id), str(batch_id))
                from app.core.security import decode_feedback_token
                token_payload = decode_feedback_token(token)
                jti = token_payload["jti"]
                expires_at = datetime.fromtimestamp(token_payload["exp"], tz=timezone.utc)

                roster = BatchRoster(
                    batch_id=batch_id,
                    participant_id=participant.id,
                    feedback_token=token,
                )
                db.add(roster)

                survey_token = SurveyToken(
                    jti=jti,
                    participant_id=participant.id,
                    batch_id=batch_id,
                    expires_at=expires_at,
                )
                db.add(survey_token)
                enrolled += 1

        except Exception as e:
            errors.append({"employee_id": p_data.employee_id, "error": str(e)})

    # Update batch enrolled count
    await db.execute(
        update(TrainingBatch)
        .where(TrainingBatch.id == batch_id)
        .values(actual_enrolled=TrainingBatch.actual_enrolled + enrolled)
    )
    await db.commit()
    return BulkUploadResult(created=created, updated=updated, errors=errors, enrolled=enrolled)


@router.post("/batches/{batch_id}/participants/csv", response_model=BulkUploadResult, status_code=201)
async def upload_participants_csv(
    batch_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    participants = []
    for row in reader:
        try:
            from app.schemas.pydantic_schemas import ParticipantCSVRow
            p = ParticipantCSVRow(
                full_name=row.get("full_name", "").strip(),
                email=row.get("email", "").strip(),
                employee_id=row.get("employee_id", "").strip(),
                department=row.get("department", "").strip() or None,
                designation=row.get("designation", "").strip() or None,
            )
            participants.append(ParticipantCreate(**p.model_dump()))
        except Exception as e:
            pass  # skip malformed rows

    return await upload_participants(
        batch_id=batch_id,
        payload=BulkParticipantUpload(participants=participants),
        db=db,
        current_user=current_user,
    )


@router.get("/batches/{batch_id}/participants", response_model=PaginatedResponse)
async def list_batch_participants(
    batch_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    q = (
        select(Participant)
        .join(BatchRoster, BatchRoster.participant_id == Participant.id)
        .where(BatchRoster.batch_id == batch_id)
    )
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return PaginatedResponse(
        items=[ParticipantOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


# ─── Send feedback links ──────────────────────────────────────────────────────

@router.post("/batches/{batch_id}/send-feedback-links")
async def send_feedback_links(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    batch = (await db.execute(
        select(TrainingBatch)
        .options(selectinload(TrainingBatch.trainer), selectinload(TrainingBatch.program))
        .where(TrainingBatch.id == batch_id, TrainingBatch.organization_id == current_user.organization_id)
    )).scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    rosters = (await db.execute(
        select(BatchRoster)
        .options(selectinload(BatchRoster.participant))
        .where(BatchRoster.batch_id == batch_id, BatchRoster.feedback_link_sent == False)
    )).scalars().all()

    sent_count = 0
    from app.core.email import send_feedback_email
    for roster in rosters:
        try:
            feedback_url = f"{settings.FRONTEND_URL}/feedback/{roster.feedback_token}"
            await send_feedback_email(
                to_email=roster.participant.email,
                to_name=roster.participant.full_name,
                feedback_url=feedback_url,
                batch_title=batch.title or batch.program.title,
                trainer_name=batch.trainer.full_name,
            )
            roster.feedback_link_sent = True
            roster.feedback_link_sent_at = datetime.now(timezone.utc)
            sent_count += 1
        except Exception:
            pass

    await db.execute(
        update(TrainingBatch).where(TrainingBatch.id == batch_id).values(status="survey_open")
    )
    await db.commit()
    return {"sent": sent_count, "total_enrolled": batch.actual_enrolled}
