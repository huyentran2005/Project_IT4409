from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "taskflow",
    broker=settings.CELERY_BROKER_URL,
    include=["app.tasks.document_processing"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_track_started=True,
    broker_connection_retry_on_startup=True,
)
