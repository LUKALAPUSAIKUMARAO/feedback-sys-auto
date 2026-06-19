"""
Pytest fixtures for the Training Feedback Intelligence Platform.

All tests run against an in-memory SQLite database and a FakeRedis instance so
the suite is fully self-contained — no Postgres, no real Redis, no Celery needed.
"""
import os
import asyncio
import pytest
import pytest_asyncio
import fakeredis.aioredis as fakeredis_aioredis
from typing import AsyncGenerator

# ── env vars must be set BEFORE any app module is imported ───────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")  # overridden below
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-do-not-use-in-prod")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")
os.environ.setdefault("SENDGRID_API_KEY", "test-sendgrid-key")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault("BACKEND_URL", "http://localhost:8000")
os.environ.setdefault("FEEDBACK_TOKEN_EXPIRE_HOURS", "72")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
os.environ.setdefault("FEEDBACK_THRESHOLD", "5")

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# App imports (after env vars are set)
from app.main import app
from app.core.database import Base, get_db
import app.core.redis_client as _redis_module
from app.models.db_models import (
    Organization, User, Trainer, TrainingProgram, TrainingBatch,
    Participant, BatchRoster, SurveyToken,
)
from app.core.security import get_password_hash, create_feedback_token, decode_feedback_token
from app.core.config import settings

# ── Test database engine (SQLite in-memory) ───────────────────────────────────
TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Session-scoped setup: create tables once per session ─────────────────────
@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_tables():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


# ── Function-scoped: wipe all rows between tests ─────────────────────────────
@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    """Truncate all tables before each test for isolation."""
    yield
    async with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


# ── FakeRedis — reset before each test ───────────────────────────────────────
@pytest_asyncio.fixture(autouse=True)
async def _fake_redis():
    """Inject a fresh FakeRedis client before each test."""
    fake = fakeredis_aioredis.FakeRedis(decode_responses=True)
    _redis_module._redis_client = fake
    yield fake
    await fake.flushall()
    _redis_module._redis_client = None


# ── Override get_db dependency to use test database ──────────────────────────
async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = _override_get_db


# ── AsyncClient fixture ───────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ── Helper: raw DB session (bypasses HTTP layer) ──────────────────────────────
@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Domain fixtures
# ─────────────────────────────────────────────────────────────────────────────

ORG_ID = "00000000-0000-0000-0000-000000000001"
ADMIN_ID = "00000000-0000-0000-0000-000000000002"
ADMIN_EMAIL = "admin@bilvantis.io"
ADMIN_PASSWORD = "Admin@1234"


@pytest_asyncio.fixture
async def admin_token(test_client: AsyncClient, db_session: AsyncSession) -> str:
    """
    Create the default org + admin user, then return a valid Bearer token.
    Returns the raw token string (without 'Bearer ' prefix).
    """
    # Create org
    org = Organization(
        id=ORG_ID,
        name="Bilvantis",
        domain="bilvantis.io",
        settings={},
        is_active=True,
    )
    db_session.add(org)

    # Create admin user
    admin = User(
        id=ADMIN_ID,
        organization_id=ORG_ID,
        email=ADMIN_EMAIL,
        hashed_password=get_password_hash(ADMIN_PASSWORD),
        full_name="Bilvantis Admin",
        employee_id="ADMIN-001",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()

    # Login via API
    resp = await test_client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 200, f"admin_token fixture login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def seeded_batch(db_session: AsyncSession, admin_token: str):
    """
    Create a complete training scenario:
      - 1 Trainer
      - 1 TrainingProgram
      - 1 TrainingBatch
      - 3 Participants enrolled via BatchRoster (with feedback tokens)

    Returns a dict with all IDs and the raw feedback tokens for each participant.
    """
    from datetime import datetime, timezone, timedelta

    # Trainer
    trainer = Trainer(
        organization_id=ORG_ID,
        full_name="John Doe",
        employee_id="TR-001",
        email="john.doe@bilvantis.io",
        designation="Senior Trainer",
        department="Engineering",
    )
    db_session.add(trainer)
    await db_session.flush()

    # Program
    program = TrainingProgram(
        organization_id=ORG_ID,
        title="Python Fundamentals",
        description="Intro to Python",
        skills_covered=["python", "oop"],
        competency_tags=["backend"],
        duration_hours=16.0,
        level="beginner",
        created_by=ADMIN_ID,
    )
    db_session.add(program)
    await db_session.flush()

    # Batch
    now = datetime.now(timezone.utc)
    batch = TrainingBatch(
        organization_id=ORG_ID,
        program_id=program.id,
        trainer_id=trainer.id,
        batch_code="BATCH-TEST-001",
        title="Python Batch Q1",
        start_datetime=now - timedelta(days=5),
        end_datetime=now - timedelta(days=1),
        max_capacity=30,
        actual_enrolled=0,
        mode="online",
        status="completed",
        feedback_threshold=5,
        created_by=ADMIN_ID,
        survey_deadline=now + timedelta(days=2),
    )
    db_session.add(batch)
    await db_session.flush()

    # Participants + Roster entries
    participants = []
    tokens = []
    for i in range(1, 4):
        p = Participant(
            organization_id=ORG_ID,
            full_name=f"Participant {i}",
            email=f"participant{i}@test.com",
            employee_id=f"EMP-{i:03d}",
            department="Engineering",
        )
        db_session.add(p)
        await db_session.flush()

        token = create_feedback_token(str(p.id), str(batch.id))
        token_payload = decode_feedback_token(token)
        jti = token_payload["jti"]
        expires_at = datetime.fromtimestamp(token_payload["exp"], tz=timezone.utc)

        roster = BatchRoster(
            batch_id=batch.id,
            participant_id=p.id,
            feedback_token=token,
        )
        db_session.add(roster)

        survey_token = SurveyToken(
            jti=jti,
            participant_id=p.id,
            batch_id=batch.id,
            expires_at=expires_at,
        )
        db_session.add(survey_token)

        participants.append(p)
        tokens.append(token)

    batch.actual_enrolled = 3
    await db_session.commit()

    return {
        "trainer_id": str(trainer.id),
        "program_id": str(program.id),
        "batch_id": str(batch.id),
        "participants": [str(p.id) for p in participants],
        "tokens": tokens,  # index 0 = participant 1's token, etc.
    }


@pytest_asyncio.fixture
async def feedback_token(seeded_batch: dict) -> str:
    """Return a valid feedback JWT for participant 1 in the seeded batch."""
    return seeded_batch["tokens"][0]
