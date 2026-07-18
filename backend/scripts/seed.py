"""
สร้างตาราง + ใส่ผู้ใช้เดโมและโปรเจ็คตัวอย่าง (สำหรับเริ่มต้นเร็ว)
รัน (จากโฟลเดอร์ backend, ต้องตั้ง DATABASE_URL ก่อน):
  python scripts/seed.py
เดโม: sqlite ก็ได้ →  set DATABASE_URL=sqlite+aiosqlite:///./rankpilot.db
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import session as db          # noqa: E402
from app.auth import security             # noqa: E402


async def main():
    if not db.enabled():
        print("ตั้ง DATABASE_URL ก่อน เช่น sqlite+aiosqlite:///./rankpilot.db")
        return
    from app.db.models import User, Project
    from sqlalchemy import select

    await db.create_all()
    async with db.session() as s:
        email = "demo@rankpilot.ai"
        u = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if not u:
            u = User(email=email, name="บัญชีเดโม", password_hash=security.hash_password("demo1234"))
            s.add(u); await s.commit(); await s.refresh(u)
            demo = [
                ("เว็บคลินิกความงาม ABC", "abc-beautyclinic.com", "approve"),
                ("เดอร์มา สกินแคร์", "dermaskin.co", "auto"),
                ("เวลเนส เซ็นเตอร์ BKK", "wellnessbkk.com", "approve"),
            ]
            for name, dom, mode in demo:
                s.add(Project(user_id=u.id, name=name, domain=dom, mode=mode))
            await s.commit()
            print(f"สร้างผู้ใช้เดโม + {len(demo)} โปรเจ็คแล้ว (login: {email} / demo1234)")
        else:
            print("มีผู้ใช้เดโมอยู่แล้ว")


if __name__ == "__main__":
    asyncio.run(main())
