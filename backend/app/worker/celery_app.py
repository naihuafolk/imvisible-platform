"""
Celery app — คิวงานอัตโนมัติ 24 ชม. (ตาม stack หน้า 7: Redis + Celery)
รัน worker:  celery -A app.worker.celery_app worker -l info
รัน beat:    celery -A app.worker.celery_app beat -l info   (ตัวตั้งเวลาให้วงจรทำงานเอง)
"""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "rankpilot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
    task_time_limit=600,
    timezone="Asia/Bangkok",
    enable_utc=False,
)

# ตารางเวลาให้ "วงจรโต" หมุนเอง (AI Growth Loop)
celery_app.conf.beat_schedule = {
    "measure-rank-daily": {          # M5 · เช็กอันดับทุกวัน 06:00
        "task": "app.worker.tasks.measure_all_ranks",
        "schedule": crontab(hour=6, minute=0),
    },
    "sample-citation-weekly": {      # M5 · Prompt Sampling ทุกวันจันทร์ 07:00
        "task": "app.worker.tasks.sample_all_citations",
        "schedule": crontab(hour=7, minute=0, day_of_week=1),
    },
    "freshness-check-daily": {       # M3 · ตรวจ Freshness ทุกวัน 03:00
        "task": "app.worker.tasks.freshness_sweep",
        "schedule": crontab(hour=3, minute=0),
    },
    "learn-weekly": {                # M6 · สรุป+ปรับกลยุทธ์ ทุกวันอาทิตย์ 20:00
        "task": "app.worker.tasks.learning_loop",
        "schedule": crontab(hour=20, minute=0, day_of_week=0),
    },
}
