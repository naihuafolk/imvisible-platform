"""
การนับการใช้งานจริงต่อผู้ใช้ (สำหรับบังคับโควตาแพ็กเกจ)
- จำนวนโปรเจ็คของผู้ใช้
- จำนวนบทความที่ผลิตเดือนนี้ (นับจาก Article.created_at ข้ามทุกโปรเจ็คของผู้ใช้)
"""
from datetime import datetime, timezone

from sqlalchemy import select, func

from app.db import session as db
from app import plans


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def project_count(user_id: int) -> int:
    from app.db.models import Project
    async with db.session() as s:
        return int((await s.execute(
            select(func.count(Project.id)).where(Project.user_id == user_id))).scalar() or 0)


async def articles_this_month(user_id: int) -> int:
    from app.db.models import Project, Article
    async with db.session() as s:
        return int((await s.execute(
            select(func.count(Article.id))
            .join(Project, Article.project_id == Project.id)
            .where(Project.user_id == user_id, Article.created_at >= _month_start()))).scalar() or 0)


async def user_plan(user_id: int) -> str:
    """แพ็กเกจปัจจุบันของผู้ใช้ (จาก DB — บิลลิ่งอัปเดตค่านี้)
    ยกเว้น: อีเมลใน ADMIN_EMAILS ได้ business อัตโนมัติ (เทสต์แบรนด์ตัวเองโดยไม่ต้องจ่ายเงิน)"""
    from app.db.models import User
    from app.config import settings
    async with db.session() as s:
        u = await s.get(User, user_id)
    if u:
        admins = [e.strip().lower() for e in (settings.admin_emails or "").split(",") if e.strip()]
        if (u.email or "").lower() in admins:
            return "business"
    return plans.normalize(getattr(u, "plan", None) if u else None)


async def summary(user_id: int) -> dict:
    """สรุปการใช้งานเทียบโควตาแพ็กเกจ (ให้ frontend แสดง + gate)"""
    lim = plans.limits(await user_plan(user_id))
    proj = await project_count(user_id)
    arts = await articles_this_month(user_id)
    return {
        "plan": lim["key"], "plan_label": lim["label"],
        "projects": {"used": proj, "limit": lim["projects"],
                     "remaining": max(0, lim["projects"] - proj)},
        "articles_month": {"used": arts, "limit": lim["articles_month"],
                           "remaining": max(0, lim["articles_month"] - arts)},
    }


async def can_create_project(user_id: int) -> bool:
    return (await project_count(user_id)) < plans.limits(await user_plan(user_id))["projects"]


async def can_produce_article(user_id: int) -> bool:
    return (await articles_this_month(user_id)) < plans.limits(await user_plan(user_id))["articles_month"]
