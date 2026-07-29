"""
แจ้งเตือน / ส่งรายงาน — อีเมล (SMTP) + LINE (reuse โทเคนกลาง)
ใช้ส่ง 'รายงานรายสัปดาห์' จากผลจริง (คะแนน AEO + อันดับ + citation)
"""
import asyncio
import smtplib
import ssl
from email.mime.text import MIMEText

import httpx

from app.config import settings


def email_enabled() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def _send_email_sync(to: str, subject: str, html: str) -> None:
    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    ctx = ssl.create_default_context()
    if int(settings.smtp_port) == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, 465, context=ctx, timeout=30) as srv:
            if settings.smtp_user:
                srv.login(settings.smtp_user, settings.smtp_password)
            srv.sendmail(settings.smtp_from, [to], msg.as_string())
    else:
        with smtplib.SMTP(settings.smtp_host, int(settings.smtp_port) or 587, timeout=30) as srv:
            srv.starttls(context=ctx)
            if settings.smtp_user:
                srv.login(settings.smtp_user, settings.smtp_password)
            srv.sendmail(settings.smtp_from, [to], msg.as_string())


async def send_email(to: str, subject: str, html: str) -> bool:
    """ส่งอีเมล (smtplib เป็น blocking → รันใน thread) — คืน True ถ้าส่งได้"""
    if not (email_enabled() and to):
        return False
    await asyncio.to_thread(_send_email_sync, to, subject, html)
    return True


def sms_ready() -> bool:
    """เซิร์ฟเวอร์พร้อมส่ง SMS ไหม (ต้องมี Account SID + วิธียืนยันตัวตน + ต้นทาง)"""
    has_auth = bool((settings.twilio_api_key_sid and settings.twilio_api_key_secret)
                    or settings.twilio_auth_token)
    has_from = bool(settings.twilio_from or settings.twilio_messaging_service_sid)
    return bool(settings.twilio_account_sid and has_auth and has_from)


def normalize_phone(raw: str, default_cc: str = "66") -> str:
    """แปลงเบอร์ไทยเป็นรูปแบบสากล E.164 (+66...) — 0987893988 → +66987893988
    ถ้าใส่ +.. มาแล้วคงเดิม · ไม่รู้จักรูปแบบ = คืนค่าที่ล้างช่องว่างแล้ว"""
    s = "".join(ch for ch in (raw or "") if ch.isdigit() or ch == "+").strip()
    if not s:
        return ""
    if s.startswith("+"):
        return s
    if s.startswith("00"):
        return "+" + s[2:]
    if s.startswith("0"):                      # เบอร์ในประเทศ → เติมรหัสประเทศ
        return "+" + default_cc + s[1:]
    if s.startswith(default_cc):
        return "+" + s
    return "+" + s


async def send_sms_detail(to: str, text: str) -> dict:
    """ส่ง SMS ผ่าน Twilio + คืนเหตุผลจริง (โปร่งใส) — log ทุกกรณีให้เห็นใน docker logs
    ไม่ปิดบัง: ถ้า Twilio ปฏิเสธจะคืน code+message จริงของ Twilio กลับมา"""
    acct = settings.twilio_account_sid
    to_e164 = normalize_phone(to)
    if not sms_ready():
        miss = []
        if not settings.twilio_account_sid:
            miss.append("TWILIO_ACCOUNT_SID")
        if not (settings.twilio_api_key_sid and settings.twilio_api_key_secret) and not settings.twilio_auth_token:
            miss.append("TWILIO_AUTH_TOKEN หรือ (TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET)")
        if not (settings.twilio_from or settings.twilio_messaging_service_sid):
            miss.append("TWILIO_FROM หรือ TWILIO_MESSAGING_SERVICE_SID")
        reason = "Twilio ยังไม่พร้อม ขาด env: " + ", ".join(miss)
        print("[SMS] ✗ " + reason)
        return {"ok": False, "reason": reason}
    if not to_e164:
        print("[SMS] ✗ เบอร์ปลายทางว่าง/ไม่ถูกต้อง: %r" % (to,))
        return {"ok": False, "reason": "เบอร์ปลายทางว่างหรือไม่ถูกต้อง"}
    if settings.twilio_api_key_sid and settings.twilio_api_key_secret:
        auth = (settings.twilio_api_key_sid, settings.twilio_api_key_secret)
    else:
        auth = (acct, settings.twilio_auth_token)
    data = {"To": to_e164, "Body": text[:1500]}
    if settings.twilio_messaging_service_sid:
        data["MessagingServiceSid"] = settings.twilio_messaging_service_sid
    else:
        data["From"] = settings.twilio_from
    url = "https://api.twilio.com/2010-04-01/Accounts/%s/Messages.json" % acct
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(url, data=data, auth=auth)
    except Exception as e:  # noqa: BLE001
        print("[SMS] ✗ เชื่อม Twilio ไม่ได้: %r" % e)
        return {"ok": False, "reason": "เชื่อม Twilio ไม่ได้: %s" % e}
    if r.status_code in (200, 201):
        print("[SMS] ✓ ส่งถึง %s สำเร็จ" % to_e164)
        return {"ok": True, "to": to_e164}
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        j = {}
    code = j.get("code")
    message = j.get("message") or (r.text or "")[:300]
    print("[SMS] ✗ Twilio ปฏิเสธ (HTTP %d · code=%s): %s" % (r.status_code, code, message))
    hint = {21608: "บัญชี trial ส่งได้เฉพาะเบอร์ที่ verify แล้ว — verify เบอร์ปลายทางใน Twilio หรืออัปเกรดบัญชี",
            21211: "รูปแบบเบอร์ปลายทางไม่ถูกต้อง",
            21606: "เบอร์ต้นทาง (From) ส่ง SMS ไม่ได้/ไม่ใช่เบอร์ SMS",
            21612: "เส้นทางนี้ส่งไม่ได้ — เปิด Geo Permission ประเทศไทยใน Twilio (Messaging → Geo Permissions)"}.get(code)
    return {"ok": False, "status": r.status_code, "code": code, "reason": message, "hint": hint}


async def send_sms(to: str, text: str) -> bool:
    """ส่ง SMS ผ่าน Twilio — คืน True ถ้าส่งสำเร็จ (log เหตุผลจริงเสมอผ่าน send_sms_detail)"""
    res = await send_sms_detail(to, text)
    return bool(res.get("ok"))


async def reply_line(reply_token: str, text: str) -> bool:
    """ตอบกลับข้อความ LINE ด้วย reply token (ใช้ตอบ group/user ID กลับไปในแชท เพื่อไปตั้ง LINE_DEFAULT_TO)"""
    token = settings.line_channel_access_token
    if not (token and reply_token):
        return False
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("https://api.line.me/v2/bot/message/reply",
                         headers={"Authorization": "Bearer " + token},
                         json={"replyToken": reply_token, "messages": [{"type": "text", "text": text[:1900]}]})
        return r.status_code == 200


async def send_line(text: str, to: str = "") -> bool:
    """ส่งข้อความ LINE ผ่านโทเคนกลาง (broadcast หรือ push หา userId ที่ระบุ)"""
    token = settings.line_channel_access_token
    if not token:
        return False
    target = to or settings.line_default_to
    url = "https://api.line.me/v2/bot/message/" + ("push" if target else "broadcast")
    payload = {"messages": [{"type": "text", "text": text[:4900]}]}
    if target:
        payload["to"] = target
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(url, headers={"Authorization": "Bearer " + token}, json=payload)
        return r.status_code == 200
