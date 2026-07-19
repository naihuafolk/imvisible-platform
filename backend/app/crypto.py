"""
เข้ารหัส/ถอดรหัสข้อมูลลับที่เก็บใน DB (โทเคนช่องทางกระจาย LINE/Facebook ฯลฯ)
คีย์ derive จาก JWT_SECRET — ตั้ง JWT_SECRET ยาว ๆ ใน production (อย่าใช้ค่า dev)
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256((settings.jwt_secret or "dev-secret").encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def enc(plain: str) -> str:
    """คืน ciphertext (str) — ค่าว่างคืนว่าง"""
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def dec(token: str) -> str:
    """ถอดรหัส — ถ้าถอดไม่ได้ (คีย์เปลี่ยน/ข้อมูลเสีย) คืนว่าง"""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""
