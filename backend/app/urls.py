"""
ตัวช่วยสร้าง slug / URL สาธารณะ (ไม่พึ่ง FastAPI — ใช้ได้ทั้งฝั่ง API และ Celery worker)
"""
import re

from app.config import settings


def slugify(text: str, fallback: str = "post") -> str:
    """ascii slug อ่านง่าย; ถ้าเป็นไทยล้วน (เหลือว่าง) คืน fallback"""
    t = (text or "").strip().lower()
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    t = re.sub(r"[\s_-]+", "-", t).strip("-")
    ascii_only = re.sub(r"[^a-z0-9-]", "", t).strip("-")
    return ascii_only or fallback


def project_slug_from_domain(domain: str) -> str:
    d = (domain or "").strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0].removeprefix("www.")
    base = d.split(".")[0] if d else ""
    return slugify(base, "site")


def article_slug(title: str, article_id: int) -> str:
    """slug คงที่ต่อบทความ (แนบ id กันชนกัน + รองรับหัวข้อไทยล้วน)"""
    return "%s-%d" % (slugify(title, "post"), int(article_id))


def project_public_home(proj) -> str:
    """หน้าแรกบล็อกลูกค้า — custom domain ถ้าเชื่อมแล้ว ไม่งั้น path บนโดเมนหลัก"""
    scheme = settings.managed_scheme
    if getattr(proj, "custom_domain", ""):
        return "%s://%s" % (scheme, proj.custom_domain)
    return "%s://%s/blog/%s" % (scheme, settings.managed_base_domain, proj.slug)


def public_url_for(proj, art) -> str:
    """URL สาธารณะของบทความ (บันทึกลง Article.url + ใช้ ping index)"""
    key = getattr(art, "slug", "") or str(art.id)
    if getattr(proj, "custom_domain", ""):
        return "%s://%s/a/%s" % (settings.managed_scheme, proj.custom_domain, key)
    return "%s://%s/blog/%s/%s" % (settings.managed_scheme, settings.managed_base_domain, proj.slug, key)
