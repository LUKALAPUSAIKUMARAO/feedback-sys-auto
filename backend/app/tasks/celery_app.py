from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "feedback_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.celery_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
    # Run tasks synchronously when using memory:// broker (no Redis required)
    task_always_eager=settings.CELERY_BROKER_URL.startswith("memory://"),
    task_eager_propagates=True,
    beat_schedule={
        "check-completed-batches": {
            "task": "app.tasks.celery_tasks.check_completed_batches",
            "schedule": crontab(minute="*/5"),
        },
        "send-survey-reminders": {
            "task": "app.tasks.celery_tasks.send_survey_reminders",
            "schedule": crontab(hour="9", minute="0"),
        },
        "cleanup-expired-tokens": {
            "task": "app.tasks.celery_tasks.cleanup_expired_tokens",
            "schedule": crontab(hour="2", minute="0"),
        },
    },
)
