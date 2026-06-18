from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from jose import JWTError, jwt
from app.core.config import settings
import bcrypt
import secrets
import structlog

log = structlog.get_logger()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_feedback_token(participant_id: str, batch_id: str) -> str:
    """Asymmetric JWT cryptotoken binding Participant_ID + Batch_ID."""
    jti = secrets.token_urlsafe(32)
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.FEEDBACK_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": "feedback",
        "participant_id": participant_id,
        "batch_id": batch_id,
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_feedback_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("sub") != "feedback":
            raise JWTError("Invalid token subject")
        return payload
    except JWTError as e:
        log.warning("security.token_decode_failed", error=str(e))
        raise


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        log.warning("security.access_token_decode_failed", error=str(e))
        raise
