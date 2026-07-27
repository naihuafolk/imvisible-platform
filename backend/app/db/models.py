"""
โมเดลฐานข้อมูล (SQLAlchemy 2.0) — เก็บผลจริงของแต่ละโปรเจ็ค
ตาม stack หน้า 7: PostgreSQL + Vector DB (pgvector)
คอลัมน์ embedding ใช้ pgvector สำหรับวิเคราะห์คลัสเตอร์ (M6)
"""
from datetime import datetime

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(50), default="free")   # free | pro | business (บิลลิ่งอัปเดต)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TeamMember(Base):
    """สมาชิกทีมของเจ้าของบัญชี (Agency ให้ลูกค้า/ทีมเข้าดูรายงาน) — สิทธิ์ตาม role
    viewer=ดูอย่างเดียว · editor/admin=แก้ไขได้ · ผูก member_user_id เมื่อผู้ถูกเชิญสมัคร/ล็อกอิน"""
    __tablename__ = "team_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)   # เจ้าของบัญชีที่เชิญ
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(20), default="viewer")             # viewer | editor | admin
    status: Mapped[str] = mapped_column(String(20), default="invited")          # invited | active
    member_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subscription(Base):
    """สถานะการสมัครสมาชิก (Stripe) ต่อผู้ใช้ — webhook อัปเดต + sync User.plan"""
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(30), default="free")
    status: Mapped[str] = mapped_column(String(30), default="inactive")   # active|canceled|past_due|inactive
    stripe_customer_id: Mapped[str] = mapped_column(String(80), default="")
    stripe_subscription_id: Mapped[str] = mapped_column(String(80), default="")
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(255), index=True)
    country: Mapped[str] = mapped_column(String(50), default="ไทย")
    language: Mapped[str] = mapped_column(String(50), default="th")
    mode: Mapped[str] = mapped_column(String(20), default="approve")   # approve | auto
    freshness_days: Mapped[int] = mapped_column(Integer, default=120)
    keyword_pack: Mapped[int] = mapped_column(Integer, default=50)      # โควตาคีย์เวิร์ดของลูกค้ารายนี้ (10/30/50) — แอดมินตั้ง
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)   # แจ้งเตือน SMS เมื่อคีย์ติด/ขยับขึ้น
    sms_to: Mapped[str] = mapped_column(String(40), default="")         # เบอร์ปลายทาง SMS (E.164 เช่น +66...)
    # --- ปลายทางเผยแพร่ (Phase 1: Managed Hosting) ---
    # ความ unique ของ slug + custom_domain บังคับด้วย unique index ใน migrate.py
    # (สร้างหลัง backfill — กัน hijack/ชน + กัน MultipleResultsFound)
    slug: Mapped[str] = mapped_column(String(120), default="")                  # โฮสต์ที่ {slug}.imvisible.tech / /blog/{slug}
    publish_mode: Mapped[str] = mapped_column(String(20), default="managed")    # managed | wordpress | none
    custom_domain: Mapped[str] = mapped_column(String(255), default="")         # เช่น blog.abccoffee.com (CNAME มาที่เรา)
    # --- Site Intelligence: สิ่งที่ระบบ "อ่านจากเว็บลูกค้า" (ทำให้ 'ใส่แค่ลิงก์' เป็นจริง) ---
    business_context: Mapped[str] = mapped_column(Text, default="")             # ธุรกิจทำอะไร/ขายอะไร/ให้ใคร → ป้อนเครื่องยนต์คอนเทนต์
    brand_terms: Mapped[str] = mapped_column(Text, default="")                  # คำแบรนด์ (คั่นด้วย ,) → ใช้ตรวจ AI citation
    topic_plan: Mapped[str] = mapped_column(Text, default="")                   # แผนหัวข้อ (JSON) เรียงตามคำที่ชนะได้ก่อน
    aeo_questions: Mapped[str] = mapped_column(Text, default="")                 # คำถาม AEO ที่ลูกค้าตั้งเอง (JSON list) → สุ่มถาม AI 'ให้ตรง' (มาก่อนอัตโนมัติ)
    cta_json: Mapped[str] = mapped_column(Text, default="")                      # กล่องดักลูกค้า (CTA) ท้ายบทความ (JSON) — เนียนขายบริการ/เก็บลีดต่อโปรเจ็ค
    report_token: Mapped[str] = mapped_column(String(64), default="", index=True)  # โทเคนลิงก์รายงานสาธารณะ (ส่งให้ลูกค้าเปิดดูได้โดยไม่ต้องล็อกอิน)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    articles: Mapped[list["Article"]] = relationship(back_populates="project")


class Article(Base):
    __tablename__ = "articles"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    slug: Mapped[str] = mapped_column(String(200), default="", index=True)   # ส่วนท้าย URL สาธารณะ
    description: Mapped[str] = mapped_column(String(400), default="")        # meta description / excerpt
    cover_url: Mapped[str] = mapped_column(Text, default="")                 # รูปปก (Seedream/ModelArk) + og:image (signed URL อาจยาว → Text)
    cluster: Mapped[str] = mapped_column(String(200), default="")
    fmt: Mapped[str] = mapped_column(String(50), default="บทความยาว")
    html: Mapped[str] = mapped_column(Text, default="")
    schema_json: Mapped[str] = mapped_column(Text, default="")               # JSON-LD (Article/FAQPage) สำหรับ render หน้า AEO
    words: Mapped[int] = mapped_column(Integer, default=0)
    aeo_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft")   # draft|factcheck|ready|scheduled|published
    url: Mapped[str] = mapped_column(String(500), default="")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # ตั้งเวลาเผยแพร่
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())  # ใช้คิดโควตา/เดือน
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project: Mapped["Project"] = relationship(back_populates="articles")


class RankSnapshot(Base):
    """ผลตรวจอันดับรายวัน (จาก SERP API) — ตัวเลขจริง ตรวจสอบได้"""
    __tablename__ = "rank_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    keyword: Mapped[str] = mapped_column(String(300), index=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    on_page1: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CitationSnapshot(Base):
    """ผล Prompt Sampling รายสัปดาห์ (ค่าประมาณเชิงสถิติ)"""
    __tablename__ = "citation_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    engine: Mapped[str] = mapped_column(String(30))
    sov_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    answered: Mapped[int] = mapped_column(Integer, default=0)
    cited: Mapped[int] = mapped_column(Integer, default=0)
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CitationExample(Base):
    """หลักฐาน AEO — คำถามที่ AI 'ตอบแล้วอ้างอิงแบรนด์/เว็บเราจริง' + snippet คำตอบ (ไว้โชว์ลูกค้า)
    เก็บเฉพาะกรณี cited=True ต่อรอบสุ่มถาม → ตรวจสอบย้อนได้ว่าติด AEO จริง"""
    __tablename__ = "citation_examples"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    engine: Mapped[str] = mapped_column(String(30))
    question: Mapped[str] = mapped_column(String(500), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DistributionChannel(Base):
    """ช่องทางกระจายโพสต่อโปรเจ็ค (โซเชียลของลูกค้าเอง) — โทเคนเก็บแบบเข้ารหัส (crypto.enc)"""
    __tablename__ = "distribution_channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))           # line | facebook | x | linkedin
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ref: Mapped[str] = mapped_column(String(255), default="")     # page_id / userId / groupId (ไม่ลับ)
    token_enc: Mapped[str] = mapped_column(Text, default="")      # โทเคน (เข้ารหัสแล้ว)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectCredential(Base):
    """คีย์/บัญชีเชื่อมต่อ 'ของลูกค้าเอง' ต่อโปรเจ็ค (DataForSEO/WordPress/GSC) — เก็บเข้ารหัส
    ทำให้เป็น multi-tenant จริง: ลูกค้าใช้คีย์ตัวเอง ไม่ใช่คีย์กลางของแพลตฟอร์ม"""
    __tablename__ = "project_credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))            # dataforseo | wordpress | gsc
    data_enc: Mapped[str] = mapped_column(Text, default="")  # JSON ของฟิลด์ (เข้ารหัส crypto.enc)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DistributionEvent(Base):
    """บันทึกการกระจายต่อบทความ — ลูกค้าเห็นได้ว่าคอนเทนต์ไปโผล่ที่ไหนบ้าง (โปร่งใส)"""
    __tablename__ = "distribution_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))        # blog | indexnow | wordpress | line | facebook ...
    status: Mapped[str] = mapped_column(String(12), default="posted")   # posted | failed | skipped
    url: Mapped[str] = mapped_column(String(600), default="")
    detail: Mapped[str] = mapped_column(String(400), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LeadMagnet(Base):
    """สื่อแจกฟรี (คอร์ส/คู่มือ/เช็คลิสต์/เทมเพลต) — gate หลังอีเมล/แชร์ เพื่อเก็บลีด
    มีเวอร์ชันสาธารณะ (teaser) ให้ Google เก็บ+ติดอันดับ + เวอร์ชันเต็ม (content) ปลดล็อกด้วยอีเมล"""
    __tablename__ = "lead_magnets"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="guide")      # course | guide | checklist | template
    language: Mapped[str] = mapped_column(String(20), default="th")     # th | en (สื่อมีเวอร์ชันภาษาของตัวเอง)
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")          # คำโปรยสั้น (โชว์บนหน้า gate + meta)
    teaser_html: Mapped[str] = mapped_column(Text, default="")          # สารบัญ/เกริ่น โชว์ก่อนปลดล็อก (สาธารณะ ติดอันดับได้)
    content_html: Mapped[str] = mapped_column(Text, default="")         # เนื้อหาเต็ม (โชว์หลังกรอกอีเมล)
    cover_url: Mapped[str] = mapped_column(Text, default="")
    token: Mapped[str] = mapped_column(String(64), default="", index=True)   # ลิงก์ gate สาธารณะ
    require_share: Mapped[bool] = mapped_column(Boolean, default=False)      # ต้องกดแชร์ก่อนปลดล็อก (เพิ่ม reach)
    leads_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(300), default="")              # ว่าง=กำลังสร้าง/สำเร็จ · มีค่า=สร้างล้ม (กันค้าง building ตลอดกาล)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContactLead(Base):
    """ลีดจากฟอร์มติดต่อบนหน้าแรก (ผู้สนใจกรอกเอง) → แจ้งแอดมินทาง LINE ทันที"""
    __tablename__ = "contact_leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(60), default="")
    business: Mapped[str] = mapped_column(String(300), default="")
    keywords: Mapped[str] = mapped_column(Text, default="")            # คีย์เวิร์ดที่คาดหวัง (คั่นด้วย ,)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lead(Base):
    """ลีดที่เก็บได้จากสื่อแจกฟรี — เอาไปตามขายบริการ (funnel เนียนขาย)"""
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    magnet_id: Mapped[int | None] = mapped_column(ForeignKey("lead_magnets.id"), nullable=True, index=True)
    email: Mapped[str] = mapped_column(String(255), default="", index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
