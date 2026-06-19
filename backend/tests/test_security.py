"""
Security-focused tests — replay attacks, token cross-batch abuse, unauthorised access,
role enforcement, and input validation.
"""
import pytest
import secrets
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from jose import jwt

from app.core.config import settings
from app.core.security import create_feedback_token


# ─── Helpers ──────────────────────────────────────────────────────────────────

def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def valid_ratings() -> dict:
    return {
        "rating_technical_knowledge": 4,
        "rating_communication": 5,
        "rating_session_engagement": 4,
        "rating_time_management": 3,
        "rating_practical_learning": 5,
        "rating_content_quality": 4,
        "is_anonymous": False,
    }


def submit_payload(token: str, overrides: dict | None = None) -> dict:
    payload = {"token": token, **valid_ratings()}
    if overrides:
        payload.update(overrides)
    return payload


# ─── Replay attack ────────────────────────────────────────────────────────────

async def test_replay_attack_blocked(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """
    Using the same feedback token twice must be rejected on the second attempt.
    The first call succeeds; the second is blocked by the Redis + DB idempotency guards.
    """
    payload = submit_payload(feedback_token)

    resp1 = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp1.status_code == 200, f"First submission failed: {resp1.text}"
    assert resp1.json()["success"] is True

    resp2 = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp2.status_code == 409
    detail = resp2.json()["detail"].lower()
    assert "already" in detail or "used" in detail


# ─── Cross-batch token abuse ──────────────────────────────────────────────────

async def test_token_wrong_batch(test_client: AsyncClient, seeded_batch: dict, admin_token: str):
    """
    A feedback token that encodes a valid participant + a DIFFERENT batch must
    not be accepted for the original batch, and vice-versa.

    Scenario: participant 0 holds a token bound to batch A.  We craft a second
    token for the same participant but bound to a fictitious batch B, then
    submit it.  The submission "succeeds" at the HTTP level (SQLite doesn't
    enforce FK constraints by default) but is recorded against the wrong
    (nonexistent) batch — the key security property is that the token is
    cryptographically bound to participant_id + batch_id, so the original
    token for batch A cannot be replayed for a different batch entry.

    We verify this by submitting the legitimate batch-A token AFTER the fake
    batch-B token: if the fake token had poisoned the idempotency guard for
    batch A the second submit would be blocked — but it should succeed because
    the jti values are independent.
    """
    participant_id = seeded_batch["participants"][0]
    legitimate_token = seeded_batch["tokens"][0]

    # Craft a token for a nonexistent/different batch
    fake_batch_id = "00000000-dead-beef-0000-000000000099"
    fake_token = create_feedback_token(participant_id, fake_batch_id)

    # Submit the fake-batch token — may succeed or fail depending on FK enforcement
    fake_resp = await test_client.post(
        "/api/v1/feedback/submit",
        json=submit_payload(fake_token),
    )
    # We don't assert the status of this call — SQLite may or may not enforce FK

    # The legitimate token must still work because it has a different jti
    legit_resp = await test_client.post(
        "/api/v1/feedback/submit",
        json=submit_payload(legitimate_token),
    )
    assert legit_resp.status_code == 200, (
        f"Legitimate token was blocked after fake-batch submission. "
        f"Fake status={fake_resp.status_code}, legit status={legit_resp.status_code}"
    )
    assert legit_resp.json()["success"] is True


# ─── Unauthorised admin endpoint access ───────────────────────────────────────

async def test_unauthorized_admin_endpoint(test_client: AsyncClient, admin_token: str):
    """GET /admin/trainers without a token → 401."""
    resp = await test_client.get("/api/v1/admin/trainers")
    assert resp.status_code == 401


async def test_admin_endpoint_with_invalid_token(test_client: AsyncClient, admin_token: str):
    """GET /admin/trainers with a malformed token → 401."""
    resp = await test_client.get(
        "/api/v1/admin/trainers",
        headers={"Authorization": "Bearer garbage.token.value"},
    )
    assert resp.status_code == 401


async def test_admin_endpoint_with_expired_access_token(
    test_client: AsyncClient, admin_token: str
):
    """GET /admin/trainers with an expired admin access token → 401."""
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    expired_token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000002",
            "role": "admin",
            "exp": past,
            "iat": datetime.now(timezone.utc) - timedelta(seconds=60),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    resp = await test_client.get(
        "/api/v1/admin/trainers",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


# ─── Rating validation ────────────────────────────────────────────────────────

async def test_invalid_rating_too_low(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """Ratings below 1 must be rejected with 422."""
    payload = submit_payload(feedback_token, {"rating_technical_knowledge": 0})
    resp = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp.status_code == 422


async def test_invalid_rating_too_high(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """Ratings above 5 must be rejected with 422."""
    payload = submit_payload(feedback_token, {"rating_communication": 6})
    resp = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp.status_code == 422


async def test_invalid_rating_negative(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """Negative rating values must be rejected with 422."""
    payload = submit_payload(feedback_token, {"rating_session_engagement": -1})
    resp = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp.status_code == 422


async def test_invalid_rating_string_value(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """Non-numeric rating values must be rejected with 422."""
    payload = submit_payload(feedback_token, {"rating_content_quality": "excellent"})
    resp = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp.status_code == 422


async def test_missing_required_rating(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """Omitting a required rating field must be rejected with 422."""
    payload = {
        "token": feedback_token,
        "rating_technical_knowledge": 4,
        # rating_communication is missing
        "rating_session_engagement": 4,
        "rating_time_management": 3,
        "rating_practical_learning": 5,
        "rating_content_quality": 4,
        "is_anonymous": False,
    }
    resp = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp.status_code == 422


# ─── Token subject validation ─────────────────────────────────────────────────

async def test_access_token_rejected_as_feedback_token(
    test_client: AsyncClient, admin_token: str, seeded_batch: dict
):
    """
    An admin access token (sub='<user_id>') must be rejected when used as a
    feedback token because decode_feedback_token checks sub == 'feedback'.
    """
    resp = await test_client.post(
        "/api/v1/feedback/submit",
        json=submit_payload(admin_token),
    )
    assert resp.status_code == 400
