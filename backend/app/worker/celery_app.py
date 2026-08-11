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
    # โหมดคุณภาพสูง (Fable 5 คิดลึก + 3 สเตจ + รูป) ใช้เวลานาน → ขยายเพดานไม่ให้ถูกฆ่ากลางคัน
    task_time_limit=2400,          # ฆ่าแข็งที่ 40 นาที (กัน task ค้างจริง)
    task_soft_time_limit=2280,     # เตือน/ให้จบสวย ๆ ก่อน 38 นาที
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
    "submit-sitemaps-daily": {       # ⚡ ออโต้บอก Google(GSC)+Bing(IndexNow) ให้เก็บบทความครบทุกวัน 02:45 (หลังผลิต 02:00)
        "task": "app.worker.tasks.submit_sitemaps",
        "schedule": crontab(hour=2, minute=45),
    },
    "aeo-study-weekly": {            # 📊 #12 Data Study · สแกนเว็บไทยจริง → สถิติ AEO (linkable asset) ทุกเสาร์ 08:30
        "task": "app.worker.tasks.scan_aeo_study",
        "schedule": crontab(hour=8, minute=30, day_of_week=6),
    },
    "measure-rank-daily": {          # M5 · เช็กอันดับทุกวัน 06:00
        "task": "app.worker.tasks.measure_all_ranks",
        "schedule": crontab(hour=6, minute=0),
    },
    "boost-rankings-daily": {        # ⚡ ดันหน้าจ่อหน้า1 (11-40) / หลุดหน้า1 ทุกวัน 06:30 (หลังวัดอันดับ)
        "task": "app.worker.tasks.boost_rankings",
        "schedule": crontab(hour=6, minute=30),
    },
    "link-push-daily": {             # ⚡ อัดลิงก์ภายใน → หน้าจ่อหน้า1 ทุกวัน 06:45 (ฟรี ไม่ยิง API)
        "task": "app.worker.tasks.link_push",
        "schedule": crontab(hour=6, minute=45),
    },
    "paa-sniper-weekly": {           # ⚡ ดึง PAA จริง → เติม FAQ ให้หน้าจ่อหน้า1 ทุกวันอังคาร 07:15 (ต้องต่อ DataForSEO)
        "task": "app.worker.tasks.paa_boost",
        "schedule": crontab(hour=7, minute=15, day_of_week=2),
    },
    "sample-citation-weekly": {      # M5 · Prompt Sampling ทุกวันจันทร์ 07:00
        "task": "app.worker.tasks.sample_all_citations",
        "schedule": crontab(hour=7, minute=0, day_of_week=1),
    },
    "freshness-check-daily": {       # M3 · ตรวจ Freshness ทุกวัน 03:00
        "task": "app.worker.tasks.freshness_sweep",
        "schedule": crontab(hour=3, minute=0),
    },
    "easy-win-assess-daily": {       # ⚡ #1 Easy-Win Radar · ประเมินความยากคีย์เวิร์ดจาก SERP ทุกวัน 01:30 (ก่อนผลิต 02:00)
        "task": "app.worker.tasks.assess_easy_wins",
        "schedule": crontab(hour=1, minute=30),
    },
    "optimize-lowscore-daily": {     # M3 · ซ่อมบทความคะแนน AEO ต่ำสุดทุกวัน 05:00 (auto-tuning)
        "task": "app.worker.tasks.optimize_low_scores",
        "schedule": crontab(hour=5, minute=0),
    },
    "grow-clusters-weekly": {        # ⚡ #3 ขยายคลัสเตอร์เป็นชุด (อำนาจหัวข้อ) ทุกวันพุธ 04:00
        "task": "app.worker.tasks.grow_clusters",
        "schedule": crontab(hour=4, minute=0, day_of_week=3),
    },
    "backfill-schema-daily": {       # ⚡ เติม Schema (JSON-LD) ที่ขาด 'ทุกวัน' 03:30 (เร็ว/deterministic) → coverage พุ่ง
        "task": "app.worker.tasks.backfill_schema",
        "schedule": crontab(hour=3, minute=30),
    },
    "backfill-covers-daily": {       # ⚡ เติมรูปปก+รูปในเนื้อ ให้บทความที่ยังไม่มีภาพ 'ทุกวัน' 03:45 (หลังเติม Schema) → หน้าบทความสวย
        "task": "app.worker.tasks.backfill_covers",
        "schedule": crontab(hour=3, minute=45),
    },
    "refresh-interlinks-daily": {    # ⚡ #5 หมุนลิงก์ภายใน 'ทุกวัน' 04:30 (ช่วยหน้ากำพร้า+ดันหน้าใหม่)
        "task": "app.worker.tasks.refresh_interlinks",
        "schedule": crontab(hour=4, minute=30),
    },
    "gsc-ctr-weekly": {              # ⚡ #4 CTR optimizer (ต้องต่อ GSC) ทุกวันพฤหัส 05:30
        "task": "app.worker.tasks.gsc_ctr_boost",
        "schedule": crontab(hour=5, minute=30, day_of_week=4),
    },
    "gsc-opportunities-weekly": {    # ⚡ GSC Opportunity Finder: คีย์ที่ Google โชว์เราแล้ว → เขียน/ดัน (ต้องต่อ GSC) ทุกพุธ 06:15
        "task": "app.worker.tasks.gsc_opportunities",
        "schedule": crontab(hour=6, minute=15, day_of_week=3),
    },
    "competitor-gap-weekly": {       # ⚡ #7 competitor gap (ต้องต่อ DataForSEO) ทุกวันศุกร์ 05:00
        "task": "app.worker.tasks.competitor_gap_scan",
        "schedule": crontab(hour=5, minute=0, day_of_week=5),
    },
    "authority-sweep-weekly": {      # 🔗 คิว backlink/outreach (competitor gap → OutreachTask) ทุกศุกร์ 09:00
        "task": "app.worker.tasks.authority_sweep",
        "schedule": crontab(hour=9, minute=0, day_of_week=5),
    },
    "learn-weekly": {                # M6 · สรุป+ปรับกลยุทธ์ ทุกวันอาทิตย์ 20:00
        "task": "app.worker.tasks.learning_loop",
        "schedule": crontab(hour=20, minute=0, day_of_week=0),
    },
    "report-weekly": {               # M6 · ส่งรายงานรายสัปดาห์ทางอีเมล ทุกวันจันทร์ 08:00
        "task": "app.worker.tasks.send_weekly_reports",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
    },
    "cost-watch-daily": {            # 💳 เฝ้าค่าใช้จ่าย/เครดิต → เตือน LINE เมื่อใกล้หมด/เกินงบ ทุกวัน 09:00
        "task": "app.worker.tasks.cost_watch",
        "schedule": crontab(hour=9, minute=0),
    },
    "self-check-daily": {            # 🩺 เฝ้าระบบ + ซ่อมเบา ๆ (db/redis/การผลิต/บทความตั้งเวลา) → เตือน LINE เมื่อมีปัญหา ทุกวัน 09:30
        "task": "app.worker.tasks.self_check",
        "schedule": crontab(hour=9, minute=30),
    },
    "social-push-daily": {           # ♻️ กระจายบทความไป FB/โซเชียลที่ต่อไว้ (ดริปวันละ 1/ช่อง กันสแปม) ทุกวัน 10:15
        "task": "app.worker.tasks.social_push",
        "schedule": crontab(hour=10, minute=15),
    },
    "publish-scheduled": {           # M4 · เผยแพร่บทความที่ตั้งเวลาไว้ ทุก 15 นาที
        "task": "app.worker.tasks.publish_scheduled",
        "schedule": crontab(minute="*/15"),
    },
}
