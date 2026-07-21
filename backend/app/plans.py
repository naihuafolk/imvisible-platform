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
}
DEFAULT_PLAN = "free"


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
