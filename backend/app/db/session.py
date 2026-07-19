"""
เชื่อมฐานข้อมูล (async) — ใช้เมื่อมี DATABASE_URL เท่านั้น
ถ้าไม่ตั้ง DATABASE_URL ระบบยังทำงานได้ (endpoint ที่ไม่พึ่ง DB)
"""
from app.config import settings

_engine = None
_sessionmaker = None


def _normalize(url: str) -> str:
    # ให้ connection string ของ Render/Heroku (postgres://) ใช้ driver async ได้เลย
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


def _init():
    global _engine, _sessionmaker
    if _engine is not None or not settings.database_url:
        return
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import NullPool
    # NullPool: ไม่ reuse connection ข้าม event loop — จำเป็นสำหรับ Celery ที่เรียก asyncio.run() ใหม่ทุก task
    # (ไม่งั้น asyncpg connection ที่ผูก loop เก่าจะพังใน task ที่ 2 เป็นต้นไป)
    _engine = create_async_engine(_normalize(settings.database_url), poolclass=NullPool)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)


def enabled() -> bool:
    return bool(settings.database_url)


def session():
    """คืน AsyncSession context manager — เรียกใน `async with session() as s:`"""
    _init()
    if _sessionmaker is None:
        raise RuntimeError("ยังไม่ได้ตั้ง DATABASE_URL")
    return _sessionmaker()


async def create_all():
    """สร้างตารางทั้งหมด (ใช้ตอน bootstrap; production ควรใช้ Alembic)"""
    _init()
    if _engine is None:
        raise RuntimeError("ยังไม่ได้ตั้ง DATABASE_URL")
    from app.db.models import Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
