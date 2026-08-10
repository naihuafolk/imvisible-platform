"""Pydantic request/response models"""
from pydantic import BaseModel, Field


class RankCheckRequest(BaseModel):
    keyword: str
    domain: str = Field(..., description="โดเมนที่ต้องการหาว่าติดอันดับไหม เช่น abc-beautyclinic.com")
    location_code: int | None = None
    language_code: str | None = None


class GSCSummaryRequest(BaseModel):
    site_url: str = Field(..., description="เช่น sc-domain:abc-beautyclinic.com หรือ https://abc-beautyclinic.com/")
    days: int = 28


class CitationSampleRequest(BaseModel):
    questions: list[str]
    brand_terms: list[str]
    domain: str
    engines: list[str] = ["openai", "gemini", "perplexity"]


class ProjectCitationRequest(BaseModel):
    # คำถามที่จะสุ่มถาม AI (ว่าง = ระบบเลือกจากแผนหัวข้อ/บทความจริงของโปรเจ็คให้เอง)
    questions: list[str] = []


class CredentialUpdate(BaseModel):
    kind: str                    # dataforseo | wordpress | gsc
    fields: dict = {}            # ฟิลด์ลับของบริการนั้น (ค่าว่าง = ไม่ตั้ง)


class CheckoutRequest(BaseModel):
    plan: str                    # pro | business


class TeamInvite(BaseModel):
    email: str
    role: str = "viewer"         # viewer | editor | admin


class ScheduleRequest(BaseModel):
    at: str                      # เวลาเผยแพร่ (ISO เช่น 2026-08-01T09:00)


class KeywordRequest(BaseModel):
    keyword: str


class GSCDaysRequest(BaseModel):
    days: int = 28


class ContentGenerateRequest(BaseModel):
    topic: str
    fmt: str = "บทความยาว"
    words: int = 1500


class PublishRequest(BaseModel):
    title: str
    html: str
    status: str = "draft"        # draft | publish
    url_path: str | None = None  # สำหรับ IndexNow ping


class MineRequest(BaseModel):
    seed: str = Field(..., description="หัวข้อธุรกิจ/สินค้า เช่น ครีมกันแดด")
    location_code: int | None = None
    language_code: str | None = None


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    name: str = ""
    accept_terms: bool = False    # ต้องยอมรับข้อกำหนด + นโยบายความเป็นส่วนตัว (PDPA)


class LoginRequest(BaseModel):
    email: str
    password: str


class ProjectCreate(BaseModel):
    name: str = ""
    domain: str = ""
    url: str = ""                    # ลูกค้าใส่แค่ลิงก์เว็บ → ระบบแตกเป็น domain/name/slug ให้เอง
    country: str = "ไทย"
    language: str = "th"
    mode: str = "approve"
    publish_mode: str = "managed"    # managed (เราโฮสต์ให้) | wordpress | none
    custom_domain: str = ""          # เช่น blog.abccoffee.com (ตั้ง CNAME มาที่เรา)
    keywords: list[str] = []         # คีย์เวิร์ด/หัวข้อเริ่มต้นที่ลูกค้าเลือก (AI ช่วยคิด) → ใช้ผลิตบทความแรกจริง
    keyword_pack: int = 50           # แพ็กคีย์เวิร์ดของลูกค้ารายนี้ (10/30/50) — โควตารวมที่ระบบติดตาม+ดัน
    source_type: str = "website"     # website (มีเว็บ) | facebook (มีแค่เพจ FB → เราโฮสต์บล็อกให้ + CTA ลิงก์ไปเพจ)
    facebook_url: str = ""           # ลิงก์เพจ Facebook (ใช้เมื่อ source_type=facebook)


class KeywordPackUpdate(BaseModel):
    pack: int = 50                   # ตั้งแพ็กคีย์เวิร์ดของโปรเจ็ค (10/30/50) — เฉพาะแอดมิน


class FacebookConvert(BaseModel):
    facebook_url: str = ""           # ลิงก์เพจ Facebook — ตั้งเป็นปุ่ม CTA ท้ายบทความ
    name: str = ""                   # (ทางเลือก) เปลี่ยนชื่อโปรเจ็คเป็นชื่อธุรกิจ


class SmsAlertUpdate(BaseModel):
    enabled: bool = False            # เปิดแจ้งเตือน SMS อันดับ (คีย์ติด/ขยับขึ้น) ของโปรเจ็คนี้
    to: str = ""                     # เบอร์ปลายทาง (0xxxxxxxxx หรือ +66... — ระบบแปลงเป็น E.164 ให้)


class KeywordSuggestRequest(BaseModel):
    url: str = ""                    # ลูกค้าวางลิงก์ → AI ช่วยคิดคีย์เวิร์ดจากเว็บ (ไม่ต้องคิดเอง)
    domain: str = ""
    name: str = ""
    language: str = "th"


class KeywordsAddRequest(BaseModel):
    keywords: list[str] = []         # เพิ่มคีย์เวิร์ด/หัวข้อให้โปรเจ็คที่กำลังทำงาน (ต่อท้าย · สูงสุดรวม 50)


class AeoQuestionsUpdate(BaseModel):
    questions: list[str] = []        # คำถาม AEO ที่ลูกค้าตั้งเอง (คำที่คนถาม AI จริง) → บันทึกแทนที่ · สูงสุด 30


class AdCreativeRequest(BaseModel):
    keyword: str = ""                # คีย์เวิร์ดที่จะร่างชุดโฆษณา Google Ads (RSA) ให้


class CtaUpdate(BaseModel):
    enabled: bool = False            # เปิดกล่องดักลูกค้าท้ายบทความ
    headline: str = ""               # หัวข้อ CTA
    text: str = ""                   # ข้อความรอง
    button: str = "ปรึกษาฟรี"        # ป้ายปุ่ม
    url: str = ""                    # ลิงก์ปุ่ม (signup/ไลน์/หน้าติดต่อ)


class PostCreate(BaseModel):
    title: str = ""                  # หัวข้อโพสต์
    content: str = ""                # เนื้อหา (HTML หรือข้อความธรรมดา — ระบบห่อ <p> ให้)
    cover_url: str = ""              # รูปปก (ไม่บังคับ)
    video_url: str = ""              # ลิงก์ YouTube → ฝังวิดีโอด้านบน (ไม่บังคับ)
    status: str = "published"        # published | draft


class PublishTargetUpdate(BaseModel):
    publish_mode: str = "managed"    # managed | wordpress | none
    custom_domain: str = ""


class ProjectModeUpdate(BaseModel):
    mode: str = "approve"            # auto (Full-Auto เผยแพร่เอง) | approve (ร่างรออนุมัติก่อนเผยแพร่)


class ProjectUpdate(BaseModel):
    name: str = ""                   # แก้ชื่อ/โดเมน (ลิงก์) ของโปรเจ็ค — ว่าง = ไม่เปลี่ยนฟิลด์นั้น
    domain: str = ""


class ProjectActiveUpdate(BaseModel):
    active: bool = True              # true = เปิดใช้ (ทำงานอัตโนมัติ) | false = พักไว้


class KeywordReportRequest(BaseModel):
    keyword: str = ""                # คีย์เวิร์ดหลัก/หัวข้อ (สำหรับรายงานขายลูกค้า)
    business: str = ""               # บริบทธุรกิจ (ช่วยให้คีย์ที่ดึงมาตรงขึ้น)
    limit: int = 30


class BacklinkOutreachRequest(BaseModel):
    url: str = ""                    # เว็บเป้าหมายที่จะติดต่อ
    title: str = ""                  # ชื่อหน้า/เว็บ (ประกอบการร่าง)
    kind: str = "mention"            # mention | resource | guest


class PantipRadarRequest(BaseModel):
    keyword: str = ""                # หัวข้อ/คีย์เวิร์ดที่อยากหากระทู้ Pantip ติดหน้า 1
    business: str = ""               # บริบทธุรกิจ (เสริม query ให้ตรงขึ้น)


class PantipReplyRequest(BaseModel):
    url: str = ""                    # ลิงก์กระทู้
    title: str = ""                  # หัวข้อกระทู้ (ใช้ร่างคำตอบ)
    snippet: str = ""                # ข้อความย่อจาก SERP (บริบท)
    brand: str = ""                  # แบรนด์ (ห้ามโฆษณาโต้ง ๆ) — ว่าง= ImVisible
    reference: str = ""              # ลิงก์อ้างอิงที่จะแนบถ้าเกี่ยวจริง (ว่างได้)


class LeadMagnetCreate(BaseModel):
    kind: str = "guide"              # course | guide | checklist | template
    topic: str = ""                  # หัวข้อสื่อที่อยากแจก
    require_share: bool = False       # ต้องกดแชร์ก่อนปลดล็อก (เพิ่ม reach)
    lang: str = ""                   # "" = ตามภาษาโปรเจ็ค · th · en · both (สร้างทั้งไทย+อังกฤษ)


class LeadUnlock(BaseModel):
    email: str = ""
    name: str = ""
    shared: bool = False


class ContactForm(BaseModel):
    name: str = ""
    phone: str = ""
    business: str = ""
    keywords: list[str] = []          # คีย์เวิร์ดที่คาดหวัง (สูงสุด 3)


class SiteCheckRequest(BaseModel):
    url: str = ""                     # ลิงก์เว็บที่จะตรวจสุขภาพ (สาธารณะ — หน้าแรก)
    keywords: list[str] = []          # คีย์เวิร์ดที่อยากติด (สูงสุด 3) → ประเมินการครอบคลุมบนหน้าเพจ


class SiteReportCreate(BaseModel):
    """พนักงานสร้าง 'ลิงก์รายงานสุขภาพเว็บ' ส่งลูกค้า (เก็บลีด) — ตรวจจริง + บันทึกเป็น snapshot"""
    url: str = ""                     # ลิงก์เว็บลูกค้า/ผู้สนใจ
    keywords: list[str] = []          # คีย์เวิร์ดที่อยากติด (สูงสุด 3)
    business_name: str = ""           # ชื่อธุรกิจ (โชว์บนหน้ารายงาน · ว่าง=ใช้โดเมน)


class ReportLeadCreate(BaseModel):
    """ผู้สนใจกรอกจากหน้ารายงานสาธารณะ เพื่อดูแผนแก้ + ขอให้ทีมช่วย (สาธารณะ ไม่ต้องล็อกอิน)"""
    name: str = ""
    phone: str = ""
    contact: str = ""                 # LINE ID / อีเมล (ช่องทางเสริม)
    message: str = ""


class ChannelUpdate(BaseModel):
    kind: str                        # line | facebook | telegram | x | linkedin | discord | mastodon | webhook
    ref: str = ""                    # facebook: page_id · line: userId/groupId (หรือ 'broadcast')
    token: str = ""                  # โทเคน (ส่งมาเฉพาะตอนตั้ง/เปลี่ยน · ว่าง = คงเดิม)
    enabled: bool = True


class DraftRequest(BaseModel):
    question: str                    # กระทู้/คำถามในชุมชนที่จะร่างคำตอบให้
    snippet: str = ""
    url: str = ""                    # ลิงก์บทความอ้างอิง (ใส่ถ้าเกี่ยวข้องจริง)


class SocialRadarRequest(BaseModel):
    keyword: str = ""                # หัวข้อ/คีย์เวิร์ดที่อยากหาหน้า Reddit/Quora/Medium ติดหน้า 1
    business: str = ""               # บริบทธุรกิจ (เสริม query ให้ตรงขึ้น)
    sites: list[str] = ["reddit.com", "quora.com", "medium.com"]  # แพลตฟอร์มที่จะสแกน (GEO)


class BacklinkGapsRequest(BaseModel):
    competitors: list[str] = []      # โดเมนคู่แข่ง (เช่น competitor.com) — หาว่าใครลิงก์หาพวกเขา
    domain: str = ""                 # โดเมนเราเอง (ตัดออกจากผล ไม่นับเป็นโอกาส) — ว่างได้
    limit: int = 100                 # จำนวน referring domains ต่อคู่แข่งที่ดึงมาวิเคราะห์


class ContentGapRequest(BaseModel):
    domain: str = ""                 # โดเมนเว็บของเรา (ตัดออกจากช่องว่าง = คีย์ที่เราติดแล้ว)
    competitors: list[str] = []      # โดเมนคู่แข่ง (สูงสุด 5 ราย — คุมเครดิต)
    limit: int = 100                 # จำนวนคีย์ต่อโดเมนที่ดึงมาเทียบ


class SnippetSniperRequest(BaseModel):
    keyword: str = ""                # คีย์เวิร์ดเดี่ยว (สะดวกกรณียิงคำเดียว)
    keywords: list[str] = []         # หลายคีย์พร้อมกัน (สูงสุด 8 คำ/รอบ = 8 SERP calls)


class FaqItem(BaseModel):
    q: str = ""                      # คำถามที่ลูกค้าถามบ่อย
    a: str = ""                      # คำตอบ


class SiteBrief(BaseModel):
    """brief สร้างเว็บแบบละเอียด — ป้อน IM WEB ให้ได้เว็บที่ดี + เก็บ 'วัตถุดิบ AEO/GEO' (FAQ/ที่ตั้ง/ติดต่อ)
    ที่จะ carry เข้าโปรเจกต์ตอน save → เครื่องยนต์โตเองเริ่มแบบเต็มแม็ก + ฝัง schema ให้ AI แนะนำได้"""
    # ธุรกิจ
    brand_name: str = ""
    biz_type: str = ""               # ประเภทธุรกิจ เช่น คาเฟ่ / คลินิก
    about: str = ""                  # เกี่ยวกับธุรกิจ
    usp: str = ""                    # จุดเด่น / ทำไมต้องเลือกเรา
    audience: str = ""               # กลุ่มลูกค้าเป้าหมาย
    products: str = ""               # สินค้า/บริการ (คั่นด้วย ,)
    price_info: str = ""             # ราคา/แพ็กเกจ (อิสระ · ไม่บังคับ)
    # ติดต่อ & ที่ตั้ง (วัตถุดิบ GEO / LocalBusiness)
    phone: str = ""
    line: str = ""                   # LINE id/ลิงก์
    email: str = ""
    facebook: str = ""               # URL เพจ
    instagram: str = ""              # URL/handle
    address: str = ""                # ที่อยู่ (มี = ทำ LocalBusiness schema)
    service_area: str = ""           # พื้นที่ให้บริการ เช่น กรุงเทพและปริมณฑล
    hours: str = ""                  # เวลาทำการ
    map_url: str = ""                # ลิงก์ Google Maps
    # เป้าหมาย & แบรนด์
    goal: str = ""                   # booking | order | call | chat | leads
    brand_color: str = ""            # สีหลัก (hex หรือคำ)
    logo_url: str = ""               # ลิงก์โลโก้
    vibe: str = ""                   # โทน/อารมณ์
    # AEO/GEO
    keywords: list[str] = []         # คีย์เวิร์ดที่อยากติด
    faqs: list[FaqItem] = []         # FAQ จริง → FAQPage schema (AEO) + aeo_questions ของโปรเจกต์


class ImwebGenerateRequest(BaseModel):
    brief: SiteBrief = Field(default_factory=SiteBrief)
    language: str = "th"             # ภาษาเว็บ
    motion_level: str = "high"       # ระดับ animation: low | high | max
    tier: str = "paid"               # paid | free (คุณภาพ engine)
    variants: int = 1                # จำนวนสไตล์ที่อยากได้ (1-3)


class ImwebSaveRequest(BaseModel):
    html: str = ""                   # HTML เว็บที่เลือก (จาก IM WEB) → โฮสต์เป็นหน้าแรก
    brief: SiteBrief = Field(default_factory=SiteBrief)   # brief เดิม → carry เข้าโปรเจกต์ + ฝัง schema
    language: str = "th"


class ImwebPrefillRequest(BaseModel):
    """วางลิงก์เว็บ/เพจเดิม → อ่านหน้าจริง + ให้ AI เรียบเรียงเป็นบรีฟ (ลูกค้าไม่ต้องกรอกเอง)"""
    url: str = ""


class PseoTopicsRequest(BaseModel):
    """pSEO โหมด 'ติดอันดับ' — เพิ่มหลายหัวข้อ unique 'บนโดเมนหลัก' ทีเดียว → เครื่องยนต์ผลิตหน้า on-domain เอง
    white-hat: หน้าอยู่บนโดเมนเดียว(สะสม authority) + เนื้อหา AI ต่างกันจริงต่อ variant (ไม่ใช่ doorway)"""
    project_id: int = 0              # 0 = โปรเจกต์หลัก (id ต่ำสุดของผู้ใช้ = โดเมนแข็งสุด)
    pattern: str = "รับทำเว็บ{x}"    # {x} = ตัวแปร · ไม่มี {x} = ต่อท้าย
    variants: list[str] = []         # เช่น คลินิกความงาม, ร้านอาหาร, โรงแรม, เชียงใหม่
    cluster: str = "pSEO"            # ป้ายคลัสเตอร์
    produce_now: bool = False        # เริ่มผลิตชุดแรกทันที (ไม่งั้นรอรอบอัตโนมัติ)
