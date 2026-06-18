"""Extend admin router with org-level participant listing."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from app.core.database import get_db
from app.models.db_models import Participant, User
from app.schemas.pydantic_schemas import ParticipantOut, PaginatedResponse
from app.api.v1.auth import require_admin_or_management

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/participants", response_model=PaginatedResponse)
async def list_all_participants(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    department: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin_or_management),
):
    q = select(Participant).where(
        Participant.organization_id == current_user.organization_id,
        Participant.is_active == True,
    )
    if search:
        q = q.where(
            (Participant.full_name.ilike(f"%{search}%")) |
            (Participant.employee_id.ilike(f"%{search}%")) |
            (Participant.email.ilike(f"%{search}%"))
        )
    if department:
        q = q.where(Participant.department.ilike(f"%{department}%"))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    rows = (await db.execute(
        q.order_by(Participant.full_name).offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return PaginatedResponse(
        items=[ParticipantOut.model_validate(r) for r in rows],
        total=total, page=page, page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )
