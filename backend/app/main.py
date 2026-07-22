"""
RankPilot AI — Backend API (FastAPI)
รัน: uvicorn app.main:app --reload   (จากโฟลเดอร์ backend/)
เอกสาร API อัตโนมัติ: http://localhost:8000/docs
"""
import secrets
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings, integration_status, is_prod, DEV_JWT_DEFAULT

# Error monitoring (เปิดเมื่อมี SENTRY_DSN + ติดตั้ง sentry-sdk) — ไม่มี = ข้ามเงียบ ๆ
if settings.sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1,
                        environment=settings.app_env)
    except Exception:  # noqa: BLE001
        pass
from app.schemas import (
    RankCheckRequest, GSCSummaryRequest, CitationSampleRequest, ProjectCitationRequest,
    ContentGenerateRequest, PublishRequest, MineRequest,
    RegisterRequest, LoginRequest, ProjectCreate, PublishTargetUpdate, ChannelUpdate, DraftRequest,
    CredentialUpdate, KeywordRequest, GSCDaysRequest, CheckoutRequest, ScheduleRequest, TeamInvite,
    KeywordSuggestRequest,
)
from app.connectors import serp, gsc, citation, content, publish, mining, social, billing, pagespeed
from app.auth import security
from app.auth.deps import get_current_user
from app.db import session as db
from app import public, legal
from app.urls import project_slug_from_domain, project_public_home

app = FastAPI(title="ImVisible API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(legal.router)   # /legal/terms, /legal/privacy (PDPA)
# Managed Hosting — เสิร์ฟบล็อกลูกค้าจาก DB (/blog/{slug}, custom domain, sitemap, llms.txt)
app.include_router(public.router)


# ---------- Security headers (ทุก response) ----------
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-XSS-Protection", "0")
    if is_prod():
        resp.headers.setdefault("Strict-Transport-Security",
                                "max-age=63072000; includeSubDomains")
    return resp


# ---------- Rate limit (กัน brute-force ที่ auth) — in-memory ต่อ process ----------
_rl_hits: dict = defaultdict(deque)


async def rate_limit_auth(request: Request):
    ip = (request.client.host if request.client else "") or "unknown"
    now = time.time()
    dq = _rl_hits[ip]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= settings.rate_limit_per_min:
        raise HTTPException(429, "คำขอถี่เกินไป กรุณาลองใหม่ในอีกสักครู่")
    dq.append(now)


@app.on_event("startup")
async def _startup():
    # ความปลอดภัย: prod ห้ามใช้ JWT_SECRET ค่า dev (fail closed — ไม่ยอมสตาร์ท)
    if is_prod() and settings.jwt_secret == DEV_JWT_DEFAULT:
        raise RuntimeError("ตั้ง JWT_SECRET ที่ยาว/สุ่มจริงก่อนรัน production (ห้ามใช้ค่า dev)")
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
    return {"status": "ok", "service": "ImVisible API", "db": db.enabled(),
            "registration_open": settings.registration_open}


# ---------- Auth (JWT + hash รหัสผ่าน) ----------
def _user_dict(u):
    return {"id": u.id, "email": u.email, "name": u.name, "plan": u.plan}


@app.post("/api/auth/register")
async def register(req: RegisterRequest, _rl=Depends(rate_limit_auth)):
    if not settings.registration_open:
        raise HTTPException(403, "ขณะนี้ยังไม่เปิดรับสมัครสมาชิกทั่วไป")
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    if not req.accept_terms:
        raise HTTPException(422, "ต้องยอมรับข้อกำหนดการใช้บริการและนโยบายความเป็นส่วนตัวก่อนสมัคร")
    from app.db.models import User
    async with db.session() as s:
        exists = (await s.execute(select(User).where(User.email == req.email))).scalar_one_or_none()
        if exists:
            raise HTTPException(409, "อีเมลนี้ถูกใช้แล้ว")
        u = User(email=req.email, name=req.name or req.email.split("@")[0],
                 password_hash=security.hash_password(req.password))
        s.add(u); await s.commit(); await s.refresh(u)
        uid, uemail = u.id, u.email
        udict = _user_dict(u)
    from app import team
    await team.link_invites(uid, uemail)          # ผูกคำเชิญที่ค้างอยู่ (ถ้ามี)
    return {"token": security.create_token(uid, uemail), "user": udict}


@app.post("/api/auth/login")
async def login(req: LoginRequest, _rl=Depends(rate_limit_auth)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import User
    async with db.session() as s:
        u = (await s.execute(select(User).where(User.email == req.email))).scalar_one_or_none()
    if not u or not security.verify_password(req.password, u.password_hash):
        raise HTTPException(401, "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    from app import team
    await team.link_invites(u.id, u.email)        # ผูกคำเชิญที่มีมาหลังสมัคร
    return {"token": security.create_token(u.id, u.email), "user": _user_dict(u)}


@app.get("/api/projects/overview")
async def projects_overview(user=Depends(get_current_user)):
    """ภาพรวมทุกโปรเจ็คในครั้งเดียว (สำหรับ agency ดูลูกค้าทุกรายพร้อมกัน)
    ต่อโปรเจ็ค: บทความ/เผยแพร่/คะแนน AEO เฉลี่ย/ติดหน้า 1/กิจกรรมล่าสุด"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from sqlalchemy import func, case
    from app import team
    from app.db.models import Project, Article, RankSnapshot
    owners = await team.accessible_owner_ids(user["id"])
    async with db.session() as s:
        projs = (await s.execute(select(Project).where(Project.user_id.in_(owners))
                                 .order_by(Project.id))).scalars().all()
        pids = [p.id for p in projs]
        if not pids:
            return {"projects": []}
        arows = (await s.execute(
            select(Article.project_id, func.count(Article.id),
                   func.sum(case((Article.status == "published", 1), else_=0)),
                   func.max(Article.created_at))
            .where(Article.project_id.in_(pids)).group_by(Article.project_id))).all()
        stat = {pid: (c or 0, pub or 0, last) for pid, c, pub, last in arows}
        avgrows = (await s.execute(
            select(Article.project_id, func.avg(Article.aeo_score))
            .where(Article.project_id.in_(pids), Article.status == "published", Article.aeo_score > 0)
            .group_by(Article.project_id))).all()
        aeoavg = {pid: round(float(a)) for pid, a in avgrows if a is not None}
        snaps = (await s.execute(
            select(RankSnapshot.project_id, RankSnapshot.keyword, RankSnapshot.on_page1)
            .where(RankSnapshot.project_id.in_(pids))
            .order_by(RankSnapshot.checked_at))).all()
        latest = {}
        for pid, kw, op in snaps:
            latest[(pid, kw)] = bool(op)
        page1 = {}
        for (pid, _kw), op in latest.items():
            if op:
                page1[pid] = page1.get(pid, 0) + 1
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    def _status(arts, last):
        """สถานะทำงานจริง จากบทความล่าสุดที่ระบบผลิต (ไม่ปลอม)"""
        if arts == 0:
            return ("idle", "ยังไม่เริ่มผลิต", "slate")
        if isinstance(last, datetime):
            lt = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
            age = (now - lt).days
        else:
            age = 999
        if age <= 3:
            return ("active", "ทำงานปกติ", "green")
        if age <= 10:
            return ("slow", "ช้าลง", "amber")
        return ("stalled", "ไม่เคลื่อนไหว", "red")

    out = []
    for p in projs:
        c, pub, last = stat.get(p.id, (0, 0, None))
        skey, slabel, stone = _status(int(c), last)
        out.append({"id": p.id, "name": p.name, "domain": p.domain,
                    "public_home": project_public_home(p), "mode": p.mode,
                    "articles": int(c), "published": int(pub),
                    "avg_aeo": aeoavg.get(p.id), "page1": page1.get(p.id, 0),
                    "last_at": last.isoformat() if last else "",
                    "status": skey, "status_label": slabel, "status_tone": stone})
    return {"projects": out}


@app.get("/api/admin/costs")
async def admin_costs(user=Depends(get_current_user)):
    """ต้นทุน API เดือนนี้ (ประมาณการ = ใช้งานจริงจาก DB × ราคาต่อหน่วยโดยประมาณ) — เฉพาะแอดมิน
    ไว้เตรียมเติมเงิน/เครดิตของแต่ละผู้ให้บริการ (ไม่ใช่บิลจริง · ยอดจริงดูที่ console แต่ละเจ้า)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import usage
    if (await usage.user_plan(user["id"])) != "admin":
        raise HTTPException(403, "หน้านี้สำหรับแอดมินเท่านั้น")
    from datetime import datetime, timezone
    from sqlalchemy import func
    from app.db.models import Project, Article, RankSnapshot, CitationSnapshot
    from app.config import settings
    now = datetime.now(timezone.utc)
    mstart = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    async with db.session() as s:
        articles = int((await s.execute(select(func.count(Article.id)).where(Article.created_at >= mstart))).scalar() or 0)
        with_img = int((await s.execute(select(func.count(Article.id)).where(Article.created_at >= mstart, Article.cover_url != ""))).scalar() or 0)
        ranks = int((await s.execute(select(func.count(RankSnapshot.id)).where(RankSnapshot.checked_at >= mstart))).scalar() or 0)
        cites = int((await s.execute(select(func.count(CitationSnapshot.id)).where(CitationSnapshot.sampled_at >= mstart))).scalar() or 0)
        projects = int((await s.execute(select(func.count(Project.id)))).scalar() or 0)
    # ราคาต่อหน่วยโดยประมาณ (บาท) — อ้างอิงราคาสาธารณะทั่วไป ปรับได้ภายหลัง
    U = {"article": 12.0, "image": 5.0, "rank": 0.3, "citation": 2.0}
    lines = [
        {"key": "llm", "name": "LLM — เขียนบทความ (3-stage)", "provider": "Anthropic / OpenAI / Gemini",
         "usage": articles, "unit": "บทความ", "unit_cost": U["article"], "est": round(articles * U["article"]),
         "topup": "console.anthropic.com · platform.openai.com · aistudio.google.com",
         "active": bool(settings.anthropic_api_key or settings.openai_api_key or settings.gemini_api_key)},
        {"key": "image", "name": "รูปภาพ — ปก + ในเนื้อ (FLUX / Seedream)",
         "provider": ("fal.ai (FLUX)" if settings.fal_key else "ModelArk (BytePlus)"),
         "usage": with_img, "unit": "บทความมีรูป", "unit_cost": U["image"], "est": round(with_img * U["image"]),
         "topup": ("fal.ai › Billing" if settings.fal_key else "BytePlus Console › ModelArk"),
         "active": bool(settings.fal_key or settings.ark_api_key)},
        {"key": "rank", "name": "วัดอันดับ + ขุดคีย์เวิร์ด", "provider": "DataForSEO",
         "usage": ranks, "unit": "ครั้ง", "unit_cost": U["rank"], "est": round(ranks * U["rank"]),
         "topup": "app.dataforseo.com › Billing", "active": bool(settings.dataforseo_login and settings.dataforseo_password)},
        {"key": "citation", "name": "วัด AI Citation (ถาม AI จริง)", "provider": "LLM หลายเจ้า",
         "usage": cites, "unit": "ครั้ง", "unit_cost": U["citation"], "est": round(cites * U["citation"]),
         "topup": "เดียวกับ LLM", "active": bool(settings.anthropic_api_key or settings.gemini_api_key or settings.openai_api_key or settings.perplexity_api_key)},
    ]
    return {"month": mstart.strftime("%Y-%m"), "projects": projects,
            "lines": lines, "total_est": sum(x["est"] for x in lines),
            "video_enabled": bool(settings.ark_video_model),
            "fixed_note": "เซิร์ฟเวอร์ BytePlus ECS + Postgres + Redis = ค่าคงที่รายเดือน (ดูที่บิล BytePlus)",
            "note": "ประมาณการ = การใช้งานจริงเดือนนี้ (จาก DB) × ราคาต่อหน่วยโดยประมาณ · ไม่ใช่บิลจริง · ยอดเครดิตคงเหลือจริง ดูที่ console ของแต่ละผู้ให้บริการ"}


@app.get("/api/activity")
async def activity_feed(limit: int = 40, project_id: int = 0, user=Depends(get_current_user)):
    """กิจกรรมสดของบัญชี — ไทม์ไลน์ล่าสุด (บทความ/เผยแพร่/วัดอันดับ/AI citation)
    อ่านอย่างเดียว · เห็นเฉพาะโปรเจ็คที่ตัวเองเข้าถึงได้ (เจ้าของ+ทีม) · ไม่มีข้อมูลลับ
    project_id > 0 = กรองเฉพาะโปรเจ็คนั้น (แดชบอร์ดต่อโปรเจ็ค)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from sqlalchemy import func
    from app import team
    from app.db.models import Project, Article, DistributionEvent, RankSnapshot, CitationSnapshot
    limit = max(5, min(int(limit), 100))
    owners = await team.accessible_owner_ids(user["id"])
    async with db.session() as s:
        prows = (await s.execute(select(Project.id, Project.name).where(Project.user_id.in_(owners)))).all()
        pname = {pid: name for pid, name in prows}
        pids = list(pname.keys())
        if project_id and project_id in pname:      # กรองต่อโปรเจ็ค
            pids = [project_id]
            pname = {project_id: pname[project_id]}
        if not pids:
            return {"events": [], "summary": {"projects": 0, "articles": 0, "published": 0}}
        arts = (await s.execute(select(Article).where(Article.project_id.in_(pids))
                                .order_by(Article.id.desc()).limit(limit))).scalars().all()
        dist = (await s.execute(select(DistributionEvent).where(DistributionEvent.project_id.in_(pids))
                                .order_by(DistributionEvent.id.desc()).limit(limit))).scalars().all()
        ranks = (await s.execute(select(RankSnapshot).where(RankSnapshot.project_id.in_(pids))
                                 .order_by(RankSnapshot.id.desc()).limit(limit))).scalars().all()
        cits = (await s.execute(select(CitationSnapshot).where(CitationSnapshot.project_id.in_(pids))
                                .order_by(CitationSnapshot.id.desc()).limit(limit))).scalars().all()
        total_art = (await s.execute(select(func.count(Article.id)).where(Article.project_id.in_(pids)))).scalar() or 0
        published = (await s.execute(select(func.count(Article.id)).where(
            Article.project_id.in_(pids), Article.status == "published"))).scalar() or 0

    def _iso(dt):
        return dt.isoformat() if dt else ""

    ev = []
    for a in arts:
        ev.append({"type": "article", "at": _iso(getattr(a, "created_at", None) or a.updated_at),
                   "project": pname.get(a.project_id, ""), "title": a.title,
                   "status": a.status, "score": a.aeo_score, "url": a.url})
    for d in dist:
        ev.append({"type": "distribute", "at": _iso(d.created_at), "project": pname.get(d.project_id, ""),
                   "channel": d.channel, "status": d.status, "detail": (d.detail or "")[:120], "url": d.url})
    for r in ranks:
        ev.append({"type": "rank", "at": _iso(r.checked_at), "project": pname.get(r.project_id, ""),
                   "keyword": r.keyword, "rank": r.rank, "on_page1": bool(r.on_page1)})
    for c in cits:
        ev.append({"type": "citation", "at": _iso(c.sampled_at), "project": pname.get(c.project_id, ""),
                   "engine": c.engine, "sov": c.sov_percent})
    ev = [e for e in ev if e["at"]]
    ev.sort(key=lambda e: e["at"], reverse=True)
    return {"events": ev[:limit],
            "summary": {"projects": len(pids), "articles": int(total_art), "published": int(published)}}


@app.get("/api/plans")
async def list_plans():
    """แพ็กเกจ + ราคา + โควตา (เปิดสาธารณะ — ใช้แสดงหน้าราคา/อัปเกรด)"""
    from app import plans
    return {"plans": plans.public_list()}


@app.get("/api/usage")
async def get_usage(user=Depends(get_current_user)):
    """การใช้งานจริงเทียบโควตาแพ็กเกจของผู้ใช้ (โปรเจ็ค + บทความเดือนนี้)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import usage
    return await usage.summary(user["id"])


# ---------- Billing (Stripe subscription) ----------
async def _apply_subscription(user_id: int, plan: str, status: str,
                              customer_id: str = "", subscription_id: str = ""):
    """อัปเดต Subscription + sync User.plan (แหล่งความจริงของโควตา)"""
    from app.db.models import User, Subscription
    from app import plans as plan_mod
    plan = plan_mod.normalize(plan)
    async with db.session() as s:
        u = await s.get(User, user_id)
        if u:
            u.plan = plan if status == "active" else "free"
        sub = (await s.execute(select(Subscription).where(Subscription.user_id == user_id))).scalars().first()
        if not sub:
            sub = Subscription(user_id=user_id)
            s.add(sub)
        sub.plan = plan
        sub.status = status
        if customer_id:
            sub.stripe_customer_id = customer_id
        if subscription_id:
            sub.stripe_subscription_id = subscription_id
        await s.commit()


@app.post("/api/billing/checkout")
async def billing_checkout(req: CheckoutRequest, user=Depends(get_current_user)):
    """สร้างลิงก์จ่ายเงิน Stripe Checkout สำหรับอัปเกรดแพ็กเกจ"""
    if req.plan not in ("pro", "business"):
        raise HTTPException(422, "แพ็กเกจต้องเป็น pro | business")
    if not billing.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่าระบบชำระเงิน (STRIPE_SECRET_KEY)")
    base = settings.app_base_url.rstrip("/")
    try:
        sess = await billing.create_checkout_session(
            user["id"], user.get("email", ""), req.plan,
            success_url=base + "/#/settings?billing=success",
            cancel_url=base + "/#/settings?billing=cancel")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
    return sess


@app.get("/api/billing/status")
async def billing_status(user=Depends(get_current_user)):
    """สถานะการสมัครสมาชิกปัจจุบัน (จาก DB)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Subscription
    from app import usage
    async with db.session() as s:
        sub = (await s.execute(select(Subscription).where(Subscription.user_id == user["id"]))).scalars().first()
    return {
        "plan": (await usage.user_plan(user["id"])),
        "status": sub.status if sub else "inactive",
        "current_period_end": sub.current_period_end.isoformat() if (sub and sub.current_period_end) else None,
        "stripe_enabled": billing.enabled(),
    }


@app.post("/api/billing/webhook")
async def billing_webhook(request: Request):
    """รับ event จาก Stripe — ตรวจลายเซ็นจริงก่อน แล้ว sync แพ็กเกจ (upgrade/downgrade)"""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = billing.verify_webhook(payload, sig)
    except Exception:  # noqa: BLE001 — ลายเซ็นไม่ผ่าน = ปฏิเสธ (กัน event ปลอม)
        raise HTTPException(400, "invalid signature")
    typ = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    meta = obj.get("metadata") or {}
    uid = meta.get("user_id") or obj.get("client_reference_id")
    try:
        uid = int(uid) if uid is not None else None
    except (TypeError, ValueError):
        uid = None
    if uid and db.enabled():
        if typ == "checkout.session.completed":
            await _apply_subscription(uid, meta.get("plan") or "pro", "active",
                                      obj.get("customer") or "", obj.get("subscription") or "")
        elif typ in ("customer.subscription.deleted",):
            await _apply_subscription(uid, "free", "canceled")
        elif typ == "customer.subscription.updated":
            status = obj.get("status") or "active"
            await _apply_subscription(uid, meta.get("plan") or "pro",
                                      "active" if status in ("active", "trialing") else status)
    return {"received": True}


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
    """ลูกค้าตั้งได้ managed | wordpress | none (wordpress ใช้บัญชี WordPress ของลูกค้าเองที่ผูกไว้)"""
    return mode if mode in ("managed", "wordpress", "none") else "managed"


@app.get("/api/projects")
async def list_projects(user=Depends(get_current_user)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    from app import team
    owners = await team.accessible_owner_ids(user["id"])   # ตัวเอง + บัญชีที่แชร์ให้เรา
    async with db.session() as s:
        rows = (await s.execute(select(Project).where(Project.user_id.in_(owners)).order_by(Project.id))).scalars().all()
    out = []
    for p in rows:
        d = _proj_dict(p)
        d["shared"] = (p.user_id != user["id"])           # โปรเจ็คที่คนอื่นแชร์ให้เรา (ดูอย่างเดียว)
        out.append(d)
    return {"projects": out}


@app.post("/api/projects")
async def create_project(req: ProjectCreate, user=Depends(get_current_user)):
    """ลูกค้าใส่แค่ลิงก์เว็บ (url) หรือ domain → ระบบแตกเป็น name/domain/slug + ตั้งปลายทางเผยแพร่ให้เอง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from urllib.parse import urlparse
    from app.db.models import Project
    from app import usage, plans
    if not await usage.can_create_project(user["id"]):
        lim = plans.limits(await usage.user_plan(user["id"]))
        raise HTTPException(402, "ถึงขีดจำกัดจำนวนโปรเจ็คของแพ็กเกจ %s (%d โปรเจ็ค) — อัปเกรดเพื่อเพิ่ม"
                            % (lim["label"], lim["projects"]))
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
        # คีย์เวิร์ดที่ลูกค้าเลือก (AI ช่วยคิด) → บันทึกเป็นแผนหัวข้อตั้งต้น เพื่อให้ระบบผลิตบทความจากคีย์เหล่านี้จริง
        seeds = [str(k).strip() for k in (req.keywords or []) if str(k).strip()][:20]
        if seeds:
            import json as _json
            p.topic_plan = _json.dumps([{"topic": k, "cluster": ""} for k in seeds], ensure_ascii=False)
            await s.commit()
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


@app.post("/api/keywords/suggest")
async def keywords_suggest(req: KeywordSuggestRequest, user=Depends(get_current_user)):
    """🤖 AI ช่วยคิดคีย์เวิร์ดตอนสร้างโปรเจ็ค — ลูกค้าวางลิงก์ก็พอ ไม่ต้องคิดคีย์เวิร์ดเอง"""
    from urllib.parse import urlparse
    from app.connectors import content
    domain = (req.domain or "").strip().lower()
    if not domain and req.url:
        u = req.url.strip()
        if "://" not in u:
            u = "https://" + u
        domain = (urlparse(u).hostname or "").removeprefix("www.")
    if not domain:
        raise HTTPException(422, "กรุณาระบุลิงก์/โดเมนเว็บไซต์ก่อน")
    lang = "English" if str(req.language).lower().startswith("en") else "ภาษาไทย"
    source = "ai"
    try:
        kws = await content.suggest_keywords(domain, req.name or "", lang, 12)
    except Exception:  # noqa: BLE001
        kws = []
    if not kws:                                   # AI ล่ม/คีย์ไม่พร้อม → หัวข้อตั้งต้นจากแบรนด์ (ยังใช้งานได้)
        from app.worker.tasks import _starter_topics
        kws = [{"kw": t, "intent": "", "why": ""} for t in _starter_topics(req.name or domain, lang)]
        source = "starter"
    return {"domain": domain, "keywords": kws, "source": source}


@app.put("/api/projects/{project_id}/publish")
async def set_publish_target(project_id: int, req: PublishTargetUpdate, user=Depends(get_current_user)):
    """ตั้งปลายทางเผยแพร่ของโปรเจ็ค: managed (เราโฮสต์ให้) / wordpress / none + custom domain"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    if req.publish_mode not in ("managed", "wordpress", "none"):
        raise HTTPException(422, "publish_mode ต้องเป็น managed | wordpress | none")
    if req.publish_mode == "wordpress":                # ต้องผูกบัญชี WordPress ของลูกค้าก่อน (หรือมีคีย์กลาง)
        from app import creds
        st = (await creds.status(project_id)).get("wordpress", {})
        if not st.get("connected"):
            raise HTTPException(422, "ต้องเชื่อมบัญชี WordPress ของคุณก่อน (หน้าตั้งค่า › การเชื่อมต่อ)")
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
    from app import usage, plans
    async with db.session() as s:
        p = await s.get(Project, project_id)
    if not p or p.user_id != user["id"]:
        raise HTTPException(404, "ไม่พบโปรเจ็ค")
    if not await usage.can_produce_article(user["id"]):
        lim = plans.limits(await usage.user_plan(user["id"]))
        raise HTTPException(402, "ถึงโควตาบทความเดือนนี้ของแพ็กเกจ %s (%d บทความ/เดือน) — อัปเกรดเพื่อผลิตเพิ่ม"
                            % (lim["label"], lim["articles_month"]))
    try:
        from app.worker.tasks import produce_for_project
        task = produce_for_project.delay(project_id, 1)
        return {"queued": True, "task_id": str(task.id), "project": p.name, "mode": p.mode}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ต่อคิวงานไม่ได้ (backend/worker/redis พร้อมไหม): " + str(e))


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, user=Depends(get_current_user)):
    """ลบโปรเจ็คถาวร + ข้อมูลลูกทั้งหมด (บทความ/อันดับ/citation/ช่องทาง/คีย์/ล็อก) — เจ้าของเท่านั้น"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from sqlalchemy import delete as sa_delete
    from app.db.models import (Project, Article, RankSnapshot, CitationSnapshot,
                               DistributionChannel, ProjectCredential, DistributionEvent)
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        name = p.name
        # ลบลูกก่อน (DistributionEvent อ้าง article_id → ต้องลบก่อน Article)
        for model in (DistributionEvent, RankSnapshot, CitationSnapshot,
                      DistributionChannel, ProjectCredential, Article):
            await s.execute(sa_delete(model).where(model.project_id == project_id))
        await s.delete(p)
        await s.commit()
    return {"deleted": True, "project": name}


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


async def _read_project(s, project_id, user):
    """เข้าถึงแบบ 'อ่าน' — เจ้าของ หรือ สมาชิกทีม (viewer/editor/admin) ของเจ้าของ"""
    from app.db.models import Project
    from app import team
    p = await s.get(Project, project_id)
    if not p:
        raise HTTPException(404, "ไม่พบโปรเจ็ค")
    if p.user_id == user["id"]:
        return p
    if p.user_id in await team.accessible_owner_ids(user["id"]):
        return p
    raise HTTPException(404, "ไม่พบโปรเจ็ค")


# ---------- Team / multi-seat (Agency เชิญลูกค้า/ทีมเข้าดูรายงาน) ----------
@app.get("/api/team")
async def list_team(user=Depends(get_current_user)):
    """สมาชิกทีมของฉัน (ที่ฉันเชิญ) + บัญชีที่ฉันถูกเชิญให้เข้าถึง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import TeamMember, User
    async with db.session() as s:
        mine = (await s.execute(select(TeamMember).where(TeamMember.owner_id == user["id"]))).scalars().all()
        shared = (await s.execute(select(TeamMember).where(
            TeamMember.member_user_id == user["id"], TeamMember.status == "active"))).scalars().all()
        owners = {}
        for r in shared:
            o = await s.get(User, r.owner_id)
            owners[r.owner_id] = (o.name or o.email) if o else str(r.owner_id)
    return {
        "members": [{"id": m.id, "email": m.email, "role": m.role, "status": m.status} for m in mine],
        "shared_with_me": [{"owner": owners.get(r.owner_id, ""), "role": r.role} for r in shared],
    }


@app.post("/api/team/invite")
async def invite_team(req: TeamInvite, user=Depends(get_current_user)):
    """เชิญสมาชิกด้วยอีเมล — ถ้าอีเมลนั้นมีบัญชีอยู่แล้ว ผูก+active ทันที ไม่งั้นค้างเป็น invited"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    email = (req.email or "").strip().lower()
    role = req.role if req.role in ("viewer", "editor", "admin") else "viewer"
    if not email or "@" not in email:
        raise HTTPException(422, "อีเมลไม่ถูกต้อง")
    from app.db.models import TeamMember, User
    async with db.session() as s:
        me = await s.get(User, user["id"])
        if me and email == (me.email or "").lower():
            raise HTTPException(422, "เชิญตัวเองไม่ได้")
        dup = (await s.execute(select(TeamMember).where(
            TeamMember.owner_id == user["id"], TeamMember.email == email))).scalars().first()
        if dup:
            raise HTTPException(409, "เชิญอีเมลนี้ไปแล้ว")
        existing = (await s.execute(select(User).where(User.email == email))).scalars().first()
        m = TeamMember(owner_id=user["id"], email=email, role=role,
                       status="active" if existing else "invited",
                       member_user_id=existing.id if existing else None)
        s.add(m)
        await s.commit()
        await s.refresh(m)
    return {"id": m.id, "email": m.email, "role": m.role, "status": m.status}


@app.delete("/api/team/{member_id}")
async def remove_team(member_id: int, user=Depends(get_current_user)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import TeamMember
    async with db.session() as s:
        m = await s.get(TeamMember, member_id)
        if not m or m.owner_id != user["id"]:
            raise HTTPException(404, "ไม่พบสมาชิก")
        await s.delete(m)
        await s.commit()
    return {"ok": True}


# ---------- Per-tenant credentials (ลูกค้าเชื่อมคีย์ตัวเอง — multi-tenant จริง) ----------
@app.get("/api/projects/{project_id}/credentials")
async def get_credentials(project_id: int, user=Depends(get_current_user)):
    """สถานะการเชื่อมต่อของโปรเจ็ค (โปร่งใส): แต่ละบริการเชื่อมด้วยคีย์ลูกค้า/คีย์กลาง/ยังไม่เชื่อม
    ไม่คืนค่าลับใด ๆ กลับไป (คืนเฉพาะ connected + source)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import creds
    async with db.session() as s:
        await _own_project(s, project_id, user)
    return {"status": await creds.status(project_id),
            "fields": {k: v for k, v in creds.FIELDS.items()}}


@app.put("/api/projects/{project_id}/credentials")
async def set_credentials(project_id: int, req: CredentialUpdate, user=Depends(get_current_user)):
    """บันทึกคีย์ 'ของลูกค้า' ต่อโปรเจ็ค (เข้ารหัสก่อนเก็บ) — connector จะใช้คีย์นี้ก่อนคีย์กลาง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import creds
    if not creds.valid_kind(req.kind):
        raise HTTPException(422, "บริการไม่ถูกต้อง (dataforseo | wordpress | gsc)")
    async with db.session() as s:
        await _own_project(s, project_id, user)
    await creds.set_creds(project_id, req.kind, req.fields or {})
    return {"ok": True, "status": await creds.status(project_id)}


@app.post("/api/projects/{project_id}/rank/check")
async def project_rank_check(project_id: int, req: KeywordRequest, user=Depends(get_current_user)):
    """M5 · ตรวจอันดับสดด้วย 'โดเมนของโปรเจ็คเอง' + คีย์ DataForSEO ของลูกค้า แล้วบันทึกผล
    (ใช้ proj.domain เสมอ กันตรวจโดเมนคนอื่น) — feed เข้าประวัติอันดับด้วย"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import creds
    async with db.session() as s:
        proj = await _own_project(s, project_id, user)
        domain = proj.domain
    if not domain:
        raise HTTPException(422, "โปรเจ็คนี้ยังไม่ได้ตั้งโดเมน")
    dfs = await creds.get_creds(project_id, "dataforseo")
    try:
        res = await serp.rank_check(req.keyword, domain, creds=dfs or None)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
    try:
        from app.db.models import RankSnapshot
        async with db.session() as s:
            s.add(RankSnapshot(project_id=project_id, keyword=res.get("keyword", req.keyword),
                               rank=res.get("our_rank"), on_page1=bool(res.get("on_page1"))))
            await s.commit()
    except Exception:  # noqa: BLE001
        pass
    return res


@app.post("/api/projects/{project_id}/gsc/summary")
async def project_gsc_summary(project_id: int, req: GSCDaysRequest, user=Depends(get_current_user)):
    """M5 · ดึง Search Console ด้วยบัญชี GSC 'ของลูกค้า' + โดเมนของโปรเจ็คเอง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import creds
    async with db.session() as s:
        proj = await _own_project(s, project_id, user)
        domain = proj.domain
    if not domain:
        raise HTTPException(422, "โปรเจ็คนี้ยังไม่ได้ตั้งโดเมน")
    g = await creds.get_creds(project_id, "gsc")
    try:
        return await gsc.summary("sc-domain:" + domain, req.days, creds=g or None)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


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
        await _read_project(s, project_id, user)
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


@app.get("/api/projects/{project_id}/drafts")
async def project_drafts(project_id: int, user=Depends(get_current_user)):
    """M4 · บทความที่รออนุมัติ (โหมด approve ผลิตเป็น draft) — ให้ลูกค้ากดอนุมัติได้จริง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Article
    async with db.session() as s:
        await _read_project(s, project_id, user)
        rows = (await s.execute(
            select(Article).where(Article.project_id == project_id, Article.status == "draft")
            .order_by(Article.id.desc()))).scalars().all()
    return {"drafts": [{"id": a.id, "title": a.title, "words": a.words,
                        "aeo_score": a.aeo_score, "cluster": a.cluster,
                        "description": (a.description or "")[:160]} for a in rows]}


@app.put("/api/articles/{article_id}/schedule")
async def article_schedule(article_id: int, req: ScheduleRequest, user=Depends(get_current_user)):
    """M4 · ตั้งเวลาเผยแพร่บทความ draft — beat จะเผยแพร่ให้เองเมื่อถึงเวลา"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from datetime import datetime, timedelta, timezone as _tz
    from app.db.models import Article, Project
    try:
        dt = datetime.fromisoformat((req.at or "").replace("Z", "+00:00"))
    except Exception:
        raise HTTPException(422, "รูปแบบเวลาไม่ถูกต้อง (ต้องเป็น ISO เช่น 2026-08-01T09:00)")
    if dt.tzinfo is None:                              # datetime-local ไม่มี tz → ถือเป็นเวลาไทย (+07:00)
        dt = dt.replace(tzinfo=_tz(timedelta(hours=7)))
    async with db.session() as s:
        art = await s.get(Article, article_id)
        if not art:
            raise HTTPException(404, "ไม่พบบทความ")
        proj = await s.get(Project, art.project_id)
        if not proj or proj.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบบทความ")
        if art.status == "published":
            raise HTTPException(409, "บทความนี้เผยแพร่ไปแล้ว")
        art.status = "scheduled"
        art.scheduled_at = dt
        await s.commit()
    return {"ok": True, "article_id": article_id, "scheduled_at": dt.isoformat()}


@app.post("/api/articles/{article_id}/approve")
async def article_approve(article_id: int, user=Depends(get_current_user)):
    """M4 · อนุมัติ draft → เผยแพร่จริง (managed/wordpress) + แจ้ง index + กระจาย (เข้าคิว)"""
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
        if art.status == "published":
            raise HTTPException(409, "บทความนี้เผยแพร่ไปแล้ว")
        title = art.title
    try:
        from app.worker.tasks import approve_article
        task = approve_article.delay(article_id)
        return {"queued": True, "task_id": str(task.id), "article": title}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ต่อคิวไม่ได้ (worker/redis พร้อมไหม): " + str(e))


@app.post("/api/projects/{project_id}/audit/performance")
async def project_perf_audit(project_id: int, user=Depends(get_current_user)):
    """M3 · วัดความเร็ว/Core Web Vitals จริงของหน้าเว็บโปรเจ็ค (PageSpeed Insights)
    วัดเฉพาะหน้าสาธารณะของโปรเจ็คเอง (ไม่รับ URL จากผู้ใช้ = กันใช้ยิงเว็บคนอื่น)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    async with db.session() as s:
        proj = await _own_project(s, project_id, user)
        url = project_public_home(proj)
    if not url:
        raise HTTPException(422, "โปรเจ็คนี้ยังไม่มีหน้าเว็บให้ตรวจ")
    try:
        return await pagespeed.audit(url, "mobile")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ตรวจความเร็วไม่สำเร็จ: " + str(e)[:160])


@app.get("/api/projects/{project_id}/seo-audit")
async def project_seo_audit(project_id: int, user=Depends(get_current_user)):
    """M3 · ตรวจสุขภาพ SEO/AEO 'จากข้อมูลจริงใน DB' (ไม่ต้อง crawl):
    ความครอบคลุม schema, จำนวน URL ใน sitemap, ลิงก์ภายในรวม, หน้ากำพร้า, และหน้าที่เก่าเกินเกณฑ์"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import re as _re
    from datetime import datetime, timezone
    from app.db.models import Article
    from app.connectors.aeo_score import _valid_schema
    _HREF = _re.compile(r"""href\s*=\s*("|')(.*?)\1""", _re.I)
    async with db.session() as s:
        proj = await _read_project(s, project_id, user)
        arts = (await s.execute(
            select(Article).where(Article.project_id == project_id,
                                  Article.status == "published"))).scalars().all()
    n = len(arts)
    fd = getattr(proj, "freshness_days", 120) or 120
    with_schema = sum(1 for a in arts if _valid_schema(a.schema_json or "")[0])
    # ลิงก์ภายใน + หน้ากำพร้า: จับ href แล้วเทียบกับ url/slug ของบทความพี่น้อง
    idx = [(a, a.url or "", ("/" + (a.slug or "")) if a.slug else "") for a in arts]
    inbound = {a.id: 0 for a in arts}
    total_internal = 0
    for src in arts:
        targets = [m.group(2).strip() for m in _HREF.finditer(src.html or "")]
        for t in targets:
            if not t or t == "#":
                continue
            for a, u, sl in idx:
                if a.id == src.id:
                    continue
                if (u and u in t) or (sl and len(sl) > 1 and sl in t):
                    inbound[a.id] += 1
                    total_internal += 1
                    break
    orphans = [a for a in arts if inbound[a.id] == 0]
    now = datetime.now(timezone.utc)
    stale = []
    for a in arts:
        if getattr(a, "updated_at", None):
            try:
                age = (now - a.updated_at).days
            except Exception:  # noqa: BLE001
                continue
            if age > fd:
                stale.append({"id": a.id, "title": a.title, "age_days": age, "url": a.url})
    stale.sort(key=lambda x: x["age_days"], reverse=True)
    return {
        "articles": n,
        "schema_coverage": round(with_schema / n * 100) if n else 0,
        "schema_pages": with_schema,
        "sitemap_urls": n + 1,                      # + หน้าแรก
        "internal_links_total": total_internal,
        "internal_links_avg": round(total_internal / n, 1) if n else 0,
        "orphan_pages": len(orphans),
        "orphan_titles": [a.title for a in orphans][:10],
        "stale_count": len(stale),
        "freshness": stale[:20],
        "freshness_days": fd,
        "note": "คำนวณจากบทความจริงในฐานข้อมูลของโปรเจ็คนี้ (ไม่ใช่ค่าประเมิน)",
    }


# ---------- GSC in-app OAuth (ลูกค้ากดเชื่อม Google เอง แทนแปะ refresh_token) ----------
@app.get("/api/projects/{project_id}/gsc/connect")
async def gsc_connect_start(project_id: int, user=Depends(get_current_user)):
    """คืนลิงก์ให้ลูกค้าไปยินยอมที่ Google — state มีลายเซ็นผูก user+project (กัน CSRF)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    if not gsc.oauth_configured():
        raise HTTPException(503, "ผู้ดูแลยังไม่ได้ตั้งค่า Google OAuth (client_id/secret/redirect_uri)")
    async with db.session() as s:
        await _own_project(s, project_id, user)
    state = security.create_state({"t": "gsc", "uid": user["id"], "pid": project_id})
    return {"url": gsc.consent_url(state)}


@app.get("/api/oauth/google/callback")
async def gsc_oauth_callback(code: str = "", state: str = ""):
    """Google redirect กลับมาที่นี่ — ตรวจ state, แลก code → refresh_token, เก็บเป็นคีย์ GSC ของโปรเจ็ค"""
    from fastapi.responses import RedirectResponse
    from app import creds
    base = settings.app_base_url.rstrip("/")
    try:
        st = security.read_state(state)
        assert st.get("t") == "gsc" and st.get("uid") and st.get("pid")
    except Exception:
        return RedirectResponse(base + "/#/settings?gsc=badstate")
    if not code:
        return RedirectResponse(base + "/#/settings?gsc=denied")
    uid, pid = int(st["uid"]), int(st["pid"])
    async with db.session() as s:                       # ยืนยันว่า project ยังเป็นของ user นี้
        from app.db.models import Project
        p = await s.get(Project, pid)
        if not p or p.user_id != uid:
            return RedirectResponse(base + "/#/settings?gsc=forbidden")
    try:
        refresh = await gsc.exchange_code(code)
    except Exception:
        return RedirectResponse(base + "/#/settings?gsc=exchangefail")
    if not refresh:
        return RedirectResponse(base + "/#/settings?gsc=notoken")
    await creds.set_creds(pid, "gsc", {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "refresh_token": refresh})
    return RedirectResponse(base + "/#/settings?gsc=connected")


@app.post("/api/projects/{project_id}/sitemap/submit")
async def project_submit_sitemap(project_id: int, user=Depends(get_current_user)):
    """M3 · ส่ง sitemap ของโปรเจ็คเข้า Google Search Console (ใช้บัญชี GSC ของลูกค้า)
    ใช้ได้เมื่อโดเมนถูก verify ใน GSC ของลูกค้า (โดเมนตัวเอง/custom domain)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import creds
    async with db.session() as s:
        proj = await _own_project(s, project_id, user)
        domain, home = proj.domain, project_public_home(proj)
    if not domain:
        raise HTTPException(422, "โปรเจ็คนี้ยังไม่ได้ตั้งโดเมน")
    g = await creds.get_creds(project_id, "gsc")
    sitemap_url = home.rstrip("/") + "/sitemap.xml"
    try:
        return await gsc.submit_sitemap("sc-domain:" + domain, sitemap_url, creds=g or None)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/articles/{article_id}/optimize")
async def article_optimize(article_id: int, user=Depends(get_current_user)):
    """M3 · ป้อนจุดอ่อน AEO Score กลับให้เครื่องยนต์เขียนซ่อม → ดันคะแนน (เข้าคิวเบื้องหลัง)"""
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
        title = art.title
    try:
        from app.worker.tasks import optimize_article
        task = optimize_article.delay(article_id)
        return {"queued": True, "task_id": str(task.id), "article": title}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ต่อคิวไม่ได้ (worker/redis พร้อมไหม): " + str(e))


@app.get("/api/projects/{project_id}/aeo")
async def project_aeo(project_id: int, user=Depends(get_current_user)):
    """M3 · ภาพรวมคะแนน AEO/SEO ทั้งโปรเจ็ค — คะแนนเฉลี่ย, การกระจายเกรด, คะแนนต่อบทความ,
    และ 'แก้ตรงไหนได้คะแนนรวมมากสุด' (จัดลำดับงานปรับให้ติดเร็ว)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Article, Project
    async with db.session() as s:
        proj = await _read_project(s, project_id, user)
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


@app.get("/api/projects/{project_id}/insights")
async def project_insights(project_id: int, user=Depends(get_current_user)):
    """M6 · Learning Loop — เรียนรู้จากผลจริง (คะแนน AEO + อันดับ) ว่าอะไรทำให้ติด/ถูกอ้าง
    คืน insights + คลัสเตอร์ที่แข็งสุด (ไม่มีข้อมูล = ว่างจริง ไม่เดา)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    async with db.session() as s:
        proj = await _read_project(s, project_id, user)
    from app.worker.tasks import _project_insights
    return await _project_insights(project_id, proj)


@app.get("/api/projects/{project_id}/citation/history")
async def project_citation_history(project_id: int, user=Depends(get_current_user)):
    """แนวโน้ม Share of Voice ที่ 'สะสมจากการรันจริง' — จัดกลุ่มเป็นรอบ (ต่อครั้งที่รัน)
    คืนซีรีส์ overall + ต่อเอนจิน เพื่อวาดกราฟแนวโน้มบัญชีจริง (ไม่มีข้อมูล = ว่างจริง)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import CitationSnapshot
    async with db.session() as s:
        await _read_project(s, project_id, user)
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
