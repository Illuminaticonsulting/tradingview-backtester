"""
Celery application configuration.
"""
from celery import Celery

from ..config import get_settings

settings = get_settings()

celery_app = Celery(
    "tv_backtester",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.api.workers.backtest_worker"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # One task at a time (Playwright needs resources)
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
