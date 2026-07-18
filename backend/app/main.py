"""
RankPilot AI — Backend API (FastAPI)
รัน: uvicorn app.main:app --reload   (จากโฟลเดอร์ backend/)
เอกสาร API อัตโนมัติ: http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import settings, integration_status
from app.schemas import (
    RankCheckRequest, GSCSummaryRequest, CitationSampleRequest,
    ContentGenerateRequest, PublishRequest, MineRequest,
    RegisterRequest, LoginRequest, ProjectCreate,
)
from app.connectors import serp, gsc, citation, content, publish, mining
from app.auth import security
from app.auth.deps import get_current_user
from app.db import session as db

app = FastAPI(title="RankPilot AI API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    # dev convenience: สร้างตารางให้อัตโนมัติ (production ควรใช้ Alembic)
    if db.enabled():
        try:
            await db.create_all()
        except Exception:
            pass


@app.get("/health")
async def health():
    return {"status": "ok", "service": "RankPilot AI API", "db": db.enabled()}


# ---------- Auth (JWT + hash รหัสผ่าน) ----------
def _user_dict(u):
    return {"id": u.id, "email": u.email, "name": u.name, "plan": u.plan}


@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import User
    async with db.session() as s:
        exists = (await s.execute(select(User).where(User.email == req.email))).scalar_one_or_none()
        if exists:
            raise HTTPException(409, "อีเมลนี้ถูกใช้แล้ว")
        u = User(email=req.email, name=req.name or req.email.split("@")[0],
                 password_hash=security.hash_password(req.password))
        s.add(u); await s.commit(); await s.refresh(u)
    return {"token": security.create_token(u.id, u.email), "user": _user_dict(u)}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import User
    async with db.session() as s:
        u = (await s.execute(select(User).where(User.email == req.email))).scalar_one_or_none()
    if not u or not security.verify_password(req.password, u.password_hash):
        raise HTTPException(401, "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    return {"token": security.create_token(u.id, u.email), "user": _user_dict(u)}


@app.get("/api/auth/me")
async def me(user=Depends(get_current_user)):
    if not db.enabled():
        return user
    from app.db.models import User
    async with db.session() as s:
        u = await s.get(User, user["id"])
    if not u:
        raise HTTPException(404, "ไม่พบผู้ใช้")
    return _user_dict(u)


# ---------- Projects (เชื่อม DB จริง) ----------
def _proj_dict(p):
    return {"id": p.id, "name": p.name, "domain": p.domain, "country": p.country,
            "mode": p.mode, "freshness_days": p.freshness_days}


@app.get("/api/projects")
async def list_projects(user=Depends(get_current_user)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    async with db.session() as s:
        rows = (await s.execute(select(Project).where(Project.user_id == user["id"]).order_by(Project.id))).scalars().all()
    return {"projects": [_proj_dict(p) for p in rows]}


@app.post("/api/projects")
async def create_project(req: ProjectCreate, user=Depends(get_current_user)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    async with db.session() as s:
        p = Project(user_id=user["id"], name=req.name, domain=req.domain, country=req.country, mode=req.mode)
        s.add(p); await s.commit(); await s.refresh(p)
    return _proj_dict(p)


@app.get("/api/integrations")
async def integrations():
    """สถานะการเชื่อมต่อจริง (คีย์ครบไหม) — ตรงกับหน้า 'การตั้งค่า' ในแดชบอร์ด"""
    items = integration_status()
    required_ready = all(i["connected"] for i in items if i["required"])
    return {"ready_for_measurement": required_ready, "integrations": items}


@app.post("/api/mine")
async def mine_questions(req: MineRequest):
    """M1 · ขุดคำถามจริง (Google Suggest + People Also Ask)"""
    try:
        return await mining.mine(req.seed, req.location_code, req.language_code)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/rank/check")
async def rank_check(req: RankCheckRequest):
    """M5 · อันดับ Google จริง (DataForSEO) — ตรวจสอบได้: เสิร์ชเองก็เห็น"""
    try:
        return await serp.rank_check(req.keyword, req.domain, req.location_code, req.language_code)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/gsc/summary")
async def gsc_summary(req: GSCSummaryRequest):
    """M5 · คลิก/Impressions/อันดับ จริงจาก Google Search Console"""
    try:
        return await gsc.summary(req.site_url, req.days)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/citation/sample")
async def citation_sample(req: CitationSampleRequest):
    """M5 · AI Citation / Share of Voice (Prompt Sampling — ค่าประมาณเชิงสถิติ)"""
    try:
        return await citation.sample(req.questions, req.brand_terms, req.domain, req.engines)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/content/generate")
async def content_generate(req: ContentGenerateRequest):
    """M2 · ผลิตบทความสูตร AEO ด้วย LLM จริง"""
    try:
        return await content.generate(req.topic, req.fmt, req.words)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/publish")
async def publish_post(req: PublishRequest):
    """M4 · เผยแพร่ขึ้น WordPress จริง + IndexNow ping"""
    try:
        return await publish.publish_and_index(req.title, req.html, req.status, req.url_path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
