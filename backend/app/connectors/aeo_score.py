"""
AEO/SEO Score Engine (M3) — วัด "ตัวแปรที่ทำให้ติดอันดับเร็ว" จากบทความจริง
================================================================================
คะแนน 0-100 ประกอบจากปัจจัยจัดอันดับที่ "วัดได้จริงจาก HTML" (ไม่เดา ไม่มโน) —
แต่ละปัจจัยบอกน้ำหนัก, ผ่าน/ไม่ผ่าน, และ "วิธีแก้" เพื่อป้อนกลับให้เครื่องยนต์เขียนใหม่

ทำไมปัจจัยพวกนี้ = ติดเร็ว (SEO 2026 + AEO):
  answer-first + answer blocks + FAQ/schema  → ถูกหยิบเป็น Featured Snippet / AI Overview
                                               (มองเห็นเร็วสุด ไม่ต้องรอไต่อันดับ 10 อันดับ)
  topical depth + keyword placement          → Google เข้าใจว่า "หน้านี้ตอบคำนี้ตรง"
  internal links                             → กระจาย link equity ทั่วคลัสเตอร์ = ทั้งกลุ่มติดเร็ว
  schema/definition/entity                   → AEO: AI อ้างอิงได้ทันที
  freshness + media + scannability           → สัญญาณคุณภาพ + engagement

ค่าที่ได้เก็บใน Article.aeo_score (0-100) และแสดง breakdown ให้ลูกค้าเห็นว่าจะดันคะแนนยังไง
"""
import json
import re

_TAG = re.compile(r"<[^>]+>")
_H2 = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.I | re.S)
_H3 = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.I | re.S)
_H1 = re.compile(r"<h1\b", re.I)
_FIRST_P = re.compile(r"<p\b[^>]*>(.*?)</p>", re.I | re.S)
_A_HREF = re.compile(r"""<a\b[^>]*\bhref\s*=\s*("|')(.*?)\1[^>]*>(.*?)</a>""", re.I | re.S)
_LIST_TBL = re.compile(r"<(ul|ol|table)\b", re.I)
_Q_MARK = re.compile(r"(ไหม|อะไร|ยังไง|อย่างไร|ทำไม|ที่ไหน|กี่|เท่าไห|ไหนดี|อันไหน|วิธี|\?|how|what|why|which|when)", re.I)
_THAI = re.compile(r"[฀-๿]")
_DEF = re.compile(r"(\S+\s*คือ\s*\S+|\bคือ\b|\bหมายถึง\b|\bis a\b|\bis an\b|\brefers to\b|\bmeans\b)", re.I)


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", _TAG.sub(" ", html or "")).strip()


def _wc(text: str) -> int:
    return len((text or "").split())


def _depth_units(plain: str):
    """คืน (หน่วยที่ใช้วัด, จำนวน) — ไทยนับตัวอักษร (ไม่มีช่องว่างระหว่างคำ) · อังกฤษนับคำ"""
    if _THAI.search(plain):
        return "chars", len(re.sub(r"\s+", "", plain))
    return "words", _wc(plain)


def _clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _valid_schema(schema_json: str) -> tuple[bool, set]:
    raw = (schema_json or "").strip()
    if not raw:
        return False, set()
    raw = re.sub(r"(?is)</?script[^>]*>", "", raw).strip()
    try:
        data = json.loads(raw)
    except Exception:
        return False, set()
    types = set()

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

    _walk(data)
    return bool(types), types


def score(html: str, *, title: str = "", description: str = "", schema_json: str = "",
          cover_url: str = "", keyword: str = "", target_words: int = 1200,
          age_days=None, freshness_days: int = 120, site_host: str = "") -> dict:
    """ให้คะแนน AEO/SEO 0-100 + breakdown ต่อปัจจัย + วิธีแก้ (ทั้งหมดวัดจาก HTML จริง)"""
    html = html or ""
    plain = _plain(html)
    unit, depth = _depth_units(plain)
    h2s = [_plain(m) for m in _H2.findall(html)]
    h3s = [_plain(m) for m in _H3.findall(html)]
    kw = (keyword or "").strip().lower()
    first_120 = plain[:120].lower()

    factors = []

    def add(key, label, weight, earned, detail, fix=""):
        earned = _clip(earned)
        factors.append({"key": key, "label": label, "weight": weight,
                        "earned": round(earned, 2), "ok": earned >= 0.999,
                        "points": round(weight * earned, 1),
                        "detail": detail, "fix": fix if earned < 0.999 else ""})

    # 1) ANSWER-FIRST — ย่อหน้าแรกตอบตรง กระชับ (Featured Snippet / AI Overview)
    fp = _FIRST_P.search(html)
    fp_txt = _plain(fp.group(1)) if fp else ""
    fp_u = len(re.sub(r"\s+", "", fp_txt)) if unit == "chars" else _wc(fp_txt)
    lo, hi = (140, 520) if unit == "chars" else (30, 90)
    a1 = 1.0 if (fp and lo <= fp_u <= hi) else (0.5 if fp and fp_u >= (lo // 2) else 0.0)
    add("answer_first", "ย่อหน้าแรกตอบตรง (answer-first)", 12, a1,
        "ย่อหน้าแรก ~%d %s" % (fp_u, "อักษร" if unit == "chars" else "คำ") if fp else "ไม่พบย่อหน้าเปิด",
        "เปิดด้วยคำตอบตรง ๆ 40-60 คำ (ไทย ~200-400 อักษร) ก่อนขึ้นหัวข้อแรก — ให้ AI/Google หยิบไปตอบได้ทันที")

    # 2) FAQ + FAQPage schema — snippet + AEO ตัวแรง
    has_faq_sec = ("คำถามที่พบบ่อย" in plain) or ("faq" in plain.lower()) or bool(_Q_MARK.search(" ".join(h2s + h3s)))
    schema_ok, stypes = _valid_schema(schema_json)
    has_faqpage = "FAQPage" in stypes
    f2 = 1.0 if (has_faq_sec and has_faqpage) else (0.5 if (has_faq_sec or has_faqpage) else 0.0)
    add("faq", "ส่วนคำถามที่พบบ่อย + FAQPage schema", 12, f2,
        "FAQ ในเนื้อ: %s · FAQPage schema: %s" % ("มี" if has_faq_sec else "ไม่มี", "มี" if has_faqpage else "ไม่มี"),
        "เพิ่ม H2 'คำถามที่พบบ่อย' 4-8 ข้อ + ฝัง FAQPage JSON-LD ให้ตรงคำถาม-คำตอบ")

    # 3) STRUCTURED DATA — schema valid มี @type
    add("schema", "Structured data (JSON-LD)", 10, 1.0 if schema_ok else 0.0,
        "ชนิด schema: %s" % (", ".join(sorted(stypes)) or "ไม่มี"),
        "ใส่ JSON-LD Article/BlogPosting (+ FAQPage) ที่ valid — ธีมฝังให้อัตโนมัติถ้ามี schema_json")

    # 4) HEADING STRUCTURE — H2 พอ, H3 ซ้อน, ไม่มี H1 (ธีมใส่เอง)
    n_h2 = len(h2s)
    struct = 0.0
    if n_h2 >= 3:
        struct = 1.0
    elif n_h2 >= 1:
        struct = 0.5
    if _H1.search(html):
        struct = min(struct, 0.5)   # มี H1 ในเนื้อ = ผิดหลัก (ธีมมี H1 อยู่แล้ว → ซ้ำ)
    add("headings", "โครงหัวข้อ H2/H3", 8, struct,
        "H2 %d หัวข้อ · H3 %d · %s" % (n_h2, len(h3s), "พบ H1 ในเนื้อ (ควรตัด)" if _H1.search(html) else "ไม่มี H1 ซ้ำ"),
        "จัดโครงเป็น H2 อย่างน้อย 3 หัวข้อ H3 ซ้อนใต้ H2 และห้ามใส่ H1 ในเนื้อ")

    # 5) ANSWER BLOCKS — H2 คำถามตามด้วยย่อหน้าตอบ (self-contained chunk)
    q_h2 = [t for t in h2s if _Q_MARK.search(t)]
    blocks = 0
    for m in _H2.finditer(html):
        seg = html[m.end():m.end() + 400]
        if re.match(r"\s*<p\b", seg, re.I):
            blocks += 1
    ab = _clip(blocks / max(3, n_h2)) if n_h2 else 0.0
    add("answer_blocks", "บล็อกคำตอบใต้หัวข้อ (quotable)", 10, ab,
        "H2 ที่ตามด้วยย่อหน้าตอบ: %d/%d · H2 เชิงคำถาม: %d" % (blocks, n_h2, len(q_h2)),
        "ใต้ทุก H2 (โดยเฉพาะที่เป็นคำถาม) เปิดด้วยย่อหน้าตอบตรง 40-60 คำ ก่อนขยายความ")

    # 6) DEFINITION / ENTITY CLARITY — 'X คือ Y' (AEO ต้องการนิยาม)
    add("definition", "ประโยคนิยาม/entity ('X คือ...')", 6, 1.0 if _DEF.search(plain) else 0.0,
        "พบประโยคนิยาม" if _DEF.search(plain) else "ยังไม่พบประโยคนิยาม",
        "ใส่ประโยคนิยามชัด ๆ ('<คำหลัก> คือ ...') ใกล้ต้นบทความ ให้ AI ยกไปตอบได้")

    # 7) TITLE — ยาว ≤60 + มีคีย์เวิร์ด
    tl = len(title or "")
    t_len_ok = 1.0 if 10 <= tl <= 60 else (0.6 if tl <= 70 else 0.3)
    t_kw_ok = 1.0 if (kw and kw in (title or "").lower()) else (0.5 if not kw else 0.0)
    t7 = round((t_len_ok + t_kw_ok) / 2, 2)
    add("title", "Title tag (ยาว+คีย์เวิร์ด)", 8, t7,
        "ยาว %d ตัวอักษร · คีย์เวิร์ดใน title: %s" % (tl, "มี" if (kw and kw in (title or "").lower()) else "—"),
        "ตั้ง title ≤60 ตัวอักษร วางคีย์เวิร์ดหลักไว้ต้น ๆ")

    # 8) META DESCRIPTION — 80-160
    dl = len(description or "")
    d8 = 1.0 if 80 <= dl <= 160 else (0.5 if 40 <= dl <= 200 else 0.0)
    add("meta_desc", "Meta description", 6, d8,
        "ยาว %d ตัวอักษร" % dl,
        "เขียน meta description 120-160 ตัวอักษร ดึงดูดคลิก มีคีย์เวิร์ด")

    # 9) DEPTH — ความลึกพอชนะคู่แข่ง
    tgt = target_words if unit == "words" else max(2200, target_words * 2)   # ไทยนับอักษร ตั้งเป้าสูงกว่า
    d9 = _clip(depth / tgt) if tgt else 0.0
    add("depth", "ความลึกของเนื้อหา", 10, d9,
        "%d %s (เป้า ~%d)" % (depth, "อักษร" if unit == "chars" else "คำ", tgt),
        "เพิ่มความลึก: ตัวเลข/ราคา/ตัวอย่าง/ขั้นตอน อุด content gap ให้ครบเจตนาการค้นหา")

    # 10) KEYWORD PLACEMENT — ในต้นเรื่อง + ใน H2
    if kw:
        in_intro = kw in first_120
        in_h2 = any(kw in t.lower() for t in h2s)
        k10 = (0.5 if in_intro else 0.0) + (0.5 if in_h2 else 0.0)
        detail = "ใน 120 อักษรแรก: %s · ใน H2: %s" % ("มี" if in_intro else "—", "มี" if in_h2 else "—")
    else:
        k10, detail = 0.5, "ยังไม่ได้ตั้งคีย์เวิร์ดหลักของโปรเจ็ค"
    add("keyword", "วางคีย์เวิร์ดหลัก", 8, k10, detail,
        "วางคีย์เวิร์ดหลักในย่อหน้าแรก (100 คำแรก) และในหัวข้อ H2 อย่างน้อย 1 จุด อย่างเป็นธรรมชาติ")

    # 11) INTERNAL LINKS — ลิงก์ในเนื้อ (กระจาย link equity)
    internal = 0
    for _q, href, _txt in _A_HREF.findall(html):
        h = (href or "").strip().lower()
        if not h or h == "#" or h.startswith("mailto:") or h.startswith("tel:"):
            continue
        if site_host:
            if site_host.lower() in h or h.startswith("/"):
                internal += 1
        elif h.startswith("/") or (not h.startswith("http")):
            internal += 1
        elif site_host == "" and h.startswith("http"):
            internal += 1   # ไม่ทราบ host → นับลิงก์จริงทั้งหมด (interlink ชี้ในไซต์อยู่แล้ว)
    l11 = 1.0 if internal >= 3 else (0.66 if internal == 2 else (0.33 if internal == 1 else 0.0))
    add("internal_links", "ลิงก์ภายในบทความ", 8, l11,
        "ลิงก์ในเนื้อ %d จุด" % internal,
        "ลิงก์ไปบทความอื่นในคลัสเตอร์ 2-4 จุด ด้วย anchor ไทยกลมกลืน (ระบบทำให้อัตโนมัติเมื่อมีบทความพี่น้อง)")

    # 12) MEDIA — มีรูปปก (og:image + engagement)
    add("media", "รูปปก/สื่อ", 6, 1.0 if (cover_url or "").strip() else 0.0,
        "มีรูปปก" if (cover_url or "").strip() else "ยังไม่มีรูปปก",
        "ใส่รูปปก (ใช้เป็น og:image ด้วย) — ระบบสร้างให้อัตโนมัติถ้าตั้งคีย์ ModelArk")

    # 13) SCANNABILITY — มี list/table
    add("scannability", "อ่านง่าย (list/ตาราง)", 6, 1.0 if _LIST_TBL.search(html) else 0.0,
        "มี list/ตาราง" if _LIST_TBL.search(html) else "ยังไม่มี list/ตาราง",
        "ใช้ <ul>/<ol> เมื่อมีขั้นตอน และ <table> เมื่อเทียบราคา/คุณสมบัติ (ช่วยติด snippet)")

    # 14) FRESHNESS — ความสด
    if age_days is None:
        f14, fdetail = 1.0, "บทความใหม่"
    else:
        f14 = 1.0 if age_days <= freshness_days else _clip(1 - (age_days - freshness_days) / max(freshness_days, 1))
        fdetail = "อายุ %d วัน (เกณฑ์สด %d วัน)" % (age_days, freshness_days)
    add("freshness", "ความสดของเนื้อหา", 4, f14, fdetail,
        "อัปเดตเนื้อหา/ตัวเลข/ปี ให้สดเมื่อเกิน %d วัน (Freshness Engine ทำให้อัตโนมัติ)" % freshness_days)

    total_w = sum(f["weight"] for f in factors)
    earned = sum(f["points"] for f in factors)
    pct = int(round(earned / total_w * 100)) if total_w else 0
    grade = "A" if pct >= 85 else "B" if pct >= 70 else "C" if pct >= 55 else "D"
    top_fixes = [{"label": f["label"], "fix": f["fix"], "gain": round(f["weight"] * (1 - f["earned"]), 1)}
                 for f in factors if not f["ok"]]
    top_fixes.sort(key=lambda x: x["gain"], reverse=True)
    return {
        "score": pct, "grade": grade,
        "passed": sum(1 for f in factors if f["ok"]), "total": len(factors),
        "factors": factors,
        "top_fixes": top_fixes[:6],
        "note": "คะแนนคำนวณจากปัจจัยจัดอันดับที่วัดได้จริงจากบทความ (ไม่ใช่ค่าประเมินลอย ๆ)",
    }
