"""
Managed Hosting — render บทความจาก DB เป็นหน้าเว็บสาธารณะที่ถูกหลัก SEO/AEO เต็ม
================================================================================
จุดขาย "ลูกค้าใส่แค่ลิงก์ = ของเราทั้งหมด":
  - ค่าเริ่มต้น (zero setup): โฮสต์ที่  https://imvisible.tech/blog/{slug}
  - อัปเกรด (CNAME 1 บรรทัด):        https://blog.ลูกค้า.com   (เสิร์ฟที่ root ตาม Host)
เราคุมสัญญาณ AEO ทุกตัวเอง: <head> ครบ, JSON-LD, canonical, hreflang, OG,
sitemap.xml, llms.txt, robots.txt, HTML สะอาด — เว็บลูกค้าจะห่วยแค่ไหนก็ตาม
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


# ---------------------------------------------------------------- helpers ----
def _esc(t: str) -> str:
    return _html.escape(t or "", quote=True)


def _host(request: Request) -> str:
    h = (request.headers.get("host") or "").split(":")[0].strip().lower()
    return h


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
        # โดเมนลูกค้าเอง (custom_domain ในฐานข้อมูลถูกกันไม่ให้ลงท้ายด้วย base อยู่แล้ว)
        return (await s.execute(
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
            Article.slug == key))).scalar_one_or_none()
        if not art and str(key).isdigit():
            art = (await s.execute(select(Article).where(
                Article.project_id == project_id, Article.status == "published",
                Article.id == int(key)))).scalar_one_or_none()
        return art


def _plain(htmltext: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", htmltext or "")).strip()


def _desc(art) -> str:
    return (getattr(art, "description", "") or _plain(art.html))[:155]


# ------------------------------------------------------------- templates ----
_CSS = """
:root{--ink:#0d1526;--sub:#4a5878;--blue:#1c40d8;--line:#e3e9f5;--soft:#f5f8fe;--paper:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);line-height:1.72;
font-family:"Sarabun","Noto Sans Thai","Sukhumvit Set","Segoe UI",-apple-system,BlinkMacSystemFont,Tahoma,sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.top{border-bottom:1px solid var(--line)}
.bar{max-width:760px;margin:0 auto;padding:16px 22px;display:flex;align-items:center;gap:10px}
.logo{width:26px;height:26px;border-radius:7px;background:var(--blue);color:#fff;display:grid;place-items:center;font-weight:800;font-size:15px}
.bar b{font-size:15px}.bar .dm{color:var(--sub);font-size:13px}
main{max-width:760px;margin:0 auto;padding:30px 22px 70px}
h1{font-size:clamp(26px,5vw,38px);line-height:1.22;letter-spacing:-.01em;margin:.2em 0 .3em}
h2{font-size:clamp(20px,3.4vw,26px);margin:1.6em 0 .4em;letter-spacing:-.01em}
h3{font-size:19px;margin:1.3em 0 .3em}
p,li{font-size:17.5px}
.meta{color:var(--sub);font-size:14px;margin-bottom:6px}
.crumb{font-size:13px;color:var(--sub);margin-bottom:18px}
article img{max-width:100%;height:auto;border-radius:12px}
table{border-collapse:collapse;width:100%;overflow-x:auto;display:block}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;font-size:15.5px}
.card{display:block;padding:18px 20px;border:1px solid var(--line);border-radius:14px;margin-bottom:14px;background:var(--paper)}
.card:hover{border-color:var(--blue)}.card h3{margin:0 0 4px}.card p{margin:0;color:var(--sub);font-size:15px}
.foot{border-top:1px solid var(--line);margin-top:40px;padding-top:18px;color:var(--sub);font-size:13px}
@media(prefers-color-scheme:dark){:root{--ink:#e9eefb;--sub:#9aa8c9;--blue:#6f8dff;--line:#233150;--soft:#121a2e;--paper:#0a0f1c}}
"""


def _head(title, desc, canonical, lang, jsonld_list, og_type="article"):
    ld = "\n".join(
        '<script type="application/ld+json">%s</script>' % j for j in jsonld_list if j)
    return (
        '<!doctype html><html lang="%s"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>%s</title><meta name="description" content="%s">'
        '<link rel="canonical" href="%s">'
        '<meta property="og:type" content="%s"><meta property="og:title" content="%s">'
        '<meta property="og:description" content="%s"><meta property="og:url" content="%s">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="alternate" hreflang="%s" href="%s"><link rel="alternate" hreflang="x-default" href="%s">'
        '<style>%s</style>%s</head>'
        % (lang, _esc(title), _esc(desc), _esc(canonical), og_type, _esc(title),
           _esc(desc), _esc(canonical), lang, _esc(canonical), _esc(canonical), _CSS, ld)
    )


def _chrome(proj, home):
    return (
        '<div class="top"><div class="bar"><span class="logo">%s</span>'
        '<b><a href="%s" style="color:inherit">%s</a></b>'
        '<span class="dm">%s</span></div></div>'
        % (_esc((proj.name or "I")[:1].upper()), _esc(home), _esc(proj.name or proj.domain), _esc(proj.domain))
    )


def _footer(proj):
    return ('<div class="foot">© %s · ขับเคลื่อนคอนเทนต์โดย '
            '<a href="https://imvisible.tech" rel="nofollow">ImVisible</a> — โปร่งใส ตรวจสอบได้</div>'
            % _esc(proj.name or proj.domain))


def _article_jsonld(proj, art, canonical, home, lang):
    """ใช้ schema จากเครื่องยนต์ถ้ามี; เสริม BreadcrumbList เสมอ"""
    out = []
    raw = (getattr(art, "schema_json", "") or "").strip()
    if raw:                                   # ลอก <script> ที่อาจติดมา + ตรวจว่าเป็น JSON จริงก่อนฝัง
        raw = re.sub(r"(?is)</?script[^>]*>", "", raw).strip()
        try:
            json.loads(raw)
        except Exception:
            raw = ""
    if raw:
        out.append(raw)
    else:
        out.append(json.dumps({
            "@context": "https://schema.org", "@type": "Article",
            "headline": art.title, "description": _desc(art),
            "inLanguage": lang, "mainEntityOfPage": canonical,
            "author": {"@type": "Organization", "name": proj.name or proj.domain},
            "publisher": {"@type": "Organization", "name": proj.name or proj.domain},
        }, ensure_ascii=False))
    out.append(json.dumps({
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": proj.name or proj.domain, "item": home},
            {"@type": "ListItem", "position": 2, "name": art.title, "item": canonical},
        ]}, ensure_ascii=False))
    return out


def render_article_page(proj, art) -> str:
    home = project_public_home(proj)
    canonical = art.url or public_url_for(proj, art)
    lang = "en" if str(proj.language).lower().startswith("en") else "th"
    body = art.html or ""
    has_h1 = bool(re.search(r"<h1[\s>]", body, re.I))
    header = "" if has_h1 else "<h1>%s</h1>" % _esc(art.title)
    return (
        _head(art.title, _desc(art), canonical, lang,
              _article_jsonld(proj, art, canonical, home, lang), "article")
        + "<body>" + _chrome(proj, home)
        + '<main><div class="crumb"><a href="%s">หน้าแรก</a> › บทความ</div>' % _esc(home)
        + header + '<div class="meta">โดย %s</div>' % _esc(proj.name or proj.domain)
        + "<article>" + body + "</article>"
        + _footer(proj) + "</main></body></html>"
    )


def render_index_page(proj, arts) -> str:
    home = project_public_home(proj)
    lang = "en" if str(proj.language).lower().startswith("en") else "th"
    title = "%s — บทความ & คู่มือ" % (proj.name or proj.domain)
    desc = "รวมบทความและคู่มือจาก %s ที่เขียนให้ตอบคำถามจริง ถูกหลัก SEO/AEO" % (proj.name or proj.domain)
    website_ld = json.dumps({
        "@context": "https://schema.org", "@type": "WebSite",
        "name": proj.name or proj.domain, "url": home, "inLanguage": lang,
    }, ensure_ascii=False)
    cards = "".join(
        '<a class="card" href="%s"><h3>%s</h3><p>%s</p></a>'
        % (_esc(a.url or public_url_for(proj, a)), _esc(a.title), _esc(_desc(a)))
        for a in arts) or '<p style="color:var(--sub)">กำลังจัดเตรียมบทความ…</p>'
    return (
        _head(title, desc, home, lang, [website_ld], "website")
        + "<body>" + _chrome(proj, home)
        + "<main><h1>%s</h1><p class='meta'>%s</p>" % (_esc(proj.name or proj.domain), _esc(desc))
        + cards + _footer(proj) + "</main></body></html>"
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
    return HTMLResponse(render_article_page(proj, art))


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
    return HTMLResponse(render_article_page(proj, art))


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
