"""
Performance / Core Web Vitals — วัด 'ความเร็วจริง' ด้วย Google PageSpeed Insights
(Lighthouse lab data + CrUX field data) · ใช้กับ M3 Technical Audit
CWV เป็นปัจจัยจัดอันดับจริงของ Google — ที่นี่วัดจากหน้าเว็บจริง ไม่ประเมินลอย ๆ
"""
import httpx

from app.config import settings

PSI = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _dv(audits: dict, key: str):
    a = audits.get(key) or {}
    return a.get("displayValue")


async def audit(url: str, strategy: str = "mobile") -> dict:
    """คืนคะแนน performance + LCP/CLS/FCP/TBT + สถานะ Core Web Vitals จริง"""
    params = {"url": url, "strategy": strategy, "category": "performance"}
    if settings.pagespeed_api_key:
        params["key"] = settings.pagespeed_api_key
    async with httpx.AsyncClient(timeout=90) as c:
        r = await c.get(PSI, params=params)
        r.raise_for_status()
        j = r.json()
    lh = j.get("lighthouseResult") or {}
    audits = lh.get("audits") or {}
    score = ((lh.get("categories") or {}).get("performance") or {}).get("score")
    le = j.get("loadingExperience") or {}
    cwv_field = le.get("overall_category")   # FAST | AVERAGE | SLOW | None (ยังไม่มีข้อมูล field)
    return {
        "url": url,
        "strategy": strategy,
        "performance_score": round(score * 100) if score is not None else None,
        "lcp": _dv(audits, "largest-contentful-paint"),
        "cls": _dv(audits, "cumulative-layout-shift"),
        "fcp": _dv(audits, "first-contentful-paint"),
        "tbt": _dv(audits, "total-blocking-time"),
        "speed_index": _dv(audits, "speed-index"),
        "cwv_field": cwv_field,
        "note": "วัดจริงด้วย Google PageSpeed Insights (Lighthouse + Chrome UX Report)",
    }
