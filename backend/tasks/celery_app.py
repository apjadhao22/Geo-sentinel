from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery("pcmc", broker=settings.redis_url)

celery_app.conf.beat_schedule = {
    "ingest-imagery": {
        "task": "tasks.ingest",
        "schedule": crontab(hour=6, minute=0),  # 6:00 AM IST daily
    },
    "check-grace-periods": {
        "task": "tasks.check_grace_periods",
        "schedule": crontab(hour=7, minute=0),  # 7:00 AM IST daily
    },
    "cleanup-old-imagery": {
        "task": "tasks.cleanup_old_imagery",
        "schedule": crontab(day_of_month=1, hour=2, minute=0),  # 1st of month, 2 AM
    },
}
celery_app.conf.timezone = "Asia/Kolkata"


@celery_app.task(name="tasks.ingest")
def ingest_imagery_task():
    import asyncio
    from ingestion.ingest_task import run_ingestion
    asyncio.run(run_ingestion())


@celery_app.task(name="tasks.check_grace_periods")
def check_grace_periods_task():
    import asyncio
    from tasks.grace_period_task import check_expired_grace_periods
    asyncio.run(check_expired_grace_periods())


@celery_app.task(name="tasks.cleanup_old_imagery")
def cleanup_old_imagery_task():
    import asyncio
    from tasks.retention_task import cleanup_old_images
    asyncio.run(cleanup_old_images())
