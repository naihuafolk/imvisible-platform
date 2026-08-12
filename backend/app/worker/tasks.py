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
from app import urls, crypto, creds, plans


def _run(coro):
    return asyncio.run(coro)


def _pack_cap(p) -> int:
    """เพดานคีย์เวิร์ดของโปรเจ็ค = แพ็กของลูกค้า (10/30/50) · ค่าเริ่มต้น 50 (โปรเจ็คเดิม)"""
    return plans.normalize_pack(getattr(p, "keyword_pack", plans.DEFAULT_PACK))


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


async def _visual_concept(topic: str, section: str = "") -> str:
    """แปลงหัวข้อ (อาจเป็นไทย) → คำบรรยาย 'ฉากภาพจริง' สั้น ๆ เป็นภาษาอังกฤษ ที่สื่อถึงเนื้อหา
    → ป้อนให้ fal.ai (เข้าใจอังกฤษดีกว่าไทย) ได้ภาพที่ 'ตรงเรื่อง' ไม่ใช่นามธรรมมั่ว · crash-safe"""
    try:
        sysmsg = ("You are the photo editor at a premium magazine choosing a cover shot. "
                  "Turn an article topic into ONE vivid ENGLISH description of a single striking, real-life PHOTOGRAPH "
                  "that makes a reader stop scrolling. Choose a concrete focal subject — a real person mid-action, "
                  "a specific place, or a hero product/object — in a specific setting, with specific lighting, time of day and mood. "
                  "Think authentic editorial/documentary photography with real human warmth and a clear story. "
                  "Avoid cliches: NO generic 'person at a laptop', no charts/graphs/dashboards, no abstract concepts, "
                  "no floating icons or holograms, no glowing blue tech backgrounds. Keep it grounded and real. "
                  "The photo must contain NO text. Reply with ONLY the scene — one rich, specific sentence, no quotes, no preface.")
        usermsg = ("Article topic: %s%s\nThe single most beautiful, on-topic REAL photograph to use as the cover:"
                   % (topic, (" · section: " + section) if section else ""))
        _p, txt = await content._llm(sysmsg, usermsg, tier="fast")
        return (txt or "").strip().strip('"').replace("\n", " ")[:320]
    except Exception:  # noqa: BLE001
        return ""


async def _gen_cover(topic: str) -> str:
    """สร้างรูปปกที่ 'สื่อถึงเนื้อหา' — แปลงหัวข้อเป็นฉากอังกฤษก่อน แล้วเจนภาพสมจริง · crash-safe (ล้ม='')"""
    try:
        if not media.enabled():
            return ""
        scene = (await _visual_concept(topic)) or ("a scene that represents: " + topic)
        prompt = ("Editorial magazine cover photograph. Scene: %s. "
                  "Authentic documentary/editorial style shot on a full-frame camera with a 35mm lens, "
                  "natural and cinematic lighting, photorealistic with lifelike skin, textures and true-to-life color, "
                  "shallow depth of field, elegant rule-of-thirds composition, sharp focus on the subject, "
                  "high dynamic range, rich fine detail, 4K. "
                  "It must look like a REAL photograph — not an illustration, not a 3D render, not CGI, not a flat stock photo. "
                  "Absolutely no text, no letters, no words, no numbers, no logos, no watermark, no signature, no UI." % scene)
        return await media.generate_image(prompt) or ""
    except Exception:  # noqa: BLE001
        return ""


async def _gen_magnet_cover(topic: str, kind: str = "guide") -> str:
    """รูปปกสื่อแจกฟรี — สไตล์ 'ปกอีบุ๊ก/คอร์ส' ดึงดูดสายตาที่สุด (ใช้เป็น OG image ตอนแชร์ด้วย) · crash-safe"""
    try:
        if not media.enabled():
            return ""
        label = {"course": "online course", "guide": "guide / ebook",
                 "checklist": "checklist", "template": "template"}.get(kind, "guide / ebook")
        scene = (await _visual_concept(topic)) or ("a scene representing: " + topic)
        prompt = ("Striking, share-worthy cover for a free %s. Scene: %s. "
                  "Premium modern design — photorealistic hero photography or a polished 3D render, a strong focal subject, "
                  "cinematic lighting, rich depth, vibrant yet tasteful, high contrast, scroll-stopping, magazine-quality 4K. "
                  "Award-winning art direction, ultra-detailed. "
                  "Absolutely no text, no letters, no words, no numbers, no logos, no watermark, no signature, no UI." % (label, scene))
        return await media.generate_image(prompt) or ""
    except Exception:  # noqa: BLE001
        return ""


def _pick_h2_idxs(n: int) -> list:
    """เลือก H2 ที่จะแทรกรูป (กระจายกลาง ๆ เลี่ยงหัว/ท้าย) — บทความยาวใส่ได้ถึง 3 จุด"""
    if n <= 0:
        return []
    if n <= 2:
        return [min(1, n - 1)]
    if n <= 4:
        return sorted(set([1, n - 2]))[:2]
    return sorted(set([1, n // 2, n - 2]))[:3]


async def _enrich_media(html: str, topic: str) -> str:
    """แทรกรูปประกอบในเนื้อบทความ (Seedream) หลัง H2 ที่เลือก — crash-safe: ปิด/ล้ม = คืน html เดิม
    เปิดใช้เมื่อมี ARK_API_KEY (ModelArk) เท่านั้น → คุมต้นทุน"""
    import re as _re
    import asyncio as _aio
    try:
        if not html or not media.enabled():
            return html
        ms = list(_re.finditer(r"</h2>", html, flags=_re.I))
        if not ms:
            return html

        async def _one(i):                       # สร้างรูปแต่ละใบ (จะรันพร้อมกันด้วย gather → เร็ว)
            start = html.rfind("<h2", 0, ms[i].start())
            h2text = _re.sub(r"<[^>]+>", "", html[start:ms[i].end()] if start >= 0 else "").strip()[:120] or topic
            try:
                _scene = (await _visual_concept(topic, h2text)) or (h2text + " — related to " + topic)
                url = await media.generate_image(
                    "Photorealistic professional photo. Scene: " + _scene +
                    ". Real-world relevant, high-end editorial photography or clean 3D render, "
                    "natural lighting, shallow depth of field, modern, beautiful, ultra-detailed 4K. "
                    "No text, no letters, no words, no logos, no watermark, no UI.")
            except Exception:  # noqa: BLE001
                url = ""
            if not url:
                return None
            alt = h2text.replace('"', "'")
            return (ms[i].end(),
                    '<figure class="inline-img"><img src="' + url + '" alt="' + alt +
                    '" loading="lazy" style="width:100%;border-radius:12px"></figure>')
        res = await _aio.gather(*[_one(i) for i in _pick_h2_idxs(len(ms))])
        for pos, frag in sorted([x for x in res if x], key=lambda z: -z[0]):
            html = html[:pos] + frag + html[pos:]
        return html
    except Exception:  # noqa: BLE001
        return html


def _render_infographic(spec: dict) -> str:
    """เรนเดอร์ 'ภาพสรุป' เป็น HTML block (สไตล์อยู่ใน public.py _CSS) — escape ทุก field กัน XSS"""
    import html as _h
    def e(x): return _h.escape(str(x or ""))
    t = spec.get("type"); items = spec.get("items") or []
    head = '<div class="ig-h">%s</div>' % e(spec.get("title") or "ภาพสรุป")
    if t == "steps":
        body = '<div class="ig-steps">%s</div>' % "".join(
            '<div class="ig-step"><span class="ig-n">%d</span><div><b>%s</b>%s</div></div>'
            % (i + 1, e(it.get("title")), ('<span>%s</span>' % e(it.get("detail"))) if it.get("detail") else "")
            for i, it in enumerate(items))
    elif t == "compare":
        rows = "".join(
            '<div class="ig-row"><span class="ig-lab">%s</span><span>%s</span><span>%s</span></div>'
            % (e(it.get("label")), e(it.get("left")), e(it.get("right"))) for it in items)
        body = ('<div class="ig-compare"><div class="ig-row ig-head"><span class="ig-lab"></span>'
                '<span>%s</span><span>%s</span></div>%s</div>'
                % (e(spec.get("leftHead") or "A"), e(spec.get("rightHead") or "B"), rows))
    else:  # points
        body = '<div class="ig-points">%s</div>' % "".join(
            '<div class="ig-pt"><span class="ig-dot"></span><div><b>%s</b>%s</div></div>'
            % (e(it.get("title")), ('<span>%s</span>' % e(it.get("detail"))) if it.get("detail") else "")
            for it in items)
    return '<aside class="infographic" aria-label="ภาพสรุป">%s%s</aside>' % (head, body)


def _insert_infographic(html: str, block: str) -> str:
    """วาง block ภาพสรุปหลังย่อหน้าแรก (answer-first) — ให้อยู่สูง อ่านง่าย + AEO ดี"""
    if not block:
        return html
    import re as _re
    m = _re.search(r"</p>", html or "", _re.I)
    return (html[:m.end()] + block + html[m.end():]) if m else (block + (html or ""))


async def _infographic_html(html: str, topic: str, lang: str) -> str:
    """คืน HTML ภาพสรุป (หรือ '' ถ้าไม่มีอะไรเหมาะ) — จากเนื้อบทความจริง ไม่ปั้นเลข · crash-safe"""
    try:
        spec = await content.infographic_spec(_plain(html), topic, lang)
        return _render_infographic(spec) if spec else ""
    except Exception:  # noqa: BLE001
        return ""


def _render_trend_chart(data: dict) -> str:
    """เรนเดอร์กราฟแท่งเทรนด์การค้นหา 'จริง' (SVG) — ตัวเลขจาก DataForSEO ทั้งหมด (ไม่ปั้นเลข)"""
    import html as _h
    monthly = data.get("monthly") or []
    vals = [int(m.get("v") or 0) for m in monthly]
    if not vals:
        return ""
    kw = _h.escape(str(data.get("keyword") or ""))
    vol = data.get("volume")
    src = _h.escape(str(data.get("source") or "DataForSEO"))
    mx = max(vals) or 1
    n = len(vals); W = 520; H = 150; gap = 7
    bw = (W - gap * (n - 1)) / n
    mth = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    def _ml(m): mi = m.get("m") or 0; return (mth[mi] if 0 <= mi <= 12 else "") + " " + str(m.get("y") or "")
    bars = []
    for i, m in enumerate(monthly):
        v = int(m.get("v") or 0)
        bh = max(2.0, (v / mx) * (H - 8)); x = i * (bw + gap); y = H - bh
        mi = m.get("m") or 0
        lbl = ((mth[mi] if 0 <= mi <= 12 else "") + " {:,}".format(v)).strip()
        bars.append('<rect class="tc-bar" x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3"><title>%s</title></rect>'
                    % (x, y, bw, bh, _h.escape(lbl)))
    svg = ('<svg viewBox="0 0 %d %d" style="width:100%%;height:auto" role="img" aria-label="กราฟเทรนด์การค้นหา">%s</svg>'
           % (W, H, "".join(bars)))
    avg = "{:,}".format(int(vol)) if isinstance(vol, (int, float)) else _h.escape(str(vol))
    rng = _h.escape((_ml(monthly[0]) + "–" + _ml(monthly[-1])).strip())
    return ('<figure class="trend-chart"><div class="tc-h">ความสนใจการค้นหา “%s” · 12 เดือน</div>%s'
            '<figcaption class="tc-cap">เฉลี่ย ~%s ครั้ง/เดือน · %s · ที่มา: %s</figcaption></figure>'
            % (kw, svg, avg, rng, src))


def _insert_trend(html: str, block: str) -> str:
    """วางกราฟเทรนด์ก่อนหัวข้อที่ 2 (กลางเนื้อ) — ถ้า h2 < 2 ต่อท้าย"""
    if not block:
        return html
    import re as _re
    ms = list(_re.finditer(r"<h2", html or "", _re.I))
    if len(ms) >= 2:
        pos = ms[1].start()
        return html[:pos] + block + html[pos:]
    return (html or "") + block


async def _trend_chart_html(keyword: str, creds) -> str:
    """กราฟเทรนด์การค้นหาจริง (DataForSEO) — เปิดเมื่อ settings.trend_chart=true · crash-safe → ''"""
    try:
        from app.config import settings as _cfg
        if not getattr(_cfg, "trend_chart", False):
            return ""
        data = await serp.keyword_volume(keyword, creds=creds or None)
        return _render_trend_chart(data) if (data and data.get("monthly")) else ""
    except Exception:  # noqa: BLE001
        return ""


async def _hero_video(topic: str) -> str:
    """วิดีโอ hero — ปิดเป็นค่าเริ่มต้น (เปิดเมื่อ operator ตั้ง FAL_VIDEO_MODEL หรือ ARK_VIDEO_MODEL) เพราะช้า+แพง"""
    try:
        from app.config import settings
        if not media.enabled() or not (settings.fal_video_model or settings.ark_video_model):
            return ""
        return await media.generate_video("Short cinematic b-roll, blue-white minimal aesthetic, about: " + topic) or ""
    except Exception:  # noqa: BLE001
        return ""


async def _lead_magnet_video(topic: str, kind: str = "course") -> str:
    """วิดีโอ hero สำหรับ 'คอร์ส/คู่มือ' — ใช้โมเดลวิดีโอที่ดีที่สุด (fal Kling) · เปิดด้วย LEAD_MAGNET_VIDEO
    แยกจากวิดีโอบทความ เพื่อไม่ให้ทุกบทความช้า · เฉพาะสื่อชิ้นใหญ่ (course/guide) · crash-safe: ล้ม = คืน ''"""
    try:
        from app.config import settings
        if kind not in ("course", "guide"):                # เช็คลิสต์/เทมเพลตไม่ต้องมีวิดีโอ
            return ""
        if not (getattr(settings, "lead_magnet_video", False) and media.enabled() and settings.fal_key):
            return ""
        model = getattr(settings, "lead_magnet_video_model", "") or settings.fal_video_model
        if not model:
            return ""
        scene = await _visual_concept(topic, "hero")          # แปลหัวข้อไทย → ซีนภาษาอังกฤษ (โมเดลเข้าใจดีกว่า)
        prompt = ("Short cinematic educational b-roll, clean modern learning/course aesthetic, "
                  "soft depth of field, professional: " + (scene or topic))
        print("[lead-magnet video] generating via %s …" % model)
        url = await media.generate_video(prompt, ratio="16:9", duration=5, model=model) or ""
        print("[lead-magnet video] %s" % ("ok" if url else "empty result"))
        return url
    except Exception as e:  # noqa: BLE001 — โชว์เหตุผลใน worker log เพื่อ debug (เช่น Kling ยังไม่เปิดสิทธิ์/เครดิตหมด)
        print("[lead-magnet video] failed: %s" % str(e)[:200])
        return ""


async def _google_index(url: str):
    """แจ้ง Google Indexing API (crash-safe) — เก็บ connector ไว้ 'เฉพาะ' เคสที่ Google รองรับจริง:
    หน้า JobPosting (ประกาศงาน) / BroadcastEvent (ไลฟ์สด) เท่านั้น
    ⚠️ ห้ามเรียกกับบล็อก/บทความทั่วไป — Google ถือเป็นการใช้ผิด (สแปม) · เว็บบล็อกใช้ IndexNow + sitemap + internal link แทน"""
    try:
        from app.connectors import indexing
        if url and indexing.enabled():
            await indexing.submit(url)
    except Exception:  # noqa: BLE001
        pass


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
                assess_easy_wins.delay(project_id, 8)   # ⚡ ประเมิน Easy-Win ก่อน → รอบผลิตถัดไปหยิบคีย์ง่ายก่อน
            except Exception:  # noqa: BLE001
                pass
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
    try:                                                  # 🌱 seed คำถาม AEO 'recommendation-intent' → วัด AI Citation ได้มีความหมาย (แก้/ลบเองได้)
        aeo_qs = await content.suggest_aeo_questions(name, domain, ctx_text, lang, n=8)
    except Exception:  # noqa: BLE001
        aeo_qs = []

    async with db.session() as s:
        p = await s.get(Project, project_id)
        if p:
            # ไม่ทับบริบท/คำแบรนด์ที่ 'ป้อนมาตอน onboard' (เช่น เว็บที่สร้างจาก IM WEB carry brief เข้ามา)
            # — เขียนเฉพาะตอนยังว่าง เพื่อไม่ให้ analyze ของเว็บที่ไม่มี URL จริงมาล้างข้อมูลดี ๆ ทิ้ง
            if ctx_text and not (getattr(p, "business_context", "") or "").strip():
                p.business_context = ctx_text
            if brands_txt and not (getattr(p, "brand_terms", "") or "").strip():
                p.brand_terms = brands_txt
            # ไม่ทับแผนหัวข้อที่ลูกค้าเลือกไว้ตอนสร้าง (คีย์เวิร์ดที่ AI ช่วยคิด/ติ๊กเอง)
            if plan and not (getattr(p, "topic_plan", "") or "").strip():
                p.topic_plan = json.dumps(plan, ensure_ascii=False)
            if aeo_qs and not (getattr(p, "aeo_questions", "") or "").strip():   # ไม่ทับคำถามที่ลูกค้าตั้งเอง
                p.aeo_questions = json.dumps(aeo_qs, ensure_ascii=False)
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


# YMYL (Your Money Your Life) — แพทย์/สุขภาพ/การเงิน/กฎหมาย: ห้าม auto-publish เด็ดขาด (ต้องคนรีวิว)
# กัน Google Scaled-Content-Abuse + ความรับผิดของลูกค้า (เช่น คลินิก/เวชสำอาง/สินเชื่อ)
_YMYL_TERMS = (
    "คลินิก", "ศัลยกรรม", "ความงาม", "ผิวหนัง", "ทันตกรรม", "การแพทย์", "แพทย์", "เวชสำอาง",
    "ฟิลเลอร์", "โบท็อก", "รักษาโรค", "อาหารเสริม", "วิตามิน", "ยารักษา",
    "สินเชื่อ", "เงินกู้", "กู้เงิน", "ลงทุน", "คริปโต", "ประกันชีวิต", "ประกันภัย",
    "กฎหมาย", "ทนายความ", "คดีความ",
    "clinic", "medical", "cosmetic surgery", "dermatolog", "dental", "pharmacy", "supplement",
    "finance", "loan", "invest", "insurance", "lawyer", "legal advice",
)


def _is_ymyl(text: str) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in _YMYL_TERMS)


@celery_app.task(name="app.worker.tasks.produce_for_project")
def produce_for_project(project_id: int, max_new: int = 1) -> dict:
    """1 โปรเจ็ค: ขุดคำถาม → เลือกหัวข้อใหม่ (กันซ้ำ) → เขียนด้วย AI →
    ถ้าโหมด auto เผยแพร่+แจ้ง index / ถ้า approve เก็บเป็นร่างรออนุมัติ → บันทึก DB"""
    return _run(_produce_for_project(project_id, max_new))


def _order_easy_cluster(topics: list[str], cluster_of: dict, diff_of: dict, launch: bool) -> list[str]:
    """⚡ จัดลำดับหัวข้อผลิตให้ 'ติดไวขึ้น':
    - launch (บทความยังน้อย): จัดเป็นคลัสเตอร์ เลือกคลัสเตอร์ใหญ่สุดก่อน (สร้างอำนาจหัวข้อ = Cluster-First) ภายในคลัสเตอร์ 'ง่ายก่อน'
    - steady: เรียง 'ง่ายก่อน' ทั่วทั้งแผน (Easy-Win = คีย์คู่แข่งอ่อน ติดเร็ว ได้โมเมนตัมก่อน)"""
    if not topics:
        return topics
    if launch:
        groups: dict[str, list[str]] = {}
        for t in topics:
            groups.setdefault((cluster_of.get(t) or "_"), []).append(t)
        order = sorted(groups.keys(), key=lambda c: (c == "_", -len(groups[c])))   # คลัสเตอร์ใหญ่ก่อน (ว่างไปท้าย)
        out: list[str] = []
        for c in order:
            out.extend(sorted(groups[c], key=lambda t: diff_of.get(t, 50)))         # ภายในคลัสเตอร์ ง่ายก่อน
        return out
    return sorted(topics, key=lambda t: diff_of.get(t, 50))


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
        from app import usage, plans
        _allowed = plans.limits(await usage.user_plan(owner_id))["articles_month"]
        _remaining = max(0, _allowed - await usage.articles_this_month(owner_id))
        if _remaining <= 0:
            return {"project": proj.name, "produced": 0, "note": "ถึงโควตาบทความของแพ็กเกจเดือนนี้แล้ว"}
        max_new = min(max_new, _remaining)          # กันผลิตเกินโควตาเมื่อ batch>1 (เช่น grow_clusters)
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
        planned, diff_of = [], {}
        for it in plan:
            if isinstance(it, dict) and it.get("topic"):
                t = str(it["topic"])
                planned.append(t)
                cluster_of[t] = str(it.get("cluster") or "")[:200]
                diff_of[t] = it.get("difficulty") if it.get("difficulty") is not None else 50
        all_q = planned[:20]
        unproduced = [t for t in planned if t not in existing]
        # ⚡ Easy-Win + Cluster-First: เปิดตัว (<6 บทความ) จัดเป็นคลัสเตอร์สร้างอำนาจหัวข้อ · จากนั้นเรียง 'ง่ายก่อน'
        unproduced = _order_easy_cluster(unproduced, cluster_of, diff_of, launch=(len(existing) < 6))
        topics = unproduced[:max_new]
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
    # YMYL: ธุรกิจแพทย์/สุขภาพ/การเงิน/กฎหมาย → บังคับเข้าคิวรีวิวคนเสมอ (แม้ตั้งโหมด auto)
    ymyl_project = _is_ymyl((p.business_context or "") + " " + (p.name or "") + " " + (p.domain or ""))
    from app.config import settings as _cfg
    min_score = int(getattr(_cfg, "min_publish_score", 82) or 82)   # ประตูคุณภาพ: ต่ำกว่านี้ = ไม่เผยแพร่ (เก็บร่าง + ปรับก่อน)
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
            import asyncio as _aio
            html_i, cover, video, ig_block, tc_block = await _aio.gather(   # ⚡ รูปในเนื้อ+ปก+วิดีโอ+ภาพสรุป+กราฟเทรนด์ 'พร้อมกัน'
                _enrich_media(html, topic),                            #   แทรกรูปในเนื้อ (ถ้าเปิด fal/ModelArk)
                _gen_cover(topic),                                     #   รูปปก (crash-safe: ล้ม='')
                _hero_video(topic),                                    #   วิดีโอ hero (ถ้าตั้ง fal/ARK video)
                _infographic_html(html, topic, lang),                  #   ภาพสรุป (จากเนื้อบทความจริง ไม่ปั้นเลข)
                _trend_chart_html(topic, dfs))                         #   กราฟเทรนด์ค้นหาจริง (เปิดเมื่อ trend_chart=true)
            html = _insert_infographic(html_i, ig_block)               #   วางภาพสรุปหลังย่อหน้าแรก
            html = _insert_trend(html, tc_block)                       #   วางกราฟเทรนด์กลางเนื้อ
            if video:
                html = ('<figure class="hero-video"><video src="' + video +
                        '" controls preload="metadata" playsinline style="width:100%;border-radius:12px"></video></figure>') + html
            schema = gen.get("schema", "") or ""
            desc = _plain(html)[:300]
            aeo = _aeo_of(html, topic, desc, schema, cover)          # คะแนน AEO/SEO จริง (ตัวแปรจัดอันดับ)
            ymyl = ymyl_project or _is_ymyl(topic)                   # หัวข้อ YMYL แม้ธุรกิจทั่วไป ก็ต้องรีวิวก่อน
            publish_now = auto and (aeo >= min_score) and not ymyl   # ⭐ พรีเมียม + ไม่ใช่ YMYL ถึงเผยแพร่อัตโนมัติ (กันบทความห่วย/เสี่ยงหลุด)
            async with db.session() as s:
                art = Article(project_id=project_id, title=topic, html=html,
                              schema_json=schema,
                              description=desc, cover_url=cover,
                              cluster=cluster_of.get(topic, ""),
                              aeo_score=aeo,
                              words=_wordcount(html), fmt="บทความยาว",
                              status="published" if publish_now else "draft")
                s.add(art); await s.commit(); await s.refresh(art)
                art.slug = urls.article_slug(topic, art.id)
                if publish_now and p.publish_mode == "managed":   # managed = เสิร์ฟจาก DB → ตั้ง URL สาธารณะเลย
                    art.url = urls.public_url_for(p, art)
                await s.commit()
                art_id, art_slug, art_url = art.id, art.slug, art.url
            item = {"topic": topic, "article_id": art_id, "provider": gen.get("provider"),
                    "publish_mode": p.publish_mode, "aeo": aeo}
            if not publish_now:
                if auto:                                              # ออโต้แต่คะแนนยังไม่ถึงพรีเมียม → เก็บร่าง + สั่งปรับให้ถึงเกณฑ์ก่อน
                    item["status"] = "draft (AEO %d < %d — กำลังปรับให้ถึงพรีเมียมก่อนเผยแพร่)" % (aeo, min_score)
                    try:
                        optimize_article.delay(art_id)
                    except Exception:  # noqa: BLE001
                        pass
                else:                                                 # โหมด approve → เก็บเป็นร่างรออนุมัติ
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
def optimize_article(article_id: int, min_score: int = 85, deep: bool = False) -> dict:
    """🔧 ป้อนจุดอ่อนจาก AEO Score กลับให้เครื่องยนต์เขียนซ่อม → ดันคะแนน (บันทึกเฉพาะเมื่อดีขึ้น)
    deep=True (escalate เมื่ออันดับนิ่ง): เขียนมุมใหม่/เติมของสดแม้คะแนนสูงแล้ว + bump dateModified"""
    return _run(_optimize_article(article_id, min_score, deep))


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


async def _optimize_article(article_id: int, min_score: int, deep: bool = False) -> dict:
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

    if not deep and (before["score"] >= min_score or not before["top_fixes"]):
        return {"article_id": article_id, "optimized": False, "score": before["score"],
                "note": "คะแนนถึงเกณฑ์แล้ว/ไม่มีจุดต้องแก้"}

    if before["top_fixes"]:
        weaknesses = "\n".join("- %s — %s" % (f["label"], f.get("fix", "")) for f in before["top_fixes"])
    else:   # deep escalate + ไม่มีจุดอ่อนชัด → สั่งยกระดับมุมใหม่/ของสด (สำหรับหน้าที่อันดับนิ่ง)
        weaknesses = ("ยกระดับให้เหนือคู่แข่ง: เพิ่มมุมมอง/ตัวอย่าง/ข้อมูลใหม่ที่ยังไม่มีในบทความ, "
                      "เพิ่มหัวข้อย่อย + คำถาม FAQ ที่ผู้ค้นหาถามจริง, อัปเดตข้อมูลให้ทันสมัยปีปัจจุบัน, "
                      "กระชับส่วนยืดเยื้อ และเสริมความน่าเชื่อ (ข้อมูล/แหล่งอ้างอิง)")
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

    # ปกติ: ต้องดีขึ้นถึงเก็บ · deep(อันดับนิ่ง): เก็บได้ถ้าไม่แย่ลงเกิน 3 แต้ม (ยอมคะแนนคงที่เพื่อ 'มุมใหม่+สดใหม่')
    min_keep = before["score"] - 3 if deep else before["score"]
    if after["score"] <= min_keep:                       # ห้าม regress — เก็บของเดิมถ้าไม่ดีขึ้น/แย่ลง
        return {"article_id": article_id, "optimized": False,
                "score_before": before["score"], "score_after": after["score"],
                "note": "ผลใหม่ไม่ดีกว่าเดิม — คงบทความเดิมไว้"}

    was_draft = False
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
            was_draft = (a.status == "draft")
    # ปิดลูปคุณภาพ: ร่างที่ปรับจนคะแนนถึงเกณฑ์พรีเมียมแล้ว + โปรเจ็คโหมด auto → เผยแพร่อัตโนมัติ
    promoted = False
    from app.config import settings as _cfg
    if was_draft and after["score"] >= int(getattr(_cfg, "min_publish_score", 82) or 82):
        from app.db.models import Project
        async with db.session() as s:
            pr = await s.get(Project, project_id)
            promoted = bool(pr and pr.mode == "auto")
        if promoted:
            try:
                approve_article.delay(article_id)
            except Exception:  # noqa: BLE001
                pass
    return {"article_id": article_id, "optimized": True, "promoted": promoted,
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
        projs = (await s.execute(select(Project.id, Project.mode))).all()
        for pid, mode in projs:
            # โหมด auto: ซ่อม 'ร่างที่คะแนนยังไม่ถึงเกณฑ์' ด้วย → พอถึงเกณฑ์จะเผยแพร่เอง (กันร่างค้างถาวร)
            statuses = ["published", "draft"] if mode == "auto" else ["published"]
            rows = (await s.execute(
                select(Article.id).where(Article.project_id == pid,
                                         Article.status.in_(statuses),
                                         Article.aeo_score < threshold)
                .order_by(Article.aeo_score.asc()).limit(per_project))).scalars().all()
            for aid in rows:
                optimize_article.delay(aid)
                n += 1
    return "queued optimize for %d low-scoring articles" % n


async def _find_article_for_keyword(s, pid: int, kw: str):
    """หา 'บทความที่ตรงคีย์เวิร์ดที่สุด' ของโปรเจ็ค — แก้บั๊กเดิมที่ใช้ title==kw เป๊ะ
    (ทำให้คีย์เวิร์ดลูกค้าที่ไม่ใช่ชื่อบทความเป๊ะ ถูกข้ามไม่เคยถูกดันเลย)
    ลำดับ: (1) ชื่อตรงเป๊ะ (2) ชื่อ/คีย์ เป็น substring ของกัน (3) คำในคีย์อยู่ในชื่อ ≥ ครึ่ง
    รองรับไทย (ไม่มีเว้นวรรคระหว่างคำ) ด้วยการเช็ก substring ทีละก้อนคีย์"""
    from app.db.models import Article
    kw = (kw or "").strip()
    if not kw:
        return None
    aid = (await s.execute(select(Article.id).where(
        Article.project_id == pid, Article.title == kw, Article.status == "published").limit(1))).scalar()
    if aid:
        return aid
    rows = (await s.execute(select(Article.id, Article.title).where(
        Article.project_id == pid, Article.status == "published"))).all()
    kwl = kw.lower()
    chunks = [w for w in kwl.replace(",", " ").split() if len(w) > 1]
    best, best_score = None, 0.0
    for aid, title in rows:
        tl = (title or "").lower()
        if not tl:
            continue
        if kwl in tl or tl in kwl:                     # substring = ตรงพอ ใช้เลย (ครอบคลุมไทย)
            return aid
        if chunks:
            hit = sum(1 for w in chunks if w in tl) / len(chunks)   # สัดส่วนก้อนคีย์ที่อยู่ในชื่อ
            if hit > best_score:
                best_score, best = hit, aid
    return best if best_score >= 0.5 else None


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
        pids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
        for pid in pids:
            snaps = (await s.execute(
                select(RankSnapshot.keyword, RankSnapshot.rank, RankSnapshot.on_page1)
                .where(RankSnapshot.project_id == pid)
                .order_by(RankSnapshot.checked_at))).all()
            latest, ever_p1, history = {}, {}, {}
            for kw, rank, op in snaps:                        # ไล่จากเก่า→ใหม่ → latest ได้ค่าล่าสุด
                latest[kw] = (rank, bool(op))
                ever_p1[kw] = ever_p1.get(kw, False) or bool(op)
                if rank is not None:
                    history.setdefault(kw, []).append(rank)
            # ⚡ #2 Striking-Distance Sniper: จัดคิวตัว 'จ่อหน้า 1 ที่สุด' ก่อน (#11-20 มาก่อน #21-40)
            #    ใช้แรง optimize ให้คุ้มสุด → ดันขึ้นหน้า 1 เร็ว (ROI สูงกว่าไล่สุ่ม)
            scored = []
            for kw, (rank, op) in latest.items():
                if op:                                        # ติดหน้า 1 อยู่แล้ว = ไม่ต้องดัน
                    continue
                if rank is not None and lo <= rank <= hi:     # จ่อหน้า 1 — ใกล้สุดก่อน (#11-20 เป็น tier 0)
                    scored.append((0 if rank <= 20 else 1, rank, kw))
                elif ever_p1.get(kw, False):                  # เคยหน้า 1 แล้วหลุด — ดึงกลับ (tier 2)
                    scored.append((2, 999, kw))
            scored.sort(key=lambda x: (x[0], x[1]))
            targets = [kw for _pri, _r, kw in scored]
            for kw in targets[:per_project]:
                aid = await _find_article_for_keyword(s, pid, kw)   # จับคู่ยืดหยุ่น (ไม่ใช่ชื่อตรงเป๊ะ)
                if aid:
                    h = history.get(kw, [])
                    # อันดับนิ่ง = วัดแล้ว ≥4 รอบ แต่ 3 รอบล่าสุดไม่ขยับดีขึ้นเลย → escalate (deep rewrite มุมใหม่)
                    stalled = len(h) >= 4 and min(h[-3:]) >= h[-4]
                    optimize_article.delay(aid, 85, stalled)
                    n += 1
    return "queued rank-boost for %d pages (striking %d-%d / dropped off page1)" % (n, lo, hi)


def _striking_keywords(snaps, lo: int = 11, hi: int = 30) -> list:
    """คีย์ 'จ่อหน้า 1' (#lo-hi ยังไม่ติดหน้า 1) เรียงใกล้ติดสุดก่อน — จาก RankSnapshot rows (asc by time)"""
    latest = {}
    for kw, rank, op in snaps:
        latest[kw] = (rank, bool(op))
    striking = [(rank, kw) for kw, (rank, op) in latest.items()
                if (not op) and rank is not None and lo <= rank <= hi]
    striking.sort(key=lambda x: x[0])
    return [kw for _r, kw in striking]


@celery_app.task(name="app.worker.tasks.paa_boost")
def paa_boost(per_project: int = 3) -> str:
    """⚡ PAA Sniper: ดึง 'People Also Ask' จริงจาก Google ของคีย์ 'จ่อหน้า 1 (#11-30)'
    → เติมเป็น FAQ ตรงคำถามที่ Google โชว์ → คว้า featured snippet / PAA box / AI citation
    ข้อมูลจริงจาก SERP (ไม่ปั้นคำถาม) · ต้องต่อ DataForSEO"""
    return _run(_paa_boost(per_project))


async def _paa_boost(per_project: int) -> str:
    from app.db.models import Project, Article, RankSnapshot
    if not db.enabled():
        return "DB not configured"
    n = 0
    async with db.session() as s:
        pids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
    for pid in pids:
        async with db.session() as s:
            snaps = (await s.execute(
                select(RankSnapshot.keyword, RankSnapshot.rank, RankSnapshot.on_page1)
                .where(RankSnapshot.project_id == pid).order_by(RankSnapshot.checked_at))).all()
        targets = _striking_keywords(snaps)
        if not targets:
            continue
        dfs = await creds.get_creds(pid, "dataforseo")
        for kw in targets[:per_project]:
            try:
                pr = await mining.paa_related(kw, creds=dfs or None)
                paa = [q.strip() for q in (pr.get("paa") or []) if q and q.strip()][:8]
            except Exception:  # noqa: BLE001
                paa = []
            if not paa:
                continue
            async with db.session() as s:
                aid = await _find_article_for_keyword(s, pid, kw)   # จับคู่ยืดหยุ่น (ไม่ใช่ชื่อตรงเป๊ะ)
                art = (await s.get(Article, aid)) if aid else None
                if not art:
                    continue
                proj = await s.get(Project, pid)
                aid, title = art.id, art.title
                html, schema = art.html or "", art.schema_json or ""
                cover = getattr(art, "cover_url", "") or ""
                lang = "English" if str(getattr(proj, "language", "th")).lower().startswith("en") else "ภาษาไทย"
            new_qs = [q for q in paa if q.lower()[:18] not in html.lower()]   # คำถามที่ยังไม่มีในบทความ
            if not new_qs:
                continue
            weaknesses = ("เพิ่ม/เสริมหัวข้อ 'คำถามที่พบบ่อย' ด้วยคำถามจริงที่ Google แสดง (People Also Ask) เหล่านี้ "
                          "พร้อมคำตอบตรงประเด็น self-contained 40-60 คำต่อข้อ (ใช้เฉพาะข้อมูลจริง ห้ามแต่งตัวเลข):\n"
                          + "\n".join("- " + q for q in new_qs[:6]))
            try:
                imp = await content.improve(html, title, weaknesses, language=lang)
            except Exception:  # noqa: BLE001
                continue
            if not imp.get("changed"):
                continue
            new_html = await _apply_internal_links(pid, title, imp["html"])
            if len(new_html) < len(html) * 0.9:              # กัน regress (เนื้อหด = ทิ้ง)
                continue
            new_schema = imp.get("schema") or schema
            new_desc = _plain(new_html)[:300]
            after = aeo_score.score(new_html, title=title, description=new_desc[:155],
                                    schema_json=new_schema, cover_url=cover, keyword=title, target_words=1200)
            async with db.session() as s:
                a = await s.get(Article, aid)
                if a:
                    a.html = new_html; a.schema_json = new_schema; a.description = new_desc
                    a.words = _wordcount(new_html); a.aeo_score = after["score"]
                    a.updated_at = datetime.now(timezone.utc)
                    await s.commit(); n += 1
    return "PAA-enriched %d striking articles" % n


def _find_linkable(html: str, phrase: str) -> int:
    """หาตำแหน่งวลีในเนื้อ (อยู่ใน <p> · ไม่อยู่ในแท็ก/ลิงก์เดิม) ที่ปลอดภัยจะแทรกลิงก์ · -1 = ไม่พบ"""
    low = html.lower(); p = phrase.lower()
    if len(p) < 6:                                          # สั้นไปเสี่ยงลิงก์มั่ว
        return -1
    start = 0
    while True:
        i = low.find(p, start)
        if i < 0:
            return -1
        in_p = low.rfind("<p", 0, i) > low.rfind("</p>", 0, i)
        in_anchor = (low.count("<a ", 0, i) + low.count("<a>", 0, i)) > low.count("</a>", 0, i)
        in_tag = html.rfind("<", 0, i) > html.rfind(">", 0, i)
        if in_p and not in_anchor and not in_tag:
            return i
        start = i + len(p)


@celery_app.task(name="app.worker.tasks.link_push")
def link_push(per_project: int = 4, links_each: int = 3) -> str:
    """⚡ Internal-Link Power Push: อัดลิงก์ภายในจากบทความอื่น → หน้า 'จ่อหน้า 1 (#11-30)'
    (แทรกที่วลีคีย์เวิร์ดปรากฏจริงในย่อหน้า) → โฟกัสพลังลิงก์ที่หน้าใกล้ติด = ดันขึ้นหน้า 1 ไว · ฟรี (ไม่ยิง API)"""
    return _run(_link_push_striking(per_project, links_each))


async def _link_push_striking(per_project: int, links_each: int) -> str:
    from app.db.models import Project, Article, RankSnapshot
    import html as _h
    if not db.enabled():
        return "DB not configured"
    n = 0
    async with db.session() as s:
        pids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
    for pid in pids:
        async with db.session() as s:
            snaps = (await s.execute(
                select(RankSnapshot.keyword, RankSnapshot.rank, RankSnapshot.on_page1)
                .where(RankSnapshot.project_id == pid).order_by(RankSnapshot.checked_at))).all()
        targets = _striking_keywords(snaps)
        if not targets:
            continue
        for kw in targets[:per_project]:
            async with db.session() as s:
                aid = await _find_article_for_keyword(s, pid, kw)   # จับคู่ยืดหยุ่น (ไม่ใช่ชื่อตรงเป๊ะ)
                target = (await s.get(Article, aid)) if aid else None
                if not target or not (target.url or "").strip():
                    continue
                turl = target.url
                others = (await s.execute(select(Article).where(
                    Article.project_id == pid, Article.status == "published",
                    Article.id != target.id))).scalars().all()
                added = 0
                for o in others:
                    if added >= links_each:
                        break
                    oh = o.html or ""
                    if not oh or turl in oh:                 # ลิงก์ไปเป้าหมายอยู่แล้ว → ข้าม (idempotent)
                        continue
                    idx = _find_linkable(oh, kw)
                    if idx < 0:
                        continue
                    anchor = '<a href="%s">%s</a>' % (_h.escape(turl), _h.escape(kw))
                    o.html = oh[:idx] + anchor + oh[idx + len(kw):]
                    added += 1; n += 1
                if added:
                    await s.commit()
    return "power-pushed %d internal links to striking pages" % n


@celery_app.task(name="app.worker.tasks.assess_easy_wins")
def assess_easy_wins(project_id: int = 0, cap: int = 8) -> str:
    """⚡ #1 Easy-Win Radar: ประเมิน 'ความยากในการติดอันดับ' ของคีย์เวิร์ดในแผน จากหน้า SERP จริง
    → ติดแท็ก difficulty ลง topic_plan ให้รอบผลิตหยิบ 'คีย์ที่ชนะง่าย' มาทำก่อน = ติดไวขึ้นมาก"""
    return _run(_assess_easy_wins(project_id, cap))


async def _assess_easy_wins(project_id: int, cap: int) -> str:
    from app.db.models import Project
    from app.connectors import serp
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        ids = [project_id] if project_id else \
            (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
    scored = 0
    for pid in ids:
        async with db.session() as s:
            p = await s.get(Project, pid)
            if not p or not (p.topic_plan or "").strip():
                continue
            try:
                plan = json.loads(p.topic_plan) or []
            except Exception:  # noqa: BLE001
                continue
            dfs = await creds.get_creds(pid, "dataforseo")
            n = 0
            for it in plan:
                if not isinstance(it, dict) or not it.get("topic"):
                    continue
                if it.get("difficulty") is not None:          # ประเมินแล้ว ข้าม (ไม่จ่ายซ้ำ)
                    continue
                if n >= cap:                                  # cap ต่อรอบ/โปรเจ็ค กันค่า SERP บานปลาย
                    break
                d = await serp.keyword_difficulty(it["topic"], creds=dfs or None)
                if d.get("score") is not None:
                    it["difficulty"] = d["score"]
                    it["difficulty_label"] = d.get("label") or ""
                    n += 1; scored += 1
            if n:
                p.topic_plan = json.dumps(plan, ensure_ascii=False)
                await s.commit()
    return "easy-win: assessed %d keywords across %d project(s)" % (scored, len(ids))


@celery_app.task(name="app.worker.tasks.build_lead_magnet")
def build_lead_magnet(magnet_id: int, topic: str) -> dict:
    """🎁 สร้างสื่อแจกฟรีเบื้องหลัง: เขียนเนื้อหา (Fable 5) + รูปปก + รูปประกอบในเนื้อ (fal.ai) ตามหัวข้อ
    ทำใน worker เพื่อไม่ให้ HTTP timeout (เนื้อหายาว + สร้างรูปหลายใบ)"""
    return _run(_build_lead_magnet(magnet_id, topic))


async def _build_lead_magnet(magnet_id: int, topic: str) -> dict:
    from app.db.models import LeadMagnet, Project
    if not db.enabled():
        return {"error": "DB not configured"}
    async with db.session() as s:
        m = await s.get(LeadMagnet, magnet_id)
        if not m:
            return {"error": "magnet not found"}
        proj = await s.get(Project, m.project_id)
        kind = m.kind
        biz = (getattr(proj, "business_context", "") or (proj.name if proj else "")) if proj else ""
        lang_code = (getattr(m, "language", "") or (proj.language if proj else "") or "th")
        lang = "English" if str(lang_code).lower().startswith("en") else "ภาษาไทย"
        m.stage = "✍️ กำลังเขียนเนื้อหา (AI)"; await s.commit()   # ขั้นที่ 1
    try:
        gen = await content.generate_lead_magnet(kind, topic, business_context=biz, language=lang)
    except Exception as e:  # noqa: BLE001 — บันทึก error ลง DB ไม่งั้นหน้า gate จะค้าง 'กำลังสร้าง' ตลอดกาล
        emsg = ("generate failed: " + str(e))[:280]
        try:
            async with db.session() as s:
                m = await s.get(LeadMagnet, magnet_id)
                if m:
                    m.error = emsg; m.stage = ""; await s.commit()
        except Exception:  # noqa: BLE001
            pass
        return {"error": emsg}
    async with db.session() as s:                        # ขั้นที่ 2
        m = await s.get(LeadMagnet, magnet_id)
        if m:
            m.stage = ("🎬 กำลังทำรูป + วิดีโอ" if kind in ("course", "guide") else "🖼️ กำลังใส่รูป")
            await s.commit()
    import asyncio as _aio
    content_html, cover, video = await _aio.gather(
        _enrich_media(gen["content_html"], topic),      # แทรกรูปประกอบในเนื้อตามหัวข้อ (fal.ai Seedream · crash-safe)
        _gen_magnet_cover(topic, kind),                 # รูปปกดึงดูด (สไตล์อีบุ๊ก · crash-safe: ล้ม='')
        _lead_magnet_video(topic, kind))                # วิดีโอ hero (โมเดลดีสุด · เฉพาะ course/guide · crash-safe)
    body = content_html or gen["content_html"]
    if video:                                           # วางวิดีโอไว้บนสุดของเนื้อหา (โชว์หลังปลดล็อกอีเมล) → ให้ดูเป็นคอร์สจริง
        body = ('<figure class="hero-video"><video src="%s" controls preload="metadata" playsinline '
                'style="width:100%%;border-radius:12px"></video></figure>' % video) + body
    async with db.session() as s:
        m = await s.get(LeadMagnet, magnet_id)
        if m:
            m.title = gen["title"]
            m.description = gen["description"]
            m.teaser_html = gen["teaser_html"]
            m.content_html = body
            m.cover_url = cover or ""
            m.error = ""; m.stage = ""                   # เคลียร์ (เสร็จแล้ว/กรณี retry สำเร็จ)
            await s.commit()
    return {"magnet_id": magnet_id, "built": True, "images": bool(cover), "video": bool(video)}


@celery_app.task(name="app.worker.tasks.gsc_opportunities")
def gsc_opportunities(per_project: int = 5) -> str:
    """⚡ GSC Opportunity Finder: ดึงคีย์ที่ 'Google โชว์เราแล้วจริง' (impression สูง) จาก Search Console
    → คีย์ 'ยังไม่มีบทความ' = เพิ่มเข้าแผนเขียนเลย (ดีมานด์พิสูจน์แล้ว = ติดไวสุด) · คีย์ที่มีแล้วแต่จ่อหน้า 1 = ดัน
    ต้องต่อ GSC ต่อโปรเจ็คก่อน (ไม่ต่อ = ข้าม)"""
    return _run(_gsc_opportunities(per_project))


async def _gsc_opportunities(per_project: int) -> str:
    from app.db.models import Project, Article
    from app.connectors import gsc
    if not db.enabled():
        return "DB not configured"
    added = boosted = 0
    async with db.session() as s:
        projs = (await s.execute(select(Project))).scalars().all()
    for p in projs:
        g = await creds.get_creds(p.id, "gsc")
        if not g or not p.domain:                         # ยังไม่ต่อ GSC = ข้าม (gated)
            continue
        try:
            summ = await gsc.summary("sc-domain:" + p.domain, 28, creds=g)
        except Exception:  # noqa: BLE001
            continue
        async with db.session() as s:
            titles = set((t or "").strip().lower() for t in (await s.execute(
                select(Article.title).where(Article.project_id == p.id))).scalars().all())
        new_topics = []
        for q in (summ.get("top_queries") or []):
            query = (q.get("query") or "").strip()
            pos = q.get("position") or 0
            if not query or (q.get("impressions") or 0) < 20:    # เอาเฉพาะคีย์ที่มีดีมานด์จริง
                continue
            if query.lower() in titles:                   # มีบทความแล้ว + จ่อหน้า 1 → ดัน
                if 8 <= pos <= 25:
                    async with db.session() as s:
                        aid = await _find_article_for_keyword(s, p.id, query)
                    if aid:
                        optimize_article.delay(aid); boosted += 1
            else:                                         # Google โชว์เราแต่ยังไม่มีบทความ → เขียนเลย
                new_topics.append(query)
        if new_topics:
            async with db.session() as s:
                proj = await s.get(Project, p.id)
                try:
                    plan = json.loads(proj.topic_plan) if (proj.topic_plan or "").strip() else []
                except Exception:  # noqa: BLE001
                    plan = []
                have = set(((it.get("topic") if isinstance(it, dict) else str(it)) or "").strip().lower() for it in plan)
                pa = 0
                gcap = _pack_cap(proj)
                for t in new_topics[:per_project]:
                    if len(plan) >= gcap:                 # เพดานรวม = แพ็กของลูกค้า (10/30/50)
                        break
                    if t.lower() not in have:
                        plan.append({"topic": t, "cluster": "GSC opportunity"})
                        have.add(t.lower()); pa += 1
                if pa:
                    proj.topic_plan = json.dumps(plan, ensure_ascii=False)
                    await s.commit(); added += pa
    return "GSC opportunities: +%d new topics (proven demand), %d boosts queued" % (added, boosted)


@celery_app.task(name="app.worker.tasks.grow_clusters")
def grow_clusters(batch: int = 3) -> str:
    """⚡ #3 Cluster Autopilot: ผลิตเป็นชุด (batch) ต่อโปรเจ็ค → ขยายคลัสเตอร์ให้ลึก = สร้างอำนาจหัวข้อ
    ติดเร็วขึ้นทั้งกลุ่ม (produce เลือกหัวข้อจากแผนที่จัดกลุ่มไว้ + interlink เชื่อมพี่น้องคลัสเตอร์เดียวกัน)"""
    return _run(_grow_clusters(batch))


async def _grow_clusters(batch: int) -> str:
    from app.db.models import Project
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        ids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
    for pid in ids:
        produce_for_project.delay(pid, batch)   # โควตายังบังคับใน produce → ไม่ผลิตเกินแพ็กเกจ
    return "queued cluster wave (batch=%d) for %d projects" % (batch, len(ids))


@celery_app.task(name="app.worker.tasks.refresh_interlinks")
def refresh_interlinks(per_project: int = 10) -> str:
    """⚡ #5 Authority Internal Linking: re-apply ลิงก์ภายในทุกบทความ → บทความเก่า (index แล้ว/แข็ง)
    ได้ลิงก์ไปหาบทความใหม่ = ส่ง crawl equity ให้หน้าใหม่ถูกเก็บ+ติดเร็วขึ้น"""
    return _run(_refresh_interlinks(per_project))


async def _refresh_interlinks(per_project: int) -> str:
    from app.db.models import Project, Article
    if not db.enabled():
        return "DB not configured"
    n = 0
    from sqlalchemy import func as _func
    async with db.session() as s:
        pids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
    day = datetime.now(timezone.utc).timetuple().tm_yday   # หมุนหน้าต่างทุกวัน → ครอบคลุม 'ทุกบทความ' ตามเวลา
    for pid in pids:
        async with db.session() as s:
            total = int((await s.execute(select(_func.count(Article.id)).where(
                Article.project_id == pid, Article.status == "published"))).scalar() or 0)
            if not total:
                continue
            offset = (day * per_project) % total           # เดิมค้างที่ 10 บทความเก่าสุดตลอด (audit HIGH) → หมุนไปเรื่อย ๆ
            arts = (await s.execute(
                select(Article.id, Article.title, Article.html)
                .where(Article.project_id == pid, Article.status == "published")
                .order_by(Article.id.asc()).offset(offset).limit(per_project))).all()
        for aid, title, html in arts:
            try:
                new_html = await _apply_internal_links(pid, title, html or "")
            except Exception:  # noqa: BLE001
                new_html = html
            if new_html and new_html != html:
                async with db.session() as s:
                    a = await s.get(Article, aid)
                    if a:
                        a.html = new_html
                        a.words = _wordcount(new_html)
                        await s.commit()
                        n += 1
    return "refreshed internal links on %d articles" % n


def _parse_competitors(raw) -> list:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()][:8]
    except Exception:  # noqa: BLE001
        pass
    return [x.strip() for x in raw.replace("\n", ",").split(",") if x.strip()][:8]


@celery_app.task(name="app.worker.tasks.authority_sweep")
def authority_sweep(per_project: int = 15) -> str:
    """⚡ Authority queue (รายสัปดาห์): เก็บ 'แหล่งที่ควรไปขอลิงก์' จาก Competitor Backlink Gap จริง
    → คิว OutreachTask ต่อโปรเจ็ค (คนรีวิว+ส่งเอง) · ต้องต่อ DataForSEO Backlinks · white-hat: ไม่ auto-โพสต์/ไม่ซื้อ"""
    return _run(_authority_sweep(per_project))


async def _authority_sweep(per_project: int) -> str:
    from app.db.models import Project, OutreachTask
    from app.connectors import growth
    from app.config import settings as _s
    if not db.enabled():
        return "DB not configured"
    if not (_s.dataforseo_login and _s.dataforseo_password):
        return "skip: no DataForSEO creds (Backlinks API needed)"
    async with db.session() as s:
        projs = (await s.execute(select(Project.id, Project.domain, Project.ai_competitors)
                                 .where(Project.active == True))).all()
    added = 0
    for pid, domain, comp_raw in projs:
        comps = _parse_competitors(comp_raw)
        if not comps:
            continue
        try:
            opps = await growth.backlink_gaps(comps, our_domain=(domain or ""), limit=per_project * 2)
        except Exception:  # noqa: BLE001
            continue
        if not opps:
            continue
        async with db.session() as s:
            existing = set((await s.execute(select(OutreachTask.source_domain)
                            .where(OutreachTask.project_id == pid))).scalars().all())
            for o in opps[:per_project]:
                dom = (o.get("domain") or "").strip().lower()
                if not dom or dom in existing:
                    continue
                hit = ", ".join((o.get("competitors") or [])[:4])
                s.add(OutreachTask(project_id=pid, source_domain=dom, kind="competitor-gap",
                                   reason=("ลิงก์ให้คู่แข่ง %d เจ้า: %s" % (o.get("competitors_count") or 0, hit))[:400],
                                   authority=int(o.get("backlinks") or 0), status="todo"))
                existing.add(dom); added += 1
            await s.commit()
    return "authority_sweep: +%d outreach opportunities queued" % added


@celery_app.task(name="app.worker.tasks.ensure_schema")
def ensure_schema(per_project: int = 4) -> str:
    """⚡ #8 AEO Schema completeness: หาบทความที่ยังไม่มี schema (JSON-LD) → เข้าคิว optimize
    (สร้าง schema + ดันคะแนน AEO) → ชิง Featured Snippet / ให้ AI หยิบไปตอบง่ายขึ้น"""
    return _run(_ensure_schema(per_project))


async def _ensure_schema(per_project: int) -> str:
    from app.db.models import Project, Article
    if not db.enabled():
        return "DB not configured"
    n = 0
    async with db.session() as s:
        pids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
        for pid in pids:
            rows = (await s.execute(
                select(Article.id).where(
                    Article.project_id == pid, Article.status == "published",
                    (Article.schema_json == "") | (Article.schema_json.is_(None)))
                .limit(per_project))).scalars().all()
            for aid in rows:
                optimize_article.delay(aid)
                n += 1
    return "queued schema/optimize for %d articles missing schema" % n


_FAQ_QWORDS = ("ไหม", "หรือไม่", "อย่างไร", "ยังไง", "อะไร", "ทำไม", "เท่าไร", "เท่าไหร่",
               "กี่", "เมื่อไร", "เมื่อไหร่", "ที่ไหน", "ใคร", "ควร", "?", "how", "what",
               "why", "when", "where", "which", "who", "can ", "does ", "is ", "are ", "do ")


def _looks_like_question(t: str) -> bool:
    tl = (t or "").strip().lower()
    return bool(tl) and (tl.endswith("?") or any(w in tl for w in _FAQ_QWORDS))


def _faq_from_html(html: str) -> list:
    """ดึงคู่ Q/A จากบทความ → FAQPage schema (AEO: ชิง snippet + AI หยิบง่าย)
    รองรับหลายรูปแบบ: h2/h3/h4 เป็นคำถาม + คำตอบเป็น p/ul/ol, และ <dl><dt>/<dd> — ทนแท็กคั่น
    (เดิมจับแค่ h3+p แคบเกิน → บทความส่วนใหญ่เลยไม่ได้ FAQPage)"""
    import re as _re
    src = html or ""

    def _txt(s):
        return _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", s or "")).strip()

    # โฟกัสส่วน FAQ ถ้าเจอหัวข้อ (ไม่เจอก็สแกนทั้งหน้า — คำถามชัดในตัวอยู่แล้ว)
    m = _re.search(r"คำถามที่พบบ่อย|FAQ|Q\s*&\s*A|ถาม-ตอบ|คำถามยอดฮิต", src, _re.I)
    seg = src[m.start():] if m else src
    out, seen = [], set()
    # หัวข้อ (h2/h3/h4/dt) → คำตอบ = บล็อกถัดไปจนถึงหัวข้อถัดไป (เอา p/li/dd มาต่อกัน)
    for mm in _re.finditer(r"<(h[234]|dt)\b[^>]*>(.*?)</\1>(.*?)(?=<(?:h[1-6]|dt)\b|$)",
                           seg, _re.S | _re.I):
        q = _txt(mm.group(2))
        rest = mm.group(3) or ""
        parts = _re.findall(r"<(?:p|li|dd)\b[^>]*>(.*?)</(?:p|li|dd)>", rest, _re.S | _re.I)
        a = _txt(" ".join(parts)) if parts else _txt(rest)
        k = q.lower()
        if q and a and _looks_like_question(q) and len(q) <= 200 and len(a) >= 10 and k not in seen:
            seen.add(k)
            out.append((q[:200], a[:900]))
        if len(out) >= 10:
            break
    return out


def _build_schema(art, brand: str) -> str:
    """สร้าง JSON-LD (@graph: Article + Breadcrumb + Organization + FAQPage ถ้ามี) แบบ deterministic
    เร็ว/ฟรี/ครบ — ไม่ต้องเรียก LLM เขียนใหม่ทั้งบทความ → เติม schema ให้ทุกหน้าได้เร็ว"""
    import json as _json, re as _re
    from urllib.parse import urlsplit
    title = (art.title or "").strip()
    desc = (art.description or _re.sub(r"<[^>]+>", "", art.html or "")[:155]).strip()
    url = (art.url or "").strip()
    home = ""
    if url:
        p = urlsplit(url)
        if p.scheme and p.netloc:
            home = "%s://%s" % (p.scheme, p.netloc)
    art_node = {"@type": "Article", "headline": title[:110], "description": desc[:300],
                "author": {"@type": "Organization", "name": brand},
                "publisher": {"@type": "Organization", "name": brand}}
    if url:
        art_node["mainEntityOfPage"] = {"@type": "WebPage", "@id": url}
    if getattr(art, "cover_url", ""):
        art_node["image"] = art.cover_url
    if getattr(art, "created_at", None):
        art_node["datePublished"] = art.created_at.isoformat()
    if getattr(art, "updated_at", None):
        art_node["dateModified"] = art.updated_at.isoformat()
    graph = [art_node]
    if home and url:
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": brand, "item": home},
            {"@type": "ListItem", "position": 2, "name": title[:80], "item": url}]})
    graph.append({"@type": "Organization", "name": brand, "url": home or url})
    faqs = _faq_from_html(art.html or "")
    if faqs:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faqs]})
    return _json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)


@celery_app.task(name="app.worker.tasks.backfill_schema")
def backfill_schema(project_id: int = 0, cap: int = 300) -> str:
    """⚡ เติม Schema (JSON-LD) ให้บทความที่ยังไม่มี — deterministic เร็ว/ฟรี → Schema coverage พุ่งเป็น ~100%"""
    return _run(_backfill_schema(project_id, cap))


async def _backfill_schema(project_id: int, cap: int) -> str:
    from app.db.models import Project, Article
    from app.connectors.aeo_score import _valid_schema
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        ids = [project_id] if project_id else (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
    fixed = 0
    for pid in ids:
        async with db.session() as s:
            proj = await s.get(Project, pid)
            if not proj:
                continue
            brand = (proj.name or proj.domain or "").strip()
            arts = (await s.execute(
                select(Article).where(Article.project_id == pid, Article.status == "published")
                .limit(cap))).scalars().all()
            n = 0
            for a in arts:
                if _valid_schema(a.schema_json or "")[0]:      # มี schema ถูกต้องแล้ว ข้าม
                    continue
                a.schema_json = _build_schema(a, brand)
                a.aeo_score = _aeo_of(a.html or "", a.title or "", (a.description or "")[:155],
                                      a.schema_json, getattr(a, "cover_url", "") or "")
                n += 1; fixed += 1
                if n >= cap:
                    break
            if n:
                await s.commit()
    return "backfilled schema on %d articles" % fixed


# ── สร้างเว็บลูกค้า 'สวยขายได้' — Claude เขียนคอนเทนต์ + Imgentic ทำ hero + รูปจริงลูกค้า ──
async def _client_site_copy(name: str, biz_type: str, about: str, lang: str) -> dict:
    """ให้ Claude เขียนคอนเทนต์หน้าแรกเว็บ (โครงพร้อม render) จากบรีฟจริง — no-faking (ไม่กุสถิติ/รีวิว/รางวัล)"""
    from app.connectors import content
    import json as _json, re as _re
    en = str(lang).lower().startswith("en")
    L = "English" if en else "ภาษาไทยที่เป็นธรรมชาติ สละสลวย"
    system = ("คุณเป็นนักเขียนคอนเทนต์เว็บธุรกิจ + copywriter ระดับพรีเมียม เขียนเป็น%s. "
              "เขียนคอนเทนต์หน้าแรกเว็บที่ 'ดูแพง น่าเชื่อถือ ชวนติดต่อ'. "
              "กฎเหล็ก: ห้ามกุข้อมูลเท็จเด็ดขาด — ห้ามแต่งสถิติ/ตัวเลข/รีวิว/รางวัล/ปีที่ก่อตั้ง/จำนวนลูกค้า ที่ไม่ได้ระบุมา. "
              "เขียนจากสิ่งที่ธุรกิจ 'เป็นจริง' เท่านั้น กระชับ ทรงพลัง. ตอบกลับเป็น JSON ล้วนเท่านั้น ไม่มีข้อความอื่น." % L)
    user = ("ข้อมูลธุรกิจ:\nชื่อ: %s\nประเภท: %s\nรายละเอียด/บรีฟ: %s\n\n"
            "สร้าง JSON โครงนี้ (ทุกฟิลด์เป็น%s):\n"
            "{\n \"hero_headline\": พาดหัวหลักสั้นทรงพลัง 4-9 คำ (ไม่ใช่แค่ชื่อร้าน),\n"
            " \"hero_sub\": 1 ประโยคขยายชวนมาใช้บริการ,\n"
            " \"cta\": ข้อความปุ่ม 2-3 คำ (เช่น จองโต๊ะ / สั่งเลย / ติดต่อเรา),\n"
            " \"about_title\": หัวข้อ about,\n \"about_body\": 2-3 ประโยคเล่าจุดเด่น/เรื่องราวจริงของธุรกิจ,\n"
            " \"features\": [{\"icon\": อีโมจิ 1 ตัว, \"title\": สั้น, \"desc\": 1 ประโยค} 3 จุดเด่น/บริการ],\n"
            " \"why\": [เหตุผลเลือกเรา 3 ข้อ สั้นกระชับ],\n"
            " \"gallery_title\": หัวข้อแกลเลอรี,\n \"contact_title\": หัวข้อชวนติดต่อ\n}"
            % (name, biz_type, (about or "")[:600], L))
    try:
        _prov, text = await content._llm(system, user, tier="strong")   # tier=strong = Claude (คุณภาพสูง)
        m = _re.search(r"\{.*\}", text or "", _re.S)
        d = _json.loads(m.group(0)) if m else {}
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


@celery_app.task(name="app.worker.tasks.build_client_site")
def build_client_site(project_id: int, brief: dict | None = None) -> str:
    return _run(_build_client_site(project_id, brief or {}))


async def _build_client_site(project_id: int, brief: dict) -> str:
    """ยกระดับ home_html ของลูกค้าให้ 'สวยขายได้': Claude เขียนคอนเทนต์ + Imgentic เจน hero + รูปจริง + schema"""
    from app.db.models import Project, UploadedImage
    from app import public as _public
    from app.connectors import imgentic
    from app.config import settings as S
    if not db.enabled():
        return "no db"
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p:
            return "no project"
        name = (brief.get("name") or p.name or "").strip()
        biz_type = (brief.get("biz_type") or "").strip()
        about = (brief.get("about") or getattr(p, "business_context", "") or "").strip()
        lang = brief.get("lang") or ("en" if str(p.language).lower().startswith("en") else "th")
        rtoken = getattr(p, "report_token", "") or ""
        try:
            home_url = _public.project_public_home(p) or ""
        except Exception:  # noqa: BLE001
            home_url = ""
        base = (S.app_base_url or "").rstrip("/")
        imgs = (await s.execute(select(UploadedImage).where(UploadedImage.project_id == project_id))).scalars().all()
        photo_urls = [base + "/api/media/" + str(im.id) for im in imgs]
    contact = brief.get("contact") or {}
    # 1) Claude เขียนคอนเทนต์
    copy = await _client_site_copy(name, biz_type or about[:60], about, lang)
    # 2) Imgentic เจนภาพ hero พรีเมียม (ถ้าพร้อม) — ไม่พร้อม/พลาด = ใช้รูปจริงลูกค้าเป็น hero
    hero_img = ""
    if imgentic.image_ready():
        try:
            desc = ((copy.get("about_body") if isinstance(copy, dict) else "") or about or biz_type or name)[:200]
            hay = (biz_type + " " + about).lower()
            style = ("appetizing warm food & interior photography" if any(k in hay for k in ("อาหาร", "cafe", "restaurant", "บาร์", "bar", "food", "คาเฟ่", "bistro"))
                     else "clean premium editorial brand photography")
            prompt = ("Premium website hero image for '%s' (%s). %s. %s, cinematic lighting, high-end, magazine quality, no text, no logo, no watermark."
                      % (name, biz_type or "business", desc, style))
            hero_img = (await imgentic.generate_image(prompt)) or ""
        except Exception:  # noqa: BLE001
            hero_img = ""
    # 3) เก็บ 'บรีฟเว็บ' (copy+hero+รูป) → ใช้ re-render ได้ทั้ง 3 variants ในหน้าเลือกแบบ
    import json as _json2
    brief_store = {"copy": copy if isinstance(copy, dict) else {}, "hero_img": hero_img,
                   "photo_urls": photo_urls, "name": name, "biz_type": biz_type, "about": about,
                   "contact": contact, "lang": lang, "report_token": rtoken, "home_url": home_url}
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if p:
            p.site_brief = _json2.dumps(brief_store, ensure_ascii=False)
            variant = getattr(p, "site_variant", 0) or 1        # เลือกไว้แล้วใช้อันนั้น · ไม่งั้น default 1
            home = _public.render_client_home(name, biz_type, about, contact, photo_urls, lang, rtoken,
                                              copy=brief_store["copy"], hero_img=hero_img, variant=variant)
            try:
                home = _public.inject_aeo_geo(home, name=name, home=home_url,
                                              lang=("en" if str(lang).lower().startswith("en") else "th"), brief={})
            except Exception:  # noqa: BLE001
                pass
            p.home_html = home
            await s.commit()
    return "built site brief: %s (copy=%s hero=%s photos=%d)" % (name, bool(copy), bool(hero_img), len(photo_urls))


@celery_app.task(name="app.worker.tasks.backfill_covers")
def backfill_covers(project_id: int = 0, cap: int = 40, force: bool = False) -> str:
    """⚡ เติมรูปปก + รูปในเนื้อ + ภาพสรุป ให้บทความ → หน้าบทความมีภาพครบ ดูพรีเมียม
    force=True → 'สร้างภาพใหม่ทับของเดิมทุกชิ้น' (ใช้ตอนอัปเกรดคุณภาพภาพ) · crash-safe + จำกัด cap คุมต้นทุน"""
    return _run(_backfill_covers(project_id, cap, force))


async def _backfill_covers(project_id: int, cap: int, force: bool = False) -> str:
    import re as _re
    from sqlalchemy import or_, func as _func
    from app.db.models import Project, Article
    if not db.enabled():
        return "DB not configured"
    from app.config import settings as _cfg
    can_img = media.enabled()                              # รูป (ปก/ในเนื้อ) ต้องมี fal/ARK · ภาพสรุปใช้แค่ LLM
    trend_on = bool(getattr(_cfg, "trend_chart", False))   # กราฟเทรนด์ = opt-in (กินเครดิต DataForSEO)
    async with db.session() as s:
        ids = [project_id] if project_id else (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
    fixed = 0
    for pid in ids:
        if fixed >= cap:
            break
        async with db.session() as s:                      # force → ทุกบทความ · ไม่ force → เฉพาะที่ขาด ปก/รูป/ภาพสรุป
            proj = await s.get(Project, pid)
            lang = "English" if (proj and str(proj.language).lower().startswith("en")) else "ภาษาไทย"
            base = [Article.project_id == pid, Article.status == "published"]
            if not force:
                conds = [_func.coalesce(Article.cover_url, "") == "",
                         Article.html.notlike("%inline-img%"),
                         Article.html.notlike('%class="infographic"%')]
                if trend_on:
                    conds.append(Article.html.notlike('%class="trend-chart"%'))
                base.append(or_(*conds))
            arts = (await s.execute(
                select(Article).where(*base).order_by(Article.id).limit(cap))).scalars().all()
        dfs = await creds.get_creds(pid, "dataforseo") if trend_on else None
        for a in arts:
            if fixed >= cap:
                break
            cur = a.html or ""
            if force and can_img:                          # อัปเกรดภาพ: ลบรูปในเนื้อเก่าออกก่อน แล้วสร้างใหม่
                cur = _re.sub(r'<figure class="inline-img">.*?</figure>', '', cur, flags=_re.S)
            cover_new = (await _gen_cover(a.title or "")) \
                if (can_img and (force or not (getattr(a, "cover_url", "") or "").strip())) else ""
            if can_img and (force or "inline-img" not in cur):   # เติม/สร้างรูปในเนื้อใหม่
                h2 = await _enrich_media(cur, a.title or "")
                if h2 and "inline-img" in h2:
                    cur = h2
            if 'class="infographic"' not in cur:           # เติมภาพสรุป (จากเนื้อบทความจริง ไม่ปั้นเลข)
                blk = await _infographic_html(cur, a.title or "", lang)
                if blk:
                    cur = _insert_infographic(cur, blk)
            if trend_on and 'class="trend-chart"' not in cur:   # เติมกราฟเทรนด์ค้นหาจริง (DataForSEO)
                tcb = await _trend_chart_html(a.title or "", dfs)
                if tcb:
                    cur = _insert_trend(cur, tcb)
            if not (cover_new or cur != (a.html or "")):   # ไม่มีอะไรเปลี่ยน → ข้าม
                continue
            async with db.session() as s2:
                art = await s2.get(Article, a.id)
                if not art:
                    continue
                if cover_new:
                    art.cover_url = cover_new
                if cur != (art.html or ""):
                    art.html = cur
                art.aeo_score = _aeo_of(art.html or "", art.title or "", (art.description or "")[:155],
                                        art.schema_json or "", getattr(art, "cover_url", "") or "")
                await s2.commit()
            fixed += 1
    return "backfilled media on %d articles" % fixed


@celery_app.task(name="app.worker.tasks.gsc_ctr_boost")
def gsc_ctr_boost(per_project: int = 3) -> str:
    """⚡ #4 CTR Optimizer: ใช้ Google Search Console หา query ที่ 'มีคนเห็นแต่ CTR ต่ำ + อันดับ 5-15'
    → เข้าคิว optimize (รีไรต์ title/meta ให้คนคลิกมากขึ้น) → CTR สูงหนุนอันดับ · ต้องต่อ GSC ต่อโปรเจ็คก่อน"""
    return _run(_gsc_ctr_boost(per_project))


async def _gsc_ctr_boost(per_project: int) -> str:
    from app.db.models import Project, Article
    from app.connectors import gsc
    if not db.enabled():
        return "DB not configured"
    n = 0
    async with db.session() as s:
        projs = (await s.execute(select(Project))).scalars().all()
    for p in projs:
        g = await creds.get_creds(p.id, "gsc")
        if not g or not p.domain:                             # ยังไม่ต่อ GSC = ข้าม (gated)
            continue
        try:
            summ = await gsc.summary("sc-domain:" + p.domain, 28, creds=g)
        except Exception:  # noqa: BLE001
            continue
        picks = [q for q in (summ.get("top_queries") or [])
                 if 5 <= (q.get("position") or 0) <= 15 and (q.get("ctr") or 0) < 3
                 and (q.get("impressions") or 0) >= 10]
        for q in picks[:per_project]:
            async with db.session() as s:
                aid = await _find_article_for_keyword(s, p.id, q["query"])
            if aid:
                optimize_article.delay(aid)
                n += 1
    return "queued CTR-boost optimize for %d low-CTR queries" % n


@celery_app.task(name="app.worker.tasks.competitor_gap_scan")
def competitor_gap_scan(per_project: int = 2, add_max: int = 4) -> str:
    """⚡ #7 Competitor Gap Monitor: ดูหน้าที่คู่แข่งติดอันดับสำหรับคีย์ที่เรายังไม่ติด
    → เพิ่ม 'หัวข้อ gap' เข้าแผนหัวข้อ (topic_plan) ให้รอบผลิตถัดไปเขียนแซง · ต้องต่อ DataForSEO"""
    return _run(_competitor_gap_scan(per_project, add_max))


async def _competitor_gap_scan(per_project: int, add_max: int) -> str:
    from app.db.models import Project, Article, RankSnapshot
    if not db.enabled():
        return "DB not configured"
    added = 0
    async with db.session() as s:
        projs = (await s.execute(select(Project))).scalars().all()
    for p in projs:
        dfs = await creds.get_creds(p.id, "dataforseo")
        async with db.session() as s:
            snaps = (await s.execute(
                select(RankSnapshot.keyword, RankSnapshot.on_page1)
                .where(RankSnapshot.project_id == p.id).order_by(RankSnapshot.checked_at))).all()
            existing = set((await s.execute(
                select(Article.title).where(Article.project_id == p.id))).scalars().all())
        latest = {}
        for kw, op in snaps:
            latest[kw] = bool(op)
        weak = [kw for kw, op in latest.items() if not op][:per_project]   # คีย์ที่ยังไม่ติดหน้า 1
        gap_topics = []
        for kw in weak:
            try:
                comps = await serp.top_competitors(kw, n=5, creds=dfs or None)
            except Exception:  # noqa: BLE001
                comps = []
            for c in comps:
                t = (c.get("title") or "").strip()
                if t and t not in existing and t not in gap_topics and len(t) <= 120:
                    gap_topics.append(t)
        gap_topics = gap_topics[:add_max]
        if not gap_topics:
            continue
        async with db.session() as s:
            proj = await s.get(Project, p.id)
            try:
                plan = json.loads(proj.topic_plan) if (proj.topic_plan or "").strip() else []
            except Exception:  # noqa: BLE001
                plan = []
            have = {(it.get("topic") if isinstance(it, dict) else str(it)) for it in plan}
            gcap = _pack_cap(proj)
            for t in gap_topics:
                if len(plan) >= gcap:                     # ไม่เกินโควตาแพ็กของลูกค้า
                    break
                if t not in have:
                    plan.append({"topic": t, "cluster": "competitor-gap"})
                    added += 1
            proj.topic_plan = json.dumps(plan, ensure_ascii=False)
            await s.commit()
    return "added %d competitor-gap topics to content plans" % added


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
        ids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
    # ทยอยผลิตห่างกัน 7 นาที/โปรเจ็ค — กันเครื่องตันจากงานหนัก (Fable 5 + รูป) พร้อมกันหลายตัว → บทความออกครบ
    for i, pid in enumerate(ids):
        produce_for_project.apply_async((pid, 1), countdown=i * 420)
    return "queued content production for %d projects (staggered)" % len(ids)


# =========================================================
#  MEASURE (M5) — วัดอันดับจริงของทุกโปรเจ็ค
# =========================================================

@celery_app.task(name="app.worker.tasks.measure_all_ranks")
def measure_all_ranks() -> str:
    return _run(_measure_all_ranks())


def _tracked_keywords(p, article_titles, cap: int = 50) -> list:
    """คีย์ที่โปรเจ็ค 'ติดตาม' = คีย์ใน topic_plan (ที่ลูกค้าเพิ่ม) ก่อน + หัวข้อบทความที่เผยแพร่ · ตัดซ้ำ · สูงสุด cap"""
    out, seen = [], set()
    try:
        for it in (json.loads(p.topic_plan) if (getattr(p, "topic_plan", "") or "").strip() else []):
            t = ((it.get("topic") if isinstance(it, dict) else str(it)) or "").strip()
            if t and t.lower() not in seen:
                seen.add(t.lower()); out.append(t)
    except Exception:  # noqa: BLE001
        pass
    for t in (article_titles or []):
        t = (t or "").strip()
        if t and t.lower() not in seen:
            seen.add(t.lower()); out.append(t)
    return out[:cap]


async def _measure_all_ranks() -> str:
    from app.db.models import Project, Article
    if not db.enabled():
        return "DB not configured"
    n = 0
    async with db.session() as s:
        projs = (await s.execute(select(Project))).scalars().all()
    for p in projs:
        async with db.session() as s:
            titles = (await s.execute(
                select(Article.title).where(Article.project_id == p.id,
                                            Article.status == "published"))).scalars().all()
        for kw in _tracked_keywords(p, titles, _pack_cap(p)):   # คีย์ลูกค้า (topic_plan) + หัวข้อบทความ · สูงสุด = แพ็ก
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


def _aeo_questions_of(p) -> list[str]:
    """คำถาม AEO ที่ 'ลูกค้าตั้งเอง' (JSON list) — สิ่งที่คนถาม AI จริง ๆ ให้ตรงกว่าคีย์เวิร์ด SEO"""
    raw = getattr(p, "aeo_questions", "") or ""
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
        out, seen = [], set()
        for q in (data or []):
            t = str(q).strip()
            if t and t.lower() not in seen:
                seen.add(t.lower()); out.append(t)
        return out[:30]
    except Exception:  # noqa: BLE001
        return []


async def _project_questions(p, project_id: int, limit: int = 6) -> list[str]:
    """ชุดคำถามสำหรับสุ่มถาม AI (วัด AI Citation) — 'คำถาม AEO ที่ลูกค้าตั้งเอง' มาก่อน (ตรงที่สุด)
    ถ้ายังไม่พอ → สร้าง 'คำถาม recommendation-intent' (ที่ AI จะแนะนำแบรนด์จริง) จากบริบทธุรกิจ
    → สำรองด้วยหัวข้อบทความ/แผนหัวข้อเฉพาะกรณีสร้างคำถามไม่ได้"""
    from app.db.models import Article
    custom = _aeo_questions_of(p)                         # ลูกค้าตั้งเอง = ลำดับแรกเสมอ
    qs: list[str] = list(custom)
    if len(qs) < limit:                                   # เติมด้วยคำถามที่ 'ทำให้ AI แนะนำแบรนด์' (ไม่ใช่คีย์เวิร์ดลอย ๆ)
        try:
            lang = "English" if str(getattr(p, "language", "") or "").lower().startswith("en") else "ภาษาไทย"
            gen = await content.suggest_aeo_questions(
                getattr(p, "name", "") or "", getattr(p, "domain", "") or "",
                getattr(p, "business_context", "") or "", lang, n=limit)
            qs += [q for q in gen if q]
        except Exception:  # noqa: BLE001
            pass
    if len(qs) < 2 and db.enabled():                      # สำรองสุดท้าย: หัวข้อบทความจริง (กันว่างเปล่า)
        async with db.session() as s:
            titles = (await s.execute(
                select(Article.title).where(Article.project_id == project_id,
                                            Article.status == "published")
                .order_by(Article.id.desc()).limit(limit))).scalars().all()
        qs += [t for t in titles if t]
    # กันซ้ำ คงลำดับ — ถ้าลูกค้าตั้งคำถามเองไว้เยอะ ให้ใช้ครบ (เพดาน 10 กันค่ายิงบานปลาย)
    seen, out = set(), []
    for q in qs:
        k = q.strip().lower()
        if q.strip() and k not in seen:
            seen.add(k); out.append(q.strip())
    cap = min(10, max(limit, len(custom)))
    return out[:cap]


async def _sample_and_save(project_id: int, questions: list[str] | None = None) -> dict:
    """รัน Prompt Sampling จริงต่อโปรเจ็ค แล้ว 'บันทึกผลลง DB' (CitationSnapshot)
    → นี่คือสิ่งที่ทำให้ 'แนวโน้ม Share of Voice' สะสมได้จริง (ไม่ใช่ยิงแล้วทิ้ง)"""
    from app.db.models import Project, CitationSnapshot, CitationExample
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
        lang = "English" if str(getattr(p, "language", "") or "").lower().startswith("en") else "ภาษาไทย"
        qs = [q for q in (questions or []) if q and q.strip()]
        if not qs:
            qs = await _project_questions(p, project_id)
    if not qs:
        return {"project": domain, "saved": False, "note": "ยังไม่มีชุดคำถามให้สุ่มถาม"}

    res = await citation.sample(qs, brand_terms, domain, engines, lang)

    per = res.get("per_engine") or {}
    competitors = res.get("competitors") or []           # คู่แข่งที่ AI แนะนำแทนเรา
    # หลักฐาน AEO: เก็บตัวอย่างคำถามที่ AI 'ตอบแล้วอ้างเราจริง' (มี snippet) สูงสุด 6 ต่อรอบ
    examples = [d for d in (res.get("details") or []) if d.get("cited") and d.get("snippet")][:6]
    async with db.session() as s:                    # บันทึก snapshot ต่อเอนจิน (ตรวจสอบย้อนได้)
        for eng, v in per.items():
            s.add(CitationSnapshot(project_id=project_id, engine=eng,
                                   sov_percent=v.get("sov_percent"),
                                   answered=v.get("answered") or 0,
                                   cited=v.get("cited") or 0))
        for d in examples:
            s.add(CitationExample(project_id=project_id, engine=d.get("engine") or "",
                                  question=(d.get("question") or "")[:500],
                                  snippet=(d.get("snippet") or "")[:280]))
        if competitors:                                  # เก็บ 'คู่แข่งที่ AI แนะนำ' ล่าสุดไว้ที่โปรเจ็ค (โชว์ในรายงาน)
            pp = await s.get(Project, project_id)
            if pp:
                pp.ai_competitors = json.dumps(competitors, ensure_ascii=False)
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
        ids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
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
    from app.db.models import Project, Lead
    from sqlalchemy import func as _func
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    week_ago = _dt.now(_tz.utc) - _td(days=7)
    async with db.session() as s:
        projs = (await s.execute(select(Project).where(Project.user_id == user.id))).scalars().all()
    if not projs:
        return None
    blocks = []
    for p in projs:
        ins = await _project_insights(p.id, p)
        if not ins.get("count"):
            continue
        async with db.session() as s2:      # 🎯 ลีดที่เก็บได้ (พิสูจน์ ROI — ไม่ใช่แค่อันดับ)
            leads_wk = int((await s2.execute(select(_func.count(Lead.id)).where(
                Lead.project_id == p.id, Lead.created_at >= week_ago))).scalar() or 0)
            leads_all = int((await s2.execute(select(_func.count(Lead.id)).where(
                Lead.project_id == p.id))).scalar() or 0)
        lead_line = ("<div style='color:#0f8a55;font-weight:700;font-size:14px;margin:2px 0 8px'>🎯 ลีดใหม่สัปดาห์นี้ %d คน (สะสม %d)</div>" % (leads_wk, leads_all)) if leads_all else ""
        items = "".join("<li>%s</li>" % _esc(i.get("text", "")) for i in ins.get("insights", [])[:4])
        blocks.append(
            "<div style='margin:0 0 22px;padding:16px;border:1px solid #e7ecf6;border-radius:12px'>"
            "<div style='font-weight:800;font-size:16px'>%s</div>"
            "<div style='color:#5a6a86;font-size:14px;margin:4px 0 8px'>บทความ %d · คะแนน AEO เฉลี่ย %s · ติดหน้า 1 %d คีย์เวิร์ด</div>"
            "%s"
            "<ul style='margin:0;padding-left:18px;font-size:14px'>%s</ul></div>"
            % (_esc(p.name or p.domain), ins["count"],
               ins.get("avg_score", "—"), ins.get("page1", 0), lead_line, items or "<li>กำลังสะสมข้อมูลเพิ่ม</li>"))
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


@celery_app.task(name="app.worker.tasks.cost_watch")
def cost_watch() -> str:
    """💳 เฝ้าค่าใช้จ่าย/เครดิต → เด้ง LINE เตือนเมื่อยอด DataForSEO ใกล้หมด หรือค่าใช้จ่ายเดือนนี้ใกล้/เกินงบ"""
    return _run(_cost_watch())


async def _cost_watch() -> str:
    from datetime import datetime, timezone
    from sqlalchemy import func
    from app.db.models import Article, RankSnapshot, CitationSnapshot
    from app.connectors import notify, serp
    from app.config import settings as S
    if not db.enabled():
        return "DB not configured"
    alerts = []
    # 1) ยอดคงเหลือ DataForSEO (ดึงสดจาก API) — เตือนก่อนหมดเครดิต
    low_usd = float(getattr(S, "cost_alert_low_usd", 5.0) or 5.0)
    if S.dataforseo_login and S.dataforseo_password:
        try:
            bal = await serp.account_balance()
        except Exception:  # noqa: BLE001
            bal = None
        if bal is not None and bal < low_usd:
            alerts.append("💳 DataForSEO เหลือ $%.2f (ต่ำกว่า $%g) — เติมด่วน\n   → app.dataforseo.com › Billing" % (bal, low_usd))
    # 2) ค่าใช้จ่ายเดือนนี้ (ประมาณการจากการใช้จริง) เทียบงบที่ตั้งไว้
    budget = int(getattr(S, "cost_budget_thb", 0) or 0)
    if budget > 0:
        mstart = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        async with db.session() as s:
            arts = int((await s.execute(select(func.count(Article.id)).where(Article.created_at >= mstart))).scalar() or 0)
            imgs = int((await s.execute(select(func.count(Article.id)).where(Article.created_at >= mstart, Article.cover_url != ""))).scalar() or 0)
            rnk = int((await s.execute(select(func.count(RankSnapshot.id)).where(RankSnapshot.checked_at >= mstart))).scalar() or 0)
            cit = int((await s.execute(select(func.count(CitationSnapshot.id)).where(CitationSnapshot.sampled_at >= mstart))).scalar() or 0)
        total = round(arts * 12.0 + imgs * 5.0 + rnk * 0.3 + cit * 2.0)
        pct = round(total / budget * 100)
        if total >= budget:
            alerts.append("📊 ค่าใช้จ่ายเดือนนี้ ~฿%s / งบ ฿%s (%d%%) — เกินงบแล้ว!" % (total, budget, pct))
        elif pct >= 80:
            alerts.append("📊 ค่าใช้จ่ายเดือนนี้ ~฿%s / งบ ฿%s (%d%%) — ใกล้เต็มงบ" % (total, budget, pct))
    if not alerts:
        return "cost ok — ไม่มีอะไรต้องเตือน"
    msg = "⚠️ แจ้งเตือนค่าใช้จ่าย ImVisible\n\n" + "\n\n".join(alerts) + "\n\n(ดูละเอียดที่แดชบอร์ด › ต้นทุน)"
    try:
        ok = await notify.send_line(msg)
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        print("[cost_watch] มีเรื่องต้องเตือน %d ข้อ แต่ส่ง LINE ไม่สำเร็จ (ตรวจ LINE_CHANNEL_ACCESS_TOKEN/LINE_DEFAULT_TO)" % len(alerts))
    return "cost alert: %d issue · line_sent=%s" % (len(alerts), ok)


@celery_app.task(name="app.worker.tasks.learning_loop")
def learning_loop() -> str:
    """M6: เรียนรู้จากผลจริงของทุกโปรเจ็ค → ปรับลำดับหัวข้อให้คลัสเตอร์ที่ได้ผลมาก่อน"""
    return _run(_learning_loop())


async def _learning_loop() -> str:
    from app.db.models import Project
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        ids = (await s.execute(select(Project.id).where(Project.active == True))).scalars().all()
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


# ============================================================
# ♻️ Social Push — กระจาย 'สื่อแจกฟรี/บทความ' ไปช่องโซเชียล (FB Page ฯลฯ) อัตโนมัติ
#   • โพสต์ 'ครั้งเดียวต่อบทความต่อช่อง' (กันสแปม) → backfill บทความเก่า + ช่องที่เพิ่งต่อ
#   • caption ดึงดูด + รูปปก (FB ดึง og:image จากหน้าบทความ = รูปหัวข้อโดน ๆ อัตโนมัติ)
#   • หมายเหตุตามจริง: ลิงก์ FB = nofollow → คุณค่าคือ traffic + AEO/entity + เหยื่อลิงก์ (ไม่ใช่ backlink สาย SEO ตรง ๆ)
# ============================================================
_SOCIAL_KINDS = {"facebook", "x", "linkedin", "telegram", "instagram", "pinterest", "mastodon", "discord", "webhook"}
_HOOKS_TH = ["🔥 อ่านจบทำตามได้เลย", "📌 สรุปครบในโพสต์เดียว", "💡 รู้ไว้ไม่พลาด", "✅ เช็กลิสต์ทำจริง", "🚀 เริ่มวันนี้เห็นผลไว"]
_HOOKS_EN = ["🔥 A practical guide", "📌 Save this for later", "💡 Worth knowing", "✅ A hands-on checklist", "🚀 Start today"]


def _social_caption(title: str, desc: str, lang: str = "th") -> str:
    """คำโปรยโซเชียลสั้น ๆ ดึงดูด (deterministic · ไม่ยิง LLM = ไม่มีค่าใช้จ่าย/ไม่ล้ม)"""
    title = (title or "").strip()
    hooks = _HOOKS_EN if lang == "en" else _HOOKS_TH
    hook = hooks[len(title) % len(hooks)] if title else hooks[0]
    cta = "อ่านเต็ม ๆ 👇" if lang != "en" else "Read the full guide 👇"
    d = (desc or "").strip()
    if len(d) > 160:
        d = d[:157].rstrip() + "…"
    lines = [hook, "", title]
    if d:
        lines += ["", d]
    lines += ["", cta]
    return "\n".join(x for x in lines if x is not None)


@celery_app.task(name="app.worker.tasks.social_push")
def social_push(project_id: int = 0, per_project: int = 1) -> str:
    """♻️ (beat/แมนนวล) กระจายบทความที่เผยแพร่แล้วไปช่องโซเชียลที่ 'ยังไม่เคยโพสต์' — ดริปวันละไม่กี่ชิ้น กันสแปม"""
    return _run(_social_push(project_id, per_project))


async def _social_push(project_id: int, per_project: int) -> str:
    from app.db.models import Project
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        if project_id:
            pids = [project_id] if await s.get(Project, project_id) else []
        else:
            pids = list((await s.execute(select(Project.id).where(Project.active == True))).scalars().all())
    total = 0
    for pid in pids:
        try:
            total += await _social_push_one(pid, per_project)
        except Exception:  # noqa: BLE001 — โปรเจ็คเดียวล้ม ไม่ให้ทั้งชุดพัง
            continue
    return "social push: posted %d item(s) across %d project(s)" % (total, len(pids))


async def _social_push_one(project_id: int, per_project: int) -> int:
    from app.db.models import Project, Article, DistributionChannel, DistributionEvent
    async with db.session() as s:
        proj = await s.get(Project, project_id)
        if not proj:
            return 0
        chans = (await s.execute(select(DistributionChannel).where(
            DistributionChannel.project_id == project_id,
            DistributionChannel.enabled == True))).scalars().all()   # noqa: E712
        targets = [(c.kind, crypto.dec(c.token_enc), c.ref) for c in chans
                   if c.kind in _SOCIAL_KINDS and c.token_enc]
        if not targets:
            return 0                                     # ไม่มีช่องโซเชียลที่ต่อไว้ → เงียบ (opt-in ด้วยการต่อช่อง)
        arts = (await s.execute(select(Article).where(
            Article.project_id == project_id, Article.status == "published",
            Article.url != "").order_by(Article.id))).scalars().all()
        done = (await s.execute(select(DistributionEvent.article_id, DistributionEvent.channel).where(
            DistributionEvent.project_id == project_id,
            DistributionEvent.status == "posted"))).all()
    done_set = {(aid, ch) for aid, ch in done}           # โพสต์แล้ว (บทความ×ช่อง) — กันซ้ำ
    lang = "en" if str(getattr(proj, "language", "") or "").lower().startswith("en") else "th"
    posted = 0
    for kind, token, ref in targets:
        if not token:
            continue
        picked = [a for a in arts if (a.id, kind) not in done_set][:max(1, per_project)]
        for a in picked:
            caption = _social_caption(a.title, a.description or "", lang)
            res = await social.dispatch(kind, token, ref, caption, a.url, a.cover_url or "")
            async with db.session() as s:
                s.add(DistributionEvent(article_id=a.id, project_id=project_id, channel=kind,
                                        status="posted" if res.get("ok") else "failed",
                                        url=(res.get("url") or "")[:600], detail=(res.get("detail") or "")[:390]))
                await s.commit()
            if res.get("ok"):
                posted += 1
    return posted


@celery_app.task(name="app.worker.tasks.submit_sitemaps")
def submit_sitemaps() -> str:
    """♻️ (beat) บอก Google/Bing ให้มาเก็บบทความ 'ครบทุกชิ้น' อัตโนมัติ — แก้รูรั่ว 'ผลิตแล้ว Google ไม่เห็น'"""
    return _run(_submit_sitemaps())


async def _submit_sitemaps() -> str:
    """ส่ง sitemap ของทุกโปรเจกต์ active เข้า Google (GSC ถ้าต่อไว้) + ยิง IndexNow ทุก URL (Bing/AI-search)"""
    from app.db.models import Project, Article
    from app.public import project_public_home
    from app.connectors import gsc as _gsc, publish as _pub
    from app import creds as _creds
    if not db.enabled():
        return "DB not configured"
    async with db.session() as s:
        pids = list((await s.execute(select(Project.id).where(Project.active == True))).scalars().all())
    gsc_ok = idx_urls = 0
    for pid in pids:
        try:
            async with db.session() as s:
                proj = await s.get(Project, pid)
                if not proj or not proj.domain:
                    continue
                home = project_public_home(proj)
                urls = list((await s.execute(select(Article.url).where(
                    Article.project_id == pid, Article.status == "published",
                    Article.url != ""))).scalars().all())
            sitemap_url = home.rstrip("/") + "/sitemap.xml"
            g = await _creds.get_creds(pid, "gsc")           # 1) Google Search Console (ตัวหลักฝั่ง Google)
            if g:
                try:
                    await _gsc.submit_sitemap("sc-domain:" + proj.domain, sitemap_url, creds=g)
                    gsc_ok += 1
                except Exception:  # noqa: BLE001
                    pass
            if urls:                                         # 2) IndexNow (Bing/AI) — ยิงทุก URL ในคำขอเดียว
                try:
                    await _pub.indexnow_submit(urls=urls)
                    idx_urls += len(urls)
                except Exception:  # noqa: BLE001
                    pass
        except Exception:  # noqa: BLE001
            continue
    return "sitemaps auto: GSC %d proj · IndexNow %d url" % (gsc_ok, idx_urls)


# ============================================================
# 🩺 Self-Check — เฝ้าระบบ + ซ่อมเบา ๆ อัตโนมัติทุกวัน → เตือน LINE เมื่อมีปัญหา
# ============================================================
@celery_app.task(name="app.worker.tasks.self_check")
def self_check() -> str:
    """🩺 (beat) เช็ค DB/Redis/การผลิต + กู้บทความตั้งเวลาที่ตกค้าง · เตือน LINE เฉพาะเมื่อมีปัญหา (ปกติเงียบ)"""
    return _run(_self_check())


async def _self_check() -> str:
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import func, text as _text
    from app.db.models import Article, Project
    from app.connectors import notify
    from app.config import settings as S
    problems: list[str] = []
    heals: list[str] = []
    # 1) ฐานข้อมูล
    db_ok = False
    if db.enabled():
        try:
            async with db.session() as s:
                await s.execute(_text("SELECT 1"))
            db_ok = True
        except Exception as e:  # noqa: BLE001
            problems.append("🛑 ฐานข้อมูลต่อไม่ได้: %s" % str(e)[:120])
    else:
        problems.append("🛑 ยังไม่ได้ตั้ง DATABASE_URL")
    # 2) Redis / คิวงาน (broker)
    try:
        import redis as _redis
        _redis.from_url(S.redis_url, socket_connect_timeout=3, socket_timeout=3).ping()
    except Exception as e:  # noqa: BLE001
        problems.append("🛑 Redis/คิวงานต่อไม่ได้: %s" % str(e)[:120])
    # 3) การผลิตยังเดินอยู่ไหม + ซ่อมบทความตั้งเวลาที่ถึงกำหนดแต่ค้าง
    if db_ok:
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=48)
            async with db.session() as s:
                nprj = int((await s.execute(select(func.count(Project.id)))).scalar() or 0)
                recent = int((await s.execute(select(func.count(Article.id)).where(Article.created_at >= since))).scalar() or 0)
            if nprj > 0 and recent == 0:
                problems.append("⚠️ ไม่มีบทความใหม่ใน 48 ชม. — วงจรผลิตอาจสะดุด (ตรวจ worker/beat)")
        except Exception:  # noqa: BLE001
            pass
        try:
            r = await _publish_scheduled()               # idempotent — เผยแพร่ที่ถึงกำหนด (ซ่อม)
            if r.startswith("published ") and not r.startswith("published 0 "):
                heals.append("🔧 " + r)
        except Exception:  # noqa: BLE001
            pass
    if not problems and not heals:
        return "self-check: healthy"
    if problems:                                         # เตือน LINE เฉพาะเมื่อมีปัญหาจริง
        body = ["🩺 ระบบ ImVisible — ต้องดู:\n" + "\n".join(problems)]
        if heals:
            body.append("ซ่อมอัตโนมัติแล้ว:\n" + "\n".join(heals))
        try:
            await notify.send_line("\n\n".join(body))
        except Exception:  # noqa: BLE001
            pass
    return "self-check: %d problem(s), %d heal(s)" % (len(problems), len(heals))


async def _save_rank(project_id: int, res: dict):
    from app.db.models import RankSnapshot, Project
    kw = res.get("keyword", "")
    cur = res.get("our_rank")
    on_p1 = bool(res.get("on_page1"))
    async with db.session() as s:
        # อ่านสแนปช็อตล่าสุด 'ก่อนหน้า' ของคีย์นี้ ไว้เทียบว่าขยับขึ้น/เพิ่งติด (ก่อนบันทึกอันใหม่)
        prev = (await s.execute(
            select(RankSnapshot.rank, RankSnapshot.on_page1)
            .where(RankSnapshot.project_id == project_id, RankSnapshot.keyword == kw)
            .order_by(RankSnapshot.checked_at.desc()).limit(1))).first()
        s.add(RankSnapshot(project_id=project_id, keyword=kw, rank=cur, on_page1=on_p1))
        await s.commit()
        proj = await s.get(Project, project_id)
    try:
        await _maybe_alert_rank(proj, kw, prev, cur, on_p1)
    except Exception:  # noqa: BLE001 — แจ้งเตือนล้มต้องไม่กระทบการบันทึกอันดับ
        pass


async def _maybe_alert_rank(proj, kw: str, prev, cur, on_p1: bool):
    """ส่ง SMS แจ้ง 'ข่าวดี' ต่อโปรเจ็ค: ติดหน้า 1 / เพิ่งเริ่มติด / ขยับขึ้น
    เงื่อนไขกันสแปม: ครั้งแรกที่วัด (ไม่มีประวัติ) = ตั้ง baseline เฉย ๆ ไม่แจ้ง · แจ้งเฉพาะที่อยู่ในระยะแข่งได้"""
    if not proj or not getattr(proj, "sms_enabled", False):
        return
    to = (getattr(proj, "sms_to", "") or "").strip()
    if not to or cur is None:                       # ไม่ติดอันดับ = ไม่ใช่ข่าวดี = ไม่แจ้ง
        return
    if prev is None:                                # ครั้งแรกของคีย์นี้ = baseline · ไม่แจ้ง (กันยิงรัวตอนวัดรอบแรก)
        return
    prev_rank, prev_p1 = prev[0], bool(prev[1])
    name = (proj.name or proj.domain or "").strip()
    msg = None
    if on_p1 and not prev_p1:                        # ก้าวข้ามเข้า Top 10
        msg = '🎉 %s: คีย์ "%s" ติดหน้า 1 แล้ว! อันดับ #%d' % (name, kw, cur)
    elif prev_rank is None and cur <= 30:            # ก่อนหน้าไม่ติด → ตอนนี้ติด (ในระยะแข่งได้)
        msg = '📈 %s: คีย์ "%s" เริ่มติดอันดับที่ #%d' % (name, kw, cur)
    elif prev_rank is not None and cur < prev_rank and cur <= 20:   # ขยับขึ้น + อยู่ Top 20
        msg = '⬆️ %s: คีย์ "%s" ขยับขึ้น #%d → #%d' % (name, kw, prev_rank, cur)
    if not msg:
        return
    from app.connectors import notify
    await notify.send_sms(to, msg)


# ---- เพิ่มใน backend/app/worker/tasks.py (beat task · growth import แบบ inline กัน circular) ----
@celery_app.task(name="app.worker.tasks.scan_aeo_study")
def scan_aeo_study() -> dict:
    """📊 #12 Data Study / Digital PR — 'สำรวจความพร้อม AEO ของเว็บไทย' (linkable asset)
    สแกนเว็บไทยจริงเก็บลง DB → aggregate เป็นสถิติที่นักข่าว/บล็อกอ้างอิงได้ (= backlink)
    สัปดาห์ละครั้งพอ (สแกน HTML หน้าแรก + llms.txt จริง) · ตัวเลขจริงล้วน (no-faking)"""
    from app.connectors import growth
    return _run(growth.scan_and_store_study(growth.AEO_STUDY_SEEDS))
