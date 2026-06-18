"""Seed default org + admin user on first startup."""
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.db_models import Organization, User
from app.core.security import get_password_hash
import structlog

log = structlog.get_logger()

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_ADMIN_ID = "00000000-0000-0000-0000-000000000002"
DEFAULT_ADMIN_EMAIL = "admin@bilvantis.io"
DEFAULT_ADMIN_PASSWORD = "Admin@1234"


async def seed_database():
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(Organization).where(Organization.id == DEFAULT_ORG_ID))
        if existing.scalar_one_or_none():
            return

        org = Organization(
            id=DEFAULT_ORG_ID,
            name="Bilvantis",
            domain="bilvantis.io",
            settings={},
            is_active=True,
        )
        db.add(org)

        admin = User(
            id=DEFAULT_ADMIN_ID,
            organization_id=DEFAULT_ORG_ID,
            email=DEFAULT_ADMIN_EMAIL,
            hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            full_name="Bilvantis Admin",
            employee_id="ADMIN-001",
            role="admin",
            is_active=True,
        )
        db.add(admin)

        await db.commit()
        log.info("seed.complete", admin_email=DEFAULT_ADMIN_EMAIL)
