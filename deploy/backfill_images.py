#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backfill_images.py — สร้างรูปหน้าปกบทความด้วย Seedream (BytePlus ModelArk)
                     แล้วตั้งเป็น Featured Image ให้โพสต์ WordPress อัตโนมัติ
--------------------------------------------------------------------------
- ใช้ Seedream 5.0 Pro (text-to-image) ผ่าน ModelArk (OpenAI-compatible)
- ดาวน์โหลดรูป → อัปขึ้น WordPress Media → ตั้งเป็นรูปปก (featured_media)
- idempotent: ถ้าโพสต์มีรูปปกอยู่แล้วจะข้าม (เว้นแต่ใส่ --force)
- ใช้เฉพาะ Python stdlib

ต้องมีใน backend/.env (หรือ export env):
    ARK_API_KEY=<API key จาก BytePlus ModelArk>
    ARK_IMAGE_MODEL=<โมเดล/endpoint id ของ Seedream 5.0 Pro จาก console>
    ARK_BASE_URL=https://ark.ap-southeast.bytepluses.com/api/v3   (ค่าเริ่มต้น ap-southeast)
    WORDPRESS_BASE_URL / WORDPRESS_USERNAME / WORDPRESS_APP_PASSWORD (มีแล้วจากตอนลงบทความ)

ใช้งาน:
    python3 backfill_images.py            # ทำเฉพาะโพสต์ที่ยังไม่มีรูปปก
    python3 backfill_images.py --force    # สร้างรูปใหม่ทับทุกโพสต์
    python3 backfill_images.py --only what-is-aeo   # ทดสอบทีละอัน
"""
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.normpath(os.path.join(HERE, "..", "backend", ".env"))
FORCE = "--force" in sys.argv
ONLY = None
if "--only" in sys.argv:
    i = sys.argv.index("--only")
    ONLY = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

# บทความ 9 ชิ้น (หน้า home/pricing ไม่ต้องมีรูปปก) + คำใบ้ธีมภาพ (ต่อท้าย prompt กลาง)
TOPICS = {
    "what-is-aeo":           "answer engine optimization, AI answering questions, chat bubbles and search",
    "get-recommended-by-ai": "AI assistant recommending a brand, spotlight on a chosen answer",
    "ranked-but-not-cited":  "a website ranked high but not cited by AI, magnifying glass and citation marks",
    "what-is-seo":           "search engine optimization basics, upward ranking chart and magnifier",
    "why-not-ranking":       "website not ranking on Google, troubleshooting and climbing steps",
    "diy-seo-checklist":     "a clean SEO checklist with checkmarks, do-it-yourself concept",
    "seo-price-2026":        "SEO pricing and packages, coins and value scale, business planning",
    "seo-white-vs-gray-hat": "white hat vs gray hat SEO, balance and ethics concept",
    "choose-seo-agency":     "choosing a trustworthy SEO agency, handshake and shield of trust",
}

STYLE = ("modern minimal flat vector illustration, tech and marketing theme, "
         "azure blue (#1a56ff) and cyan with soft white background, clean corporate, "
         "high quality, professional, no text, no words, no letters, 16:9")


def load_env():
    cfg = {}
    keys = ("ARK_API_KEY", "ARK_IMAGE_MODEL", "ARK_BASE_URL",
            "WORDPRESS_BASE_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD")
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
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key in keys and val and not cfg.get(key):
                    cfg[key] = val
    cfg.setdefault("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
    cfg.setdefault("ARK_IMAGE_MODEL", "dola-seedream-5-0-pro-260628")
    return cfg


def http_json(method, url, headers, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError("HTTP %s %s\n   %s" % (e.code, url, e.read().decode(errors="replace")[:400]))


def ark_image(cfg, prompt):
    """เรียก Seedream (ModelArk) สร้างภาพ → คืน URL ภาพ"""
    url = cfg["ARK_BASE_URL"].rstrip("/") + "/images/generations"
    headers = {"Authorization": "Bearer " + cfg["ARK_API_KEY"], "Content-Type": "application/json"}
    payload = {"model": cfg["ARK_IMAGE_MODEL"], "prompt": prompt,
               "size": "2K", "output_format": "png", "watermark": False}
    data = http_json("POST", url, headers, payload)
    items = data.get("data") or []
    if not items:
        raise RuntimeError("ModelArk ไม่ส่งภาพกลับมา: " + json.dumps(data)[:300])
    return items[0].get("url") or items[0].get("b64_json")


def download(url):
    if url.startswith("data:") or (len(url) > 200 and "http" not in url[:10]):
        return base64.b64decode(url.split(",")[-1])
    with urllib.request.urlopen(url, timeout=120) as r:
        return r.read()


class WP:
    def __init__(self, cfg):
        self.base = cfg["WORDPRESS_BASE_URL"].rstrip("/") + "/wp-json/wp/v2"
        tok = base64.b64encode(("%s:%s" % (cfg["WORDPRESS_USERNAME"], cfg["WORDPRESS_APP_PASSWORD"])).encode()).decode()
        self.auth = "Basic " + tok

    def find(self, slug):
        url = self.base + "/posts?" + urllib.parse.urlencode({"slug": slug, "status": "publish,draft"})
        req = urllib.request.Request(url, headers={"Authorization": self.auth})
        with urllib.request.urlopen(req, timeout=60) as r:
            items = json.loads(r.read().decode())
        return items[0] if items else None

    def upload_media(self, img_bytes, filename, alt):
        req = urllib.request.Request(self.base + "/media", data=img_bytes, method="POST")
        req.add_header("Authorization", self.auth)
        req.add_header("Content-Type", "image/png")
        req.add_header("Content-Disposition", 'attachment; filename="%s"' % filename)
        with urllib.request.urlopen(req, timeout=120) as r:
            media = json.loads(r.read().decode())
        # ตั้ง alt text (ดีต่อ SEO)
        try:
            http_json("POST", self.base + "/media/%s" % media["id"],
                      {"Authorization": self.auth, "Content-Type": "application/json"},
                      {"alt_text": alt})
        except Exception:
            pass
        return media["id"]

    def set_featured(self, post_id, media_id):
        return http_json("POST", self.base + "/posts/%s" % post_id,
                         {"Authorization": self.auth, "Content-Type": "application/json"},
                         {"featured_media": media_id})


def main():
    cfg = load_env()
    need = [k for k in ("ARK_API_KEY", "ARK_IMAGE_MODEL", "WORDPRESS_BASE_URL",
                        "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD") if not cfg.get(k)]
    if need:
        print("❌ ยังไม่มีค่า:", ", ".join(need))
        print("   เพิ่ม ARK_API_KEY + ARK_IMAGE_MODEL ใน backend/.env ก่อน (ดูวิธีขอคีย์จาก BytePlus ModelArk)")
        sys.exit(1)

    print("→ ModelArk:", cfg["ARK_BASE_URL"], "| model:", cfg["ARK_IMAGE_MODEL"])
    print("→ WordPress:", cfg["WORDPRESS_BASE_URL"])
    wp = WP(cfg)
    todo = {ONLY: TOPICS[ONLY]} if (ONLY and ONLY in TOPICS) else TOPICS
    done = 0
    for slug, hint in todo.items():
        post = wp.find(slug)
        if not post:
            print("  – ข้าม (ไม่พบโพสต์):", slug); continue
        if post.get("featured_media") and not FORCE:
            print("  – ข้าม (มีรูปปกแล้ว):", slug); continue
        title = (post.get("title") or {}).get("rendered") or slug
        prompt = "%s. %s" % (hint, STYLE)
        try:
            print("  • สร้างรูป:", slug, "…", end=" ", flush=True)
            img_url = ark_image(cfg, prompt)
            img = download(img_url)
            mid = wp.upload_media(img, slug + "-cover.png", title)
            wp.set_featured(post["id"], mid)
            print("✓ ตั้งรูปปกแล้ว (media id=%s)" % mid)
            done += 1
            time.sleep(1)
        except Exception as e:
            print("✗ ล้มเหลว:", e)
    print("\n─────────────\nเสร็จ: ใส่รูปปก %d โพสต์" % done)


if __name__ == "__main__":
    main()
