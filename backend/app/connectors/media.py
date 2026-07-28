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
    return bool(settings.fal_key or settings.ark_api_key)


def _headers() -> dict:
    if not settings.ark_api_key:
        raise RuntimeError("ยังไม่ได้ตั้ง ARK_API_KEY (ModelArk)")
    return {"Authorization": "Bearer " + settings.ark_api_key, "Content-Type": "application/json"}


async def _fal_image(prompt: str, image_size: str = "landscape_16_9") -> str:
    """fal.ai (FLUX) — text→image · sync endpoint fal.run · auth 'Key id:secret' · คืน URL รูป"""
    model = settings.fal_image_model or "fal-ai/flux/schnell"
    headers = {"Authorization": "Key " + settings.fal_key, "Content-Type": "application/json"}
    body = {"prompt": prompt, "num_images": 1}
    if "seedream" in model:                        # Seedream: image_size = object {width,height} 16:9 HD + enhance
        body["image_size"] = {"width": 1920, "height": 1080}
        body["enhance_prompt_mode"] = "standard"
    elif "flux-pro" in model or "ultra" in model:  # flux-pro/ultra ใช้ aspect_ratio
        body["aspect_ratio"] = "16:9"
    else:                                          # flux schnell/dev ใช้ image_size (enum string)
        body["image_size"] = image_size
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post("https://fal.run/" + model, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    imgs = data.get("images") or []
    if imgs:
        return imgs[0].get("url") or ""
    poll = data.get("response_url") or data.get("status_url")   # เผื่อ endpoint คืนแบบคิว
    if poll:
        for _ in range(30):
            await asyncio.sleep(2)
            async with httpx.AsyncClient(timeout=60) as c:
                rr = await c.get(poll, headers=headers)
                rr.raise_for_status()
                d2 = rr.json()
            imgs = d2.get("images") or []
            if imgs:
                return imgs[0].get("url") or ""
    raise RuntimeError("fal.ai ไม่ส่งภาพกลับมา: " + str(data)[:200])


async def generate_image(prompt: str, size: str = "2K") -> str:
    """text→image · ใช้ fal.ai (FLUX) ถ้าตั้ง FAL_KEY ไว้ ไม่งั้นใช้ Seedream (ModelArk) · คืน URL รูป"""
    if settings.fal_key:
        return await _fal_image(prompt, "landscape_16_9")
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


def _extract_video_url(d: dict) -> str:
    v = d.get("video")
    if isinstance(v, dict) and v.get("url"):
        return v["url"]
    if isinstance(v, str) and v:
        return v
    vids = d.get("videos") or d.get("output") or []
    if isinstance(vids, list) and vids and isinstance(vids[0], dict) and vids[0].get("url"):
        return vids[0]["url"]
    return ""


async def _fal_video(prompt: str, ratio: str = "16:9", duration: int = 5, model: str = "") -> str:
    """fal.ai text→video (queue API) · คืน URL วิดีโอ · ช้า (poll หลายรอบ) — ใช้เมื่อตั้ง FAL_VIDEO_MODEL"""
    vm = model or settings.fal_video_model
    headers = {"Authorization": "Key " + settings.fal_key, "Content-Type": "application/json"}
    body = {"prompt": prompt, "aspect_ratio": ratio, "duration": str(duration)}
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.post("https://queue.fal.run/" + vm, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    direct = _extract_video_url(data)                      # บาง endpoint คืนผลตรง
    if direct:
        return direct
    poll = data.get("response_url") or data.get("status_url")
    if not poll:
        raise RuntimeError("fal video: ไม่มี response_url: " + str(data)[:180])
    for _ in range(45):
        await asyncio.sleep(5)
        async with httpx.AsyncClient(timeout=60) as c:
            rr = await c.get(poll, headers=headers)
        if rr.status_code >= 400:
            continue
        try:
            d2 = rr.json()
        except Exception:  # noqa: BLE001
            continue
        u = _extract_video_url(d2)
        if u:
            return u
    raise RuntimeError("fal video timeout (task ยังไม่เสร็จ)")


async def generate_video(prompt: str, ratio: str = "16:9", duration: int = 5,
                         max_polls: int = 40, interval: int = 6, model: str = "") -> str:
    """text→video · ใช้ fal.ai ถ้าตั้ง model/FAL_VIDEO_MODEL ไม่งั้น Seedance (ModelArk) · สร้าง task → poll → คืน URL"""
    vm = model or settings.fal_video_model
    if vm and settings.fal_key:                            # fal.ai video (ใช้ FAL_KEY เดิม ไม่ต้องคีย์ใหม่)
        return await _fal_video(prompt, ratio, duration, model=vm)
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
