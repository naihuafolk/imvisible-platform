"""
ModelArk (BytePlus) connector — Seedream (รูป) + Seedance (วิดีโอ)
OpenAI-compatible endpoint: {ARK_BASE_URL}/images/generations · /contents/generations/tasks

ใช้เสริมบทความ (รูปในเนื้อหา / วิดีโอ) — เรียกจาก content engine หรือ post-publish step
หมายเหตุ: ต้องเปิด outbound ให้เซิร์ฟเวอร์ต่อ ark.ap-southeast.bytepluses.com ได้ก่อน (Security Group)
"""
import asyncio

import httpx

from app.config import settings


def enabled() -> bool:
    return bool(settings.ark_api_key)


def _headers() -> dict:
    if not settings.ark_api_key:
        raise RuntimeError("ยังไม่ได้ตั้ง ARK_API_KEY (ModelArk)")
    return {"Authorization": "Bearer " + settings.ark_api_key, "Content-Type": "application/json"}


async def generate_image(prompt: str, size: str = "2K") -> str:
    """Seedream — text→image · คืน URL รูป (หรือ b64)"""
    url = settings.ark_base_url.rstrip("/") + "/images/generations"
    payload = {"model": settings.ark_image_model, "prompt": prompt,
               "size": size, "output_format": "png", "watermark": False}
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(url, headers=_headers(), json=payload)
        r.raise_for_status()
        data = r.json()
    items = data.get("data") or []
    if not items:
        raise RuntimeError("ModelArk ไม่ส่งภาพกลับมา: " + str(data)[:200])
    return items[0].get("url") or items[0].get("b64_json") or ""


async def generate_video(prompt: str, ratio: str = "16:9", duration: int = 5,
                         max_polls: int = 40, interval: int = 6) -> str:
    """Seedance — text→video (async task) · สร้าง task แล้ว poll จนเสร็จ คืน URL วิดีโอ"""
    if not settings.ark_video_model:
        raise RuntimeError("ยังไม่ได้ตั้ง ARK_VIDEO_MODEL (Seedance)")
    base = settings.ark_base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(base + "/contents/generations/tasks", headers=_headers(),
                         json={"model": settings.ark_video_model,
                               "content": [{"type": "text",
                                            "text": f"{prompt} --ratio {ratio} --dur {duration}"}]})
        r.raise_for_status()
        task_id = r.json().get("id")
    if not task_id:
        raise RuntimeError("สร้าง task วิดีโอไม่ได้")
    for _ in range(max_polls):
        await asyncio.sleep(interval)
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.get(base + f"/contents/generations/tasks/{task_id}", headers=_headers())
            r.raise_for_status()
            d = r.json()
        status = d.get("status")
        if status == "succeeded":
            return (d.get("content") or {}).get("video_url") or ""
        if status in ("failed", "canceled"):
            raise RuntimeError("วิดีโอล้มเหลว: " + str(d.get("error") or status))
    raise RuntimeError("วิดีโอ timeout (task ยังไม่เสร็จ)")
