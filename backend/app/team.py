"""
ทีม / multi-seat — เจ้าของบัญชีเชิญสมาชิกให้เข้าถึงโปรเจ็คของตน (ตาม role)
viewer = ดูอย่างเดียว · editor/admin = แก้ไขได้
"""
from sqlalchemy import select

from app.db import session as db

WRITE_ROLES = ("editor", "admin")


async def link_invites(user_id: int, email: str) -> int:
    """ผูกคำเชิญที่ค้างอยู่ (status=invited, email ตรง) เข้ากับผู้ใช้ที่เพิ่งสมัคร/ล็อกอิน"""
    from app.db.models import TeamMember
    n = 0
    async with db.session() as s:
        rows = (await s.execute(select(TeamMember).where(
            TeamMember.email == (email or "").lower(),
            TeamMember.member_user_id.is_(None)))).scalars().all()
        for r in rows:
            r.member_user_id = user_id
            r.status = "active"
            n += 1
        if n:
            await s.commit()
    return n


async def accessible_owner_ids(user_id: int) -> list[int]:
    """เจ้าของบัญชีที่ผู้ใช้นี้เข้าถึงได้ = ตัวเอง + บัญชีที่เชิญเราเป็นสมาชิก active"""
    from app.db.models import TeamMember
    async with db.session() as s:
        owners = (await s.execute(select(TeamMember.owner_id).where(
            TeamMember.member_user_id == user_id,
            TeamMember.status == "active"))).scalars().all()
    return [user_id] + [o for o in owners if o != user_id]


async def role_on(user_id: int, owner_id: int) -> str:
    """สิทธิ์ของ user บนบัญชีของ owner ('owner' ถ้าเป็นเจ้าของเอง / role / '' ถ้าไม่มีสิทธิ์)"""
    if user_id == owner_id:
        return "owner"
    from app.db.models import TeamMember
    async with db.session() as s:
        r = (await s.execute(select(TeamMember.role).where(
            TeamMember.owner_id == owner_id, TeamMember.member_user_id == user_id,
            TeamMember.status == "active"))).scalars().first()
    return r or ""
