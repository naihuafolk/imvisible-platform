"""
โมเดลฐานข้อมูล (SQLAlchemy 2.0) — เก็บผลจริงของแต่ละโปรเจ็ค
ตาม stack หน้า 7: PostgreSQL + Vector DB (pgvector)
คอลัมน์ embedding ใช้ pgvector สำหรับวิเคราะห์คลัสเตอร์ (M6)
"""
from datetime import datetime

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, LargeBinary, func
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
    mode: Mapped[str] = mapped_column(String(20), default="auto")   # auto (เผยแพร่เอง — ค่าเริ่มต้น) | approve (รออนุมัติ — เปิดเมื่อลูกค้าต้องการรีวิวก่อน เช่น เนื้อหาการแพทย์)
    active: Mapped[bool] = mapped_column(Boolean, default=True)      # true = ทำงานอัตโนมัติ | false = พักไว้ (หยุดผลิต/วัดอันดับ/citation · ข้อมูลเดิมอยู่ครบ)
    freshness_days: Mapped[int] = mapped_column(Integer, default=120)
    keyword_pack: Mapped[int] = mapped_column(Integer, default=50)      # โควตาคีย์เวิร์ดของลูกค้ารายนี้ (10/30/50) — แอดมินตั้ง
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=False)   # แจ้งเตือน SMS เมื่อคีย์ติด/ขยับขึ้น
    sms_to: Mapped[str] = mapped_column(String(40), default="")         # เบอร์ปลายทาง SMS (E.164 เช่น +66...)
    lead_line_to: Mapped[str] = mapped_column(String(80), default="")    # LINE userId/groupId 'ของลูกค้าเจ้าของธุรกิจ' → ส่งลีดที่เก็บได้ให้เขาตรง (ไม่ใช่แค่แอดมินกลาง)
    lead_email: Mapped[str] = mapped_column(String(255), default="")     # อีเมลลูกค้าสำหรับรับลีด/รายงาน (สำรอง)
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
    home_html: Mapped[str] = mapped_column(Text, default="")                     # HTML หน้าแรกที่ IM WEB สร้าง (โฮสต์เป็นเว็บจริง) — ว่าง=ใช้หน้าบล็อกปกติ
    report_token: Mapped[str] = mapped_column(String(64), default="", index=True)  # โทเคนลิงก์รายงานสาธารณะ (ส่งให้ลูกค้าเปิดดูได้โดยไม่ต้องล็อกอิน)
    ai_competitors: Mapped[str] = mapped_column(Text, default="")               # แบรนด์ที่ AI แนะนำในหมวดเรา (JSON) — คู่แข่งที่ต้องแซงในสนาม AEO
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
    stage: Mapped[str] = mapped_column(String(120), default="")              # ขั้นตอนที่กำลังทำ (เขียน→รูป/วิดีโอ→เสร็จ) โชว์ความคืบหน้า
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
    phone: Mapped[str] = mapped_column(String(60), default="")           # ลีดจากฟอร์มบทความมักให้เบอร์ (ไทยนิยมโทร)
    name: Mapped[str] = mapped_column(String(200), default="")
    message: Mapped[str] = mapped_column(Text, default="")               # ข้อความ/สิ่งที่ลูกค้าปลายทางอยากได้
    shared: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---- เพิ่มต่อท้าย backend/app/db/models.py (คลาสใหม่ · ตาราง auto-create ตอน startup ผ่าน create_all) ----
class AeoStudySnapshot(Base):
    """#12 Data Study / Digital PR — 'สำรวจความพร้อม AEO ของเว็บไทย' (linkable asset)
    เก็บผลสแกนหน้าแรกของเว็บไทย 'จริง' (จาก sitecheck.check_url) 1 แถวต่อการสแกน 1 เว็บ 1 รอบ
    แล้ว aggregate เป็นสถิติสาธารณะที่นักข่าว/บล็อกอ้างอิงได้ (= backlink) · ตัวเลขจริงล้วน ไม่กุ
    ok=False = เปิดเว็บ/สแกนไม่ได้ (เก็บไว้บอก coverage แต่ไม่นับในค่าเฉลี่ย)"""
    __tablename__ = "aeo_study_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)          # โดเมนล้วน (ตัด scheme/www/path)
    ok: Mapped[bool] = mapped_column(Boolean, default=False)              # สแกนสำเร็จไหม (อ่าน HTML หน้าแรกได้)
    aeo_score: Mapped[int | None] = mapped_column(Integer, nullable=True) # คะแนน AEO 0-100 (None ถ้าสแกนล้ม)
    aeo_grade: Mapped[str] = mapped_column(String(2), default="")         # A/B/C/D
    seo_score: Mapped[int | None] = mapped_column(Integer, nullable=True) # คะแนน SEO 0-100 (None ถ้าสแกนล้ม)
    has_schema: Mapped[bool] = mapped_column(Boolean, default=False)      # มี JSON-LD ที่ valid
    has_faq: Mapped[bool] = mapped_column(Boolean, default=False)         # มีสัญญาณ Q&A/FAQ (FAQPage หรือหัวข้อคำถาม)
    has_entity: Mapped[bool] = mapped_column(Boolean, default=False)      # ประกาศตัวตนแบรนด์ (Organization schema)
    has_llms: Mapped[bool] = mapped_column(Boolean, default=False)        # มีไฟล์ /llms.txt
    note: Mapped[str] = mapped_column(String(300), default="")           # เหตุผลกรณีล้ม / หมายเหตุ
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SiteReport(Base):
    """รายงานสุขภาพเว็บสาธารณะ (แชร์ได้) — พนักงานสร้างลิงก์ให้ลูกค้า/ผู้สนใจเปิดดู
    หน้ารายงานโชว์คะแนน SEO + AEO/GEO 'จริง' (จาก sitecheck.check_url) + ปัญหาที่เจอ
    'แผนแก้ + ให้ทีมทำให้' ถูก gate ไว้หลังฟอร์ม → กรอกชื่อ/เบอร์ = ได้ลีด (เด้ง LINE แอดมิน)
    = ทำให้ 'ทั้งคนและเว็บขายตัวเอง': เว็บดึงคนมา (แชร์ได้) + คนคัดตัวเอง (เห็นคะแนน→ขอให้ช่วย)
    data_json = ผลตรวจเต็มตอนสร้าง (snapshot · ไม่ต้องยิงซ้ำ) · ตัวเลขจริงล้วน ไม่กุ"""
    __tablename__ = "site_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(64), default="", index=True)   # ลิงก์สาธารณะ (secrets.token_urlsafe)
    url: Mapped[str] = mapped_column(String(600), default="")                # ลิงก์ที่ตรวจ (base https://domain)
    domain: Mapped[str] = mapped_column(String(255), default="", index=True) # โดเมนล้วน
    business_name: Mapped[str] = mapped_column(String(300), default="")      # ชื่อธุรกิจลูกค้า (พนักงานกรอก · ว่าง=ใช้โดเมน)
    keywords: Mapped[str] = mapped_column(Text, default="")                  # คีย์เวิร์ดที่ประเมิน (คั่นด้วย ,)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)  # พนักงานที่สร้าง
    score: Mapped[int] = mapped_column(Integer, default=0)                   # SEO 0-100 (denorm ไว้โชว์ในลิสต์)
    grade: Mapped[str] = mapped_column(String(2), default="")
    aeo_score: Mapped[int] = mapped_column(Integer, default=0)               # AEO/GEO 0-100
    aeo_grade: Mapped[str] = mapped_column(String(2), default="")
    data_json: Mapped[str] = mapped_column(Text, default="")                 # ผลตรวจเต็ม (json) ตอนสร้าง — ใช้เรนเดอร์หน้า
    leads_count: Mapped[int] = mapped_column(Integer, default=0)             # กี่คนที่ขอให้ช่วย (unlock แผนแก้)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportLead(Base):
    """ลีดจากหน้ารายงานสุขภาพเว็บ — ผู้สนใจกรอกชื่อ/เบอร์เพื่อดูแผนแก้ + ขอให้ทีมช่วย
    เด้งแจ้ง LINE แอดมินทันที + เก็บไว้เป็น 'รายชื่อโทรตามปิดการขาย' ในแอดมิน"""
    __tablename__ = "report_leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("site_reports.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(60), default="")
    contact: Mapped[str] = mapped_column(String(255), default="")            # LINE ID / อีเมล (ช่องทางเสริม)
    message: Mapped[str] = mapped_column(Text, default="")                   # ข้อความ/สิ่งที่อยากได้
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutreachTask(Base):
    """คิว backlink/outreach ต่อโปรเจ็ค — ระบบเก็บ 'แหล่งที่ควรขอลิงก์' อัตโนมัติรายสัปดาห์
    (จาก Competitor Backlink Gap จริง) แล้วคนตามสถานะ + กดส่งเอง · white-hat: ไม่ auto-โพสต์/ไม่ซื้อลิงก์
    ตารางสร้างเองตอน startup (create_all)"""
    __tablename__ = "outreach_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    source_domain: Mapped[str] = mapped_column(String(255), default="", index=True)   # เว็บเป้าที่จะไปขอลิงก์
    kind: Mapped[str] = mapped_column(String(40), default="competitor-gap")            # competitor-gap | resource | mention
    reason: Mapped[str] = mapped_column(String(400), default="")                       # เช่น "ลิงก์ให้คู่แข่ง 3 เจ้า: a, b, c"
    authority: Mapped[int] = mapped_column(Integer, default=0)                         # backlinks/rank ของแหล่ง (ประกอบการตัดสินใจ)
    status: Mapped[str] = mapped_column(String(20), default="todo", index=True)        # todo | contacted | won | skip
    note: Mapped[str] = mapped_column(Text, default="")                                # โน้ตของทีม (ติดต่อใคร/ผลเป็นไง)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WebRequest(Base):
    """คำขอสร้างเว็บจากลูกค้า — แอดมินส่ง 'ลิงก์ฟอร์ม' ให้ลูกค้ากรอก → submit → เข้าคิวอนุมัติ →
    อนุมัติแล้วระบบสร้างโปรเจ็ค+เว็บให้ → ลูกค้ารอดูแบบ (preview) · ตารางสร้างเองตอน startup"""
    __tablename__ = "web_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    business_name: Mapped[str] = mapped_column(String(300), default="")
    biz_type: Mapped[str] = mapped_column(String(120), default="")          # ประเภทธุรกิจ (คาเฟ่/คลินิก/ร้านค้า…)
    contact: Mapped[str] = mapped_column(String(255), default="")           # เบอร์/LINE/อีเมล ติดต่อกลับ
    links: Mapped[str] = mapped_column(Text, default="")                    # ลิงก์ที่มี (FB/เว็บเดิม/IG) — คั่นบรรทัด/comma
    detail: Mapped[str] = mapped_column(Text, default="")                   # อยากได้เว็บแบบไหน/ข้อมูลเพิ่ม
    language: Mapped[str] = mapped_column(String(10), default="th")         # th | en (เน้นลูกค้าต่างชาติ = en)
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)   # new | approved | rejected
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)  # โปรเจ็คที่สร้างหลังอนุมัติ
    preview_url: Mapped[str] = mapped_column(String(600), default="")       # ลิงก์ให้ลูกค้าดูแบบ
    note: Mapped[str] = mapped_column(Text, default="")                     # โน้ตแอดมิน
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UploadedImage(Base):
    """รูปที่ลูกค้าแนบมาตอนกรอกฟอร์มขอทำเว็บ — เก็บ bytes ใน DB (จำนวนน้อย/ต่อลูกค้า) → เสิร์ฟผ่าน /api/media/{id}
    ตอนสร้างเว็บ ระบบดึงรูปพวกนี้ไปแทรกใน home_html (แกลเลอรี/hero) แทนรูป stock · ตารางสร้างเองตอน startup"""
    __tablename__ = "uploaded_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    web_request_id: Mapped[int | None] = mapped_column(ForeignKey("web_requests.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    content_type: Mapped[str] = mapped_column(String(60), default="image/jpeg")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
