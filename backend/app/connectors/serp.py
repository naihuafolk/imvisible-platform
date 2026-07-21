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
