"""
Site Intelligence — "ใส่แค่ลิงก์" ให้เป็นจริง
================================================
1) เปิดอ่านเว็บลูกค้าจริง (หน้าแรก + about/บริการ/สินค้า)
2) ให้ LLM สกัด "บริบทธุรกิจ" : ทำอะไร · ขายอะไร · พื้นที่ · กลุ่มเป้าหมาย · โทน · คำแบรนด์ · คีย์เวิร์ดตั้งต้น
3) วางแผนหัวข้อ (topical map) เรียงตาม "คำที่ชนะได้ก่อน" → ออโต้ลูปหยิบไปเขียนตามแผน

ไม่มีอะไรถูกกุ: ถ้าอ่านเว็บไม่ได้ จะคืนค่าว่าง แล้วระบบถอยไปใช้ชื่อโปรเจ็คเหมือนเดิม
"""
import ipaddress
import json
import re
from urllib.parse import urljoin, urlparse

import httpx

from app.connectors import content

_BLOCK_HOSTS = {"localhost", "metadata.google.internal", "metadata"}


def _public_host(host: str) -> bool:
    """กัน SSRF: โดเมนมาจากที่ลูกค้ากรอกเอง → ห้ามยิงเข้าเครือข่ายภายใน/metadata"""
    h = (host or "").strip().lower()
    if not h or h in _BLOCK_HOSTS or h.endswith(".local") or h.endswith(".internal"):
        return False
    if "." not in h:                      # ต้องเป็นโดเมนจริง ไม่ใช่ชื่อเครื่องภายใน
        return False
    try:
        ip = ipaddress.ip_address(h)
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
                or ip.is_multicast or ip.is_unspecified):
            return False
    except ValueError:
        pass                              # เป็น hostname ปกติ
    return True

_UA = {"User-Agent": "Mozilla/5.0 (compatible; ImVisibleBot/1.0; +https://imvisible.tech)"}
_HINT = ("about", "เกี่ยวกับ", "service", "บริการ", "product", "สินค้า", "menu", "เมนู",
         "package", "แพ็กเกจ", "price", "ราคา", "course", "คอร์ส")


def _strip_html(html: str) -> str:
    h = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html or "")
    h = re.sub(r"(?is)<!--.*?-->", " ", h)
    h = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6])>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")
    h = re.sub(r"[ \t]+", " ", h)
    h = re.sub(r"\n\s*\n+", "\n", h)
    return h.strip()


def _norm(domain: str) -> str:
    d = (domain or "").strip().lower()
    d = re.sub(r"^https?://", "", d).split("/")[0]
    return d


async def fetch_site(domain: str, max_pages: int = 4, timeout: int = 20) -> dict:
    """ดึงหน้าแรก + หน้าที่น่าจะบอกว่าธุรกิจทำอะไร · คืน {ok, text, title, pages}"""
    host = _norm(domain)
    if not host or not _public_host(host):        # กัน SSRF (โดเมนมาจากลูกค้า)
        return {"ok": False, "text": "", "title": "", "pages": [], "note": "โดเมนไม่ถูกต้อง/ไม่ปลอดภัย"}
    base = "https://" + host
    seen, texts, pages, title = set(), [], [], ""
    async with httpx.AsyncClient(timeout=timeout, headers=_UA, follow_redirects=True) as c:
        try:
            r = await c.get(base)
            r.raise_for_status()
            home = r.text
        except Exception:  # noqa: BLE001
            return {"ok": False, "text": "", "title": "", "pages": []}
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", home)
        title = _strip_html(m.group(1)) if m else ""
        texts.append(_strip_html(home)[:6000])
        pages.append(base)
        seen.add(base.rstrip("/"))

        # เก็บลิงก์ภายในที่น่าจะเป็นหน้า about/บริการ/สินค้า
        cands = []
        for href in re.findall(r'(?i)<a[^>]+href=["\']([^"\'#]+)', home):
            u = urljoin(base, href)
            if urlparse(u).hostname != urlparse(base).hostname:
                continue
            low = u.lower()
            if any(k in low for k in _HINT) and u.rstrip("/") not in seen:
                cands.append(u); seen.add(u.rstrip("/"))
            if len(cands) >= max_pages - 1:
                break
        for u in cands:
            try:
                rr = await c.get(u)
                if rr.status_code == 200:
                    texts.append(_strip_html(rr.text)[:4000]); pages.append(u)
            except Exception:  # noqa: BLE001
                continue
    return {"ok": True, "text": "\n\n".join(texts)[:14000], "title": title, "pages": pages}


_ANALYZE_SYS = (
    "คุณเป็นนักวางกลยุทธ์ SEO/AEO ที่อ่านเว็บไซต์แล้วสรุป 'ธุรกิจนี้คือใคร ขายอะไร ให้ใคร' อย่างแม่นยำ "
    "ห้ามเดาเกินจากข้อมูลที่เห็น ถ้าข้อมูลไม่พอให้เว้นว่าง/ใส่ค่าที่มั่นใจเท่านั้น "
    "ตอบเป็น JSON เท่านั้น ไม่มีข้อความอื่น"
)
_ANALYZE_USER = (
    "โดเมน: {domain}\nชื่อที่ลูกค้าตั้ง: {name}\nTitle เว็บ: {title}\n\n"
    "เนื้อหาที่ดึงจากเว็บ:\n---\n{text}\n---\n\n"
    "สรุปเป็น JSON ตามนี้ (ภาษา{lang}):\n"
    "{{\n"
    '  "business": "ธุรกิจนี้ทำอะไร 1-2 ประโยค",\n'
    '  "offerings": ["บริการ/สินค้าหลัก อย่างละสั้นๆ (3-8 ข้อ)"],\n'
    '  "location": "พื้นที่ให้บริการ (ถ้าไม่ระบุใส่ค่าว่าง)",\n'
    '  "audience": "กลุ่มลูกค้าเป้าหมาย",\n'
    '  "tone": "โทนการสื่อสารที่เหมาะ",\n'
    '  "brand_terms": ["คำที่ใช้ตรวจว่า AI พูดถึงแบรนด์นี้ (ชื่อแบรนด์/ชื่อเว็บ/ชื่อเรียกอื่น 2-5 คำ)"],\n'
    '  "seed_keywords": ["คีย์เวิร์ดตั้งต้นที่ธุรกิจนี้ควรติด (6-12 คำ ที่คนค้นหาจริง ไม่ใช่ชื่อแบรนด์)"]\n'
    "}}"
)


def _json_or_none(text: str):
    try:
        return json.loads(content._strip_fence(text))
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", text or "", re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:  # noqa: BLE001
                return None
        return None


async def analyze(domain: str, name: str = "", language: str = "ภาษาไทย") -> dict:
    """อ่านเว็บจริง → สกัดบริบทธุรกิจ · คืน {} ถ้าอ่านไม่ได้/วิเคราะห์ไม่ได้ (ระบบจะ fallback เอง)"""
    site = await fetch_site(domain)
    if not site.get("ok") or len(site.get("text") or "") < 120:
        return {}
    user = _ANALYZE_USER.format(domain=_norm(domain), name=name or "-", title=site.get("title") or "-",
                                text=site.get("text"), lang=language)
    try:
        _prov, out = await content._llm(_ANALYZE_SYS, user, tier="strong")
    except Exception:  # noqa: BLE001
        return {}
    data = _json_or_none(out)
    if not isinstance(data, dict):
        return {}
    data["_pages_read"] = site.get("pages") or []
    data["_title"] = site.get("title") or ""
    return data


_PLAN_SYS = (
    "คุณเป็นนักวางแผนคอนเทนต์ SEO/AEO ที่เก่งเรื่อง 'เลือกคำที่ชนะได้ก่อน' (long-tail ก่อน head term) "
    "และจัดกลุ่มเป็นคลัสเตอร์เพื่อสะสม topical authority ตอบเป็น JSON เท่านั้น"
)
_PLAN_USER = (
    "บริบทธุรกิจ:\n{ctx}\n\nคำถามจริงที่คนค้นหา (จาก Google Suggest/PAA):\n{questions}\n\n"
    "วางแผนหัวข้อบทความ 20 หัวข้อ (ภาษา{lang}) เป็น JSON:\n"
    '{{"plan":[{{"topic":"หัวข้อบทความที่จะเขียน (เป็นคำถาม/คำค้นที่คนหาจริง)",'
    '"cluster":"ชื่อคลัสเตอร์","intent":"informational|commercial|transactional",'
    '"priority":1}}]}}\n\n'
    "กติกา: priority 1 = ควรเขียนก่อนสุด (แข่งง่าย ใกล้เงิน) → 20 = ทีหลัง · "
    "หัวข้อต้องเจาะจงพอที่จะติดจริง ห้ามกว้างลอย ๆ · ห้ามใส่ชื่อแบรนด์ตัวเองเป็นหัวข้อหลัก"
)


async def build_plan(ctx: dict, questions=None, language: str = "ภาษาไทย") -> list:
    """สร้างแผนหัวข้อจากบริบทธุรกิจ + คำถามจริง · คืน [] ถ้าทำไม่ได้"""
    if not ctx:
        return []
    ctx_txt = json.dumps({k: v for k, v in ctx.items() if not k.startswith("_")}, ensure_ascii=False)
    qs = "\n".join(("- " + q) for q in (questions or [])[:25]) or "(ไม่มี)"
    try:
        _prov, out = await content._llm(_PLAN_SYS, _PLAN_USER.format(ctx=ctx_txt, questions=qs, lang=language),
                                        tier="fast")
    except Exception:  # noqa: BLE001
        return []
    data = _json_or_none(out)
    plan = (data or {}).get("plan") if isinstance(data, dict) else None
    if not isinstance(plan, list):
        return []
    out_plan = []
    for it in plan:
        if isinstance(it, dict) and it.get("topic"):
            out_plan.append({"topic": str(it.get("topic"))[:300],
                             "cluster": str(it.get("cluster") or "")[:120],
                             "intent": str(it.get("intent") or "")[:30],
                             "priority": int(it.get("priority") or 99)})
    out_plan.sort(key=lambda x: x["priority"])
    return out_plan[:30]


def context_text(ctx: dict) -> str:
    """แปลงบริบทเป็นข้อความสั้นสำหรับป้อนเครื่องยนต์คอนเทนต์ (business_context)"""
    if not ctx:
        return ""
    parts = []
    if ctx.get("business"):
        parts.append("ธุรกิจ: " + str(ctx["business"]))
    off = ctx.get("offerings")
    if isinstance(off, list) and off:
        parts.append("บริการ/สินค้า: " + ", ".join(str(o) for o in off[:8]))
    if ctx.get("location"):
        parts.append("พื้นที่: " + str(ctx["location"]))
    if ctx.get("audience"):
        parts.append("กลุ่มเป้าหมาย: " + str(ctx["audience"]))
    if ctx.get("tone"):
        parts.append("โทน: " + str(ctx["tone"]))
    return " · ".join(parts)[:1500]
