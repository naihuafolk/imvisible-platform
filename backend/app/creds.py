"""
Per-tenant credentials — ให้ลูกค้าเชื่อม "คีย์ของตัวเอง" ต่อโปรเจ็ค (multi-tenant จริง)
================================================================================
เดิมทั้งระบบใช้คีย์กลางตัวเดียว (DataForSEO/WordPress/GSC) → วัด/เผยแพร่ให้โดเมนลูกค้า
คนอื่นไม่ได้จริง และสถานะ "เชื่อมแล้ว" สะท้อนคีย์ของแพลตฟอร์ม ไม่ใช่ของลูกค้า

ที่นี่เก็บคีย์ของลูกค้าแบบเข้ารหัส (crypto.enc, คีย์ผูก JWT_SECRET) ต่อโปรเจ็ค แล้ว
connector จะใช้ "คีย์ของโปรเจ็คก่อน → ไม่มีค่อย fallback คีย์กลาง" อย่างโปร่งใส
สถานะจะบอกชัดว่าแต่ละบริการเชื่อมด้วย 'คีย์ลูกค้า (project)' หรือ 'คีย์กลาง (platform)'
"""
import json

from sqlalchemy import select

from app import crypto
from app.config import settings
from app.db import session as db

# ฟิลด์ของแต่ละบริการ (ค่าลับทั้งหมด — ไม่ส่งกลับให้ client เด็ดขาด)
FIELDS = {
    "dataforseo": ["login", "password"],
    "wordpress": ["base_url", "username", "app_password"],
    "gsc": ["client_id", "client_secret", "refresh_token"],
}


def valid_kind(kind: str) -> bool:
    return kind in FIELDS


async def set_creds(project_id: int, kind: str, data: dict) -> None:
    """บันทึกคีย์ลูกค้า (เข้ารหัส) — เก็บเฉพาะฟิลด์ที่รู้จัก · ค่าว่าง = ไม่ตั้ง"""
    from app.db.models import ProjectCredential
    if kind not in FIELDS:
        raise ValueError("unknown credential kind")
    clean = {k: str((data or {}).get(k, "")).strip() for k in FIELDS[kind]}
    enc = crypto.enc(json.dumps(clean, ensure_ascii=False))
    async with db.session() as s:
        row = (await s.execute(select(ProjectCredential).where(
            ProjectCredential.project_id == project_id,
            ProjectCredential.kind == kind))).scalars().first()
        if row:
            row.data_enc = enc
        else:
            s.add(ProjectCredential(project_id=project_id, kind=kind, data_enc=enc))
        await s.commit()


async def get_creds(project_id: int, kind: str) -> dict:
    """คืน dict คีย์ลูกค้า (ถอดรหัส) — ไม่มี/ถอดไม่ได้ = {}"""
    from app.db.models import ProjectCredential
    if not db.enabled():
        return {}
    async with db.session() as s:
        row = (await s.execute(select(ProjectCredential).where(
            ProjectCredential.project_id == project_id,
            ProjectCredential.kind == kind))).scalars().first()
    if not row or not row.data_enc:
        return {}
    try:
        d = json.loads(crypto.dec(row.data_enc) or "{}")
        return d if isinstance(d, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


async def delete_creds(project_id: int, kind: str) -> None:
    from app.db.models import ProjectCredential
    async with db.session() as s:
        row = (await s.execute(select(ProjectCredential).where(
            ProjectCredential.project_id == project_id,
            ProjectCredential.kind == kind))).scalars().first()
        if row:
            await s.delete(row)
            await s.commit()


def _project_complete(kind: str, c: dict) -> bool:
    return bool(c) and all(str(c.get(f, "")).strip() for f in FIELDS[kind])


def _platform_has(kind: str) -> bool:
    if kind == "dataforseo":
        return bool(settings.dataforseo_login and settings.dataforseo_password)
    if kind == "wordpress":
        return bool(settings.wordpress_base_url and settings.wordpress_username
                    and settings.wordpress_app_password)
    if kind == "gsc":
        return bool(settings.google_client_id and settings.google_client_secret
                    and settings.google_refresh_token)
    return False


async def status(project_id: int) -> dict:
    """สถานะการเชื่อมต่อต่อโปรเจ็ค (โปร่งใส): เชื่อมด้วยคีย์ลูกค้า/คีย์กลาง/ยังไม่เชื่อม"""
    out = {}
    for kind in FIELDS:
        c = await get_creds(project_id, kind)
        proj_ok = _project_complete(kind, c)
        plat_ok = _platform_has(kind)
        out[kind] = {"connected": proj_ok or plat_ok,
                     "source": "project" if proj_ok else ("platform" if plat_ok else "none")}
    return out
