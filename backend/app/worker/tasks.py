"""
งานในคิว (Celery tasks) — เครื่องยนต์ AI Growth Loop ที่ "ทำงานเอง"
แต่ละงานยิง connector จริง (async ผ่าน asyncio.run) และบันทึกผลลง DB
วงจรอัตโนมัติต่อโปรเจ็ค:  ขุดคำถาม (M1) → เขียน (M2) → เผยแพร่+แจ้ง index (M4)
                         → วัดอันดับ (M5) → รีเฟรช (M3) → เรียนรู้ (M6)
"""
import asyncio
import json
import re
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.worker.celery_app import celery_app
from app.connectors import mining, content, serp, citation, publish, social, media, interlink, aeo_score
from app.db import session as db
from app import urls, crypto, creds


def _run(coro):
    return asyncio.run(coro)


def _wordcount(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", html or "").split())


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def _aeo_of(html: str, title: str, desc: str, schema: str, cover: str) -> int:
    """คะแนน AEO/SEO 0-100 จากปัจจัยจัดอันดับที่วัดได้จริง (crash-safe: ล้ม=0)"""
    try:
        return int(aeo_score.score(html, title=title, description=desc[:155],
                                   schema_json=schema, cover_url=cover,
                                   keyword=title, target_words=1200).get("score", 0))
    except Exception:  # noqa: BLE001
        return 0


async def _apply_internal_links(project_id: int, self_title: str, html: str) -> str:
    """M3 · เปลี่ยนลิงก์ภายในลอย (<a href='#'>) ให้ชี้บทความพี่น้องจริง + auto-link ในคลัสเตอร์
    crash-safe: ล้ม = คืน html เดิม (บทความยังผลิตได้) แต่เคสปกติจะไม่มีลิงก์ตายหลุดออกไป"""
    try:
        if not html or not db.enabled():
            return html
        from app.db.models import Article
        async with db.session() as s:
            rows = (await s.execute(
                select(Article.title, Article.url, Article.cluster).where(
                    Article.project_id == project_id, Article.status == "published",
                    Article.url != ""))).all()
        siblings = [{"title": t, "url": u, "cluster": c or ""} for (t, u, c) in rows]
        new_html, _stats = interlink.apply(html, siblings, self_title=self_title)
        return new_html or html
    except Exception:  # noqa: BLE001
        return html


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


def _pick_h2_idxs(n: int) -> list:
    """เลือก H2 ที่จะแทรกรูป (สูงสุด 2 จุด กระจายกลาง ๆ เลี่ยงหัว/ท้าย)"""
    if n <= 0:
        return []
    if n <= 2:
        return [min(1, n - 1)]
    return sorted(set([1, n - 2]))[:2]


async def _enrich_media(html: str, topic: str) -> str:
    """แทรกรูปประกอบในเนื้อบทความ (Seedream) หลัง H2 ที่เลือก — crash-safe: ปิด/ล้ม = คืน html เดิม
    เปิดใช้เมื่อมี ARK_API_KEY (ModelArk) เท่านั้น → คุมต้นทุน"""
    import re as _re
    try:
        if not html or not media.enabled():
            return html
        ms = list(_re.finditer(r"</h2>", html, flags=_re.I))
        if not ms:
            return html
        inserts = []
        for i in _pick_h2_idxs(len(ms)):
            start = html.rfind("<h2", 0, ms[i].start())
            h2text = _re.sub(r"<[^>]+>", "", html[start:ms[i].end()] if start >= 0 else "").strip()[:120] or topic
            try:
                url = await media.generate_image(
                    "Editorial illustration for the section '" + h2text + "' of an article about '" + topic +
                    "'. Modern, clean, minimal, professional, blue and white palette, abstract, no text, no letters.")
            except Exception:  # noqa: BLE001
                url = ""
            if url:
                alt = h2text.replace('"', "'")
                inserts.append((ms[i].end(),
                    '<figure class="inline-img"><img src="' + url + '" alt="' + alt +
                    '" loading="lazy" style="width:100%;border-radius:12px"></figure>'))
        for pos, frag in sorted(inserts, key=lambda z: -z[0]):
            html = html[:pos] + frag + html[pos:]
        return html
    except Exception:  # noqa: BLE001
        return html


async def _hero_video(topic: str) -> str:
    """วิดีโอ hero (Seedance) — ปิดเป็นค่าเริ่มต้น (เปิดเมื่อ operator ตั้ง ARK_VIDEO_MODEL) เพราะช้า+แพง"""
    try:
        from app.config import settings
        if not media.enabled() or not settings.ark_video_model:
            return ""
        return await media.generate_video("Short cinematic b-roll, blue-white minimal aesthetic, about: " + topic) or ""
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
    dfs = await creds.get_creds(project_id, "dataforseo") if (project_id and db.enabled()) else {}
    res = await serp.rank_check(keyword, domain, creds=dfs or None)   # คีย์ลูกค้าก่อน → กลาง
    if project_id and db.enabled():
        await _save_rank(project_id, res)
    return res


# =========================================================
#  🚀 AUTO GROWTH LOOP — วงจรที่ "หมุนเอง" ต่อโปรเจ็ค
# =========================================================

@celery_app.task(name="app.worker.tasks.analyze_project")
def analyze_project(project_id: int, then_produce: bool = True) -> dict:
    """🔎 Site Intelligence: อ่านเว็บลูกค้าจริง → สกัดบริบทธุรกิจ + คำแบรนด์ + วางแผนหัวข้อ
    แล้ว 'ผลิตบทความแรกเองทันที' (ออโตจริง — สร้างโปรเจ็คแล้วมีบทความเลย ไม่ต้องรอ beat/สั่งเอง)"""
    try:
        r = _run(_analyze_project(project_id))
    except Exception as e:  # noqa: BLE001
        r = {"analyzed": False, "error": str(e)[:200]}
    finally:
        # ฝังออโต: ต้องสั่งผลิตเสมอ แม้ analyze จะล่ม (ไม่งั้นโปรเจ็คจะค้างไม่มีบทความ)
        if then_produce:
            try:
                produce_for_project.delay(project_id, 1)
            except Exception:  # noqa: BLE001
                pass
    return r


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
            # ไม่ทับแผนหัวข้อที่ลูกค้าเลือกไว้ตอนสร้าง (คีย์เวิร์ดที่ AI ช่วยคิด/ติ๊กเอง)
            if plan and not (getattr(p, "topic_plan", "") or "").strip():
                p.topic_plan = json.dumps(plan, ensure_ascii=False)
            p.analyzed_at = datetime.now(timezone.utc)
            await s.commit()
    return {"project": name, "analyzed": True, "pages_read": ctx.get("_pages_read") or [],
            "context": ctx_text[:220], "brand_terms": brands_txt, "plan_size": len(plan)}


def _starter_topics(seed: str, lang: str) -> list[str]:
    """หัวข้อตั้งต้นจากชื่อแบรนด์/โดเมน — ใช้เมื่อยังไม่มีแผนหัวข้อ และขุดคีย์เวิร์ดไม่ได้
    (เช่น ไม่มี/คีย์ DataForSEO ใช้ไม่ได้) เพื่อให้ทุกโปรเจ็ค 'เริ่มผลิตได้เสมอ'
    หมายเหตุ: เป็นหัวข้อบทความจริงที่ AI จะเขียนเนื้อหาให้ ไม่ใช่ตัวเลข/ผลลัพธ์ปลอม"""
    seed = (seed or "").strip() or "แบรนด์"
    if lang == "English":
        return [f"What is {seed}? A complete guide",
                f"{seed}: benefits, features and how it works",
                f"How to choose {seed} — a buyer's guide",
                f"{seed} vs the alternatives: which is best?",
                f"{seed} FAQ: everything you need to know"]
    return [f"{seed} คืออะไร? คู่มือฉบับสมบูรณ์",
            f"{seed} ดีอย่างไร จุดเด่นและวิธีใช้งาน",
            f"วิธีเลือก {seed} ให้เหมาะกับคุณ",
            f"{seed} เทียบกับตัวเลือกอื่น แบบไหนดีกว่า",
            f"รวมคำถามที่พบบ่อยเกี่ยวกับ {seed}"]


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
        owner_id = proj.user_id
    if owner_id:                                    # โควตาแพ็กเกจ: กันลูปอัตโนมัติผลิตเกินแพ็กเกจ
        from app import usage
        if not await usage.can_produce_article(owner_id):
            return {"project": proj.name, "produced": 0, "note": "ถึงโควตาบทความของแพ็กเกจเดือนนี้แล้ว"}
    async with db.session() as s:
        proj = await s.get(Project, project_id)
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

    dfs = await creds.get_creds(project_id, "dataforseo")   # คีย์ลูกค้า (per-project) — ว่าง = fallback กลาง
    wp = await creds.get_creds(project_id, "wordpress")

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
    lang = "English" if str(p.language).lower().startswith("en") else "ภาษาไทย"
    if not topics:
        seed = (p.name or p.domain or "").strip()
        all_q = []
        try:
            mined = await mining.mine(seed, creds=dfs or None)
            all_q = [q.get("q") for q in mined.get("questions", []) if q.get("q")]
        except Exception:  # noqa: BLE001
            all_q = []
        if not all_q:                    # ขุดคีย์เวิร์ดไม่ได้ (ไม่มี/คีย์ DataForSEO ใช้ไม่ได้) → หัวข้อตั้งต้นจากแบรนด์เอง (ผลิตได้เสมอ)
            all_q = _starter_topics(seed, lang)
        topics = [q for q in all_q if q not in existing][:max_new]
    if not topics:
        return {"project": p.name, "produced": 0, "note": "ไม่มีหัวข้อใหม่ให้ผลิต"}
    auto = (p.mode == "auto")
    results = []
    for topic in topics:
        try:
            try:  # ดึงคู่แข่งจริงจาก SERP → Stage 1 หา content gap แซงคู่แข่งได้
                comps = await serp.top_competitors(topic, n=5, creds=dfs or None)
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
            html = await _apply_internal_links(project_id, topic, html)  # ลิงก์ภายในจริง (M3) — ห้ามปล่อยลิงก์ตาย
            html = await _enrich_media(html, topic)                   # แทรกรูปในเนื้อ (ถ้าเปิด ModelArk)
            cover = await _gen_cover(topic)                           # รูปปก (crash-safe: ล้ม='')
            video = await _hero_video(topic)                          # วิดีโอ hero (ถ้าตั้ง ARK_VIDEO_MODEL)
            if video:
                html = ('<figure class="hero-video"><video src="' + video +
                        '" controls preload="metadata" playsinline style="width:100%;border-radius:12px"></video></figure>') + html
            schema = gen.get("schema", "") or ""
            desc = _plain(html)[:300]
            aeo = _aeo_of(html, topic, desc, schema, cover)          # คะแนน AEO/SEO จริง (ตัวแปรจัดอันดับ)
            async with db.session() as s:
                art = Article(project_id=project_id, title=topic, html=html,
                              schema_json=schema,
                              description=desc, cover_url=cover,
                              cluster=cluster_of.get(topic, ""),
                              aeo_score=aeo,
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
                pub = await publish.publish_and_index(topic, html, "publish", None, creds=wp or None)
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
    written = [r for r in results if r.get("article_id")]   # นับเฉพาะบทความที่เขียนลง DB จริง (ไม่โม้)
    out = {"project": p.name, "mode": p.mode, "publish_mode": p.publish_mode,
           "produced": len(written), "attempted": len(results), "items": results}
    if not written and results:                            # ผลิตไม่ได้เลย → บอกเหตุผลจริง (มักคือคีย์ AI)
        out["note"] = "เขียนบทความไม่สำเร็จ: " + str(results[0].get("error") or "")[:160]
    return out


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


@celery_app.task(name="app.worker.tasks.approve_article")
def approve_article(article_id: int) -> dict:
    """M4 · อนุมัติบทความ draft → เผยแพร่จริง (managed/wordpress) + แจ้ง index + กระจาย"""
    return _run(_approve_article(article_id))


async def _approve_article(article_id: int) -> dict:
    from app.db.models import Article, Project
    if not db.enabled():
        return {"error": "DB not configured"}
    async with db.session() as s:
        art = await s.get(Article, article_id)
        if not art:
            return {"error": "article not found"}
        proj = await s.get(Project, art.project_id)
        if not proj:
            return {"error": "project not found"}
        if art.status == "published":
            return {"article_id": article_id, "already": True, "url": art.url}
        # เก็บค่าที่ต้องใช้ (กัน attribute expire หลังปิด session)
        project_id = proj.id
        publish_mode = getattr(proj, "publish_mode", "managed") or "managed"
        pj = SimpleNamespace(name=proj.name, domain=proj.domain, slug=proj.slug,
                             custom_domain=getattr(proj, "custom_domain", "") or "")
        title, html = art.title, art.html or ""
        desc, cover = (art.description or ""), (art.cover_url or "")
        if not (art.slug or "").strip():
            art.slug = urls.article_slug(title, art.id)
        art.status = "published"
        if publish_mode == "managed":
            art.url = urls.public_url_for(pj, art)
        await s.commit()
        art_url, art_slug = art.url, art.slug

    wp = await creds.get_creds(project_id, "wordpress")
    result = {"article_id": article_id, "publish_mode": publish_mode}
    if publish_mode == "wordpress":                       # เผยแพร่ขึ้น WordPress ลูกค้า
        pub = await publish.publish_and_index(title, html, "publish", None, creds=wp or None)
        link = (pub.get("wordpress") or {}).get("link", "")
        if link:
            async with db.session() as s:
                a = await s.get(Article, article_id)
                if a:
                    a.url = link
                    await s.commit()
            art_url = link
        result["published"] = link or "(no link)"
        result["distributed"] = await _distribute(project_id, article_id, title, _plain(html)[:160],
                                                   link or art_url, "wordpress", bool(pub.get("indexnow")), cover)
    elif publish_mode == "managed":                       # Managed = สดจาก DB + แจ้ง index
        indexnow_ok = False
        try:
            from urllib.parse import urlparse
            host = urlparse(art_url).hostname or ""
            if host.endswith(publish_host_base()):
                await publish.indexnow_submit(art_url)
                indexnow_ok = True
        except Exception:  # noqa: BLE001
            pass
        result["published"] = art_url
        result["distributed"] = await _distribute(project_id, article_id, title, _plain(html)[:160],
                                                   art_url, "blog", indexnow_ok, cover)
    else:
        result["published"] = "(mode=none)"
    return result


@celery_app.task(name="app.worker.tasks.optimize_article")
def optimize_article(article_id: int, min_score: int = 85) -> dict:
    """🔧 ป้อนจุดอ่อนจาก AEO Score กลับให้เครื่องยนต์เขียนซ่อม → ดันคะแนน (บันทึกเฉพาะเมื่อดีขึ้น)"""
    return _run(_optimize_article(article_id, min_score))


def _score_art(art, proj) -> dict:
    age = None
    if getattr(art, "updated_at", None):
        try:
            age = (datetime.now(timezone.utc) - art.updated_at).days
        except Exception:  # noqa: BLE001
            age = None
    return aeo_score.score(art.html or "", title=art.title or "",
                           description=(art.description or "")[:155],
                           schema_json=art.schema_json or "", cover_url=art.cover_url or "",
                           keyword=art.title or "", target_words=1200, age_days=age,
                           freshness_days=getattr(proj, "freshness_days", 120) or 120)


async def _optimize_article(article_id: int, min_score: int) -> dict:
    from app.db.models import Article, Project
    if not db.enabled():
        return {"error": "DB not configured"}
    async with db.session() as s:
        art = await s.get(Article, article_id)
        if not art:
            return {"error": "article not found"}
        proj = await s.get(Project, art.project_id)
        title, html, schema = art.title, art.html or "", art.schema_json or ""
        project_id = art.project_id
        lang = "English" if str(getattr(proj, "language", "th")).lower().startswith("en") else "ภาษาไทย"
        before = _score_art(art, proj)

    if before["score"] >= min_score or not before["top_fixes"]:
        return {"article_id": article_id, "optimized": False, "score": before["score"],
                "note": "คะแนนถึงเกณฑ์แล้ว/ไม่มีจุดต้องแก้"}

    weaknesses = "\n".join("- %s — %s" % (f["label"], f.get("fix", "")) for f in before["top_fixes"])
    try:
        imp = await content.improve(html, title, weaknesses, language=lang)
    except Exception as e:  # noqa: BLE001
        return {"article_id": article_id, "optimized": False, "error": str(e)[:160]}
    if not imp.get("changed"):
        return {"article_id": article_id, "optimized": False, "note": "เครื่องยนต์ซ่อมไม่สำเร็จ"}

    new_html = await _apply_internal_links(project_id, title, imp["html"])   # คงลิงก์ภายในให้จริง
    new_schema = imp.get("schema") or schema
    new_desc = _plain(new_html)[:300]
    after = aeo_score.score(new_html, title=title, description=new_desc[:155],
                            schema_json=new_schema, cover_url=getattr(art, "cover_url", "") or "",
                            keyword=title, target_words=1200)

    if after["score"] <= before["score"]:                # ห้าม regress — เก็บของเดิมถ้าไม่ดีขึ้น
        return {"article_id": article_id, "optimized": False,
                "score_before": before["score"], "score_after": after["score"],
                "note": "ผลใหม่ไม่ดีกว่าเดิม — คงบทความเดิมไว้"}

    async with db.session() as s:
        a = await s.get(Article, article_id)
        if a:
            a.html = new_html
            a.schema_json = new_schema
            a.description = new_desc
            a.words = _wordcount(new_html)
            a.aeo_score = after["score"]
            a.updated_at = datetime.now(timezone.utc)          # bump dateModified (สดขึ้นด้วย)
            await s.commit()
    return {"article_id": article_id, "optimized": True,
            "score_before": before["score"], "score_after": after["score"],
            "gain": after["score"] - before["score"]}


@celery_app.task(name="app.worker.tasks.optimize_low_scores")
def optimize_low_scores(threshold: int = 80, per_project: int = 2) -> str:
    """beat: ไล่ซ่อมบทความคะแนนต่ำสุดของแต่ละโปรเจ็ค (auto-tuning ดันอันดับต่อเนื่อง)"""
    return _run(_optimize_low_scores(threshold, per_project))


async def _optimize_low_scores(threshold: int, per_project: int) -> str:
    from app.db.models import Project, Article
    if not db.enabled():
        return "DB not configured"
    n = 0
    async with db.session() as s:
        pids = (await s.execute(select(Project.id))).scalars().all()
        for pid in pids:
            rows = (await s.execute(
                select(Article.id).where(Article.project_id == pid,
                                         Article.status == "published",
                                         Article.aeo_score < threshold)
                .order_by(Article.aeo_score.asc()).limit(per_project))).scalars().all()
            for aid in rows:
                optimize_article.delay(aid)
                n += 1
    return "queued optimize for %d low-scoring articles" % n


@celery_app.task(name="app.worker.tasks.boost_rankings")
def boost_rankings(lo: int = 11, hi: int = 40, per_project: int = 4) -> str:
    """⚡ คันเร่งอันดับ: ดันหน้า 'จ่อหน้า 1 (อันดับ 11-40)' หรือ 'เคยติดหน้า 1 แล้วหลุด'
    ให้เข้าคิว optimize ซ่อม (เติมเนื้อ/ลิงก์ใน/สดขึ้น) → ดันขึ้นหน้า 1 หรือดึงกลับ · ใช้ข้อมูลอันดับจริง"""
    return _run(_boost_rankings(lo, hi, per_project))


async def _boost_rankings(lo: int, hi: int, per_project: int) -> str:
    from app.db.models import Project, Article, RankSnapshot
    if not db.enabled():
        return "DB not configured"
    n = 0
    async with db.session() as s:
        pids = (await s.execute(select(Project.id))).scalars().all()
        for pid in pids:
            snaps = (await s.execute(
                select(RankSnapshot.keyword, RankSnapshot.rank, RankSnapshot.on_page1)
                .where(RankSnapshot.project_id == pid)
                .order_by(RankSnapshot.checked_at))).all()
            latest, ever_p1 = {}, {}
            for kw, rank, op in snaps:                        # ไล่จากเก่า→ใหม่ → latest ได้ค่าล่าสุด
                latest[kw] = (rank, bool(op))
                ever_p1[kw] = ever_p1.get(kw, False) or bool(op)
            targets = []
            for kw, (rank, op) in latest.items():
                if op:                                        # ติดหน้า 1 อยู่แล้ว = ไม่ต้องดัน
                    continue
                striking = (rank is not None and lo <= rank <= hi)   # จ่อหน้า 1
                dropped = ever_p1.get(kw, False)                     # เคยหน้า 1 แล้วหลุด
                if striking or dropped:
                    targets.append(kw)
            for kw in targets[:per_project]:
                aid = (await s.execute(
                    select(Article.id).where(Article.project_id == pid, Article.title == kw,
                                             Article.status == "published").limit(1))).scalar()
                if aid:
                    optimize_article.delay(aid)
                    n += 1
    return "queued rank-boost for %d pages (striking %d-%d / dropped off page1)" % (n, lo, hi)


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


def _available_engines() -> list[str]:
    """เอนจินที่ตั้งคีย์แล้วเท่านั้น (ไม่มีคีย์ = ไม่ยิง = ไม่เดาผล)"""
    from app.config import settings
    engs = []
    if settings.openai_api_key:
        engs.append("openai")
    if settings.gemini_api_key:
        engs.append("gemini")
    if settings.perplexity_api_key:
        engs.append("perplexity")
    if settings.anthropic_api_key:
        engs.append("anthropic")
    return engs


def _brand_terms_of(p) -> list[str]:
    """คำแบรนด์จากที่ Site Intelligence สกัดไว้ (คั่นด้วย ,) → fallback ชื่อ+โดเมน
    (ไม่งั้นบัญชีจริงที่ยังไม่ตั้งคำแบรนด์จะได้ SoV=0 เสมอ)"""
    terms = [t.strip() for t in (getattr(p, "brand_terms", "") or "").split(",") if t.strip()]
    if terms:
        return terms[:8]
    out = []
    if p.name:
        out.append(str(p.name).strip())
    if p.domain:
        dom = str(p.domain).strip()
        out.append(dom)
        label = dom.replace("www.", "").split(".")[0]
        if label and label not in out:
            out.append(label)
    return [t for t in out if t]


async def _project_questions(p, project_id: int, limit: int = 6) -> list[str]:
    """ชุดคำถามสำหรับสุ่มถาม AI — เอาจากแผนหัวข้อ (Site Intelligence) ก่อน
    แล้วค่อยถอยไปหัวข้อบทความที่เผยแพร่จริง แล้วสุดท้ายขุดสดจากชื่อโปรเจ็ค"""
    from app.db.models import Article
    qs: list[str] = []
    if getattr(p, "topic_plan", ""):
        try:
            for it in (json.loads(p.topic_plan) or []):
                if isinstance(it, dict) and it.get("topic"):
                    qs.append(str(it["topic"]))
        except Exception:  # noqa: BLE001
            pass
    if len(qs) < limit and db.enabled():
        async with db.session() as s:
            titles = (await s.execute(
                select(Article.title).where(Article.project_id == project_id,
                                            Article.status == "published")
                .order_by(Article.id.desc()).limit(limit))).scalars().all()
        qs += [t for t in titles if t]
    if not qs:
        try:
            mined = await mining.mine((p.name or p.domain or "").strip())
            qs = [q.get("q") for q in mined.get("questions", []) if q.get("q")]
        except Exception:  # noqa: BLE001
            qs = []
    # กันซ้ำ คงลำดับ
    seen, out = set(), []
    for q in qs:
        k = q.strip().lower()
        if q.strip() and k not in seen:
            seen.add(k); out.append(q.strip())
    return out[:limit]


async def _sample_and_save(project_id: int, questions: list[str] | None = None) -> dict:
    """รัน Prompt Sampling จริงต่อโปรเจ็ค แล้ว 'บันทึกผลลง DB' (CitationSnapshot)
    → นี่คือสิ่งที่ทำให้ 'แนวโน้ม Share of Voice' สะสมได้จริง (ไม่ใช่ยิงแล้วทิ้ง)"""
    from app.db.models import Project, CitationSnapshot
    if not db.enabled():
        return {"error": "DB not configured"}
    engines = _available_engines()
    if not engines:
        return {"error": "ยังไม่ได้ตั้งคีย์ AI สำหรับ Prompt Sampling (OpenAI/Gemini/Perplexity)"}
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p:
            return {"error": "project %s not found" % project_id}
        domain = p.domain
        brand_terms = _brand_terms_of(p)
        qs = [q for q in (questions or []) if q and q.strip()]
        if not qs:
            qs = await _project_questions(p, project_id)
    if not qs:
        return {"project": domain, "saved": False, "note": "ยังไม่มีชุดคำถามให้สุ่มถาม"}

    res = await citation.sample(qs, brand_terms, domain, engines)

    per = res.get("per_engine") or {}
    async with db.session() as s:                    # บันทึก snapshot ต่อเอนจิน (ตรวจสอบย้อนได้)
        for eng, v in per.items():
            s.add(CitationSnapshot(project_id=project_id, engine=eng,
                                   sov_percent=v.get("sov_percent"),
                                   answered=v.get("answered") or 0,
                                   cited=v.get("cited") or 0))
        await s.commit()
    res["saved"] = bool(per)
    res["engines_used"] = engines
    res["questions_used"] = len(qs)
    return res


@celery_app.task(name="app.worker.tasks.sample_citations_for_project")
def sample_citations_for_project(project_id: int) -> dict:
    return _run(_sample_and_save(project_id))


@celery_app.task(name="app.worker.tasks.sample_all_citations")
def sample_all_citations() -> str:
    """M5 (beat): สุ่มถาม AI ให้ทุกโปรเจ็ค แล้วบันทึก Share of Voice (สะสมเป็นแนวโน้ม)"""
    return _run(_sample_all_citations())


async def _sample_all_citations() -> str:
    from app.db.models import Project
    if not db.enabled():
        return "DB not configured"
    if not _available_engines():
        return "no AI keys configured — skip prompt sampling"
    async with db.session() as s:
        ids = (await s.execute(select(Project.id))).scalars().all()
    for pid in ids:
        sample_citations_for_project.delay(pid)
    return "queued prompt sampling for %d projects" % len(ids)


@celery_app.task(name="app.worker.tasks.freshness_sweep")
def freshness_sweep() -> str:
    """M3: หาบทความที่เก่าเกิน freshness_days แล้วเข้าคิวผลิตใหม่/รีเฟรช"""
    return _run(_freshness_sweep())


async def _freshness_sweep() -> str:
    """หาบทความที่ 'เก่าเกิน freshness_days จริง' (จาก updated_at) แล้วสั่งเขียนซ่อม/รีเฟรช
    (optimize จะรีไรต์ + bump updated_at = สดขึ้นจริง) — ไม่มีของเก่า ค่อยผลิตใหม่คงความสดคลัสเตอร์"""
    from app.db.models import Project, Article
    if not db.enabled():
        return "DB not configured"
    now = datetime.now(timezone.utc)
    refreshed, produced = 0, 0
    async with db.session() as s:
        projs = (await s.execute(select(Project))).scalars().all()
        plan = []
        for p in projs:
            fd = getattr(p, "freshness_days", 120) or 120
            cutoff = now - timedelta(days=fd)
            stale = (await s.execute(
                select(Article.id).where(Article.project_id == p.id,
                                         Article.status == "published",
                                         Article.updated_at < cutoff)
                .order_by(Article.updated_at.asc()).limit(3))).scalars().all()
            plan.append((p.id, list(stale)))
    for pid, stale in plan:
        if stale:
            for aid in stale:
                optimize_article.delay(aid)     # รีเฟรชของเก่าจริง (รีไรต์ + updated_at ใหม่)
                refreshed += 1
        else:
            produce_for_project.delay(pid, 1)   # ทุกหน้ายังสด → ขยายคลัสเตอร์
            produced += 1
    return "freshness: refreshed %d aging articles, queued %d new" % (refreshed, produced)


# =========================================================
#  M6 — LEARNING LOOP: เรียนรู้จาก 'ผลจริง' ว่าอะไรทำให้ติด/ถูกอ้าง แล้วปรับกลยุทธ์
# =========================================================

async def _project_insights(project_id: int, proj=None) -> dict:
    """วิเคราะห์จากข้อมูลจริง: คะแนน AEO ต่อบทความ + อันดับจริง (RankSnapshot) →
    หา 'ปัจจัยร่วมของหน้าที่ได้ผล', คลัสเตอร์ที่แข็ง, และปัจจัยที่อ่อนสุดของทั้งโปรเจ็ค"""
    from app.db.models import Project, Article, RankSnapshot
    async with db.session() as s:
        if proj is None:
            proj = await s.get(Project, project_id)
        arts = (await s.execute(
            select(Article).where(Article.project_id == project_id).limit(100))).scalars().all()
        ranks = (await s.execute(
            select(RankSnapshot).where(RankSnapshot.project_id == project_id)
            .order_by(RankSnapshot.checked_at))).scalars().all()
    if not proj:
        return {"count": 0, "insights": [], "clusters": [], "note": "ไม่พบโปรเจ็ค"}

    page1 = {}                                   # อันดับล่าสุดต่อคีย์เวิร์ด(=หัวข้อ)
    for r in ranks:
        page1[r.keyword] = bool(r.on_page1)

    scored, labels = [], {}
    for a in arts:
        r = _score_art(a, proj)
        labels.update({f["key"]: f["label"] for f in r["factors"]})
        scored.append({"title": a.title, "cluster": (a.cluster or "").strip(),
                       "score": r["score"], "grade": r["grade"],
                       "factors": {f["key"]: f["ok"] for f in r["factors"]},
                       "on_page1": page1.get(a.title)})
    n = len(scored)
    if not n:
        return {"count": 0, "insights": [], "clusters": [],
                "note": "ยังไม่มีบทความให้เรียนรู้ — ผลิตบทความก่อน"}

    avg_score = round(sum(x["score"] for x in scored) / n)
    winners = [x for x in scored if x["on_page1"] or x["score"] >= 80]
    losers = [x for x in scored if x not in winners]
    p1_count = sum(1 for x in scored if x["on_page1"])

    insights = []
    if winners and losers:
        wa = round(sum(x["score"] for x in winners) / len(winners))
        la = round(sum(x["score"] for x in losers) / len(losers))
        if wa > la:
            insights.append({"type": "score_gap",
                             "text": "หน้าที่ได้ผลมีคะแนน AEO เฉลี่ย %d เทียบกับ %d ของหน้าที่ยังไม่ติด — ดันคะแนนหน้าอ่อนคือทางลัด" % (wa, la)})
    # ปัจจัยร่วมของหน้าที่ได้ผล (ผ่านในกลุ่ม winner มากกว่ากลุ่ม loser ชัด)
    if winners:
        diffs = []
        for k, lab in labels.items():
            wp = sum(1 for x in winners if x["factors"].get(k)) / len(winners)
            lp = (sum(1 for x in losers if x["factors"].get(k)) / len(losers)) if losers else 0
            if wp - lp >= 0.25:
                diffs.append((wp - lp, lab, round(wp * 100), round(lp * 100)))
        diffs.sort(reverse=True)
        for _d, lab, wp, lp in diffs[:3]:
            insights.append({"type": "winning_factor",
                             "text": "หน้าที่ได้ผลมักมี '%s' (%d%% เทียบ %d%% ของหน้าอื่น)" % (lab, wp, lp)})
    # ปัจจัยที่อ่อนสุดทั้งโปรเจ็ค (ผ่านน้อยสุด) → แก้แล้วดันได้ทั้งกลุ่ม
    weak = sorted(labels.keys(), key=lambda k: sum(1 for x in scored if x["factors"].get(k)))
    if weak:
        k = weak[0]
        pct = round(sum(1 for x in scored if x["factors"].get(k)) / n * 100)
        insights.append({"type": "weak_factor",
                         "text": "ปัจจัยที่อ่อนสุดคือ '%s' (ผ่านแค่ %d%% ของบทความ) — โฟกัสแก้ตัวนี้ก่อน" % (labels[k], pct)})

    # คลัสเตอร์ที่แข็งสุด (คะแนนเฉลี่ย + ติดหน้า 1)
    cl = {}
    for x in scored:
        c = x["cluster"] or "ไม่ระบุคลัสเตอร์"
        g = cl.setdefault(c, {"cluster": c, "n": 0, "score_sum": 0, "page1": 0})
        g["n"] += 1; g["score_sum"] += x["score"]; g["page1"] += 1 if x["on_page1"] else 0
    clusters = sorted(
        ({"cluster": g["cluster"], "articles": g["n"],
          "avg_score": round(g["score_sum"] / g["n"]), "page1": g["page1"]} for g in cl.values()),
        key=lambda c: (c["page1"], c["avg_score"]), reverse=True)
    if clusters and clusters[0]["cluster"] != "ไม่ระบุคลัสเตอร์":
        b = clusters[0]
        insights.append({"type": "best_cluster",
                         "text": "คลัสเตอร์ที่แข็งสุด: '%s' (คะแนนเฉลี่ย %d, ติดหน้า 1 %d หน้า) — ควรขยายคลัสเตอร์นี้ต่อ" % (b["cluster"], b["avg_score"], b["page1"])})

    return {"count": n, "avg_score": avg_score, "page1": p1_count,
            "winners": len(winners), "insights": insights, "clusters": clusters[:6],
            "note": "สรุปจากผลจริง (คะแนน AEO + อันดับที่เก็บได้) — ไม่ใช่คำแนะนำสำเร็จรูป"}


async def _reprioritize_plan(project_id: int, clusters: list):
    """ปรับลำดับ topic_plan: ดันหัวข้อในคลัสเตอร์ที่ 'พิสูจน์แล้วว่าได้ผล' ขึ้นก่อน (auto-tuning จริง)"""
    from app.db.models import Project
    winning = [c["cluster"] for c in clusters if c["page1"] > 0 or c["avg_score"] >= 80]
    if not winning:
        return False
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or not (p.topic_plan or "").strip():
            return False
        try:
            plan = json.loads(p.topic_plan) or []
        except Exception:  # noqa: BLE001
            return False
        if not isinstance(plan, list) or not plan:
            return False
        wset = set(winning)
        plan.sort(key=lambda it: 0 if isinstance(it, dict) and str(it.get("cluster") or "") in wset else 1)
        p.topic_plan = json.dumps(plan, ensure_ascii=False)
        await s.commit()
    return True


async def _compose_report(user) -> str | None:
    """ประกอบรายงานรายสัปดาห์ 'จากผลจริง' ต่อผู้ใช้ (คะแนน AEO + อันดับ + ข้อค้นพบ)
    คืน None ถ้ายังไม่มีข้อมูลพอ (ไม่ส่งอีเมลว่างเปล่า)"""
    from app.db.models import Project
    async with db.session() as s:
        projs = (await s.execute(select(Project).where(Project.user_id == user.id))).scalars().all()
    if not projs:
        return None
    blocks = []
    for p in projs:
        ins = await _project_insights(p.id, p)
        if not ins.get("count"):
            continue
        items = "".join("<li>%s</li>" % _esc(i.get("text", "")) for i in ins.get("insights", [])[:4])
        blocks.append(
            "<div style='margin:0 0 22px;padding:16px;border:1px solid #e7ecf6;border-radius:12px'>"
            "<div style='font-weight:800;font-size:16px'>%s</div>"
            "<div style='color:#5a6a86;font-size:14px;margin:4px 0 8px'>บทความ %d · คะแนน AEO เฉลี่ย %s · ติดหน้า 1 %d คีย์เวิร์ด</div>"
            "<ul style='margin:0;padding-left:18px;font-size:14px'>%s</ul></div>"
            % (_esc(p.name or p.domain), ins["count"],
               ins.get("avg_score", "—"), ins.get("page1", 0), items or "<li>กำลังสะสมข้อมูลเพิ่ม</li>"))
    if not blocks:
        return None
    return ("<div style='font-family:Sarabun,Segoe UI,sans-serif;max-width:640px;margin:auto'>"
            "<h2 style='color:#12299e'>รายงานรายสัปดาห์ · ImVisible</h2>"
            "<p style='color:#5a6a86'>สรุปจากผลจริงของเว็บคุณ (คะแนน AEO + อันดับ + ข้อค้นพบ)</p>"
            + "".join(blocks) +
            "<p style='color:#889;font-size:12px'>— ระบบ AEO ของ ImVisible · imvisible.tech</p></div>")


def _esc(t) -> str:
    import html as _h
    return _h.escape(str(t or ""))


@celery_app.task(name="app.worker.tasks.publish_scheduled")
def publish_scheduled() -> str:
    """M4 (beat): เผยแพร่บทความที่ 'ถึงเวลาที่ตั้งไว้' (status=scheduled + scheduled_at<=now)"""
    return _run(_publish_scheduled())


async def _publish_scheduled() -> str:
    from app.db.models import Article
    if not db.enabled():
        return "DB not configured"
    now = datetime.now(timezone.utc)
    async with db.session() as s:
        rows = (await s.execute(
            select(Article.id, Article.scheduled_at).where(
                Article.status == "scheduled", Article.scheduled_at.isnot(None)))).all()
    due = []
    for aid, sat in rows:
        if not sat:
            continue
        if sat.tzinfo is None:              # sqlite อาจคืน naive → ถือเป็น UTC
            sat = sat.replace(tzinfo=timezone.utc)
        if sat <= now:
            due.append(aid)
    for aid in due:
        approve_article.delay(aid)          # ใช้เส้นทางเผยแพร่จริงเดียวกับการอนุมัติ
    return "published %d scheduled articles" % len(due)


@celery_app.task(name="app.worker.tasks.send_weekly_reports")
def send_weekly_reports() -> str:
    """M6 (beat): ส่งรายงานรายสัปดาห์จากผลจริงให้ผู้ใช้ทุกคนทางอีเมล"""
    return _run(_send_weekly_reports())


async def _send_weekly_reports() -> str:
    from app.db.models import User
    from app.connectors import notify
    if not db.enabled():
        return "DB not configured"
    if not notify.email_enabled():
        return "email (SMTP) not configured — skip weekly reports"
    async with db.session() as s:
        users = (await s.execute(select(User))).scalars().all()
    sent = 0
    for u in users:
        try:
            html = await _compose_report(u)
            if html and await notify.send_email(u.email, "รายงานรายสัปดาห์ · ImVisible", html):
                sent += 1
        except Exception:  # noqa: BLE001 — ผู้ใช้คนเดียวล้ม ไม่ให้ทั้งชุดพัง
            continue
    return "sent %d weekly reports" % sent


@celery_app.task(name="app.worker.tasks.learning_loop")
def learning_loop() -> str:
    """M6: เรียนรู้จากผลจริงของทุกโปรเจ็ค → ปรับลำดับหัวข้อให้คลัสเตอร์ที่ได้ผลมาก่อน"""
    return _run(_learning_loop())


async def _learning_loop() -> str:
    from app.db.models import Project
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        ids = (await s.execute(select(Project.id))).scalars().all()
    tuned, total_insights = 0, 0
    for pid in ids:
        try:
            ins = await _project_insights(pid)
            total_insights += len(ins.get("insights", []))
            if await _reprioritize_plan(pid, ins.get("clusters", [])):
                tuned += 1
        except Exception:  # noqa: BLE001
            continue
    return "learning loop: analyzed %d projects, %d insights, re-prioritized %d plans" % (
        len(ids), total_insights, tuned)


async def _save_rank(project_id: int, res: dict):
    from app.db.models import RankSnapshot
    async with db.session() as s:
        s.add(RankSnapshot(project_id=project_id, keyword=res.get("keyword", ""),
                           rank=res.get("our_rank"), on_page1=bool(res.get("on_page1"))))
        await s.commit()
