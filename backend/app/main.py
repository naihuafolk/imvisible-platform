"""
RankPilot AI — Backend API (FastAPI)
รัน: uvicorn app.main:app --reload   (จากโฟลเดอร์ backend/)
เอกสาร API อัตโนมัติ: http://localhost:8000/docs
"""
import secrets

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings, integration_status
from app.schemas import (
    RankCheckRequest, GSCSummaryRequest, CitationSampleRequest, ProjectCitationRequest,
    ContentGenerateRequest, PublishRequest, MineRequest,
    RegisterRequest, LoginRequest, ProjectCreate, PublishTargetUpdate, ChannelUpdate, DraftRequest,
)
from app.connectors import serp, gsc, citation, content, publish, mining, social
from app.auth import security
from app.auth.deps import get_current_user
from app.db import session as db
from app import public
from app.urls import project_slug_from_domain, project_public_home

app = FastAPI(title="ImVisible API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Managed Hosting — เสิร์ฟบล็อกลูกค้าจาก DB (/blog/{slug}, custom domain, sitemap, llms.txt)
app.include_router(public.router)


@app.on_event("startup")
async def _startup():
    # dev convenience: สร้างตารางให้อัตโนมัติ (production ควรใช้ Alembic)
    if db.enabled():
        try:
            await db.create_all()
        except Exception:
            pass
        # เพิ่มคอลัมน์ Managed Hosting ให้ตารางเดิม + backfill slug (idempotent)
        # สำคัญ: กันช่วงที่ ORM มีคอลัมน์ใหม่แต่ตารางยังไม่มี → ทุก query จะพัง
        try:
            from app import migrate
            await migrate.run()
        except Exception:
            pass


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ImVisible API", "db": db.enabled()}


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
            "language": p.language, "mode": p.mode, "freshness_days": p.freshness_days,
            "slug": p.slug, "publish_mode": p.publish_mode, "custom_domain": p.custom_domain,
            "public_home": project_public_home(p),
            # Site Intelligence (สิ่งที่ระบบอ่านได้จากเว็บลูกค้า)
            "analyzed": bool(getattr(p, "analyzed_at", None)),
            "business_context": getattr(p, "business_context", "") or "",
            "brand_terms": getattr(p, "brand_terms", "") or "",
            "topic_plan": getattr(p, "topic_plan", "") or ""}


def _clean_custom_domain(raw: str) -> str:
    """ตรวจ custom domain ที่ลูกค้าส่งมา — กันตั้งเป็น *.imvisible.tech (แย่งซับโดเมนคนอื่น) + กันค่าเพี้ยน"""
    d = (raw or "").strip().lower().split("/")[0].split(":")[0]
    if not d:
        return ""
    base = settings.managed_base_domain.lower()
    if d == base or d.endswith("." + base):
        raise HTTPException(422, "custom domain ต้องเป็นโดเมนของลูกค้าเอง (ตั้งเป็น *.%s ไม่ได้)" % base)
    if " " in d or "." not in d or ".." in d or d.startswith(".") or d.endswith("."):
        raise HTTPException(422, "custom domain ไม่ถูกต้อง")
    return d


def _norm_publish_mode(mode: str) -> str:
    """ลูกค้าตั้งได้แค่ managed | none (wordpress = Phase 2 ต้องมี per-project creds ก่อน)"""
    return mode if mode in ("managed", "none") else "managed"


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
    """ลูกค้าใส่แค่ลิงก์เว็บ (url) หรือ domain → ระบบแตกเป็น name/domain/slug + ตั้งปลายทางเผยแพร่ให้เอง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from urllib.parse import urlparse
    from app.db.models import Project
    domain = (req.domain or "").strip().lower()
    if not domain and req.url:                       # "ลูกค้าใส่แค่ลิงก์"
        u = req.url.strip()
        if "://" not in u:
            u = "https://" + u
        domain = (urlparse(u).hostname or "").removeprefix("www.")
    if not domain:
        raise HTTPException(422, "กรุณาระบุเว็บไซต์ (url หรือ domain)")
    name = (req.name or "").strip() or domain
    base_slug = project_slug_from_domain(domain)
    custom = _clean_custom_domain(req.custom_domain)
    pmode = _norm_publish_mode(req.publish_mode or "managed")
    async with db.session() as s:
        if custom:                                   # กันโดเมนซ้ำกับโปรเจ็คอื่น (backstop = unique index)
            dup = (await s.execute(select(Project.id).where(Project.custom_domain == custom))).first()
            if dup:
                raise HTTPException(409, "โดเมนนี้ถูกใช้กับโปรเจ็คอื่นแล้ว")
        slug = base_slug
        p = None
        for _ in range(6):                           # slug unique index จับการชน (รวม race) → retry
            cand = Project(user_id=user["id"], name=name, domain=domain, country=req.country,
                           language=req.language or "th", mode=req.mode,
                           publish_mode=pmode, custom_domain=custom, slug=slug)
            s.add(cand)
            try:
                await s.commit()
                p = cand
                break
            except IntegrityError:
                await s.rollback()
                slug = "%s-%s" % (base_slug, secrets.token_hex(3))
        if p is None:
            raise HTTPException(409, "สร้างโปรเจ็คไม่สำเร็จ (โดเมน/slug ชนกัน) ลองใหม่อีกครั้ง")
        await s.refresh(p)
        result = _proj_dict(p)
        new_id = p.id
    # "ใส่แค่ลิงก์" → ระบบไปอ่านเว็บลูกค้าเองทันที (เบื้องหลัง · ล้มก็ไม่กระทบการสร้างโปรเจ็ค)
    try:
        from app.worker.tasks import analyze_project
        analyze_project.delay(new_id)
        result["analyzing"] = True
    except Exception:  # noqa: BLE001
        result["analyzing"] = False
    return result


@app.put("/api/projects/{project_id}/publish")
async def set_publish_target(project_id: int, req: PublishTargetUpdate, user=Depends(get_current_user)):
    """ตั้งปลายทางเผยแพร่ของโปรเจ็ค: managed (เราโฮสต์ให้) / wordpress / none + custom domain"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    if req.publish_mode not in ("managed", "none"):
        raise HTTPException(422, "publish_mode ต้องเป็น managed | none")
    custom = _clean_custom_domain(req.custom_domain)
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        if custom:                                   # กันแย่งโดเมนโปรเจ็คอื่น (backstop = unique index)
            dup = (await s.execute(select(Project.id).where(
                Project.custom_domain == custom, Project.id != project_id))).first()
            if dup:
                raise HTTPException(409, "โดเมนนี้ถูกใช้กับโปรเจ็คอื่นแล้ว")
        p.publish_mode = req.publish_mode
        p.custom_domain = custom
        try:
            await s.commit()
        except IntegrityError:
            await s.rollback()
            raise HTTPException(409, "โดเมนนี้ถูกใช้แล้ว")
        await s.refresh(p)
        result = _proj_dict(p)
    return result


@app.post("/api/projects/{project_id}/grow")
async def grow_project(project_id: int, user=Depends(get_current_user)):
    """🚀 สั่ง 'วงจรโต' ให้โปรเจ็คนี้เดี๋ยวนี้: ขุดคำถาม→เขียน→เผยแพร่ (เข้าคิว Celery ทำเบื้องหลัง)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    async with db.session() as s:
        p = await s.get(Project, project_id)
    if not p or p.user_id != user["id"]:
        raise HTTPException(404, "ไม่พบโปรเจ็ค")
    try:
        from app.worker.tasks import produce_for_project
        task = produce_for_project.delay(project_id, 1)
        return {"queued": True, "task_id": str(task.id), "project": p.name, "mode": p.mode}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ต่อคิวงานไม่ได้ (backend/worker/redis พร้อมไหม): " + str(e))


@app.post("/api/projects/{project_id}/analyze")
async def analyze_project_ep(project_id: int, user=Depends(get_current_user)):
    """🔎 อ่านเว็บลูกค้าจริง → สกัดบริบทธุรกิจ + คำแบรนด์ + วางแผนหัวข้อ (เข้าคิวเบื้องหลัง)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        name = p.name
    try:
        from app.worker.tasks import analyze_project
        task = analyze_project.delay(project_id)
        return {"queued": True, "task_id": str(task.id), "project": name}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ต่อคิวไม่ได้ (worker/redis พร้อมไหม): " + str(e))


@app.get("/api/projects/{project_id}/articles")
async def project_articles(project_id: int, user=Depends(get_current_user)):
    """ดูบทความที่ระบบผลิตให้โปรเจ็คนี้ (ของจริงจาก DB)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project, Article
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        rows = (await s.execute(
            select(Article).where(Article.project_id == project_id).order_by(Article.id.desc()))).scalars().all()
    return {"articles": [{"id": a.id, "title": a.title, "status": a.status,
                          "words": a.words, "url": a.url} for a in rows]}


# ---------- Distribution (ช่องทางกระจาย + Log โปร่งใส) ----------
async def _own_project(s, project_id, user):
    from app.db.models import Project
    p = await s.get(Project, project_id)
    if not p or p.user_id != user["id"]:
        raise HTTPException(404, "ไม่พบโปรเจ็ค")
    return p


# ---------- AI Citation ต่อโปรเจ็ค (Prompt Sampling ที่ 'บันทึกผล' → สะสมเป็นแนวโน้ม) ----------
@app.post("/api/projects/{project_id}/citation/sample")
async def project_citation_sample(project_id: int, req: ProjectCitationRequest,
                                  user=Depends(get_current_user)):
    """M5 · รัน Prompt Sampling ให้โปรเจ็คนี้ 'แล้วบันทึกผล' (CitationSnapshot)
    ต่างจาก /api/citation/sample เดิมที่ยิงแล้วทิ้ง — อันนี้ทำให้ SoV สะสมเป็นแนวโน้มจริง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    async with db.session() as s:
        await _own_project(s, project_id, user)   # กันตรวจ/บันทึกให้โปรเจ็คคนอื่น
    try:
        from app.worker.tasks import _sample_and_save
        res = await _sample_and_save(project_id, req.questions or None)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
    if res.get("error"):
        raise HTTPException(502, res["error"])
    return res


@app.get("/api/projects/{project_id}/rank/history")
async def project_rank_history(project_id: int, user=Depends(get_current_user)):
    """M5 · แนวโน้มอันดับ Google ที่ 'เก็บสะสมจริง' (RankSnapshot จาก beat รายวัน)
    คืนสรุป (ติดหน้า1/Top3/อันดับเฉลี่ย) + อันดับล่าสุดต่อคีย์เวิร์ด + แนวโน้มจำนวนหน้า1
    ไม่มีข้อมูล = ว่างจริง (บัญชีจริงต้องรอเก็บ 1-7 วัน หรือกดตรวจสด)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import RankSnapshot
    async with db.session() as s:
        await _own_project(s, project_id, user)
        rows = (await s.execute(
            select(RankSnapshot).where(RankSnapshot.project_id == project_id)
            .order_by(RankSnapshot.checked_at))).scalars().all()

    latest: dict[str, dict] = {}          # อันดับล่าสุดต่อคีย์เวิร์ด (rows เรียง asc → ตัวหลังทับ = ใหม่สุด)
    day_page1: dict[str, dict] = {}       # day → {keyword: on_page1} สำหรับแนวโน้มหน้า 1
    for r in rows:
        latest[r.keyword] = {"keyword": r.keyword, "rank": r.rank,
                             "on_page1": bool(r.on_page1),
                             "checked_at": r.checked_at.isoformat() if r.checked_at else ""}
        d = r.checked_at.date().isoformat() if r.checked_at else ""
        if d:
            day_page1.setdefault(d, {})[r.keyword] = bool(r.on_page1)

    kws = sorted(latest.values(),
                 key=lambda k: (k["rank"] is None, k["rank"] if k["rank"] is not None else 999))
    ranked = [k["rank"] for k in kws if k["rank"] is not None]
    page1 = sum(1 for k in kws if k["on_page1"])
    top3 = sum(1 for k in kws if k["rank"] is not None and k["rank"] <= 3)
    avg_position = round(sum(ranked) / len(ranked), 1) if ranked else None
    trend = [{"date": d, "page1": sum(1 for v in m.values() if v)}
             for d, m in sorted(day_page1.items())]
    return {
        "keywords_tracked": len(latest),
        "page1": page1, "top3": top3, "avg_position": avg_position,
        "keywords": kws[:50],
        "page1_trend": [t["page1"] for t in trend],
        "trend": trend,
        "count": len(latest),
        "note": "อันดับจริงจาก SERP API — ตรวจสอบได้ (เสิร์ชเองก็เห็น)",
    }


# ---------- AEO/SEO Score Engine (M3) — "ตัวแปรที่ทำให้ติดเร็ว" วัดจากบทความจริง ----------
def _score_article(art, proj):
    from app.connectors import aeo_score
    from datetime import datetime, timezone
    age = None
    if getattr(art, "updated_at", None):
        try:
            age = (datetime.now(timezone.utc) - art.updated_at).days
        except Exception:  # noqa: BLE001
            age = None
    return aeo_score.score(
        art.html or "", title=art.title or "", description=(art.description or "")[:155],
        schema_json=art.schema_json or "", cover_url=art.cover_url or "",
        keyword=art.title or "", target_words=1200,
        age_days=age, freshness_days=getattr(proj, "freshness_days", 120) or 120)


@app.get("/api/articles/{article_id}/aeo")
async def article_aeo(article_id: int, user=Depends(get_current_user)):
    """M3 · คะแนน AEO/SEO ของบทความเดียว + breakdown ต่อปัจจัย + วิธีแก้ (คำนวณสดจาก HTML จริง)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Article, Project
    async with db.session() as s:
        art = await s.get(Article, article_id)
        if not art:
            raise HTTPException(404, "ไม่พบบทความ")
        proj = await s.get(Project, art.project_id)
        if not proj or proj.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบบทความ")
        res = _score_article(art, proj)
        if art.aeo_score != res["score"]:      # อัปเดตคะแนนที่เก็บให้ตรงกับที่วัดล่าสุด
            art.aeo_score = res["score"]
            await s.commit()
    res.update({"article_id": art.id, "title": art.title, "url": art.url})
    return res


@app.get("/api/projects/{project_id}/aeo")
async def project_aeo(project_id: int, user=Depends(get_current_user)):
    """M3 · ภาพรวมคะแนน AEO/SEO ทั้งโปรเจ็ค — คะแนนเฉลี่ย, การกระจายเกรด, คะแนนต่อบทความ,
    และ 'แก้ตรงไหนได้คะแนนรวมมากสุด' (จัดลำดับงานปรับให้ติดเร็ว)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Article, Project
    async with db.session() as s:
        proj = await _own_project(s, project_id, user)
        arts = (await s.execute(
            select(Article).where(Article.project_id == project_id)
            .order_by(Article.id.desc()).limit(100))).scalars().all()
        items, dist, agg = [], {"A": 0, "B": 0, "C": 0, "D": 0}, {}
        changed = False
        for a in arts:
            r = _score_article(a, proj)
            if a.aeo_score != r["score"]:
                a.aeo_score = r["score"]; changed = True
            dist[r["grade"]] = dist.get(r["grade"], 0) + 1
            for f in r["factors"]:
                if not f["ok"]:
                    g = agg.setdefault(f["key"], {"label": f["label"], "gain": 0.0, "count": 0})
                    g["gain"] += f["weight"] * (1 - f["earned"]); g["count"] += 1
            items.append({"id": a.id, "title": a.title, "url": a.url,
                          "status": a.status, "score": r["score"], "grade": r["grade"]})
        if changed:
            await s.commit()
    scores = [i["score"] for i in items]
    avg = round(sum(scores) / len(scores)) if scores else None
    top_fixes = sorted(({"key": k, **v, "gain": round(v["gain"], 1)} for k, v in agg.items()),
                       key=lambda x: x["gain"], reverse=True)[:6]
    return {
        "count": len(items), "avg_score": avg, "grade_dist": dist,
        "articles": items, "top_fixes": top_fixes,
        "note": "คะแนนวัดจากปัจจัยจัดอันดับจริงของแต่ละบทความ — แก้ตามลำดับ 'ได้คะแนนรวมมากสุด' เพื่อดันทั้งคลัสเตอร์",
    }


@app.get("/api/projects/{project_id}/citation/history")
async def project_citation_history(project_id: int, user=Depends(get_current_user)):
    """แนวโน้ม Share of Voice ที่ 'สะสมจากการรันจริง' — จัดกลุ่มเป็นรอบ (ต่อครั้งที่รัน)
    คืนซีรีส์ overall + ต่อเอนจิน เพื่อวาดกราฟแนวโน้มบัญชีจริง (ไม่มีข้อมูล = ว่างจริง)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import CitationSnapshot
    async with db.session() as s:
        await _own_project(s, project_id, user)
        rows = (await s.execute(
            select(CitationSnapshot).where(CitationSnapshot.project_id == project_id)
            .order_by(CitationSnapshot.sampled_at))).scalars().all()

    runs: list[dict] = []
    by_bucket: dict[str, dict] = {}
    for r in rows:
        # จัดกลุ่มแถวของ 'รอบเดียวกัน' ด้วยเวลาระดับนาที (การรัน 1 ครั้งเขียนหลายเอนจินพร้อมกัน)
        at = r.sampled_at
        bucket = at.strftime("%Y-%m-%dT%H:%M") if at else ""
        run = by_bucket.get(bucket)
        if run is None:
            run = {"at": at.isoformat() if at else "", "per_engine": {}}
            by_bucket[bucket] = run
            runs.append(run)
        if r.sov_percent is not None:
            run["per_engine"][r.engine] = r.sov_percent

    trend = []
    for run in runs:
        vals = list(run["per_engine"].values())
        run["overall"] = round(sum(vals) / len(vals), 1) if vals else None
        if run["overall"] is not None:
            trend.append(run["overall"])

    latest = runs[-1] if runs else None
    prev = runs[-2] if len(runs) >= 2 else None
    return {
        "runs": runs,
        "trend": trend,                       # ซีรีส์ overall (วาด sparkline แนวโน้ม)
        "latest_sov": latest["overall"] if latest else None,
        "prev_sov": prev["overall"] if prev else None,
        "per_engine_latest": latest["per_engine"] if latest else {},
        "count": len(runs),
        "note": "ค่าประมาณเชิงสถิติจากการสุ่มถาม — สะสมจากการรันจริงของโปรเจ็คนี้",
    }


@app.get("/api/projects/{project_id}/channels")
async def list_channels(project_id: int, user=Depends(get_current_user)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import DistributionChannel
    async with db.session() as s:
        await _own_project(s, project_id, user)
        rows = (await s.execute(select(DistributionChannel).where(
            DistributionChannel.project_id == project_id))).scalars().all()
        # ไม่คืน token — คืนแค่ว่าเชื่อมแล้วหรือยัง (โปร่งใส แต่ไม่รั่วความลับ)
        out = [{"kind": c.kind, "ref": c.ref, "enabled": c.enabled, "connected": bool(c.token_enc)} for c in rows]
    return {"channels": out}


@app.put("/api/projects/{project_id}/channels")
async def set_channel(project_id: int, req: ChannelUpdate, user=Depends(get_current_user)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import DistributionChannel
    from app import crypto
    if req.kind not in social.SUPPORTED:
        raise HTTPException(422, "ช่องทางไม่รองรับ (รองรับ: %s)" % ", ".join(social.SUPPORTED))
    async with db.session() as s:
        await _own_project(s, project_id, user)
        c = (await s.execute(select(DistributionChannel).where(
            DistributionChannel.project_id == project_id, DistributionChannel.kind == req.kind))).scalars().first()
        if not c:
            c = DistributionChannel(project_id=project_id, kind=req.kind); s.add(c)
        c.ref = (req.ref or "").strip()
        c.enabled = bool(req.enabled)
        if req.token:                                # ส่ง token = ตั้ง/เปลี่ยน · ว่าง = คงเดิม
            c.token_enc = crypto.enc(req.token.strip())
        await s.commit()
        result = {"kind": c.kind, "ref": c.ref, "enabled": c.enabled, "connected": bool(c.token_enc)}
    return result


@app.get("/api/articles/{article_id}/distribution")
async def article_distribution(article_id: int, user=Depends(get_current_user)):
    """Log การกระจายต่อบทความ — ลูกค้าเห็นว่าคอนเทนต์ไปโผล่ที่ไหนบ้าง (โปร่งใส)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Article, DistributionEvent
    async with db.session() as s:
        art = await s.get(Article, article_id)
        if not art:
            raise HTTPException(404, "ไม่พบบทความ")
        await _own_project(s, art.project_id, user)
        rows = (await s.execute(select(DistributionEvent).where(
            DistributionEvent.article_id == article_id).order_by(DistributionEvent.id))).scalars().all()
        out = [{"channel": e.channel, "status": e.status, "url": e.url, "detail": e.detail,
                "at": e.created_at.isoformat() if e.created_at else ""} for e in rows]
    return {"events": out}


@app.post("/api/articles/{article_id}/distribute")
async def redistribute(article_id: int, user=Depends(get_current_user)):
    """สั่งกระจายบทความที่เผยแพร่แล้วซ้ำ (เช่น เพิ่งเชื่อมช่องใหม่)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Article
    async with db.session() as s:
        art = await s.get(Article, article_id)
        if not art:
            raise HTTPException(404, "ไม่พบบทความ")
        await _own_project(s, art.project_id, user)
        pid = art.project_id
    try:
        from app.worker.tasks import distribute_article
        task = distribute_article.delay(pid, article_id)
        return {"queued": True, "task_id": str(task.id)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ต่อคิวไม่ได้ (worker/redis พร้อมไหม): " + str(e))


# ---------- Distribution Discovery (หาช่องกระจายต่อลูกค้า + ร่างคำตอบ · ขาว) ----------
@app.post("/api/projects/{project_id}/discover")
async def discover_channels(project_id: int, user=Depends(get_current_user)):
    """หา 'โอกาสกระจาย' ต่อลูกค้า: กระทู้ Pantip / ชุมชน / ไดเรกทอรี ที่ตรง niche (SERP จริง)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project, Article
    from app.connectors import discovery
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        name, domain = p.name, p.domain
        lang = "English" if str(p.language).lower().startswith("en") else "ภาษาไทย"
        titles = (await s.execute(select(Article.title).where(
            Article.project_id == project_id).order_by(Article.id.desc()).limit(3))).scalars().all()
    kws = [name] + [t for t in titles if t]
    try:
        return await discovery.discover(name, domain, kws, lang)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "หาโอกาสกระจายไม่ได้ (ตรวจคีย์ SERP/DataForSEO): " + str(e)[:150])


@app.post("/api/projects/{project_id}/draft-reply")
async def draft_reply_ep(project_id: int, req: DraftRequest, user=Depends(get_current_user)):
    """AI ร่างคำตอบชุมชนแบบจริงใจ (คนเอาไปตรวจ+โพสต์เอง · ไม่ auto-ยิง = ไม่โดนแบน)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    from app.connectors import discovery
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        brand = p.name
        lang = "English" if str(p.language).lower().startswith("en") else "ภาษาไทย"
    try:
        return await discovery.draft_reply(req.question, req.snippet, req.url, brand, lang)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ร่างคำตอบไม่ได้ (ตรวจคีย์ LLM): " + str(e)[:150])


@app.get("/api/tls/check")
async def tls_check(domain: str = ""):
    """Caddy on-demand TLS 'ask' — คืน 200 เฉพาะโดเมนลูกค้าที่ลงทะเบียนจริง (กันคนสุ่มยิงขอ cert)"""
    d = (domain or "").strip().lower().split(":")[0]
    if not d:
        raise HTTPException(400, "no domain")
    base = settings.managed_base_domain.lower()
    from app.db.models import Project
    if d == base or d.endswith("." + base):          # {slug}.imvisible.tech → ต้องมี slug จริง
        sub = d[: -(len(base) + 1)] if d.endswith("." + base) else ""
        if db.enabled() and sub and "." not in sub:
            async with db.session() as s:
                p = (await s.execute(select(Project).where(Project.slug == sub))).scalars().first()
            if p:
                return {"ok": True, "domain": d}
        raise HTTPException(404, "unknown subdomain")
    if db.enabled():                                 # custom domain → ต้องผูกกับโปรเจ็คไว้
        async with db.session() as s:
            p = (await s.execute(select(Project).where(Project.custom_domain == d))).scalars().first()
        if p:
            return {"ok": True, "domain": d}
    raise HTTPException(404, "unknown domain")


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
