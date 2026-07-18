"""
ขอ Google refresh_token สำหรับ Search Console (และ GA4 ถ้าต้องการ)
— ขั้นตอนตั้งค่าที่ยุ่งสุด สคริปต์นี้ทำให้จบใน 1 คำสั่ง

เตรียมก่อนรัน:
  1) ไปที่ https://console.cloud.google.com  → สร้างโปรเจ็ค
  2) เปิดใช้ "Google Search Console API" (และ "Google Analytics Data API" ถ้าใช้ GA4)
  3) OAuth consent screen: เพิ่มอีเมลตัวเองใน Test users
  4) Credentials → Create OAuth client ID → ประเภท "Desktop app"
     คัดลอก Client ID / Client Secret มาใส่ตอนรัน (หรือใส่ใน .env ก่อน)

รัน (จากโฟลเดอร์ backend):
  python scripts/get_gsc_token.py
จะเปิดเบราว์เซอร์ให้ล็อกอิน/กดอนุญาต แล้วพิมพ์ refresh_token ออกมา
เอาค่าไปใส่ GOOGLE_REFRESH_TOKEN ใน .env
"""
import json
import os
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

# โหลด .env ถ้ามี (ไม่ต้องพึ่ง dependency)
def _load_env():
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_env()

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",   # Search Console
    "https://www.googleapis.com/auth/analytics.readonly",    # GA4 (เอาออกได้ถ้าไม่ใช้)
]
PORT = 8765
REDIRECT = f"http://127.0.0.1:{PORT}"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

_code_holder: dict = {}


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        qs = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(qs)
        _code_holder["code"] = params.get("code", [None])[0]
        _code_holder["error"] = params.get("error", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = "สำเร็จ! กลับไปที่เทอร์มินัลได้เลย" if _code_holder.get("code") else "เกิดข้อผิดพลาด ลองใหม่"
        self.wfile.write(f"<h2>{msg}</h2><p>RankPilot AI — ปิดหน้านี้ได้</p>".encode("utf-8"))

    def log_message(self, *args):  # ปิด log รก ๆ
        pass


def main():
    client_id = os.environ.get("GOOGLE_CLIENT_ID") or input("GOOGLE_CLIENT_ID: ").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET") or input("GOOGLE_CLIENT_SECRET: ").strip()
    if not client_id or not client_secret:
        print("ต้องมี Client ID / Secret ก่อน"); sys.exit(1)

    auth = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",   # บังคับให้ได้ refresh_token ทุกครั้ง
    })

    server = HTTPServer(("127.0.0.1", PORT), _Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    print("\nเปิดเบราว์เซอร์เพื่ออนุญาตสิทธิ์... ถ้าไม่เด้ง ให้ก็อปลิงก์นี้ไปเปิดเอง:\n" + auth + "\n")
    webbrowser.open(auth)

    # รอ callback
    import time
    for _ in range(300):
        if _code_holder.get("code") or _code_holder.get("error"):
            break
        time.sleep(1)

    if _code_holder.get("error") or not _code_holder.get("code"):
        print("ไม่ได้รับ code:", _code_holder.get("error")); sys.exit(1)

    data = urllib.parse.urlencode({
        "code": _code_holder["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req) as resp:
        tok = json.loads(resp.read())

    rt = tok.get("refresh_token")
    if not rt:
        print("ไม่ได้ refresh_token (ลองลบสิทธิ์เดิมที่ myaccount.google.com/permissions แล้วรันใหม่)")
        print(json.dumps(tok, ensure_ascii=False, indent=2)); sys.exit(1)

    print("\n============================================================")
    print("✅ สำเร็จ! ใส่ค่านี้ใน .env:")
    print(f"GOOGLE_REFRESH_TOKEN={rt}")
    print("============================================================")


if __name__ == "__main__":
    main()
