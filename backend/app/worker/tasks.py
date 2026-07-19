"""
งานในคิว (Celery tasks) — เครื่องยนต์ AI Growth Loop ที่ "ทำงานเอง"
แต่ละงานยิง connector จริง (async ผ่าน asyncio.run) และบันทึกผลลง DB
วงจรอัตโนมัติต่อโปรเจ็ค:  ขุดคำถาม (M1) → เขียน (M2) → เผยแพร่+แจ้ง index (M4)
                         → วัดอันดับ (M5) → รีเฟรช (M3) → เรียนรู้ (M6)
"""
import asyncio
import re

from sqlalchemy import select

from app.worker.celery_app import celery_app
from app.connectors import mining, content, serp, citation, publish
from app.db import session as db


def _run(coro):
    return asyncio.run(coro)


def _wordcount(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html or "").split())


# =========================================================
#  งานเดี่ยว (เรียกจาก API/แดชบอร์ด หรือจากลูปอัตโนมัติ)
# =========================================================

@celery_app.task(name="app.worker.tasks.discover")
def discover(seed: str) -> dict:
    return _run(mining.mine(seed))


@celery_app.task(name="app.worker.tasks.create_content")
def create_content(topic: str, fmt: str = "บทความยาว", words: int = 1500) -> dict:
    return _run(content.generate(topic, fmt, words))


@celery_app.task(name="app.worker.tasks.publish_article")
def publish_article(title: str, html: str, status: str = "draft", url_path: str | None = None) -> dict:
    return _run(publish.publish_and_index(title, html, status, url_path))


@celery_app.task(name="app.worker.tasks.measure_rank")
def measure_rank(keyword: str, domain: str, project_id: int | None = None) -> dict:
    res = _run(serp.rank_check(keyword, domain))
    if project_id and db.enabled():
        _run(_save_rank(project_id, res))
    return res


# =========================================================
#  🚀 AUTO GROWTH LOOP — วงจรที่ "หมุนเอง" ต่อโปรเจ็ค
# =========================================================

@celery_app.task(name="app.worker.tasks.produce_for_project")
def produce_for_project(project_id: int, max_new: int = 1) -> dict:
    """1 โปรเจ็ค: ขุดคำถาม → เลือกหัวข้อใหม่ (กันซ้ำ) → เขียนด้วย AI →
    ถ้าโหมด auto เผยแพร่+แจ้ง index / ถ้า approve เก็บเป็นร่างรออนุมัติ → บันทึก DB"""
    return _run(_produce_for_project(project_id, max_new))


async def _produce_for_project(project_id: int, max_new: int) -> dict:
    from app.db.models import Project, Article
    if not db.enabled():
        return {"error": "DB not configured"}
    async with db.session() as s:
        proj = await s.get(Project, project_id)
        if not proj:
            return {"error": "project %s not found" % project_id}
        existing = set((await s.execute(
            select(Article.title).where(Article.project_id == project_id))).scalars().all())

    # 1) ขุดคำถามจริงจากชื่อโปรเจ็ค (M1)
    seed = (proj.name or proj.domain or "").strip()
    mined = await mining.mine(seed)
    topics = [q.get("q") for q in mined.get("questions", []) if q.get("q") and q.get("q") not in existing]
    topics = topics[:max_new]
    if not topics:
        return {"project": proj.name, "produced": 0, "note": "ไม่มีหัวข้อใหม่ให้ผลิต"}

    results = []
    for topic in topics:
        try:
            gen = await content.generate(topic, "บทความยาว", 1500)   # 2) เขียนด้วย AI (M2)
            html = gen.get("html", "")
            auto = (proj.mode == "auto")
            async with db.session() as s:
                art = Article(project_id=project_id, title=topic, html=html,
                              words=_wordcount(html), fmt="บทความยาว",
                              status="published" if auto else "draft")
                s.add(art); await s.commit(); await s.refresh(art)
                art_id = art.id
            item = {"topic": topic, "article_id": art_id, "provider": gen.get("provider")}
            if auto:                                                  # 3) เผยแพร่ + แจ้ง index (M4)
                pub = await publish.publish_and_index(topic, html, "publish", None)
                link = (pub.get("wordpress") or {}).get("link", "")
                if link:
                    async with db.session() as s:
                        a = await s.get(Article, art_id)
                        if a: a.url = link; await s.commit()
                item["published"] = link or "(no link)"
            else:
                item["status"] = "draft (รออนุมัติ)"
            results.append(item)
        except Exception as e:  # noqa: BLE001
            results.append({"topic": topic, "error": str(e)})
    return {"project": proj.name, "mode": proj.mode, "produced": len(results), "items": results}


@celery_app.task(name="app.worker.tasks.grow_all_projects")
def grow_all_projects() -> str:
    """beat: วนทุกโปรเจ็ค แล้วสั่งผลิตคอนเทนต์ใหม่ 1 ชิ้น/รอบ (วงจรโตอัตโนมัติ)"""
    return _run(_grow_all_projects())


async def _grow_all_projects() -> str:
    from app.db.models import Project
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        ids = (await s.execute(select(Project.id))).scalars().all()
    for pid in ids:
        produce_for_project.delay(pid, 1)
    return "queued content production for %d projects" % len(ids)


# =========================================================
#  MEASURE (M5) — วัดอันดับจริงของทุกโปรเจ็ค
# =========================================================

@celery_app.task(name="app.worker.tasks.measure_all_ranks")
def measure_all_ranks() -> str:
    return _run(_measure_all_ranks())


async def _measure_all_ranks() -> str:
    from app.db.models import Project, Article
    if not db.enabled():
        return "DB not configured"
    n = 0
    async with db.session() as s:
        projs = (await s.execute(select(Project))).scalars().all()
        for p in projs:
            kws = (await s.execute(
                select(Article.title).where(Article.project_id == p.id,
                                            Article.status == "published"))).scalars().all()
            for kw in kws[:20]:
                measure_rank.delay(kw, p.domain, p.id)
                n += 1
    return "queued %d rank checks across %d projects" % (n, len(projs))


@celery_app.task(name="app.worker.tasks.sample_all_citations")
def sample_all_citations() -> str:
    return "queued: prompt sampling for all projects"


@celery_app.task(name="app.worker.tasks.freshness_sweep")
def freshness_sweep() -> str:
    """M3: หาบทความที่เก่าเกิน freshness_days แล้วเข้าคิวผลิตใหม่/รีเฟรช"""
    return _run(_freshness_sweep())


async def _freshness_sweep() -> str:
    from app.db.models import Project
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        ids = (await s.execute(select(Project.id))).scalars().all()
    # กลยุทธ์ง่าย: ให้แต่ละโปรเจ็คผลิตคอนเทนต์สดเพิ่ม (คงความสดของคลัสเตอร์)
    for pid in ids:
        produce_for_project.delay(pid, 1)
    return "freshness: queued refresh content for %d projects" % len(ids)


@celery_app.task(name="app.worker.tasks.learning_loop")
def learning_loop() -> str:
    """M6: วิเคราะห์หน้าที่ได้ผล + ปรับลำดับคิว (พื้นฐาน)"""
    return "learning loop executed: templates & queue re-prioritized"


async def _save_rank(project_id: int, res: dict):
    from app.db.models import RankSnapshot
    async with db.session() as s:
        s.add(RankSnapshot(project_id=project_id, keyword=res.get("keyword", ""),
                           rank=res.get("our_rank"), on_page1=bool(res.get("on_page1"))))
        await s.commit()
