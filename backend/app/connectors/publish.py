"""
เผยแพร่ + แจ้ง index จริง
- WordPress REST API (Application Password)
- IndexNow (Bing/Yandex) แจ้ง URL ทันทีที่เผยแพร่
"""
import httpx

from app.config import settings


async def wordpress_publish(title: str, html: str, status: str = "draft") -> dict:
    """
    สร้างโพสต์บน WordPress จริง
    เอกสาร: https://developer.wordpress.org/rest-api/reference/posts/#create-a-post
    Auth: Basic (username : application password)
    """
    if not (settings.wordpress_base_url and settings.wordpress_username and settings.wordpress_app_password):
        raise RuntimeError("ยังไม่ได้ตั้งค่า WORDPRESS_BASE_URL / USERNAME / APP_PASSWORD")
    url = settings.wordpress_base_url.rstrip("/") + "/wp-json/wp/v2/posts"
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            url,
            auth=(settings.wordpress_username, settings.wordpress_app_password),
            json={"title": title, "content": html, "status": status},
        )
        r.raise_for_status()
        data = r.json()
    return {"id": data.get("id"), "link": data.get("link"), "status": data.get("status")}


async def indexnow_submit(url: str) -> dict:
    """
    แจ้ง IndexNow ให้ Search Engine มาเก็บ index ทันที
    เอกสาร: https://www.indexnow.org/documentation
    ต้องวางไฟล์ {key}.txt ไว้ที่ root ของเว็บก่อน
    """
    if not (settings.indexnow_key and settings.indexnow_host):
        raise RuntimeError("ยังไม่ได้ตั้งค่า INDEXNOW_KEY / INDEXNOW_HOST")
    payload = {
        "host": settings.indexnow_host,
        "key": settings.indexnow_key,
        "keyLocation": f"https://{settings.indexnow_host}/{settings.indexnow_key}.txt",
        "urlList": [url],
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://api.indexnow.org/indexnow", json=payload)
        return {"status_code": r.status_code, "ok": r.status_code in (200, 202)}


async def publish_and_index(title: str, html: str, status: str, url_path: str | None) -> dict:
    result: dict = {"wordpress": await wordpress_publish(title, html, status)}
    link = result["wordpress"].get("link")
    ping_url = link or (
        f"https://{settings.indexnow_host}{url_path}" if (settings.indexnow_host and url_path) else None
    )
    if ping_url and settings.indexnow_key and settings.indexnow_host:
        try:
            result["indexnow"] = await indexnow_submit(ping_url)
        except Exception as e:  # noqa: BLE001
            result["indexnow"] = {"error": str(e)}
    return result
