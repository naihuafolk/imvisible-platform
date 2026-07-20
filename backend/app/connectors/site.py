"""
Site Intelligence — "ใส่แค่ลิงก์" ให้เป็นจริง
================================================
1) เปิดอ่านเว็บลูกค้าจริง (หน้าแรก + about/บริการ/สินค้า)
2) ให้ LLM สกัด "บริบทธุรกิจ" : ทำอะไร · ขายอะไร · พื้นที่ · กลุ่มเป้าหมาย · โทน · คำแบรนด์ · คีย์เวิร์ดตั้งต้น
3) วางแผนหัวข้อ (topical map) เรียงตาม "คำที่ชนะได้ก่อน" → ออโต้ลูปหยิบไปเขียนตามแผน

ไม่มีอะไรถูกกุ: ถ้าอ่านเว็บไม่ได้ จะคืนค่าว่าง แล้วระบบถอยไปใช้ชื่อโปรเจ็คเหมือนเดิม
"""
import asyncio
import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx

from app.connectors import content

_BLOCK_HOSTS = {"localhost", "metadata.google.internal", "metadata"}


def _clean_host(raw: str) -> str:
    """แยก host จริงออกจาก scheme / userinfo / port / วงเล็บ IPv6"""
    h = (raw or "").strip().lower()
    h = re.sub(r"^[a-z]+://", "", h).split("/")[0].split("?")[0]
    if "@" in h:                                   # ตัด user:pass@
        h = h.rsplit("@", 1)[-1]
    if h.startswith("["):                          # [IPv6]:port
        end = h.find("]")
        return h[1:end] if end > 0 else ""
    if h.count(":") == 1:                          # host:port
        h = h.split(":")[0]
    return h


def _ip_ok(addr: str) -> bool:
    """IP นี้เป็น public จริงไหม (รวมกรณี IPv4-mapped IPv6)"""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped:
        ip = mapped
    return not (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def _resolve_ok(host: str) -> bool:
    """resolve จริงแล้วตรวจ 'ทุก' IP ที่ได้ — กัน DNS ที่ชี้เข้าเครือข่ายภายใน (เช่น 10.x.x.x.nip.io)"""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except Exception:  # noqa: BLE001
        return False
    if not infos:
        return False
    for info in infos:
        if not _ip_ok(info[4][0]):
            return False
    return True


async def host_allowed(raw: str) -> bool:
    """กัน SSRF ให้ครบ: ตัด port/วงเล็บ → ถ้าเป็น IP ตรวจตรง → ถ้าเป็นชื่อโดเมน resolve แล้วตรวจทุก IP"""
    h = _clean_host(raw)
    if not h or h in _BLOCK_HOSTS or h.endswith(".local") or h.endswith(".internal"):
        return False
    try:
        ipaddress.ip_address(h)                    # เป็น IP literal → ตรวจตรงเลย
        return _ip_ok(h)
    except ValueError:
        pass
    if "." not in h:
        return False
    return await asyncio.to_thread(_resolve_ok, h)  # DNS ไม่บล็อก event loop


async def _get_guarded(client, url: str, max_hops: int = 3):
    """GET โดยตรวจ 'ทุก hop' ของ redirect เอง (httpx ตามเองไม่ได้ — มันข้ามการตรวจ)"""
    cur = url
    for _ in range(max_hops + 1):
        if not cur.lower().startswith("https://"):  # ห้าม downgrade เป็น http
            return None
        if not await host_allowed(cur):
            return None
        r = await client.get(cur)
        if r.status_code in (301, 302, 303, 307, 308):
            loc = r.headers.get("location") or ""
            if not loc:
                return None
            cur = urljoin(cur, loc)
            continue
        return r
    return None

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
    host = _clean_host(domain)
    if not host or not await host_allowed(host):   # กัน SSRF (โดเมนมาจากลูกค้ากรอกเอง)
        return {"ok": False, "text": "", "title": "", "pages": [], "note": "โดเมนไม่ถูกต้อง/ไม่ปลอดภัย"}
    base = "https://" + host
    seen, texts, pages, title = set(), [], [], ""
    # follow_redirects=False โดยตั้งใจ — เราตามเองผ่าน _get_guarded เพื่อตรวจทุก hop
    async with httpx.AsyncClient(timeout=timeout, headers=_UA, follow_redirects=False) as c:
        try:
            r = await _get_guarded(c, base)
            if r is None or r.status_code != 200:
                return {"ok": False, "text": "", "title": "", "pages": []}
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
                rr = await _get_guarded(c, u)
                if rr is not None and rr.status_code == 200:
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


def _prio(v) -> int:
    """LLM มักตอบ priority เป็น '1 (แข่งง่าย)' / 'high' / '1-3' → ต้องแปลงแบบไม่ระเบิด"""
    try:
        s = str(v if v is not None else 99).strip()
        m = re.search(r"\d+", s)
        return int(m.group(0)) if m else 99
    except Exception:  # noqa: BLE001
        return 99


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
                             "priority": _prio(it.get("priority"))})
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
