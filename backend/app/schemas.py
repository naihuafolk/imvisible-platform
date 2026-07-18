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


class LoginRequest(BaseModel):
    email: str
    password: str


class ProjectCreate(BaseModel):
    name: str
    domain: str
    country: str = "ไทย"
    mode: str = "approve"
