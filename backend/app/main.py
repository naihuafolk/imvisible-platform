"""
RankPilot AI — Backend API (FastAPI)
รัน: uvicorn app.main:app --reload   (จากโฟลเดอร์ backend/)
เอกสาร API อัตโนมัติ: http://localhost:8000/docs
"""
import secrets
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Depends, Request, Form
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
    RegisterRequest, LoginRequest, ProjectCreate, PublishTargetUpdate, ProjectModeUpdate, ProjectUpdate, ProjectActiveUpdate, KeywordReportRequest, ChannelUpdate, DraftRequest,
    BacklinkOutreachRequest, PantipRadarRequest, PantipReplyRequest, SocialRadarRequest, BacklinkGapsRequest, ContentGapRequest, SnippetSniperRequest, ImwebGenerateRequest, ImwebSaveRequest, ImwebPrefillRequest, PseoTopicsRequest, LeadMagnetCreate, LeadUnlock, ContactForm, SiteCheckRequest, SiteReportCreate, ReportLeadCreate, KeywordPackUpdate, SmsAlertUpdate, FacebookConvert,
    CredentialUpdate, KeywordRequest, GSCDaysRequest, CheckoutRequest, ScheduleRequest, TeamInvite, AdminCreateUser, OutreachUpdate,
    KeywordSuggestRequest, KeywordsAddRequest, AeoQuestionsUpdate, AdCreativeRequest, PostCreate, CtaUpdate,
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
    resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    if is_prod():
        resp.headers.setdefault("Strict-Transport-Security",
                                "max-age=63072000; includeSubDomains")
    return resp


# ---------- Rate limit (กัน brute-force ที่ auth) — in-memory ต่อ process ----------
_rl_hits: dict = defaultdict(deque)


async def rate_limit_auth(request: Request):
    ip = (request.client.host if request.client else "") or "unknown"
    now = time.time()
    if len(_rl_hits) > 10000:          # กันคีย์ล้น (IP หมุนเวียน) → OOM · ล้างเมื่อโตเกิน
        _rl_hits.clear()
    dq = _rl_hits[ip]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= settings.rate_limit_per_min:
        raise HTTPException(429, "คำขอถี่เกินไป กรุณาลองใหม่ในอีกสักครู่")
    dq.append(now)


# ---------- Login lockout (กัน brute-force / credential stuffing 'ต่อบัญชี') ----------
_login_fails: dict = defaultdict(deque)
_LOGIN_LOCK_WINDOW = 900      # 15 นาที
_LOGIN_LOCK_MAX = 6           # ล้มเหลวเกินนี้ในหน้าต่างเวลา = ล็อกชั่วคราว


def _login_locked(email: str) -> bool:
    dq = _login_fails.get(email)          # ใช้ .get กันสร้างคีย์เปล่าตอนเช็ก
    if not dq:
        return False
    now = time.time()
    while dq and now - dq[0] > _LOGIN_LOCK_WINDOW:
        dq.popleft()
    if not dq:                            # หมดอายุ → ลบคีย์ทิ้ง (กัน memory leak)
        _login_fails.pop(email, None)
        return False
    return len(dq) >= _LOGIN_LOCK_MAX


def _login_record_fail(email: str):
    if len(_login_fails) > 10000:         # กันคีย์ล้น (อีเมลสุ่ม) → OOM
        _login_fails.clear()
    _login_fails[email].append(time.time())


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


# โลโก้แบรนด์ (globe) — เสิร์ฟให้หน้าบล็อกลูกค้าใช้เป็น favicon แทน default/WordPress
_BRAND_SVG = (
    '<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ImVisible">'
    '<defs><linearGradient id="ivg" x1="6" y1="4" x2="58" y2="60" gradientUnits="userSpaceOnUse">'
    '<stop offset="0" stop-color="#3d6bff"/><stop offset="1" stop-color="#5b4ff0"/></linearGradient></defs>'
    '<rect width="64" height="64" rx="15" fill="url(#ivg)"/>'
    '<g fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="31" cy="34" r="15"/><ellipse cx="31" cy="34" rx="6.4" ry="15"/>'
    '<line x1="16" y1="34" x2="46" y2="34"/>'
    '<path d="M19.6 24.6 q11.4 5 22.8 0" stroke-width="2.2"/>'
    '<path d="M19.6 43.4 q11.4 -5 22.8 0" stroke-width="2.2"/></g>'
    '<circle cx="49" cy="16" r="6.2" fill="url(#ivg)"/><circle cx="49" cy="16" r="6.2" fill="#fff" opacity=".18"/>'
    '<circle cx="49" cy="16" r="5.4" fill="none" stroke="#fff" stroke-width="2.4"/>'
    '<circle cx="49" cy="16" r="2.5" fill="#3ce0ff"/></svg>'
)


@app.get("/favicon.svg")
async def favicon_svg():
    from fastapi import Response
    return Response(content=_BRAND_SVG, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"})


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
    email = (req.email or "").strip().lower()
    if _login_locked(email):                       # ล็อกชั่วคราวหลังผิดหลายครั้ง (กันยิงรหัส)
        raise HTTPException(429, "เข้าสู่ระบบผิดหลายครั้งเกินไป — กรุณารอสักครู่ (~15 นาที) แล้วลองใหม่")
    from app.db.models import User
    async with db.session() as s:
        u = (await s.execute(select(User).where(User.email == req.email))).scalar_one_or_none()
    if not u or not security.verify_password(req.password, u.password_hash):
        _login_record_fail(email)
        raise HTTPException(401, "อีเมลหรือรหัสผ่านไม่ถูกต้อง")
    _login_fails.pop(email, None)                  # สำเร็จ → ล้างตัวนับล้มเหลว
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

    from app import plans
    out = []
    for p in projs:
        c, pub, last = stat.get(p.id, (0, 0, None))
        skey, slabel, stone = _status(int(c), last)
        out.append({"id": p.id, "name": p.name, "domain": p.domain,
                    "public_home": project_public_home(p), "mode": p.mode,
                    "articles": int(c), "published": int(pub),
                    "avg_aeo": aeoavg.get(p.id), "page1": page1.get(p.id, 0),
                    "keyword_pack": plans.normalize_pack(getattr(p, "keyword_pack", plans.DEFAULT_PACK)),
                    "keywords_used": _topic_count(p),
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
    # ยอดเครดิต DataForSEO 'จริง' (USD) — เตือนเติมก่อนหมด · crash-safe
    dfs_balance = None
    if settings.dataforseo_login and settings.dataforseo_password:
        from app.connectors import serp
        dfs_balance = await serp.account_balance()
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
         "topup": "app.dataforseo.com › Billing", "active": bool(settings.dataforseo_login and settings.dataforseo_password),
         "balance_usd": dfs_balance},
        {"key": "citation", "name": "วัด AI Citation (ถาม AI จริง)", "provider": "LLM หลายเจ้า",
         "usage": cites, "unit": "ครั้ง", "unit_cost": U["citation"], "est": round(cites * U["citation"]),
         "topup": "เดียวกับ LLM", "active": bool(settings.anthropic_api_key or settings.gemini_api_key or settings.openai_api_key or settings.perplexity_api_key)},
    ]
    # ── ศูนย์เติมเงิน: รายผู้ให้บริการที่ 'เราต้องจ่าย' + ลิงก์เติมตรง + ยอด/สถานะจริง ──
    LOW = 5.0                                            # เกณฑ์เตือน DataForSEO (USD)
    def _prov(active, name, role, url, *, balance=None, source="console",
              auto=False, note=""):
        low = bool(source == "api" and balance is not None and balance < LOW)
        return {"name": name, "role": role, "active": bool(active), "topup_url": url,
                "balance_usd": balance, "balance_source": source,      # api = ดึงสด · console = ดูที่หน้าเจ้านั้น
                "auto_recharge": bool(auto), "low": low, "note": note}
    providers = [
        _prov(settings.dataforseo_login and settings.dataforseo_password,
              "DataForSEO", "วัดอันดับ + ขุดคีย์เวิร์ด", "https://app.dataforseo.com/",
              balance=dfs_balance, source="api", note="ยอดคงเหลือดึงสดจาก API"),
        _prov(settings.anthropic_api_key, "Anthropic (Claude)",
              "เขียนบทความ + วัด AI Citation (หลัก)", "https://console.anthropic.com/settings/billing",
              auto=True, note="ตั้ง Auto-reload ที่ Billing = ไม่มีวันเครดิตหมด"),
        _prov(settings.fal_key, "fal.ai", "สร้างรูปภาพ (Seedream/FLUX)",
              "https://fal.ai/dashboard/billing", auto=True, note="ตั้ง Auto top-up ได้ที่ Billing"),
        _prov(settings.gemini_api_key, "Google Gemini", "LLM สำรอง + วัด AI Citation",
              "https://aistudio.google.com/app/apikey", note="เติมผ่าน Google Cloud Billing"),
        _prov(settings.openai_api_key, "OpenAI", "LLM สำรอง + วัด AI Citation",
              "https://platform.openai.com/settings/organization/billing/overview",
              auto=True, note="ตั้ง Auto-recharge ได้ที่ Billing"),
        _prov(settings.perplexity_api_key, "Perplexity", "วัด AI Citation",
              "https://www.perplexity.ai/settings/api"),
        _prov(settings.ark_api_key, "ModelArk (BytePlus)", "รูป/วิดีโอ สำรอง",
              "https://console.byteplus.com/"),
    ]
    topup_alert = sum(1 for p in providers if p["low"])   # จำนวนเจ้าที่ยอดต่ำ (มี API) → ต้องเติมด่วน
    total = sum(x["est"] for x in lines)
    budget = int(settings.cost_budget_thb or 0)
    alert_level, alert_pct = "off", None
    if budget > 0:
        alert_pct = round(total / budget * 100)
        alert_level = "over" if total >= budget else ("warn" if alert_pct >= 80 else "ok")
    return {"month": mstart.strftime("%Y-%m"), "projects": projects,
            "lines": lines, "total_est": total, "providers": providers, "topup_alert": topup_alert,
            "budget": budget, "alert_level": alert_level, "alert_pct": alert_pct,
            "video_enabled": bool(settings.ark_video_model),
            "fixed_note": "เซิร์ฟเวอร์ BytePlus ECS + Postgres + Redis = ค่าคงที่รายเดือน (ดูที่บิล BytePlus)",
            "note": "ประมาณการ = การใช้งานจริงเดือนนี้ (จาก DB) × ราคาต่อหน่วยโดยประมาณ · ไม่ใช่บิลจริง · ยอดเครดิตคงเหลือจริง ดูที่ console ของแต่ละผู้ให้บริการ"}


@app.post("/api/admin/cost-check")
async def admin_cost_check(user=Depends(get_current_user)):
    """สั่งเช็กค่าใช้จ่าย/เครดิตเดี๋ยวนี้ + เตือน LINE ถ้าถึงเกณฑ์ (แอดมิน) — ไว้ทดสอบเอง"""
    from app import usage
    if (await usage.user_plan(user["id"])) != "admin":
        raise HTTPException(403, "หน้านี้สำหรับแอดมินเท่านั้น")
    from app.worker.tasks import _cost_watch
    return {"result": await _cost_watch()}


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
def _topic_count(p) -> int:
    """จำนวนคีย์เวิร์ด/หัวข้อในแผน (topic_plan) ของโปรเจ็ค — ใช้เทียบโควตาแพ็ก"""
    import json as _json
    raw = getattr(p, "topic_plan", "") or ""
    if not raw.strip():
        return 0
    try:
        return len(_json.loads(raw) or [])
    except Exception:  # noqa: BLE001
        return 0


def _html_plain(html: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", html or "")).strip()


def _split_html_sections(html: str) -> list:
    """แตก HTML ตามหัวข้อ <h2> → [{title, html}] (ใช้แตกคอร์ส/คู่มือเป็นบทความทีละบท)"""
    import re as _re
    out = []
    for part in _re.split(r"(?=<h2\b)", html or "", flags=_re.I):
        mm = _re.search(r"<h2\b[^>]*>(.*?)</h2>", part, flags=_re.I | _re.S)
        if not mm:
            continue
        title = _re.sub(r"<[^>]+>", "", mm.group(1)).strip()
        if not title or len(part.strip()) < 60:      # ข้ามส่วนหัว/บทที่สั้นเกินเป็นบทความ
            continue
        out.append({"title": title[:480], "html": part.strip()})
    return out


def _proj_dict(p):
    from app import plans
    pack = plans.normalize_pack(getattr(p, "keyword_pack", plans.DEFAULT_PACK))
    return {"id": p.id, "name": p.name, "domain": p.domain, "country": p.country,
            "language": p.language, "mode": p.mode, "active": bool(getattr(p, "active", True)),
            "freshness_days": p.freshness_days,
            "slug": p.slug, "publish_mode": p.publish_mode, "custom_domain": p.custom_domain,
            "public_home": project_public_home(p),
            "keyword_pack": pack, "keywords_used": _topic_count(p),   # โควตาแพ็ก + ที่ใช้ไปแล้ว
            # Site Intelligence (สิ่งที่ระบบอ่านได้จากเว็บลูกค้า)
            "analyzed": bool(getattr(p, "analyzed_at", None)),
            "business_context": getattr(p, "business_context", "") or "",
            "brand_terms": getattr(p, "brand_terms", "") or "",
            "lead_line_to": getattr(p, "lead_line_to", "") or "",
            "lead_email": getattr(p, "lead_email", "") or "",
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
async def create_project(req: ProjectCreate, user=Depends(get_current_user), defer_analyze: bool = False):
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
    src = (getattr(req, "source_type", "") or "website").strip().lower()
    fb_url = (getattr(req, "facebook_url", "") or "").strip()
    domain = (req.domain or "").strip().lower()
    if src == "facebook":                            # ลูกค้ามีแค่เพจ Facebook (ไม่มีเว็บ) → เราโฮสต์บล็อกให้ + CTA ลิงก์ไปเพจ
        if not (req.name or "").strip():
            raise HTTPException(422, "กรุณาระบุชื่อธุรกิจ (ลูกค้าที่มีแค่ Facebook)")
        if not fb_url:
            raise HTTPException(422, "กรุณาวางลิงก์เพจ Facebook")
        name = req.name.strip()
        base_slug = project_slug_from_domain(name) or "brand"
        domain = base_slug                           # โดเมนเทียมจากชื่อธุรกิจ (ตัวระบุ) — เนื้อหาเผยแพร่บนบล็อกที่เราโฮสต์
        custom = _clean_custom_domain(req.custom_domain)
        pmode = "managed"                            # บังคับโฮสต์บล็อกให้ (ลูกค้าไม่มีเว็บของตัวเอง)
    else:
        if not domain and req.url:                   # "ลูกค้าใส่แค่ลิงก์"
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
    pack = plans.normalize_pack(getattr(req, "keyword_pack", plans.DEFAULT_PACK))   # แพ็กคีย์ของลูกค้ารายนี้
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
                           publish_mode=pmode, custom_domain=custom, slug=slug, keyword_pack=pack)
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
        # คีย์เวิร์ดที่ลูกค้าเลือก (AI ช่วยคิด) → บันทึกเป็นแผนหัวข้อตั้งต้น (ไม่เกินโควตาแพ็ก)
        seeds = [str(k).strip() for k in (req.keywords or []) if str(k).strip()][:pack]
        if seeds:
            import json as _json
            p.topic_plan = _json.dumps([{"topic": k, "cluster": ""} for k in seeds], ensure_ascii=False)
            await s.commit()
        import json as _json
        if src == "facebook" and fb_url:             # 📘 กลไก FB: CTA ท้ายบทความ → ลิงก์ไปเพจ Facebook (คนอ่าน→ทักเพจ)
            p.cta_json = _json.dumps({"enabled": True, "headline": "สนใจบริการ? ทักเราเลย",
                                      "text": "แชทกับเราทาง Facebook ได้ทันที", "button": "💬 ทักทาง Facebook",
                                      "url": fb_url}, ensure_ascii=False)
        elif not (p.cta_json or "").strip():         # 🎯 ทุกโปรเจ็ค: เปิดฟอร์มดักลีดท้ายบทความ default (เก็บชื่อ+เบอร์ → ส่งให้ลูกค้าเจ้าของธุรกิจ)
            p.cta_json = _json.dumps({"enabled": True, "capture": True, "headline": "สนใจบริการของเรา?",
                                      "text": "ทิ้งชื่อและเบอร์ไว้ เดี๋ยวทีมงานติดต่อกลับ", "button": "ให้เราติดต่อกลับ"},
                                     ensure_ascii=False)
        if not (getattr(p, "report_token", "") or "").strip():   # โทเคนสาธารณะ — ผูกลีดจากฟอร์มบทความ + ลิงก์รายงาน
            p.report_token = secrets.token_urlsafe(16)
        await s.commit()
        await s.refresh(p)
        result = _proj_dict(p)
        new_id = p.id
    if defer_analyze:                                # ผู้เรียก (เช่น imweb_save) จะ enqueue analyze เองหลัง commit brief → บทความแรกได้ business_context/FAQ ครบ (กัน race)
        result["analyzing"] = False
        result["producing"] = False
        result["deferred"] = True
        return result
    # "ใส่แค่ลิงก์" → อ่านเว็บลูกค้าเอง + 'เริ่มเขียนบทความแรกให้เลย' (เบื้องหลัง · ล้มก็ไม่กระทบการสร้างโปรเจ็ค)
    try:
        from app.worker.tasks import analyze_project
        # analyze_project (then_produce=True) อ่านเว็บจริงเสร็จแล้ว 'สั่งผลิตบทความแรกเองใน finally' เสมอ
        # (แม้ analyze ล่ม) → ไม่ต้อง enqueue produce ซ้ำที่นี่ กันบทความแรกซ้ำหัวข้อจาก 2 รอบชนกัน
        analyze_project.delay(new_id)
        result["analyzing"] = True
        result["producing"] = True
    except Exception:  # noqa: BLE001
        result["analyzing"] = False
        result["producing"] = False
    return result


@app.post("/api/projects/{project_id}/keywords")
async def add_keywords(project_id: int, req: KeywordsAddRequest, user=Depends(get_current_user)):
    """➕ เพิ่มคีย์เวิร์ด/หัวข้อให้โปรเจ็คที่ 'กำลังทำงาน' — ต่อท้ายแผนหัวข้อ (topic_plan)
    ไม่กระทบบทความที่ผลิตอยู่ (produce หยิบหัวข้อที่ยังไม่ผลิตในรอบถัดไป) · รวมสูงสุด 50"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import json as _json
    from app.db.models import Project
    from app import plans
    kws = [str(k).strip() for k in (req.keywords or []) if str(k).strip()]
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        cap = plans.normalize_pack(getattr(p, "keyword_pack", plans.DEFAULT_PACK))   # เพดาน = แพ็กของลูกค้า
        try:
            plan = _json.loads(p.topic_plan) if (p.topic_plan or "").strip() else []
        except Exception:  # noqa: BLE001
            plan = []
        have = set()
        for it in plan:
            t = (it.get("topic") if isinstance(it, dict) else str(it)) or ""
            have.add(t.strip().lower())
        added = 0
        for k in kws:
            if len(plan) >= cap:                     # เพดานรวม = แพ็ก (10/30/50)
                break
            if k.lower() not in have:
                plan.append({"topic": k, "cluster": "เพิ่มเอง"})
                have.add(k.lower()); added += 1
        p.topic_plan = _json.dumps(plan, ensure_ascii=False)
        await s.commit()
        total = len(plan)
    return {"added": added, "total": total, "cap": cap}


@app.put("/api/projects/{project_id}/pack")
async def set_project_pack(project_id: int, req: KeywordPackUpdate, user=Depends(get_current_user)):
    """ตั้งแพ็กคีย์เวิร์ดของโปรเจ็ค/ลูกค้า (10/30/50) — เฉพาะแอดมิน
    โครงสร้างพร้อมเปิดให้ลูกค้าเลือกเอง (ผูกบิลลิ่ง) ภายหลัง · ไม่ลบคีย์เดิม (กันข้อมูลหาย)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import usage, plans
    from app.db.models import Project
    if (await usage.user_plan(user["id"])) != "admin":
        raise HTTPException(403, "การตั้งแพ็กสงวนไว้สำหรับแอดมินเท่านั้น")
    pack = plans.normalize_pack(req.pack)
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        p.keyword_pack = pack
        await s.commit()
        used = _topic_count(p)
    return {"ok": True, "keyword_pack": pack, "keywords_used": used, "over_quota": used > pack}


@app.post("/api/projects/{project_id}/to-facebook")
async def convert_to_facebook(project_id: int, req: FacebookConvert, user=Depends(get_current_user)):
    """📘 แปลงโปรเจ็คให้ทำงานแบบ 'ลูกค้ามีแค่ Facebook' — โฮสต์บล็อกให้ (managed) + ตั้งปุ่ม CTA ลิงก์ไปเพจ FB
    ใช้กับโปรเจ็คที่เผลอสร้างเป็น facebook.com หรือเว็บที่จริง ๆ ลูกค้าไม่มี → ให้กลไกถูกต้อง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    fb_url = (req.facebook_url or "").strip()
    if not fb_url:
        raise HTTPException(422, "กรุณาวางลิงก์เพจ Facebook")
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        p.publish_mode = "managed"                   # โฮสต์บล็อกให้ (ลูกค้าไม่มีเว็บของตัวเอง)
        import json as _json
        p.cta_json = _json.dumps({"enabled": True, "headline": "สนใจบริการ? ทักเราเลย",
                                  "text": "แชทกับเราทาง Facebook ได้ทันที", "button": "💬 ทักทาง Facebook",
                                  "url": fb_url}, ensure_ascii=False)
        if (req.name or "").strip():
            p.name = req.name.strip()[:200]
        await s.commit()
    return {"ok": True, "publish_mode": "managed", "cta_url": fb_url}


@app.get("/api/projects/{project_id}/sms")
async def get_sms_alert(project_id: int, user=Depends(get_current_user)):
    """ตั้งค่าแจ้งเตือน SMS ของโปรเจ็ค + สถานะว่าเซิร์ฟเวอร์ตั้ง Twilio พร้อมส่งไหม"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    from app.connectors import notify
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        enabled = bool(getattr(p, "sms_enabled", False))
        to = getattr(p, "sms_to", "") or ""
    return {"enabled": enabled, "to": to, "twilio_ready": notify.sms_ready()}


@app.put("/api/projects/{project_id}/sms")
async def set_sms_alert(project_id: int, req: SmsAlertUpdate, user=Depends(get_current_user)):
    """เปิด/ปิด + ตั้งเบอร์แจ้งเตือน SMS อันดับของโปรเจ็ค (คีย์ติด/ขยับขึ้น) — ระบบแปลงเบอร์เป็น E.164 ให้"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    from app.connectors import notify
    to = notify.normalize_phone(req.to or "")
    if req.enabled and not to:
        raise HTTPException(422, "กรุณากรอกเบอร์ปลายทางให้ถูกต้อง (เช่น 0987893988)")
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        p.sms_enabled = bool(req.enabled)
        p.sms_to = to
        await s.commit()
    return {"ok": True, "enabled": bool(req.enabled), "to": to, "twilio_ready": notify.sms_ready()}


@app.get("/api/projects/{project_id}/aeo-questions")
async def get_aeo_questions(project_id: int, user=Depends(get_current_user)):
    """คำถาม AEO ที่ลูกค้าตั้งเอง + ชุด 'แนะนำอัตโนมัติ' (ถ้ายังไม่ได้ตั้ง) ไว้เติมในกล่องให้ง่าย"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    from app.worker.tasks import _aeo_questions_of, _project_questions
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        custom = _aeo_questions_of(p)
        suggested = [] if custom else await _project_questions(p, project_id)
    return {"questions": custom, "suggested": suggested, "cap": 30}


@app.put("/api/projects/{project_id}/aeo-questions")
async def set_aeo_questions(project_id: int, req: AeoQuestionsUpdate, user=Depends(get_current_user)):
    """บันทึกคำถาม AEO (แทนที่ทั้งชุด) — ใช้ 'มาก่อน' คำถามอัตโนมัติเวลาสุ่มถาม AI · สูงสุด 30
    ไม่กระทบบทความที่ผลิตอยู่ (มีผลกับรอบวัด AI Citation ครั้งถัดไปเท่านั้น)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import json as _json
    from app.db.models import Project
    seen, qs = set(), []
    for q in (req.questions or []):
        t = str(q).strip()
        if t and t.lower() not in seen:
            seen.add(t.lower()); qs.append(t)
        if len(qs) >= 30:
            break
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        p.aeo_questions = _json.dumps(qs, ensure_ascii=False)
        await s.commit()
    return {"total": len(qs), "cap": 30}


@app.get("/api/projects/{project_id}/ads/recommend")
async def ads_recommend(project_id: int, user=Depends(get_current_user)):
    """📣 Ads Advisor — แนะนำว่าควรยิง Google Ads คีย์ไหน (จากช่องว่าง organic จริง)
    'ยิง' = คีย์มูลค่าที่ยังไม่ติดหน้า 1 · 'ปิด' = คีย์ที่ติดหน้า 1 แล้ว (จ่ายซ้ำไม่คุ้ม) — ข้อมูลจริงล้วน"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import RankSnapshot, Article
    async with db.session() as s:
        proj = await _read_project(s, project_id, user)
        rows = (await s.execute(
            select(RankSnapshot).where(RankSnapshot.project_id == project_id)
            .order_by(RankSnapshot.checked_at))).scalars().all()
        arts = (await s.execute(
            select(Article.id, Article.title, Article.url).where(
                Article.project_id == project_id, Article.status == "published"))).all()
    latest = {r.keyword: (r.rank, bool(r.on_page1)) for r in rows}
    land = {(t or "").strip().lower(): {"article_id": aid, "url": u or ""} for aid, t, u in arts}
    # ผู้สมัคร: คีย์ที่วัดอันดับแล้ว + หัวข้อบทความที่เผยแพร่ (ยังไม่วัด = ถือว่ายังไม่ติด → ยิงได้)
    candidates = set(latest.keys()) | {a[1] for a in arts if a[1]}
    advertise, pause = [], []
    for kw in candidates:
        rank, op = latest.get(kw, (None, False))
        lk = land.get(kw.strip().lower(), {})
        item = {"keyword": kw, "rank": rank, "article_id": lk.get("article_id"), "url": lk.get("url") or ""}
        if op or (rank is not None and rank <= 10):
            item["reason"] = "ติดหน้า 1 แล้ว (#%d) — พิจารณาปิด Ads ประหยัดงบ" % rank
            pause.append(item)
        else:
            item["reason"] = ("ยังไม่ติด (>100) — ยิงเก็บทราฟฟิกเลย" if rank is None
                              else "จ่อหน้า 1 (#%d) — ยิงเสริมระหว่างดันขึ้น" % rank)
            advertise.append(item)
    advertise.sort(key=lambda x: (x["rank"] is None, x["rank"] if x["rank"] is not None else 999))
    pause.sort(key=lambda x: x["rank"] if x["rank"] is not None else 999)
    return {"advertise": advertise[:30], "pause": pause[:20],
            "tracked": len(latest), "domain": proj.domain,
            "note": "แนะนำจากช่องว่าง organic จริง — ยิงเฉพาะที่ยังไม่ติด แล้วปิดเมื่อติดหน้า 1 = ประหยัดสุด"}


@app.post("/api/projects/{project_id}/ads/creative")
async def ads_creative(project_id: int, req: AdCreativeRequest, user=Depends(get_current_user)):
    """📣 ร่างชุดโฆษณา Google Ads (RSA) จริงตามสเปกให้คีย์เวิร์ดที่เลือก — headlines/descriptions/paths + ลิงก์ปลายทาง"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    kw = (req.keyword or "").strip()
    if not kw:
        raise HTTPException(400, "ต้องระบุคีย์เวิร์ด")
    from sqlalchemy import func as _func
    from app.db.models import Article
    from app.connectors import content
    async with db.session() as s:
        proj = await _read_project(s, project_id, user)
        biz = getattr(proj, "business_context", "") or proj.name
        domain, lang = proj.domain, proj.language
        art = (await s.execute(
            select(Article.title, Article.url).where(
                Article.project_id == project_id, Article.status == "published",
                _func.lower(Article.title) == kw.lower()).limit(1))).first()
    final_url = (art[1] if (art and art[1]) else ("https://" + (domain or "")))
    title = (art[0] if art else kw)
    try:
        data = await content.ad_copy(kw, business_context=biz, url=final_url, title=title, language=lang)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ร่างโฆษณาไม่สำเร็จ: " + str(e)[:150])
    data["final_url"] = final_url
    data["keyword"] = kw
    data["has_landing"] = bool(art and art[1])
    return data


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
    source, context, seed = "ai", "", None
    try:                                             # อ่านเว็บลูกค้า 'จริง' ก่อน → คีย์ตรงกับสินค้า/บริการจริง (ไม่เดาจากชื่อโดเมน)
        from app.connectors import site
        ctx = await site.analyze(domain, req.name or "", lang)
        if ctx:
            context = site.context_text(ctx)
            seed = ctx.get("seed_keywords") or None
            source = "site"
    except Exception:  # noqa: BLE001
        pass
    try:
        kws = await content.suggest_keywords(domain, req.name or "", lang, 12, context=context, seed=seed)
    except Exception:  # noqa: BLE001
        kws = []
    if not kws:                                   # AI ล่ม/คีย์ไม่พร้อม → หัวข้อตั้งต้นจากแบรนด์ (ยังใช้งานได้)
        from app.worker.tasks import _starter_topics
        kws = [{"kw": t, "intent": "", "why": ""} for t in _starter_topics(req.name or domain, lang)]
        source = "starter"
    return {"domain": domain, "keywords": kws, "source": source}


@app.post("/api/keyword-report")
async def keyword_report(req: KeywordReportRequest, user=Depends(get_current_user)):
    """💼 รายงานวิจัยคีย์เวิร์ด 'สำหรับขายลูกค้า' — ใส่คีย์+ธุรกิจ → ดึงคีย์ที่เกี่ยว 20+ คำ
    พร้อมปริมาณค้นหาจริง/เดือน+วัน (Google Ads) + % ความยากติดหน้า 1 (KD 0-100) · ตัวเลขจริงจาก DataForSEO"""
    from app.connectors import serp
    from app.config import settings as S
    if not (S.dataforseo_login and S.dataforseo_password):
        raise HTTPException(503, "ยังไม่ได้ตั้งคีย์ DataForSEO — ต้องมีเพื่อดึงปริมาณค้นหา/ความยาก 'จริง'")
    seed = (req.keyword or "").strip()
    biz = (req.business or "").strip()
    if not seed and not biz:
        raise HTTPException(422, "กรุณาใส่คีย์เวิร์ดหลัก หรือชื่อธุรกิจ")
    try:
        rows = await serp.keyword_research([x for x in (seed, biz) if x], limit=req.limit or 30)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ดึงคีย์เวิร์ดไม่ได้ (ตรวจเครดิต/คีย์ DataForSEO): " + str(e)[:150])
    rows = [r for r in rows if r.get("volume")]              # เอาเฉพาะที่มีปริมาณค้นหาจริง
    if not rows:                                             # ว่างจริง → แยก 'เครดิตหมด' ออกจาก 'ไม่มีคำ' (โปร่งใส)
        bal = await serp.account_balance()
        if bal is not None and bal < 0.05:
            raise HTTPException(402, "เครดิต DataForSEO หมด (เหลือ $%.2f) — เติมเงินก่อนใช้งาน" % bal)
    # ── จัดกลุ่ม 'เชิงธุรกิจ' ตามเจตนาการค้นหา → รายงานที่เอาไปขายได้จริง ──
    _LABELS = {
        "commercial": ("🔥", "เชิงแนะนำ / พร้อมจ้าง",
                       "คนกำลังหา 'คนทำ · ราคา · ที่ไหนดี' = ลูกค้าพร้อมจ่าย ปิดการขายง่ายสุด"),
        "problem":    ("💡", "เชิงปัญหา / คำถาม",
                       "คนมีคำถาม/ปัญหา = ทำคอนเทนต์ดักไว้ให้ Google + AI หยิบไปตอบ (SEO/AEO)"),
        "generic":    ("📦", "หมวดสินค้า / บริการ",
                       "ค้นชื่อสินค้า/บริการตรง ๆ = ดัน SEO ให้ติดหน้าแรก กินทราฟฟิกกว้าง"),
        "brand":      ("🏢", "แบรนด์ / คู่แข่ง (ไม่นับรวม)",
                       "ชื่อบริษัทคู่แข่ง — ไว้ดูว่าใครครองตลาด ไม่ใช่คีย์ที่เราปั้นให้ลูกค้า"),
    }

    def _sub(rs):
        vol = sum(r["volume"] for r in rs)
        ds = [r["difficulty"] for r in rs if isinstance(r.get("difficulty"), (int, float))]
        return {"count": len(rs), "monthly": vol, "daily": round(vol / 30),
                "avg_difficulty": round(sum(ds) / len(ds)) if ds else None}

    groups = []
    for key in ("commercial", "problem", "generic", "brand"):
        rs = [r for r in rows if r.get("intent") == key]
        if not rs:
            continue
        emoji, title, desc = _LABELS[key]
        groups.append({"key": key, "emoji": emoji, "title": title, "desc": desc,
                       "summary": _sub(rs), "keywords": rs})

    sellable = [r for r in rows if r.get("intent") != "brand"]   # ที่ปั้นให้ลูกค้าได้จริง (ตัดคู่แข่ง)
    diffs = [r["difficulty"] for r in sellable if isinstance(r.get("difficulty"), (int, float))]
    total_vol = sum(r["volume"] for r in sellable)
    summary = {
        "count": len(sellable),
        "total_monthly": total_vol,
        "total_daily": round(total_vol / 30),
        "avg_difficulty": round(sum(diffs) / len(diffs)) if diffs else None,
        "easy": sum(1 for d in diffs if d < 30),
        "medium": sum(1 for d in diffs if 30 <= d < 60),
        "hard": sum(1 for d in diffs if d >= 60),
        "commercial": sum(1 for r in rows if r.get("intent") == "commercial"),
        "problem": sum(1 for r in rows if r.get("intent") == "problem"),
    }
    return {"keyword": seed, "business": biz,
            "keywords": sellable, "groups": groups, "summary": summary,
            "note": "แยกตามเจตนาการค้นหา · ปริมาณค้นหา = Google Ads (DataForSEO) · "
                    "ความยาก = Keyword Difficulty 0-100 (ต่ำ=ง่ายติดหน้า 1) · ตัวเลขจริง ตรวจย้อนได้"}


@app.post("/api/pantip-radar")
async def pantip_radar(req: PantipRadarRequest, user=Depends(get_current_user)):
    """🎯 เรดาร์ Pantip — หากระทู้ที่ 'ติดหน้า 1 Google' สำหรับหัวข้อเรา (SERP จริง)
    ไปตอบให้มีประโยชน์ = ยืมทราฟฟิก+ความน่าเชื่อถือที่กระทู้นั้นมีอยู่แล้ว (ต้องโพสต์เอง ห้ามสแปม/auto)"""
    from app.connectors import serp
    from app.config import settings as S
    if not (S.dataforseo_login and S.dataforseo_password):
        raise HTTPException(503, "ยังไม่ได้ตั้งคีย์ DataForSEO — ต้องมีเพื่อดึงผลอันดับ Google จริง")
    kw = (req.keyword or "").strip()
    if not kw:
        raise HTTPException(422, "ใส่คีย์เวิร์ด/หัวข้อก่อน")
    biz = (req.business or "").strip()
    # สร้างชุด query ที่ Pantip มักติดหน้า 1 (คำถาม/รีวิว/ความเห็น)
    queries = [kw, kw + " pantip", kw + " ดีไหม", kw + " รีวิว", kw + " ที่ไหนดี pantip"]
    if biz:
        queries += [biz + " pantip", biz + " ดีไหม pantip"]
    try:
        threads = await serp.pantip_page1(queries)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ดึงผล SERP ไม่ได้ (ตรวจเครดิต/คีย์ DataForSEO): " + str(e)[:150])
    return {"keyword": kw, "business": biz, "threads": threads, "count": len(threads),
            "note": "กระทู้ Pantip ที่ติดหน้า 1 Google สำหรับหัวข้อนี้ · ไปตอบให้ 'มีประโยชน์จริง' "
                    "= ยืมทราฟฟิก+ความน่าเชื่อถือที่มีอยู่แล้ว · ต้องรีวิว+โพสต์เอง (ขาว ไม่สแปม ไม่ auto)"}


@app.post("/api/pantip-reply")
async def pantip_reply(req: PantipReplyRequest, user=Depends(get_current_user)):
    """✍️ ร่างคำตอบกระทู้แบบ 'ช่วยจริง ไม่ขายของ' ให้เอาไปตรวจ+โพสต์เอง (ไม่โพสต์อัตโนมัติ = ไม่โดนแบน)"""
    from app.connectors import discovery
    brand = (req.brand or "ImVisible").strip()
    ref = (req.reference or "").strip()
    try:
        out = await discovery.draft_reply(req.title or "", req.snippet or "", ref, brand)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ร่างคำตอบไม่ได้: " + str(e)[:150])
    return {"reply": (out or {}).get("text", ""), "provider": (out or {}).get("provider"),
            "url": req.url or "",
            "note": "ตรวจให้เข้ากับกระทู้ก่อนโพสต์เอง · ตอบให้ตรงคำถาม ห้ามยัดลิงก์/โฆษณา"}


@app.get("/api/projects/{project_id}/indexnow")
async def indexnow_info(project_id: int, user=Depends(get_current_user)):
    """⚡ คีย์ IndexNow 'ต่อโดเมน' ของโปรเจกต์ + ไฟล์ที่ต้องวาง — วางครั้งเดียว → ทุกบทความใหม่
    ถูกแจ้ง index ทันที (Bing/Yandex + AI-search ที่ใช้ Bing เช่น ChatGPT/Copilot) = ติดไวขึ้นมาก"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from urllib.parse import urlparse
    from app.db.models import Project
    from app.connectors import publish as pub
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        domain = (getattr(p, "custom_domain", "") or p.domain or "").strip()
    host = (urlparse(domain if "://" in domain else "https://" + domain).hostname or "").lower().lstrip(".")
    if not host:
        raise HTTPException(422, "โปรเจ็คนี้ยังไม่มีโดเมน — เพิ่มโดเมนก่อน")
    key = pub.indexnow_key_for(host)
    managed = bool(pub_settings_indexnow_host() and host == pub_settings_indexnow_host())
    return {
        "host": host, "key": key,
        "file_name": key + ".txt",
        "file_content": key,
        "file_url": "https://%s/%s.txt" % (host, key),
        "managed": managed,   # true = โดเมนที่เราโฮสต์ให้ (วางไฟล์ให้แล้ว ไม่ต้องทำอะไร)
        "instructions": (
            "โดเมนนี้เราโฮสต์ให้ — วางไฟล์คีย์ให้เรียบร้อยแล้ว บทความใหม่จะถูกเร่ง index อัตโนมัติ ✅"
            if managed else
            "สร้างไฟล์ชื่อ “%s.txt” ข้างในพิมพ์ “%s” แล้ววางที่ root ของ %s (เปิดได้ที่ https://%s/%s.txt) "
            "→ จากนั้นทุกบทความใหม่จะถูกแจ้ง index อัตโนมัติทันที · ทำครั้งเดียวใช้ยาว" % (key, key, host, host, key)
        ),
    }


def pub_settings_indexnow_host() -> str:
    from app.config import settings as _s
    return (getattr(_s, "indexnow_host", "") or "").lower()


_GOAL_TH = {"booking": "รับการจอง/นัดหมาย", "order": "ขาย/สั่งซื้อสินค้า", "call": "โทรหาเรา",
            "chat": "แชท/ทักสอบถาม", "leads": "เก็บรายชื่อผู้สนใจ (ลีด)"}
_GOAL_BTN = {"booking": "📅 จองเลย", "order": "🛒 สั่งซื้อ", "call": "📞 โทรเลย",
             "chat": "💬 ทักแชท", "leads": "✉️ ติดต่อเรา"}


def _brief_line_url(line: str) -> str:
    ln = (line or "").strip()
    if not ln:
        return ""
    if ln.startswith("http"):
        return ln
    if ln.startswith("@"):
        return "https://line.me/R/ti/p/%40" + ln[1:]
    return "https://line.me/ti/p/" + ln


def _brief_to_imweb(b) -> dict:
    """ประกอบ brief ที่ 'รวย' ส่ง IM WEB — ทั้ง key มีโครงสร้าง + description ข้อความ (IM WEB อ่าน brief แบบอิสระ)"""
    def cl(x):
        return (x or "").strip()
    contact = {k: v for k, v in {
        "line": cl(b.line), "phone": cl(b.phone), "email": cl(b.email),
        "facebook": cl(b.facebook), "instagram": cl(b.instagram),
        "address": cl(b.address), "serviceArea": cl(b.service_area),
        "hours": cl(b.hours), "mapUrl": cl(b.map_url)}.items() if v}
    faqs = [{"q": cl(f.q), "a": cl(f.a)} for f in (b.faqs or []) if cl(f.q)]
    segs = []
    if cl(b.brand_name):
        segs.append("สร้างเว็บสำหรับ '%s'%s" % (cl(b.brand_name), (" (%s)" % cl(b.biz_type)) if cl(b.biz_type) else ""))
    if cl(b.about):
        segs.append("รายละเอียด: " + cl(b.about))
    if cl(b.usp):
        segs.append("จุดเด่นที่ต้องชูให้เด่น: " + cl(b.usp))
    if cl(b.audience):
        segs.append("กลุ่มลูกค้าเป้าหมาย: " + cl(b.audience))
    if cl(b.products):
        segs.append("สินค้า/บริการ: " + cl(b.products))
    if cl(b.price_info):
        segs.append("ราคา/แพ็กเกจ: " + cl(b.price_info))
    if cl(b.goal):
        segs.append("เป้าหมายหลักของเว็บ (ปุ่ม CTA ต้องพาไปทำสิ่งนี้): " + _GOAL_TH.get(cl(b.goal), cl(b.goal)))
    if contact:
        bits = [x for x in [cl(b.phone) and ("โทร " + cl(b.phone)), cl(b.line) and ("LINE " + cl(b.line)),
                            cl(b.address) and ("ที่อยู่ " + cl(b.address)), cl(b.hours) and ("เวลาทำการ " + cl(b.hours))] if x]
        if bits:
            segs.append("ช่องทางติดต่อ/ข้อมูลร้าน: " + " · ".join(bits))
    if faqs:
        segs.append("ใส่ส่วน 'คำถามที่พบบ่อย (FAQ)' ด้วยคำถาม: " + " / ".join(f["q"] for f in faqs[:8]))
    return {
        "brandName": cl(b.brand_name), "bizType": cl(b.biz_type), "about": cl(b.about),
        "usp": cl(b.usp), "audience": cl(b.audience), "products": cl(b.products),
        "pricing": cl(b.price_info), "vibe": cl(b.vibe), "goal": cl(b.goal),
        "brandColor": cl(b.brand_color), "logoUrl": cl(b.logo_url),
        "keywords": [k for k in (b.keywords or []) if str(k).strip()][:12],
        "faqs": faqs, "contact": contact,
        "description": " \n".join(segs),
    }


def _brief_context(b) -> str:
    """business_context ป้อนเครื่องยนต์คอนเทนต์ (ข้อความล้วน)"""
    def cl(x):
        return (x or "").strip()
    parts = []
    if cl(b.brand_name):
        parts.append("ธุรกิจ: %s%s" % (cl(b.brand_name), (" (%s)" % cl(b.biz_type)) if cl(b.biz_type) else ""))
    for lbl, v in [("", cl(b.about)), ("จุดเด่น", cl(b.usp)), ("กลุ่มลูกค้า", cl(b.audience)),
                   ("สินค้า/บริการ", cl(b.products)), ("ราคา", cl(b.price_info)),
                   ("พื้นที่บริการ", cl(b.service_area)), ("ที่ตั้ง", cl(b.address))]:
        if v:
            parts.append(("%s: %s" % (lbl, v)) if lbl else v)
    return " · ".join(parts)[:2000]


def _brief_brand_terms(b) -> str:
    """brand_terms (คั่น ,) → ใช้ตรวจ AI citation + ดึง URL โซเชียลเป็น sameAs"""
    def cl(x):
        return (x or "").strip()
    terms = []
    if cl(b.brand_name):
        terms.append(cl(b.brand_name))
    for u in (cl(b.facebook), cl(b.instagram)):
        if u.startswith("http"):
            terms.append(u)
    lu = _brief_line_url(b.line)
    if lu.startswith("http"):
        terms.append(lu)
    out, seen = [], set()
    for t in terms:
        if t and t not in seen:
            seen.add(t); out.append(t)
    return ", ".join(out)[:1000]


def _brief_cta(b) -> dict | None:
    """cta_json ท้ายบทความ (เนียนขาย/เก็บลีด) จากเป้าหมาย + ช่องทางติดต่อ"""
    def cl(x):
        return (x or "").strip()
    goal = cl(b.goal).lower()
    url = ""
    if goal == "call" and cl(b.phone):
        url = "tel:" + cl(b.phone)
    elif cl(b.line):
        url = _brief_line_url(b.line)
    elif cl(b.phone):
        url = "tel:" + cl(b.phone)
    elif cl(b.facebook).startswith("http"):
        url = cl(b.facebook)
    elif cl(b.map_url).startswith("http"):
        url = cl(b.map_url)
    if not url:
        return None
    return {"enabled": True,
            "headline": ("สนใจบริการ%s?" % ((" " + cl(b.brand_name)) if cl(b.brand_name) else "")),
            "text": "ติดต่อเราได้เลย ยินดีให้คำปรึกษาฟรี",
            "button": _GOAL_BTN.get(goal, "💬 ติดต่อเรา"), "url": url}


@app.post("/api/imweb/generate")
async def imweb_generate(req: ImwebGenerateRequest, user=Depends(get_current_user)):
    """🏗️ สร้างเว็บด้วย IM WEB (AI builder) จาก brief ละเอียด → คืน HTML เว็บพร้อมใช้ (themes)
    brief ที่รวย (จุดเด่น/ติดต่อ/ที่ตั้ง/FAQ) = เว็บดีขึ้น + เก็บวัตถุดิบ AEO/GEO ไว้ carry เข้าโปรเจกต์ตอน save"""
    from app.connectors import imweb
    if not imweb.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้ง IMWEB_API_KEY (ผู้ดูแลตั้งใน backend/.env)")
    b = req.brief
    if not ((b.brand_name or "").strip() or (b.about or "").strip()):
        raise HTTPException(422, "ใส่ชื่อแบรนด์ หรือรายละเอียดธุรกิจก่อน")
    brief = _brief_to_imweb(b)
    brief["motionLevel"] = (req.motion_level or "high").strip()
    brief["language"] = (req.language or "th").strip()
    res = await imweb.generate_site(brief, tier=req.tier or "paid", variants=req.variants or 1)
    if not res.get("ok"):
        raise HTTPException(502, "สร้างเว็บไม่สำเร็จ (IM WEB): " + str(res.get("error"))[:160])
    return res


@app.post("/api/imweb/save")
async def imweb_save(req: ImwebSaveRequest, user=Depends(get_current_user)):
    """✅ 'ใช้เว็บนี้' — บันทึกเว็บที่ IM WEB สร้าง → สร้างโปรเจกต์ (โฮสต์ให้) + ฝัง schema AEO/GEO ลงหน้าแรก
    + carry brief เข้าโปรเจกต์ (business_context/brand_terms/aeo_questions/cta) → 'โตเอง' แบบเต็มแม็กตั้งแต่แรก"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import json as _json
    from app import public as _public
    from app.db.models import Project
    b = req.brief
    html = (req.html or "").strip()
    if len(html) < 100:
        raise HTTPException(422, "ไม่มี HTML เว็บ — สร้างเว็บก่อน")
    if len(html) > 900000:
        raise HTTPException(413, "HTML ใหญ่เกิน 900KB")
    brand = (b.brand_name or "เว็บใหม่").strip()
    lang = (req.language or "th")                            # SiteBrief ไม่มี field language → ใช้ req.language เท่านั้น
    pseudo = project_slug_from_domain(brand) or "site"      # ไม่มีเว็บนอก → เราโฮสต์เอง (โดเมนเทียมจากชื่อแบรนด์)
    kws = [str(k).strip() for k in (b.keywords or []) if str(k).strip()][:50]
    pc = ProjectCreate(name=brand, domain=pseudo, url="", language=lang, mode="auto",
                       publish_mode="managed", keywords=kws)
    created = await create_project(pc, user, defer_analyze=True)   # ชะลอ analyze → ให้ carry brief commit ก่อน (บทความแรกได้บริบทครบ)
    pid = created.get("id")
    if not pid:
        raise HTTPException(500, "สร้างโปรเจกต์ไม่สำเร็จ")
    home = created.get("public_home") or ""
    brief_d = _brief_to_imweb(b)                             # dict สำหรับ inject (มี about/usp/contact/faqs/logo)
    brief_d.update({"line": (b.line or "").strip(), "phone": (b.phone or "").strip(),
                    "email": (b.email or "").strip(), "facebook": (b.facebook or "").strip(),
                    "instagram": (b.instagram or "").strip(), "address": (b.address or "").strip(),
                    "service_area": (b.service_area or "").strip(), "hours": (b.hours or "").strip(),
                    "map_url": (b.map_url or "").strip(), "logo_url": (b.logo_url or "").strip()})
    enriched = _public.inject_aeo_geo(html, name=brand, home=home, lang=lang, brief=brief_d)
    ctx = _brief_context(b)
    bterms = _brief_brand_terms(b)
    faq_qs = [(f.q or "").strip() for f in (b.faqs or []) if (f.q or "").strip()]
    cta = _brief_cta(b)
    async with db.session() as s:                            # เก็บ HTML (ฝัง schema แล้ว) + carry brief เข้าโปรเจกต์
        p = await s.get(Project, pid)
        if p:
            p.home_html = enriched
            if ctx:
                p.business_context = ctx
            if bterms:
                p.brand_terms = bterms
            if faq_qs and not (getattr(p, "aeo_questions", "") or "").strip():
                p.aeo_questions = _json.dumps(faq_qs[:10], ensure_ascii=False)
            if cta and not (getattr(p, "cta_json", "") or "").strip():
                p.cta_json = _json.dumps(cta, ensure_ascii=False)
            await s.commit()
    try:                                                     # commit brief แล้ว → ค่อย enqueue analyze/produce (บทความแรกได้ business_context+FAQ ครบ)
        from app.worker.tasks import analyze_project
        analyze_project.delay(pid)
    except Exception as e:  # noqa: BLE001
        print("[imweb_save] enqueue analyze ไม่ได้: %r" % e)
    return {"ok": True, "project_id": pid, "name": created.get("name"),
            "public_home": home,
            "aeo_injected": True, "faqs": len(faq_qs), "carried": bool(ctx),
            "note": "บันทึก+โฮสต์เว็บ + ฝัง schema AEO/GEO แล้ว · ระบบเริ่มผลิตคอนเทนต์ + ดันอันดับให้อัตโนมัติ (เว็บที่โตเอง)"}


@app.post("/api/imweb/prefill")
async def imweb_prefill(req: ImwebPrefillRequest, user=Depends(get_current_user)):
    """🔗 วางลิงก์เว็บ/เพจเดิม → AI อ่านหน้าจริง (กัน SSRF) แล้วเรียบเรียงเป็น 'บรีฟ' อัตโนมัติ
    → เติมฟอร์มสร้างเว็บให้ ลูกค้าไม่ต้องกรอกเยอะ (about/usp/faqs AI เรียบเรียงให้จากเนื้อหา) · ตรวจ/แก้ก่อนสร้างได้"""
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(422, "กรุณาใส่ลิงก์เว็บ/เพจ")
    import re as _re, json as _json2
    from app.connectors import sitecheck, content
    base, html, err = await sitecheck._fetch_home(url)
    text = ""
    if html:
        text = _re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
        text = _re.sub(r"(?s)<[^>]+>", " ", text)
        text = _re.sub(r"\s+", " ", text).strip()[:5000]
    if len(text) < 400:      # อ่านไม่ได้/บางเกิน (Facebook/JS) → ให้บอทค้นเว็บสาธารณะเองจาก 'ชื่อธุรกิจ'
        from app.connectors import site as _site
        qn = ""
        if html:             # เดาชื่อธุรกิจจาก og:title / <title> ที่เพจส่งมา (FB มักมี)
            mt = _re.search(r'og:title["\']?\s*content=["\']([^"\']+)', html) or _re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
            if mt:
                qn = _re.sub(r"\s+", " ", mt.group(1)).strip()[:80]
        if not qn:           # ไม่มี → ใช้ slug จาก URL (เช่น .../tothemoonchumphon)
            seg = url.rstrip("/").split("/")[-1].split("?")[0]
            qn = _re.sub(r"[-_.]+", " ", seg).strip()
        web = await _site._web_context(qn) if qn else {}
        if (web or {}).get("text"):
            text = web["text"][:5000]
            base = base or url
    if len(text) < 120:
        raise HTTPException(422, "อ่านเว็บ/เพจไม่ได้ และค้นเว็บสาธารณะไม่พบข้อมูลพอ — ลองใส่ชื่อธุรกิจให้ชัดในลิงก์ หรือกรอกบรีฟสั้น ๆ เอง")
    sysmsg = ("คุณคือผู้ช่วยเก็บบรีฟทำเว็บ อ่านเนื้อหาหน้าเพจธุรกิจแล้วสกัด/เรียบเรียงเป็น 'บรีฟ' เป็น JSON เท่านั้น "
              "(ห้ามมีข้อความอื่นนอก JSON). คีย์: brand_name, biz_type, about, usp, audience, products, "
              'keywords (array ของ string), faqs (array ของ {"q":..,"a":..}), phone, line, email, facebook, instagram, address, hours. '
              "เติมจากหน้าเพจ; about/usp/faqs เรียบเรียงเองได้จากเนื้อหา. ข้อความเป็นภาษาไทย. ไม่รู้=ค่าว่างหรืออาเรย์ว่าง.")
    usermsg = "URL: %s\n\nเนื้อหาหน้าเพจ:\n%s\n\nส่ง JSON บรีฟเท่านั้น:" % (base, text)
    try:
        _p, raw = await content._llm(sysmsg, usermsg, tier="fast")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "AI อ่านไม่สำเร็จ ลองใหม่: " + str(e)[:120])
    m = _re.search(r"\{.*\}", raw or "", _re.S)
    brief = None
    if m:
        try:
            brief = _json2.loads(m.group(0))
        except Exception:  # noqa: BLE001
            brief = None
    if not isinstance(brief, dict):
        raise HTTPException(502, "AI เรียบเรียงบรีฟไม่สำเร็จ ลองใหม่อีกครั้ง")

    def _s(k):
        v = brief.get(k)
        return v.strip() if isinstance(v, str) else ""
    kraw = brief.get("keywords") if isinstance(brief.get("keywords"), list) else []
    kws = [str(k).strip() for k in kraw if str(k).strip()][:12]
    fraw = brief.get("faqs") if isinstance(brief.get("faqs"), list) else []
    faqs = [{"q": str(f.get("q") or "").strip(), "a": str(f.get("a") or "").strip()}
            for f in fraw if isinstance(f, dict) and str(f.get("q") or "").strip()][:8]
    out = {k: _s(k) for k in ("brand_name", "biz_type", "about", "usp", "audience", "products",
                              "phone", "line", "email", "facebook", "instagram", "address", "hours")}
    out["keywords"] = kws
    out["faqs"] = faqs
    return {"ok": True, "read_from": base, "brief": out}


@app.post("/api/pseo/topics")
async def pseo_topics(req: PseoTopicsRequest, user=Depends(get_current_user)):
    """🎯 pSEO (ติดอันดับ) — เพิ่มหลายหัวข้อ unique 'บนโดเมนหลัก' ทีเดียว → เครื่องยนต์ผลิตหน้า on-domain อัตโนมัติ
    white-hat: หน้าอยู่บนโดเมนเดียว (สะสม authority รวมกัน) + AI เขียนเนื้อหาต่างกันจริงต่อ variant (ไม่ใช่ doorway)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import json as _json
    from app.db.models import Project
    pat = (req.pattern or "รับทำเว็บ{x}").strip()
    variants = [str(v).strip() for v in (req.variants or []) if str(v).strip()][:30]   # กันยิงถี่เกิน
    if not variants:
        raise HTTPException(422, "ใส่ตัวแปรอย่างน้อย 1 อย่าง (เช่น คลินิก, ร้านอาหาร)")
    cluster = (req.cluster or "pSEO").strip()[:60]

    def _mk(v):                                        # ประกอบหัวข้อจาก pattern + variant
        return (pat.replace("{x}", v) if "{x}" in pat else (pat + " " + v)).strip()[:200]

    topics = []
    seen_new = set()
    for v in variants:
        t = _mk(v)
        if t and t.lower() not in seen_new:
            seen_new.add(t.lower()); topics.append(t)

    async with db.session() as s:
        if req.project_id:                             # เจาะจงโปรเจกต์ (ต้องเป็นของผู้ใช้)
            p = await s.get(Project, req.project_id)
            if not p or p.user_id != user["id"]:
                raise HTTPException(404, "ไม่พบโปรเจกต์")
        else:                                          # ไม่ระบุ = โปรเจกต์หลัก (id ต่ำสุด = โดเมนแข็งสุด)
            p = (await s.execute(select(Project).where(Project.user_id == user["id"])
                 .order_by(Project.id).limit(1))).scalars().first()
            if not p:
                raise HTTPException(404, "ยังไม่มีโปรเจกต์ — สร้างโปรเจกต์เว็บหลักก่อน")
        try:
            plan = _json.loads(p.topic_plan) if (p.topic_plan or "").strip() else []
        except Exception:  # noqa: BLE001
            plan = []
        have = {((it.get("topic") if isinstance(it, dict) else str(it)) or "").strip().lower() for it in plan}
        from app import plans
        cap = plans.normalize_pack(getattr(p, "keyword_pack", plans.DEFAULT_PACK))   # เพดาน = แพ็กของลูกค้า (สอดคล้อง add_keywords/GSC/competitor-gap)
        added_list, capped = [], False
        for t in topics:
            if len(plan) >= cap:                       # เต็มโควตาแพ็ก → หยุด (กันผลิตเกินที่จ่าย)
                capped = True; break
            if t.lower() not in have:
                plan.append({"topic": t, "cluster": cluster})
                have.add(t.lower()); added_list.append(t)
        p.topic_plan = _json.dumps(plan, ensure_ascii=False)
        await s.commit()
        pid, pname, pslug = p.id, p.name, (getattr(p, "slug", "") or "")

    producing = False
    if req.produce_now and added_list:                 # เริ่มผลิตชุดแรกทันที (ที่เหลือรอรอบอัตโนมัติ)
        try:
            from app.worker.tasks import produce_for_project
            produce_for_project.delay(pid, min(len(added_list), 3))
            producing = True
        except Exception as e:  # noqa: BLE001
            print("[pseo] enqueue produce ไม่ได้: %r" % e)

    return {"ok": True, "project_id": pid, "project": pname, "slug": pslug,
            "added": len(added_list), "topics": added_list, "total": len(plan),
            "producing": producing, "capped": capped,
            "note": (("บางหัวข้อไม่ถูกเพิ่มเพราะเต็มโควตาแพ็กแล้ว (อัปเกรดแพ็กเพื่อเพิ่ม) · " if capped else "")
                     + "หน้าจะถูกผลิตบนโดเมนหลัก (imvisible.tech/blog/%s/...) — เนื้อหา AI ต่างกันจริงต่อ variant") % pslug}


@app.get("/api/imgentic/models")
async def imgentic_models(user=Depends(get_current_user)):
    """ดึงแคตตาล็อกโมเดล Imgentic (ไว้เลือกชื่อไปตั้ง IMGENTIC_IMAGE_MODEL) — read-only ไม่เสียเครดิต"""
    from app.connectors import imgentic
    if not imgentic.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้ง IMGENTIC_API_KEY ใน backend/.env")
    try:
        models = await imgentic.list_models()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ดึงรายชื่อโมเดล Imgentic ไม่ได้: " + str(e)[:150])
    slim = []
    for m in (models or []):
        if isinstance(m, dict):
            slim.append({"id": m.get("id") or m.get("_id") or "", "name": m.get("name") or m.get("model") or "",
                         "type": m.get("type") or m.get("category") or "", "provider": m.get("provider") or ""})
        else:
            slim.append({"name": str(m)})
    return {"count": len(slim), "models": slim,
            "current_image_model": settings.imgentic_image_model,
            "hint": "เอา name/id ที่เป็น text-to-image ไปตั้ง IMGENTIC_IMAGE_MODEL ใน backend/.env แล้ว force-recreate api worker"}


# ---- เพิ่มใน backend/app/main.py (public endpoint · rate_limit_auth · growth import แบบ inline) ----
@app.get("/api/aeo-study")
async def get_aeo_study(_rl=Depends(rate_limit_auth)):
    """#12 Data Study (สาธารณะ) — สถิติ 'ความพร้อม AEO ของเว็บไทย' จากการสแกนเว็บจริง (linkable asset)
    ตัวเลขจริงจาก DB · ไม่มีดาต้า = คืน ready=False (ไม่กุ) · rate-limit กันสแปม"""
    from app.connectors import growth
    return await growth.aeo_study()



# ---- reddit_quora_radar ----
# import ที่ต้องเพิ่ม: ไม่มี — main.py มี HTTPException/Depends/get_current_user อยู่แล้ว
#   ต้องเพิ่ม SocialRadarRequest ใน import จาก app.schemas ที่หัว main.py (ดู schema_code)
#   วางต่อจาก endpoint pantip_reply (~บรรทัด 1091)

@app.post("/api/social-radar")
async def social_radar(req: SocialRadarRequest, user=Depends(get_current_user)):
    """🌐 เรดาร์ GEO — หาหน้า Reddit · Quora · Medium ที่ 'ติดหน้า 1 Google' สำหรับหัวข้อเรา (SERP จริง)
    AI (ChatGPT/Perplexity) อ้างอิงชุมชนพวกนี้หนักมาก → ไปตอบให้มีประโยชน์ = ดัน GEO
    (ต้องรีวิว+โพสต์เอง ห้ามสแปม/auto)"""
    from app.connectors import growth
    from app.config import settings as S
    if not (S.dataforseo_login and S.dataforseo_password):
        raise HTTPException(503, "ยังไม่ได้ตั้งคีย์ DataForSEO — ต้องมีเพื่อดึงผลอันดับ Google จริง")
    kw = (req.keyword or "").strip()
    if not kw:
        raise HTTPException(422, "ใส่คีย์เวิร์ด/หัวข้อก่อน")
    biz = (req.business or "").strip()
    sites = tuple(s.strip().lower() for s in (req.sites or []) if s.strip()) or \
        ("reddit.com", "quora.com", "medium.com")
    # สร้างชุด query ที่ชุมชนต่างชาติมักติดหน้า 1 (คำถาม/รีวิว/แนะนำ — reddit/quora ส่วนใหญ่อังกฤษ)
    queries = [kw, kw + " reddit", kw + " quora", kw + " review",
               kw + " best", kw + " recommendations"]
    if biz:
        queries += [biz + " reddit", biz + " review"]
    try:
        threads = await growth.social_radar(queries, sites=sites)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ดึงผล SERP ไม่ได้ (ตรวจเครดิต/คีย์ DataForSEO): " + str(e)[:150])
    return {"keyword": kw, "business": biz, "sites": list(sites),
            "threads": threads, "count": len(threads),
            "note": "หน้า Reddit/Quora/Medium ที่ติดหน้า 1 Google สำหรับหัวข้อนี้ · AI อ้างอิงชุมชนพวกนี้บ่อย "
                    "→ ไปตอบให้ 'มีประโยชน์จริง' = ดัน GEO + ยืมความน่าเชื่อถือที่มีอยู่แล้ว · "
                    "ต้องรีวิว+โพสต์เอง (ขาว ไม่สแปม ไม่ auto)"}


# ---- competitor_backlink ----
# import ที่ต้องเพิ่มบนหัว main.py: from app.schemas import BacklinkGapsRequest
#   (เพิ่มชื่อ BacklinkGapsRequest เข้าไปใน import schemas ที่มีอยู่แล้ว — pattern เดียวกับ KeywordReportRequest/PantipRadarRequest)
# วางต่อท้าย main.py ใกล้ ๆ keyword_report/pantip_radar (~บรรทัด 1076)

@app.post("/api/backlink-gaps")
async def backlink_gaps(req: BacklinkGapsRequest, user=Depends(get_current_user)):
    """🔗 Backlink Gap Mining (#10) — ใส่โดเมนคู่แข่ง → หา 'ใครลิงก์หาคู่แข่งหลายเจ้า' = แหล่งที่เราควรไปขอลิงก์ (outreach)
    ตัวเลข/โดเมนจริงจาก DataForSEO Backlinks API · ตัดโดเมนเราเอง+ตัวคู่แข่งเองออกให้ · คนเอาไปติดต่อเอง (white-hat ไม่ซื้อ ไม่สแปม)"""
    from app.connectors import growth
    from app.config import settings as S
    if not (S.dataforseo_login and S.dataforseo_password):
        raise HTTPException(503, "ยังไม่ได้ตั้งคีย์ DataForSEO — ต้องมีเพื่อดึงข้อมูล backlink 'จริง' (Backlinks API เป็นแพ็กเกจแยก)")
    comps = [str(c).strip() for c in (req.competitors or []) if str(c).strip()]
    if not comps:
        raise HTTPException(422, "ใส่โดเมนคู่แข่งอย่างน้อย 1 โดเมนก่อน (เช่น competitor.com)")
    our = (req.domain or "").strip()
    try:
        opportunities = await growth.backlink_gaps(comps, our_domain=our, limit=req.limit or 100)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ขุด backlink gap ไม่ได้ (ตรวจเครดิต/สิทธิ์ Backlinks API ของ DataForSEO): " + str(e)[:150])
    return {"competitors": comps, "domain": our,
            "opportunities": opportunities, "count": len(opportunities),
            "note": "โดเมนที่ลิงก์ให้คู่แข่งหลายเจ้า = โอกาสได้ลิงก์สูงสุด (จัดอันดับตามจำนวนคู่แข่ง→rank) · "
                    "ตัวเลขจริงจาก DataForSEO Backlinks · ไปติดต่อขอลิงก์เอง (white-hat ไม่ซื้อ ไม่สแปม)"}


# ---- content_gap ----
# วางต่อท้าย backend/app/main.py (หลัง endpoint pantip_radar/pantip_reply)
# import ที่ต้องเพิ่ม: เพิ่ม ContentGapRequest เข้าใน 'from app.schemas import (...)' บล็อกบนหัวไฟล์ (บรรทัด ~25)
@app.post("/api/content-gaps")
async def content_gaps(req: ContentGapRequest, user=Depends(get_current_user)):
    """🎯 Content Gap Capture — คีย์ที่ 'คู่แข่งติดหน้า 1-2 แต่เราไม่มี' = ช่องว่างผลิตคอนเทนต์แซงได้
    ดึงคีย์ที่คู่แข่งติดจริง (DataForSEO Labs) ลบคีย์ที่เราติดแล้ว → คืนพร้อมปริมาณค้นหา/ความยาก 'จริง'"""
    from app.connectors import growth
    from app.config import settings as S
    if not (S.dataforseo_login and S.dataforseo_password):
        raise HTTPException(503, "ยังไม่ได้ตั้งคีย์ DataForSEO — ต้องมีเพื่อดึงคีย์ที่ติดอันดับ 'จริง'")
    our = (req.domain or "").strip()
    comps = [c for c in (req.competitors or []) if str(c).strip()]
    if not our:
        raise HTTPException(422, "กรุณาระบุโดเมนเว็บของเราก่อน")
    if not comps:
        raise HTTPException(422, "กรุณาระบุโดเมนคู่แข่งอย่างน้อย 1 ราย")
    try:
        gaps = await growth.content_gaps(our, comps, limit=req.limit or 100)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ดึง Content Gap ไม่ได้ (ตรวจเครดิต/คีย์ DataForSEO): " + str(e)[:150])
    if not gaps:                                    # ว่างจริง → แยก 'เครดิตหมด' ออกจาก 'ไม่มีช่องว่าง' (โปร่งใส)
        from app.connectors import serp
        bal = await serp.account_balance()
        if bal is not None and bal < 0.05:
            raise HTTPException(402, "เครดิต DataForSEO หมด (เหลือ $%.2f) — เติมเงินก่อนใช้งาน" % bal)
    total_vol = sum(g["volume"] for g in gaps if g.get("volume"))
    diffs = [g["difficulty"] for g in gaps if isinstance(g.get("difficulty"), (int, float))]
    summary = {
        "count": len(gaps),
        "total_monthly": total_vol,
        "total_daily": round(total_vol / 30) if total_vol else 0,
        "avg_difficulty": round(sum(diffs) / len(diffs)) if diffs else None,
        "easy": sum(1 for d in diffs if d < 30),
        "medium": sum(1 for d in diffs if 30 <= d < 60),
        "hard": sum(1 for d in diffs if d >= 60),
    }
    return {"domain": our, "competitors": comps, "gaps": gaps, "summary": summary,
            "note": "คีย์ที่คู่แข่งติดหน้า 1-2 (อันดับ ≤20) แต่เรายังไม่ติด · เอาไปผลิตคอนเทนต์แซงได้ · "
                    "ปริมาณค้นหา/ความยาก = DataForSEO Labs (ตัวเลขจริง ตรวจย้อนได้)"}


# ---- featured_snippet ----
# วางต่อท้าย main.py (หลัง endpoint pantip_radar) · import ที่ต้องเพิ่ม: from app.schemas import SnippetSniperRequest (ถ้า main.py import schema แบบ per-class — ดูว่าไฟล์ import KeywordReportRequest ยังไงแล้วเพิ่มชื่อนี้ต่อ)

@app.post("/api/snippet-opportunities")
async def snippet_opportunities(req: SnippetSniperRequest, user=Depends(get_current_user)):
    """🎯 Featured Snippet Sniper — ใส่คีย์ (เดี่ยว/หลายคีย์) → ดู SERP จริงว่ามี Featured Snippet / People-Also-Ask ไหม
    เพื่อ 'ชิง Position 0' · คืนช่องว่าง+เจ้าของ Snippet ปัจจุบัน+คำถาม PAA จริง + คำแนะนำจัดรูปแบบ (ตัวเลขจริง ไม่กุ)"""
    from app.connectors import growth
    from app.config import settings as S
    if not (S.dataforseo_login and S.dataforseo_password):
        raise HTTPException(503, "ยังไม่ได้ตั้งคีย์ DataForSEO — ต้องมีเพื่อดึงผล SERP (Featured Snippet/PAA) 'จริง'")
    # รวมคีย์จาก keyword (เดี่ยว) + keywords (ลิสต์) แล้ว dedupe รักษาลำดับ
    raw = list(req.keywords or [])
    if (req.keyword or "").strip():
        raw.insert(0, req.keyword.strip())
    kws, seen = [], set()
    for k in raw:
        k = str(k).strip()
        if k and k.lower() not in seen:
            seen.add(k.lower())
            kws.append(k)
    if not kws:
        raise HTTPException(422, "ใส่คีย์เวิร์ดอย่างน้อย 1 คำ")
    try:
        opportunities = await growth.snippet_opportunities(kws)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ดึงผล SERP ไม่ได้ (ตรวจเครดิต/คีย์ DataForSEO): " + str(e)[:150])
    return {"keywords": kws, "opportunities": opportunities, "count": len(opportunities),
            "note": "Featured Snippet/People-Also-Ask จาก SERP จริง (DataForSEO) · ชิง Position 0 โดยตอบตรง 40-55 คำ "
                    "ใต้ H2 ที่เป็นคำถาม + ทำ list/table ตอบ PAA · ตัวเลขจริง ตรวจย้อนได้"}


# ---- ai_citation_engine ----
# วางต่อท้าย main.py · ไม่ต้องเพิ่ม import บนหัวไฟล์ (db, HTTPException, Depends, get_current_user,
# _own_project มีอยู่แล้ว · ที่เหลือ import ในฟังก์ชันตามแบบ endpoint อื่น ๆ)

@app.post("/api/projects/{project_id}/ai-citation-audit")
async def project_ai_citation_audit(project_id: int, user=Depends(get_current_user)):
    """#9 · AI-Citation Engine (GEO core) — วัด 'AI แนะนำเราแค่ไหน' (Share of Voice เทียบคู่แข่ง)
    + 'AI/Google ดึงคำตอบจากแหล่งไหนที่เรายังไม่อยู่' (source gaps) → รู้ว่าต้องไปแทรกตรงไหน
    โหลด brand_terms/domain/คำถาม AEO ของโปรเจ็คเอง · ผลเป็นค่าประมาณเชิงสถิติจากการสุ่มถามจริง (no-faking)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import creds
    from app.connectors import growth
    from app.worker.tasks import _brand_terms_of, _project_questions, _available_engines
    engines = _available_engines()
    if not engines:                          # ไม่มีคีย์ AI = ไม่ยิง = ไม่เดาผล (โปร่งใส)
        raise HTTPException(503, "ยังไม่ได้ตั้งคีย์ AI (OpenAI/Gemini/Perplexity/Anthropic) — ต้องมีเพื่อสุ่มถาม AI จริง")
    async with db.session() as s:
        proj = await _own_project(s, project_id, user)      # กันตรวจ/ยิงให้โปรเจ็คคนอื่น (เสียเครดิต AI/SERP จริง)
        domain = proj.domain
        brand_terms = _brand_terms_of(proj)                 # คำแบรนด์ที่ Site Intelligence สกัดไว้ (fallback ชื่อ+โดเมน)
        lang = "English" if str(getattr(proj, "language", "") or "").lower().startswith("en") else "ภาษาไทย"
        # คู่แข่งที่ AI เคยแนะนำในหมวดเรา (สะสมจาก Prompt Sampling) → ใช้เป็นชื่อคู่แข่งที่ต้องนับ
        import json as _json
        comp_raw = getattr(proj, "ai_competitors", "") or ""
        try:
            competitor_terms = [(c.get("name") if isinstance(c, dict) else str(c))
                                for c in (_json.loads(comp_raw) if comp_raw.strip() else [])]
            competitor_terms = [c for c in competitor_terms if c]
        except Exception:  # noqa: BLE001
            competitor_terms = []
        questions = await _project_questions(proj, project_id)   # คำถาม AEO ลูกค้าก่อน → เติมอัตโนมัติ
    if not domain:
        raise HTTPException(422, "โปรเจ็คนี้ยังไม่ได้ตั้งโดเมน")
    if not questions:
        raise HTTPException(422, "ยังไม่มีชุดคำถาม AEO — ตั้งคำถามก่อน หรือรอระบบวิเคราะห์เว็บ")
    dfs = await creds.get_creds(project_id, "dataforseo")   # คีย์ SERP ของลูกค้า (สำหรับหา source gaps · ไม่มีก็ยังได้ SoV)
    try:
        res = await growth.ai_citation_audit(questions, brand_terms, competitor_terms,
                                             domain, creds=dfs or None, language=lang)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
    res["questions_used"] = questions
    res["engines_used"] = engines
    return res



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


@app.put("/api/projects/{project_id}/mode")
async def set_project_mode(project_id: int, req: ProjectModeUpdate, user=Depends(get_current_user)):
    """สลับโหมดเผยแพร่ของโปรเจ็ค: auto (Full-Auto เผยแพร่เอง) | approve (ร่างรออนุมัติก่อน)
    สลับเป็น auto → เผยแพร่ 'ร่างที่ผ่านเกณฑ์คุณภาพ (AEO ถึงเกณฑ์)' ที่ค้างอยู่ให้เลย = เห็นผลทันที"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project, Article
    from app.config import settings as _cfg
    mode = (req.mode or "").strip().lower()
    if mode not in ("auto", "approve"):
        raise HTTPException(422, "mode ต้องเป็น auto | approve")
    thr = int(getattr(_cfg, "min_publish_score", 82) or 82)
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        p.mode = mode
        await s.commit()
        drafts = []
        if mode == "auto":                          # Full-Auto → เผยแพร่ร่างพรีเมียมที่ค้างในคิวให้เลย
            drafts = (await s.execute(
                select(Article.id).where(Article.project_id == project_id,
                                         Article.status == "draft",
                                         Article.aeo_score >= thr))).scalars().all()
        await s.refresh(p)
        result = _proj_dict(p)
    published = 0
    for aid in drafts:
        try:
            from app.worker.tasks import approve_article
            approve_article.delay(aid); published += 1
        except Exception:  # noqa: BLE001
            pass
    result["mode"] = mode
    result["auto_published"] = published
    return result


@app.post("/api/projects/{project_id}/report-link")
async def create_report_link(project_id: int, user=Depends(get_current_user)):
    """สร้าง/ดึงลิงก์รายงานสาธารณะของโปรเจ็ค — ส่งให้ลูกค้าเปิดดูได้โดยไม่ต้องล็อกอิน (read-only)
    คืน token + path รายสัปดาห์/รายเดือน (frontend ต่อ origin เอง)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        if not (getattr(p, "report_token", "") or "").strip():
            p.report_token = secrets.token_urlsafe(16)
            await s.commit()
        token = p.report_token
    return {"token": token,
            "week": "/api/report/%s?period=week" % token,
            "month": "/api/report/%s?period=month" % token}


@app.get("/api/report/{token}")
async def public_report(token: str, period: str = "week"):
    """หน้ารายงานสาธารณะ (ไม่ต้องล็อกอิน) — เปิดจากลิงก์ที่แอดมินสร้างให้ลูกค้า · read-only · noindex"""
    from fastapi.responses import HTMLResponse
    from datetime import datetime, timezone, timedelta
    from app.db.models import Project
    from app import public as _public
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    token = (token or "").strip()
    if len(token) < 8:
        raise HTTPException(404, "ไม่พบรายงาน")
    async with db.session() as s:
        pid = (await s.execute(select(Project.id).where(Project.report_token == token))).scalar_one_or_none()
    if not pid:
        raise HTTPException(404, "ไม่พบรายงาน (ลิงก์ไม่ถูกต้องหรือถูกยกเลิก)")
    days = 30 if str(period).lower().startswith("m") else 7
    data = await _public.report_data(pid, days)
    if not data:
        raise HTTPException(404, "ยังไม่มีข้อมูลรายงาน / no report data yet")
    en = str(getattr(data["proj"], "language", "") or "").lower().startswith("en")   # ภาษาโปรเจ็ค → รายงานสองภาษา
    now7 = datetime.now(timezone.utc) + timedelta(hours=7)
    if en:
        label = "Monthly (last 30 days)" if days == 30 else "Weekly (last 7 days)"
        gen = now7.strftime("%d %b %Y, %H:%M")
    else:
        label = "รายเดือน (30 วันล่าสุด)" if days == 30 else "รายสัปดาห์ (7 วันล่าสุด)"
        gen = now7.strftime("%d/%m/%Y %H:%M น.")
    html = _public.render_report_page(data, label, gen)
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=300", "X-Robots-Tag": "noindex"})


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


@app.put("/api/projects/{project_id}")
async def update_project(project_id: int, req: ProjectUpdate, user=Depends(get_current_user)):
    """✏️ แก้ชื่อ/โดเมน (ลิงก์) ของโปรเจ็ค — เจ้าของเท่านั้น · ไม่กระทบบทความที่ผลิตไว้ (โดเมนใหม่มีผลกับการวัดอันดับรอบถัดไป)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    name = (req.name or "").strip()
    domain = (req.domain or "").strip().lower().replace("https://", "").replace("http://", "").strip("/").split("/")[0]
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        if name:
            p.name = name[:200]
        if domain:
            p.domain = domain[:255]
        if req.business_context is not None:      # กรอกบรีฟเองได้ (อุดกรณี crawler อ่านเว็บไม่ได้)
            p.business_context = (req.business_context or "").strip()
        if req.brand_terms is not None:
            p.brand_terms = (req.brand_terms or "").strip()
        if req.lead_line_to is not None:
            p.lead_line_to = (req.lead_line_to or "").strip()[:80]
        if req.lead_email is not None:
            p.lead_email = (req.lead_email or "").strip()[:255]
        await s.commit()
        return {"ok": True, "id": p.id, "name": p.name, "domain": p.domain}


@app.get("/api/projects/{project_id}/leads")
async def project_leads(project_id: int, user=Depends(get_current_user)):
    """📥 ลีดของแคมเปญ/โปรเจ็คนี้ (จากฟอร์มดักลูกค้าท้ายบทความ + สื่อแจกฟรี) — โผล่ในระบบ แยกตามลูกค้า
    เอาไว้ให้เอเจนซี/ลูกค้าตามปิดการขาย (ตัวเลขจริงจากผู้กรอกเอง ไม่กุ)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Lead
    async with db.session() as s:
        await _own_project(s, project_id, user)
        rows = (await s.execute(select(Lead).where(Lead.project_id == project_id)
                                .order_by(Lead.created_at.desc()).limit(500))).scalars().all()
        leads = [{"id": r.id, "name": r.name or "", "phone": getattr(r, "phone", "") or "",
                  "email": r.email or "", "message": getattr(r, "message", "") or "",
                  "source": r.source or "",
                  "created_at": r.created_at.isoformat() if r.created_at else ""} for r in rows]
    return {"leads": leads, "count": len(leads)}


@app.put("/api/projects/{project_id}/active")
async def set_project_active(project_id: int, req: ProjectActiveUpdate, user=Depends(get_current_user)):
    """⏸/▶️ พัก/เปิดใช้โปรเจ็ค — พัก = หยุดผลิต/วัดอันดับ/citation อัตโนมัติ (ข้อมูลเดิมอยู่ครบ) · เจ้าของเท่านั้น"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        p.active = bool(req.active)
        await s.commit()
        return {"ok": True, "id": p.id, "active": p.active}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: int, user=Depends(get_current_user)):
    """ลบโปรเจ็คถาวร + ข้อมูลลูกทั้งหมด (บทความ/อันดับ/citation/ช่องทาง/คีย์/ล็อก) — เจ้าของเท่านั้น"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from sqlalchemy import delete as sa_delete
    from app.db.models import (Project, Article, RankSnapshot, CitationSnapshot, CitationExample,
                               DistributionChannel, ProjectCredential, DistributionEvent, LeadMagnet, Lead)
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        name = p.name
        # ลบลูกก่อน (DistributionEvent อ้าง article_id → ก่อน Article · Lead อ้าง magnet_id → ก่อน LeadMagnet)
        for model in (DistributionEvent, Lead, RankSnapshot, CitationSnapshot, CitationExample,
                      DistributionChannel, ProjectCredential, LeadMagnet, Article):
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
                          "words": a.words, "url": a.url,
                          "fmt": getattr(a, "fmt", ""), "aeo_score": getattr(a, "aeo_score", 0)} for a in rows]}


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


@app.post("/api/admin/create-user")
async def admin_create_user(req: AdminCreateUser, user=Depends(get_current_user)):
    """แอดมินสร้างบัญชีเข้าใช้ให้ลูกค้า/ทีม (อีเมล+รหัส) โดยตรง — แทนการสมัครเองที่ปิดไว้
    ตั้งรหัสให้เลย แล้วส่ง 'อีเมล+รหัส' ให้ลูกค้าล็อกอิน · as_member = ผูกเป็นสมาชิกทีมของแอดมิน"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import usage
    if (await usage.user_plan(user["id"])) != "admin":
        raise HTTPException(403, "เฉพาะแอดมินเท่านั้นที่สร้างบัญชีได้ (ตั้งอีเมลคุณใน ADMIN_EMAILS)")
    email = (req.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(422, "อีเมลไม่ถูกต้อง")
    if len((req.password or "").strip()) < 8:
        raise HTTPException(422, "รหัสผ่านอย่างน้อย 8 ตัวอักษร")
    name = (req.name or email.split("@")[0]).strip()
    from app.db.models import User, TeamMember
    async with db.session() as s:
        exists = (await s.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if exists:
            raise HTTPException(409, "อีเมลนี้มีบัญชีแล้ว")
        u = User(email=email, name=name, password_hash=security.hash_password(req.password))
        s.add(u); await s.commit(); await s.refresh(u)
        uid = u.id
        if req.as_member and uid != user["id"]:
            role = req.role if req.role in ("viewer", "editor", "admin") else "viewer"
            dup = (await s.execute(select(TeamMember).where(
                TeamMember.owner_id == user["id"], TeamMember.email == email))).scalars().first()
            if not dup:
                s.add(TeamMember(owner_id=user["id"], email=email, role=role,
                                 status="active", member_user_id=uid))
                await s.commit()
    from app import team
    await team.link_invites(uid, email)
    return {"ok": True, "email": email, "name": name, "as_member": bool(req.as_member)}


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


@app.get("/api/projects/{project_id}/onboarding")
async def project_onboarding(project_id: int, user=Depends(get_current_user)):
    """เช็กลิสต์เซ็ตอัพ 'ต่อลูกค้า 1 ราย' (ประกอบการขาย/ส่งมอบ) — รับงานลูกค้าใหม่แล้วเห็นทันที
    ว่าต้องเสียบอะไรให้ครบก่อนระบบดันอันดับอัตโนมัติ · ไม่คืนค่าลับ (เฉพาะ done/scope/why)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import creds
    from app.connectors import indexing
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        name, domain = p.name, p.domain
        pub = p.publish_mode or "managed"
        has_ctx = bool((p.business_context or "").strip())
        has_brand = bool((p.brand_terms or "").strip())
        has_cta = bool((p.cta_json or "").strip())
    st = await creds.status(project_id)
    gsc_c = st.get("gsc", {})
    serp_c = st.get("dataforseo", {})
    wp_c = st.get("wordpress", {})
    publish_done = (pub == "managed") or (pub == "wordpress" and bool(wp_c.get("connected")))
    cite_ready = bool(settings.openai_api_key or settings.gemini_api_key
                      or settings.perplexity_api_key or settings.anthropic_api_key)
    items = [
        {"key": "brief", "label": "ข้อมูลธุรกิจ (บริบท/บริการ)", "scope": "project", "required": True,
         "why": "ป้อนเครื่องยนต์คอนเทนต์ให้เขียนตรงธุรกิจลูกค้า", "done": has_ctx, "action": "project_edit"},
        {"key": "gsc", "label": "Google Search Console (อันดับจริง)", "scope": "project", "required": True,
         "why": "ดึงคลิก/อันดับจริงจาก Google → ป้อน Striking-Distance Sniper",
         "done": bool(gsc_c.get("connected")), "source": gsc_c.get("source", "none"), "action": "gsc_connect"},
        {"key": "serp", "label": "SERP API (ตรวจอันดับรายวัน)", "scope": "project", "required": True,
         "why": "ตรวจอันดับคีย์เวิร์ดรายวันของโดเมนลูกค้า",
         "done": bool(serp_c.get("connected")), "source": serp_c.get("source", "none"), "action": "settings"},
        {"key": "publish", "label": "ปลายทางเผยแพร่บทความ", "scope": "project", "required": True,
         "why": "โพสต์บทความอัตโนมัติ (โฮสต์ให้ หรือส่งเข้า WordPress ลูกค้า)",
         "done": bool(publish_done), "detail": pub, "action": "settings"},
        {"key": "brand", "label": "คำแบรนด์ (วัด AI Citation)", "scope": "project", "required": True,
         "why": "ใช้ตรวจว่า ChatGPT/Gemini เอ่ยถึงแบรนด์ลูกค้าไหม — จุดขาย AEO/GEO",
         "done": has_brand, "action": "project_edit"},
        {"key": "cta", "label": "กล่องดักลีดท้ายบทความ (CTA)", "scope": "project", "required": False,
         "why": "เปลี่ยนคนอ่านเป็นลีด — เนียนขายบริการลูกค้า", "done": has_cta, "action": "project_edit"},
        {"key": "indexing", "label": "Google Indexing API (ติด index เร็ว)", "scope": "platform", "required": False,
         "why": "แจ้ง Google เก็บหน้าใหม่ใน 'ชั่วโมง' — ตั้งครั้งเดียว ใช้ได้ทุกลูกค้า",
         "done": indexing.enabled(), "action": "settings"},
        {"key": "citation", "label": "คีย์ AI (วัด AEO/GEO)", "scope": "platform", "required": False,
         "why": "ยิงถาม ChatGPT/Gemini/Perplexity วัด Share of Voice — ตั้งครั้งเดียว",
         "done": cite_ready, "action": "settings"},
    ]
    core = [i for i in items if i["scope"] == "project" and i["required"]]
    done = sum(1 for i in core if i["done"])
    pct = round(100 * done / len(core)) if core else 0
    return {"project": {"id": project_id, "name": name, "domain": domain, "publish_mode": pub},
            "ready_pct": pct, "done": done, "total": len(core), "items": items}


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


@app.post("/api/projects/{project_id}/rank/measure-all")
async def project_measure_all(project_id: int, user=Depends(get_current_user)):
    """วัดอันดับ Google 'เดี๋ยวนี้' — 'ทุกคีย์ที่ติดตาม' (คีย์ลูกค้าใน topic_plan + หัวข้อบทความที่เผยแพร่)
    ตรงกับที่หน้ารายงานโชว์ · สูงสุด = แพ็กของโปรเจ็ค · เข้าคิวเบื้องหลัง (ต้องต่อ DataForSEO)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project, Article
    from app.worker.tasks import _tracked_keywords, _pack_cap
    async with db.session() as s:
        p = await s.get(Project, project_id)
        if not p or p.user_id != user["id"]:
            raise HTTPException(404, "ไม่พบโปรเจ็ค")
        domain = p.domain
        if not domain:
            raise HTTPException(422, "โปรเจ็คนี้ยังไม่ได้ตั้งโดเมน")
        titles = (await s.execute(
            select(Article.title).where(Article.project_id == project_id,
                                        Article.status == "published"))).scalars().all()
        kws = _tracked_keywords(p, titles, _pack_cap(p))   # คีย์ลูกค้า (topic_plan) + หัวข้อบทความ · สูงสุด=แพ็ก
        pname = p.name
    if not kws:
        return {"queued": 0, "note": "ยังไม่มีคีย์เวิร์ดให้วัด — เพิ่มคีย์เวิร์ดที่หน้าจัดการโปรเจ็คก่อน"}
    try:
        from app.worker.tasks import measure_rank
        for kw in kws:
            measure_rank.delay(kw, domain, project_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ต่อคิวไม่ได้ (worker/redis พร้อมไหม): " + str(e))
    return {"queued": len(kws), "project": pname}


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
    from app.db.models import RankSnapshot, Article
    from app import public as _public
    async with db.session() as s:
        proj = await _read_project(s, project_id, user)
        plan_raw = getattr(proj, "topic_plan", "") or ""
        rows = (await s.execute(
            select(RankSnapshot).where(RankSnapshot.project_id == project_id)
            .order_by(RankSnapshot.checked_at))).scalars().all()
        arts = (await s.execute(select(Article.title, Article.status)
                .where(Article.project_id == project_id))).all()
    status_map = _public.article_status_map(arts)   # หัวข้อบทความ(=คีย์) → สถานะ (published/draft/…)

    latest: dict[str, dict] = {}          # อันดับล่าสุดต่อคีย์เวิร์ด (rows เรียง asc → ตัวหลังทับ = ใหม่สุด)
    series: dict[str, list] = {}          # keyword → ลำดับอันดับตามเวลา (ไว้คิด best/prev)
    day_page1: dict[str, dict] = {}       # day → {keyword: on_page1} สำหรับแนวโน้มหน้า 1
    for r in rows:
        latest[r.keyword] = {"keyword": r.keyword, "rank": r.rank,
                             "on_page1": bool(r.on_page1),
                             "checked_at": r.checked_at.isoformat() if r.checked_at else ""}
        series.setdefault(r.keyword, []).append(r.rank)
        d = r.checked_at.date().isoformat() if r.checked_at else ""
        if d:
            day_page1.setdefault(d, {})[r.keyword] = bool(r.on_page1)
    for kw, info in latest.items():        # อันดับดีสุดที่เคยทำได้ + อันดับก่อนหน้า (ไว้โชว์การเคลื่อนไหว ▲▼)
        seq = series.get(kw, [])
        rr = [x for x in seq if x is not None]
        info["best_rank"] = min(rr) if rr else None
        info["prev_rank"] = seq[-2] if len(seq) >= 2 else None

    kws = sorted(latest.values(),
                 key=lambda k: (k["rank"] is None, k["rank"] if k["rank"] is not None else 999))
    # แนบระดับความยาก (Easy-Win Radar) จาก topic_plan → ให้รายงานโชว์ป้าย ง่าย/ปานกลาง/ยาก
    import json as _json
    diff_map: dict[str, dict] = {}
    try:
        for it in (_json.loads(plan_raw) if plan_raw.strip() else []):
            if isinstance(it, dict) and it.get("topic") and it.get("difficulty") is not None:
                diff_map[str(it["topic"]).strip().lower()] = {
                    "difficulty": it.get("difficulty"), "difficulty_label": it.get("difficulty_label") or ""}
    except Exception:  # noqa: BLE001
        diff_map = {}
    for k in kws:
        d = diff_map.get(str(k.get("keyword") or "").strip().lower())
        if d:
            k["difficulty"] = d["difficulty"]
            k["difficulty_label"] = d["difficulty_label"]
    # แสดง 'คีย์ที่กำลังติดตาม' ทุกตัวจาก topic_plan แม้ยังไม่ถูกวัดอันดับ
    # (ลูกค้าซื้อสูงสุด 50 คีย์ → ต้องเห็นครบทันทีที่เพิ่ม ไม่ต้องรอมีบทความ/วัดอันดับก่อน)
    have_kw = {str(k.get("keyword") or "").strip().lower() for k in kws}
    try:
        for it in (_json.loads(plan_raw) if plan_raw.strip() else []):
            topic = ((it.get("topic") if isinstance(it, dict) else str(it)) or "").strip()
            if not topic or topic.lower() in have_kw:
                continue
            have_kw.add(topic.lower())
            entry = {"keyword": topic, "rank": None, "on_page1": False,
                     "best_rank": None, "prev_rank": None, "pending": True}
            if isinstance(it, dict) and it.get("difficulty") is not None:
                entry["difficulty"] = it.get("difficulty")
                entry["difficulty_label"] = it.get("difficulty_label") or ""
            kws.append(entry)
    except Exception:  # noqa: BLE001
        pass
    # 🔎 สถานะไปป์ไลน์ต่อคีย์ — ให้เห็นว่า "คีย์ที่ยังไม่ติด" ระบบทำถึงไหนแล้ว (เขียน/รอคิว/เผยแพร่)
    pipeline = {"published": 0, "scheduled": 0, "drafting": 0, "queued": 0}
    for k in kws:
        stage, label = _public.keyword_stage(
            status_map.get(str(k.get("keyword") or "").strip().lower(), ""))
        k["stage"] = stage
        k["stage_label"] = label
        pipeline[stage] = pipeline.get(stage, 0) + 1
    ranked = [k["rank"] for k in kws if k["rank"] is not None]
    page1 = sum(1 for k in kws if k["on_page1"])
    top3 = sum(1 for k in kws if k["rank"] is not None and k["rank"] <= 3)
    avg_position = round(sum(ranked) / len(ranked), 1) if ranked else None
    trend = [{"date": d, "page1": sum(1 for v in m.values() if v)}
             for d, m in sorted(day_page1.items())]
    return {
        "keywords_tracked": len(latest),
        "keywords_total": len(have_kw),          # คีย์ที่ติดตามทั้งหมด (วัดแล้ว + รอวัด) — ตรงกับที่ลูกค้าเพิ่ม
        "page1": page1, "top3": top3, "avg_position": avg_position,
        "pipeline": pipeline,                    # ระบบทำถึงไหน: เผยแพร่แล้ว/ตั้งเวลา/กำลังเขียน/รอคิว
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


@app.post("/api/projects/{project_id}/site-health/fix")
async def site_health_fix(project_id: int, user=Depends(get_current_user)):
    """🔧 ซ่อมปัจจัยอันดับที่แดง 'เดี๋ยวนี้' — เติม Schema ที่ขาด (เร็ว/ฟรี) + รีเฟรชลิงก์ภายในทั้งโปรเจ็ค
    (ช่วยหน้ากำพร้าให้มีลิงก์เข้าด้วย) · ทำงานกับบทความที่เผยแพร่แล้ว ไม่เขียนใหม่ทั้งบทความ"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    async with db.session() as s:
        await _own_project(s, project_id, user)
    from app.db.models import Article
    from app.worker.tasks import _backfill_schema, _apply_internal_links
    schema_note = await _backfill_schema(project_id, 300)         # เติม schema ทุกหน้าที่ขาด
    links = 0
    async with db.session() as s:
        arts = (await s.execute(
            select(Article.id, Article.title, Article.html).where(
                Article.project_id == project_id, Article.status == "published"))).all()
    for aid, title, html in arts:                                # รีเฟรชลิงก์ภายในต่อหน้า (regex ไม่ใช้ LLM = เร็ว)
        try:
            nh = await _apply_internal_links(project_id, title or "", html or "")
        except Exception:  # noqa: BLE001
            nh = html
        if nh and nh != html:
            async with db.session() as s:
                a = await s.get(Article, aid)
                if a:
                    a.html = nh
                    await s.commit()
                    links += 1
    import re as _re
    m = _re.search(r"(\d+)", schema_note or "")
    return {"schema_fixed": int(m.group(1)) if m else 0,
            "links_refreshed": links, "articles": len(arts),
            "note": "เติม schema + รีเฟรชลิงก์ภายในแล้ว — รอ ~1 นาทีแล้วรีเฟรชรายงานดูค่าที่ดีขึ้น"}


@app.get("/api/projects/{project_id}/cta")
async def get_cta(project_id: int, user=Depends(get_current_user)):
    """กล่องดักลูกค้า (CTA) ท้ายบทความของโปรเจ็คนี้"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import json as _json
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        raw = getattr(p, "cta_json", "") or ""
    try:
        c = _json.loads(raw) if raw.strip() else {}
    except Exception:  # noqa: BLE001
        c = {}
    return {"enabled": bool(c.get("enabled")), "headline": c.get("headline", ""), "text": c.get("text", ""),
            "button": c.get("button", "ปรึกษาฟรี"), "url": c.get("url", "")}


@app.put("/api/projects/{project_id}/cta")
async def set_cta(project_id: int, req: CtaUpdate, user=Depends(get_current_user)):
    """ตั้งกล่องดักลูกค้า (CTA) ท้ายบทความ — เนียนขายบริการ/พาไปเก็บลีด · มีผลทุกบทความของโปรเจ็คทันที"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import json as _json
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        p.cta_json = _json.dumps({"enabled": bool(req.enabled),
                                  "headline": (req.headline or "")[:160], "text": (req.text or "")[:400],
                                  "button": (req.button or "ปรึกษาฟรี")[:40], "url": (req.url or "")[:500]},
                                 ensure_ascii=False)
        await s.commit()
    return {"saved": True}


@app.post("/api/projects/{project_id}/posts")
async def create_post(project_id: int, req: PostCreate, user=Depends(get_current_user)):
    """✍️ แอดมินเขียนโพสต์เอง (บทความ/วิดีโอ) → เผยแพร่ขึ้นบล็อกแบรนด์
    ใช้ระบบเดิม (slug/url/schema/ลิงก์ภายใน) → SEO/AEO เต็มเหมือนบทความ AI · เจ้าของโปรเจ็คเท่านั้น"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import html as _html, re as _re
    from app.db.models import Article
    from app import urls
    from app.worker.tasks import _build_schema, _apply_internal_links, _aeo_of
    title = (req.title or "").strip()
    if not title:
        raise HTTPException(400, "ต้องมีหัวข้อ")
    c = (req.content or "").strip()
    if c and "<" not in c:                                        # ข้อความธรรมดา → ห่อเป็นย่อหน้า
        c = "".join("<p>%s</p>" % _html.escape(x.strip()) for x in _re.split(r"\n{2,}|\n", c) if x.strip())
    ytm = _re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", req.video_url or "")
    embed = (('<div style="position:relative;padding-bottom:56.25%%;height:0;margin:0 0 20px">'
              '<iframe src="https://www.youtube.com/embed/%s" style="position:absolute;inset:0;width:100%%;height:100%%;border:0" '
              'loading="lazy" allowfullscreen title="video"></iframe></div>') % ytm.group(1)) if ytm else ""
    status = "published" if (req.status or "published") == "published" else "draft"
    from types import SimpleNamespace
    # 1) ตรวจสิทธิ์ + snapshot ค่าโปรเจ็ค (กัน detached/nested-session)
    async with db.session() as s:
        proj = await _own_project(s, project_id, user)
        p = SimpleNamespace(name=proj.name, domain=proj.domain,
                            slug=(proj.slug or urls.project_slug_from_domain(proj.domain or proj.name)),
                            custom_domain=getattr(proj, "custom_domain", "") or "",
                            publish_mode=getattr(proj, "publish_mode", "managed") or "managed")
    brand = (p.name or p.domain or "").strip()
    # 2) ลิงก์ภายใน (เปิด session ของตัวเอง — เรียกนอก block กัน nested)
    html_body = embed + (c or "<p></p>")
    html_body = await _apply_internal_links(project_id, title, html_body)
    plain = _re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", html_body)).strip()
    # 3) สร้าง + จัดการ slug/url/schema/aeo
    async with db.session() as s:
        art = Article(project_id=project_id, title=title, html=html_body,
                      description=plain[:300], cover_url=(req.cover_url or "").strip(),
                      fmt="โพสต์", words=len(plain.split()), status=status)
        s.add(art); await s.commit(); await s.refresh(art)
        art.slug = urls.article_slug(title, art.id)
        if status == "published" and p.publish_mode == "managed":
            art.url = urls.public_url_for(p, art)
        art.schema_json = _build_schema(art, brand)                           # JSON-LD ครบ
        art.aeo_score = _aeo_of(art.html, title, (art.description or "")[:155], art.schema_json, art.cover_url or "")
        await s.commit()
        aid, aurl, aslug = art.id, art.url, art.slug
    if status == "published" and aurl:                            # แจ้ง IndexNow (crash-safe)
        try:
            from app.connectors import publish as _pub
            from urllib.parse import urlparse as _up
            if _up(aurl).hostname:
                await _pub.indexnow_submit(aurl)
        except Exception:  # noqa: BLE001
            pass
    return {"article_id": aid, "url": aurl, "slug": aslug, "status": status}


@app.get("/api/projects/{project_id}/citation/examples")
async def project_citation_examples(project_id: int, user=Depends(get_current_user)):
    """หลักฐาน AEO — ตัวอย่างจริงที่ 'ถาม AI แล้ว AI ตอบโดยอ้างอิงแบรนด์/เว็บเรา' (คำถาม + เอนจิน + snippet)
    เก็บสะสมจากรอบสุ่มถามจริง → ลูกค้าเห็นว่าติด AEO จริง ตรวจสอบย้อนได้"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import CitationExample
    async with db.session() as s:
        await _read_project(s, project_id, user)
        rows = (await s.execute(
            select(CitationExample).where(CitationExample.project_id == project_id)
            .order_by(CitationExample.id.desc()).limit(12))).scalars().all()
    return {"examples": [{"engine": r.engine, "question": r.question, "snippet": r.snippet,
                          "at": r.sampled_at.isoformat() if r.sampled_at else ""} for r in rows],
            "count": len(rows)}


@app.post("/api/projects/{project_id}/backlinks")
async def project_backlinks(project_id: int, user=Depends(get_current_user)):
    """Backlink 'จริง' ของเว็บ (DataForSEO Backlinks API) — ตามคำขอ (กดปุ่ม) เพื่อคุมค่าใช้จ่าย
    ⚠️ Backlinks เป็นผลิตภัณฑ์แยกของ DataForSEO คิดเครดิตต่างหาก · crash-safe"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.config import settings
    from app.connectors import serp
    async with db.session() as s:
        p = await _read_project(s, project_id, user)
        domain = p.domain
    if not (settings.dataforseo_login and settings.dataforseo_password):
        return {"available": False, "note": "ยังไม่ได้ตั้งคีย์ DataForSEO — ตั้งที่ ⚙️ การตั้งค่า"}
    data = await serp.backlinks_summary(domain)
    if not data or data.get("error"):
        reason = (data or {}).get("error") or "ไม่ทราบสาเหตุ"
        return {"available": False,
                "note": "ดึง Backlink ไม่ได้: " + reason +
                        " · หมายเหตุ: Backlinks API ต้องสมัคร/เปิดสิทธิ์แยกในบัญชี DataForSEO"}
    return {"available": True, "domain": domain, "data": data}


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
        p = await _read_project(s, project_id, user)
        comp_raw = getattr(p, "ai_competitors", "") or ""
        rows = (await s.execute(
            select(CitationSnapshot).where(CitationSnapshot.project_id == project_id)
            .order_by(CitationSnapshot.sampled_at))).scalars().all()
    import json as _json
    try:
        competitors = _json.loads(comp_raw) if comp_raw.strip() else []
    except Exception:  # noqa: BLE001
        competitors = []

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
        "competitors": competitors,           # คู่แข่งที่ AI แนะนำในหมวดเรา (ล่าสุด)
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


@app.get("/api/projects/{project_id}/outreach")
async def outreach_list(project_id: int, user=Depends(get_current_user)):
    """🔗 คิว backlink/outreach ของโปรเจ็ค (todo ก่อน, authority สูงก่อน) — auto เก็บรายสัปดาห์ + คนตามสถานะ"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import OutreachTask
    async with db.session() as s:
        await _own_project(s, project_id, user)
        rows = (await s.execute(select(OutreachTask).where(OutreachTask.project_id == project_id)
                .order_by(OutreachTask.status.asc(), OutreachTask.authority.desc()).limit(500))).scalars().all()
        items = [{"id": r.id, "source_domain": r.source_domain, "kind": r.kind, "reason": r.reason,
                  "authority": r.authority, "status": r.status, "note": r.note or ""} for r in rows]
    counts = {}
    for it in items:
        counts[it["status"]] = counts.get(it["status"], 0) + 1
    return {"items": items, "count": len(items), "counts": counts}


@app.put("/api/outreach/{task_id}")
async def outreach_update(task_id: int, req: OutreachUpdate, user=Depends(get_current_user)):
    """อัปเดตสถานะ/โน้ต งาน outreach (todo/contacted/won/skip) — เจ้าของโปรเจ็คเท่านั้น"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import OutreachTask
    async with db.session() as s:
        t = await s.get(OutreachTask, task_id)
        if not t:
            raise HTTPException(404, "ไม่พบงาน")
        await _own_project(s, t.project_id, user)
        if req.status in ("todo", "contacted", "won", "skip"):
            t.status = req.status
        if req.note is not None:
            t.note = (req.note or "")[:1000]
        await s.commit()
    return {"ok": True}


@app.post("/api/projects/{project_id}/outreach/scan")
async def outreach_scan(project_id: int, user=Depends(get_current_user)):
    """สแกนหาโอกาส backlink เพิ่มทันที (Competitor Gap จริง) → เข้าคิว · คนไปติดต่อเอง (white-hat)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.config import settings as S
    if not (S.dataforseo_login and S.dataforseo_password):
        raise HTTPException(503, "ต้องตั้งคีย์ DataForSEO (Backlinks API) ก่อนถึงดึงข้อมูล backlink จริงได้")
    from app.db.models import OutreachTask
    from app.connectors import growth
    from app.worker.tasks import _parse_competitors
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        domain, comp_raw = p.domain, getattr(p, "ai_competitors", "") or ""
    comps = _parse_competitors(comp_raw)
    if not comps:
        raise HTTPException(422, "ยังไม่ได้ตั้งโดเมนคู่แข่งของโปรเจ็คนี้ก่อน")
    try:
        opps = await growth.backlink_gaps(comps, our_domain=domain or "", limit=30)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ดึง backlink gap ไม่ได้ (เช็กเครดิต/สิทธิ์ Backlinks API): " + str(e)[:150])
    added = 0
    async with db.session() as s:
        existing = set((await s.execute(select(OutreachTask.source_domain)
                        .where(OutreachTask.project_id == project_id))).scalars().all())
        for o in opps[:15]:
            dom = (o.get("domain") or "").strip().lower()
            if not dom or dom in existing:
                continue
            hit = ", ".join((o.get("competitors") or [])[:4])
            s.add(OutreachTask(project_id=project_id, source_domain=dom, kind="competitor-gap",
                               reason=("ลิงก์ให้คู่แข่ง %d เจ้า: %s" % (o.get("competitors_count") or 0, hit))[:400],
                               authority=int(o.get("backlinks") or 0), status="todo"))
            existing.add(dom); added += 1
        await s.commit()
    return {"ok": True, "added": added}


@app.post("/api/projects/{project_id}/backlink-opportunities")
async def backlink_opportunities(project_id: int, user=Depends(get_current_user)):
    """หาโอกาสได้แบ็กลิงก์ white-hat (mention/resource/guest) จาก SERP จริง — คนเอาไปติดต่อเอง (ไม่ซื้อ ไม่สแปม)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project, Article
    from app.connectors import discovery
    import json as _json
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        name, domain = p.name, p.domain
        lang = "English" if str(p.language).lower().startswith("en") else "ภาษาไทย"
        brand_terms = [t.strip() for t in (getattr(p, "brand_terms", "") or "").split(",") if t.strip()]
        plan_raw = getattr(p, "topic_plan", "") or ""
    # คีย์สำหรับค้นโอกาส = ตัวแทน 'แต่ละคลัสเตอร์' ใน topic_plan (ครอบหลายกลุ่ม ไม่ใช่คีย์เดียว)
    reps, seen_cl = [], set()
    try:
        for it in (_json.loads(plan_raw) if plan_raw.strip() else []):
            topic = ((it.get("topic") if isinstance(it, dict) else str(it)) or "").strip()
            if not topic:
                continue
            cl = ((it.get("cluster") if isinstance(it, dict) else "") or "").strip().lower()
            if cl and cl in seen_cl:
                continue
            if cl:
                seen_cl.add(cl)
            reps.append(topic)
    except Exception:  # noqa: BLE001
        reps = []
    kws = reps[:3] or [name]
    try:
        return await discovery.find_link_opportunities(name, domain, brand_terms, kws, lang)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "หาโอกาสแบ็กลิงก์ไม่ได้ (ตรวจคีย์ SERP/DataForSEO): " + str(e)[:150])


@app.post("/api/projects/{project_id}/backlink-outreach")
async def backlink_outreach(project_id: int, req: BacklinkOutreachRequest, user=Depends(get_current_user)):
    """ร่างข้อความติดต่อขอแบ็กลิงก์ (คนเอาไปตรวจ+ส่งเอง · ไม่ auto-ยิง = white-hat)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Project, LeadMagnet
    from app.connectors import discovery
    from app.config import settings
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        brand, domain = p.name, p.domain
        lang = "English" if str(p.language).lower().startswith("en") else "ภาษาไทย"
        # ชูโรงด้วย 'สื่อฟรี' ล่าสุดที่พร้อม (คอร์ส/คู่มือมาก่อน) → outreach แบบเสนอของมีค่า
        mag = (await s.execute(select(LeadMagnet).where(LeadMagnet.project_id == project_id)
               .order_by(LeadMagnet.id.desc()))).scalars().all()
    res_title, res_url = "", ""
    for m in mag:
        if not (m.content_html or "").strip():
            continue
        if m.kind in ("course", "guide") or not res_title:   # คอร์ส/คู่มือมาก่อน; ไม่งั้นใช้ชิ้นล่าสุดที่มีเนื้อหา
            res_title = m.title or ""
            base = (settings.app_base_url or "").rstrip("/")
            res_url = "%s/api/lead/%s" % (base, m.token) if (base and m.token) else ""
            if m.kind in ("course", "guide"):
                break
    try:
        return await discovery.draft_outreach(req.url, req.title, req.kind, brand, domain, lang,
                                              res_title, res_url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, "ร่างข้อความไม่ได้ (ตรวจคีย์ LLM): " + str(e)[:150])


@app.post("/api/projects/{project_id}/lead-magnets")
async def create_lead_magnet(project_id: int, req: LeadMagnetCreate, user=Depends(get_current_user)):
    """สร้างสื่อแจกฟรี (คอร์ส/คู่มือ/เช็คลิสต์/เทมเพลต) — สร้างเบื้องหลัง (เขียน + ใส่รูป) กัน HTTP timeout"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import LeadMagnet
    topic = (req.topic or "").strip()
    if not topic:
        raise HTTPException(422, "กรุณาระบุหัวข้อสื่อ")
    kind = req.kind if req.kind in ("course", "guide", "checklist", "template") else "guide"
    lang = (req.lang or "").strip().lower()
    async with db.session() as s:
        p = await _own_project(s, project_id, user)
        proj_lang = "en" if str(p.language).lower().startswith("en") else "th"
        langs = ["th", "en"] if lang == "both" else ([lang] if lang in ("th", "en") else [proj_lang])
        created = []
        for lc in langs:                              # lang=both → สร้างทั้งไทย+อังกฤษ (2 ชิ้น)
            m = LeadMagnet(project_id=project_id, kind=kind, language=lc, title=topic[:280],
                           description="", teaser_html="", content_html="", stage="⏳ อยู่ในคิว…",
                           token=secrets.token_urlsafe(12), require_share=bool(req.require_share))
            s.add(m); await s.commit(); await s.refresh(m)
            created.append({"id": m.id, "token": m.token, "language": lc, "path": "/api/lead/%s" % m.token})
    building = True
    try:                                              # ⚡ สร้างเบื้องหลัง: เนื้อหา (Fable 5) + รูปปกดึงดูด + รูปในเนื้อ
        from app.worker.tasks import build_lead_magnet
        for c in created:
            build_lead_magnet.delay(c["id"], topic)
    except Exception:  # noqa: BLE001
        building = False
    return {"created": created, "count": len(created), "building": building,
            "kind": kind, "title": topic[:280]}


@app.get("/api/projects/{project_id}/lead-magnets")
async def list_lead_magnets(project_id: int, user=Depends(get_current_user)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import LeadMagnet
    async with db.session() as s:
        await _own_project(s, project_id, user)
        rows = (await s.execute(select(LeadMagnet).where(LeadMagnet.project_id == project_id)
                .order_by(LeadMagnet.id.desc()))).scalars().all()
    return {"magnets": [{"id": m.id, "kind": m.kind, "title": m.title, "token": m.token,
                         "language": getattr(m, "language", "th"),
                         "require_share": m.require_share, "leads_count": m.leads_count,
                         "building": not (m.content_html or "").strip() and not (getattr(m, "error", "") or ""),
                         "failed": bool(getattr(m, "error", "") or "") and not (m.content_html or "").strip(),
                         "error": getattr(m, "error", "") or "",
                         "stage": getattr(m, "stage", "") or "",
                         "path": "/api/lead/%s" % m.token} for m in rows]}


@app.post("/api/lead-magnets/{magnet_id}/retry")
async def retry_lead_magnet(magnet_id: int, user=Depends(get_current_user)):
    """ลองสร้างสื่อแจกฟรีใหม่ (กรณีสร้างล้มค้าง) — เคลียร์ error แล้ว enqueue ใหม่"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import LeadMagnet
    async with db.session() as s:
        m = await s.get(LeadMagnet, magnet_id)
        if not m:
            raise HTTPException(404, "not found")
        await _own_project(s, m.project_id, user)
        topic = m.title or ""
        m.error = ""; m.stage = "⏳ อยู่ในคิว…"; await s.commit()
    try:
        from app.worker.tasks import build_lead_magnet
        build_lead_magnet.delay(magnet_id, topic)
    except Exception:  # noqa: BLE001
        raise HTTPException(503, "คิวงานไม่พร้อม (worker/redis)")
    return {"ok": True, "building": True}


@app.post("/api/lead-magnets/{magnet_id}/to-articles")
async def lead_magnet_to_articles(magnet_id: int, user=Depends(get_current_user)):
    """✂️ แตก 'คอร์ส/คู่มือ' เป็นบทความ SEO ทีละบท (เก็บเป็นร่าง) — 1 บท (H2) = 1 หน้าที่ติดอันดับได้
    คูณคอนเทนต์ฟรี ๆ · เก็บเป็น draft ให้ตรวจ/อนุมัติก่อนเผยแพร่ (กันเนื้อหาซ้ำ/บาง)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import LeadMagnet, Article
    from app.connectors import aeo_score
    async with db.session() as s:
        m = await s.get(LeadMagnet, magnet_id)
        if not m:
            raise HTTPException(404, "not found")
        await _own_project(s, m.project_id, user)          # กันแตกของโปรเจ็คคนอื่น
        pid, mtitle, html = m.project_id, (m.title or ""), (m.content_html or "")
    sections = _split_html_sections(html)
    if not sections:
        raise HTTPException(422, "ยังไม่มีเนื้อหาให้แตก (สื่ออาจกำลังสร้าง/ล้ม หรือไม่มีหัวข้อ H2)")
    async with db.session() as s:                          # กันซ้ำ: ข้ามหัวข้อที่มีบทความชื่อเดียวกันแล้ว
        existing = set(t.strip().lower() for t in (await s.execute(
            select(Article.title).where(Article.project_id == pid))).scalars().all() if t)
    created = []
    for sec in sections:
        if sec["title"].strip().lower() in existing:
            continue
        body = sec["html"]
        desc = _html_plain(body)[:155]
        try:
            aeo = int(aeo_score.score(body, title=sec["title"], description=desc,
                                      keyword=sec["title"], target_words=700).get("score", 0))
        except Exception:  # noqa: BLE001
            aeo = 0
        async with db.session() as s:
            art = Article(project_id=pid, title=sec["title"][:480], html=body, description=desc,
                          cluster=("จากคอร์ส: " + mtitle)[:200], aeo_score=aeo,
                          words=len(_html_plain(body).split()), fmt="บทความยาว", status="draft")
            s.add(art); await s.commit(); await s.refresh(art)
            art.slug = urls.article_slug(sec["title"], art.id)
            await s.commit()
        created.append({"id": art.id, "title": sec["title"]})
        existing.add(sec["title"].strip().lower())
    return {"ok": True, "created": len(created), "sections": len(sections),
            "articles": created, "note": "เก็บเป็นร่าง — ตรวจ/อนุมัติก่อนเผยแพร่ที่หน้าคิวรออนุมัติ"}


@app.get("/api/projects/{project_id}/leads")
async def list_leads(project_id: int, user=Depends(get_current_user)):
    """รายชื่อลีดที่เก็บได้จากสื่อแจกฟรี — เอาไปตามขายบริการ"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import Lead
    async with db.session() as s:
        await _own_project(s, project_id, user)
        rows = (await s.execute(select(Lead).where(Lead.project_id == project_id)
                .order_by(Lead.id.desc()).limit(500))).scalars().all()
    return {"leads": [{"email": r.email, "name": r.name, "shared": r.shared, "source": r.source,
                       "at": r.created_at.isoformat() if r.created_at else ""} for r in rows],
            "count": len(rows)}


@app.get("/api/lead/{token}")
async def public_lead_gate(token: str):
    """หน้า gate สื่อแจกฟรี (สาธารณะ ไม่ต้องล็อกอิน) — teaser ติดอันดับได้ + ฟอร์มปลดล็อก"""
    from fastapi.responses import HTMLResponse
    from app.db.models import Project, LeadMagnet
    from app import public as _public
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    async with db.session() as s:
        m = (await s.execute(select(LeadMagnet).where(
            LeadMagnet.token == (token or "").strip()).limit(1))).scalars().first()
        if not m:
            raise HTTPException(404, "ไม่พบสื่อนี้ / not found")
        proj = await s.get(Project, m.project_id)
    if not proj:
        raise HTTPException(404, "not found")
    return HTMLResponse(_public.render_lead_magnet_gate(m, proj),
                        headers={"Cache-Control": "public, max-age=120"})


@app.post("/api/lead/{token}/unlock")
async def public_lead_unlock(token: str, req: LeadUnlock):
    """ปลดล็อกสื่อ: เก็บอีเมล (ลีด) → คืนเนื้อหาเต็ม · ไม่ต้องล็อกอิน · กันอีเมลซ้ำต่อสื่อ"""
    from app.db.models import LeadMagnet, Lead, Project
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    email = (req.email or "").strip().lower()
    if "@" not in email or len(email) < 5:
        raise HTTPException(422, "อีเมลไม่ถูกต้อง / invalid email")
    alert = None
    async with db.session() as s:
        m = (await s.execute(select(LeadMagnet).where(
            LeadMagnet.token == (token or "").strip()).limit(1))).scalars().first()
        if not m:
            raise HTTPException(404, "not found")
        if not (m.content_html or "").strip():        # ยังสร้างไม่เสร็จ/ล้ม → อย่าเพิ่งเก็บอีเมล+เพิ่มยอด (จะได้ลีดผีของสื่อที่ไม่มีจริง)
            raise HTTPException(409, "สื่อกำลังจัดเตรียม กรุณาลองใหม่อีกครู่ / resource is still being prepared")
        dup = (await s.execute(select(Lead.id).where(
            Lead.magnet_id == m.id, Lead.email == email).limit(1))).scalar()
        if not dup:
            s.add(Lead(project_id=m.project_id, magnet_id=m.id, email=email,
                       name=(req.name or "").strip()[:200], shared=bool(req.shared),
                       source=("lead-magnet: " + (m.title or ""))[:160]))
            m.leads_count = (m.leads_count or 0) + 1
            await s.commit()
            proj = await s.get(Project, m.project_id)
            alert = {"title": m.title or "", "name": (req.name or "").strip(), "email": email,
                     "pname": (proj.name if proj else "") or "",
                     "lead_to": (getattr(proj, "lead_line_to", "") or "").strip() if proj else ""}
        content_html = m.content_html or ""
    if alert:                                          # แจ้งลีดใหม่ → ลูกค้าเจ้าของธุรกิจ (ถ้าตั้ง LINE ไว้) + แอดมินกลาง
        msg = ("🎯 ลีดใหม่จากสื่อแจกฟรี\nโปรเจ็ค: %s\nสื่อ: %s\nชื่อ: %s\nอีเมล: %s"
               % (alert["pname"] or "-", alert["title"] or "-", alert["name"] or "-", alert["email"]))
        try:
            if alert["lead_to"]:
                await notify.send_line(msg, to=alert["lead_to"])
            await notify.send_line(msg)
        except Exception:  # noqa: BLE001
            pass
    return {"content_html": content_html}


def _lead_thanks_html(ok: bool = True) -> str:
    msg = ("ได้รับข้อมูลแล้ว ✓<br>ทีมงานจะติดต่อกลับโดยเร็วที่สุด" if ok
           else "ส่งข้อมูลไม่สำเร็จ กรุณาลองใหม่อีกครั้ง")
    return ('<!doctype html><html lang="th"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>ขอบคุณ</title>'
            '<style>body{font-family:"Sarabun","Segoe UI",sans-serif;background:#f5f8fc;margin:0;'
            'display:grid;place-items:center;min-height:100vh;color:#0f1b2d}'
            '.c{background:#fff;border-radius:16px;padding:40px 44px;box-shadow:0 8px 30px rgba(0,0,0,.1);text-align:center;max-width:420px}'
            '.i{font-size:52px;margin-bottom:8px}h1{font-size:22px;margin:6px 0}p{color:#55647c;line-height:1.7}'
            'a{display:inline-block;margin-top:14px;color:#1657d6;text-decoration:none;font-weight:700}</style></head>'
            '<body><div class="c"><div class="i">' + ('🎉' if ok else '⚠️') + '</div>'
            '<h1>ขอบคุณครับ</h1><p>' + msg + '</p>'
            '<a href="javascript:history.back()">← กลับไปอ่านต่อ</a></div></body></html>')


@app.post("/api/public/lead")
async def public_article_lead(token: str = Form(""), name: str = Form(""), phone: str = Form(""),
                              message: str = Form(""), _rl=Depends(rate_limit_auth)):
    """ลีดจากฟอร์มดักลูกค้าท้ายบทความ (native form submit — โพสต์ข้ามโดเมนได้ ไม่ติด CORS)
    token = report_token ของโปรเจ็ค → เก็บ Lead + แจ้ง LINE 'ลูกค้าเจ้าของธุรกิจ' + แอดมิน → คืนหน้าขอบคุณ"""
    from fastapi.responses import HTMLResponse
    from app.db.models import Project, Lead
    name = (name or "").strip()[:200]; phone = (phone or "").strip()[:60]; message = (message or "").strip()[:1000]
    token = (token or "").strip()
    if not db.enabled() or not token or not (name or phone):
        return HTMLResponse(_lead_thanks_html(ok=False), status_code=200)
    alert = None
    async with db.session() as s:
        p = (await s.execute(select(Project).where(Project.report_token == token).limit(1))).scalars().first()
        if not p:
            return HTMLResponse(_lead_thanks_html(ok=False), status_code=200)
        s.add(Lead(project_id=p.id, name=name, phone=phone, message=message, source="article-cta"))
        await s.commit()
        alert = {"pname": p.name or "", "lead_to": (getattr(p, "lead_line_to", "") or "").strip()}
    msg = ("🎯 ลีดใหม่จากบทความ\nโปรเจ็ค: %s\nชื่อ: %s\nเบอร์: %s%s"
           % (alert["pname"] or "-", name or "-", phone or "-", ("\nข้อความ: " + message) if message else ""))
    try:                                               # ส่งให้ลูกค้าเจ้าของธุรกิจ (ถ้าตั้ง LINE) + แอดมินกลาง
        if alert["lead_to"]:
            await notify.send_line(msg, to=alert["lead_to"])
        await notify.send_line(msg)
    except Exception:  # noqa: BLE001
        pass
    return HTMLResponse(_lead_thanks_html(ok=True))


def _build_form_html() -> str:
    """ฟอร์มสาธารณะ 'ขอทำเว็บ' — แอดมินส่งลิงก์ /build ให้ลูกค้ากรอก → submit เข้าคิวอนุมัติ"""
    inp = ('font-family:inherit;width:100%;padding:11px 13px;border:1px solid #d7deea;border-radius:10px;'
           'font-size:15px;box-sizing:border-box;margin-top:5px;background:#fff;color:#0f1b2d')
    return ('<!doctype html><html lang="th"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>ขอทำเว็บกับ ImVisible</title>'
            '<style>body{font-family:"Sarabun","Segoe UI",sans-serif;background:#f5f8fc;margin:0;color:#0f1b2d;line-height:1.6}'
            '.wrap{max-width:560px;margin:0 auto;padding:28px 18px}.card{background:#fff;border:1px solid #e3e9f2;border-radius:18px;'
            'padding:26px 24px;box-shadow:0 8px 30px rgba(16,28,48,.08)}h1{font-size:24px;margin:6px 0 2px;color:#0f1b2d}'
            '.sub{color:#55647c;font-size:14px;margin-bottom:18px}label{font-weight:700;font-size:14px}'
            '.hint{color:#8a97ab;font-size:12px}.b{background:#1657d6;color:#fff;border:0;border-radius:999px;padding:13px 30px;'
            'font-size:16px;font-weight:800;cursor:pointer;width:100%;margin-top:18px;font-family:inherit}'
            '.k{display:inline-flex;gap:8px;align-items:center;font-size:12px;font-weight:700;letter-spacing:.1em;color:#0e3fa0;'
            'background:#eaf1ff;border:1px solid #e3e9f2;padding:5px 12px;border-radius:999px;text-transform:uppercase}</style></head>'
            '<body><div class="wrap"><div class="card">'
            '<span class="k">🌐 ImVisible · ขอทำเว็บ</span>'
            '<h1>อยากได้เว็บที่ Google + AI แนะนำ?</h1>'
            '<div class="sub">กรอกสั้น ๆ แล้วส่งมา — ทีมเราสร้างแบบให้ดูฟรี ไม่มีข้อผูกมัด · มีแค่เพจ Facebook ก็ได้</div>'
            '<form action="/api/public/web-request" method="post">'
            '<div style="margin-bottom:13px"><label>ชื่อธุรกิจ/ร้าน *</label>'
            '<input name="business_name" required placeholder="เช่น To The Moon Chumphon" style="' + inp + '"></div>'
            '<div style="margin-bottom:13px"><label>ประเภทธุรกิจ</label>'
            '<input name="biz_type" placeholder="เช่น คาเฟ่ / ร้านอาหาร / คลินิก" style="' + inp + '"></div>'
            '<div style="margin-bottom:13px"><label>เบอร์/LINE/อีเมล ติดต่อกลับ *</label>'
            '<input name="contact" required placeholder="เช่น 08x-xxx-xxxx หรือ LINE ID" style="' + inp + '"></div>'
            '<div style="margin-bottom:13px"><label>ลิงก์ที่มีอยู่</label>'
            '<textarea name="links" rows="3" placeholder="วางลิงก์ Facebook / เว็บเดิม / IG (ระบบดึงข้อมูลให้เอง)" style="' + inp + '"></textarea>'
            '<div class="hint">มีแค่เพจ Facebook ก็พอ — ระบบไปหาข้อมูลให้เอง</div></div>'
            '<div style="margin-bottom:13px"><label>อยากได้เว็บแบบไหน / ข้อมูลเพิ่ม</label>'
            '<textarea name="detail" rows="3" placeholder="เช่น เน้นลูกค้าต่างชาติ, ขายกาแฟ+จองโต๊ะ, โทนอบอุ่น" style="' + inp + '"></textarea></div>'
            '<div style="margin-bottom:4px"><label>ภาษาเว็บหลัก</label>'
            '<select name="language" style="' + inp + '"><option value="th">ไทย</option><option value="en">อังกฤษ (เน้นต่างชาติ)</option></select></div>'
            '<button class="b" type="submit">ส่งคำขอ — ให้ทีมสร้างแบบให้</button>'
            '<div class="hint" style="text-align:center;margin-top:12px">ส่งแล้วทีมงานจะติดต่อกลับพร้อมแบบเว็บให้ดู</div>'
            '</form></div></div></body></html>')


@app.get("/api/build")
async def build_form_page():
    """ฟอร์มสาธารณะ 'ขอทำเว็บ' — อยู่ใต้ /api/ เพื่อให้ nginx proxy ถึง (เหมือน public page อื่น เช่น /api/report)"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(_build_form_html(), headers={"Cache-Control": "public, max-age=300"})


@app.post("/api/public/web-request")
async def submit_web_request(business_name: str = Form(""), biz_type: str = Form(""), contact: str = Form(""),
                             links: str = Form(""), detail: str = Form(""), language: str = Form("th"),
                             _rl=Depends(rate_limit_auth)):
    """ลูกค้ากรอกฟอร์มขอทำเว็บ (native submit) → เข้าคิว WebRequest + แจ้ง LINE แอดมิน → หน้าขอบคุณ"""
    from fastapi.responses import HTMLResponse
    from app.db.models import WebRequest
    business_name = (business_name or "").strip()[:300]
    if not db.enabled() or not business_name or not (contact or "").strip():
        return HTMLResponse(_lead_thanks_html(ok=False), status_code=200)
    async with db.session() as s:
        s.add(WebRequest(business_name=business_name, biz_type=(biz_type or "").strip()[:120],
                         contact=(contact or "").strip()[:255], links=(links or "").strip()[:2000],
                         detail=(detail or "").strip()[:3000],
                         language=("en" if language == "en" else "th"), status="new"))
        await s.commit()
    try:
        await notify.send_line("🌐 คำขอทำเว็บใหม่!\nธุรกิจ: %s (%s)\nติดต่อ: %s\nลิงก์: %s"
                               % (business_name, biz_type or "-", contact, (links or "-")[:200]))
    except Exception:  # noqa: BLE001
        pass
    return HTMLResponse(_lead_thanks_html(ok=True))


@app.get("/api/web-requests")
async def web_requests_list(user=Depends(get_current_user)):
    """คิวคำขอทำเว็บ (แอดมิน) — ใหม่ก่อน"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import usage
    if (await usage.user_plan(user["id"])) != "admin":
        raise HTTPException(403, "เฉพาะแอดมิน")
    from app.db.models import WebRequest
    async with db.session() as s:
        rows = (await s.execute(select(WebRequest).order_by(WebRequest.status.asc(), WebRequest.created_at.desc())
                .limit(300))).scalars().all()
        items = [{"id": r.id, "business_name": r.business_name, "biz_type": r.biz_type, "contact": r.contact,
                  "links": r.links, "detail": r.detail, "language": r.language, "status": r.status,
                  "project_id": r.project_id, "preview_url": r.preview_url or "", "note": r.note or "",
                  "created_at": r.created_at.isoformat() if r.created_at else ""} for r in rows]
    return {"items": items, "count": len(items)}


@app.post("/api/web-requests/{req_id}/approve")
async def web_request_approve(req_id: int, user=Depends(get_current_user)):
    """อนุมัติคำขอ → สร้างโปรเจ็ค (ระบบค้นเว็บจากลิงก์ให้เอง) + คืนลิงก์ให้ลูกค้าดูแบบ — แอดมิน"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import usage
    if (await usage.user_plan(user["id"])) != "admin":
        raise HTTPException(403, "เฉพาะแอดมิน")
    from app.db.models import WebRequest
    import re as _re2
    async with db.session() as s:
        wr = await s.get(WebRequest, req_id)
        if not wr:
            raise HTTPException(404, "ไม่พบคำขอ")
        if wr.status == "approved" and wr.project_id:
            raise HTTPException(409, "อนุมัติไปแล้ว")
        name, links, lang = wr.business_name, wr.links or "", (wr.language or "th")
    first = ""
    for l in _re2.split(r"[\n,]", links):
        if l.strip():
            first = l.strip(); break
    pc = ProjectCreate(name=name, url=first, language=lang, publish_mode="managed", mode="approve")
    res = await create_project(pc, user)          # สร้าง + analyze (ค้นเว็บถ้า FB) + ผลิตบทความแรก
    pid = res.get("id")
    preview = res.get("public_home") or ""
    async with db.session() as s:
        wr = await s.get(WebRequest, req_id)
        if wr:
            wr.status = "approved"; wr.project_id = pid; wr.preview_url = preview
            await s.commit()
    try:
        await notify.send_line("✅ อนุมัติ+สร้างโปรเจ็คแล้ว: %s\nดูแบบ: %s" % (name, preview or "-"))
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "project_id": pid, "preview_url": preview}


@app.post("/api/web-requests/{req_id}/reject")
async def web_request_reject(req_id: int, user=Depends(get_current_user)):
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app import usage
    if (await usage.user_plan(user["id"])) != "admin":
        raise HTTPException(403, "เฉพาะแอดมิน")
    from app.db.models import WebRequest
    async with db.session() as s:
        wr = await s.get(WebRequest, req_id)
        if not wr:
            raise HTTPException(404, "ไม่พบคำขอ")
        wr.status = "rejected"
        await s.commit()
    return {"ok": True}


@app.post("/api/contact")
async def contact_form(req: ContactForm, _rl=Depends(rate_limit_auth)):
    """ฟอร์มติดต่อจากหน้าแรก (สาธารณะ) → เก็บลีด + แจ้งแอดมินทาง SMS และ/หรือ LINE ทันที · rate-limit กันสแปม"""
    name = (req.name or "").strip()[:200]
    phone = (req.phone or "").strip()[:60]
    if not (name and phone):
        raise HTTPException(422, "กรุณากรอกชื่อและเบอร์ติดต่อ")
    business = (req.business or "").strip()[:300]
    kws = [str(k).strip() for k in (req.keywords or []) if str(k).strip()][:5]
    kw_txt = ", ".join(kws)
    if db.enabled():
        from app.db.models import ContactLead
        async with db.session() as s:
            s.add(ContactLead(name=name, phone=phone, business=business, keywords=kw_txt))
            await s.commit()
    from app.connectors import notify
    try:                                              # 📱 SMS เข้ามือถือแอดมินทันที (ตั้ง CONTACT_SMS_TO) — crash-safe + log เหตุผลจริง
        if settings.contact_sms_to:
            sms = ("ลีดใหม่ imvisible.tech | ชื่อ: %s | เบอร์: %s | ธุรกิจ: %s | คีย์: %s"
                   % (name, phone, business or "-", kw_txt or "-"))
            res = await notify.send_sms_detail(settings.contact_sms_to, sms)
            if not res.get("ok"):
                print("[contact] SMS ไม่ส่ง: %s" % (res.get("reason") or "ไม่ทราบสาเหตุ"))
        else:
            print("[contact] ข้าม SMS — ยังไม่ได้ตั้ง CONTACT_SMS_TO ใน .env")
    except Exception as e:  # noqa: BLE001
        print("[contact] SMS error: %r" % e)
    try:                                              # แจ้ง LINE ด้วย (ถ้าตั้งไว้) — ล้มก็ยังเก็บลีด+ส่ง SMS ไปแล้ว
        msg = ("\U0001F514 มีคนสนใจบริการ (จากหน้าเว็บ imvisible.tech)\n"
               "\U0001F464 ชื่อ: %s\n\U0001F4DE เบอร์: %s\n\U0001F3E2 ธุรกิจ: %s\n\U0001F3AF คีย์เวิร์ด: %s"
               % (name, phone, business or "-", kw_txt or "-"))
        if not await notify.send_line(msg):
            print("[contact] LINE ไม่ส่ง — ตรวจ LINE_CHANNEL_ACCESS_TOKEN / LINE_DEFAULT_TO")
    except Exception as e:  # noqa: BLE001
        print("[contact] LINE error: %r" % e)
    return {"ok": True}


@app.post("/api/site-check")
async def site_check(req: SiteCheckRequest, _rl=Depends(rate_limit_auth)):
    """ตรวจสุขภาพเว็บจากหน้าแรก 'จริง' (สาธารณะ) → คะแนน + วิธีแก้ + การครอบคลุมคีย์เวิร์ด
    วัดจาก HTML จริง ไม่กุคะแนน · กัน SSRF · rate-limit กันสแปม"""
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(422, "กรุณาใส่ลิงก์เว็บไซต์ของคุณ")
    from app.connectors import sitecheck
    res = await sitecheck.check_url(url, req.keywords or [])
    if not res.get("ok"):
        raise HTTPException(422, res.get("note") or "เปิดเว็บไม่ได้ — ตรวจสอบลิงก์อีกครั้ง")
    if req.deep:      # 🎯 สัญญาณจับต้องได้: Google เก็บ index กี่หน้า + คีย์เวิร์ดอันดับ + เทส AI สดว่าแนะนำไหม
        try:
            biz = (req.business_name or res.get("business") or "").strip()
            res.update(await _report_extras(_domain_of(url), biz, req.keywords or []))
        except Exception:  # noqa: BLE001
            pass
    return res


async def _report_extras(domain: str, biz: str, kws: list) -> dict:
    """สัญญาณ 'จับต้องได้' สำหรับรายงานสุขภาพ (ตัวเลขจริง · best-effort ล้ม/ไม่มีคีย์ = ข้าม):
    google = ติด index กี่หน้า + คีย์เวิร์ดอันดับเท่าไร · ai_test = ถาม ChatGPT/Gemini จริงว่าแนะนำแบรนด์นี้ไหม"""
    import asyncio as _aio
    from app.connectors import serp, citation
    biz = (biz or (domain.split(".")[0] if domain else "")).strip()
    kws = [str(k).strip() for k in (kws or []) if str(k).strip()][:3]

    async def _google():
        g = {"indexed_pages": None, "ranks": []}
        try:
            idx = await serp.search("site:" + domain, n=10)
            g["indexed_pages"] = len(idx or [])
        except Exception:  # noqa: BLE001
            pass
        for kw in kws:
            try:
                r = await serp.rank_check(kw, domain)
                g["ranks"].append({"keyword": kw, "rank": r.get("our_rank"), "on_page1": bool(r.get("on_page1"))})
            except Exception:  # noqa: BLE001
                g["ranks"].append({"keyword": kw, "rank": None, "on_page1": False})
        return g

    async def _ai():
        q = (kws[0] + " แนะนำที่ไหนดี") if kws else (biz + " ดีไหม แนะนำหน่อย")
        brand_terms = [t for t in [biz, (domain.split(".")[0] if domain else "")] if t]
        engines = []

        async def one(name, fn):
            try:
                ans = await fn(q)
                if ans:
                    engines.append({"engine": name, "cited": bool(citation._is_cited(ans, brand_terms, domain)),
                                    "excerpt": (ans or "").strip()[:420]})
            except Exception:  # noqa: BLE001
                pass
        await _aio.gather(one("ChatGPT", citation._ask_openai), one("Gemini", citation._ask_gemini))
        return {"question": q, "engines": engines}

    g, a = await _aio.gather(_google(), _ai())
    return {"google": g, "ai_test": a}


def _domain_of(u: str) -> str:
    return (u or "").strip().lower().replace("https://", "").replace("http://", "").strip("/").split("/")[0]


@app.post("/api/site-report")
async def create_site_report(req: SiteReportCreate, user=Depends(get_current_user)):
    """สร้าง 'ลิงก์รายงานสุขภาพเว็บ' สาธารณะ (แชร์ได้) ส่งให้ลูกค้า/ผู้สนใจ — เก็บลีดเมื่อเขาขอให้ช่วย
    ตรวจหน้าเว็บจริงด้วย sitecheck (ตัวเลขจริง ไม่กุ) แล้วบันทึกเป็น snapshot + คืน token/ลิงก์"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(422, "กรุณาใส่ลิงก์เว็บลูกค้า")
    kws = [str(k).strip() for k in (req.keywords or []) if str(k).strip()][:3]
    from app.connectors import sitecheck
    res = await sitecheck.check_url(url, kws)
    if not res.get("ok"):
        raise HTTPException(422, res.get("note") or "เปิดเว็บไม่ได้ — ตรวจสอบลิงก์อีกครั้ง")
    import json as _json
    from app.db.models import SiteReport
    token = secrets.token_urlsafe(12)
    domain = _domain_of(res.get("url") or url)
    async with db.session() as s:
        rep = SiteReport(
            token=token, url=(res.get("url") or url)[:600], domain=domain[:255],
            business_name=(req.business_name or "").strip()[:300], keywords=", ".join(kws)[:2000],
            created_by=user["id"], score=int(res.get("score") or 0), grade=(res.get("grade") or "")[:2],
            aeo_score=int(res.get("aeo_score") or 0), aeo_grade=(res.get("aeo_grade") or "")[:2],
            data_json=_json.dumps(res, ensure_ascii=False),
        )
        s.add(rep)
        await s.commit()
    base = (settings.app_base_url or "").rstrip("/")
    path = "/api/site-report/%s" % token
    return {"ok": True, "token": token, "path": path, "public_url": (base + path) if base else path,
            "domain": domain, "score": res.get("score"), "grade": res.get("grade"),
            "aeo_score": res.get("aeo_score"), "aeo_grade": res.get("aeo_grade")}


@app.get("/api/site-report/{token}")
async def public_site_report(token: str):
    """หน้ารายงานสุขภาพเว็บสาธารณะ (ไม่ต้องล็อกอิน · แชร์ได้) — เกจคะแนน + ปัญหา + แผนแก้ที่ gate ด้วยฟอร์ม"""
    from fastapi.responses import HTMLResponse
    from datetime import datetime, timezone, timedelta
    import json as _json
    from app.db.models import SiteReport
    from app import public as _public
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    token = (token or "").strip()
    if len(token) < 8:
        raise HTTPException(404, "ไม่พบรายงาน")
    async with db.session() as s:
        rep = (await s.execute(select(SiteReport).where(SiteReport.token == token).limit(1))).scalars().first()
    if not rep:
        raise HTTPException(404, "ไม่พบรายงาน (ลิงก์ไม่ถูกต้องหรือถูกยกเลิก)")
    try:
        data = _json.loads(rep.data_json or "{}")
    except Exception:  # noqa: BLE001
        data = {}
    now7 = (rep.created_at or datetime.now(timezone.utc)) + timedelta(hours=7) if rep.created_at else (datetime.now(timezone.utc) + timedelta(hours=7))
    gen = now7.strftime("%d/%m/%Y %H:%M น.")
    html = _public.render_site_report_page(rep, data, gen)
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=180", "X-Robots-Tag": "noindex, follow"})


@app.post("/api/site-report/{token}/lead")
async def site_report_lead(token: str, req: ReportLeadCreate, _rl=Depends(rate_limit_auth)):
    """ผู้สนใจกรอกจากหน้ารายงาน → เก็บลีด + เด้ง LINE แอดมินทันที + คืน 'แผนแก้เต็ม' · rate-limit กันสแปม"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    import json as _json
    from app.db.models import SiteReport, ReportLead
    from app import public as _public
    name = (req.name or "").strip()[:200]
    phone = (req.phone or "").strip()[:60]
    contact = (req.contact or "").strip()[:255]
    message = (req.message or "").strip()[:1000]
    if not name:
        raise HTTPException(422, "กรุณากรอกชื่อ")
    if not (phone or contact):
        raise HTTPException(422, "กรุณากรอกเบอร์โทรหรือ LINE/อีเมล")
    async with db.session() as s:
        rep = (await s.execute(select(SiteReport).where(SiteReport.token == (token or "").strip()).limit(1))).scalars().first()
        if not rep:
            raise HTTPException(404, "ไม่พบรายงาน")
        dup = (await s.execute(select(ReportLead.id).where(
            ReportLead.report_id == rep.id,
            ReportLead.phone == phone, ReportLead.contact == contact).limit(1))).scalar()
        is_new = not dup
        if is_new:
            s.add(ReportLead(report_id=rep.id, name=name, phone=phone, contact=contact, message=message))
            rep.leads_count = (rep.leads_count or 0) + 1
            await s.commit()
        try:
            data = _json.loads(rep.data_json or "{}")
        except Exception:  # noqa: BLE001
            data = {}
        biz = rep.business_name or rep.domain
        score, aeo = rep.score, rep.aeo_score
    if is_new:                                        # แจ้ง LINE แอดมินเฉพาะลีดใหม่ (กันเด้งซ้ำตอนรีเฟรช) · crash-safe
        try:
            from app.connectors import notify
            base = (settings.app_base_url or "").rstrip("/")
            link = (base + "/api/site-report/" + rep.token) if base else ("/api/site-report/" + rep.token)
            msg = ("\U0001F525 ลีดใหม่จากรายงานสุขภาพเว็บ!\n"
                   "\U0001F3E2 ธุรกิจ: %s\n\U0001F464 ชื่อ: %s\n\U0001F4DE เบอร์: %s\n\U0001F4AC LINE/อีเมล: %s\n"
                   "\U0001F4CA คะแนน: SEO %s · AEO/GEO %s\n%s%s"
                   % (biz, name, phone or "-", contact or "-", score, aeo,
                      ("\U0001F5D2 ข้อความ: %s\n" % message) if message else "", "\U0001F517 " + link))
            if not await notify.send_line(msg):
                print("[site-report] LINE ไม่ส่ง — ตรวจ LINE_CHANNEL_ACCESS_TOKEN / LINE_DEFAULT_TO")
        except Exception as e:  # noqa: BLE001
            print("[site-report] LINE error: %r" % e)
    return {"ok": True, "plan_html": _public.render_report_plan(data)}


@app.get("/api/site-reports")
async def list_site_reports(user=Depends(get_current_user)):
    """รายการลิงก์รายงานที่สร้างไว้ + จำนวนลีดของแต่ละอัน (แอดมินติดตาม/ส่งซ้ำ)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import SiteReport
    base = (settings.app_base_url or "").rstrip("/")
    async with db.session() as s:
        rows = (await s.execute(select(SiteReport).order_by(SiteReport.id.desc()).limit(300))).scalars().all()
    return {"reports": [{
        "token": r.token, "path": "/api/site-report/%s" % r.token,
        "public_url": (base + "/api/site-report/" + r.token) if base else ("/api/site-report/" + r.token),
        "business": r.business_name or r.domain, "domain": r.domain,
        "score": r.score, "grade": r.grade, "aeo_score": r.aeo_score, "aeo_grade": r.aeo_grade,
        "leads": r.leads_count or 0, "at": r.created_at.isoformat() if r.created_at else ""}
        for r in rows], "count": len(rows)}


@app.get("/api/report-leads")
async def list_report_leads(user=Depends(get_current_user)):
    """รายชื่อลีดจากหน้ารายงาน (รายชื่อโทรตามปิดการขาย) — ใหม่สุดก่อน + บริบทเว็บ/คะแนน"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import SiteReport, ReportLead
    base = (settings.app_base_url or "").rstrip("/")
    async with db.session() as s:
        rows = (await s.execute(
            select(ReportLead, SiteReport)
            .join(SiteReport, ReportLead.report_id == SiteReport.id)
            .order_by(ReportLead.id.desc()).limit(400))).all()
    out = []
    for lead, rep in rows:
        path = "/api/site-report/%s" % rep.token
        out.append({
            "name": lead.name, "phone": lead.phone, "contact": lead.contact, "message": lead.message,
            "business": rep.business_name or rep.domain, "domain": rep.domain,
            "token": rep.token, "path": path, "public_url": (base + path) if base else path,
            "score": rep.score, "aeo_score": rep.aeo_score,
            "at": lead.created_at.isoformat() if lead.created_at else ""})
    return {"leads": out, "count": len(out)}


@app.get("/api/contacts")
async def list_contacts(user=Depends(get_current_user)):
    """รายชื่อลีดจากฟอร์มติดต่อหน้าแรก (แอดมินดูย้อนหลัง เผื่อ LINE พลาด)"""
    if not db.enabled():
        raise HTTPException(503, "ยังไม่ได้ตั้งค่า DATABASE_URL")
    from app.db.models import ContactLead
    async with db.session() as s:
        rows = (await s.execute(select(ContactLead).order_by(ContactLead.id.desc()).limit(300))).scalars().all()
    return {"contacts": [{"name": r.name, "phone": r.phone, "business": r.business,
                          "keywords": r.keywords, "at": r.created_at.isoformat() if r.created_at else ""}
                         for r in rows], "count": len(rows)}


@app.post("/api/sms/test")
async def sms_test(to: str = "", user=Depends(get_current_user)):
    """ทดสอบส่ง SMS จริง (แอดมิน) → คืนเหตุผลจริงของ Twilio ทันที เพื่อวินิจฉัยว่าทำไมไม่ส่ง
    ?to=0xxxxxxxxx เพื่อทดสอบเบอร์เจาะจง · ว่าง = ใช้ CONTACT_SMS_TO"""
    from app.connectors import notify
    target = (to or settings.contact_sms_to or "").strip()
    if not target:
        raise HTTPException(422, "ไม่มีเบอร์ปลายทาง — ส่ง ?to=0xxxxxxxxx หรือตั้ง CONTACT_SMS_TO ก่อน")
    return await notify.send_sms_detail(target, "ทดสอบ SMS จาก imvisible.tech ✓ ระบบแจ้งเตือนลีดพร้อมใช้งาน")


@app.post("/api/line/webhook")
async def line_webhook(request: Request):
    """Webhook LINE — ตัวช่วย 'คว้า ID' ของ group/user เพื่อไปตั้ง LINE_DEFAULT_TO
    วิธีใช้: เพิ่มบอทเข้ากลุ่ม แล้วพิมพ์อะไรก็ได้ → บอทตอบ ID ของกลุ่มกลับมาในแชท ก็อปไปใส่ .env"""
    raw = await request.body()
    if settings.line_channel_secret:                 # ยืนยันว่ามาจาก LINE จริง (ถ้าตั้ง secret)
        import hmac, hashlib, base64
        expect = base64.b64encode(hmac.new(settings.line_channel_secret.encode(), raw, hashlib.sha256).digest()).decode()
        if request.headers.get("x-line-signature", "") != expect:
            return {"ok": True}
    import json as _json
    try:
        body = _json.loads(raw or b"{}")
    except Exception:  # noqa: BLE001
        return {"ok": True}
    from app.connectors import notify
    for ev in (body.get("events") or []):
        src = ev.get("source") or {}
        sid = src.get("groupId") or src.get("roomId") or src.get("userId") or ""
        stype = src.get("type") or ""
        if not sid:
            continue
        print("[LINE webhook] source=%s id=%s type=%s" % (stype, sid, ev.get("type")))   # โผล่ใน docker logs ด้วย
        rt = ev.get("replyToken")
        if rt:
            label = {"group": "กลุ่มนี้", "room": "ห้องนี้", "user": "แชทนี้"}.get(stype, stype)
            try:
                await notify.reply_line(rt, "✅ ID ของ%s:\n%s\n\nนำไปวางใน LINE_DEFAULT_TO ใน .env แล้วรีสตาร์ต เพื่อให้แจ้งเตือนเด้งที่นี่" % (label, sid))
            except Exception:  # noqa: BLE001
                pass
    return {"ok": True}


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
async def mine_questions(req: MineRequest, user=Depends(get_current_user)):
    """M1 · ขุดคำถามจริง (Google Suggest + People Also Ask)"""
    try:
        return await mining.mine(req.seed, req.location_code, req.language_code)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/rank/check")
async def rank_check(req: RankCheckRequest, user=Depends(get_current_user)):
    """M5 · อันดับ Google จริง (DataForSEO) — ตรวจสอบได้: เสิร์ชเองก็เห็น"""
    try:
        return await serp.rank_check(req.keyword, req.domain, req.location_code, req.language_code)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/gsc/summary")
async def gsc_summary(req: GSCSummaryRequest, user=Depends(get_current_user)):
    """M5 · คลิก/Impressions/อันดับ จริงจาก Google Search Console"""
    try:
        return await gsc.summary(req.site_url, req.days)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/citation/sample")
async def citation_sample(req: CitationSampleRequest, user=Depends(get_current_user)):
    """M5 · AI Citation / Share of Voice (Prompt Sampling — ค่าประมาณเชิงสถิติ)"""
    try:
        return await citation.sample(req.questions, req.brand_terms, req.domain, req.engines)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/content/generate")
async def content_generate(req: ContentGenerateRequest, user=Depends(get_current_user)):
    """M2 · ผลิตบทความสูตร AEO ด้วย LLM จริง"""
    try:
        return await content.generate(req.topic, req.fmt, req.words)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))


@app.post("/api/publish")
async def publish_post(req: PublishRequest, user=Depends(get_current_user)):
    """M4 · เผยแพร่ขึ้น WordPress จริง + IndexNow ping"""
    try:
        return await publish.publish_and_index(req.title, req.html, req.status, req.url_path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, str(e))
