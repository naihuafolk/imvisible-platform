"""
Managed Hosting — render บทความจาก DB เป็นหน้าเว็บสาธารณะที่ถูกหลัก SEO/AEO เต็ม
================================================================================
จุดขาย "ลูกค้าใส่แค่ลิงก์ = ของเราทั้งหมด":
  - ค่าเริ่มต้น (zero setup): โฮสต์ที่  https://imvisible.tech/blog/{slug}
  - อัปเกรด (CNAME 1 บรรทัด):        https://blog.ลูกค้า.com   (เสิร์ฟที่ root ตาม Host)

ดีไซน์ "The Visible Issue" (editorial ฟ้า-ขาว) + องค์ประกอบที่ช่วยอันดับจริง:
  สารบัญ (jump link) · reading time · byline/วันที่ (E-E-A-T) · related posts
  (internal linking) · JSON-LD/canonical/hreflang/OG · HTML สะอาด no-JS (CWV ดี)
"""
import html as _html
import json
import re

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from sqlalchemy import select

from app.config import settings
from app.db import session as db
from app.urls import slugify, project_slug_from_domain, project_public_home, public_url_for  # noqa: F401

router = APIRouter(tags=["public"])

_RESERVED = {"api", "app", "www", "docs", "health", "openapi.json", "sitemap.xml",
             "llms.txt", "robots.txt", "favicon.ico", "blog", "a"}
_H_RE = re.compile(r"<h([23])(\s[^>]*)?>(.*?)</h\1>", re.I | re.S)


# ---------------------------------------------------------------- helpers ----
def _esc(t: str) -> str:
    return _html.escape(t or "", quote=True)


def _plain(htmltext: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", htmltext or "")).strip()


def _desc(art) -> str:
    return (getattr(art, "description", "") or _plain(art.html))[:155]


def _reading_time(words) -> int:
    return max(1, round((words or 0) / 200))


def _fmt_date(dt) -> str:
    return dt.strftime("%d/%m/%Y") if dt else ""


def _build_toc(html: str):
    """ใส่ id ให้ H2/H3 + คืน (html, [(level,id,text)]) — ทำสารบัญ + jump link (ดีต่อ engagement/AEO)"""
    items = []

    def _repl(m):
        lvl, attrs, inner = m.group(1), m.group(2) or "", m.group(3)
        hid = "sec-%d" % (len(items) + 1)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", inner)).strip()
        items.append((lvl, hid, text))
        return '<h%s id="%s"%s>%s</h%s>' % (lvl, hid, attrs, inner, lvl)

    return _H_RE.sub(_repl, html or ""), items


def _host(request: Request) -> str:
    return (request.headers.get("host") or "").split(":")[0].strip().lower()


async def _project_by_host(host: str):
    """map Host → โปรเจ็ค
    สำคัญด้านความปลอดภัย: host ที่เป็นโดเมนของเรา ({slug}.imvisible.tech) ต้องตัดสินด้วย
    slug เท่านั้น — ห้ามให้ custom_domain ของคนอื่นมาแย่งซับโดเมนได้ (กัน hijack)
    """
    if not host or not db.enabled():
        return None
    from app.db.models import Project
    base = settings.managed_base_domain.lower()
    async with db.session() as s:
        if host == base or host.endswith("." + base):          # โดเมนของเรา → slug เท่านั้น
            if host.endswith("." + base):
                sub = host[: -(len(base) + 1)]
                if sub and "." not in sub and sub not in _RESERVED:
                    return (await s.execute(
                        select(Project).where(Project.slug == sub))).scalars().first()
            return None
        return (await s.execute(                               # โดเมนลูกค้าเอง
            select(Project).where(Project.custom_domain == host))).scalars().first()


async def _project_by_slug(slug: str):
    if not db.enabled():
        return None
    from app.db.models import Project
    async with db.session() as s:
        return (await s.execute(select(Project).where(Project.slug == slug))).scalars().first()


async def _published(project_id: int):
    from app.db.models import Article
    async with db.session() as s:
        return (await s.execute(
            select(Article).where(Article.project_id == project_id,
                                  Article.status == "published").order_by(Article.id.desc()))).scalars().all()


async def _one_article(project_id: int, key: str):
    from app.db.models import Article
    async with db.session() as s:
        art = (await s.execute(select(Article).where(
            Article.project_id == project_id, Article.status == "published",
            Article.slug == key))).scalars().first()
        if not art and str(key).isdigit():
            art = (await s.execute(select(Article).where(
                Article.project_id == project_id, Article.status == "published",
                Article.id == int(key)))).scalars().first()
        return art


async def _related(project_id: int, exclude_id: int, n: int = 4):
    from app.db.models import Article
    async with db.session() as s:
        return (await s.execute(
            select(Article).where(Article.project_id == project_id, Article.status == "published",
                                  Article.id != exclude_id).order_by(Article.id.desc()).limit(n))).scalars().all()


# ------------------------------------------------------------- templates ----
_CSS = """
*{box-sizing:border-box}
:root{--paper:#fff;--ink:#10192b;--muted:#5a6a86;--blue:#1b3fd4;--blue-ink:#12299e;
--line:#e7ecf6;--wash:#f6f8fd;--wash2:#eef3fc;--sel:#dbe6ff;--radius:16px;--maxw:722px}
@media(prefers-color-scheme:dark){:root{--paper:#0b111f;--ink:#eef2fb;--muted:#93a3c2;--blue:#7d97ff;
--blue-ink:#a9bcff;--line:#233150;--wash:#111a2e;--wash2:#16213a;--sel:#25325a}}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-size:18.5px;line-height:1.78;
font-family:"Sarabun","Noto Sans Thai","Sukhumvit Set","Segoe UI",-apple-system,BlinkMacSystemFont,Tahoma,sans-serif;
-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
::selection{background:var(--sel)}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline;text-underline-offset:3px}
img{max-width:100%;height:auto;border-radius:12px}
.cover{margin:0 0 30px}.cover img{width:100%;border-radius:var(--radius);display:block;aspect-ratio:16/9;object-fit:cover}
.card .thumb{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:12px;margin-bottom:12px;display:block}
.site{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--paper) 85%,transparent);
backdrop-filter:saturate(1.5) blur(10px);-webkit-backdrop-filter:saturate(1.5) blur(10px);border-bottom:1px solid var(--line)}
.site .in{max-width:1040px;margin:0 auto;padding:13px 22px}
.brand{display:inline-flex;align-items:center;gap:10px;color:inherit;font-weight:800;letter-spacing:-.01em}
.brand .mk{width:30px;height:30px;border-radius:9px;background:var(--blue);color:#fff;display:grid;place-items:center;font-size:16px}
.brand .dm{color:var(--muted);font-weight:500;font-size:13.5px}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 22px}
main{padding:38px 0 88px}
.crumb{font-size:13px;color:var(--muted);margin:0 0 18px}.crumb a{color:var(--muted)}.crumb a:hover{color:var(--blue)}
.eyebrow{display:inline-block;font-size:12.5px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--blue);margin-bottom:12px}
h1{font-size:clamp(30px,5.2vw,46px);line-height:1.13;letter-spacing:-.022em;margin:.05em 0 .32em;font-weight:800;text-wrap:balance}
article h2{font-size:clamp(23px,3.4vw,30px);line-height:1.25;letter-spacing:-.015em;margin:1.9em 0 .5em;font-weight:800;scroll-margin-top:82px}
article h3{font-size:20px;line-height:1.35;margin:1.5em 0 .35em;font-weight:700;scroll-margin-top:82px}
article p,article li{font-size:18.5px}
article>p:first-of-type{font-size:21px;line-height:1.68}
article ul,article ol{padding-left:1.35em}article li{margin:.32em 0}
article strong{font-weight:700}
article a{text-decoration:underline;text-underline-offset:3px;text-decoration-color:color-mix(in srgb,var(--blue) 42%,transparent)}
.byline{display:flex;flex-wrap:wrap;align-items:center;gap:8px 13px;color:var(--muted);font-size:14.5px;
padding-bottom:22px;margin-bottom:30px;border-bottom:1px solid var(--line)}
.byline .who{display:inline-flex;align-items:center;gap:9px;color:var(--ink);font-weight:700}
.byline .av{width:29px;height:29px;border-radius:50%;background:linear-gradient(135deg,var(--blue),var(--blue-ink));color:#fff;display:grid;place-items:center;font-size:13px;font-weight:800}
.byline .sep{width:4px;height:4px;border-radius:50%;background:var(--muted);opacity:.5}
.toc{background:var(--wash);border:1px solid var(--line);border-radius:var(--radius);padding:17px 20px;margin:0 0 34px}
.toc .lb{font-size:12px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:9px}
.toc ol{margin:0;padding:0;list-style:none;counter-reset:t}
.toc li{counter-increment:t;margin:7px 0;font-size:15.5px;display:flex;gap:10px;line-height:1.45}
.toc li::before{content:counter(t,decimal-leading-zero);color:var(--blue);font-weight:800;font-variant-numeric:tabular-nums;font-size:13px;padding-top:2px}
.toc li.l3{padding-left:24px}.toc li.l3::before{content:"–"}
.toc a{color:var(--ink)}.toc a:hover{color:var(--blue)}
article blockquote{margin:1.6em 0;padding:4px 0 4px 22px;border-left:3px solid var(--blue);font-size:20px;font-style:italic}
.tblx,article table{overflow-x:auto}
article table{border-collapse:collapse;width:100%;margin:1.5em 0;font-size:15.5px;display:block}
article th,article td{border:1px solid var(--line);padding:10px 12px;text-align:left}
article th{background:var(--wash);font-weight:700}
article code{background:var(--wash2);padding:.12em .4em;border-radius:6px;font-size:.9em;font-family:ui-monospace,Menlo,Consolas,monospace}
article pre{background:var(--wash2);border:1px solid var(--line);border-radius:12px;padding:16px;overflow-x:auto}
article hr{border:0;border-top:1px solid var(--line);margin:2.3em 0}
.abox{display:flex;gap:14px;align-items:flex-start;background:var(--wash);border:1px solid var(--line);border-radius:var(--radius);padding:20px;margin:46px 0 0}
.abox .av{width:46px;height:46px;border-radius:13px;background:linear-gradient(135deg,var(--blue),var(--blue-ink));color:#fff;display:grid;place-items:center;font-weight:800;font-size:20px;flex:none}
.abox .nm{font-weight:800}.abox .ds{color:var(--muted);font-size:14.5px;margin-top:2px;line-height:1.55}
.rel{margin:50px 0 0}
.rel .lb{font-size:12.5px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:15px}
.rel .grid,.cards{display:grid;gap:15px;grid-template-columns:1fr}
@media(min-width:620px){.rel .grid{grid-template-columns:1fr 1fr}}
@media(min-width:680px){.cards{grid-template-columns:1fr 1fr}}
.rcard{display:block;padding:17px 19px;border:1px solid var(--line);border-radius:14px;background:var(--paper);transition:border-color .15s,transform .15s}
.rcard:hover{border-color:var(--blue);transform:translateY(-2px)}
.rcard .t{font-weight:700;color:var(--ink);line-height:1.35;margin-bottom:5px}
.rcard .x{color:var(--muted);font-size:14px;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.hero{padding:22px 0 32px;border-bottom:1px solid var(--line);margin-bottom:34px}
.hero p{color:var(--muted);font-size:18px;margin:.35em 0 0;max-width:60ch}
.card{display:flex;flex-direction:column;padding:22px;border:1px solid var(--line);border-radius:var(--radius);background:var(--paper);transition:border-color .15s,transform .15s,box-shadow .15s}
.card:hover{border-color:var(--blue);transform:translateY(-3px);box-shadow:0 14px 32px rgba(20,40,120,.09)}
.card .ey{font-size:11.5px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--blue);margin-bottom:9px}
.card .t{font-size:20px;font-weight:800;line-height:1.28;letter-spacing:-.01em;color:var(--ink);margin-bottom:8px}
.card .x{color:var(--muted);font-size:15px;line-height:1.55;flex:1;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.card .mt{margin-top:14px;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.empty{color:var(--muted);padding:48px 0;text-align:center}
.foot{border-top:1px solid var(--line);margin-top:58px;padding:26px 0 0;color:var(--muted);font-size:13.5px;line-height:1.7}
.foot a{color:var(--blue)}
.share-bar{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin:42px 0 0;padding-top:24px;border-top:1px solid var(--line)}
.share-lbl{font-weight:800;font-size:14px;color:var(--muted);margin-right:4px}
.share-bar .sh{display:inline-flex;align-items:center;gap:6px;padding:8px 15px;border-radius:11px;border:1px solid var(--line);background:var(--paper);color:var(--ink);font-size:14px;font-weight:700;cursor:pointer;transition:border-color .15s,transform .15s}
.share-bar .sh:hover{border-color:var(--blue);transform:translateY(-1px);text-decoration:none}
.share-bar .sh-fb{color:#1877f2}.share-bar .sh-line{color:#06c755}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def _share_bar(url: str, title: str) -> str:
    """ปุ่มแชร์ท้ายบทความ (Facebook / LINE / X / คัดลอกลิงก์) — ให้คนอ่านช่วยแชร์ต่อ = reach + โอกาส earned link"""
    from urllib.parse import quote
    u = quote(url or "", safe="")
    t = quote(title or "", safe="")
    cu = (url or "").replace('"', "").replace("'", "").replace("\\", "").replace("<", "").replace(">", "")  # ตัดอักขระอันตราย (กัน attribute injection/XSS)
    return (
        '<div class="share-bar"><span class="share-lbl">แชร์บทความนี้</span>'
        '<a class="sh sh-fb" href="https://www.facebook.com/sharer/sharer.php?u=' + u + '" target="_blank" rel="noopener">Facebook</a>'
        '<a class="sh sh-line" href="https://social-plugins.line.me/lineit/share?url=' + u + '" target="_blank" rel="noopener">LINE</a>'
        '<a class="sh sh-x" href="https://twitter.com/intent/tweet?url=' + u + '&text=' + t + '" target="_blank" rel="noopener">X (Twitter)</a>'
        '<button class="sh sh-copy" type="button" onclick="navigator.clipboard.writeText(\'' + cu + '\');this.textContent=\'คัดลอกแล้ว ✓\'">คัดลอกลิงก์</button>'
        '</div>')


def _head(title, desc, canonical, lang, jsonld_list, og_type="article", published=None, modified=None, image=""):
    # escape "</" -> "<\/" (valid JSON) กัน </script> ในหัวข้อ/คำอธิบายมาปิด script block ก่อน (กัน JSON-LD พัง/injection)
    ld = "\n".join('<script type="application/ld+json">%s</script>' % j.replace("</", "<\\/")
                   for j in jsonld_list if j)
    times = ""
    if published:
        times += '<meta property="article:published_time" content="%s">' % _esc(published.isoformat())
    if modified:
        times += '<meta property="article:modified_time" content="%s">' % _esc(modified.isoformat())
    img = ('<meta property="og:image" content="%s"><meta name="twitter:image" content="%s">'
           % (_esc(image), _esc(image))) if image else ""
    return (
        '<!doctype html><html lang="%s"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg"><meta name="theme-color" content="#3d6bff">'
        '<title>%s</title><meta name="description" content="%s">'
        '<link rel="canonical" href="%s"><meta property="og:site_name" content="ImVisible">'
        '<meta property="og:type" content="%s"><meta property="og:title" content="%s">'
        '<meta property="og:description" content="%s"><meta property="og:url" content="%s">'
        '<meta name="twitter:card" content="summary_large_image">%s'
        '<link rel="alternate" hreflang="%s" href="%s"><link rel="alternate" hreflang="x-default" href="%s">'
        '%s<style>%s</style>%s</head>'
        % (lang, _esc(title), _esc(desc), _esc(canonical), og_type, _esc(title),
           _esc(desc), _esc(canonical), img, lang, _esc(canonical), _esc(canonical), times, _CSS, ld)
    )


def _chrome(proj, home):
    return (
        '<header class="site"><div class="in"><a class="brand" href="%s">'
        '<span class="mk">%s</span>%s<span class="dm">%s</span></a></div></header>'
        % (_esc(home), _esc((proj.name or "I")[:1].upper()), _esc(proj.name or proj.domain), _esc(proj.domain))
    )


def _footer(proj):
    return ('<footer class="foot">© %s · ทุกบทความผลิตและดูแลโดยระบบ AEO ของ '
            '<a href="https://imvisible.tech" rel="nofollow">ImVisible</a> — เขียนให้ตอบคำถามจริง โปร่งใส ตรวจสอบได้'
            '</footer>' % _esc(proj.name or proj.domain))


def _article_jsonld(proj, art, canonical, home, lang):
    """ใช้ schema จากเครื่องยนต์ถ้ามี (ตรวจว่าเป็น JSON จริงก่อนฝัง); เสริม Article + BreadcrumbList เสมอ"""
    out = []
    raw = (getattr(art, "schema_json", "") or "").strip()
    if raw:
        raw = re.sub(r"(?is)</?script[^>]*>", "", raw).strip()
        try:
            json.loads(raw)
        except Exception:
            raw = ""
    if raw:
        out.append(raw)
    else:
        dt = getattr(art, "updated_at", None)
        article = {
            "@context": "https://schema.org", "@type": "Article",
            "headline": art.title, "description": _desc(art),
            "inLanguage": lang, "mainEntityOfPage": canonical,
            "author": {"@type": "Organization", "name": proj.name or proj.domain},
            "publisher": {"@type": "Organization", "name": proj.name or proj.domain},
        }
        if dt:
            article["datePublished"] = dt.isoformat()
            article["dateModified"] = dt.isoformat()
        out.append(json.dumps(article, ensure_ascii=False))
    out.append(json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": proj.name or proj.domain, "item": home},
            {"@type": "ListItem", "position": 2, "name": art.title, "item": canonical},
        ]}, ensure_ascii=False))
    return out


def render_article_page(proj, art, related=None) -> str:
    home = project_public_home(proj)
    canonical = art.url or public_url_for(proj, art)
    lang = "en" if str(proj.language).lower().startswith("en") else "th"
    author = proj.name or proj.domain
    cluster = getattr(art, "cluster", "") or "บทความ"
    dt = getattr(art, "updated_at", None)
    body, toc = _build_toc(art.html or "")
    has_h1 = bool(re.search(r"<h1[\s>]", body, re.I))

    byline = ('<div class="byline"><span class="who"><span class="av">%s</span>ทีม %s</span>'
              % (_esc(author[:1].upper()), _esc(author)))
    if _fmt_date(dt):
        byline += '<span class="sep"></span><span>อัปเดต %s</span>' % _esc(_fmt_date(dt))
    byline += '<span class="sep"></span><span>อ่าน ~%d นาที</span></div>' % _reading_time(getattr(art, "words", 0))

    toc_html = ""
    if len(toc) >= 3:
        lis = "".join('<li class="l%s"><a href="#%s">%s</a></li>' % (lvl, hid, _esc(text))
                      for lvl, hid, text in toc)
        toc_html = '<nav class="toc"><div class="lb">สารบัญ</div><ol>%s</ol></nav>' % lis

    abox = ('<div class="abox"><div class="av">%s</div><div><div class="nm">ทีม %s</div>'
            '<div class="ds">ผลิต + ดูแลคอนเทนต์โดยระบบ AEO ของ ImVisible — ทุกบทความเขียนให้ตอบคำถามจริง '
            'ตรวจข้อเท็จจริง และปรับให้สดใหม่อยู่เสมอ</div></div></div>'
            % (_esc(author[:1].upper()), _esc(author)))

    rel_html = ""
    if related:
        cards = "".join('<a class="rcard" href="%s"><div class="t">%s</div><div class="x">%s</div></a>'
                        % (_esc(a.url or public_url_for(proj, a)), _esc(a.title), _esc(_desc(a)))
                        for a in related)
        rel_html = '<section class="rel"><div class="lb">อ่านต่อ</div><div class="grid">%s</div></section>' % cards

    header = "" if has_h1 else "<h1>%s</h1>" % _esc(art.title)
    cover = getattr(art, "cover_url", "") or ""
    cover_html = ('<figure class="cover"><img src="%s" alt="%s" loading="lazy"></figure>'
                  % (_esc(cover), _esc(art.title))) if cover else ""
    return (
        _head(art.title, _desc(art), canonical, lang,
              _article_jsonld(proj, art, canonical, home, lang), "article",
              published=dt, modified=dt, image=cover)
        + "<body>" + _chrome(proj, home)
        + '<main><div class="wrap">'
        + '<div class="crumb"><a href="%s">หน้าแรก</a> › %s</div>' % (_esc(home), _esc(cluster))
        + '<span class="eyebrow">%s</span>' % _esc(cluster)
        + header + byline + cover_html + toc_html
        + "<article>" + body + "</article>"
        + _share_bar(canonical, art.title)
        + abox + rel_html
        + _footer(proj) + "</div></main></body></html>"
    )


def render_index_page(proj, arts) -> str:
    home = project_public_home(proj)
    lang = "en" if str(proj.language).lower().startswith("en") else "th"
    title = "%s — บทความ & คู่มือ" % (proj.name or proj.domain)
    desc = "คลังบทความและคู่มือจาก %s เขียนให้ตอบคำถามจริง ถูกหลัก SEO/AEO อ่านง่าย ตรวจสอบได้" % (proj.name or proj.domain)
    website_ld = json.dumps({
        "@context": "https://schema.org", "@type": "WebSite",
        "name": proj.name or proj.domain, "url": home, "inLanguage": lang,
    }, ensure_ascii=False)
    if arts:
        cards = "".join(
            '<a class="card" href="%s">%s<div class="ey">%s</div><div class="t">%s</div>'
            '<div class="x">%s</div><div class="mt">อ่าน ~%d นาที</div></a>'
            % (_esc(a.url or public_url_for(proj, a)),
               ('<img class="thumb" src="%s" alt="" loading="lazy">' % _esc(getattr(a, "cover_url", "") or ""))
               if getattr(a, "cover_url", "") else "",
               _esc(getattr(a, "cluster", "") or "บทความ"),
               _esc(a.title), _esc(_desc(a)), _reading_time(getattr(a, "words", 0)))
            for a in arts)
        body = '<div class="cards">%s</div>' % cards
    else:
        body = '<div class="empty">กำลังจัดเตรียมบทความ — ระบบ AEO กำลังผลิตให้เร็ว ๆ นี้</div>'
    return (
        _head(title, desc, home, lang, [website_ld], "website")
        + "<body>" + _chrome(proj, home)
        + '<main><div class="wrap">'
        + '<header class="hero"><span class="eyebrow">คลังความรู้</span>'
        + "<h1>%s</h1><p>%s</p></header>" % (_esc(proj.name or proj.domain), _esc(desc))
        + body + _footer(proj) + "</div></main></body></html>"
    )


def render_sitemap(proj, arts) -> str:
    home = project_public_home(proj)
    urls = ["<url><loc>%s</loc></url>" % _esc(home)]
    for a in arts:
        loc = _esc(a.url or public_url_for(proj, a))
        lm = getattr(a, "updated_at", None)
        lastmod = "<lastmod>%s</lastmod>" % lm.date().isoformat() if lm else ""
        urls.append("<url><loc>%s</loc>%s</url>" % (loc, lastmod))
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % "".join(urls))


def render_llms_txt(proj, arts) -> str:
    home = project_public_home(proj)
    lines = ["# %s" % (proj.name or proj.domain), "",
             "> บทความและคู่มือที่เขียนให้ตอบคำถามจริง ถูกหลัก AEO — อ้างอิงได้", "",
             "## บทความ"]
    for a in arts:
        lines.append("- [%s](%s): %s" % (a.title, a.url or public_url_for(proj, a), _desc(a)))
    lines += ["", "## เกี่ยวกับ", "- เว็บไซต์: %s" % home,
              "- โฮสต์คอนเทนต์โดย ImVisible (imvisible.tech)"]
    return "\n".join(lines) + "\n"


def render_robots(proj) -> str:
    home = project_public_home(proj)
    return "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % home


# ---------------------------------------------------------------- routes ----
# ---- แบบ path (ใช้ได้ทันทีบนโดเมนหลัก ไม่ต้องตั้ง DNS): /blog/{slug}/... ----
@router.get("/blog/{project_slug}", response_class=HTMLResponse)
async def blog_index_path(project_slug: str):
    proj = await _project_by_slug(project_slug)
    if not proj:
        return HTMLResponse("ไม่พบบล็อกนี้", status_code=404)
    return HTMLResponse(render_index_page(proj, await _published(proj.id)))


@router.get("/blog/{project_slug}/sitemap.xml")
async def blog_sitemap_path(project_slug: str):
    proj = await _project_by_slug(project_slug)
    if not proj:
        return PlainTextResponse("not found", status_code=404)
    return Response_xml(render_sitemap(proj, await _published(proj.id)))


@router.get("/blog/{project_slug}/llms.txt", response_class=PlainTextResponse)
async def blog_llms_path(project_slug: str):
    proj = await _project_by_slug(project_slug)
    if not proj:
        return PlainTextResponse("not found", status_code=404)
    return PlainTextResponse(render_llms_txt(proj, await _published(proj.id)))


@router.get("/blog/{project_slug}/{article_key}", response_class=HTMLResponse)
async def blog_article_path(project_slug: str, article_key: str):
    proj = await _project_by_slug(project_slug)
    if not proj:
        return HTMLResponse("ไม่พบบล็อกนี้", status_code=404)
    art = await _one_article(proj.id, article_key)
    if not art:
        return HTMLResponse("ไม่พบบทความ", status_code=404)
    return HTMLResponse(render_article_page(proj, art, await _related(proj.id, art.id)))


# ---- แบบ Host (custom domain / {slug}.imvisible.tech) เสิร์ฟที่ root ----
@router.get("/", response_class=HTMLResponse)
async def host_root(request: Request):
    proj = await _project_by_host(_host(request))
    if not proj:
        return JSONResponse({"service": "ImVisible API", "docs": "/docs"})
    return HTMLResponse(render_index_page(proj, await _published(proj.id)))


@router.get("/a/{article_key}", response_class=HTMLResponse)
async def host_article(article_key: str, request: Request):
    proj = await _project_by_host(_host(request))
    if not proj:
        return HTMLResponse("ไม่พบบทความ", status_code=404)
    art = await _one_article(proj.id, article_key)
    if not art:
        return HTMLResponse("ไม่พบบทความ", status_code=404)
    return HTMLResponse(render_article_page(proj, art, await _related(proj.id, art.id)))


@router.get("/sitemap.xml")
async def host_sitemap(request: Request):
    proj = await _project_by_host(_host(request))
    if not proj:
        return PlainTextResponse("not found", status_code=404)
    return Response_xml(render_sitemap(proj, await _published(proj.id)))


@router.get("/llms.txt", response_class=PlainTextResponse)
async def host_llms(request: Request):
    proj = await _project_by_host(_host(request))
    if not proj:
        return PlainTextResponse("not found", status_code=404)
    return PlainTextResponse(render_llms_txt(proj, await _published(proj.id)))


@router.get("/robots.txt", response_class=PlainTextResponse)
async def host_robots(request: Request):
    proj = await _project_by_host(_host(request))
    if not proj:
        return PlainTextResponse("User-agent: *\nAllow: /\n")
    return PlainTextResponse(render_robots(proj))


def Response_xml(body: str):
    from fastapi.responses import Response
    return Response(content=body, media_type="application/xml")
