"""
SERP connector — ดึงผลอันดับ Google จริงผ่าน DataForSEO
เอกสาร: https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/
ใช้วัด "อันดับ / ติดหน้า 1" (M5) และประกอบการขุดคำถาม (M1)
"""
import base64
import httpx

from app.config import settings

BASE = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"


def _auth_header(creds: dict | None = None) -> dict:
    # คีย์ของลูกค้า (per-project) ก่อน → ไม่มีค่อย fallback คีย์กลางของแพลตฟอร์ม
    login = (creds or {}).get("login") or settings.dataforseo_login
    password = (creds or {}).get("password") or settings.dataforseo_password
    if not (login and password):
        raise RuntimeError("ยังไม่ได้ตั้งค่า DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD (คีย์ลูกค้าหรือคีย์กลาง)")
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


async def account_balance(creds: dict | None = None) -> float | None:
    """ยอดเงินคงเหลือจริงใน DataForSEO (USD) — ไว้เตือนแอดมินให้เติมเครดิต · crash-safe (None ถ้าดึงไม่ได้)"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.dataforseo.com/v3/appendix/user_data", headers=_auth_header(creds))
            r.raise_for_status()
            data = r.json()
        money = (data["tasks"][0]["result"][0].get("money") or {})
        bal = money.get("balance")
        return float(bal) if bal is not None else None
    except Exception:  # noqa: BLE001
        return None


async def backlinks_summary(domain: str, creds: dict | None = None) -> dict | None:
    """สรุป Backlink 'จริง' ของโดเมน (DataForSEO Backlinks API) — จำนวนลิงก์ · โดเมนอ้างอิง ·
    dofollow · rank · spam score (= ตัวชี้คุณภาพ) · new/lost
    ⚠️ Backlinks เป็นผลิตภัณฑ์แยกของ DataForSEO คิดเครดิตต่างหาก · crash-safe (None ถ้าไม่มีสิทธิ์/พลาด)"""
    target = (domain or "").strip().replace("https://", "").replace("http://", "").strip("/")
    if target.startswith("www."):
        target = target[4:]
    target = target.split("/")[0]
    if not target:
        return None
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.dataforseo.com/v3/backlinks/summary/live",
                headers=_auth_header(creds),
                json=[{"target": target, "internal_list_limit": 10,
                       "backlinks_status_type": "live", "include_subdomains": True}])
            r.raise_for_status()
            data = r.json()
        res = ((data.get("tasks") or [{}])[0].get("result") or [])
        if not res:
            return None
        d = res[0] or {}
        attr = d.get("referring_links_attributes") or {}
        return {
            "target": target,
            "backlinks": d.get("backlinks"),
            "referring_domains": d.get("referring_domains"),
            "referring_main_domains": d.get("referring_main_domains"),
            "referring_domains_nofollow": d.get("referring_domains_nofollow"),
            "dofollow": attr.get("dofollow"),
            "nofollow": attr.get("nofollow"),
            "rank": d.get("rank"),
            "spam_score": d.get("backlinks_spam_score"),
            "new_referring_domains": d.get("new_referring_domains"),
            "lost_referring_domains": d.get("lost_referring_domains"),
        }
    except Exception:  # noqa: BLE001
        return None


async def rank_check(keyword: str, domain: str,
                     location_code: int | None = None,
                     language_code: str | None = None,
                     creds: dict | None = None) -> dict:
    """
    ยิงคีย์เวิร์ดไปที่ Google (ผ่าน DataForSEO) แล้ว:
      - คืน top 10 (หน้า 1)
      - หา 'อันดับของโดเมนเรา' ในผลทั้งหมด
      - บอกว่า 'ติดหน้า 1 จริงไหม' (อันดับ 1–10)
    ตัวเลขนี้ตรวจสอบเองได้: เปิด Google เสิร์ชคำเดียวกันก็เห็น
    """
    payload = [{
        "keyword": keyword,
        "location_code": location_code or settings.serp_location_code,
        "language_code": language_code or settings.serp_language_code,
        "device": "desktop",
        "depth": 100,
    }]
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(BASE, headers=_auth_header(creds), json=payload)
        r.raise_for_status()
        data = r.json()

    try:
        items = data["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError, TypeError):
        return {"keyword": keyword, "domain": domain, "our_rank": None,
                "on_page1": False, "top10": [], "raw_status": data.get("status_message")}

    dom = domain.lower().removeprefix("www.")
    organic = [it for it in items if it.get("type") == "organic"]

    our_rank = None
    for it in organic:
        d = (it.get("domain") or "").lower().removeprefix("www.")
        if d == dom:
            our_rank = it.get("rank_absolute")
            break

    top10 = [{
        "rank": it.get("rank_absolute"),
        "title": it.get("title"),
        "domain": it.get("domain"),
        "url": it.get("url"),
    } for it in organic if (it.get("rank_absolute") or 999) <= 10]

    return {
        "keyword": keyword,
        "domain": domain,
        "our_rank": our_rank,
        "on_page1": our_rank is not None and our_rank <= 10,
        "top10": top10,
    }


async def search(query: str, n: int = 8,
                 location_code: int | None = None,
                 language_code: str | None = None,
                 creds: dict | None = None) -> list[dict]:
    """SERP search ทั่วไป — คืน organic results (title/url/domain/snippet)
    ใช้หา 'โอกาสกระจาย' จริง: กระทู้ Pantip / ชุมชน / ไดเรกทอรี ที่ตรง niche ลูกค้า"""
    payload = [{
        "keyword": query,
        "location_code": location_code or settings.serp_location_code,
        "language_code": language_code or settings.serp_language_code,
        "device": "desktop",
        "depth": 20,
    }]
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(BASE, headers=_auth_header(creds), json=payload)
        r.raise_for_status()
        data = r.json()
    try:
        items = data["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError, TypeError):
        return []
    organic = [it for it in items if it.get("type") == "organic"]
    return [{
        "title": it.get("title"), "url": it.get("url"),
        "domain": it.get("domain"), "snippet": it.get("description"),
    } for it in organic[:n]]


async def top_competitors(keyword: str, n: int = 5,
                          location_code: int | None = None,
                          language_code: str | None = None,
                          creds: dict | None = None) -> list[dict]:
    """ดึงหน้าที่ติดอันดับต้น ๆ จริง (title + snippet + url) เพื่อป้อนเครื่องยนต์คอนเทนต์
    ใช้วิเคราะห์ content gap ใน Stage 1 (แซงคู่แข่งที่ติดอยู่แล้ว) — คืน [] ถ้าไม่มีคีย์/ล้ม"""
    payload = [{
        "keyword": keyword,
        "location_code": location_code or settings.serp_location_code,
        "language_code": language_code or settings.serp_language_code,
        "device": "desktop",
        "depth": 20,
    }]
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(BASE, headers=_auth_header(creds), json=payload)
        r.raise_for_status()
        data = r.json()
    try:
        items = data["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError, TypeError):
        return []
    organic = [it for it in items if it.get("type") == "organic"]
    return [{
        "rank": it.get("rank_absolute"),
        "title": it.get("title"),
        "snippet": it.get("description"),
        "url": it.get("url"),
        "domain": it.get("domain"),
    } for it in organic[:n]]
