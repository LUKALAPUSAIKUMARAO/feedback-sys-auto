"""
Feedback workflow tests — /api/v1/feedback/validate and /api/v1/feedback/submit
"""
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient

from app.core.security import create_feedback_token


# ─── Helpers ──────────────────────────────────────────────────────────────────

def valid_ratings() -> dict:
    """Return a complete, valid set of rating fields for a submission payload."""
    return {
        "rating_technical_knowledge": 4,
        "rating_communication": 5,
        "rating_session_engagement": 4,
        "rating_time_management": 3,
        "rating_practical_learning": 5,
        "rating_content_quality": 4,
        "free_text_positive": "Great session!",
        "free_text_improve": "More exercises would help.",
        "free_text_overall": "Overall a good experience.",
        "is_anonymous": False,
    }


def submit_payload(token: str, overrides: dict | None = None) -> dict:
    payload = {"token": token, **valid_ratings()}
    if overrides:
        payload.update(overrides)
    return payload


# ─── Validate endpoint ────────────────────────────────────────────────────────

async def test_validate_token_valid(test_client: AsyncClient, seeded_batch: dict, feedback_token: str):
    """GET /feedback/validate/{token} with a fresh token → valid=True."""
    resp = await test_client.get(f"/api/v1/feedback/validate/{feedback_token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["already_submitted"] is False
    assert body["expired"] is False
    # Context fields should be populated from the seeded batch
    assert body["participant_name"] == "Participant 1"
    assert "Python" in body["program_title"]


async def test_validate_token_invalid(test_client: AsyncClient, admin_token: str):
    """GET /feedback/validate/badtoken → valid=False (JWT decode fails)."""
    resp = await test_client.get("/api/v1/feedback/validate/this-is-not-a-valid-jwt-token")
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False


async def test_validate_token_after_submission(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """After a successful submission the validate endpoint marks the token as already_submitted."""
    # Submit first
    submit_resp = await test_client.post(
        "/api/v1/feedback/submit",
        json=submit_payload(feedback_token),
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["success"] is True

    # Validate should now report already_submitted
    validate_resp = await test_client.get(f"/api/v1/feedback/validate/{feedback_token}")
    assert validate_resp.status_code == 200
    body = validate_resp.json()
    assert body["valid"] is False
    assert body["already_submitted"] is True


# ─── Submit endpoint ──────────────────────────────────────────────────────────

async def test_submit_feedback_success(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """POST /feedback/submit with a valid token → 200 + success=True."""
    resp = await test_client.post(
        "/api/v1/feedback/submit",
        json=submit_payload(feedback_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "submission_id" in body
    assert body["submission_id"] is not None
    assert "Thank you" in body["message"]


async def test_submit_feedback_duplicate(
    test_client: AsyncClient, seeded_batch: dict, feedback_token: str
):
    """Submitting feedback twice with the same token → second call returns 409."""
    payload = submit_payload(feedback_token)

    resp1 = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp1.status_code == 200

    resp2 = await test_client.post("/api/v1/feedback/submit", json=payload)
    assert resp2.status_code == 409
    detail = resp2.json()["detail"].lower()
    assert "already" in detail or "used" in detail


async def test_submit_feedback_expired_token(
    test_client: AsyncClient, seeded_batch: dict
):
    """An expired JWT → submit returns 400 (invalid/expired token)."""
    from datetime import timedelta
    import time
    from jose import jwt
    from app.core.config import settings
    import secrets

    participant_id = seeded_batch["participants"][1]
    batch_id = seeded_batch["batch_id"]

    jti = secrets.token_urlsafe(32)
    # Expire 1 second in the past
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    payload = {
        "sub": "feedback",
        "participant_id": participant_id,
        "batch_id": batch_id,
        "jti": jti,
        "exp": past,
        "iat": datetime.now(timezone.utc) - timedelta(seconds=10),
    }
    expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    resp = await test_client.post(
        "/api/v1/feedback/submit",
        json=submit_payload(expired_token),
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()


async def test_submit_feedback_invalid_token_string(test_client: AsyncClient, admin_token: str):
    """Completely invalid token string → 400."""
    resp = await test_client.post(
        "/api/v1/feedback/submit",
        json=submit_payload("not.a.real.token.at.all"),
    )
    assert resp.status_code == 400


async def test_submit_feedback_all_participants(
    test_client: AsyncClient, seeded_batch: dict
):
    """All 3 participants can each submit feedback once without errors."""
    for token in seeded_batch["tokens"]:
        resp = await test_client.post(
            "/api/v1/feedback/submit",
            json=submit_payload(token),
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True
