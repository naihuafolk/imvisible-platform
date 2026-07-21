# -*- coding: utf-8 -*-
"""
Bootstrap เจ้าของแบรนด์ — สร้างบัญชี + โปรเจ็ค (managed hosting) + อ่านเว็บจริง + ผลิตบทความแรก
ทั้งหมด "ในกระบวนการเดียว" ไม่ต้องมี worker/redis — เหมาะกับ 'เทสแบรนด์ตัวเองหลัง deploy'

รันในคอนเทนเนอร์ api (prod):
  docker compose -f deploy/docker-compose.prod.yml exec api \
    python scripts/bootstrap_owner.py --email you@imvisible.tech --password 'yourpass' \
    --url imvisible.tech --name ImVisible

รัน local (ตั้ง DATABASE_URL ก่อน):
  cd backend && python scripts/bootstrap_owner.py --email you@imvisible.tech --url imvisible.tech
"""
import argparse
import asyncio
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db import session as db          # noqa: E402
from app.auth import security             # noqa: E402


def _domain(url: str) -> str:
    u = (url or "").strip()
    if "://" not in u:
        u = "https://" + u
    return (urlparse(u).hostname or "").removeprefix("www.").lower()


async def main(args):
    if not db.enabled():
        print("!! ตั้ง DATABASE_URL ก่อน (เช่น sqlite+aiosqlite:///./rankpilot.db หรือ Postgres จริง)")
        return 1

    await db.create_all()
    try:
        from app import migrate
        await migrate.run()
    except Exception as e:  # noqa: BLE001
        print("  (migrate เตือน:", str(e)[:80], ")")

    from sqlalchemy import select
    from app.db.models import User, Project
    from app import urls

    domain = _domain(args.url)
    if not domain:
        print("!! --url ไม่ถูกต้อง")
        return 1

    # 1) เจ้าของบัญชี (upsert) + ตั้งแพ็กเกจ business (เทสได้ไม่ติดโควตา ไม่ต้องจ่ายเงิน)
    async with db.session() as s:
        u = (await s.execute(select(User).where(User.email == args.email))).scalar_one_or_none()
        if not u:
            u = User(email=args.email, name=args.name or args.email.split("@")[0],
                     password_hash=security.hash_password(args.password), plan="business")
            s.add(u); await s.commit(); await s.refresh(u)
            print("✓ สร้างบัญชีเจ้าของ: %s (แพ็กเกจ business)" % u.email)
        else:
            u.plan = "business"
            await s.commit()
            print("• ใช้บัญชีเดิม: %s (ตั้งเป็น business)" % u.email)
        uid = u.id

    # 2) โปรเจ็ค managed hosting (mode=auto → เผยแพร่อัตโนมัติ)
    async with db.session() as s:
        p = (await s.execute(select(Project).where(
            Project.user_id == uid, Project.domain == domain))).scalars().first()
        if not p:
            slug = urls.project_slug_from_domain(domain)
            p = Project(user_id=uid, name=args.name or domain, domain=domain,
                        mode="auto", publish_mode="managed", slug=slug)
            s.add(p); await s.commit(); await s.refresh(p)
            print("✓ สร้างโปรเจ็ค: %s · %s · โหมด auto · managed · id=%d" % (p.name, domain, p.id))
        else:
            print("• ใช้โปรเจ็คเดิม: %s id=%d" % (p.name, p.id))
        pid = p.id
        home = urls.project_public_home(p)
    print("  บล็อกที่เราโฮสต์ให้:", home)

    # 3) อ่านเว็บลูกค้าจริง (Site Intelligence) — ต้องมี LLM key
    if not args.skip_analyze:
        print("\n→ อ่านเว็บ + สกัดบริบทธุรกิจ (Site Intelligence) ...")
        from app.worker.tasks import _analyze_project
        try:
            r = await _analyze_project(pid)
            print("  ", {k: r.get(k) for k in ("analyzed", "brand_terms", "plan_size", "note") if k in r})
        except Exception as e:  # noqa: BLE001
            print("  (analyze ล้ม:", str(e)[:120], "— ต้องมี ANTHROPIC/OPENAI/GEMINI key)")

    # 4) ผลิต + เผยแพร่บทความแรก — ต้องมี LLM key (+ DataForSEO ช่วยหาคู่แข่ง)
    if not args.skip_produce:
        print("\n→ ผลิตบทความแรก (ขุดคำถาม → เขียนด้วย AI → ให้คะแนน → เผยแพร่) ...")
        print("  (ใช้เวลาสัก 30-90 วิ เพราะ AI กำลังเขียนจริง)")
        from app.worker.tasks import _produce_for_project
        try:
            r = await _produce_for_project(pid, 1)
            print("  ผลิต:", r.get("produced"), "· รายการ:", r.get("items") or r.get("note"))
        except Exception as e:  # noqa: BLE001
            print("  (produce ล้ม:", str(e)[:160], "— ตรวจ LLM key)")

    print("\n✅ เสร็จ — เปิดดูบล็อกได้ที่:", home)
    print("   เข้าแดชบอร์ดด้วยอีเมล/รหัสที่ตั้งไว้ แล้วดู M2/M3/M5 ได้เลย")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", default="changeme1234")
    ap.add_argument("--name", default="")
    ap.add_argument("--url", required=True, help="เช่น imvisible.tech")
    ap.add_argument("--skip-analyze", action="store_true")
    ap.add_argument("--skip-produce", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args())) or 0)
