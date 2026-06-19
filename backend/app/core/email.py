import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.core.config import settings
import structlog

log = structlog.get_logger()


def _build_html(to_name: str, feedback_url: str, batch_title: str, trainer_name: str, to_email: str, is_reminder: bool, use_google_form: bool = False) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; margin: 0; padding: 0; }}
    .container {{ max-width: 600px; margin: 40px auto; background: #fff; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%); padding: 32px 40px; }}
    .header h1 {{ color: #fff; font-size: 22px; font-weight: 600; margin: 0; }}
    .header p {{ color: #94a3b8; margin: 6px 0 0; font-size: 14px; }}
    .body {{ padding: 40px; }}
    .body p {{ color: #475569; font-size: 15px; line-height: 1.6; margin: 0 0 16px; }}
    .cta {{ display: block; background: #2563eb; color: #fff !important; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 15px; text-align: center; margin: 28px 0; }}
    .meta {{ background: #f1f5f9; border-radius: 8px; padding: 16px 20px; margin: 24px 0; }}
    .meta p {{ color: #64748b; font-size: 13px; margin: 4px 0; }}
    .footer {{ padding: 24px 40px; border-top: 1px solid #e2e8f0; }}
    .footer p {{ color: #94a3b8; font-size: 12px; margin: 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Bilvantis Training Intelligence</h1>
      <p>{"Friendly Reminder — " if is_reminder else ""}Feedback Request</p>
    </div>
    <div class="body">
      <p>Hi {to_name},</p>
      <p>{"We noticed you haven't shared your feedback yet. There's still time!" if is_reminder else f"Thank you for attending <strong>{batch_title}</strong> with {trainer_name}."}</p>
      <p>Your feedback directly improves training quality for your entire organization. It takes less than 3 minutes to complete{"via Google Forms" if use_google_form else ""}.</p>
      <div class="meta">
        <p><strong>Training:</strong> {batch_title}</p>
        <p><strong>Trainer:</strong> {trainer_name}</p>
      </div>
      <a href="{feedback_url}" class="cta">{"Open Google Form →" if use_google_form else "Share My Feedback →"}</a>
      {"<p>Click the button above to open the Google Form and submit your feedback. It only takes 2-3 minutes.</p>" if use_google_form else "<p>This link is unique to you and expires in 72 hours. Please do not share it with others.</p>"}
    </div>
    <div class="footer">
      <p>Bilvantis Agentic AI Training Platform · This email was sent to {to_email}</p>
    </div>
  </div>
</body>
</html>"""


async def send_feedback_email(
    to_email: str,
    to_name: str,
    feedback_url: str,
    batch_title: str,
    trainer_name: str,
    is_reminder: bool = False,
    use_google_form: bool = False,
) -> bool:
    subject = (
        f"Reminder: Share Your Feedback — {batch_title}"
        if is_reminder
        else f"Your Feedback Matters — {batch_title}"
    )
    html_content = _build_html(to_name, feedback_url, batch_title, trainer_name, to_email, is_reminder, use_google_form)

    # Try SMTP first (real delivery)
    if settings.SMTP_USER and settings.SMTP_PASSWORD and settings.SMTP_FROM_EMAIL:
        return await _send_smtp(to_email, subject, html_content)

    # Fallback: SendGrid
    if settings.SENDGRID_API_KEY:
        return await _send_sendgrid(to_email, subject, html_content)

    # Fallback: log only (dev mode)
    log.warning("email.no_provider_configured", to=to_email, subject=subject)
    log.info("email.simulated_send", to=to_email, feedback_url=feedback_url)
    return True


async def _send_smtp(to_email: str, subject: str, html_content: str) -> bool:
    def _blocking_send():
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_content, "html"))
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())

    try:
        await asyncio.to_thread(_blocking_send)
        log.info("email.smtp_sent", to=to_email)
        return True
    except Exception as e:
        log.error("email.smtp_failed", to=to_email, error=str(e))
        return False


async def _send_sendgrid(to_email: str, subject: str, html_content: str) -> bool:
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        log.info("email.sendgrid_sent", to=to_email, status=response.status_code)
        return response.status_code in (200, 202)
    except Exception as e:
        log.error("email.sendgrid_failed", to=to_email, error=str(e))
        return False
