"""
Billing (Stripe) — subscription จริง ผ่าน httpx (ไม่ผูก stripe SDK)
- create_checkout_session: สร้างลิงก์จ่ายเงิน (Stripe Checkout, mode=subscription)
- verify_webhook: ตรวจลายเซ็น Stripe จริง (HMAC-SHA256) ก่อนเชื่อ event
คีย์: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PRICE_PRO/BUSINESS
"""
import hashlib
import hmac
import json

import httpx

from app.config import settings

STRIPE_API = "https://api.stripe.com/v1"


def enabled() -> bool:
    return bool(settings.stripe_secret_key)


def price_for(plan: str) -> str:
    return {"pro": settings.stripe_price_pro,
            "business": settings.stripe_price_business}.get(plan, "")


def plan_for_price(price_id: str) -> str:
    if price_id and price_id == settings.stripe_price_business:
        return "business"
    if price_id and price_id == settings.stripe_price_pro:
        return "pro"
    return ""


async def create_checkout_session(user_id: int, email: str, plan: str,
                                  success_url: str, cancel_url: str) -> dict:
    """คืนลิงก์ Stripe Checkout สำหรับสมัครแพ็กเกจ (ผูก user ผ่าน client_reference_id + metadata)"""
    price = price_for(plan)
    if not enabled():
        raise RuntimeError("ยังไม่ได้ตั้งค่า STRIPE_SECRET_KEY")
    if not price:
        raise RuntimeError("ยังไม่ได้ตั้ง price_id ของแพ็กเกจ '%s'" % plan)
    data = {
        "mode": "subscription",
        "line_items[0][price]": price,
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(user_id),
        "customer_email": email,
        "metadata[plan]": plan,
        "metadata[user_id]": str(user_id),
        "subscription_data[metadata][plan]": plan,
        "subscription_data[metadata][user_id]": str(user_id),
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{STRIPE_API}/checkout/sessions", data=data,
                         auth=(settings.stripe_secret_key, ""))
        r.raise_for_status()
        j = r.json()
    return {"url": j.get("url"), "id": j.get("id")}


def verify_webhook(payload: bytes, sig_header: str) -> dict:
    """ตรวจลายเซ็น Stripe จริงตามสเปก (t=<ts>,v1=<hmac>) แล้วคืน event ที่ parse แล้ว
    ป้องกันการปลอม event มายิง webhook (ถ้าลายเซ็นไม่ตรง = โยน ValueError)"""
    secret = settings.stripe_webhook_secret
    if not secret:
        raise RuntimeError("ยังไม่ได้ตั้ง STRIPE_WEBHOOK_SECRET")
    parts = dict(p.split("=", 1) for p in (sig_header or "").split(",") if "=" in p)
    t, v1 = parts.get("t"), parts.get("v1")
    if not (t and v1):
        raise ValueError("bad stripe signature header")
    signed = (t + ".").encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v1):
        raise ValueError("stripe signature mismatch")
    return json.loads(payload.decode("utf-8"))


def sign_payload(payload: bytes, timestamp: int) -> str:
    """(ใช้ในเทสต์) สร้าง header ลายเซ็นแบบเดียวกับที่ Stripe ส่ง"""
    signed = (str(timestamp) + ".").encode("utf-8") + payload
    v1 = hmac.new(settings.stripe_webhook_secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return "t=%d,v1=%s" % (timestamp, v1)
