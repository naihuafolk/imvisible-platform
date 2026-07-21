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
