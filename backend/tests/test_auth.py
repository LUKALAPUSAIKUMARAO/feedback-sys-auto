"""
Auth endpoint tests — /api/v1/auth/login and /api/v1/auth/me
"""
import pytest
from httpx import AsyncClient


# ─── Login ────────────────────────────────────────────────────────────────────

async def test_login_success(test_client: AsyncClient, admin_token: str):
    """Valid credentials return 200 with an access_token."""
    # admin_token fixture already performed a successful login; we verify the shape
    resp = await test_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@bilvantis.io", "password": "Admin@1234"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["role"] == "admin"
    assert body["full_name"] == "Bilvantis Admin"
    assert isinstance(body["expires_in"], int)
    assert body["expires_in"] > 0


async def test_login_wrong_password(test_client: AsyncClient, admin_token: str):
    """Wrong password must return 401."""
    resp = await test_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@bilvantis.io", "password": "WrongPassword99"},
    )
    assert resp.status_code == 401
    assert "Incorrect" in resp.json()["detail"]


async def test_login_unknown_email(test_client: AsyncClient, admin_token: str):
    """Unknown email must return 401."""
    resp = await test_client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "Admin@1234"},
    )
    assert resp.status_code == 401


async def test_login_missing_fields(test_client: AsyncClient, admin_token: str):
    """Missing required fields must return 422 (validation error)."""
    resp = await test_client.post("/api/v1/auth/login", json={"email": "admin@bilvantis.io"})
    assert resp.status_code == 422


# ─── /me endpoint ─────────────────────────────────────────────────────────────

async def test_me_with_valid_token(test_client: AsyncClient, admin_token: str):
    """/me returns user info for a valid token."""
    resp = await test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "admin@bilvantis.io"
    assert body["role"] == "admin"
    assert body["full_name"] == "Bilvantis Admin"
    assert "id" in body
    assert "organization_id" in body


async def test_me_without_token(test_client: AsyncClient, admin_token: str):
    """/me without Authorization header must return 401."""
    resp = await test_client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_with_malformed_token(test_client: AsyncClient, admin_token: str):
    """/me with a garbage token must return 401."""
    resp = await test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
    )
    assert resp.status_code == 401
