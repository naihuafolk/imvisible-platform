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
    google_redirect_uri: str = ""   # เช่น https://api.imvisible.tech/api/oauth/google/callback (ต้องตรงกับที่ตั้งใน Google Console)

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

    # 7b) PageSpeed Insights (Core Web Vitals / ความเร็วจริง) — ไม่มีคีย์ก็ใช้ได้ (rate-limited)
    pagespeed_api_key: str = ""

    # 8) LINE
    line_channel_access_token: str = ""
    line_default_to: str = ""

    # 9) ModelArk (BytePlus) — Seedream (รูป) + Seedance (วิดีโอ)
    ark_api_key: str = ""
    ark_base_url: str = "https://ark.ap-southeast.bytepluses.com/api/v3"
    ark_image_model: str = "dola-seedream-5-0-pro-260628"
    ark_video_model: str = ""
    # 9b) fal.ai (FLUX) — ผู้ให้บริการรูปทางเลือก · คีย์รูปแบบ id:secret · ถ้าตั้งไว้จะใช้ fal ก่อน ModelArk
    fal_key: str = ""
    fal_image_model: str = "fal-ai/bytedance/seedream/v4/text-to-image"   # Seedream v4 (ByteDance) — รูปสวยสุดสำหรับ editorial · ทางเลือก: flux-pro/v1.1-ultra
    # 9c) งบต้นทุน API/เดือน (บาท) สำหรับแจ้งเตือนแอดมิน — 0 = ไม่ตั้งงบ (ไม่เตือน)
    cost_budget_thb: int = 0
    # 9e) ประตูคุณภาพ: คะแนน AEO ขั้นต่ำที่จะ 'เผยแพร่อัตโนมัติ' (ต่ำกว่านี้ = เก็บร่าง+ปรับก่อน) — พรีเมียมเท่านั้น
    min_publish_score: int = 82
    # 9d) Google Indexing API (instant indexing) — วาง JSON ของ service account ทั้งก้อน
    #     (ต้องเพิ่ม service account เป็น owner ของ property ใน GSC ก่อนถึงจะแจ้ง index ได้)
    google_indexing_sa_json: str = ""

    # โครงสร้างพื้นฐาน (คิวงาน + ฐานข้อมูล ตาม stack หน้า 7)
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = ""   # เช่น postgresql+asyncpg://rankpilot:rankpilot@localhost:5432/rankpilot

    # Auth (JWT) — production ตั้ง JWT_SECRET ยาว ๆ (Render ใช้ generateValue ให้)
    jwt_secret: str = "dev-only-secret-change-me-in-production-please-32b"
    jwt_expire_hours: int = 168   # 7 วัน

    cors_origins: str = "*"

    # แอดมิน/เทสต์ (ไม่ต้องผ่าน Stripe): อีเมลในนี้ได้แพ็กเกจ business อัตโนมัติ (คั่นด้วย ,)
    admin_emails: str = ""

    # เปิด/ปิดรับสมัครสมาชิกทั่วไป — false = ปิด (soft-launch เหลือแค่ล็อกอิน · แอดมินสร้างบัญชีเองได้)
    registration_open: bool = True

    # Production hardening
    app_env: str = "dev"                 # dev | prod (prod = บังคับ JWT_SECRET + HSTS)
    sentry_dsn: str = ""                 # ตั้ง = เปิด error monitoring (ต้องลง sentry-sdk)
    rate_limit_per_min: int = 30         # จำกัดคำขอ auth ต่อ IP ต่อนาที (กัน brute-force)

    # Email (รายงานรายสัปดาห์ / แจ้งเตือน)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""              # เช่น "ImVisible <no-reply@imvisible.tech>"

    # Billing (Stripe) — subscription จริง + webhook
    app_base_url: str = "http://localhost:8080"   # ใช้ทำ success/cancel URL หลังจ่ายเงิน
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""           # price_id ของแพ็กเกจ Pro
    stripe_price_business: str = ""      # price_id ของแพ็กเกจ Business


DEV_JWT_DEFAULT = "dev-only-secret-change-me-in-production-please-32b"


def is_prod() -> bool:
    return settings.app_env.strip().lower().startswith("prod")


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
         "connected": bool(s.openai_api_key or s.gemini_api_key or s.perplexity_api_key or s.anthropic_api_key)},
        {"id": "wordpress","name": "WordPress REST API",               "required": True,
         "connected": bool(s.wordpress_base_url and s.wordpress_username and s.wordpress_app_password)},
        # หมายเหตุ: Webflow ยังไม่มี connector จริง จึงไม่โฆษณาเป็น integration (กันอ้างของที่ยังไม่มี)
        {"id": "indexnow", "name": "IndexNow",                         "required": False,
         "connected": bool(s.indexnow_key and s.indexnow_host)},
        {"id": "ga4",      "name": "Google Analytics 4",               "required": False,
         "connected": bool(s.ga4_property_id and s.google_refresh_token)},
        {"id": "line",     "name": "LINE Messaging API",               "required": False,
         "connected": bool(s.line_channel_access_token)},
        {"id": "modelark", "name": "ModelArk (Seedream/Seedance)",      "required": False,
         "connected": bool(s.ark_api_key)},
    ]
