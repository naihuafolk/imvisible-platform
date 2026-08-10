"""
Imgentic (api.imgentic.ai) connector — บริการสร้าง 'ภาพ/วิดีโอ' ของเราเอง (auth: header x-api-key)
Flow ตามเอกสาร: POST /generate/text → ได้ task id → poll GET /image-status|/video-status/{id} จนเสร็จ → URL ไฟล์

⚠️ ระบบจริง ไม่มี test mode — เจนสำเร็จ = เสียเครดิตจริงทุกครั้ง · ห้ามยิงลูปถี่ ๆ (backfill ให้ระวังจำนวน)
ต้องมี 'ชื่อโมเดล' จาก GET /models ก่อน (ตั้งใน IMGENTIC_IMAGE_MODEL / IMGENTIC_VIDEO_MODEL)
crash-safe: ล้ม = คืน "" (caller เช็กเอง) — ไม่โยน exception ออก
"""
import asyncio
import json as _json

import httpx

from app.config import settings


def enabled() -> bool:
    return bool(settings.imgentic_api_key)


def image_ready() -> bool:
    """พร้อมใช้ Imgentic สร้าง 'รูป' ไหม — ต้องมีทั้งคีย์ + ชื่อโมเดล (กันเรียกทั้งที่ยังไม่เลือกโมเดล)"""
    return bool(settings.imgentic_api_key and settings.imgentic_image_model)


def _headers() -> dict:
    # Imgentic อยู่หลัง WAF ที่ 403 ทุก UA ที่ไม่ใช่ browser (python-httpx/urllib โดนบล็อก — พิสูจน์แล้ว)
    return {
        "x-api-key": settings.imgentic_api_key,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
    }


def _base() -> str:
    return (settings.imgentic_base_url or "https://api.imgentic.ai").rstrip("/")


def _dig(d, keys):
    """หาไฟล์ URL / task id จาก response ที่ field ไม่แน่นอน — เดินลง dict/list ที่พบบ่อย"""
    if isinstance(d, dict):
        for k in keys:
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
            if isinstance(v, (int, float)) and not isinstance(v, bool):  # imageTaskId เป็น int
                return str(v)
        for k in ("data", "result", "task", "output", "response"):
            sub = d.get(k)
            got = _dig(sub, keys)
            if got:
                return got
    elif isinstance(d, list):
        for it in d:
            got = _dig(it, keys)
            if got:
                return got
    return ""


# gen response ของจริงคืน task id ที่ 'imageTaskId'/'videoTaskId' (ระดับบน) — ต้องมาก่อน id ทั่วไป
_ID_KEYS = ("imageTaskId", "videoTaskId", "taskId", "task_id", "taskID", "requestId", "id")
_URL_KEYS = ("imageUrl", "image_url", "videoUrl", "video_url", "resultUrl", "result_url", "url", "urls", "fileUrl", "file_url", "output")


def _first_url(v) -> str:
    """คืน URL แรก — contract จริงของ Imgentic ห่อไว้เป็น string ของ array: image_url = '[\"https://...jpg\"]'"""
    if isinstance(v, list):
        for it in v:
            u = _first_url(it)
            if u:
                return u
        return ""
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("http"):
            return s
        if s.startswith("["):  # JSON string array ห่ออีกชั้น → แกะแล้วหา url ข้างใน
            try:
                return _first_url(_json.loads(s))
            except Exception:
                return ""
    return ""


def _media_url(d) -> str:
    return _first_url(_dig(d, _URL_KEYS))


def _status(d) -> str:
    if not isinstance(d, dict):
        return ""
    s = d.get("status") or d.get("state") or ""
    if not s and isinstance(d.get("data"), dict):
        s = d["data"].get("status") or d["data"].get("state") or ""
    return str(s or "").lower()


async def list_models() -> list:
    """GET /models — ดึงแคตตาล็อกโมเดล (ไว้เลือกชื่อไปตั้งใน IMGENTIC_IMAGE_MODEL)"""
    if not settings.imgentic_api_key:
        return []
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(_base() + "/models", headers=_headers())
        r.raise_for_status()
        data = r.json()
    if isinstance(data, dict):
        return data.get("models") or data.get("data") or data.get("items") or []
    return data if isinstance(data, list) else []


async def _generate(mode: str, prompt: str, model: str, status_path: str,
                    polls: int, interval: float, extra: dict | None = None) -> str:
    """แกนกลาง: POST /generate/text → poll status → คืน URL · crash-safe (ล้ม='')"""
    if not (settings.imgentic_api_key and model):
        return ""
    body = {"mode": mode, "prompt": prompt, "model": model}
    if settings.imgentic_provider:
        body["provider"] = settings.imgentic_provider
    if extra:
        body.update(extra)
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(_base() + "/generate/text", headers=_headers(), json=body)
            r.raise_for_status()
            d = r.json()
    except Exception as e:  # noqa: BLE001
        print("[imgentic] generate ล้ม: %r" % e)
        return ""
    url = _media_url(d)                          # เผื่อคืน URL ตรง ๆ
    if url:
        return url
    tid = _dig(d, _ID_KEYS)
    if not tid:
        print("[imgentic] ไม่พบ task id ใน response: %s" % str(d)[:160])
        return ""
    for _ in range(polls):                       # poll จนเสร็จ (หรือ fail)
        await asyncio.sleep(interval)
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                rr = await c.get(_base() + status_path + str(tid), headers=_headers())
            if rr.status_code >= 400:
                continue
            d2 = rr.json()
        except Exception:  # noqa: BLE001
            continue
        u = _media_url(d2)
        if u:
            return u
        if _status(d2) in ("failed", "error", "cancelled", "canceled"):
            print("[imgentic] task %s ล้มเหลว" % tid)
            return ""
    print("[imgentic] task %s timeout (ยังไม่เสร็จ)" % tid)
    return ""


async def generate_image(prompt: str, model: str = "") -> str:
    """text→image · poll /image-status/{id} · คืน URL รูป (ล้ม='')"""
    return await _generate("text-to-image", prompt, (model or settings.imgentic_image_model),
                           "/image-status/", polls=40, interval=2.0)


async def generate_video(prompt: str, model: str = "", duration: int = 5) -> str:
    """text→video · poll /video-status/{id} · ช้ากว่ารูปมาก (poll ถี่น้อยลง เผื่อเป็นนาที) · คืน URL (ล้ม='')"""
    return await _generate("text-to-video", prompt, (model or settings.imgentic_video_model),
                           "/video-status/", polls=60, interval=5.0, extra={"duration": duration})
