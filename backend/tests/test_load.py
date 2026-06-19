"""
Load simulation tests — bulk uploads and concurrent submissions.

These tests verify correctness at scale, not performance benchmarks.
They run against the same in-memory SQLite + FakeRedis stack as all other tests.
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient

from app.core.security import create_feedback_token


# ─── Helpers ──────────────────────────────────────────────────────────────────

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_participant_list(count: int, id_prefix: str = "BLK") -> list[dict]:
    return [
        {
            "full_name": f"Load Participant {i}",
            "email": f"load{id_prefix}{i}@test.com",
            "employee_id": f"{id_prefix}-{i:04d}",
            "department": "Engineering",
        }
        for i in range(1, count + 1)
    ]


def valid_ratings(token: str) -> dict:
    return {
        "token": token,
        "rating_technical_knowledge": 4,
        "rating_communication": 5,
        "rating_session_engagement": 4,
        "rating_time_management": 3,
        "rating_practical_learning": 5,
        "rating_content_quality": 4,
        "free_text_positive": "Load test submission",
        "is_anonymous": False,
    }


# ─── Bulk upload — 100 participants ──────────────────────────────────────────

async def test_bulk_100_participants(
    test_client: AsyncClient, admin_token: str, seeded_batch: dict
):
    """
    Upload 100 participants in a single request.
    All must be created and enrolled without errors.
    """
    participants = make_participant_list(100, "BLK100")

    resp = await test_client.post(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/participants",
        json={"participants": participants},
        headers=auth(admin_token),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["created"] == 100
    assert body["enrolled"] == 100
    assert body["errors"] == []

    # Verify roster count via GET
    roster_resp = await test_client.get(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/roster",
        headers=auth(admin_token),
    )
    assert roster_resp.status_code == 200
    roster = roster_resp.json()
    # seeded_batch had 3 participants; we added 100 more = 103 total
    assert len(roster) == 103


async def test_bulk_100_feedback_urls_present(
    test_client: AsyncClient, admin_token: str, seeded_batch: dict
):
    """
    Every participant in the bulk upload must receive a feedback_url in the roster.
    """
    participants = make_participant_list(100, "FURL")
    await test_client.post(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/participants",
        json={"participants": participants},
        headers=auth(admin_token),
    )

    roster_resp = await test_client.get(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/roster",
        headers=auth(admin_token),
    )
    roster = roster_resp.json()
    missing_urls = [r for r in roster if r.get("feedback_url") is None]
    assert missing_urls == [], f"{len(missing_urls)} roster entries are missing feedback_url"


# ─── Idempotency — upload same participants twice ─────────────────────────────

async def test_bulk_participant_idempotency(
    test_client: AsyncClient, admin_token: str, seeded_batch: dict
):
    """
    Uploading the same 50 participants twice must not double the roster count.
    The second upload should update existing participants and skip roster creation.
    """
    participants = make_participant_list(50, "IDEM")

    # First upload
    resp1 = await test_client.post(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/participants",
        json={"participants": participants},
        headers=auth(admin_token),
    )
    assert resp1.status_code == 201
    body1 = resp1.json()
    assert body1["created"] == 50
    assert body1["enrolled"] == 50

    # Second upload — same employee IDs
    resp2 = await test_client.post(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/participants",
        json={"participants": participants},
        headers=auth(admin_token),
    )
    assert resp2.status_code == 201
    body2 = resp2.json()
    # All should be updates (existing participants), none enrolled again
    assert body2["updated"] == 50
    assert body2["enrolled"] == 0  # roster already exists for each
    assert body2["errors"] == []

    # Roster count must not be doubled: 3 (seeded) + 50 (first upload) = 53
    roster_resp = await test_client.get(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/roster",
        headers=auth(admin_token),
    )
    assert len(roster_resp.json()) == 53


# ─── Concurrent feedback submissions ─────────────────────────────────────────

async def test_concurrent_feedback_submissions(
    test_client: AsyncClient, seeded_batch: dict
):
    """
    Three different participants submit feedback "simultaneously" via asyncio.gather.
    All three submissions must succeed (different participants = no conflict).
    """
    tokens = seeded_batch["tokens"]  # 3 tokens from conftest seeded_batch

    async def submit(token: str) -> int:
        resp = await test_client.post(
            "/api/v1/feedback/submit",
            json=valid_ratings(token),
        )
        return resp.status_code

    results = await asyncio.gather(*[submit(t) for t in tokens])

    assert list(results) == [200, 200, 200], (
        f"Expected all three concurrent submissions to succeed, got: {results}"
    )


async def test_concurrent_duplicate_submissions_blocked(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """
    Two concurrent requests using the SAME token — exactly one must succeed
    and the other must be blocked (409 or 429).
    This exercises the Redis lock + idempotency guard path.
    """
    async def submit() -> int:
        resp = await test_client.post(
            "/api/v1/feedback/submit",
            json=valid_ratings(feedback_token),
        )
        return resp.status_code

    results = await asyncio.gather(submit(), submit())
    status_codes = sorted(results)

    # One 200 and one 409/429, in any order
    success_count = results.count(200)
    blocked_count = sum(1 for s in results if s in (409, 429))

    assert success_count == 1, f"Expected exactly 1 success, got {success_count}. Statuses: {results}"
    assert blocked_count == 1, f"Expected exactly 1 blocked, got {blocked_count}. Statuses: {results}"


# ─── Large roster list performance check ─────────────────────────────────────

async def test_roster_endpoint_with_large_roster(
    test_client: AsyncClient, admin_token: str, seeded_batch: dict
):
    """
    Roster endpoint must return successfully even with a large number of participants.
    Upload 200 participants and verify the roster response completes.
    """
    participants = make_participant_list(200, "LRG")

    upload_resp = await test_client.post(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/participants",
        json={"participants": participants},
        headers=auth(admin_token),
    )
    assert upload_resp.status_code == 201
    assert upload_resp.json()["enrolled"] == 200

    roster_resp = await test_client.get(
        f"/api/v1/admin/batches/{seeded_batch['batch_id']}/roster",
        headers=auth(admin_token),
    )
    assert roster_resp.status_code == 200
    roster = roster_resp.json()
    assert len(roster) == 203  # 3 seeded + 200 new
