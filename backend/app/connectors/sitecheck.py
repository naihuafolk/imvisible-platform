"""
Site Health Check (สาธารณะ) — "ใส่ลิงก์ → ประเมินจริง"
=========================================================
อ่านหน้าแรกของเว็บลูกค้า 'จริง' (กัน SSRF ผ่าน app.connectors.site) แล้วให้คะแนน
SEO/AEO 0-100 จากปัจจัยที่ "วัดได้จริงจาก HTML" เท่านั้น — ไม่มีการกุคะแนน
ถ้าเปิดเว็บไม่ได้ = บอกตรง ๆ (ok=False) ไม่เดา

พร้อมประเมิน 'การครอบคลุมคีย์เวิร์ดบนหน้าเพจ' ที่ลูกค้าอยากติด — คือหน้าแรกพูดถึง
คำนั้นครบแค่ไหน (title/description/หัวข้อ/เนื้อ) — ไม่ใช่อันดับ Google จริง
(อันดับจริงเราวัดด้วย DataForSEO ตอนเป็นลูกค้า) → ซื่อสัตย์ตามหลัก no-faking
"""
import json
import re

import httpx

from app.connectors import site

_TITLE = re.compile(r"(?is)<title[^>]*>(.*?)</title>")
_META = re.compile(r"(?is)<meta\b[^>]*>")
_ATTR_NAME = re.compile(r"""(?is)\bname\s*=\s*("|')\s*description\s*\1""")
_ATTR_CONTENT = re.compile(r"""(?is)\bcontent\s*=\s*("|')(.*?)\1""")
_VIEWPORT = re.compile(r"""(?is)<meta\b[^>]*\bname\s*=\s*("|')\s*viewport\s*\1""")
_HTML_LANG = re.compile(r"""(?is)<html\b[^>]*\blang\s*=\s*("|')([^"']+)\1""")
_H1 = re.compile(r"(?is)<h1\b[^>]*>(.*?)</h1>")
_H2 = re.compile(r"(?is)<h2\b[^>]*>(.*?)</h2>")
_H3 = re.compile(r"(?is)<h3\b[^>]*>(.*?)</h3>")
_JSONLD = re.compile(r"""(?is)<script\b[^>]*type\s*=\s*("|')application/ld\+json\1[^>]*>(.*?)</script>""")
_OG_IMG = re.compile(r"""(?is)<meta\b[^>]*\bproperty\s*=\s*("|')\s*og:image\s*\1""")
_OG_TITLE = re.compile(r"""(?is)<meta\b[^>]*\bproperty\s*=\s*("|')\s*og:title\s*\1""")
_CANONICAL = re.compile(r"""(?is)<link\b[^>]*\brel\s*=\s*("|')\s*canonical\s*\1""")
_IMG = re.compile(r"(?is)<img\b[^>]*>")
_HAS_ALT = re.compile(r"""(?is)\balt\s*=\s*("|')""")
_FAVICON = re.compile(r"""(?is)<link\b[^>]*\brel\s*=\s*("|')[^"']*icon[^"']*\1""")
_TAGSTRIP = re.compile(r"<[^>]+>")
_THAI = re.compile(r"[฀-๿]")
# หัวข้อที่เป็น 'คำถาม' → AI ชอบหยิบเนื้อหาแบบถาม-ตอบไปแนะนำ (สัญญาณ AEO)
_Q_WORDS = re.compile(r"(?i)(ไหม|อะไร|ยังไง|อย่างไร|ทำไม|เท่าไ|ที่ไหน|เมื่อไ|กี่|วิธี|how |what |why |where |when |which |\?)")
# schema ที่บอก 'ตัวตนแบรนด์' → AI ยืนยันว่ามีตัวตนจริง (สัญญาณ AEO/entity)
_AEO_ENTITY = {"Organization", "WebSite", "LocalBusiness", "Corporation", "ProfessionalService",
               "Store", "OnlineStore", "OnlineBusiness", "NGO", "EducationalOrganization"}


def _tag(html: str) -> str:
    return re.sub(r"\s+", " ", _TAGSTRIP.sub(" ", html or "")).strip()


async def _fetch_home(url: str):
    """ดึง HTML หน้าแรกจริง (กัน SSRF + ตามทุก redirect hop) · คืน (base_url, html, error)"""
    host = site._clean_host(url)
    if not host or "." not in host:
        return "", "", "ลิงก์ไม่ถูกต้อง — ใส่โดเมนเว็บของคุณ เช่น yourshop.com"
    if not await site.host_allowed(host):
        return "", "", "โดเมนนี้เปิดตรวจไม่ได้ (ต้องเป็นเว็บสาธารณะที่รองรับ https)"
    base = "https://" + host
    async with httpx.AsyncClient(timeout=20, headers=site._UA, follow_redirects=False) as c:
        try:
            r = await site._get_guarded(c, base)
        except Exception:  # noqa: BLE001
            return base, "", "เปิดเว็บไม่ได้ — ตรวจว่าเว็บออนไลน์อยู่และรองรับ https"
        if r is None:
            return base, "", "เปิดเว็บไม่ได้ — เว็บอาจ redirect ไป http หรือปลายทางไม่ปลอดภัย"
        if r.status_code != 200:
            return base, "", "เว็บตอบกลับสถานะ %d (ไม่ใช่หน้าปกติ)" % r.status_code
        return base, (r.text or "")[:600000], ""


async def _has_llms_txt(base: str) -> bool:
    """เช็กว่าเว็บมี /llms.txt (มาตรฐานใหม่บอก AI ว่าเนื้อหาสำคัญอยู่ตรงไหน) — best-effort ล้มเงียบ"""
    try:
        async with httpx.AsyncClient(timeout=8, headers=site._UA, follow_redirects=False) as c:
            r = await site._get_guarded(c, base.rstrip("/") + "/llms.txt")
        return bool(r is not None and r.status_code == 200 and (r.text or "").strip())
    except Exception:  # noqa: BLE001
        return False


def _schema_types(html: str) -> tuple[bool, bool, set]:
    """คืน (มี JSON-LD ที่ valid, มี FAQPage, ชนิด schema ทั้งหมด)"""
    types: set = set()
    ok = False

    def _walk(o):
        if isinstance(o, dict):
            t = o.get("@type")
            if isinstance(t, str):
                types.add(t)
            elif isinstance(t, list):
                types.update(str(x) for x in t)
            for v in o.values():
                _walk(v)
        elif isinstance(o, list):
            for v in o:
                _walk(v)

    for _q, body in _JSONLD.findall(html):
        raw = (body or "").strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:  # noqa: BLE001
            continue
        ok = True
        _walk(data)
    return (ok and bool(types)), ("FAQPage" in types), types


def _meta_description(html: str) -> str:
    for m in _META.finditer(html):
        tag = m.group(0)
        if _ATTR_NAME.search(tag):
            cm = _ATTR_CONTENT.search(tag)
            if cm:
                return _tag(cm.group(2))
    return ""


def _keyword_rows(kws, title, desc, heads_txt, body_txt):
    """ประเมินการครอบคลุมคีย์เวิร์ดบน 'หน้าเพจ' (ไม่ใช่อันดับจริง)"""
    rows = []
    t, d, h, b = title.lower(), desc.lower(), heads_txt.lower(), body_txt.lower()
    for kw in kws:
        k = kw.lower().strip()
        if not k:
            continue
        in_title = k in t
        in_desc = k in d
        in_head = k in h
        in_body = k in b
        cov = (0.35 * in_title) + (0.15 * in_desc) + (0.25 * in_head) + (0.25 * in_body)
        if cov >= 0.5:
            label, tone = "ครอบคลุมดี", "ok"
        elif cov > 0:
            label, tone = "พอมี ยังเสริมได้", "warn"
        else:
            label, tone = "ยังไม่พบบนหน้าแรกเลย", "fail"
        rows.append({
            "keyword": kw, "coverage": round(cov, 2), "label": label, "tone": tone,
            "in_title": in_title, "in_desc": in_desc, "in_heading": in_head, "in_body": in_body,
        })
    return rows


async def check_url(url: str, keywords=None) -> dict:
    """ตรวจสุขภาพเว็บหน้าแรกจริง → คะแนน + รายการปัจจัย + วิธีแก้ + การครอบคลุมคีย์เวิร์ด"""
    kws = [str(k).strip() for k in (keywords or []) if str(k).strip()][:3]
    base, html, err = await _fetch_home(url)
    if err or not html:
        return {"ok": False, "url": base or url, "note": err or "อ่านเว็บไม่ได้"}

    title = _tag(_TITLE.search(html).group(1)) if _TITLE.search(html) else ""
    desc = _meta_description(html)
    h1s = [_tag(x) for x in _H1.findall(html)]
    h2s = [_tag(x) for x in _H2.findall(html)]
    h3s = [_tag(x) for x in _H3.findall(html)]
    heads_txt = " ".join(h1s + h2s + h3s)
    body_txt = _tag(re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html))
    thai = bool(_THAI.search(body_txt))
    depth = len(re.sub(r"\s+", "", body_txt)) if thai else len(body_txt.split())
    depth_lo = 900 if thai else 250            # หน้าแรกบางเบามาก = สัญญาณผอม
    schema_ok, has_faq, stypes = _schema_types(html)
    imgs = _IMG.findall(html)
    imgs_alt = sum(1 for t in imgs if _HAS_ALT.search(t))
    # 🕵️ ตรวจจับ JS app/SPA: เนื้อหา HTML ดิบบางมาก + สคริปต์เยอะ = เนื้อหาโหลดด้วย JS (อ่านไม่ครบ คะแนนต่ำกว่าจริง)
    _scripts = len(re.findall(r"(?is)<script[\s>]", html))
    js_app = (depth < depth_lo * 0.45) and (_scripts >= 3)

    factors = []

    def add(key, label, weight, earned, detail, fix=""):
        earned = max(0.0, min(1.0, earned))
        tone = "ok" if earned >= 0.999 else ("warn" if earned >= 0.5 else "fail")
        factors.append({"key": key, "label": label, "weight": weight, "earned": round(earned, 2),
                        "tone": tone, "points": round(weight * earned, 1),
                        "detail": detail, "fix": fix if earned < 0.999 else ""})

    # 1) HTTPS — ดึงผ่าน https สำเร็จ = ผ่าน (เราไม่ยอม downgrade เป็น http)
    add("https", "ความปลอดภัย HTTPS", 8, 1.0, "เปิดผ่าน https ได้ (มี SSL)")

    # 2) TITLE
    tl = len(title)
    t2 = 1.0 if 10 <= tl <= 60 else (0.5 if title else 0.0)
    add("title", "Title tag", 12, t2,
        ("ยาว %d ตัวอักษร: “%s”" % (tl, title[:70])) if title else "ไม่พบ <title>",
        "ตั้ง title 30–60 ตัวอักษร ใส่คีย์เวิร์ดหลัก + ชื่อแบรนด์" if t2 < 0.999 else "")

    # 3) META DESCRIPTION
    dl = len(desc)
    d3 = 1.0 if 80 <= dl <= 160 else (0.5 if desc else 0.0)
    add("meta_desc", "Meta description", 10, d3,
        ("ยาว %d ตัวอักษร" % dl) if desc else "ไม่พบ meta description",
        "เขียน meta description 120–160 ตัวอักษร ดึงดูดคลิก มีคีย์เวิร์ด" if d3 < 0.999 else "")

    # 4) MOBILE VIEWPORT
    vp = bool(_VIEWPORT.search(html))
    add("viewport", "รองรับมือถือ (viewport)", 10, 1.0 if vp else 0.0,
        "มี meta viewport" if vp else "ไม่พบ meta viewport — มือถืออาจแสดงผลเพี้ยน",
        "เพิ่ม <meta name=viewport content='width=device-width, initial-scale=1'>")

    # 5) HTML LANG
    lg = _HTML_LANG.search(html)
    add("lang", "ระบุภาษา (html lang)", 5, 1.0 if lg else 0.5,
        ("lang=%s" % lg.group(2)) if lg else "ไม่ได้ระบุ lang บน <html>",
        "ใส่ <html lang='th'> เพื่อบอก Google/AI ว่าเป็นภาษาไทย" if not lg else "")

    # 6) H1 — ควรมี 'หนึ่งเดียว'
    n1 = len(h1s)
    h6 = 1.0 if n1 == 1 else (0.5 if n1 > 1 else 0.0)
    add("h1", "หัวข้อหลัก H1", 8, h6,
        ("มี H1 %d จุด%s" % (n1, "" if n1 == 1 else " (ควรมีจุดเดียว)")) if n1 else "ไม่พบ H1",
        "ใส่ H1 เพียงหัวข้อเดียวที่บอกชัดว่าหน้านี้เกี่ยวกับอะไร" if h6 < 0.999 else "")

    # 7) H2 STRUCTURE
    n2 = len(h2s)
    h7 = 1.0 if n2 >= 3 else (0.5 if n2 >= 1 else 0.0)
    add("headings", "โครงหัวข้อ H2", 6, h7,
        "H2 %d หัวข้อ · H3 %d" % (n2, len(h3s)),
        "จัดเนื้อหาเป็นหัวข้อ H2 อย่างน้อย 3 หัวข้อ ให้อ่านง่ายและติด snippet" if h7 < 0.999 else "")

    # 8) STRUCTURED DATA
    s8 = 1.0 if schema_ok else 0.0
    add("schema", "Structured data (JSON-LD)", 12, s8,
        ("ชนิด schema: %s" % ", ".join(sorted(stypes))) if stypes else "ไม่พบ JSON-LD",
        "ฝัง JSON-LD (Organization/WebSite + FAQPage) ให้ Google/AI เข้าใจธุรกิจ" if s8 < 0.999 else "")

    # 9) OPEN GRAPH
    ogt, ogi = bool(_OG_TITLE.search(html)), bool(_OG_IMG.search(html))
    o9 = 1.0 if (ogt and ogi) else (0.5 if (ogt or ogi) else 0.0)
    add("og", "Open Graph (แชร์สวย)", 6, o9,
        "og:title %s · og:image %s" % ("มี" if ogt else "—", "มี" if ogi else "—"),
        "ใส่ og:title + og:image เพื่อให้ลิงก์ที่แชร์บนโซเชียลมีรูป/หัวข้อสวย" if o9 < 0.999 else "")

    # 10) CANONICAL
    cn = bool(_CANONICAL.search(html))
    add("canonical", "Canonical URL", 4, 1.0 if cn else 0.5,
        "มี canonical" if cn else "ไม่พบ canonical",
        "ใส่ <link rel=canonical> กัน Google สับสนหน้าซ้ำ" if not cn else "")

    # 11) IMAGE ALT
    if imgs:
        ratio = imgs_alt / len(imgs)
        i11 = 1.0 if ratio >= 0.8 else (0.5 if ratio > 0 else 0.0)
        det = "รูป %d จุด มี alt %d จุด" % (len(imgs), imgs_alt)
    else:
        i11, det = 1.0, "ไม่มีรูปในหน้าแรก"
    add("img_alt", "คำอธิบายรูป (alt)", 6, i11, det,
        "ใส่ alt ให้รูปทุกจุด บอกว่าเป็นรูปอะไร (ช่วย SEO รูป + คนพิการ)" if i11 < 0.999 else "")

    # 12) CONTENT DEPTH
    c12 = max(0.0, min(1.0, depth / depth_lo))
    add("depth", "ความลึกของเนื้อหา", 8, c12,
        "%d %s ในหน้าแรก" % (depth, "อักษร" if thai else "คำ"),
        "เพิ่มเนื้อหาบอกว่าทำอะไร ให้ใคร มีอะไรเด่น — หน้าแรกที่บางเกินไปติดยาก" if c12 < 0.999 else "")

    # 13) FAVICON
    fv = bool(_FAVICON.search(html))
    add("favicon", "ไอคอนเว็บ (favicon)", 3, 1.0 if fv else 0.5,
        "มี favicon" if fv else "ไม่พบ favicon",
        "ใส่ favicon ให้เว็บดูน่าเชื่อถือบนแท็บและผลค้นหา" if not fv else "")

    # 14) KEYWORD COVERAGE (บนหน้าเพจ — ถ้าลูกค้าใส่คีย์เวิร์ดมา)
    kw_rows = _keyword_rows(kws, title, desc, heads_txt, body_txt)
    if kw_rows:
        kw_earned = sum(r["coverage"] for r in kw_rows) / len(kw_rows)
        add("keywords", "การครอบคลุมคีย์เวิร์ด (บนหน้าเพจ)", 12, kw_earned,
            "ประเมิน %d คีย์เวิร์ดบนหน้าแรก" % len(kw_rows),
            "วางคีย์เวิร์ดที่อยากติดใน title, หัวข้อ และเนื้อหาอย่างเป็นธรรมชาติ")

    total_w = sum(f["weight"] for f in factors)
    earned = sum(f["points"] for f in factors)
    pct = int(round(earned / total_w * 100)) if total_w else 0
    grade = "A" if pct >= 85 else "B" if pct >= 70 else "C" if pct >= 55 else "D"
    fails = sum(1 for f in factors if f["tone"] == "fail")
    warns = sum(1 for f in factors if f["tone"] == "warn")
    top_fixes = [{"label": f["label"], "fix": f["fix"], "gain": round(f["weight"] * (1 - f["earned"]), 1)}
                 for f in factors if f["tone"] != "ok" and f["fix"]]
    top_fixes.sort(key=lambda x: x["gain"], reverse=True)

    issues = fails + warns
    if issues == 0:
        summary = "เว็บคุณพื้นฐานแน่นมาก (เกรด %s) — ก้าวต่อไปคือดันให้ 'ติดอันดับ' และ 'ถูก AI แนะนำ'" % grade
    else:
        summary = "เว็บคุณได้เกรด %s — เจอ %d จุดที่แก้แล้วดันอันดับได้เร็วขึ้น" % (grade, issues)

    # ================= AEO Readiness (พระเอก): 'พร้อมถูก AI แนะนำแค่ไหน' =================
    has_org = bool(stypes & _AEO_ENTITY)
    q_head = sum(1 for h in (h1s + h2s + h3s) if _Q_WORDS.search(h))
    has_llms = await _has_llms_txt(base)
    aeo_f = []

    def aadd(key, label, weight, earned, detail, fix=""):
        earned = max(0.0, min(1.0, earned))
        tone = "ok" if earned >= 0.999 else ("warn" if earned >= 0.5 else "fail")
        aeo_f.append({"key": key, "label": label, "weight": weight, "earned": round(earned, 2),
                      "tone": tone, "points": round(weight * earned, 1),
                      "detail": detail, "fix": fix if earned < 0.999 else ""})

    aadd("aeo_schema", "ข้อมูลโครงสร้าง JSON-LD (AI อ่านเข้าใจ)", 22, 1.0 if schema_ok else 0.0,
         ("มี schema: %s" % ", ".join(sorted(stypes))) if stypes else "ไม่มี JSON-LD — AI สรุปธุรกิจคุณได้ยาก",
         "ฝัง JSON-LD (Organization + FAQPage) ให้ AI เข้าใจว่าคุณคือใคร ทำอะไร")
    aadd("aeo_entity", "ตัวตนแบรนด์ (Organization schema)", 16, 1.0 if has_org else 0.0,
         "ประกาศตัวตนแบรนด์แล้ว" if has_org else "ยังไม่ประกาศตัวตนแบรนด์ให้ AI",
         "เพิ่ม Organization schema (ชื่อ โลโก้ โซเชียล) = AI ยืนยันแบรนด์คุณมีตัวตนจริง")
    faq_full = has_faq and q_head >= 2
    aadd("aeo_faq", "เนื้อหาแบบถาม-ตอบ (Q&A / FAQ)", 20, 1.0 if faq_full else (0.6 if (has_faq or q_head >= 2) else 0.0),
         "FAQ schema %s · หัวข้อคำถาม %d จุด" % ("มี" if has_faq else "—", q_head),
         "ทำส่วน 'คำถามที่พบบ่อย' + ฝัง FAQPage schema → AI ชอบหยิบคำตอบ Q&A ไปแนะนำ")
    aadd("aeo_answer", "คำอธิบายแบบตอบคำถามได้ (meta)", 12, d3,
         ("meta description %d ตัวอักษร" % dl) if desc else "ไม่มี meta description",
         "เขียน meta ให้เป็น 'คำตอบสั้นกระชับ' ที่ AI หยิบไปตอบได้ทันที")
    struct_ok = 1.0 if (n1 == 1 and n2 >= 3) else (0.5 if (n1 >= 1 and n2 >= 1) else 0.0)
    aadd("aeo_struct", "โครงหัวข้อชัด (AI แยกประเด็นได้)", 14, struct_ok,
         "H1 %d · H2 %d" % (n1, n2),
         "จัด H1 เดียว + H2 หลายหัวข้อชัดเจน ให้ AI แยกประเด็นไปตอบเป็นข้อ ๆ")
    aadd("aeo_depth", "เนื้อหาพอให้ AI อ้างอิง", 10, c12,
         "%d %s ในหน้าแรก" % (depth, "อักษร" if thai else "คำ"),
         "เพิ่มเนื้อหาเชิงลึก/ข้อเท็จจริงที่ AI เอาไปตอบได้ (ไม่ใช่แค่หน้าโฆษณาบาง ๆ)")
    aadd("aeo_llms", "ไฟล์ llms.txt (มาตรฐาน AI ล่าสุด)", 6, 1.0 if has_llms else 0.0,
         "มี /llms.txt แล้ว" if has_llms else "ยังไม่มี /llms.txt",
         "เพิ่มไฟล์ llms.txt บอก AI ว่าเนื้อหาสำคัญอยู่ตรงไหน (คู่แข่งเกือบทั้งหมดยังไม่ทำ)")

    aeo_w = sum(f["weight"] for f in aeo_f)
    aeo_pts = sum(f["points"] for f in aeo_f)
    aeo_score = int(round(aeo_pts / aeo_w * 100)) if aeo_w else 0
    aeo_grade = "A" if aeo_score >= 85 else "B" if aeo_score >= 70 else "C" if aeo_score >= 55 else "D"
    aeo_fixes = [{"label": f["label"], "fix": f["fix"], "gain": round(f["weight"] * (1 - f["earned"]), 1)}
                 for f in aeo_f if f["tone"] != "ok" and f["fix"]]
    aeo_fixes.sort(key=lambda x: x["gain"], reverse=True)
    if aeo_score >= 85:
        aeo_summary = "พร้อมมากที่จะถูก AI แนะนำ (AEO %d/100) — นำหน้าคู่แข่งส่วนใหญ่ในสนาม AI" % aeo_score
    elif aeo_score >= 55:
        aeo_summary = "มีพื้นฐาน AEO แล้ว (%d/100) แต่ยังเปิดช่องให้ AI หยิบไปแนะนำได้มากกว่านี้" % aeo_score
    else:
        aeo_summary = "ยังไม่พร้อมให้ AI แนะนำ (AEO %d/100) — นี่คือโอกาส blue-ocean ที่คู่แข่งยังไม่ทำ" % aeo_score

    return {
        "ok": True, "url": base, "title": title,
        "score": pct, "grade": grade,
        "passed": sum(1 for f in factors if f["tone"] == "ok"), "total": len(factors),
        "fails": fails, "warns": warns,
        "factors": factors, "top_fixes": top_fixes[:6],
        "keywords": kw_rows,
        "summary": summary,
        # AEO Readiness (ชูเป็นพระเอก) — 'พร้อมถูก AI แนะนำแค่ไหน'
        "aeo_score": aeo_score, "aeo_grade": aeo_grade,
        "aeo_factors": aeo_f, "aeo_fixes": aeo_fixes[:6], "aeo_summary": aeo_summary,
        "js_app": js_app,   # true = เว็บนี้เป็น JS app/SPA → อ่านเนื้อหาไม่ครบ คะแนนอาจต่ำกว่าจริง (เตือนผู้ใช้)
        "note": "คะแนนคำนวณจากปัจจัยที่วัดได้จริงจากหน้าแรกของเว็บคุณ (ไม่ใช่ค่าประเมินลอย ๆ) · "
                "การครอบคลุมคีย์เวิร์ดเป็นการวัด 'บนหน้าเพจ' ไม่ใช่อันดับ Google จริง — "
                "อันดับจริงเราวัดด้วยเครื่องมือระดับมืออาชีพให้ตอนเป็นลูกค้า",
    }
