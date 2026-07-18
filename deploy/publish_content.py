#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
publish_content.py — ลงคอนเทนต์ทั้งหมดขึ้น WordPress อัตโนมัติ (idempotent)
--------------------------------------------------------------------------
- อ่านไฟล์ใน ../content/*.html (มี header <!-- title / meta / slug -->)
- home.html, pricing.html            -> WordPress "Page"
- บทความที่เหลือ (9 ชิ้น)             -> WordPress "Post" + หมวด (Pillar)
- ตั้ง slug, excerpt (=meta), สถานะ publish, สร้างหมวดให้อัตโนมัติ
- ถ้ามี slug อยู่แล้ว = อัปเดต (ไม่สร้างซ้ำ)
- ใช้เฉพาะ Python stdlib (ไม่ต้องติดตั้งอะไรเพิ่ม)

ใช้งาน:
    # อ่านค่าจาก backend/.env อัตโนมัติ หรือส่งผ่าน env ก็ได้
    python3 publish_content.py
    # ทดสอบก่อน (ไม่เขียนจริง)
    python3 publish_content.py --dry-run

ต้องมีใน backend/.env (หรือ export เป็น env):
    WORDPRESS_BASE_URL=https://imvisible.tech
    WORDPRESS_USERNAME=<admin username>
    WORDPRESS_APP_PASSWORD=<Application Password (มีเว้นวรรคได้)>
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# บังคับ stdout เป็น UTF-8 (กันคอนโซล Windows codepage ไทยพัง)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.normpath(os.path.join(HERE, "..", "content"))
ENV_PATH = os.path.normpath(os.path.join(HERE, "..", "backend", ".env"))
DRY = "--dry-run" in sys.argv

# ---- ไฟล์ที่เป็น "หน้า" (Page) ----
PAGES = {"home", "pricing"}

# ---- แผนที่ บทความ -> หมวด (Pillar) ----
CATEGORY_OF = {
    "what-is-aeo":            "AI Search / AEO",
    "get-recommended-by-ai":  "AI Search / AEO",
    "ranked-but-not-cited":   "AI Search / AEO",
    "what-is-seo":            "ความรู้ SEO",
    "why-not-ranking":        "ความรู้ SEO",
    "diy-seo-checklist":      "ความรู้ SEO",
    "seo-price-2026":         "รับทำ SEO",
    "seo-white-vs-gray-hat":  "รับทำ SEO",
    "choose-seo-agency":      "รับทำ SEO",
}


def load_env():
    cfg = {}
    for k in ("WORDPRESS_BASE_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD"):
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
                if key.startswith("WORDPRESS_") and key not in cfg:
                    cfg[key] = val
    return cfg


def parse_file(path):
    raw = open(path, "r", encoding="utf-8").read()
    m = re.search(r"<!--(.*?)-->", raw, re.S)
    title, meta, slug = "", "", ""
    if m:
        head = m.group(1)
        t = re.search(r"title:\s*(.+)", head)
        d = re.search(r"meta:\s*(.+)", head)
        s = re.search(r"slug:\s*(.+)", head)
        title = t.group(1).strip() if t else ""
        meta = d.group(1).strip() if d else ""
        slug = (s.group(1).strip().lstrip("/") if s else "")
    body = raw[m.end():].strip() if m else raw.strip()
    if not slug:
        slug = os.path.splitext(os.path.basename(path))[0]
    if not title:
        title = slug
    return {"title": title, "meta": meta, "slug": slug, "html": body}


class WP:
    def __init__(self, base, user, app_pw):
        self.base = base.rstrip("/") + "/wp-json/wp/v2"
        tok = base64.b64encode(f"{user}:{app_pw}".encode()).decode()
        self.auth = "Basic " + tok

    def _req(self, method, path, data=None, params=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", self.auth)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise RuntimeError(f"HTTP {e.code} {method} {path}\n   {detail[:400]}")

    def ensure_category(self, name, cache):
        if name in cache:
            return cache[name]
        found = self._req("GET", "/categories", params={"search": name, "per_page": 100})
        for c in found:
            if c.get("name") == name:
                cache[name] = c["id"]
                return c["id"]
        created = self._req("POST", "/categories", data={"name": name})
        cache[name] = created["id"]
        print(f"   + สร้างหมวด: {name} (id={created['id']})")
        return created["id"]

    def find_by_slug(self, kind, slug):
        items = self._req("GET", f"/{kind}", params={"slug": slug, "status": "publish,draft,pending"})
        return items[0] if items else None

    def upsert(self, kind, payload, slug):
        existing = self.find_by_slug(kind, slug)
        if existing:
            res = self._req("POST", f"/{kind}/{existing['id']}", data=payload)
            return res, "อัปเดต"
        res = self._req("POST", f"/{kind}", data=payload)
        return res, "สร้างใหม่"


def main():
    cfg = load_env()
    missing = [k for k in ("WORDPRESS_BASE_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD") if not cfg.get(k)]
    if missing:
        print("❌ ยังไม่มีค่า:", ", ".join(missing))
        print("   ตั้งใน backend/.env หรือ export env ก่อน แล้วรันใหม่")
        sys.exit(1)

    print(f"→ WordPress: {cfg['WORDPRESS_BASE_URL']}  (user: {cfg['WORDPRESS_USERNAME']})")
    print(f"→ อ่านคอนเทนต์จาก: {CONTENT_DIR}")
    if DRY:
        print("   [DRY-RUN] จะไม่เขียนจริง\n")

    files = sorted(f for f in os.listdir(CONTENT_DIR) if f.endswith(".html"))
    wp = WP(cfg["WORDPRESS_BASE_URL"], cfg["WORDPRESS_USERNAME"], cfg["WORDPRESS_APP_PASSWORD"])
    cat_cache = {}
    results = []

    for fn in files:
        item = parse_file(os.path.join(CONTENT_DIR, fn))
        base = item["slug"]
        is_page = base in PAGES
        kind = "pages" if is_page else "posts"
        payload = {
            "title": item["title"],
            "content": item["html"],
            "slug": base,
            "status": "publish",
            "excerpt": item["meta"],
            "meta": {"rank_math_description": item["meta"]},  # ถ้า Rank Math เปิด REST ให้
        }
        if not is_page:
            cat = CATEGORY_OF.get(base)
            if cat and not DRY:
                payload["categories"] = [wp.ensure_category(cat, cat_cache)]

        label = "PAGE" if is_page else f"POST · {CATEGORY_OF.get(base, '-')}"
        if DRY:
            print(f"   [{label}] {base}  «{item['title'][:48]}»")
            results.append((base, "(dry)", ""))
            continue
        try:
            res, act = wp.upsert(kind, payload, base)
            link = res.get("link", "")
            print(f"   ✓ {act:8} [{label}] {base}  → {link}")
            results.append((base, act, link))
        except Exception as e:
            print(f"   ✗ ล้มเหลว [{label}] {base}: {e}")
            results.append((base, "ERROR", str(e)))

    ok = sum(1 for _, a, _ in results if a in ("สร้างใหม่", "อัปเดต"))
    print(f"\n─────────────────────────────\nเสร็จ: {ok}/{len(files)} ชิ้น")
    if not DRY:
        print("\nถัดไป (ทำใน WP admin):")
        print("  • Settings → Reading → ตั้งหน้าแรก (static) เป็นหน้า landing")
        print("  • Appearance → Menus → ผูกเมนู: หน้าแรก · บริการ · ราคา · บทความ · ติดต่อ")
        print("  • Rank Math → เชื่อม Search Console + ส่ง sitemap")


if __name__ == "__main__":
    main()
