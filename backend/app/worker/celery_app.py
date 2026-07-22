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
    # ถ้า Redis ล่ม: ให้ .delay() จาก API "ล้มเร็ว" (ไม่ค้างคำขอนานหลายนาที) —
    # endpoint ที่เรียกจะ try/except แล้วไปต่อได้ (เช่น สร้างโปรเจ็คสำเร็จ แต่ analyzing=False)
    task_publish_retry=False,
    broker_transport_options={"socket_connect_timeout": 3, "socket_timeout": 3},
    broker_connection_retry_on_startup=True,   # worker ยัง retry ตอน boot ได้ตามปกติ
)

# ตารางเวลาให้ "วงจรโต" หมุนเอง (AI Growth Loop)
celery_app.conf.beat_schedule = {
    "grow-content-daily": {          # 🚀 M1→M2→M4 · ผลิตคอนเทนต์ใหม่อัตโนมัติทุกวัน 02:00
        "task": "app.worker.tasks.grow_all_projects",
        "schedule": crontab(hour=2, minute=0),
    },
    "measure-rank-daily": {          # M5 · เช็กอันดับทุกวัน 06:00
        "task": "app.worker.tasks.measure_all_ranks",
        "schedule": crontab(hour=6, minute=0),
    },
    "boost-rankings-daily": {        # ⚡ ดันหน้าจ่อหน้า1 (11-40) / หลุดหน้า1 ทุกวัน 06:30 (หลังวัดอันดับ)
        "task": "app.worker.tasks.boost_rankings",
        "schedule": crontab(hour=6, minute=30),
    },
    "sample-citation-weekly": {      # M5 · Prompt Sampling ทุกวันจันทร์ 07:00
        "task": "app.worker.tasks.sample_all_citations",
        "schedule": crontab(hour=7, minute=0, day_of_week=1),
    },
    "freshness-check-daily": {       # M3 · ตรวจ Freshness ทุกวัน 03:00
        "task": "app.worker.tasks.freshness_sweep",
        "schedule": crontab(hour=3, minute=0),
    },
    "optimize-lowscore-daily": {     # M3 · ซ่อมบทความคะแนน AEO ต่ำสุดทุกวัน 05:00 (auto-tuning)
        "task": "app.worker.tasks.optimize_low_scores",
        "schedule": crontab(hour=5, minute=0),
    },
    "grow-clusters-weekly": {        # ⚡ #3 ขยายคลัสเตอร์เป็นชุด (อำนาจหัวข้อ) ทุกวันพุธ 04:00
        "task": "app.worker.tasks.grow_clusters",
        "schedule": crontab(hour=4, minute=0, day_of_week=3),
    },
    "ensure-schema-weekly": {        # ⚡ #8 เติม schema (JSON-LD) ที่ขาด ทุกวันอังคาร 04:00
        "task": "app.worker.tasks.ensure_schema",
        "schedule": crontab(hour=4, minute=0, day_of_week=2),
    },
    "refresh-interlinks-weekly": {   # ⚡ #5 หมุนลิงก์ภายใน (authority routing) ทุกวันเสาร์ 04:30
        "task": "app.worker.tasks.refresh_interlinks",
        "schedule": crontab(hour=4, minute=30, day_of_week=6),
    },
    "learn-weekly": {                # M6 · สรุป+ปรับกลยุทธ์ ทุกวันอาทิตย์ 20:00
        "task": "app.worker.tasks.learning_loop",
        "schedule": crontab(hour=20, minute=0, day_of_week=0),
    },
    "report-weekly": {               # M6 · ส่งรายงานรายสัปดาห์ทางอีเมล ทุกวันจันทร์ 08:00
        "task": "app.worker.tasks.send_weekly_reports",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
    },
    "publish-scheduled": {           # M4 · เผยแพร่บทความที่ตั้งเวลาไว้ ทุก 15 นาที
        "task": "app.worker.tasks.publish_scheduled",
        "schedule": crontab(minute="*/15"),
    },
}
