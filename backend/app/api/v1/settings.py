from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.api.v1.auth import require_admin
from app.models.db_models import User
from app.core.email import send_test_smtp
from app.core.config import settings
import structlog

log = structlog.get_logger()

router = APIRouter(prefix="/settings", tags=["Settings"])


class TestEmailRequest(BaseModel):
    to_email: str
    # If omitted, falls back to .env values
    host: str = ""
    port: int = 0
    user: str = ""
    password: str = ""
    from_email: str = ""
    from_name: str = ""


@router.post("/test-email")
async def test_email(
    payload: TestEmailRequest,
    current_user: User = Depends(require_admin),
):
    """Send a test email. Uses provided credentials, or falls back to .env SMTP values."""
    host = payload.host or settings.SMTP_HOST
    port = payload.port or settings.SMTP_PORT
    user = payload.user or settings.SMTP_USER
    password = payload.password or settings.SMTP_PASSWORD
    from_email = payload.from_email or settings.SMTP_FROM_EMAIL
    from_name = payload.from_name or settings.SMTP_FROM_NAME

    if not user or not password or not from_email:
        raise HTTPException(
            status_code=400,
            detail="SMTP credentials not configured. Set SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL in .env or pass them in the request body.",
        )

    ok, error = await send_test_smtp(
        to_email=payload.to_email,
        host=host,
        port=port,
        user=user,
        password=password,
        from_email=from_email,
        from_name=from_name,
    )
    if not ok:
        raise HTTPException(status_code=500, detail=f"Email delivery failed: {error}")
    return {"sent": True, "to": payload.to_email, "via": f"{host}:{port}", "from": from_email}
