"""
กระจายบทความใหม่ไป "ช่องของลูกค้าเอง" (โซเชียลแบรนด์เขา) — ปลอดภัย ขาว ไม่ยิงสแปม
รองรับ: LINE OA · Facebook Page · Telegram · X(Twitter) · LinkedIn · Discord · Mastodon · Webhook(Zapier/Make)
โทเคน/URL เก็บแบบเข้ารหัส (crypto.enc) · ช่องที่ใส่ URL เอง (discord/mastodon/webhook) มี guard กัน SSRF
"""
import ipaddress
from urllib.parse import urlparse

import httpx

LINE_PUSH = "https://api.line.me/v2/bot/message/push"
LINE_BROADCAST = "https://api.line.me/v2/bot/message/broadcast"
FB_GRAPH = "https://graph.facebook.com/v21.0"
TG_API = "https://api.telegram.org"
X_TWEETS = "https://api.twitter.com/2/tweets"
LI_UGC = "https://api.linkedin.com/v2/ugcPosts"

_BLOCK_HOSTS = {"localhost", "metadata.google.internal", "metadata"}
_DISCORD_HOSTS = ("discord.com", "discordapp.com", "ptb.discord.com", "canary.discord.com")


def _safe_url(u: str, allow_hosts=None) -> bool:
    """กัน SSRF: อนุญาตเฉพาะ https + host สาธารณะ (บล็อก IP ภายใน/localhost/metadata)"""
    try:
        p = urlparse(u or "")
    except Exception:  # noqa: BLE001
        return False
    if p.scheme != "https" or not p.hostname:
        return False
    host = p.hostname.lower()
    if host in _BLOCK_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:                                    # ถ้าเป็น IP literal → บล็อกช่วงภายใน/สงวน
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    except ValueError:
        pass                                # เป็น hostname ปกติ
    if allow_hosts and not any(host == h or host.endswith("." + h) for h in allow_hosts):
        return False
    return True


async def post_line(token: str, to: str, text: str) -> dict:
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    body = {"messages": [{"type": "text", "text": (text or "")[:4900]}]}
    if to and to.lower() != "broadcast":
        url = LINE_PUSH; body["to"] = to
    else:
        url = LINE_BROADCAST
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, headers=headers, json=body)
    if r.status_code == 200:
        return {"ok": True, "url": "", "detail": "ส่ง LINE แล้ว" + (" (broadcast)" if url == LINE_BROADCAST else "")}
    return {"ok": False, "url": "", "detail": "LINE %s: %s" % (r.status_code, (r.text or "")[:160])}


async def post_facebook(page_id: str, token: str, message: str, link: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("%s/%s/feed" % (FB_GRAPH, page_id),
                         data={"message": message or "", "link": link or "", "access_token": token})
    if r.status_code == 200:
        pid = ((r.json() or {}).get("id") or "")
        parts = pid.split("_")
        url = ("https://www.facebook.com/%s/posts/%s" % (parts[0], parts[1])) if len(parts) == 2 \
            else ("https://www.facebook.com/" + pid)
        return {"ok": True, "url": url, "detail": "โพสต์ Facebook แล้ว"}
    return {"ok": False, "url": "", "detail": "FB %s: %s" % (r.status_code, (r.text or "")[:160])}


async def post_telegram(bot_token: str, chat_id: str, text: str, link: str) -> dict:
    msg = ((text or "") + "\n" + (link or "")).strip()[:4000]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("%s/bot%s/sendMessage" % (TG_API, bot_token),
                         json={"chat_id": chat_id, "text": msg, "disable_web_page_preview": False})
    if r.status_code == 200 and (r.json() or {}).get("ok"):
        return {"ok": True, "url": "", "detail": "ส่ง Telegram แล้ว"}
    return {"ok": False, "url": "", "detail": "Telegram %s: %s" % (r.status_code, (r.text or "")[:160])}


async def post_x(token: str, text: str, link: str) -> dict:
    link = link or ""
    avail = 279 - len(link) - 1
    body_text = ((text or "")[:max(0, avail)].rstrip() + "\n" + link).strip()[:280]
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(X_TWEETS, headers=headers, json={"text": body_text})
    if r.status_code in (200, 201):
        tid = (((r.json() or {}).get("data") or {}).get("id") or "")
        return {"ok": True, "url": ("https://x.com/i/web/status/" + tid) if tid else "", "detail": "โพสต์ X แล้ว"}
    return {"ok": False, "url": "", "detail": "X %s: %s" % (r.status_code, (r.text or "")[:160])}


async def post_linkedin(token: str, author_urn: str, text: str, link: str) -> dict:
    headers = {"Authorization": "Bearer " + token, "X-Restli-Protocol-Version": "2.0.0",
               "Content-Type": "application/json"}
    body = {
        "author": author_urn, "lifecycleState": "PUBLISHED",
        "specificContent": {"com.linkedin.ugc.ShareContent": {
            "shareCommentary": {"text": ((text or "") + "\n" + (link or "")).strip()[:2900]},
            "shareMediaCategory": "ARTICLE",
            "media": [{"status": "READY", "originalUrl": link or ""}]}},
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(LI_UGC, headers=headers, json=body)
    if r.status_code in (200, 201):
        return {"ok": True, "url": "", "detail": "โพสต์ LinkedIn แล้ว"}
    return {"ok": False, "url": "", "detail": "LinkedIn %s: %s" % (r.status_code, (r.text or "")[:160])}


async def post_discord(webhook_url: str, text: str, link: str) -> dict:
    if not _safe_url(webhook_url, allow_hosts=_DISCORD_HOSTS):
        return {"ok": False, "url": "", "detail": "Discord webhook URL ไม่ถูกต้อง/ไม่ปลอดภัย"}
    content = ((text or "") + "\n" + (link or "")).strip()[:1900]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(webhook_url, json={"content": content})
    if r.status_code in (200, 204):
        return {"ok": True, "url": "", "detail": "โพสต์ Discord แล้ว"}
    return {"ok": False, "url": "", "detail": "Discord %s: %s" % (r.status_code, (r.text or "")[:160])}


async def post_mastodon(instance: str, token: str, text: str, link: str) -> dict:
    host = (instance or "").strip().replace("https://", "").replace("http://", "").strip("/")
    base = "https://" + host
    if not _safe_url(base):
        return {"ok": False, "url": "", "detail": "Mastodon instance ไม่ถูกต้อง/ไม่ปลอดภัย"}
    status = ((text or "") + "\n" + (link or "")).strip()[:490]
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(base + "/api/v1/statuses",
                         headers={"Authorization": "Bearer " + token}, data={"status": status})
    if r.status_code == 200:
        return {"ok": True, "url": ((r.json() or {}).get("url") or ""), "detail": "โพสต์ Mastodon แล้ว"}
    return {"ok": False, "url": "", "detail": "Mastodon %s: %s" % (r.status_code, (r.text or "")[:160])}


async def post_webhook(webhook_url: str, text: str, link: str, title: str = "") -> dict:
    """ยิง JSON ออกไป webhook ทั่วไป (Zapier/Make/n8n) → ต่อไปไหนก็ได้ (IG/TikTok/Pinterest ฯลฯ)"""
    if not _safe_url(webhook_url):
        return {"ok": False, "url": "", "detail": "Webhook URL ไม่ถูกต้อง/ไม่ปลอดภัย (ต้อง https + host สาธารณะ)"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(webhook_url, json={"title": title or text, "text": text or "", "url": link or ""})
    if 200 <= r.status_code < 300:
        return {"ok": True, "url": "", "detail": "ส่ง Webhook แล้ว (%s)" % r.status_code}
    return {"ok": False, "url": "", "detail": "Webhook %s: %s" % (r.status_code, (r.text or "")[:160])}


PIN_PINS = "https://api.pinterest.com/v5/pins"


async def post_instagram(ig_user_id: str, token: str, image_url: str, caption: str) -> dict:
    """IG Business — 2 ขั้น: สร้าง media container → publish · ต้องมีรูป (image_url)"""
    if not image_url:
        return {"ok": False, "url": "", "detail": "Instagram ต้องมีรูป (บทความนี้ยังไม่มีรูปปก)"}
    async with httpx.AsyncClient(timeout=60) as c:
        r1 = await c.post("%s/%s/media" % (FB_GRAPH, ig_user_id),
                          data={"image_url": image_url, "caption": (caption or "")[:2100], "access_token": token})
    if r1.status_code != 200:
        return {"ok": False, "url": "", "detail": "IG media %s: %s" % (r1.status_code, (r1.text or "")[:140])}
    cid = ((r1.json() or {}).get("id") or "")
    async with httpx.AsyncClient(timeout=60) as c:
        r2 = await c.post("%s/%s/media_publish" % (FB_GRAPH, ig_user_id),
                          data={"creation_id": cid, "access_token": token})
    if r2.status_code == 200:
        return {"ok": True, "url": "", "detail": "โพสต์ Instagram แล้ว"}
    return {"ok": False, "url": "", "detail": "IG publish %s: %s" % (r2.status_code, (r2.text or "")[:140])}


async def post_pinterest(board_id: str, token: str, image_url: str, title: str, link: str, desc: str) -> dict:
    """Pinterest v5 create pin · ต้องมีรูป (image_url) + board_id"""
    if not image_url:
        return {"ok": False, "url": "", "detail": "Pinterest ต้องมีรูป (บทความนี้ยังไม่มีรูปปก)"}
    body = {"board_id": board_id, "title": (title or "")[:100], "description": (desc or "")[:500],
            "link": link or "", "media_source": {"source_type": "image_url", "url": image_url}}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(PIN_PINS, headers={"Authorization": "Bearer " + token,
                                            "Content-Type": "application/json"}, json=body)
    if r.status_code in (200, 201):
        pid = ((r.json() or {}).get("id") or "")
        return {"ok": True, "url": ("https://www.pinterest.com/pin/%s/" % pid) if pid else "", "detail": "โพสต์ Pinterest แล้ว"}
    return {"ok": False, "url": "", "detail": "Pinterest %s: %s" % (r.status_code, (r.text or "")[:140])}


async def dispatch(kind: str, token: str, ref: str, text: str, link: str, image: str = "") -> dict:
    """ยิงไปช่องเดียวตามชนิด — คืน {ok, url, detail} (ไม่โยน exception ออก) · image = รูปปก (สำหรับ IG/Pinterest)"""
    try:
        if kind == "line":
            return await post_line(token, ref, (text or "") + "\n" + (link or ""))
        if kind == "facebook":
            return await post_facebook(ref, token, text, link)
        if kind == "telegram":
            return await post_telegram(token, ref, text, link)
        if kind == "x":
            return await post_x(token, text, link)
        if kind == "linkedin":
            return await post_linkedin(token, ref, text, link)
        if kind == "discord":
            return await post_discord(token, text, link)
        if kind == "mastodon":
            return await post_mastodon(ref, token, text, link)
        if kind == "webhook":
            return await post_webhook(token, text, link, ref)
        if kind == "instagram":
            return await post_instagram(ref, token, image, (text or "") + "\n" + (link or ""))
        if kind == "pinterest":
            return await post_pinterest(ref, token, image, text, link, text)
        return {"ok": False, "url": "", "detail": "ยังไม่รองรับช่อง '%s'" % kind}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "url": "", "detail": ("%s error: %s" % (kind, str(e)))[:190]}


# ชนิดที่รองรับ (ใช้ตรวจฝั่ง API + สร้างฟอร์มฝั่งแดชบอร์ด) · ig/pinterest ต้องมีรูปปก
SUPPORTED = ("line", "facebook", "telegram", "x", "linkedin", "discord", "mastodon", "webhook",
             "instagram", "pinterest")
