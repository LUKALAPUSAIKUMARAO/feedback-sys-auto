"""
Admin CRUD endpoint tests.

All tests use the seeded org + admin token from conftest fixtures.
"""
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient


# ─── Helpers ──────────────────────────────────────────────────────────────────

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def future_window(days_from_now_start: int = 1, duration_days: int = 2) -> tuple[str, str]:
    """Return ISO-formatted start/end datetimes for a batch that hasn't happened yet."""
    start = datetime.now(timezone.utc) + timedelta(days=days_from_now_start)
    end = start + timedelta(days=duration_days)
    return start.isoformat(), end.isoformat()


# ─── Trainer endpoints ────────────────────────────────────────────────────────

async def test_create_trainer(test_client: AsyncClient, admin_token: str):
    """POST /admin/trainers → 201 with trainer data."""
    resp = await test_client.post(
        "/api/v1/admin/trainers",
        json={
            "full_name": "Alice Smith",
            "employee_id": "TR-100",
            "email": "alice.smith@bilvantis.io",
            "designation": "Lead Trainer",
            "department": "Engineering",
            "skills": ["python", "aws"],
            "certifications": [],
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["full_name"] == "Alice Smith"
    assert body["employee_id"] == "TR-100"
    assert body["email"] == "alice.smith@bilvantis.io"
    assert "id" in body
    assert body["is_active"] is True


async def test_create_trainer_duplicate_employee_id(test_client: AsyncClient, admin_token: str):
    """Creating a trainer with a duplicate employee_id → 409."""
    payload = {
        "full_name": "Bob Jones",
        "employee_id": "TR-DUP",
        "email": "bob@bilvantis.io",
        "skills": [],
        "certifications": [],
    }
    resp1 = await test_client.post("/api/v1/admin/trainers", json=payload, headers=auth(admin_token))
    assert resp1.status_code == 201

    resp2 = await test_client.post(
        "/api/v1/admin/trainers",
        json={**payload, "full_name": "Bob Jones 2", "email": "bob2@bilvantis.io"},
        headers=auth(admin_token),
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()


async def test_list_trainers(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """GET /admin/trainers returns paginated results including the seeded trainer."""
    resp = await test_client.get("/api/v1/admin/trainers", headers=auth(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert "page_size" in body
    assert "pages" in body
    assert body["total"] >= 1
    # seeded trainer should appear
    ids = [item["id"] for item in body["items"]]
    assert seeded_batch["trainer_id"] in ids


async def test_list_trainers_unauthenticated(test_client: AsyncClient, admin_token: str):
    """GET /admin/trainers without token → 401."""
    resp = await test_client.get("/api/v1/admin/trainers")
    assert resp.status_code == 401


# ─── Program endpoints ────────────────────────────────────────────────────────

async def test_create_program(test_client: AsyncClient, admin_token: str):
    """POST /admin/programs → 201 with program data."""
    resp = await test_client.post(
        "/api/v1/admin/programs",
        json={
            "title": "Advanced FastAPI",
            "description": "Deep dive into FastAPI",
            "skills_covered": ["fastapi", "async"],
            "competency_tags": ["backend"],
            "duration_hours": 24.0,
            "level": "advanced",
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Advanced FastAPI"
    assert body["is_active"] is True
    assert "id" in body


async def test_list_programs(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """GET /admin/programs returns paginated list including seeded program."""
    resp = await test_client.get("/api/v1/admin/programs", headers=auth(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    ids = [item["id"] for item in body["items"]]
    assert seeded_batch["program_id"] in ids


# ─── Batch endpoints ──────────────────────────────────────────────────────────

async def test_create_batch(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """POST /admin/batches → 201 with batch data."""
    start, end = future_window(1, 2)
    resp = await test_client.post(
        "/api/v1/admin/batches",
        json={
            "program_id": seeded_batch["program_id"],
            "trainer_id": seeded_batch["trainer_id"],
            "batch_code": "BATCH-NEW-001",
            "title": "New Batch",
            "start_datetime": start,
            "end_datetime": end,
            "max_capacity": 20,
            "mode": "online",
            "feedback_threshold": 5,
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["batch_code"] == "BATCH-NEW-001"
    assert body["status"] == "scheduled"
    assert "id" in body


async def test_create_batch_invalid_dates(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """end_datetime before start_datetime → 422 validation error."""
    now = datetime.now(timezone.utc)
    start = (now + timedelta(days=2)).isoformat()
    end = (now + timedelta(days=1)).isoformat()  # end is BEFORE start

    resp = await test_client.post(
        "/api/v1/admin/batches",
        json={
            "program_id": seeded_batch["program_id"],
            "trainer_id": seeded_batch["trainer_id"],
            "batch_code": "BATCH-BAD-DATES",
            "start_datetime": start,
            "end_datetime": end,
            "max_capacity": 20,
            "mode": "online",
            "feedback_threshold": 5,
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 422


async def test_create_batch_equal_dates(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """end_datetime equal to start_datetime → 422 validation error."""
    now = datetime.now(timezone.utc)
    same = now.isoformat()

    resp = await test_client.post(
        "/api/v1/admin/batches",
        json={
            "program_id": seeded_batch["program_id"],
            "trainer_id": seeded_batch["trainer_id"],
            "batch_code": "BATCH-EQUAL-DATES",
            "start_datetime": same,
            "end_datetime": same,
            "max_capacity": 20,
            "mode": "online",
            "feedback_threshold": 5,
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 422


async def test_list_batches(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """GET /admin/batches returns paginated list with the seeded batch."""
    resp = await test_client.get("/api/v1/admin/batches", headers=auth(admin_token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 1
    ids = [item["id"] for item in body["items"]]
    assert seeded_batch["batch_id"] in ids


async def test_get_batch_by_id(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """GET /admin/batches/{id} returns batch with trainer and program relations."""
    resp = await test_client.get(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == seeded_batch["batch_id"]
    # WithRelations schema includes nested objects
    assert body["trainer"]["id"] == seeded_batch["trainer_id"]
    assert body["program"]["id"] == seeded_batch["program_id"]


# ─── Participant upload ───────────────────────────────────────────────────────

async def test_upload_participants_json(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """POST /admin/batches/{id}/participants with JSON → 201 and created count."""
    # Upload 2 brand-new participants to the already-seeded batch
    resp = await test_client.post(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/participants",
        json={
            "participants": [
                {
                    "full_name": "New Participant A",
                    "email": "new.a@test.com",
                    "employee_id": "NEW-A-001",
                    "department": "HR",
                },
                {
                    "full_name": "New Participant B",
                    "email": "new.b@test.com",
                    "employee_id": "NEW-B-001",
                    "department": "Finance",
                },
            ]
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["created"] == 2
    assert body["enrolled"] == 2
    assert body["errors"] == []


async def test_upload_participants_nonexistent_batch(test_client: AsyncClient, admin_token: str):
    """Uploading participants to a nonexistent batch → 404."""
    resp = await test_client.post(
        "/api/v1/admin/batches/00000000-0000-0000-0000-000000000099/participants",
        json={
            "participants": [
                {"full_name": "Ghost", "email": "ghost@test.com", "employee_id": "G-001"}
            ]
        },
        headers=auth(admin_token),
    )
    assert resp.status_code == 404


# ─── Roster ───────────────────────────────────────────────────────────────────

async def test_list_batch_roster(test_client: AsyncClient, admin_token: str, seeded_batch: dict):
    """GET /admin/batches/{id}/roster returns roster entries with feedback_url."""
    resp = await test_client.get(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/roster",
        headers=auth(admin_token),
    )
    assert resp.status_code == 200
    roster = resp.json()
    assert isinstance(roster, list)
    assert len(roster) == 3  # seeded_batch has 3 participants

    for entry in roster:
        assert "roster_id" in entry
        assert "participant_id" in entry
        assert "full_name" in entry
        assert "email" in entry
        assert "employee_id" in entry
        assert "feedback_url" in entry
        assert "has_submitted" in entry
        assert entry["has_submitted"] is False  # no feedback submitted yet
        # feedback_url must be a well-formed URL containing the token
        assert entry["feedback_url"] is not None
        assert entry["feedback_token"] in entry["feedback_url"]
