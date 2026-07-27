"""
แพ็กเกจ + โควตา — จำกัดการใช้งานตามแพ็กเกจจริง (บังคับก่อนสร้างโปรเจ็ค/ผลิตบทความ)
ตัวเลขอ้างอิงจากโมเดลธุรกิจในเอกสารโครงการ (ปรับได้ที่เดียว)
"""
PLANS: dict = {
    "free": {"key": "free", "label": "Free", "projects": 1, "articles_month": 4,
             "price_thb": 0, "features": ["1 โปรเจ็ค", "4 บทความ/เดือน", "โฮสต์บล็อกให้"]},
    "pro": {"key": "pro", "label": "Pro", "projects": 3, "articles_month": 60,
            "price_thb": 2900, "features": ["3 โปรเจ็ค", "60 บทความ/เดือน", "วัดอันดับ+AI citation", "กระจายโซเชียล"]},
    "business": {"key": "business", "label": "Business", "projects": 10, "articles_month": 200,
                 "price_thb": 7900, "features": ["10 โปรเจ็ค", "200 บทความ/เดือน", "ทุกฟีเจอร์ Pro", "custom domain"]},
    # แอดมิน/เจ้าของแพลตฟอร์ม — ไม่จำกัด (ไม่อยู่ในหน้าราคา · ให้ผ่าน ADMIN_EMAILS เท่านั้น)
    "admin": {"key": "admin", "label": "แอดมิน (ไม่จำกัด)", "projects": 100000, "articles_month": 100000,
              "price_thb": 0, "features": ["ไม่จำกัดโปรเจ็ค", "ไม่จำกัดบทความ", "ทุกฟีเจอร์"]},
}
DEFAULT_PLAN = "free"

# ── แพ็กคีย์เวิร์ด (ต่อ 'โปรเจ็ค/ลูกค้า 1 ราย') — โควตาจำนวนคีย์เวิร์ดที่ระบบติดตาม+ดัน ───
# ตอนนี้แอดมินตั้งให้แต่ละลูกค้าเอง · โครงสร้างพร้อมเปิดให้ลูกค้าเลือกเองภายหลัง (ผูกบิลลิ่ง)
KEYWORD_PACKS: list[int] = [10, 30, 50]
DEFAULT_PACK = 50                       # โปรเจ็คเดิม/ค่าเริ่มต้น = 50 (ตรงกับที่เคยขาย "สูงสุด 50")


def normalize_pack(n, default: int = DEFAULT_PACK) -> int:
    """แปลงค่าแพ็กที่รับเข้ามา → เลขแพ็กที่ถูกต้อง (10/30/50) · ค่าอื่นปัดขึ้นแพ็กที่ใกล้สุด"""
    try:
        v = int(n)
    except (TypeError, ValueError):
        return default
    if v in KEYWORD_PACKS:
        return v
    for pk in KEYWORD_PACKS:             # ปัดขึ้นแพ็กที่ครอบคลุมจำนวนที่ขอ
        if v <= pk:
            return pk
    return KEYWORD_PACKS[-1]             # เกิน 50 → 50


def normalize(plan: str | None) -> str:
    """map ค่าที่เก็บใน User.plan → คีย์แพ็กเกจที่รู้จัก (ค่าเก่า/ไม่รู้จัก → free)"""
    p = (plan or "").strip().lower()
    if p in PLANS:
        return p
    if "business" in p or "scale" in p:
        return "business"
    if "pro" in p:
        return "pro"
    return DEFAULT_PLAN


def limits(plan: str | None) -> dict:
    return PLANS[normalize(plan)]


def public_list() -> list[dict]:
    return [PLANS[k] for k in ("free", "pro", "business")]
