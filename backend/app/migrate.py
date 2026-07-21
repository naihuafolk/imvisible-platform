"""
Migration เบา ๆ (idempotent) — เพิ่มคอลัมน์ Managed Hosting ให้ตารางเดิม + backfill slug
เพราะ startup ใช้ create_all() ซึ่ง "สร้างตารางที่ยังไม่มี" แต่ไม่ ALTER ตารางเดิม

รันในคอนเทนเนอร์ api:
    docker compose -f docker-compose.prod.yml exec api python -m app.migrate
(ปลอดภัยรันซ้ำได้ — ADD COLUMN IF NOT EXISTS)
"""
import asyncio
import secrets

from sqlalchemy import text, select

from app.db import session as db
from app.urls import project_slug_from_domain, article_slug

# เพิ่มคอลัมน์ก่อน (ต้องมาก่อน backfill)
COLUMN_DDL = [
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS slug VARCHAR(120) DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS publish_mode VARCHAR(20) DEFAULT 'managed'",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS custom_domain VARCHAR(255) DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS business_context TEXT DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS brand_terms TEXT DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS topic_plan TEXT DEFAULT ''",
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS slug VARCHAR(200) DEFAULT ''",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS description VARCHAR(400) DEFAULT ''",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS schema_json TEXT DEFAULT ''",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS cover_url TEXT DEFAULT ''",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ",
    "ALTER TABLE articles ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()",
]

# unique index สร้าง "หลัง backfill" เท่านั้น (ตอนแรกทุกแถว slug='' จะชนกันถ้าสร้างก่อน)
#  - slug: unique เต็ม (ทุกโปรเจ็คมี slug หลัง backfill)
#  - custom_domain: unique เฉพาะที่ไม่ว่าง (partial) — ให้หลายโปรเจ็คมี '' พร้อมกันได้
INDEX_DDL = [
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_projects_slug ON projects (slug)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_projects_custom_domain ON projects (custom_domain) WHERE custom_domain <> ''",
    "CREATE INDEX IF NOT EXISTS ix_articles_slug ON articles (slug)",
]


async def run(verbose: bool = False) -> None:
    """เพิ่มคอลัมน์ + backfill slug (idempotent) — เรียกได้ทั้งตอน startup และแบบ manual"""
    if not db.enabled():
        if verbose:
            print("DB ยังไม่ได้ตั้งค่า (DATABASE_URL ว่าง) — ข้าม")
        return
    from app.db.models import Project, Article

    async def _exec(ddl):
        try:
            async with db.session() as s:
                await s.execute(text(ddl))
                await s.commit()
            if verbose:
                print("OK  ", ddl[:70])
        except Exception as e:  # noqa: BLE001
            if verbose:
                print("SKIP", ddl[:60], "->", str(e)[:90])

    # 1) เพิ่มคอลัมน์ก่อน (ต้องมาก่อน backfill)
    for ddl in COLUMN_DDL:
        await _exec(ddl)

    # 2) reconcile slug + custom_domain ของโปรเจ็ค — เติมที่ว่าง "และแก้ที่ซ้ำ"
    #    (ต้องไม่เหลือค่าซ้ำก่อนสร้าง unique index ไม่งั้น CREATE UNIQUE INDEX จะล้ม → backstop หาย)
    async with db.session() as s:
        projs = (await s.execute(select(Project).order_by(Project.id))).scalars().all()
        seen_slug, seen_cd, nslug, ncd = set(), set(), 0, 0
        for p in projs:
            cur = (p.slug or "").strip()
            if (not cur) or (cur in seen_slug):           # ว่าง หรือ ซ้ำ → ตั้งใหม่ให้ไม่ซ้ำ
                base = project_slug_from_domain(p.domain or p.name) or "site"
                cand = base if base not in seen_slug else "%s-%d" % (base, p.id)
                while cand in seen_slug:                   # กันชนซ้ำซ้อน (พบยากมาก)
                    cand = "%s-%d-%s" % (base, p.id, secrets.token_hex(2))
                p.slug = cand; nslug += 1; seen_slug.add(cand)
            else:
                seen_slug.add(cur)
            cd = (p.custom_domain or "").strip().lower()
            if cd:
                if cd in seen_cd:                          # โดเมนซ้ำ → ล้างให้ตั้งใหม่ (กัน partial-unique ล้ม)
                    p.custom_domain = ""; ncd += 1
                else:
                    seen_cd.add(cd)
        if nslug or ncd:
            await s.commit()
        if verbose:
            print("reconcile projects: slug_set=%d custom_domain_cleared=%d" % (nslug, ncd))

    # 3) backfill slug ของบทความ
    async with db.session() as s:
        arts = (await s.execute(select(Article))).scalars().all()
        m = 0
        for a in arts:
            if not (a.slug or "").strip():
                a.slug = article_slug(a.title, a.id)
                m += 1
        if m:
            await s.commit()
        if verbose:
            print("backfill articles slug:", m)

    # 4) สร้าง unique index หลัง reconcile — ถ้าล้ม "พิมพ์เสมอ" (แม้ไม่ verbose)
    #    เพราะถ้า index ไม่ถูกสร้าง = uniqueness backstop หาย ต้องเห็นใน log ทันที
    for ddl in INDEX_DDL:
        try:
            async with db.session() as s:
                await s.execute(text(ddl))
                await s.commit()
            if verbose:
                print("OK  ", ddl[:70])
        except Exception as e:  # noqa: BLE001
            print("!! INDEX FAILED (uniqueness backstop MISSING):", ddl[:72], "->", str(e)[:120])

    if verbose:
        print("migration done ✓")


async def _main():
    await run(verbose=True)


if __name__ == "__main__":
    asyncio.run(_main())
