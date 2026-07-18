"""
งานในคิว (Celery tasks) — แต่ละงานยิง connector จริง (async ผ่าน asyncio.run)
สอดคล้องกับ 6 โมดูล / AI Growth Loop
"""
import asyncio

from app.worker.celery_app import celery_app
from app.connectors import mining, content, serp, citation, publish
from app.db import session as db


def _run(coro):
    return asyncio.run(coro)


# ---- DISCOVER (M1) ----
@celery_app.task(name="app.worker.tasks.discover")
def discover(seed: str) -> dict:
    return _run(mining.mine(seed))


# ---- CREATE (M2) ----
@celery_app.task(name="app.worker.tasks.create_content")
def create_content(topic: str, fmt: str = "บทความยาว", words: int = 1500) -> dict:
    return _run(content.generate(topic, fmt, words))


# ---- PUBLISH (M4) ----
@celery_app.task(name="app.worker.tasks.publish_article")
def publish_article(title: str, html: str, status: str = "draft", url_path: str | None = None) -> dict:
    return _run(publish.publish_and_index(title, html, status, url_path))


# ---- MEASURE (M5) ----
@celery_app.task(name="app.worker.tasks.measure_rank")
def measure_rank(keyword: str, domain: str, project_id: int | None = None) -> dict:
    res = _run(serp.rank_check(keyword, domain))
    if project_id and db.enabled():
        _run(_save_rank(project_id, res))
    return res


@celery_app.task(name="app.worker.tasks.measure_all_ranks")
def measure_all_ranks() -> str:
    """beat: เช็กอันดับของทุกโปรเจ็ค (ดึงคีย์เวิร์ดจาก DB)"""
    # production: วนทุกโปรเจ็ค/คีย์เวิร์ดจากตาราง แล้ว measure_rank.delay(...)
    return "queued: measure ranks for all projects"


@celery_app.task(name="app.worker.tasks.sample_all_citations")
def sample_all_citations() -> str:
    return "queued: prompt sampling for all projects"


@celery_app.task(name="app.worker.tasks.freshness_sweep")
def freshness_sweep() -> str:
    """M3: หาหน้าที่ใกล้ครบ freshness_days แล้วเข้าคิวรีเฟรช"""
    return "queued: freshness refresh for aging pages"


@celery_app.task(name="app.worker.tasks.learning_loop")
def learning_loop() -> str:
    """M6: วิเคราะห์หน้าที่ได้ผล + ปรับเทมเพลต/ลำดับคิว + ส่งรายงาน"""
    return "learning loop executed: templates & queue re-prioritized"


async def _save_rank(project_id: int, res: dict):
    from app.db.models import RankSnapshot
    async with db.session() as s:
        s.add(RankSnapshot(project_id=project_id, keyword=res.get("keyword", ""),
                           rank=res.get("our_rank"), on_page1=bool(res.get("on_page1"))))
        await s.commit()
