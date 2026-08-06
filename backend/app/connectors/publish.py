"""
เผยแพร่ + แจ้ง index จริง
- WordPress REST API (Application Password)
- IndexNow (Bing/Yandex) แจ้ง URL ทันทีที่เผยแพร่
"""
import hashlib

import httpx

from app.config import settings

_INDEXNOW_SALT = "imvisible-indexnow-v1"   # salt คงที่ → คีย์ 'ต่อโดเมน' เสถียร (วางไฟล์ครั้งเดียวใช้ยาว)


async def wordpress_publish(title: str, html: str, status: str = "draft",
                            creds: dict | None = None) -> dict:
    """
    สร้างโพสต์บน WordPress จริง
    เอกสาร: https://developer.wordpress.org/rest-api/reference/posts/#create-a-post
    Auth: Basic (username : application password)
    ใช้บัญชี WordPress 'ของลูกค้า' (per-project) ก่อน → ไม่มีค่อย fallback บัญชีกลาง
    """
    base_url = (creds or {}).get("base_url") or settings.wordpress_base_url
    username = (creds or {}).get("username") or settings.wordpress_username
    app_password = (creds or {}).get("app_password") or settings.wordpress_app_password
    if not (base_url and username and app_password):
        raise RuntimeError("ยังไม่ได้ตั้งค่า WORDPRESS_BASE_URL / USERNAME / APP_PASSWORD (บัญชีลูกค้าหรือกลาง)")
    url = base_url.rstrip("/") + "/wp-json/wp/v2/posts"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            url,
            auth=(username, app_password),
            json={"title": title, "content": html, "status": status},
        )
        r.raise_for_status()
        data = r.json()
    return {"id": data.get("id"), "link": data.get("link"), "status": data.get("status")}


def indexnow_key_for(host: str) -> str:
    """คีย์ IndexNow แบบ 'ต่อโดเมน' (deterministic) — วางไฟล์ {key}.txt บนโดเมนนั้นครั้งเดียวใช้ยาว
    โดเมน managed กลาง = ใช้คีย์เดิมจาก settings (ไฟล์เดิมใช้ได้) · โดเมนอื่น = คำนวณใหม่ต่อ host"""
    h = (host or "").strip().lower().lstrip(".")
    if not h:
        return ""
    if settings.indexnow_host and h == settings.indexnow_host.lower() and settings.indexnow_key:
        return settings.indexnow_key
    return hashlib.sha256(("%s:%s" % (_INDEXNOW_SALT, h)).encode()).hexdigest()[:32]


async def indexnow_submit(url: str | None = None, host: str | None = None,
                          key: str | None = None, urls: list | None = None) -> dict:
    """แจ้ง IndexNow ให้ Bing/Yandex/AI-search มาเก็บ index ทันที (ต่อโดเมน · รับได้ทั้ง 1 URL หรือหลาย URL)
    ต้องมีไฟล์ {key}.txt ที่ root ของโดเมนนั้น (ถ้าไม่มี IndexNow ปฏิเสธ = ล้มเงียบ ไม่เสียหาย)
    เอกสาร: https://www.indexnow.org/documentation"""
    from urllib.parse import urlparse
    lst = [u for u in (urls if urls is not None else ([url] if url else [])) if u][:10000]
    if not lst:
        raise RuntimeError("IndexNow: ต้องมี url อย่างน้อย 1 รายการ")
    h = (host or urlparse(lst[0]).hostname or "").lower().lstrip(".")
    k = key or indexnow_key_for(h)
    if not (h and k):
        raise RuntimeError("IndexNow: ต้องมี host + key")
    payload = {"host": h, "key": k, "keyLocation": "https://%s/%s.txt" % (h, k), "urlList": lst}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.indexnow.org/indexnow", json=payload)
    return {"status_code": r.status_code, "ok": r.status_code in (200, 202),
            "host": h, "key": k, "count": len(lst)}


async def publish_and_index(title: str, html: str, status: str, url_path: str | None,
                            creds: dict | None = None) -> dict:
    from urllib.parse import urlparse
    result: dict = {"wordpress": await wordpress_publish(title, html, status, creds)}
    link = result["wordpress"].get("link")
    ping_url = link or (
        "https://%s%s" % (settings.indexnow_host, url_path) if (settings.indexnow_host and url_path) else None
    )
    if ping_url:
        host = (urlparse(ping_url).hostname or "").lower()
        try:                                    # ยิงด้วยคีย์ 'ต่อโดเมน' ของ URL นั้น · ล้มเงียบถ้ายังไม่วางไฟล์คีย์
            result["indexnow"] = await indexnow_submit(ping_url, host=host)
        except Exception as e:  # noqa: BLE001
            result["indexnow"] = {"error": str(e)}
    return result
