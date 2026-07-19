# -*- coding: utf-8 -*-
"""
grow_test.py — เดโมออโต้ลูปกับ imvisible.tech ของเราเอง (รันในคอนเทนเนอร์)
สร้างโปรเจ็คทดสอบ + สั่งวงจร: ขุดคำถามจริง → เขียนด้วย AI (Gemini) → เผยแพร่ WordPress

วิธีรัน (บนเซิร์ฟเวอร์ .101):
    docker exec -i deploy-worker-1 python < ~/imvisible-platform/deploy/grow_test.py
"""
import asyncio
from sqlalchemy import select

from app.db import session as db
from app.db.models import User, Project
from app.worker.tasks import _produce_for_project


async def main():
    if not db.enabled():
        print("!! DB ยังไม่พร้อม (ไม่มี DATABASE_URL)")
        return
    async with db.session() as s:
        user = (await s.execute(select(User).order_by(User.id))).scalars().first()
        if not user:
            print("!! ยังไม่มีผู้ใช้ในระบบ — สมัครที่ app.imvisible.tech ก่อน แล้วรันใหม่")
            return
        proj = (await s.execute(
            select(Project).where(Project.domain == "imvisible.tech"))).scalars().first()
        if not proj:
            proj = Project(user_id=user.id, name="รับทำ SEO",
                           domain="imvisible.tech", mode="auto")
            s.add(proj); await s.commit(); await s.refresh(proj)
            print("✓ สร้างโปรเจ็คทดสอบ: '%s' · imvisible.tech · โหมด auto · id=%d"
                  % (proj.name, proj.id))
        else:
            print("• ใช้โปรเจ็คเดิม: '%s' id=%d" % (proj.name, proj.id))
        pid = proj.id

    print("\n→ เริ่มวงจรอัตโนมัติ: ขุดคำถามจริง → เขียนด้วย AI → เผยแพร่ ...")
    print("  (ใช้เวลาสัก 30-60 วิ เพราะ AI กำลังเขียนบทความจริง)\n")
    try:
        res = await _produce_for_project(pid, 1)
    except Exception as e:  # noqa: BLE001
        print("!! ล้มเหลว:", e)
        return

    print("=== ผลลัพธ์วงจรอัตโนมัติ ===")
    print("โปรเจ็ค:", res.get("project"), "| โหมด:", res.get("mode"),
          "| ผลิต:", res.get("produced"), "ชิ้น")
    for it in res.get("items", []):
        if it.get("error"):
            print("  ✗", it.get("topic"), "→", it["error"])
        else:
            print("  ✓ หัวข้อ:", it.get("topic"))
            print("    เขียนโดย:", it.get("provider"), "| article_id:", it.get("article_id"))
            if it.get("published"):
                print("    🌐 เผยแพร่แล้ว:", it["published"])
            else:
                print("    📝 สถานะ:", it.get("status"))
    print("\nเสร็จ! ลองเปิดลิงก์บทความด้านบน หรือดูใน imvisible.tech/wp-admin")


asyncio.run(main())
