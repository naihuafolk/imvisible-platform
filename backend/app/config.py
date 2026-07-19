"""
การตั้งค่า (อ่านจาก .env) + สถานะการเชื่อมต่อของแต่ละ integration
ตรงกับหน้า "การตั้งค่า > การเชื่อมต่อ" ในแดชบอร์ด
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 1) SERP
    dataforseo_login: str = ""
    dataforseo_password: str = ""
    serp_location_code: int = 2764   # Thailand
    serp_language_code: str = "th"

    # 2) Google Search Console
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    # 3) LLM
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # 4) AI Citation (Prompt Sampling)
    perplexity_api_key: str = ""
    perplexity_model: str = "sonar"

    # 5) Publish
    wordpress_base_url: str = ""
    wordpress_username: str = ""
    wordpress_app_password: str = ""
    webflow_api_token: str = ""
    webflow_collection_id: str = ""

    # 5b) Managed Hosting — โฮสต์บล็อกลูกค้าให้เอง (ลูกค้าใส่แค่ลิงก์ก็ใช้ได้)
    managed_base_domain: str = "imvisible.tech"   # เสิร์ฟที่ {slug}.imvisible.tech และ /blog/{slug}
    managed_scheme: str = "https"

    # 6) IndexNow
    indexnow_key: str = ""
    indexnow_host: str = ""

    # 7) GA4
    ga4_property_id: str = ""

    # 8) LINE
    line_channel_access_token: str = ""
    line_default_to: str = ""

    # 9) ModelArk (BytePlus) — Seedream (รูป) + Seedance (วิดีโอ)
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3"
    ark_image_model: str = "dola-seedream-5-0-pro-260628"
    ark_video_model: str = ""

    # โครงสร้างพื้นฐาน (คิวงาน + ฐานข้อมูล ตาม stack หน้า 7)
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = ""   # เช่น postgresql+asyncpg://rankpilot:rankpilot@localhost:5432/rankpilot

    # Auth (JWT) — production ตั้ง JWT_SECRET ยาว ๆ (Render ใช้ generateValue ให้)
    jwt_secret: str = "dev-only-secret-change-me-in-production-please-32b"
    jwt_expire_hours: int = 168   # 7 วัน

    cors_origins: str = "*"


settings = Settings()


def integration_status() -> list[dict]:
    """คืนสถานะว่าแต่ละ integration ตั้งค่าคีย์ครบหรือยัง (required=จำเป็นก่อนวัดผลจริง)"""
    s = settings
    return [
        {"id": "serp",     "name": "SERP API (DataForSEO)",            "required": True,
         "connected": bool(s.dataforseo_login and s.dataforseo_password)},
        {"id": "gsc",      "name": "Google Search Console",            "required": True,
         "connected": bool(s.google_client_id and s.google_client_secret and s.google_refresh_token)},
        {"id": "llm",      "name": "LLM (Claude/GPT/Gemini)",          "required": True,
         "connected": bool(s.anthropic_api_key or s.openai_api_key or s.gemini_api_key)},
        {"id": "citation", "name": "AI Citation (Prompt Sampling)",    "required": True,
         "connected": bool(s.openai_api_key or s.gemini_api_key or s.perplexity_api_key)},
        {"id": "wordpress","name": "WordPress REST API",               "required": True,
         "connected": bool(s.wordpress_base_url and s.wordpress_username and s.wordpress_app_password)},
        {"id": "webflow",  "name": "Webflow API",                      "required": False,
         "connected": bool(s.webflow_api_token and s.webflow_collection_id)},
        {"id": "indexnow", "name": "IndexNow",                         "required": False,
         "connected": bool(s.indexnow_key and s.indexnow_host)},
        {"id": "ga4",      "name": "Google Analytics 4",               "required": False,
         "connected": bool(s.ga4_property_id and s.google_refresh_token)},
        {"id": "line",     "name": "LINE Messaging API",               "required": False,
         "connected": bool(s.line_channel_access_token)},
        {"id": "modelark", "name": "ModelArk (Seedream/Seedance)",      "required": False,
         "connected": bool(s.ark_api_key)},
    ]
