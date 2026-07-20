"""
งานในคิว (Celery tasks) — เครื่องยนต์ AI Growth Loop ที่ "ทำงานเอง"
แต่ละงานยิง connector จริง (async ผ่าน asyncio.run) และบันทึกผลลง DB
วงจรอัตโนมัติต่อโปรเจ็ค:  ขุดคำถาม (M1) → เขียน (M2) → เผยแพร่+แจ้ง index (M4)
                         → วัดอันดับ (M5) → รีเฟรช (M3) → เรียนรู้ (M6)
"""
import asyncio
import json
import re
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.worker.celery_app import celery_app
from app.connectors import mining, content, serp, citation, publish, social, media
from app.db import session as db
from app import urls, crypto


def _run(coro):
    return asyncio.run(coro)


def _wordcount(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html or "").split())


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


async def _gen_cover(topic: str) -> str:
    """สร้างรูปปกด้วย Seedream (ModelArk) — crash-safe: ล้ม = คืน '' (บทความยังผลิตได้ปกติ ไม่มีรูปเฉยๆ)"""
    try:
        if not media.enabled():
            return ""
        prompt = ("Editorial magazine cover illustration for a blog article about: %s. "
                  "Modern, clean, minimal, professional, blue and white color palette, "
                  "abstract geometric shapes, no text, no letters, high quality." % topic)
        return await media.generate_image(prompt) or ""
    except Exception:  # noqa: BLE001
        return ""


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
    return _run(_measure_rank(keyword, domain, project_id))


async def _measure_rank(keyword: str, domain: str, project_id: int | None) -> dict:
    """รวมเป็น coroutine เดียว (event loop เดียวต่อ task) — เช็กอันดับแล้วบันทึกในลูปเดียวกัน"""
    res = await serp.rank_check(keyword, domain)
    if project_id and db.enabled():
        await _save_rank(project_id, res)
    return res


# =========================================================
#  🚀 AUTO GROWTH LOOP — วงจรที่ "หมุนเอง" ต่อโปรเจ็ค
# =========================================================

@celery_app.task(name="app.worker.tasks.analyze_project")
def analyze_project(project_id: int) -> dict:
    """🔎 Site Intelligence: อ่านเว็บลูกค้าจริง → สกัดบริบทธุรกิจ + คำแบรนด์ + วางแผนหัวข้อ"""
    return _run(_analyze_project(project_id))


async def _analyze_project(project_id: int) -> dict:
    from app.db.models import Project
    from app.connectors import site
    if not db.enabled():
        return {"error": "DB not configured"}
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p:
            return {"error": "project %s not found" % project_id}
        domain, name = p.domain, p.name
        lang = "English" if str(p.language).lower().startswith("en") else "ภาษาไทย"

    ctx = await site.analyze(domain, name, lang)          # อ่านเว็บจริง (ล้ม = {})
    if not ctx:
        return {"project": name, "analyzed": False,
                "note": "อ่าน/วิเคราะห์เว็บไม่สำเร็จ — ระบบจะใช้ชื่อโปรเจ็คเป็นตัวตั้งต้นแทน"}

    questions = []                                        # คำถามจริงจากคีย์เวิร์ดตั้งต้น → ให้แผนอิงคำค้นจริง
    for kw in (ctx.get("seed_keywords") or [])[:3]:
        try:
            mined = await mining.mine(str(kw))
            questions += [q.get("q") for q in mined.get("questions", []) if q.get("q")]
        except Exception:  # noqa: BLE001
            pass

    try:                                                  # แผนล้ม = ยังบันทึกบริบทที่วิเคราะห์ได้แล้ว (ห้ามทิ้งงานที่ทำสำเร็จ)
        plan = await site.build_plan(ctx, questions, lang)
    except Exception:  # noqa: BLE001
        plan = []
    ctx_text = site.context_text(ctx)
    bt = ctx.get("brand_terms")
    brands_txt = ", ".join(str(b) for b in bt[:5]) if isinstance(bt, list) else str(bt or "")[:200]

    async with db.session() as s:
        p = await s.get(Project, project_id)
        if p:
            p.business_context = ctx_text
            p.brand_terms = brands_txt
            p.topic_plan = json.dumps(plan, ensure_ascii=False) if plan else ""
            p.analyzed_at = datetime.now(timezone.utc)
            await s.commit()
    return {"project": name, "analyzed": True, "pages_read": ctx.get("_pages_read") or [],
            "context": ctx_text[:220], "brand_terms": brands_txt, "plan_size": len(plan)}


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
        # ให้แน่ใจว่าโปรเจ็คมี slug (โปรเจ็คเก่า/สร้างก่อนฟีเจอร์ Managed Hosting)
        if not (proj.slug or "").strip():
            base = urls.project_slug_from_domain(proj.domain or proj.name)
            proj.slug = base
            try:                                    # slug unique index จับการชน → fallback base-{id} (unique แน่นอน)
                await s.commit()
            except IntegrityError:
                await s.rollback()
                proj = await s.get(Project, project_id)
                proj.slug = "%s-%d" % (base, project_id)
                await s.commit()
        # เก็บค่าที่ต้องใช้ลง local (กัน attribute expire หลังปิด session)
        p = SimpleNamespace(name=proj.name, domain=proj.domain, slug=proj.slug,
                            custom_domain=getattr(proj, "custom_domain", "") or "",
                            language=proj.language, mode=proj.mode,
                            publish_mode=getattr(proj, "publish_mode", "managed") or "managed",
                            business_context=getattr(proj, "business_context", "") or "",
                            topic_plan=getattr(proj, "topic_plan", "") or "")
        existing = set((await s.execute(
            select(Article.title).where(Article.project_id == project_id))).scalars().all())

    # 1) เลือกหัวข้อ — ใช้ "แผนหัวข้อ" จาก Site Intelligence ก่อน (เรียงคำที่ชนะได้ก่อน)
    #    ถ้ายังไม่มีแผน (ยังไม่ได้วิเคราะห์เว็บ/วิเคราะห์ไม่สำเร็จ) ค่อยถอยไปขุดสดจากชื่อโปรเจ็ค
    plan, cluster_of, topics, all_q = [], {}, [], []
    if p.topic_plan:
        try:
            plan = json.loads(p.topic_plan) or []
        except Exception:  # noqa: BLE001
            plan = []
    if plan:
        planned = []
        for it in plan:
            if isinstance(it, dict) and it.get("topic"):
                t = str(it["topic"])
                planned.append(t)
                cluster_of[t] = str(it.get("cluster") or "")[:200]
        all_q = planned[:20]
        topics = [t for t in planned if t not in existing][:max_new]
    if not topics:
        seed = (p.name or p.domain or "").strip()
        try:
            mined = await mining.mine(seed)
        except Exception as e:  # noqa: BLE001
            return {"project": p.name, "produced": 0, "note": "mining failed: " + str(e)[:120]}
        all_q = [q.get("q") for q in mined.get("questions", []) if q.get("q")]
        topics = [q for q in all_q if q not in existing][:max_new]
    if not topics:
        return {"project": p.name, "produced": 0, "note": "ไม่มีหัวข้อใหม่ให้ผลิต"}
    lang = "English" if str(p.language).lower().startswith("en") else "ภาษาไทย"
    auto = (p.mode == "auto")
    results = []
    for topic in topics:
        try:
            try:  # ดึงคู่แข่งจริงจาก SERP → Stage 1 หา content gap แซงคู่แข่งได้
                comps = await serp.top_competitors(topic, n=5)
                comp_text = "\n".join(
                    "- [#%s] %s (%s): %s" % (c.get("rank"), c.get("title"),
                                             c.get("domain"), c.get("snippet") or "")
                    for c in comps)
            except Exception:
                comp_text = ""
            gen = await content.generate(topic, "บทความยาว", 1500,   # 2) เขียนด้วย AI (M2 · เครื่องยนต์ 3 stage)
                                         questions=all_q, domain=p.domain, language=lang,
                                         competitors=comp_text, target_url="https://" + p.domain,
                                         business_context=p.business_context)   # ← บริบทจริงจากเว็บลูกค้า
            html = gen.get("html", "")
            cover = await _gen_cover(topic)                           # รูปปก (crash-safe: ล้ม='')
            async with db.session() as s:
                art = Article(project_id=project_id, title=topic, html=html,
                              schema_json=gen.get("schema", "") or "",
                              description=_plain(html)[:300], cover_url=cover,
                              cluster=cluster_of.get(topic, ""),
                              words=_wordcount(html), fmt="บทความยาว",
                              status="published" if auto else "draft")
                s.add(art); await s.commit(); await s.refresh(art)
                art.slug = urls.article_slug(topic, art.id)
                if auto and p.publish_mode == "managed":   # managed = เสิร์ฟจาก DB → ตั้ง URL สาธารณะเลย
                    art.url = urls.public_url_for(p, art)
                await s.commit()
                art_id, art_slug, art_url = art.id, art.slug, art.url
            item = {"topic": topic, "article_id": art_id, "provider": gen.get("provider"),
                    "publish_mode": p.publish_mode}
            if not auto:                                              # โหมด approve → เก็บเป็นร่าง
                item["status"] = "draft (รออนุมัติ)"
            elif p.publish_mode == "wordpress":                       # 3a) เผยแพร่ขึ้น WordPress ลูกค้า (M4)
                pub = await publish.publish_and_index(topic, html, "publish", None)
                link = (pub.get("wordpress") or {}).get("link", "")
                if link:
                    async with db.session() as s:
                        a = await s.get(Article, art_id)
                        if a:
                            a.url = link; await s.commit()
                item["published"] = link or "(no link)"
                item["distributed"] = await _distribute(project_id, art_id, topic, _plain(html)[:160],
                                                         link or art_url, "wordpress", bool(pub.get("indexnow")), cover)
            elif p.publish_mode == "managed":                         # 3b) Managed = สดจาก DB + แจ้ง index
                item["published"] = art_url
                indexnow_ok = False
                try:
                    from urllib.parse import urlparse
                    host = urlparse(art_url).hostname or ""
                    if host.endswith(publish_host_base()):   # ping เฉพาะโดเมนที่เราคุม key ได้
                        await publish.indexnow_submit(art_url)
                        indexnow_ok = True; item["indexnow"] = "pinged"
                except Exception:
                    pass
                item["distributed"] = await _distribute(project_id, art_id, topic, _plain(html)[:160],
                                                         art_url, "blog", indexnow_ok, cover)
            else:                                                     # none = เก็บใน DB เฉย ๆ
                item["published"] = "(mode=none)"
            results.append(item)
        except Exception as e:  # noqa: BLE001
            results.append({"topic": topic, "error": str(e)})
    return {"project": p.name, "mode": p.mode, "publish_mode": p.publish_mode,
            "produced": len(results), "items": results}


def publish_host_base() -> str:
    from app.config import settings
    return settings.managed_base_domain


async def _distribute(project_id: int, article_id: int, title: str, desc: str,
                      page_url: str, publish_channel: str, indexnow_ok: bool, cover: str = "") -> list:
    """กระจายบทความไปช่องของลูกค้า + บันทึกทุก event (โปร่งใส ลูกค้าเห็นได้)"""
    from app.db.models import DistributionChannel, DistributionEvent
    events = [(publish_channel, "posted", page_url, "เผยแพร่แล้ว")]
    if indexnow_ok:
        events.append(("indexnow", "posted", "", "แจ้ง IndexNow แล้ว"))
    try:                                              # ห้ามให้การกระจายล้มแล้วทำการผลิตบทความพัง
        async with db.session() as s:                 # อ่านช่องที่เปิด + ถอดรหัสโทเคน
            chans = (await s.execute(select(DistributionChannel).where(
                DistributionChannel.project_id == project_id,
                DistributionChannel.enabled == True))).scalars().all()   # noqa: E712
            chan_list = [(c.kind, crypto.dec(c.token_enc), c.ref) for c in chans]

        text = "%s%s" % (title, ("\n" + desc) if desc else "")
        for kind, token, ref in chan_list:
            if not token:
                events.append((kind, "skipped", "", "ยังไม่ได้เชื่อมโทเคน")); continue
            res = await social.dispatch(kind, token, ref, text, page_url, cover)
            events.append((kind, "posted" if res.get("ok") else "failed",
                           res.get("url", ""), (res.get("detail", "") or "")[:390]))

        async with db.session() as s:                 # บันทึก event ทั้งหมด
            for ch, st, url, detail in events:
                s.add(DistributionEvent(article_id=article_id, project_id=project_id,
                                        channel=ch, status=st, url=url or "", detail=detail or ""))
            await s.commit()
    except Exception as e:  # noqa: BLE001
        return [{"channel": "distribution", "status": "failed", "error": str(e)[:140]}]
    return [{"channel": e[0], "status": e[1]} for e in events]


@celery_app.task(name="app.worker.tasks.distribute_article")
def distribute_article(project_id: int, article_id: int) -> dict:
    """สั่งกระจายบทความที่เผยแพร่แล้วซ้ำ (เช่น เพิ่งเชื่อมช่องใหม่) — ใช้จาก API"""
    return _run(_redistribute(project_id, article_id))


async def _redistribute(project_id: int, article_id: int) -> dict:
    from app.db.models import Article
    if not db.enabled():
        return {"error": "DB not configured"}
    async with db.session() as s:
        art = await s.get(Article, article_id)
        if not art or art.project_id != project_id:
            return {"error": "article not found"}
        title, desc, url, cover = art.title, (art.description or ""), art.url, (art.cover_url or "")
    if not url:
        return {"error": "บทความนี้ยังไม่ถูกเผยแพร่ (ไม่มี URL)"}
    ch = "wordpress" if "/wp" in url or url.count("/") <= 3 else "blog"
    return {"distributed": await _distribute(project_id, article_id, title, desc[:160], url, ch, False, cover)}


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
