from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from app.api.v1.auth import require_admin
from app.models.db_models import User
from app.core.email import send_feedback_email
import structlog

log = structlog.get_logger()

router = APIRouter(prefix="/settings", tags=["Settings"])


class TestEmailRequest(BaseModel):
    to_email: str
    host: str = "smtp.gmail.com"
    port: int = 587
    user: str = ""
    password: str = ""
    from_email: str = ""
    from_name: str = "Bilvantis TIP"


@router.post("/test-email")
async def test_email(
    payload: TestEmailRequest,
    current_user: User = Depends(require_admin),
):
    """Send a test email using SMTP credentials from the request or configured .env."""
    success = await send_feedback_email(
        to_email=payload.to_email,
        to_name="Test User",
        feedback_url="http://localhost:3003/feedback/test-token",
        batch_title="Test Training Batch",
        trainer_name="Test Trainer",
        is_reminder=False,
    )
    if not success:
        raise HTTPException(
            status_code=500,
            detail="Email delivery failed. Check SMTP_USER, SMTP_PASSWORD, SMTP_FROM_EMAIL in your .env file. For Gmail, use an App Password (not your regular password)."
        )
    return {"sent": True, "to": payload.to_email}
