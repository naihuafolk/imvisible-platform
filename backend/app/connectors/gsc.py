"""
Google Search Console connector — ดึงคลิก/Impressions/อันดับ 'ตัวเลขจริงจาก Google เอง'
Flow: refresh_token -> access_token -> Search Analytics query
เอกสาร: https://developers.google.com/webmaster-tools/v1/searchanalytics/query
"""
import datetime as _dt
from urllib.parse import quote
import httpx

from app.config import settings

TOKEN_URL = "https://oauth2.googleapis.com/token"


async def _access_token() -> str:
    if not (settings.google_client_id and settings.google_client_secret and settings.google_refresh_token):
        raise RuntimeError("ยังไม่ได้ตั้งค่า GOOGLE_CLIENT_ID / SECRET / REFRESH_TOKEN ใน .env")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(TOKEN_URL, data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": settings.google_refresh_token,
            "grant_type": "refresh_token",
        })
        r.raise_for_status()
        return r.json()["access_token"]


async def summary(site_url: str, days: int = 28) -> dict:
    """สรุป 28 วันล่าสุด: คลิกรวม, impressions, ctr, อันดับเฉลี่ย + top query"""
    token = await _access_token()
    end = _dt.date.today()
    start = end - _dt.timedelta(days=days)
    endpoint = (
        "https://searchconsole.googleapis.com/webmasters/v3/sites/"
        f"{quote(site_url, safe='')}/searchAnalytics/query"
    )
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["query"],
        "rowLimit": 25,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(endpoint, headers={"Authorization": f"Bearer {token}"}, json=body)
        r.raise_for_status()
        rows = r.json().get("rows", [])

    total_clicks = sum(row.get("clicks", 0) for row in rows)
    total_impr = sum(row.get("impressions", 0) for row in rows)
    avg_pos = round(sum(row.get("position", 0) for row in rows) / len(rows), 1) if rows else None
    top = [{
        "query": row["keys"][0],
        "clicks": row.get("clicks", 0),
        "impressions": row.get("impressions", 0),
        "ctr": round(row.get("ctr", 0) * 100, 2),
        "position": round(row.get("position", 0), 1),
    } for row in rows[:10]]

    return {
        "site_url": site_url,
        "period_days": days,
        "clicks": total_clicks,
        "impressions": total_impr,
        "avg_position": avg_pos,
        "top_queries": top,
    }
