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


class KeywordSuggestRequest(BaseModel):
    url: str = ""                    # ลูกค้าวางลิงก์ → AI ช่วยคิดคีย์เวิร์ดจากเว็บ (ไม่ต้องคิดเอง)
    domain: str = ""
    name: str = ""
    language: str = "th"


class KeywordsAddRequest(BaseModel):
    keywords: list[str] = []         # เพิ่มคีย์เวิร์ด/หัวข้อให้โปรเจ็คที่กำลังทำงาน (ต่อท้าย · สูงสุดรวม 50)


class PublishTargetUpdate(BaseModel):
    publish_mode: str = "managed"    # managed | wordpress | none
    custom_domain: str = ""


class ChannelUpdate(BaseModel):
    kind: str                        # line | facebook | telegram | x | linkedin | discord | mastodon | webhook
    ref: str = ""                    # facebook: page_id · line: userId/groupId (หรือ 'broadcast')
    token: str = ""                  # โทเคน (ส่งมาเฉพาะตอนตั้ง/เปลี่ยน · ว่าง = คงเดิม)
    enabled: bool = True


class DraftRequest(BaseModel):
    question: str                    # กระทู้/คำถามในชุมชนที่จะร่างคำตอบให้
    snippet: str = ""
    url: str = ""                    # ลิงก์บทความอ้างอิง (ใส่ถ้าเกี่ยวข้องจริง)
