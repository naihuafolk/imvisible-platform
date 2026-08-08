"""
IM WEB (imweb.studio) connector — AI website builder ที่ 'เสียบเข้า' ImVisible
POST {base}/generate → คืน 'HTML เว็บทั้งหน้า พร้อมใช้' (themes หลายสไตล์) · Bearer auth · sync
ใช้สร้างเว็บให้ลูกค้าจากในระบบ → แล้วต่อ SEO/AEO/GEO ให้ 'โตเอง' · crash-safe (ไม่โยน exception ออก)
"""
import httpx

from app.config import settings


def enabled() -> bool:
    return bool(settings.imweb_api_key)


async def generate_site(brief: dict, tier: str = "paid", variants: int = 1) -> dict:
    """สร้างเว็บจาก brief ผ่าน IM WEB → คืน dict จาก API ตรง ๆ
    สำเร็จ: {ok:True, engine, tier, count, themes:[{id, styleName, headline, swatches:[..], html}]}
    ล้ม: {ok:False, error, status?} — crash-safe ไม่โยน exception (caller เช็ก ok เอง)"""
    if not settings.imweb_api_key:
        return {"ok": False, "error": "ยังไม่ได้ตั้ง IMWEB_API_KEY"}
    url = settings.imweb_base_url.rstrip("/") + "/generate"
    payload = {
        "tier": (tier or "paid"),
        "variants": max(1, min(int(variants or 1), 3)),
        "brief": brief or {},
    }
    try:
        async with httpx.AsyncClient(timeout=180) as c:      # สร้างเว็บ AI ใช้เวลานาน → timeout ยาว
            r = await c.post(url, json=payload, headers={
                "Authorization": "Bearer " + settings.imweb_api_key,
                "Content-Type": "application/json",
            })
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            return {"ok": False, "error": ("IM WEB ตอบไม่ใช่ JSON (HTTP %d)" % r.status_code)[:200], "status": r.status_code}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": ("เรียก IM WEB ไม่ได้: " + str(e))[:200]}
    if r.status_code >= 400 or not data.get("ok"):
        return {"ok": False, "status": r.status_code,
                "error": str(data.get("error") or ("HTTP %d" % r.status_code))[:200]}
    # เก็บเฉพาะ field ที่ใช้ + กันตอบก้อนใหญ่เกิน (html อาจยาวมาก แต่ต้องส่งกลับให้พรีวิว/บันทึก)
    themes = []
    for t in (data.get("themes") or []):
        themes.append({
            "id": t.get("id") or "",
            "styleName": t.get("styleName") or t.get("id") or "",
            "headline": t.get("headline") or "",
            "swatches": t.get("swatches") or [],
            "html": t.get("html") or "",
        })
    return {"ok": True, "engine": data.get("engine"), "tier": data.get("tier"),
            "count": len(themes), "themes": themes}
