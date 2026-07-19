"""
โพสต์บทความใหม่ไป "ช่องทางของลูกค้าเอง" (โซเชียลแบรนด์เขา) — ปลอดภัย ขาว
- LINE OA (Messaging API): push/broadcast
- Facebook Page (Graph API): โพสต์ลง feed พร้อมลิงก์
X / LinkedIn = ยังไม่รองรับ (X เสียเงิน, LinkedIn ต้องขออนุมัติ) → คืน skipped ชัดเจน
"""
import httpx

LINE_PUSH = "https://api.line.me/v2/bot/message/push"
LINE_BROADCAST = "https://api.line.me/v2/bot/message/broadcast"
FB_GRAPH = "https://graph.facebook.com/v21.0"


async def post_line(token: str, to: str, text: str) -> dict:
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    body = {"messages": [{"type": "text", "text": (text or "")[:4900]}]}
    if to and to.lower() != "broadcast":
        url = LINE_PUSH
        body["to"] = to
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


async def dispatch(kind: str, token: str, ref: str, text: str, link: str) -> dict:
    """ยิงไปช่องเดียวตามชนิด — คืน {ok, url, detail} (ไม่โยน exception ออก)"""
    try:
        if kind == "line":
            return await post_line(token, ref, (text or "") + "\n" + (link or ""))
        if kind == "facebook":
            return await post_facebook(ref, token, text, link)
        return {"ok": False, "url": "", "detail": "ยังไม่รองรับช่อง '%s'" % kind}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "url": "", "detail": ("%s error: %s" % (kind, str(e)))[:190]}
