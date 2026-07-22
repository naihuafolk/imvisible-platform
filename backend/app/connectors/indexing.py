"""Google Indexing API — แจ้ง Google ให้เก็บ (crawl) URL ทันที = instant indexing
เร่งให้หน้าใหม่/หน้าที่อัปเดตถูก index ในหลัก 'ชั่วโมง' แทนที่จะรอ crawl เอง

การตั้งค่า:
  - สร้าง service account ใน Google Cloud + เปิด Indexing API
  - เพิ่มอีเมล service account เป็น 'owner' ของ property ใน Google Search Console
  - วาง JSON ของ service account ทั้งก้อนไว้ที่ ENV: GOOGLE_INDEXING_SA_JSON
crash-safe: ยังไม่ตั้ง = no-op (ไม่กระทบการเผยแพร่)
"""
import json
import time

import httpx
import jwt

from app.config import settings

SCOPE = "https://www.googleapis.com/auth/indexing"
ENDPOINT = "https://indexing.googleapis.com/v3/urlNotifications:publish"


def enabled() -> bool:
    return bool((settings.google_indexing_sa_json or "").strip())


def _sa() -> dict:
    return json.loads(settings.google_indexing_sa_json)


async def _access_token() -> str:
    sa = _sa()
    now = int(time.time())
    token_uri = sa.get("token_uri", "https://oauth2.googleapis.com/token")
    assertion = jwt.encode(
        {"iss": sa["client_email"], "scope": SCOPE, "aud": token_uri,
         "iat": now, "exp": now + 3600},
        sa["private_key"], algorithm="RS256")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(token_uri, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion})
        r.raise_for_status()
        return r.json()["access_token"]


async def submit(url: str, kind: str = "URL_UPDATED") -> dict:
    """แจ้ง Google ให้ crawl URL นี้ทันที (kind: URL_UPDATED | URL_DELETED)
    no-op ถ้ายังไม่ตั้ง service account"""
    if not enabled() or not url:
        return {"skipped": True}
    token = await _access_token()
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(ENDPOINT,
                         headers={"Authorization": "Bearer " + token,
                                  "Content-Type": "application/json"},
                         json={"url": url, "type": kind})
        r.raise_for_status()
        return {"ok": True}
