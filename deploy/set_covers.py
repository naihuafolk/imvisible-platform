#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
set_covers.py — อัปโหลดรูปปกที่เตรียมไว้ (content/covers/<slug>.png)
                ขึ้น WordPress Media แล้วตั้งเป็น Featured Image ให้โพสต์
--------------------------------------------------------------------------
- ไม่ต้องใช้ ModelArk — ใช้รูปแบรนด์ที่ generate ไว้แล้วในโฟลเดอร์ content/covers/
- idempotent: ถ้าโพสต์มีรูปปกแล้วจะข้าม (เว้นแต่ --force)
- ใช้เฉพาะ Python stdlib · อ่าน WORDPRESS_* จาก backend/.env

ใช้งาน:
    python3 set_covers.py            # เฉพาะโพสต์ที่ยังไม่มีรูปปก
    python3 set_covers.py --force    # ตั้งรูปทับทุกโพสต์
"""
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
COVERS_DIR = os.path.normpath(os.path.join(HERE, "..", "content", "covers"))
ENV_PATH = os.path.normpath(os.path.join(HERE, "..", "backend", ".env"))
FORCE = "--force" in sys.argv


def load_env():
    cfg = {}
    keys = ("WORDPRESS_BASE_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD")
    for k in keys:
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key in keys and val and not cfg.get(key):
                    cfg[key] = val
    return cfg


class WP:
    def __init__(self, cfg):
        self.base = cfg["WORDPRESS_BASE_URL"].rstrip("/") + "/wp-json/wp/v2"
        tok = base64.b64encode(("%s:%s" % (cfg["WORDPRESS_USERNAME"], cfg["WORDPRESS_APP_PASSWORD"])).encode()).decode()
        self.auth = "Basic " + tok

    def _json(self, method, path, payload=None):
        url = self.base + path
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method,
                                     headers={"Authorization": self.auth, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise RuntimeError("HTTP %s %s\n   %s" % (e.code, path, e.read().decode(errors="replace")[:300]))

    def find(self, slug):
        items = self._json("GET", "/posts?" + urllib.parse.urlencode({"slug": slug, "status": "publish,draft"}))
        return items[0] if items else None

    def upload(self, img_bytes, filename, alt):
        req = urllib.request.Request(self.base + "/media", data=img_bytes, method="POST")
        req.add_header("Authorization", self.auth)
        req.add_header("Content-Type", "image/png")
        req.add_header("Content-Disposition", 'attachment; filename="%s"' % filename)
        with urllib.request.urlopen(req, timeout=120) as r:
            media = json.loads(r.read().decode())
        try:
            self._json("POST", "/media/%s" % media["id"], {"alt_text": alt})
        except Exception:
            pass
        return media["id"]

    def set_featured(self, post_id, media_id):
        return self._json("POST", "/posts/%s" % post_id, {"featured_media": media_id})


def main():
    cfg = load_env()
    need = [k for k in ("WORDPRESS_BASE_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD") if not cfg.get(k)]
    if need:
        print("❌ ยังไม่มีค่า:", ", ".join(need)); sys.exit(1)
    if not os.path.isdir(COVERS_DIR):
        print("❌ ไม่พบโฟลเดอร์รูปปก:", COVERS_DIR); sys.exit(1)

    print("→ WordPress:", cfg["WORDPRESS_BASE_URL"])
    print("→ รูปปกจาก:", COVERS_DIR)
    wp = WP(cfg)
    files = sorted(f for f in os.listdir(COVERS_DIR) if f.lower().endswith(".png"))
    done = 0
    for fn in files:
        slug = os.path.splitext(fn)[0]
        post = wp.find(slug)
        if not post:
            print("  – ข้าม (ไม่พบโพสต์):", slug); continue
        if post.get("featured_media") and not FORCE:
            print("  – ข้าม (มีรูปปกแล้ว):", slug); continue
        title = (post.get("title") or {}).get("rendered") or slug
        try:
            with open(os.path.join(COVERS_DIR, fn), "rb") as fp:
                img = fp.read()
            print("  • ", slug, "…", end=" ", flush=True)
            mid = wp.upload(img, slug + "-cover.png", title)
            wp.set_featured(post["id"], mid)
            print("✓ ตั้งรูปปกแล้ว (media id=%s)" % mid)
            done += 1
        except Exception as e:
            print("✗ ล้มเหลว:", e)
    print("\n─────────────\nเสร็จ: ตั้งรูปปก %d โพสต์" % done)


if __name__ == "__main__":
    main()
