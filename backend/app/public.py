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
:root{--paper:#fcfbf8;--ink:#161821;--muted:#5a6a86;--blue:#1b3fd4;--blue-ink:#12299e;
--line:#e9e6de;--wash:#f6f5f0;--wash2:#eef3fc;--sel:#dbe6ff;--radius:16px;--maxw:722px}
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
article>p:first-of-type::first-letter{font-size:3.15em;font-weight:800;float:left;line-height:.82;margin:.04em .11em 0 0;color:var(--blue)}
article .note,article .callout,article aside.note{display:flex;gap:13px;background:var(--wash);border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:0 13px 13px 0;padding:15px 18px;margin:1.6em 0;font-size:16.5px;line-height:1.62}
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
.card{display:flex;flex-direction:column;padding:0;overflow:hidden;border:1px solid var(--line);border-radius:var(--radius);background:var(--paper);transition:border-color .15s,transform .15s,box-shadow .15s}
.card:hover{border-color:var(--blue);transform:translateY(-3px);box-shadow:0 14px 32px rgba(20,40,120,.09)}
.card:hover .cov .thumb{transform:scale(1.05)}
/* magazine cover: หัวข้อพาดบนรูป */
.card .cov{position:relative;height:210px;overflow:hidden;background:linear-gradient(135deg,var(--blue),var(--blue-deep))}
.card .cov .thumb{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;margin:0;border-radius:0;transition:transform .4s cubic-bezier(.2,.6,.2,1)}
.card .cov::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(9,19,45,0) 30%,rgba(9,19,45,.5) 62%,rgba(9,19,45,.86) 100%)}
.card .cov-ey{position:absolute;top:13px;left:14px;z-index:2;background:rgba(33,84,204,.92);color:#fff;font-size:11px;font-weight:800;letter-spacing:.06em;text-transform:uppercase;padding:4px 11px;border-radius:999px}
.card .cov-t{position:absolute;left:16px;right:16px;bottom:14px;z-index:2;margin:0;color:#fff;font-size:19px;font-weight:800;line-height:1.3;letter-spacing:-.01em;text-shadow:0 2px 12px rgba(0,0,0,.55)}
.card .cbody{padding:15px 20px 20px}
.card .x{color:var(--muted);font-size:15px;line-height:1.55;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card .mt{margin-top:12px;font-size:13px;color:var(--muted);font-variant-numeric:tabular-nums}
.empty{color:var(--muted);padding:48px 0;text-align:center}
.foot{border-top:1px solid var(--line);margin-top:58px;padding:26px 0 0;color:var(--muted);font-size:13.5px;line-height:1.7}
.foot a{color:var(--blue)}
.share-bar{display:flex;flex-wrap:wrap;align-items:center;gap:9px;margin:42px 0 0;padding-top:24px;border-top:1px solid var(--line)}
.share-lbl{font-weight:800;font-size:14px;color:var(--muted);margin-right:4px}
.share-bar .sh{display:inline-flex;align-items:center;gap:6px;padding:8px 15px;border-radius:11px;border:1px solid var(--line);background:var(--paper);color:var(--ink);font-size:14px;font-weight:700;cursor:pointer;transition:border-color .15s,transform .15s}
.share-bar .sh:hover{border-color:var(--blue);transform:translateY(-1px);text-decoration:none}
.share-bar .sh-fb{color:#1877f2}.share-bar .sh-line{color:#06c755}
@media(prefers-reduced-motion:reduce){*{transition:none!important}}
/* ---- ภาพประกอบ: ระยะหายใจ + เงานุ่ม ให้ดูพรีเมียม (แก้อาการ 'กำแพงตัวอักษร') ---- */
.cover img{box-shadow:0 24px 54px -24px rgba(20,40,120,.30)}
figure.inline-img{margin:42px 0}
figure.inline-img img{width:100%;border-radius:var(--radius);display:block;box-shadow:0 16px 40px -16px rgba(20,40,120,.24)}
figure.inline-img figcaption,figure.cover figcaption{color:var(--muted);font-size:13.5px;text-align:center;margin-top:11px;font-style:italic;line-height:1.5}
figure.hero-video{margin:0 0 30px}
figure.hero-video video{width:100%;border-radius:var(--radius);display:block;box-shadow:0 24px 54px -24px rgba(20,40,120,.30)}
article>p:first-of-type{color:var(--ink)}
article blockquote{position:relative;background:var(--wash);border-radius:0 var(--radius) var(--radius) 0;padding:18px 24px 18px 26px}
/* ---- ภาพสรุป (อินโฟกราฟิก จากเนื้อบทความจริง) ---- */
.infographic{background:var(--wash);border:1px solid var(--line);border-radius:var(--radius);padding:22px 24px;margin:36px 0}
.infographic .ig-h{font-size:12.5px;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--blue);margin-bottom:16px}
.ig-steps{display:flex;flex-direction:column}
.ig-step{display:flex;gap:14px;padding:13px 0;border-top:1px solid var(--line)}
.ig-step:first-child{border-top:0;padding-top:0}
.ig-step .ig-n{flex:none;width:30px;height:30px;border-radius:50%;background:var(--blue);color:#fff;display:grid;place-items:center;font-weight:800;font-size:14px}
.ig-step b,.ig-pt b{display:block;font-size:16.5px;line-height:1.42}
.ig-step>div>span,.ig-pt>div>span{color:var(--muted);font-size:14.5px;line-height:1.5}
.ig-points{display:grid;gap:16px;grid-template-columns:1fr}
@media(min-width:560px){.ig-points{grid-template-columns:1fr 1fr}}
.ig-pt{display:flex;gap:11px}
.ig-pt .ig-dot{flex:none;width:9px;height:9px;border-radius:50%;background:var(--blue);margin-top:8px}
.ig-compare{display:flex;flex-direction:column}
.ig-compare .ig-row{display:grid;grid-template-columns:1.2fr 1fr 1fr;gap:12px;padding:11px 0;border-top:1px solid var(--line);font-size:15px}
.ig-compare .ig-row:first-child{border-top:0}
.ig-compare .ig-head{font-weight:800;font-size:13px;color:var(--ink)}
.ig-compare .ig-lab{font-weight:700;color:var(--ink)}
.ig-compare .ig-row>span:not(.ig-lab){color:var(--muted)}
.ig-compare .ig-head>span{color:var(--ink)}
/* ---- กราฟเทรนด์การค้นหา (ข้อมูลจริง DataForSEO) ---- */
.trend-chart{margin:36px 0;background:var(--wash);border:1px solid var(--line);border-radius:var(--radius);padding:20px 22px}
.trend-chart .tc-h{font-size:14px;font-weight:800;color:var(--ink);margin-bottom:14px;line-height:1.4}
.trend-chart svg{width:100%;height:auto;display:block}
.trend-chart .tc-bar{fill:var(--blue);transition:opacity .15s}
.trend-chart .tc-bar:hover{opacity:.72}
.trend-chart .tc-cap{color:var(--muted);font-size:13px;margin-top:11px;line-height:1.5}
"""


def _share_bar(url: str, title: str, en: bool = False) -> str:
    """ปุ่มแชร์ท้ายบทความ (Facebook / LINE / X / คัดลอกลิงก์) — ให้คนอ่านช่วยแชร์ต่อ = reach + โอกาส earned link"""
    from urllib.parse import quote
    u = quote(url or "", safe="")
    t = quote(title or "", safe="")
    cu = (url or "").replace('"', "").replace("'", "").replace("\\", "").replace("<", "").replace(">", "")  # ตัดอักขระอันตราย (กัน attribute injection/XSS)
    lbl = "Share this" if en else "แชร์บทความนี้"
    copy_lbl = "Copy link" if en else "คัดลอกลิงก์"
    copied = "Copied ✓" if en else "คัดลอกแล้ว ✓"
    return (
        '<div class="share-bar"><span class="share-lbl">' + lbl + '</span>'
        '<a class="sh sh-fb" href="https://www.facebook.com/sharer/sharer.php?u=' + u + '" target="_blank" rel="noopener">Facebook</a>'
        '<a class="sh sh-line" href="https://social-plugins.line.me/lineit/share?url=' + u + '" target="_blank" rel="noopener">LINE</a>'
        '<a class="sh sh-x" href="https://twitter.com/intent/tweet?url=' + u + '&text=' + t + '" target="_blank" rel="noopener">X (Twitter)</a>'
        '<button class="sh sh-copy" type="button" onclick="navigator.clipboard.writeText(\'' + cu + '\');this.textContent=\'' + copied + '\'">' + copy_lbl + '</button>'
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
    en = str(getattr(proj, "language", "") or "").lower().startswith("en")
    link = '<a href="https://imvisible.tech" rel="nofollow">ImVisible</a>'
    nm = _esc(proj.name or proj.domain)
    if en:
        return ('<footer class="foot">© %s · every article produced &amp; maintained by %s\'s AEO system '
                '— written to answer real questions, transparent and verifiable</footer>' % (nm, link))
    return ('<footer class="foot">© %s · ทุกบทความผลิตและดูแลโดยระบบ AEO ของ %s '
            '— เขียนให้ตอบคำถามจริง โปร่งใส ตรวจสอบได้</footer>' % (nm, link))


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
        _org = {"@type": "Organization", "name": proj.name or proj.domain, "url": home}
        article = {
            "@context": "https://schema.org", "@type": "Article",
            "headline": art.title, "description": _desc(art),
            "inLanguage": lang, "mainEntityOfPage": canonical,
            "author": _org, "publisher": _org,
        }
        _cov = getattr(art, "cover_url", "") or ""
        if _cov:
            article["image"] = [_cov]              # Article.image → rich result ใน Google
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
    # Entity: WebSite + Organization — บอก Google/AI ว่า 'เราคือใคร' (E-E-A-T / entity recognition → ดัน GEO)
    out.append(json.dumps({"@context": "https://schema.org", "@type": "WebSite",
                           "name": proj.name or proj.domain, "url": home, "inLanguage": lang},
                          ensure_ascii=False))
    _org_entity = {"@context": "https://schema.org", "@type": "Organization",
                   "name": proj.name or proj.domain, "url": home}
    _bc = (getattr(proj, "business_context", "") or "").strip()
    if _bc:
        _org_entity["description"] = _bc[:200]
    _sameas = [u for u in re.findall(r"https?://[^\s,;]+", getattr(proj, "brand_terms", "") or "")
               if any(s in u for s in ("facebook.com", "instagram.com", "linkedin.com", "youtube.com",
                                       "twitter.com", "x.com", "tiktok.com", "line.me"))][:6]
    if _sameas:
        _org_entity["sameAs"] = _sameas            # ลิงก์โซเชียลจริง (ถ้ามีใน brand_terms) → ยืนยันตัวตน
    out.append(json.dumps(_org_entity, ensure_ascii=False))
    # Speakable — บอก AI/voice assistant ว่า 'ก้อนคำตอบสั้น (.tldr) + หัวเรื่อง' คือส่วนที่หยิบไปตอบได้ (ดัน AEO/GEO/voice)
    out.append(json.dumps({"@context": "https://schema.org", "@type": "WebPage", "url": canonical,
                           "speakable": {"@type": "SpeakableSpecification", "cssSelector": [".tldr", "h1"]}},
                          ensure_ascii=False))
    return out


_CS_PALETTES = {          # โทนสีต่อประเภทธุรกิจ (พรีเมียม ดูแพง) — เลือกจาก biz_type/keyword
    "food":    ("#1a1410", "#c8892f", "#fbf7f0"),   # ร้านอาหาร/คาเฟ่ — ครีม-ทองอบอุ่น
    "beauty":  ("#2a1a24", "#c0567a", "#fbf3f6"),   # คลินิก/สปา/ความงาม — ชมพูโรสโกลด์
    "hotel":   ("#12212b", "#2f9a9a", "#f0f7f7"),   # โรงแรม/ที่พัก — เขียวมรกต
    "tech":    ("#0c1424", "#3b6fe0", "#eef2fb"),   # เทค/เอเจนซี — น้ำเงินสด
    "shop":    ("#171a24", "#5b6ee0", "#f0f2fb"),   # ร้านค้า/ผลิต — ม่วงน้ำเงิน
    "default": ("#111827", "#1657d6", "#f4f7fc"),
}


def _cs_palette(biz_type: str, about: str) -> tuple:
    h = ((biz_type or "") + " " + (about or "")).lower()
    def has(*ks): return any(k in h for k in ks)
    if has("อาหาร", "คาเฟ่", "กาแฟ", "restaurant", "cafe", "coffee", "บาร์", "bar", "bistro", "sushi", "บรันช์", "brunch"):
        return _CS_PALETTES["food"]
    if has("คลินิก", "clinic", "ความงาม", "beauty", "สปา", "spa", "ผิว", "salon", "ทันตกรรม"):
        return _CS_PALETTES["beauty"]
    if has("โรงแรม", "ที่พัก", "รีสอร์ท", "hotel", "resort", "hostel"):
        return _CS_PALETTES["hotel"]
    if has("เว็บ", "ซอฟต์แวร์", "software", "app", "แพลตฟอร์ม", "seo", "agency", "digital", "ai", "tech"):
        return _CS_PALETTES["tech"]
    if has("ร้าน", "shop", "store", "ผลิต", "โรงพิมพ์", "กล่อง", "จำหน่าย"):
        return _CS_PALETTES["shop"]
    return _CS_PALETTES["default"]


def parse_menu_text(text: str) -> list:
    """แปลง 'เมนูดิบ' ที่ลูกค้าวางมาในบรีฟ → โครงหมวด+รายการ (no-faking: แค่จัดรูปข้อความจริงของลูกค้า)
    - บรรทัดที่ลงท้ายด้วยราคา (ตัวเลข) = รายการ (ชื่อ + ราคา)
    - บรรทัดที่ไม่มีราคา = หัวข้อหมวดใหม่ (เช่น 'Donburi', 'หมวด: Sushi')"""
    import re as _re
    if not text or not str(text).strip():
        return []
    price_re = _re.compile(r"^(.*?)[\s.·:_\-–—]*฿?\s*([\d][\d,]*(?:\.\d+)?)\s*(?:บาท|thb|฿|baht|\.\-|\.-)?$", _re.I)
    cats, cur = [], None
    for raw in str(text).splitlines():
        line = raw.strip().strip("•*·-–—:").strip()
        if not line:
            continue
        low = line.lower()
        # ข้ามบรรทัดหมายเหตุ (service charge/vat) — ไม่ใช่รายการ/หมวด
        if ("%" in line) and any(k in low for k in ("service", "vat", "charge", "ภาษี", "เซอร์วิส")):
            continue
        m = price_re.match(line)
        if m and m.group(1).strip():
            if cur is None:
                cur = {"cat": "", "items": []}; cats.append(cur)
            cur["items"].append({"name": m.group(1).strip()[:80], "price": m.group(2).strip()})
        else:
            head = _re.sub(r"^(หมวด|category|menu)\s*[:：]\s*", "", line, flags=_re.I).strip()
            cur = {"cat": head[:40], "items": []}; cats.append(cur)
    return [c for c in cats if c.get("items")]


def render_client_home(name, biz_type, about, contact: dict, photo_urls, lang="th",
                       report_token="", copy: dict | None = None, hero_img: str = "",
                       variant: int = 1, blog: list | None = None, social: list | None = None,
                       menu: list | None = None, menu_note: str = "", logo: str = "",
                       menu_images: list | None = None) -> str:
    """สร้าง 'หน้าเว็บพรีเมียม' ให้ลูกค้า — template สวยขายได้ (ไม่พึ่ง IM WEB)
    ถ้ามี copy (Claude เขียน) + hero_img (Imgentic) จะสวยเต็มรูป · ไม่มีก็ fallback บรีฟดิบได้
    variant 1=Luxe (hero เต็มจอ) · 2=Modern (hero แบ่งซ้าย-ขวา) · 3=Warm (hero การ์ดซ้อน)
    โครง: nav · hero · about · จุดเด่น(3) · แกลเลอรีรูปจริง · ทำไมเลือกเรา · ติดต่อ+ฟอร์ม · footer"""
    variant = variant if variant in (1, 2, 3) else 1
    en = str(lang).startswith("en")
    def t(th, e): return e if en else th
    c = copy or {}
    nm = _esc((name or "").strip() or t("ธุรกิจของเรา", "Our Business"))
    biz = _esc((biz_type or "").strip())
    ink, gold, cream = _cs_palette(biz_type, about)
    if variant == 1:          # สไตล์ 1 · Moonlit Luxe — คืนจันทร์ริมทะเล (พาเลตต์ประจำสไตล์ · หรู เข้ม)
        ink, gold, cream = "#0b1a2e", "#e0a44b", "#f7f2e9"
    _hay = (biz_type + " " + about).lower()
    is_food = any(k in _hay for k in ("อาหาร", "คาเฟ่", "กาแฟ", "restaurant", "cafe", "coffee",
                                      "บาร์", "bar", "bistro", "ซูชิ", "sushi", "ครัว", "bakery",
                                      "เบเกอรี", "brunch", "บรันช์", "ก๋วยเตี๋ยว", "ชาบู", "หมูกระทะ"))
    photos = [u for u in (photo_urls or []) if u][:12]
    hero_bg = (hero_img or "").strip() or (photos[0] if photos else "")

    headline = _esc((c.get("hero_headline") or "").strip() or nm)
    subhead = _esc((c.get("hero_sub") or "").strip() or biz or t("ยินดีต้อนรับ", "Welcome"))
    cta = _esc((c.get("cta") or "").strip() or t("ติดต่อเรา", "Get in touch"))
    about_title = _esc((c.get("about_title") or "").strip() or t("เกี่ยวกับเรา", "About Us"))
    about_body = _esc((c.get("about_body") or "").strip() or (about or "").strip())

    # จุดเด่น 3 อย่าง (Claude) — ไม่มีก็ข้าม (ไม่กุ)
    feats = ""
    fl = [f for f in (c.get("features") or []) if isinstance(f, dict) and (f.get("title") or "").strip()][:3]
    if fl:
        cards = "".join(
            '<div class="cs-card"><div class="cs-ico">%s</div><h3>%s</h3><p>%s</p></div>'
            % (_esc((f.get("icon") or "✦")).strip()[:4], _esc((f.get("title") or "").strip()),
               _esc((f.get("desc") or "").strip())) for f in fl)
        feats = ('<section class="cs-sec"><div class="cs-wrap"><div class="cs-grid3">%s</div></div></section>' % cards)

    about_sec = ""
    if about_body:
        aimg = photos[1] if len(photos) > 1 else (photos[0] if photos else "")
        media = ('<div class="cs-about-img" style="background-image:url(\'%s\')"></div>' % _esc(aimg)) if aimg else ""
        about_sec = ('<section class="cs-sec" id="about"><div class="cs-wrap cs-about%s">'
                     '<div class="cs-about-txt"><span class="cs-eyebrow">%s</span><h2>%s</h2><p>%s</p></div>%s</div></section>'
                     % (" cs-about-solo" if not media else "", t("เกี่ยวกับเรา", "About"), about_title, about_body, media))

    gallery = ""
    if photos:
        cells = "".join('<img src="%s" alt="%s" loading="lazy">' % (_esc(u), nm) for u in photos)
        gallery = ('<section class="cs-sec" id="gallery"><div class="cs-wrap"><span class="cs-eyebrow cs-c">%s</span>'
                   '<h2 class="cs-c">%s</h2><div class="cs-gal">%s</div></div></section>'
                   % (t("ผลงาน", "Our Work"), _esc((c.get("gallery_title") or "").strip() or t("บรรยากาศ & ผลงานจริง", "Gallery")), cells))

    why = ""
    wl = [w for w in (c.get("why") or []) if str(w).strip()][:3]
    if wl:
        items = "".join('<li><span>✓</span>%s</li>' % _esc(str(w).strip()) for w in wl)
        why = ('<section class="cs-sec cs-why"><div class="cs-wrap"><span class="cs-eyebrow cs-c">%s</span>'
               '<h2 class="cs-c">%s</h2><ul class="cs-why-list">%s</ul></div></section>'
               % (t("ทำไมเลือกเรา", "Why Us"), t("ทำไมต้องเลือกเรา", "Why choose us"), items))

    ci = []
    for k, ic in (("phone", "📞"), ("line", "💬 LINE"), ("email", "✉️"), ("address", "📍"), ("hours", "🕒")):
        v = _esc((contact.get(k) or "").strip()) if contact else ""
        if v:
            ci.append('<div class="cs-ci">%s <span>%s</span></div>' % (ic, v))

    def _sname(u):                                     # ป้ายชื่อโซเชียลจาก URL
        ul = u.lower()
        if "facebook" in ul or "fb.com" in ul: return "📘 Facebook"
        if "instagram" in ul: return "📷 Instagram"
        if "line.me" in ul or "lin.ee" in ul: return "💬 LINE"
        if "tiktok" in ul: return "🎵 TikTok"
        if "youtube" in ul or "youtu.be" in ul: return "▶️ YouTube"
        return "🔗 " + u.replace("https://", "").replace("http://", "")[:22]
    sl = [u for u in (social or []) if str(u).startswith("http")]
    social_html = ('<div class="cs-social">' + "".join('<a href="%s" target="_blank" rel="noopener">%s</a>'
                   % (_esc(u), _sname(u)) for u in sl[:5]) + '</div>') if sl else ""
    form = ""
    if (report_token or "").strip():
        from app.config import settings as _s
        action = (_s.app_base_url or "").rstrip("/") + "/api/public/lead"
        form = ('<form class="cs-form" action="%s" method="post"><input type="hidden" name="token" value="%s">'
                '<input name="name" placeholder="%s"><input name="phone" required placeholder="%s">'
                '<button type="submit">%s</button></form>'
                % (_esc(action), _esc(report_token), t("ชื่อของคุณ", "Your name"),
                   t("เบอร์ติดต่อกลับ", "Your phone"), t("ให้เราติดต่อกลับ", "Contact me")))
    # แผนที่ร้าน (Google Maps embed) — จาก map link ที่ลูกค้าให้ หรือจาก 'ที่อยู่' (ไม่ต้องใช้ API key)
    import urllib.parse as _up
    addr = (contact.get("address") or "").strip() if contact else ""
    mp = (contact.get("map") or "").strip() if contact else ""
    map_url = ""
    if mp and ("output=embed" in mp or "/maps/embed" in mp):
        map_url = mp
    elif addr:
        map_url = "https://www.google.com/maps?q=%s&output=embed" % _up.quote(addr)
    map_sec = ""
    if map_url:
        map_sec = ('<section class="cs-sec" id="location"><div class="cs-wrap"><span class="cs-eyebrow cs-c">%s</span>'
                   '<h2 class="cs-c">%s</h2>'
                   '<div class="cs-map"><iframe src="%s" loading="lazy" referrerpolicy="no-referrer-when-downgrade" '
                   'style="width:100%%;height:400px;border:0;border-radius:18px;box-shadow:0 14px 40px #0000001f"></iframe></div></div></section>'
                   % (t("ที่ตั้ง", "Find Us"), t("แผนที่ร้าน", "Our Location"), _esc(map_url)))
    # ⭐ รีวิว Google (ร้านอาหาร) — ปุ่มไปดู/รีวิวบน Google Maps (โชว์รีวิวรายอันจริงต้องใช้ Places API)
    if is_food and (mp or addr) and map_sec:
        gmaps = mp if (mp and mp.startswith("http")) else ("https://www.google.com/maps/search/%s" % _up.quote(addr))
        rev = ('<div style="text-align:center;margin-top:18px"><a class="cs-btn" href="%s" target="_blank" rel="noopener" '
               'style="background:#fbbc04;color:#1a1a1a">%s</a></div>' % (_esc(gmaps), t("⭐ ดูรีวิว & รีวิวเราบน Google", "⭐ See & write reviews on Google")))
        map_sec = map_sec.replace("</div></section>", rev + "</div></section>", 1)
    # 📅 จองโต๊ะ (ร้านอาหาร) — ฟอร์มจอง → แจ้ง LINE ร้านทันที
    booking_sec = ""
    if is_food and (report_token or "").strip():
        from app.config import settings as _s2
        baction = (_s2.app_base_url or "").rstrip("/") + "/api/public/booking"
        bi = "padding:13px 15px;border:0;border-radius:12px;font-size:15px;font-family:inherit;min-width:120px;flex:1"
        booking_sec = ('<section class="cs-sec" id="booking" style="background:var(--cs-cream)"><div class="cs-wrap cs-contact-box" style="max-width:680px;text-align:center">'
                       '<span class="cs-eyebrow">%s</span><h2>%s</h2>'
                       '<form action="%s" method="post" style="display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:18px">'
                       '<input type="hidden" name="token" value="%s">'
                       '<input name="date" type="date" required style="%s"><input name="time" type="time" required style="%s">'
                       '<input name="guests" type="number" min="1" placeholder="%s" required style="%s">'
                       '<input name="name" placeholder="%s" required style="%s;border:1px solid #0000001a"><input name="phone" placeholder="%s" required style="%s;border:1px solid #0000001a">'
                       '<button type="submit" style="background:%s;color:#fff;font-weight:800;padding:13px 34px;border:0;border-radius:12px;font-size:1rem;cursor:pointer;font-family:inherit">%s</button></form></div></section>'
                       % (t("จองโต๊ะ", "Reserve"), t("จองโต๊ะล่วงหน้า", "Book a Table"), _esc(baction), _esc(report_token),
                          bi + ";border:1px solid #0000001a", bi + ";border:1px solid #0000001a", t("จำนวนคน", "Guests"), bi + ";border:1px solid #0000001a",
                          t("ชื่อ", "Your name"), bi, t("เบอร์โทร", "Phone"), bi, gold, t("ยืนยันการจอง", "Reserve Now")))
    # 📝 บล็อก/บทความ — การ์ดลิงก์ไปบทความจริงที่ระบบผลิต (SEO/AEO) → เว็บมีชีวิต + ลูกค้าเห็นเนื้อหา
    blog_sec = ""
    bl = [a for a in (blog or []) if isinstance(a, dict) and (a.get("title") and a.get("url"))][:6]
    if bl:
        cards = ""
        for a in bl:
            cov = (a.get("cover") or "").strip()
            imgd = ('<div class="cs-blog-img" style="background-image:url(\'%s\')"></div>' % _esc(cov)) if cov \
                else '<div class="cs-blog-img cs-blog-noimg"></div>'
            cards += ('<a class="cs-blog-card" href="%s" target="_blank" rel="noopener">%s'
                      '<div class="cs-blog-b"><h3>%s</h3><p>%s</p></div></a>'
                      % (_esc(a.get("url")), imgd, _esc((a.get("title") or "")[:90]), _esc((a.get("desc") or "")[:120])))
        blog_sec = ('<section class="cs-sec cs-blog" id="blog"><div class="cs-wrap"><span class="cs-eyebrow cs-c">%s</span>'
                    '<h2 class="cs-c">%s</h2><div class="cs-blog-grid">%s</div></div></section>'
                    % (t("บทความ", "Journal"), t("เรื่องราว & บทความ", "From Our Blog"), cards))
    # 🍽️ เมนูจริง (ร้านอาหาร) — no-faking: รูปเมนูจริง / หรือเมนู+ราคาที่ลูกค้าส่งมา
    menu_sec = ""
    mimgs = [u for u in (menu_images or []) if u]
    ml = [m for m in (menu or []) if isinstance(m, dict) and m.get("items")]
    menu_inner = ""
    if mimgs:                                    # รูปโปสเตอร์เมนู (ลูกค้าอัปมา) → โชว์เต็มอัตราส่วน คลิกซูมได้
        cells = "".join('<a class="cs-menuimg" href="%s" target="_blank" rel="noopener"><img src="%s" alt="%s" loading="lazy"></a>'
                        % (_esc(u), _esc(u), nm + " menu") for u in mimgs[:12])
        menu_inner += '<div class="cs-menuimgs">%s</div>' % cells
    if ml:
        cats = ""
        for m in ml:
            its = [it for it in (m.get("items") or []) if isinstance(it, dict) and (it.get("name") or "").strip()]
            if not its:
                continue
            rows = ""
            for it in its:
                nmi = _esc((it.get("name") or "").strip())
                d = _esc((it.get("desc") or "").strip())
                pr = (str(it.get("price")) if it.get("price") not in (None, "") else "").strip()
                prtxt = (("฿" + pr) if pr.replace(",", "").replace(".", "").isdigit() else _esc(pr)) if pr else ""
                rows += ('<div class="cs-mi"><div class="cs-mi-l"><span class="cs-mi-n">%s</span>%s</div>'
                         '<span class="cs-mi-dot"></span><span class="cs-mi-p">%s</span></div>'
                         % (nmi, ('<span class="cs-mi-d">%s</span>' % d) if d else "", prtxt))
            cnote = _esc((m.get("note") or "").strip())
            cats += ('<div class="cs-mcat"><h3>%s</h3>%s<div class="cs-mi-list">%s</div></div>'
                     % (_esc((m.get("cat") or "").strip()), ('<p class="cs-mcat-note">%s</p>' % cnote) if cnote else "", rows))
        mnote = _esc((menu_note or "").strip())
        menu_inner += ('<div class="cs-mcats">%s</div>%s'
                       % (cats, ('<p class="cs-menu-foot">%s</p>' % mnote) if mnote else ""))
    if menu_inner:
        menu_sec = ('<section class="cs-sec cs-menu" id="menu" style="background:var(--cs-cream)"><div class="cs-wrap">'
                    '<span class="cs-eyebrow cs-c">%s</span><h2 class="cs-c">%s</h2>%s</div></section>'
                    % (t("เมนู", "Menu"), t("เมนู & ราคา", "Our Menu"), menu_inner))
    # ติดต่อ (ครบขึ้น): ช่องทางติดต่อ + โซเชียล + ฟอร์มดักลีด
    contact_sec = ('<section class="cs-sec cs-contact" id="contact"><div class="cs-wrap cs-contact-box">'
                   '<span class="cs-eyebrow cs-c">%s</span><h2 class="cs-c">%s</h2>'
                   '<div class="cs-ci-row">%s</div>%s%s</div></section>'
                   % (t("ติดต่อ", "Contact"), _esc((c.get("contact_title") or "").strip() or t("สนใจ? ติดต่อเราเลย", "Get in touch")),
                      "".join(ci), social_html, form))

    css = ("""<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,600&family=Prompt:wght@400;500;600;700&display=swap');
:root{--cs-ink:%s;--cs-gold:%s;--cs-cream:%s;--cs-display:'Cormorant Garamond','Prompt','Sarabun',serif}
.cs-site{font-family:'Prompt','Sarabun','Segoe UI',sans-serif;color:var(--cs-ink);background:#fff;line-height:1.7;-webkit-font-smoothing:antialiased}
.cs-site *{box-sizing:border-box}
.cs-wrap{max-width:1120px;margin:0 auto;padding:0 22px}
.cs-nav{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.92);backdrop-filter:blur(10px);border-bottom:1px solid #0000000f}
.cs-nav .cs-wrap{display:flex;align-items:center;justify-content:space-between;height:64px}
.cs-brand{font-weight:800;font-size:1.15rem;letter-spacing:-.01em}
.cs-logo{height:44px;width:auto;max-width:210px;object-fit:contain;display:block}
.cs-hero-logo{height:82px;width:auto;max-width:280px;object-fit:contain;margin:0 auto 18px;display:block;filter:drop-shadow(0 6px 20px #0007)}
.cs-v2 .cs-hero-logo{margin-left:0}
.cs-nav a.cs-cta{background:var(--cs-gold);color:#fff;padding:9px 20px;border-radius:999px;text-decoration:none;font-weight:700;font-size:.92rem}
.cs-hero{position:relative;min-height:78vh;display:grid;place-items:center;text-align:center;color:#fff;overflow:hidden}
.cs-hero-bg{position:absolute;inset:0;background-size:cover;background-position:center;transform:scale(1.03)}
.cs-hero-bg::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,%s00 0%%,%scc 100%%),linear-gradient(%s99,%s99)}
.cs-hero-in{position:relative;z-index:2;padding:80px 22px;max-width:820px}
.cs-hero .cs-eyebrow{color:#fff;opacity:.9}
.cs-hero h1{font-family:var(--cs-display);font-size:clamp(2.7rem,7.2vw,4.8rem);line-height:1;margin:12px 0 16px;font-weight:700;letter-spacing:.005em;text-shadow:0 2px 34px #0007}
.cs-hero p{font-size:clamp(1.05rem,2.4vw,1.35rem);opacity:.96;margin:0 auto 28px;max-width:600px}
.cs-btn{display:inline-block;background:var(--cs-gold);color:#fff;font-weight:800;padding:15px 40px;border-radius:999px;text-decoration:none;font-size:1.05rem;box-shadow:0 12px 30px %s55;transition:transform .15s}
.cs-btn:hover{transform:translateY(-2px)}
.cs-eyebrow{display:inline-block;text-transform:uppercase;letter-spacing:.18em;font-size:.72rem;font-weight:800;color:var(--cs-gold);margin-bottom:8px}
.cs-c{text-align:center;display:block}
.cs-sec{padding:clamp(48px,8vw,90px) 0}
.cs-sec h2{font-family:var(--cs-display);font-size:clamp(1.9rem,4.4vw,2.9rem);font-weight:700;letter-spacing:.005em;margin:0 0 16px}
.cs-about{display:grid;grid-template-columns:1.05fr .95fr;gap:48px;align-items:center}
.cs-about.cs-about-solo{grid-template-columns:1fr;max-width:760px;text-align:center}
.cs-about-txt p{color:#00000099;font-size:1.08rem;margin:0}
.cs-about-img{border-radius:20px;min-height:360px;background-size:cover;background-position:center;box-shadow:0 24px 60px #0000001f}
.cs-grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:22px}
.cs-card{background:var(--cs-cream);border-radius:18px;padding:30px 26px;text-align:center}
.cs-card .cs-ico{font-size:2.2rem;margin-bottom:10px}
.cs-card h3{margin:0 0 8px;font-size:1.2rem;font-weight:800}
.cs-card p{margin:0;color:#00000099;font-size:.98rem}
.cs-gal{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:26px}
.cs-gal img{width:100%%;height:230px;object-fit:cover;border-radius:16px;box-shadow:0 10px 26px #0000001a}
.cs-gal img:nth-child(1){grid-column:span 2;grid-row:span 2;height:auto;min-height:474px}
.cs-why{background:var(--cs-cream)}
.cs-why-list{list-style:none;padding:0;max-width:640px;margin:26px auto 0;display:grid;gap:14px}
.cs-why-list li{display:flex;gap:14px;align-items:flex-start;font-size:1.1rem;font-weight:600}
.cs-why-list li span{flex:none;width:28px;height:28px;border-radius:50%%;background:var(--cs-gold);color:#fff;display:grid;place-items:center;font-size:.9rem}
.cs-contact{background:var(--cs-ink);color:#fff}
.cs-contact h2,.cs-contact .cs-eyebrow{color:#fff}.cs-contact .cs-eyebrow{opacity:.7}
.cs-contact-box{max-width:620px;text-align:center}
.cs-ci-row{display:flex;flex-wrap:wrap;gap:10px 26px;justify-content:center;margin:18px 0 6px}
.cs-ci{opacity:.92;font-size:1.02rem}
.cs-form{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:22px}
.cs-form input{flex:1;min-width:200px;max-width:260px;padding:14px 18px;border:0;border-radius:12px;font-size:1rem;font-family:inherit}
.cs-form button{background:var(--cs-gold);color:#fff;font-weight:800;padding:14px 34px;border:0;border-radius:12px;font-size:1rem;cursor:pointer}
.cs-foot{background:var(--cs-ink);color:#fff9;text-align:center;padding:26px;font-size:.88rem;border-top:1px solid #ffffff14}
.cs-social{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin:16px 0 4px}
.cs-social a{color:#fff;background:#ffffff22;padding:8px 16px;border-radius:999px;text-decoration:none;font-size:.9rem;font-weight:600}
.cs-social a:hover{background:#ffffff38}
.cs-blog-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:26px}
.cs-blog-card{text-decoration:none;color:inherit;background:var(--cs-cream);border-radius:16px;overflow:hidden;display:block;transition:transform .15s,box-shadow .15s}
.cs-blog-card:hover{transform:translateY(-5px);box-shadow:0 18px 44px #00000022}
.cs-blog-img{height:180px;background-size:cover;background-position:center}
.cs-blog-noimg{background:linear-gradient(135deg,var(--cs-ink),var(--cs-gold))}
.cs-blog-b{padding:16px 18px}.cs-blog-b h3{margin:0 0 6px;font-size:1.06rem;font-weight:800;line-height:1.3}
.cs-blog-b p{margin:0;color:#00000099;font-size:.9rem}
@media(max-width:760px){.cs-about{grid-template-columns:1fr;text-align:center}.cs-grid3{grid-template-columns:1fr}.cs-gal{grid-template-columns:1fr 1fr}.cs-gal img:nth-child(1){grid-column:span 2;min-height:230px}.cs-blog-grid{grid-template-columns:1fr}}
</style>""" % (ink, gold, cream, ink, ink, ink, ink, gold))

    css += ("""<style>
.cs-v2 .cs-hero{min-height:auto;text-align:left;color:var(--cs-ink)}
.cs-v2 .cs-split{display:grid;grid-template-columns:1fr 1fr;gap:0;align-items:stretch;min-height:88vh}
.cs-v2 .cs-split-txt{display:flex;flex-direction:column;justify-content:center;padding:60px clamp(24px,5vw,72px)}
.cs-v2 .cs-split-txt .cs-eyebrow{color:var(--cs-gold)}
.cs-v2 .cs-split-txt h1{font-size:clamp(2.2rem,4.5vw,3.6rem);text-shadow:none;margin:8px 0 16px}
.cs-v2 .cs-split-txt p{color:#00000099;opacity:1}
.cs-v2 .cs-split-img{background-size:cover;background-position:center;min-height:340px}
.cs-v3 .cs-hero{align-items:end;text-align:left}
.cs-v3 .cs-hero .cs-wrap{width:100%%;padding-bottom:54px}
.cs-v3 .cs-hero-cardbox{background:#fffffff2;color:var(--cs-ink);max-width:560px;padding:40px 42px;border-radius:22px;box-shadow:0 30px 80px #00000040}
.cs-v3 .cs-hero-cardbox .cs-eyebrow{color:var(--cs-gold)}
.cs-v3 .cs-hero-cardbox h1{font-size:clamp(2rem,4.4vw,3.2rem);text-shadow:none;margin:6px 0 12px}
.cs-v3 .cs-hero-cardbox p{opacity:1;color:#00000099}
.cs-v3 .cs-card{border-radius:24px}.cs-v3 .cs-gal img{border-radius:22px}
@media(max-width:760px){.cs-v2 .cs-split{grid-template-columns:1fr}.cs-v2 .cs-split-img{min-height:260px;order:-1}}
.cs-menuimgs{display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:940px;margin:34px auto 0}
.cs-menuimg{display:block;border-radius:14px;overflow:hidden;box-shadow:0 14px 40px #0000001f;transition:transform .18s,box-shadow .18s;background:#fff}
.cs-menuimg:hover{transform:translateY(-4px);box-shadow:0 22px 54px #00000030}
.cs-menuimg img{width:100%;height:auto;display:block}
.cs-menuimgs + .cs-mcats{margin-top:44px}
@media(max-width:640px){.cs-menuimgs{grid-template-columns:1fr;gap:14px}}
.cs-mcats{display:grid;grid-template-columns:1fr 1fr;gap:36px 54px;margin-top:36px;text-align:left}
.cs-mcat h3{font-size:1.32rem;color:var(--cs-ink);margin:0 0 2px;padding-bottom:9px;border-bottom:2px solid var(--cs-gold);display:inline-block;letter-spacing:.02em}
.cs-mcat-note{font-size:.84rem;color:#00000088;margin:6px 0 0}
.cs-mi-list{margin-top:15px;display:flex;flex-direction:column;gap:13px}
.cs-mi{display:flex;align-items:baseline;gap:9px}
.cs-mi-l{display:flex;flex-direction:column;min-width:0}
.cs-mi-n{font-weight:700;color:var(--cs-ink)}
.cs-mi-d{font-size:.81rem;color:#00000077;margin-top:2px;line-height:1.4}
.cs-mi-dot{flex:1;border-bottom:1px dotted #0000003a;transform:translateY(-4px);min-width:16px}
.cs-mi-p{font-weight:800;color:var(--cs-gold);white-space:nowrap}
.cs-menu-foot{text-align:center;color:#00000080;font-size:.82rem;margin-top:32px;font-style:italic}
.cs-nav-r{display:flex;align-items:center;gap:22px}
.cs-nav-lnk{color:var(--cs-ink);text-decoration:none;font-weight:600;font-size:.95rem;opacity:.85}
.cs-nav-lnk:hover{opacity:1;color:var(--cs-gold)}
@media(max-width:760px){.cs-mcats{grid-template-columns:1fr;gap:28px}.cs-nav-lnk{display:none}}
/* เส้นทองบางใต้หัวข้อ section (จังหวะพรีเมียม ทุกสไตล์) */
.cs-sec h2.cs-c{position:relative;padding-bottom:22px}
.cs-sec h2.cs-c::after{content:"";position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:50px;height:2px;background:var(--cs-gold)}
/* ===== สไตล์ 1 · Moonlit Luxe — คืนจันทร์ริมทะเล (cinematic + แสงจันทร์อุ่น) ===== */
.cs-v1 .cs-hero{min-height:86vh}
.cs-v1 .cs-hero-bg::after{background:
  radial-gradient(115% 78% at 80% 15%,rgba(224,164,75,.22),transparent 58%),
  linear-gradient(180deg,rgba(11,26,46,.30) 0%,rgba(11,26,46,.10) 40%,rgba(11,26,46,.74) 80%,rgba(8,20,38,.95) 100%)}
.cs-v1 .cs-hero h1{letter-spacing:.012em;text-shadow:0 2px 46px rgba(7,19,36,.62)}
.cs-v1 .cs-hero .cs-eyebrow{color:#e6b45c;opacity:1}
.cs-v1 .cs-hero p{color:rgba(244,236,214,.92)}
.cs-v1 .cs-btn{border-radius:3px}
.cs-v1 .cs-nav{background:rgba(11,26,46,.86);border-bottom:1px solid rgba(244,236,214,.12)}
.cs-v1 .cs-nav .cs-brand{color:#f4ecd6}
.cs-v1 .cs-nav-lnk{color:rgba(244,236,214,.82)}
.cs-v1 .cs-nav-lnk:hover{color:var(--cs-gold)}
</style>""")
    menu_lnk = ('<a class="cs-nav-lnk" href="#menu">%s</a>' % t("เมนู", "Menu")) if menu_sec else ""
    _logo = (logo or "").strip()
    brand = ('<img class="cs-logo" src="%s" alt="%s">' % (_esc(_logo), nm)) if _logo else ('<span class="cs-brand">%s</span>' % nm)
    hero_logo = ('<img class="cs-hero-logo" src="%s" alt="%s">' % (_esc(_logo), nm)) if _logo else ""
    nav = ('<nav class="cs-nav"><div class="cs-wrap">%s'
           '<span class="cs-nav-r">%s<a class="cs-cta" href="#contact">%s</a></span></div></nav>' % (brand, menu_lnk, cta))
    eyebrow = biz or t("ยินดีต้อนรับ", "Welcome")
    bgcss = ("url('%s')" % _esc(hero_bg)) if hero_bg else ("linear-gradient(135deg,%s,%s)" % (ink, gold))
    if variant == 2:                      # Modern — hero แบ่งซ้าย-ขวา
        hero = ('<header class="cs-hero"><div class="cs-wrap cs-split">'
                '<div class="cs-split-txt">%s<span class="cs-eyebrow">%s</span><h1>%s</h1><p>%s</p>'
                '<a class="cs-btn" href="#contact">%s</a></div>'
                '<div class="cs-split-img" style="background-image:%s"></div></div></header>'
                % (hero_logo, eyebrow, headline, subhead, cta, bgcss))
    elif variant == 3:                    # Warm — hero การ์ดซ้อนบนรูป
        hero = ('<header class="cs-hero"><div class="cs-hero-bg" style="background:%s;background-size:cover;background-position:center"></div>'
                '<div class="cs-wrap"><div class="cs-hero-cardbox">%s<span class="cs-eyebrow">%s</span><h1>%s</h1><p>%s</p>'
                '<a class="cs-btn" href="#contact">%s</a></div></div></header>'
                % (bgcss, hero_logo, eyebrow, headline, subhead, cta))
    else:                                 # Luxe — hero เต็มจอ กลาง (default)
        hero = ('<header class="cs-hero"><div class="cs-hero-bg" style="background:%s;background-size:cover;background-position:center"></div>'
                '<div class="cs-hero-in">%s<span class="cs-eyebrow">%s</span><h1>%s</h1><p>%s</p>'
                '<a class="cs-btn" href="#contact">%s</a></div></header>'
                % (bgcss, hero_logo, eyebrow, headline, subhead, cta))
    foot = '<footer class="cs-foot">%s · %s</footer>' % (nm, t("สร้างเว็บโดย ImVisible", "Built with ImVisible"))
    return ('<main class="cs-site cs-v%d">' % variant) + css + nav + hero + about_sec + feats + menu_sec + gallery + why + blog_sec + booking_sec + map_sec + contact_sec + foot + '</main>'


_CS_VARIANTS = [("1", "✨ Luxe", ("หรู มินิมอล · hero เต็มจอ", "Luxe · full-screen hero")),
                ("2", "◧ Modern", ("โมเดิร์น · hero แบ่งซ้าย-ขวา", "Modern · split hero")),
                ("3", "☕ Warm", ("อบอุ่น · การ์ดซ้อนบนรูป", "Warm · card over photo"))]


def render_site_chooser(name, token, base, lang="th", chosen: int = 0) -> str:
    """หน้าสาธารณะให้ 'ลูกค้าเลือกดีไซน์' 3 แบบ (พรีวิวสด) → กดเลือก → ระบบสร้างจริง"""
    en = str(lang).startswith("en")
    def t(th, e): return e if en else th
    nm = _esc((name or "").strip() or t("เว็บของคุณ", "Your website"))
    tk = _esc((token or "").strip())
    b = (base or "").rstrip("/")
    cards = ""
    for v, title, (dth, den) in _CS_VARIANTS:
        prev = "%s/api/site/%s/preview?v=%s" % (b, tk, v)
        picked = (str(chosen) == v)
        cards += ('<div class="ch-card%s"><div class="ch-frame"><iframe src="%s" loading="lazy" title="%s"></iframe>'
                  '<a class="ch-full" href="%s" target="_blank" rel="noopener">%s</a></div>'
                  '<div class="ch-body"><div class="ch-t">%s</div><div class="ch-d">%s</div>'
                  '<form method="post" action="%s/api/site/%s/select"><input type="hidden" name="v" value="%s">'
                  '<button type="submit"%s>%s</button></form></div></div>'
                  % (" ch-on" if picked else "", _esc(prev), _esc(title), _esc(prev), t("เปิดดูเต็มจอ ↗", "Open full ↗"),
                     _esc(title), _esc(den if en else dth), b, tk, v,
                     " disabled" if picked else "", t("เลือกแล้ว ✓", "Chosen ✓") if picked else t("เลือกแบบนี้", "Choose this")))
    head = t("เลือกดีไซน์เว็บที่คุณชอบ", "Choose your website design")
    sub = t("เราออกแบบให้ 3 สไตล์จากข้อมูลร้านคุณ — กดเลือกแบบที่ใช่ แล้วเราลงมือทำให้จริงทันที",
            "3 styles designed from your business info — pick your favorite and we'll build it")
    return ("""<!doctype html><html lang="%s"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>%s · %s</title>
<meta name="robots" content="noindex">
<style>
*{box-sizing:border-box}body{margin:0;font-family:'Sarabun','Prompt','Segoe UI',sans-serif;background:#0f1524;color:#eaf1fb}
.ch-hd{text-align:center;padding:44px 20px 8px}.ch-hd h1{font-size:clamp(1.5rem,4vw,2.2rem);margin:0 0 8px;font-weight:800}
.ch-hd p{color:#9fb0c8;margin:0 auto;max-width:560px;font-size:1.02rem}
.ch-brand{color:#4f8cff;font-weight:800;letter-spacing:.16em;text-transform:uppercase;font-size:.74rem;margin-bottom:10px}
.ch-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:1240px;margin:26px auto;padding:0 20px}
.ch-card{background:#16223a;border:1px solid #26374f;border-radius:18px;overflow:hidden;transition:transform .15s,border-color .15s}
.ch-card:hover{transform:translateY(-4px);border-color:#4f8cff}
.ch-card.ch-on{border-color:#35c98a;box-shadow:0 0 0 2px #35c98a55}
.ch-frame{position:relative;height:420px;overflow:hidden;background:#fff}
.ch-frame iframe{width:1280px;height:1050px;border:0;transform:scale(.372);transform-origin:top left;pointer-events:none}
.ch-full{position:absolute;top:10px;right:10px;background:#0009;color:#fff;text-decoration:none;font-size:.78rem;padding:6px 12px;border-radius:999px;backdrop-filter:blur(4px)}
.ch-body{padding:16px 18px 20px}.ch-t{font-weight:800;font-size:1.12rem}.ch-d{color:#9fb0c8;font-size:.9rem;margin:2px 0 14px}
.ch-body button{width:100%%;background:#4f8cff;color:#fff;border:0;border-radius:12px;padding:13px;font-size:1rem;font-weight:800;cursor:pointer;font-family:inherit}
.ch-body button:hover{background:#3b78ec}.ch-body button:disabled{background:#35c98a;cursor:default}
.ch-foot{text-align:center;color:#6b7c96;padding:24px;font-size:.85rem}
@media(max-width:900px){.ch-grid{grid-template-columns:1fr}.ch-frame{height:460px}.ch-frame iframe{transform:scale(.62)}}
</style></head><body>
<div class="ch-hd"><div class="ch-brand">ImVisible</div><h1>%s</h1><p>%s</p></div>
<div class="ch-grid">%s</div>
<div class="ch-foot">%s</div></body></html>""" % (
        "en" if en else "th", nm, head, head, _esc(sub), cards,
        t("ยังไม่ถูกใจ? ตอบกลับแอดมินได้เลย เราปรับให้", "Not quite right? Reply to us and we'll adjust")))


def inject_photos(html: str, urls, lang="th") -> str:
    """แทรกรูปจริงของลูกค้าเข้า HTML ที่ IM WEB สร้าง (สลับ hero + เพิ่มแกลเลอรี) — ใช้เมื่อ build ผ่าน IM WEB"""
    if not html or not urls:
        return html
    urls = [u for u in urls if u][:6]
    out = html
    m = re.search(r'<img[^>]*\ssrc=["\']([^"\']+)["\']', out)
    if m:
        out = out[:m.start(1)] + _esc(urls[0]) + out[m.end(1):]
    lbl = "Gallery" if str(lang).startswith("en") else "รูปภาพของเรา"
    cells = "".join('<img src="%s" alt="%s" loading="lazy" style="width:100%%;height:220px;object-fit:cover;border-radius:12px">' % (_esc(u), lbl) for u in urls)
    gal = ('<section style="max-width:1100px;margin:40px auto;padding:0 20px"><h2 style="text-align:center;margin-bottom:18px">%s</h2>'
           '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px">%s</div></section>' % (lbl, cells))
    return out.replace("</body>", gal + "</body>", 1) if "</body>" in out else (out + gal)


def _cta_box(proj) -> str:
    """กล่องดักลูกค้า (CTA) ท้ายบทความ — เนียนขายบริการ/พาไปเก็บลีด · ต่อโปรเจ็ค (ไม่โผล่บล็อกลูกค้าที่ไม่ได้เปิด)
    ปุ่มลิงก์ล้วน = ใช้ได้ทุกโดเมน ไม่ติด CORS"""
    import json as _json
    raw = getattr(proj, "cta_json", "") or ""
    if not raw.strip():
        return ""
    try:
        c = _json.loads(raw)
    except Exception:  # noqa: BLE001
        return ""
    if not c.get("enabled"):
        return ""
    headline = _esc((c.get("headline") or "").strip())
    text = _esc((c.get("text") or "").strip())
    btn = _esc((c.get("button") or "ปรึกษาฟรี").strip())
    url = (c.get("url") or "").strip()
    capture = bool(c.get("capture"))
    token = (getattr(proj, "report_token", "") or "").strip()
    box = ("background:linear-gradient(135deg,#3d6bff,#5b4ff0);color:#fff;border-radius:16px;"
           "padding:28px 26px;margin:34px 0;text-align:center")
    inner = ""
    if headline:
        inner += '<div style="font-size:20px;font-weight:800;margin-bottom:6px">%s</div>' % headline
    if text:
        inner += '<div style="opacity:.92;font-size:15px;line-height:1.6;margin-bottom:12px">%s</div>' % text
    if capture and token:                              # ฟอร์มดักลีดจริง (native submit → เก็บ Lead + ส่งลูกค้า) — ข้ามโดเมนได้ ไม่ติด CORS
        from app.config import settings as _s
        action = (_s.app_base_url or "").rstrip("/") + "/api/public/lead"
        istyle = ("width:100%;max-width:300px;margin:5px auto;display:block;padding:11px 14px;border:0;"
                  "border-radius:10px;font-size:15px;box-sizing:border-box;color:#0f1b2d")
        inner += ('<form action="%s" method="post" style="margin-top:2px">'
                  '<input type="hidden" name="token" value="%s">'
                  '<input name="name" placeholder="ชื่อของคุณ" style="%s">'
                  '<input name="phone" required placeholder="เบอร์โทรติดต่อกลับ" style="%s">'
                  '<button type="submit" style="margin-top:8px;background:#fff;color:#3d6bff;font-weight:800;'
                  'padding:12px 30px;border:0;border-radius:999px;font-size:15px;cursor:pointer">%s</button>'
                  '</form>' % (_esc(action), _esc(token), istyle, istyle, btn))
    elif url:
        inner += ('<a href="%s" target="_blank" rel="noopener" style="display:inline-block;margin-top:2px;'
                  'background:#fff;color:#3d6bff;font-weight:800;padding:12px 28px;border-radius:999px;'
                  'text-decoration:none">%s</a>' % (_esc(url), btn))
    if not inner:
        return ""
    return '<aside style="%s">%s</aside>' % (box, inner)


def render_article_page(proj, art, related=None) -> str:
    home = project_public_home(proj)
    canonical = art.url or public_url_for(proj, art)
    lang = "en" if str(proj.language).lower().startswith("en") else "th"
    en = (lang == "en")

    def t(th, en_):
        return en_ if en else th

    author = proj.name or proj.domain
    cluster = getattr(art, "cluster", "") or t("บทความ", "Articles")
    dt = getattr(art, "updated_at", None)
    body, toc = _build_toc(art.html or "")
    has_h1 = bool(re.search(r"<h1[\s>]", body, re.I))

    byline = ('<div class="byline"><span class="who"><span class="av">%s</span>%s</span>'
              % (_esc(author[:1].upper()), t("ทีม %s", "By %s") % _esc(author)))
    if _fmt_date(dt):
        byline += '<span class="sep"></span><span>%s</span>' % (t("อัปเดต %s", "Updated %s") % _esc(_fmt_date(dt)))
    byline += '<span class="sep"></span><span>%s</span></div>' % (t("อ่าน ~%d นาที", "%d min read") % _reading_time(getattr(art, "words", 0)))

    toc_html = ""
    if len(toc) >= 3:
        lis = "".join('<li class="l%s"><a href="#%s">%s</a></li>' % (lvl, hid, _esc(text))
                      for lvl, hid, text in toc)
        toc_html = '<nav class="toc"><div class="lb">%s</div><ol>%s</ol></nav>' % (t("สารบัญ", "Contents"), lis)

    abox = ('<div class="abox"><div class="av">%s</div><div><div class="nm">%s</div>'
            '<div class="ds">%s</div></div></div>'
            % (_esc(author[:1].upper()), t("ทีม %s", "%s Team") % _esc(author),
               t("ผลิต + ดูแลคอนเทนต์โดยระบบ AEO ของ ImVisible — ทุกบทความเขียนให้ตอบคำถามจริง ตรวจข้อเท็จจริง และปรับให้สดใหม่อยู่เสมอ",
                 "Content produced &amp; maintained by ImVisible's AEO system — every article is written to answer real questions, fact-checked, and kept fresh.")))

    rel_html = ""
    if related:
        cards = "".join('<a class="rcard" href="%s"><div class="t">%s</div><div class="x">%s</div></a>'
                        % (_esc(a.url or public_url_for(proj, a)), _esc(a.title), _esc(_desc(a)))
                        for a in related)
        rel_html = '<section class="rel"><div class="lb">%s</div><div class="grid">%s</div></section>' % (t("อ่านต่อ", "Read more"), cards)

    header = "" if has_h1 else "<h1>%s</h1>" % _esc(art.title)
    # 🎯 Answer Box (TL;DR) — ก้อนคำตอบสั้นบนสุด = ส่วนที่ AI/Google หยิบไปตอบเป๊ะ (คู่กับ Speakable schema)
    _tldr = _desc(art)
    tldr_html = ('<div class="tldr" style="background:var(--wash);border:1px solid var(--line);border-left:4px solid var(--blue);'
                 'border-radius:0 14px 14px 0;padding:16px 20px;margin:8px 0 28px;font-size:1.05rem;line-height:1.7;color:var(--ink)">'
                 '<span style="display:block;font-size:.7rem;letter-spacing:.16em;text-transform:uppercase;font-weight:800;color:var(--blue);margin-bottom:5px">%s</span>%s</div>'
                 % (t("สรุปคำตอบ", "In short"), _esc(_tldr))) if _tldr else ""
    cover = getattr(art, "cover_url", "") or ""
    cover_html = ('<figure class="cover"><img src="%s" alt="%s" fetchpriority="high" decoding="async" width="1200" height="675"></figure>'
                  % (_esc(cover), _esc(art.title))) if cover else ""
    return (
        _head(art.title, _desc(art), canonical, lang,
              _article_jsonld(proj, art, canonical, home, lang), "article",
              published=dt, modified=dt, image=cover)
        + "<body>" + _chrome(proj, home)
        + '<main><div class="wrap">'
        + '<div class="crumb"><a href="%s">%s</a> › %s</div>' % (_esc(home), t("หน้าแรก", "Home"), _esc(cluster))
        + '<span class="eyebrow">%s</span>' % _esc(cluster)
        + header + byline + cover_html + tldr_html + toc_html
        + "<article>" + body + "</article>"
        + _cta_box(proj)
        + _share_bar(canonical, art.title, en)
        + abox + rel_html
        + _footer(proj) + "</div></main></body></html>"
    )


_REPORT_ENGINES = {"openai": "ChatGPT", "gemini": "Gemini", "perplexity": "Perplexity", "anthropic": "Claude"}


# ── สถานะไปป์ไลน์ต่อคีย์เวิร์ด (ทำให้เห็นว่า "คีย์ที่ยังไม่ติด" ระบบกำลังทำอะไรอยู่) ──
# บทความถูกสร้างด้วย title = หัวข้อ (topic) ตรงตัว → จับคู่คีย์↔บทความด้วยชื่อได้
_STAGE_LABELS = {
    "published": ("✍️ เขียน+เผยแพร่แล้ว", "✍️ Published"),
    "scheduled": ("📅 ตั้งเวลาเผยแพร่", "📅 Scheduled"),
    "drafting":  ("📝 กำลังเขียน/รออนุมัติ", "📝 Writing / review"),
    "queued":    ("🕒 อยู่ในคิวเขียน", "🕒 In write queue"),
}
_STATUS_PRIORITY = {"published": 5, "scheduled": 4, "ready": 3, "factcheck": 2, "draft": 1}


def article_status_map(rows) -> dict:
    """rows = [(title, status)] → {title_lower: best_status} (เลือกสถานะที่ 'ก้าวหน้าที่สุด' ถ้าซ้ำ)"""
    m: dict = {}
    for title, status in rows:
        key = (title or "").strip().lower()
        if not key:
            continue
        if key not in m or _STATUS_PRIORITY.get(status, 0) > _STATUS_PRIORITY.get(m[key], 0):
            m[key] = status
    return m


def keyword_stage(status: str, en: bool = False) -> tuple:
    """สถานะบทความ (ว่าง=ยังไม่มีบทความ) → (stage, label) สำหรับโชว์ในรายงาน"""
    if not status:
        stage = "queued"
    elif status == "published":
        stage = "published"
    elif status == "scheduled":
        stage = "scheduled"
    else:                                    # draft | factcheck | ready
        stage = "drafting"
    th, e = _STAGE_LABELS[stage]
    return stage, (e if en else th)


async def report_data(project_id: int, days: int) -> dict | None:
    """รวมข้อมูลรายงานของโปรเจ็ค (อันดับ · AEO · AI citation · บทความ) — สำหรับหน้ารายงานสาธารณะ (ไม่ต้องล็อกอิน)"""
    from datetime import datetime, timezone, timedelta
    from app.db.models import Project, Article, RankSnapshot, CitationSnapshot, CitationExample
    if not db.enabled():
        return None
    since = datetime.now(timezone.utc) - timedelta(days=days)
    async with db.session() as s:
        proj = await s.get(Project, project_id)
        if not proj:
            return None
        rows = (await s.execute(select(RankSnapshot).where(RankSnapshot.project_id == project_id)
                .order_by(RankSnapshot.checked_at))).scalars().all()
        arts = (await s.execute(select(Article).where(Article.project_id == project_id,
                Article.status == "published").order_by(Article.id.desc()))).scalars().all()
        all_art_rows = (await s.execute(select(Article.title, Article.status)
                .where(Article.project_id == project_id))).all()
        csnaps = (await s.execute(select(CitationSnapshot).where(CitationSnapshot.project_id == project_id)
                .order_by(CitationSnapshot.sampled_at))).scalars().all()
        cexs = (await s.execute(select(CitationExample).where(CitationExample.project_id == project_id)
                .order_by(CitationExample.id.desc()).limit(6))).scalars().all()
    latest, series = {}, {}
    for r in rows:
        latest[r.keyword] = {"keyword": r.keyword, "rank": r.rank, "on_page1": bool(r.on_page1)}
        series.setdefault(r.keyword, []).append(r.rank)
    for kw, info in latest.items():
        seq = [x for x in series[kw] if x is not None]
        info["best"] = min(seq) if seq else None
        info["prev"] = series[kw][-2] if len(series[kw]) >= 2 else None
    kws = sorted(latest.values(), key=lambda k: (k["rank"] is None, k["rank"] if k["rank"] is not None else 999))
    # เพิ่มคีย์จากแผน (topic_plan) ที่ยังไม่ถูกวัด → ลูกค้าเห็นครบ + สถานะที่ระบบทำถึงไหน
    import json as _json
    have_kw = {str(k.get("keyword") or "").strip().lower() for k in kws}
    try:
        for it in (_json.loads(getattr(proj, "topic_plan", "") or "") if (getattr(proj, "topic_plan", "") or "").strip() else []):
            topic = ((it.get("topic") if isinstance(it, dict) else str(it)) or "").strip()
            if not topic or topic.lower() in have_kw:
                continue
            have_kw.add(topic.lower())
            kws.append({"keyword": topic, "rank": None, "on_page1": False, "best": None, "prev": None, "pending": True})
    except Exception:  # noqa: BLE001
        pass
    kws = sorted(kws, key=lambda k: (k["rank"] is None, k["rank"] if k["rank"] is not None else 999))
    status_map = article_status_map(all_art_rows)
    _en = str(getattr(proj, "language", "") or "").lower().startswith("en")
    pipeline = {"published": 0, "scheduled": 0, "drafting": 0, "queued": 0}
    for k in kws:
        stage, label = keyword_stage(status_map.get(str(k.get("keyword") or "").strip().lower(), ""), _en)
        k["stage"] = stage
        k["stage_label"] = label
        pipeline[stage] = pipeline.get(stage, 0) + 1
    ranked = [k["rank"] for k in kws if k["rank"] is not None]
    scored = [a.aeo_score for a in arts if getattr(a, "aeo_score", 0)]

    def _aware(dt):
        return (dt.replace(tzinfo=timezone.utc) if (dt and not dt.tzinfo) else dt)
    new_arts = [a for a in arts if _aware(getattr(a, "created_at", None)) and _aware(a.created_at) >= since]
    by_bucket = {}
    for c in csnaps:
        b = c.sampled_at.strftime("%Y-%m-%dT%H:%M") if c.sampled_at else ""
        by_bucket.setdefault(b, {})[c.engine] = c.sov_percent
    runs = list(by_bucket.values())
    per_engine = runs[-1] if runs else {}
    sov_vals = [v for v in per_engine.values() if v is not None]
    sov_now = round(sum(sov_vals) / len(sov_vals), 1) if sov_vals else None

    # --- แนวโน้ม: อันดับเฉลี่ยตามเวลา (bucket รายวัน · ยิ่งต่ำยิ่งดี) ---
    rank_buckets: dict[str, list] = {}
    for r in rows:
        if r.rank is None or not r.checked_at:
            continue
        rank_buckets.setdefault(r.checked_at.strftime("%Y-%m-%d"), []).append(r.rank)
    rank_trend = [round(sum(v) / len(v), 1) for _, v in sorted(rank_buckets.items())]
    avg_prev = rank_trend[-2] if len(rank_trend) >= 2 else None

    # --- แนวโน้ม: Share of Voice overall ต่อรอบที่รันจริง ---
    sov_trend = []
    for run in runs:
        vv = [v for v in run.values() if v is not None]
        if vv:
            sov_trend.append(round(sum(vv) / len(vv), 1))
    sov_prev = sov_trend[-2] if len(sov_trend) >= 2 else None

    # --- คู่แข่งที่ AI แนะนำในหมวดเรา (ต้องแซงในสนาม AEO) ---
    comp_names = []
    try:
        _comps = _json.loads(getattr(proj, "ai_competitors", "") or "") if (getattr(proj, "ai_competitors", "") or "").strip() else []
    except Exception:  # noqa: BLE001
        _comps = []
    for c in (_comps or [])[:10]:
        nm = (c.get("name") or c.get("brand") or c.get("competitor") or "") if isinstance(c, dict) else str(c)
        nm = str(nm).strip()
        if nm and nm.lower() not in {x.lower() for x in comp_names}:
            comp_names.append(nm)

    # --- ระดับความสำเร็จ AEO (0=ยังไม่เริ่ม · 1=เริ่มติด · 2=มีส่วนแบ่ง · 3=นำในหมวด) ---
    if sov_now is None or sov_now <= 0:
        stage_ix = 0
    elif sov_now < 20:
        stage_ix = 1
    elif sov_now < 50:
        stage_ix = 2
    else:
        stage_ix = 3

    # คำถาม AEO ที่ลูกค้าตั้งเอง (สิ่งที่คนถาม AI) → โชว์ว่าเรากำลัง 'ดัน' ให้ AI แนะนำเขาบนคำถามพวกนี้
    aeo_qs: list[str] = []
    try:
        _rawq = getattr(proj, "aeo_questions", "") or ""
        if _rawq.strip():
            _seenq = set()
            for q in (_json.loads(_rawq) or []):
                qq = str(q).strip()
                if qq and qq.lower() not in _seenq:
                    _seenq.add(qq.lower()); aeo_qs.append(qq)
    except Exception:  # noqa: BLE001
        pass
    cited_qs = {str(getattr(e, "question", "") or "").strip().lower() for e in cexs}

    return {
        "proj": proj, "kws": kws[:50], "pipeline": pipeline,
        "page1": sum(1 for k in kws if k["on_page1"]),
        "top3": sum(1 for k in kws if k["rank"] is not None and k["rank"] <= 3),
        "avg": round(sum(ranked) / len(ranked), 1) if ranked else None,
        "avg_prev": avg_prev, "rank_trend": rank_trend,
        "keywords_tracked": len(latest), "published": len(arts),
        "aeo_avg": round(sum(scored) / len(scored)) if scored else None,
        "new_count": len(new_arts), "recent": arts[:6],
        "per_engine": per_engine, "sov": sov_now, "sov_prev": sov_prev, "sov_trend": sov_trend,
        "competitors": comp_names, "stage": stage_ix,
        "examples": cexs,
        "aeo_questions": aeo_qs[:10], "cited_questions": cited_qs,
    }


_REPORT_CSS = """
*{box-sizing:border-box}:root{--pp:#fff;--ink:#0f1830;--mut:#5a6a86;--bl:#1b3fd4;--ln:#e7ecf6;--wash:#f6f8fd;--grn:#0a7350;--rd:#dc2626}
@media(prefers-color-scheme:dark){:root{--pp:#0b111f;--ink:#eef2fb;--mut:#93a3c2;--bl:#7d97ff;--ln:#233150;--wash:#111a2e}}
body{margin:0;background:var(--wash);color:var(--ink);font-family:"Sarabun","Noto Sans Thai","Segoe UI",system-ui,sans-serif;line-height:1.6}
.wrap{max-width:860px;margin:0 auto;padding:28px 20px 70px}
.brand{display:flex;align-items:center;gap:9px;font-weight:800;margin-bottom:4px}
.brand .mk{width:26px;height:26px;border-radius:7px;background:var(--bl);color:#fff;display:grid;place-items:center;font-size:14px}
.brand span{color:var(--mut);font-weight:500;font-size:13px}
h1{font-size:clamp(24px,4vw,34px);margin:14px 0 2px;letter-spacing:-.02em}
.sub{color:var(--mut);font-size:14px;margin-bottom:22px}
.card{background:var(--pp,#fff);border:1px solid var(--ln);border-radius:16px;padding:20px 22px;margin:0 0 18px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:0}
.kpi{padding:8px 16px;border-left:1px solid var(--ln)}.kpi:first-child{border-left:0}
.kpi .kv{font-size:26px;font-weight:800;letter-spacing:-.02em;color:var(--bl)}
.kpi .kl{font-size:12.5px;color:var(--mut);margin-top:2px}
h2{font-size:17px;margin:26px 0 12px}
table{width:100%;border-collapse:collapse;font-size:14.5px}
th,td{text-align:left;padding:9px 8px;border-bottom:1px solid var(--ln)}
th{font-size:12px;color:var(--mut);font-weight:700}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.center{text-align:center}.muted{color:var(--mut)}.pending{color:var(--mut);font-size:13px}
.up{color:var(--grn);font-weight:700}.down{color:var(--rd);font-weight:700}
.pill{font-size:11px;padding:1px 8px;border-radius:999px;font-weight:700;white-space:nowrap}.pill.green{background:rgba(10,115,80,.12);color:var(--grn)}
.pill.blue{background:rgba(27,63,212,.12);color:var(--bl)}.pill.amber{background:rgba(180,83,9,.14);color:#b45309}.pill.slate{background:rgba(90,106,134,.14);color:var(--mut)}
.plsum{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 14px;font-size:13px;color:var(--mut)}
.engs{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.eng{text-align:center;border:1px solid var(--ln);border-radius:12px;padding:14px 8px}
.eng .en{font-weight:800}.eng .ev{font-size:22px;font-weight:800;margin:5px 0 2px}.eng .es{font-size:12.5px;color:var(--mut)}
.proof{border-left:3px solid #4ade80;padding:2px 0 2px 12px;margin:10px 0}
.proof .pe{font-weight:700;color:var(--grn);font-size:13px}.proof .pq{font-size:13.5px;margin:2px 0}.proof .pa{color:var(--mut);font-size:13.5px}
.arts{list-style:none;padding:0;margin:0}.arts li{padding:8px 0;border-bottom:1px solid var(--ln);display:flex;justify-content:space-between;gap:10px}
.arts a{color:var(--bl);text-decoration:none}.arts a:hover{text-decoration:underline}
.foot{color:var(--mut);font-size:12.5px;text-align:center;margin-top:30px;line-height:1.7}
.note{background:var(--wash);border-radius:10px;padding:10px 14px;font-size:12.5px;color:var(--mut);margin-top:10px}
.qwant{display:flex;flex-direction:column;gap:2px}
.qrow{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid var(--ln)}
.qrow:last-child{border-bottom:0}.qq{font-size:14.5px;font-weight:600;line-height:1.4}
.aeo-spot{border:1.5px solid var(--bl);background:rgba(27,63,212,.05)}
.aeo-spot .asl{font-weight:800;font-size:15px;color:var(--bl);margin-bottom:6px}
.aeo-spot p{margin:0;font-size:14.5px;line-height:1.62}.aeo-spot b{font-weight:800}
/* exec summary */
.exec{background:linear-gradient(135deg,var(--bl),#5b4ff0);color:#fff;border:0}
.exec .el{font-size:11px;letter-spacing:.16em;text-transform:uppercase;font-weight:800;opacity:.85}
.exec p{margin:8px 0 0;font-size:15.5px;line-height:1.62}.exec b{font-weight:800}
.exec .arrow-up{color:#8affc4;font-weight:800}.exec .arrow-dn{color:#ffc4c4;font-weight:800}
/* KPI delta */
.kpi .kd{font-size:12px;font-weight:800;margin-top:3px}
.kd.up{color:var(--grn)}.kd.dn{color:var(--rd)}.kd.flat{color:var(--mut)}
/* AEO success stage stepper */
.stage-head{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:4px}
.stage-head .now{font-size:18px;font-weight:800}
.stage-head .badge{font-size:11px;font-weight:800;padding:2px 10px;border-radius:999px;background:rgba(27,63,212,.12);color:var(--bl)}
.stage-desc{color:var(--mut);font-size:13.5px;margin:2px 0 16px}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.step{border:1px solid var(--ln);border-radius:12px;padding:12px 12px 13px;position:relative;opacity:.55}
.step.on{opacity:1;border-color:var(--bl);background:rgba(27,63,212,.05)}
.step.on.cur{box-shadow:0 0 0 2px var(--bl) inset}
.step .sn{width:22px;height:22px;border-radius:50%;background:var(--ln);color:var(--mut);display:grid;place-items:center;font-size:12px;font-weight:800}
.step.on .sn{background:var(--bl);color:#fff}
.step .st{font-weight:800;font-size:13.5px;margin:7px 0 2px}.step .ss{font-size:12px;color:var(--mut);line-height:1.45}
@media(max-width:560px){.steps{grid-template-columns:1fr}}
/* trend sparklines */
.trends{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:560px){.trends{grid-template-columns:1fr}}
.trend{border:1px solid var(--ln);border-radius:12px;padding:13px 15px}
.trend .tl{font-size:12.5px;color:var(--mut);font-weight:700}
.trend .tv{font-size:22px;font-weight:800;letter-spacing:-.02em;margin:2px 0 8px;font-variant-numeric:tabular-nums}
.trend .tv small{font-size:12px;font-weight:800}.trend .th{font-size:11.5px;color:var(--mut);margin-top:5px}
/* competitors */
.comps{display:flex;flex-wrap:wrap;gap:8px;margin:2px 0 0}
.comp{font-size:13px;font-weight:700;padding:6px 13px;border-radius:999px;background:var(--wash);border:1px solid var(--ln)}
.comp::before{content:"🥊 ";}
"""


def _sparkline(vals, up_is_good=True, w=132, h=34):
    """SVG sparkline เล็ก — เขียวถ้าดีขึ้น แดงถ้าแย่ลง (อันดับใช้ up_is_good=False เพราะยิ่งต่ำยิ่งดี)"""
    vals = [v for v in (vals or []) if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    npts = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = round(i / (npts - 1) * (w - 6) + 3, 1)
        norm = (v - lo) / rng
        y = round(((1 - norm) if up_is_good else norm) * (h - 8) + 4, 1)
        pts.append("%s,%s" % (x, y))
    improved = (vals[-1] > vals[0]) if up_is_good else (vals[-1] < vals[0])
    col = "#0a7350" if improved else ("#dc2626" if vals[-1] != vals[0] else "#5a6a86")
    lx, ly = pts[-1].split(",")
    return ('<svg viewBox="0 0 %d %d" width="100%%" height="%d" preserveAspectRatio="none" style="display:block;overflow:visible">'
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
            '<circle cx="%s" cy="%s" r="2.8" fill="%s"/></svg>'
            % (w, h, h, " ".join(pts), col, lx, ly, col))


def render_report_page(data: dict, period_label: str, generated: str) -> str:
    proj = data["proj"]
    en = str(getattr(proj, "language", "") or "").lower().startswith("en")   # โปรเจ็คภาษาอังกฤษ → รายงาน EN อัตโนมัติ

    def t(th, en_):
        return en_ if en else th

    name = _esc(proj.name or proj.domain)

    def n(v):
        return "—" if v is None else str(v)

    def d_rank(cur, prev):                     # อันดับ: ต่ำลง=ดีขึ้น
        if cur is None or prev is None or cur == prev:
            return ""
        d = round(prev - cur, 1)
        return '<div class="kd up">▲ %s</div>' % d if d > 0 else '<div class="kd dn">▼ %s</div>' % (-d)

    def d_pct(cur, prev):                      # SoV: มากขึ้น=ดี
        if cur is None or prev is None or cur == prev:
            return ""
        d = round(cur - prev, 1)
        return '<div class="kd up">▲ %s pt</div>' % d if d > 0 else '<div class="kd dn">▼ %s pt</div>' % (-d)

    kpis = [(t("ติดหน้า 1", "On page 1"), n(data["page1"]), ""), ("Top 3", n(data["top3"]), ""),
            (t("อันดับเฉลี่ย", "Avg. rank"), n(data["avg"]), d_rank(data.get("avg"), data.get("avg_prev"))),
            (t("บทความเผยแพร่", "Articles published"), n(data["published"]), ""),
            ("AI Citation", ("%s%%" % data["sov"]) if data["sov"] is not None else "—", d_pct(data.get("sov"), data.get("sov_prev")))]
    kpi_html = "".join('<div class="kpi"><div class="kv">%s</div><div class="kl">%s</div>%s</div>' % (v, _esc(l), dl) for l, v, dl in kpis)

    def mv(k):
        cur, prev = k["rank"], k["prev"]
        if cur is None:
            return '<span class="pending">%s</span>' % t("รอวัด", "Pending")
        if prev is None:
            return '<span class="muted">%s</span>' % t("ใหม่", "New")
        d = prev - cur
        return ('<span class="up">▲ %d</span>' % d) if d > 0 else (('<span class="down">▼ %d</span>' % (-d)) if d < 0 else '<span class="muted">—</span>')

    _stage_tone = {"published": "green", "scheduled": "blue", "drafting": "amber", "queued": "slate"}

    def stage_pill(k):
        return '<span class="pill %s">%s</span>' % (_stage_tone.get(k.get("stage"), "slate"), _esc(k.get("stage_label") or ""))

    def _pg(k):   # หน้าผลค้นหา Google = ceil(อันดับ/10)
        return (t("หน้า %d", "Page %d") % ((k["rank"] - 1) // 10 + 1)) if k["rank"] is not None else "—"
    rank_rows = "".join(
        '<tr><td>%s%s</td><td>%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td><td class="n">%s</td></tr>'
        % (_esc(k["keyword"]), (' <span class="pill green">%s</span>' % t("หน้า 1", "Page 1")) if k["on_page1"] else '',
           stage_pill(k),
           ('#%d' % k["rank"]) if k["rank"] is not None else ('<span class="pending">%s</span>' % t("รอวัด", "Pending")),
           _pg(k),
           ('#%d' % k["best"]) if k["best"] is not None else '—', mv(k))
        for k in data["kws"]) or ('<tr><td colspan="6" class="center muted">%s</td></tr>' % t("ยังไม่มีข้อมูลอันดับ", "No ranking data yet"))

    _pl = data.get("pipeline", {}) or {}
    _writing = _pl.get("drafting", 0) + _pl.get("scheduled", 0)
    pl_html = ('<div class="plsum">🚀 %s '
               '<span class="pill green">✍️ %s %d</span>'
               '<span class="pill amber">📝 %s %d</span>'
               '<span class="pill slate">🕒 %s %d</span></div>'
               % (t("ระบบกำลังไล่ทำครบทุกคีย์:", "Working through every keyword:"),
                  t("เผยแพร่แล้ว", "Published"), _pl.get("published", 0),
                  t("กำลังเขียน", "Writing"), _writing,
                  t("รอคิว", "Queued"), _pl.get("queued", 0)))

    engs = "".join(
        '<div class="eng"><div class="en">%s</div><div class="ev">%s</div><div class="es">%s</div></div>'
        % (_esc(_REPORT_ENGINES.get(e, e)),
           ('%s%%' % data["per_engine"].get(e)) if data["per_engine"].get(e) is not None else '—',
           t("✓ อ้างอิงแล้ว", "✓ Cited") if (data["per_engine"].get(e) or 0) > 0 else t("○ ยังไม่หยิบ", "○ Not yet"))
        for e in ("openai", "gemini", "perplexity"))

    proof = ""
    if data["examples"]:
        proof = ('<h2>%s</h2><div class="card">' % t("🎯 หลักฐาน — AI พูดถึงคุณจริง", "🎯 Proof — AI actually mentions you")
                 + "".join('<div class="proof"><div class="pe">%s ✓</div><div class="pq">%s: "%s"</div><div class="pa">"%s…"</div></div>'
                           % (_esc(_REPORT_ENGINES.get(e.engine, e.engine)), t("ถาม", "Q"), _esc(e.question), _esc(e.snippet or "")[:220])
                           for e in data["examples"][:4]) + '</div>')

    recent = ""
    if data["recent"]:
        recent = ('<h2>%s</h2><div class="card"><ul class="arts">' % t("บทความล่าสุด", "Recent articles")
                  + "".join('<li>%s<span class="muted">AEO %s</span></li>'
                            % (('<a href="%s" target="_blank" rel="noopener">%s</a>' % (_esc(a.url), _esc(a.title))) if getattr(a, "url", "") else _esc(a.title),
                               getattr(a, "aeo_score", "") or "—")
                            for a in data["recent"]) + '</ul></div>')

    # ---------- ครบวงจร: exec summary + AEO success stage + trends + competitors ----------
    parts = []
    if data.get("avg") is not None:
        seg = t("อันดับเฉลี่ย <b>#%s</b>", "avg rank <b>#%s</b>") % data["avg"]
        ap = data.get("avg_prev")
        if ap is not None and ap != data["avg"]:
            up = data["avg"] < ap
            seg += ' <span class="%s">%s</span>' % ("arrow-up" if up else "arrow-dn", "▲" if up else "▼")
        parts.append(seg)
    parts.append(t("ติดหน้าแรก <b>%s</b> คีย์", "<b>%s</b> on page 1") % data["page1"])
    if data.get("sov") is not None:
        seg = t("AI แนะนำคุณ <b>%s%%</b>", "AI cites you <b>%s%%</b>") % data["sov"]
        sp = data.get("sov_prev")
        if sp is not None and sp != data["sov"]:
            up = data["sov"] > sp
            seg += ' <span class="%s">%s</span>' % ("arrow-up" if up else "arrow-dn", "▲" if up else "▼")
        parts.append(seg)
    parts.append(t("เผยแพร่ <b>%s</b> บทความช่วงนี้", "<b>%s</b> new articles this period") % data["new_count"])
    exec_html = ('<div class="card exec"><div class="el">%s</div><p>%s</p></div>'
                 % (t("สรุปผลงานช่วงนี้", "This period at a glance"), " · ".join(parts)))

    stage_ix = data.get("stage", 0)
    stage_defs = [
        (t("เริ่มติด", "Getting cited"), t("AI เริ่มพูดถึงคุณบนคำถามบางข้อ", "AI starts mentioning you on some questions")),
        (t("มีส่วนแบ่งเสียง", "Share of voice"), t("แข่งในสนามแล้ว — ถูก AI แนะนำสม่ำเสมอขึ้น", "In the mix — cited regularly")),
        (t("นำในหมวด", "Category leader"), t("AI แนะนำคุณเป็นตัวเลือกต้น ๆ", "AI recommends you as a top pick")),
    ]
    now_label = t("ยังไม่เริ่มติด", "Not cited yet") if stage_ix == 0 else stage_defs[stage_ix - 1][0]
    steps_html = "".join(
        '<div class="%s"><div class="sn">%s</div><div class="st">%s</div><div class="ss">%s</div></div>'
        % ("step" + (" on" if i <= stage_ix else "") + (" cur" if i == stage_ix else ""),
           "✓" if i < stage_ix else str(i), _esc(st), _esc(ss))
        for i, (st, ss) in enumerate(stage_defs, start=1))
    stage_html = ('<h2>%s</h2><div class="card"><div class="stage-head"><span class="now">%s</span>'
                  '<span class="badge">%s %d/3</span></div><div class="stage-desc">%s</div>'
                  '<div class="steps">%s</div></div>'
                  % (t("🏁 เส้นทางสู่ความสำเร็จ AEO", "🏁 Your AEO success path"), _esc(now_label),
                     t("ระดับ", "Stage"), stage_ix,
                     t("AEO ไม่มีเส้นชัยจุดเดียว — วัดจาก Share of Voice ที่ไต่ขึ้นต่อเนื่อง · ตอนนี้คุณอยู่ตรงนี้:",
                       "AEO isn't one finish line — it's a rising Share of Voice. Here's where you stand:"),
                     steps_html))

    tr = []
    rt = data.get("rank_trend") or []
    if len(rt) >= 2:
        tr.append('<div class="trend"><div class="tl">%s</div><div class="tv">#%s</div>%s<div class="th">%s</div></div>'
                  % (t("อันดับเฉลี่ยตามเวลา", "Avg rank over time"), rt[-1], _sparkline(rt, up_is_good=False),
                     t("ยิ่งต่ำยิ่งดี · เขียว = ดีขึ้น", "lower is better · green = improving")))
    stv = data.get("sov_trend") or []
    if len(stv) >= 2:
        tr.append('<div class="trend"><div class="tl">%s</div><div class="tv">%s<small>%%</small></div>%s<div class="th">%s</div></div>'
                  % (t("AI Citation (SoV) ตามเวลา", "AI Citation (SoV) over time"), stv[-1], _sparkline(stv, up_is_good=True),
                     t("ยิ่งสูงยิ่งดี · เขียว = ไต่ขึ้น", "higher is better · green = climbing")))
    trends_html = ('<h2>%s</h2><div class="card"><div class="trends">%s</div></div>'
                   % (t("📈 แนวโน้ม (เทียบตามเวลา)", "📈 Trends over time"), "".join(tr))) if tr else ""

    comp_html = ""
    comps = data.get("competitors") or []
    if comps:
        comp_html = ('<h2>%s</h2><div class="card"><div class="comps">%s</div><div class="note">%s</div></div>'
                     % (t("🥊 คู่แข่งที่ AI แนะนำในหมวดคุณ", "🥊 Competitors AI recommends in your space"),
                        "".join('<span class="comp">%s</span>' % _esc(c) for c in comps[:8]),
                        t("เป้าหมาย AEO = ทำให้ AI แนะนำ 'คุณ' ควบคู่/แทนแบรนด์เหล่านี้ (ระบบกำลังไล่แซง)",
                          "AEO goal = get AI to recommend YOU alongside/instead of these — the system is closing the gap")))

    # 🎯 คำถามที่ 'ดันให้ AI แนะนำคุณ' — ตอบโจทย์ลูกค้าที่อยากรู้ว่า 'AI แนะนำเราเมื่อถามอะไร'
    qwant_html = ""
    aeo_qs = data.get("aeo_questions") or []
    citedq = data.get("cited_questions") or set()
    if aeo_qs:
        qrows = "".join(
            '<div class="qrow"><span class="qq">%s</span>%s</div>'
            % (_esc(q),
               ('<span class="pill green">%s</span>' % t("✓ AI แนะนำแล้ว", "✓ AI cites you"))
               if q.strip().lower() in citedq else
               ('<span class="pill amber">%s</span>' % t("🎯 กำลังดัน", "🎯 In progress")))
            for q in aeo_qs)
        qwant_html = ('<h2>%s</h2><div class="card"><div class="qwant">%s</div><div class="note">%s</div></div>'
                      % (t("🎯 คำถามที่เราทำให้ AI แนะนำคุณ (AEO)", "🎯 Questions we're getting AI to recommend you on (AEO)"),
                         qrows,
                         t("เมื่อมีคนถาม ChatGPT / Gemini / Perplexity ด้วยคำถามเหล่านี้ เป้าหมายคือให้คำตอบของ AI แนะนำแบรนด์คุณ — ระบบกำลังผลิตคอนเทนต์ให้ AI หยิบไปตอบ",
                           "When people ask ChatGPT / Gemini / Perplexity these questions, the goal is for the answer to recommend your brand — the system keeps producing the content AI pulls from")))

    # 🤖 AEO spotlight — ชูว่า AEO คือสนามที่คู่แข่งยังไม่ทำ (blue-ocean) + สถานะจริง
    _sov = data.get("sov")
    _sov_txt = ("%s%%" % _sov) if _sov is not None else "0%"
    aeo_spotlight_html = (
        '<div class="card aeo-spot"><div class="asl">🤖 %s</div><p>%s</p></div>'
        % (t("จุดที่คุณชนะก่อนใคร: AEO", "Where you win first: AEO"),
           (t("SEO ทุกคนแย่งกัน แต่ <b>AEO — การให้ AI อย่าง ChatGPT / Gemini แนะนำคุณ</b> ยังเป็นสนามที่คู่แข่งเกือบทั้งหมดไม่ทำ · "
              "ตอนนี้ AI แนะนำคุณ <b>%s</b> ของหมวด และระบบกำลังผลิตคอนเทนต์ให้ AI หยิบไปตอบเพื่อดันส่วนนี้ขึ้นต่อเนื่อง",
              "Everyone fights over SEO, but <b>AEO — getting AI like ChatGPT / Gemini to recommend you</b> is still wide open · "
              "AI currently cites you <b>%s</b> of the category, and the system keeps producing the content AI pulls from to grow it")
            % _sov_txt)))

    link = '<a href="https://imvisible.tech" style="color:var(--bl)">ImVisible</a>'
    sub = (t("%s · %s · ผลิตในช่วงนี้ %d บทความ · คะแนน AEO เฉลี่ย %s",
             "%s · %s · %d articles this period · avg AEO %s")
           % (_esc(period_label), _esc(proj.domain or ""), data["new_count"],
              (data["aeo_avg"] if data["aeo_avg"] is not None else "—")))
    foot = (t("รายงานสร้างเมื่อ %s · ทุกตัวเลขวัดจริง ตรวจสอบย้อนได้ · จัดทำโดยระบบ AEO+SEO ของ %s",
              "Generated %s · every figure measured &amp; verifiable · powered by %s AEO+SEO")
            % (_esc(generated), link))
    return (
        '<!doctype html><html lang="%s"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow"><title>%s · %s</title>'
        '<link rel="icon" href="/favicon.svg"><style>%s</style></head><body><div class="wrap">'
        '<div class="brand"><span class="mk">i</span>ImVisible<span>%s</span></div>'
        '<h1>%s</h1><div class="sub">%s</div>'
        '%s'
        '<div class="card"><div class="kpis">%s</div></div>'
        '%s%s%s'
        '<h2>%s</h2><div class="card" style="overflow-x:auto">%s'
        '<table><thead><tr><th>%s</th><th>%s</th><th class="n">%s</th><th class="n">%s</th><th class="n">%s</th><th class="n">%s</th></tr></thead>'
        '<tbody>%s</tbody></table></div>'
        '<h2>%s</h2><div class="card"><div class="engs">%s</div><div class="note">%s</div></div>'
        '%s%s%s%s<div class="foot">%s</div>'
        '</div></body></html>'
        % ("en" if en else "th", t("รายงานผลงาน", "Performance Report"), name, _REPORT_CSS,
           t(" · รายงานผลงาน", " · Performance Report"), name, sub, exec_html, kpi_html,
           aeo_spotlight_html, stage_html, trends_html,
           t("อันดับ Google (ต่อคีย์เวิร์ด)", "Google Rankings (by keyword)"), pl_html,
           t("คีย์เวิร์ด", "Keyword"), t("สถานะ", "Stage"), t("อันดับ", "Rank"), t("หน้า", "Page"), t("ดีสุด", "Best"), t("เปลี่ยนแปลง", "Change"),
           rank_rows, t("🤖 AI แนะนำเราหรือยัง", "🤖 Is AI recommending you?"), engs,
           t("วัดจริงโดยถาม ChatGPT / Gemini / Perplexity แล้วเช็คว่าคำตอบอ้างอิงแบรนด์/เว็บของคุณ (Share of Voice)",
             "Measured by actually querying ChatGPT / Gemini / Perplexity and checking whether the answer cites your brand/site (Share of Voice)"),
           qwant_html, comp_html, proof, recent, foot)
    )


_LM_CSS = """
*{box-sizing:border-box}:root{--pp:#fff;--ink:#0f1830;--mut:#5a6a86;--bl:#1b3fd4;--ln:#e7ecf6;--wash:#f6f8fd}
@media(prefers-color-scheme:dark){:root{--pp:#0b111f;--ink:#eef2fb;--mut:#93a3c2;--bl:#7d97ff;--ln:#233150;--wash:#111a2e}}
body{margin:0;background:var(--wash);color:var(--ink);font-family:"Sarabun","Noto Sans Thai","Segoe UI",system-ui,sans-serif;line-height:1.72}
.wrap{max-width:760px;margin:0 auto;padding:26px 20px 70px}
.brand{font-weight:800;display:flex;align-items:center;gap:9px}
.brand .mk{width:26px;height:26px;border-radius:7px;background:var(--bl);color:#fff;display:grid;place-items:center;font-size:14px}
.kb{display:inline-block;background:var(--bl);color:#fff;font-size:12.5px;font-weight:800;padding:4px 13px;border-radius:999px;margin:16px 0 0}
h1{font-size:clamp(25px,4.5vw,37px);line-height:1.16;letter-spacing:-.02em;margin:10px 0 6px;text-wrap:balance}
.desc{color:var(--mut);font-size:16px;margin-bottom:20px}
.cover{width:100%;border-radius:16px;aspect-ratio:16/9;object-fit:cover;margin-bottom:20px;display:block;box-shadow:0 26px 56px -24px rgba(20,40,120,.34)}
h1{text-wrap:balance}.kb{box-shadow:0 8px 20px -8px rgba(26,86,255,.6)}
.card{background:var(--pp,#fff);border:1px solid var(--ln);border-radius:18px;padding:22px 24px}
.teaser h2{font-size:19px;margin:20px 0 8px}.teaser h3{font-size:16px;margin:14px 0 6px}.teaser p,.teaser li{font-size:15.5px}.teaser ul,.teaser ol{padding-left:1.35em}
.gate{background:linear-gradient(135deg,#3d6bff,#5b4ff0);color:#fff;border-radius:18px;padding:26px 22px;margin:24px 0;text-align:center}
.gate h3{font-size:21px;margin:0 0 4px}.gate p{opacity:.92;font-size:14.5px;margin:0 0 16px}
.gate input{width:100%;max-width:380px;padding:13px 15px;border:0;border-radius:10px;font-size:15px;margin:6px auto;display:block;color:#0f1830}
.gate .btn{background:#fff;color:#3d6bff;font-weight:800;border:0;padding:13px 32px;border-radius:999px;font-size:15px;cursor:pointer;margin-top:10px}
.gate .btn:disabled{opacity:.7}
.gate .share{background:transparent;border:1.5px solid rgba(255,255,255,.65);color:#fff;font-weight:700;padding:9px 22px;border-radius:999px;cursor:pointer;font-size:13px;margin-bottom:12px}
/* เนื้อหาเต็ม (หลังปลดล็อก) — จัดเป็น 'โมดูลบทเรียน' ให้ดูเป็นคอร์สจริง */
.content{display:none;counter-reset:les;background:var(--pp);border:1px solid var(--ln);border-radius:18px;padding:6px 26px 26px;margin-top:10px;box-shadow:0 26px 56px -30px rgba(20,40,120,.3)}
.content h2{counter-increment:les;font-size:21px;font-weight:800;line-height:1.32;margin:30px 0 12px;padding-top:26px;border-top:1px solid var(--ln);display:flex;align-items:flex-start;gap:12px}
.content h2::before{content:counter(les,decimal-leading-zero);flex:none;background:var(--bl);color:#fff;font-size:13.5px;font-weight:800;min-width:30px;height:30px;border-radius:9px;display:grid;place-items:center;margin-top:2px;font-variant-numeric:tabular-nums}
.content > h2:first-child{border-top:0;padding-top:14px;margin-top:4px}
.content h3{font-size:17.5px;font-weight:700;margin:20px 0 8px}
.content p,.content li{font-size:16.5px}.content p{margin:0 0 14px}.content ul,.content ol{padding-left:1.4em}.content li{margin-bottom:8px}.content strong{font-weight:700}
.content figure{margin:20px 0}
.content img{width:100%;border-radius:14px;display:block;box-shadow:0 20px 44px -22px rgba(20,40,120,.4)}
.content figcaption{color:var(--mut);font-size:13px;text-align:center;margin-top:8px}
.content .hero-video{margin:2px 0 22px}.content video{width:100%;border-radius:16px;display:block;box-shadow:0 24px 54px -24px rgba(20,40,120,.42)}
.foot{color:var(--mut);font-size:12.5px;text-align:center;margin-top:34px;line-height:1.7}.foot a{color:var(--bl)}
"""


_SITE_REPORT_CSS = """
*{box-sizing:border-box}
:root{--pp:#fff;--ink:#0e1526;--mut:#5c6b86;--faint:#93a0b8;--bl:#1a56ff;--bl2:#6b4ffb;--ln:#e8ecf5;--wash:#f4f6fb;--ok:#0ca678;--warn:#e8850c;--bad:#e23d3d;--card:0 24px 50px -34px rgba(20,40,120,.26)}
@media(prefers-color-scheme:dark){:root{--pp:#131a2b;--ink:#eef2fb;--mut:#9aa8c4;--faint:#66748f;--bl:#5b82ff;--bl2:#9a86ff;--ln:#26314a;--wash:#0a0f1c;--ok:#34d399;--warn:#fbbf24;--bad:#f87171;--card:0 24px 50px -30px rgba(0,0,0,.6)}}
body{margin:0;background:var(--wash);color:var(--ink);font-family:"Sarabun","Noto Sans Thai","Segoe UI",system-ui,sans-serif;line-height:1.65}
.top{background:var(--pp);border-bottom:1px solid var(--ln);position:sticky;top:0;z-index:5}
.top .in{max-width:820px;margin:0 auto;padding:14px 20px;display:flex;align-items:center;gap:10px;font-weight:800;font-size:15px}
.top .mk{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--bl),var(--bl2));color:#fff;display:grid;place-items:center}
.top .sub{color:var(--mut);font-weight:600;font-size:12px;margin-left:auto}
.wrap{max-width:820px;margin:0 auto;padding:0 20px 76px}
.hero{background:linear-gradient(135deg,#eaf1ff,#f1ecff);border:1px solid var(--ln);border-radius:24px;padding:clamp(22px,4vw,32px);margin:24px 0 16px;box-shadow:var(--card)}
@media(prefers-color-scheme:dark){.hero{background:linear-gradient(135deg,#141d38,#1a1533)}}
.hero .eyebrow{font-size:11.5px;letter-spacing:.16em;text-transform:uppercase;font-weight:800;color:var(--bl)}
.hero h1{font-size:clamp(24px,4.6vw,38px);line-height:1.12;letter-spacing:-.03em;margin:9px 0 4px;word-break:break-word}
.hero .url{color:var(--mut);font-size:13px;word-break:break-all}
.gauges{display:flex;gap:14px;flex-wrap:wrap;margin-top:22px}
.gcard{flex:1;min-width:186px;background:var(--pp);border:1px solid var(--ln);border-radius:18px;padding:16px 14px 18px;text-align:center}
.gcard .cap{font-weight:800;font-size:14px}
.gcard .cap2{color:var(--mut);font-size:11.5px}
.gg{width:150px;height:150px;margin:4px auto 0;display:block}
.gg circle{fill:none}
.gg .bg{stroke:var(--ln);stroke-width:12}
.gg .fg{stroke-width:12;stroke-linecap:round;transform:rotate(-90deg);transform-origin:75px 75px;stroke-dasharray:389.56;stroke-dashoffset:389.56;animation:draw 1.3s cubic-bezier(.32,.72,.3,1) .15s forwards}
@keyframes draw{to{stroke-dashoffset:var(--off)}}
@media(prefers-reduced-motion:reduce){.gg .fg{animation:none;stroke-dashoffset:var(--off)}}
.gg .num{font:800 34px "Sarabun",system-ui;text-anchor:middle}
.gg .den{font:600 12px "Sarabun",system-ui;fill:var(--mut);text-anchor:middle}
.badge{display:inline-block;font-weight:800;font-size:12.5px;padding:3px 13px;border-radius:100px;margin-top:8px}
.verdict{margin-top:20px;font-size:clamp(15px,1.9vw,17px);font-weight:600;line-height:1.5}
.sec{background:var(--pp);border:1px solid var(--ln);border-radius:20px;padding:18px 22px;margin-bottom:14px;box-shadow:var(--card)}
.sec h2{font-size:16.5px;margin:0 0 2px;letter-spacing:-.01em}
.sec .h2sub{color:var(--mut);font-size:11.5px;margin-bottom:8px}
.frow{display:grid;grid-template-columns:24px 1fr;gap:11px;padding:12px 0;border-top:1px solid var(--ln)}
.frow:first-of-type{border-top:0}
.frow .ic{width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:12px;font-weight:900;color:#fff;margin-top:1px}
.tone-ok .ic{background:var(--ok)}.tone-warn .ic{background:var(--warn)}.tone-bad .ic{background:var(--bad)}
.frow .lbl{font-weight:700;font-size:14.5px}
.frow .det{color:var(--mut);font-size:12.5px;font-weight:400;margin-left:5px}
.frow .fix{margin-top:7px;font-size:13px;color:var(--warn);background:color-mix(in srgb,var(--warn) 10%,transparent);border-radius:10px;padding:8px 12px;line-height:1.5}
.kw{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-top:1px solid var(--ln);font-size:14px;align-items:center}
.kw:first-of-type{border-top:0}
.kw .tag{font-weight:800;font-size:11.5px;padding:3px 11px;border-radius:100px;white-space:nowrap}
.gate{background:linear-gradient(135deg,var(--bl),var(--bl2));color:#fff;border-radius:24px;padding:clamp(24px,4vw,34px);margin:22px 0;text-align:center;box-shadow:0 34px 66px -30px rgba(40,60,220,.6)}
.gate h3{font-size:clamp(19px,2.6vw,24px);margin:0 0 6px;line-height:1.25}
.gate p{opacity:.93;font-size:14.5px;margin:0 auto 16px;max-width:420px}
.gate .teaser{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.16);border-radius:14px;padding:14px 18px;text-align:left;font-size:14px;margin:0 auto 18px;max-width:440px;line-height:1.95}
.gate .teaser .blur{filter:blur(5.5px);opacity:.6;user-select:none}
.gate form{max-width:420px;margin:0 auto}
.gate input,.gate textarea{width:100%;padding:14px 16px;border:0;border-radius:12px;font-size:15px;margin:7px 0;color:#0e1526;font-family:inherit;background:#fff}
.gate textarea{min-height:62px;resize:vertical}
.gate .btn{width:100%;background:#0e1526;color:#fff;font-weight:800;border:0;padding:15px;border-radius:12px;font-size:16px;cursor:pointer;margin-top:8px;transition:transform .15s,opacity .15s}
.gate .btn:hover{transform:translateY(-2px)}
.gate .btn:disabled{opacity:.7;transform:none}
.gate .fine{opacity:.85;font-size:12px;margin-top:12px}
.plan{display:none;background:var(--pp);border:1px solid var(--ln);border-radius:20px;padding:16px 24px 24px;margin-top:14px;box-shadow:var(--card)}
.plan ol{padding-left:1.3em;margin:8px 0}.plan li{font-size:15px;margin-bottom:11px;line-height:1.55}
.plan .done{background:var(--ok);color:#fff;border-radius:14px;padding:15px 18px;margin-top:14px;font-weight:700;text-align:center;line-height:1.5}
.foot{color:var(--faint);font-size:12px;text-align:center;margin-top:30px;line-height:1.7}.foot a{color:var(--bl);font-weight:700}
"""


def _rep_gauge(score, cap, cap2) -> str:
    """เกจวงกลม SVG (สี = ระดับคะแนน) — คะแนนจริงจาก sitecheck (ไม่กุ)"""
    s = max(0, min(100, int(score or 0)))
    color = "var(--ok)" if s >= 85 else "var(--warn)" if s >= 55 else "var(--bad)"
    grade = "A" if s >= 85 else "B" if s >= 70 else "C" if s >= 55 else "D"
    circ = 389.56  # 2*pi*62
    off = round(circ * (1 - s / 100.0), 1)
    return (
        '<div class="gcard"><div class="cap">%s</div><div class="cap2">%s</div>'
        '<svg class="gg" viewBox="0 0 150 150" role="img" aria-label="%s %d/100">'
        '<circle class="bg" cx="75" cy="75" r="62"></circle>'
        '<circle class="fg" cx="75" cy="75" r="62" style="--off:%s;stroke:%s"></circle>'
        '<text class="num" x="75" y="75" dy=".05em" style="fill:%s">%d</text>'
        '<text class="den" x="75" y="98">/100</text></svg>'
        '<span class="badge" style="color:%s;background:color-mix(in srgb,%s 12%%,transparent)">เกรด %s</span></div>'
        % (_esc(cap), _esc(cap2), _esc(cap), s, off, color, color, s, color, color, grade)
    )


def _rep_factor_rows(factors) -> str:
    out = []
    for f in (factors or []):
        tone = f.get("tone") or "bad"
        ico = "✓" if tone == "ok" else ("!" if tone == "warn" else "✕")
        fix = f.get("fix") or ""
        det = f.get("detail") or ""
        out.append(
            '<div class="frow tone-%s"><span class="ic">%s</span>'
            '<div><div class="lbl">%s%s</div>%s</div></div>'
            % (tone, ico, _esc(f.get("label") or ""),
               ('<span class="det">%s</span>' % _esc(det)) if det else "",
               ('<div class="fix">→ %s</div>' % _esc(fix)) if (tone != "ok" and fix) else "")
        )
    return "".join(out) or '<div class="frow"><span class="det">—</span></div>'


def render_report_plan(data: dict) -> str:
    """แผนแก้จัดลำดับ (โชว์หลังกรอกลีด) — AEO/GEO ก่อน แล้ว SEO เรียงตาม gain · จบด้วย CTA ให้ทีมทำให้"""
    fixes = list(data.get("aeo_fixes") or []) + list(data.get("top_fixes") or [])
    if not fixes:
        body = ('<p>เว็บพื้นฐานแน่นแล้ว 🎉 — ก้าวต่อไปคือ <b>ดันให้ติดอันดับ Google</b> '
                'และ <b>ทำให้ AI แนะนำคุณ</b> ซึ่งเป็นงานที่ทีม ImVisible ทำต่อเนื่องให้ได้</p>')
    else:
        lis = []
        for x in fixes[:8]:
            gain = (' <span style="color:var(--mut);font-size:13px">(+%s แต้ม)</span>' % x["gain"]) if x.get("gain") else ""
            lis.append('<li><b>%s</b> — %s%s</li>' % (_esc(x.get("label") or ""), _esc(x.get("fix") or ""), gain))
        body = '<ol>%s</ol>' % "".join(lis)
    return (body +
            '<div class="done">✓ ทีม ImVisible จะติดต่อกลับเพื่อช่วยทำให้ครบ — '
            'ทั้ง SEO (ติดอันดับ Google) + AEO/GEO (ให้ AI แนะนำคุณ)</div>')


def render_site_report_page(rep, data: dict, generated: str) -> str:
    """หน้ารายงานสุขภาพเว็บสาธารณะ (แชร์ได้) — เกจคะแนน + ปัญหา + แผนแก้ที่ gate ด้วยฟอร์มลีด
    ตัวเลขทุกตัวมาจาก sitecheck.check_url จริง (no-faking) · noindex (กัน doorway) แต่ OG สวยตอนแชร์"""
    import json as _json
    business = _esc((getattr(rep, "business_name", "") or getattr(rep, "domain", "") or data.get("url") or "เว็บไซต์").strip())
    url = _esc(data.get("url") or getattr(rep, "url", "") or "")
    score = int(data.get("score") or 0)
    aeo = int(data.get("aeo_score") or 0)
    verdict = _esc(data.get("aeo_summary") or data.get("summary") or "")
    token = getattr(rep, "token", "") or ""

    fixes = list(data.get("aeo_fixes") or []) + list(data.get("top_fixes") or [])
    n_fix = len(fixes)
    teaser_items = []
    for i, x in enumerate(fixes[:5]):
        cls = "" if i < 2 else "blur"
        teaser_items.append('<div class="%s">• %s</div>' % (cls, _esc(x.get("label") or "")))
    teaser = "".join(teaser_items) or '<div>เว็บพื้นฐานแน่นแล้ว — ต่อยอดสู่การติดอันดับ + ให้ AI แนะนำ</div>'

    kw_rows = data.get("keywords") or []
    kw_html = ""
    if kw_rows:
        rows = []
        for r in kw_rows:
            tone = r.get("tone")
            color = "var(--ok)" if tone == "ok" else "var(--warn)" if tone == "warn" else "var(--bad)"
            rows.append('<div class="kw"><span>%s</span><span class="tag" style="color:%s;background:color-mix(in srgb,%s 13%%,transparent)">%s</span></div>'
                        % (_esc(r.get("keyword") or ""), color, color, _esc(r.get("label") or "")))
        kw_html = ('<div class="sec"><h2>🔑 คีย์เวิร์ดที่อยากติด (บนหน้าเพจ)</h2>'
                   '<div class="h2sub">วัดว่าหน้าแรกพูดถึงคำนั้นครบไหม — ไม่ใช่อันดับ Google จริง</div>%s</div>'
                   % "".join(rows))

    cfg = _json.dumps({
        "token": token,
        "loading": "กำลังส่ง…",
        "btn": "ดูแผนแก้ทั้งหมด + ให้ทีมช่วย",
        "noname": "กรุณากรอกชื่อของคุณ",
        "nocontact": "กรุณากรอกเบอร์โทรหรือ LINE/อีเมล เพื่อให้เราติดต่อกลับได้",
        "err": "เกิดข้อผิดพลาด ลองใหม่อีกครั้ง",
        "thanks": "✓ ส่งแล้ว! ทีมเราจะติดต่อกลับเร็ว ๆ นี้",
    }, ensure_ascii=False).replace("</", "<\\/")

    js = ('<script>window.RPT=%s;</script>'
          '<script>(function(){var C=window.RPT||{};var f=document.getElementById("rl-form"),'
          'g=document.getElementById("rl-gate"),p=document.getElementById("rl-plan");'
          'if(!f)return;f.onsubmit=function(e){e.preventDefault();'
          'var nm=(document.getElementById("rl-name").value||"").trim();'
          'var ph=(document.getElementById("rl-phone").value||"").trim();'
          'var ct=(document.getElementById("rl-contact").value||"").trim();'
          'var ms=(document.getElementById("rl-msg").value||"").trim();'
          'if(!nm){alert(C.noname);return;}if(!ph&&!ct){alert(C.nocontact);return;}'
          'var b=document.getElementById("rl-btn");b.disabled=true;b.textContent=C.loading;'
          'fetch("/api/site-report/"+C.token+"/lead",{method:"POST",headers:{"Content-Type":"application/json"},'
          'body:JSON.stringify({name:nm,phone:ph,contact:ct,message:ms})})'
          '.then(function(r){return r.json();}).then(function(d){if(d&&d.plan_html){'
          'p.innerHTML=d.plan_html;p.style.display="block";'
          'g.innerHTML="<h3>"+C.thanks+"</h3>";p.scrollIntoView({behavior:"smooth"});}'
          'else{b.disabled=false;b.textContent=C.btn;alert((d&&d.detail)||C.err);}})'
          '.catch(function(){b.disabled=false;b.textContent=C.btn;alert(C.err);});};})();</script>'
          % cfg)

    page_title = "รายงานสุขภาพเว็บ · %s — SEO %d · AEO/GEO %d" % (business, score, aeo)
    meta_desc = _esc((data.get("aeo_summary") or data.get("summary") or "")[:155])

    return (
        '<!doctype html><html lang="th"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,follow">'
        '<title>%s</title><meta name="description" content="%s">'
        '<meta property="og:title" content="%s"><meta property="og:description" content="%s">'
        '<meta property="og:type" content="website">'
        '<link rel="icon" href="/favicon.svg"><style>%s</style></head><body>'
        '<div class="top"><div class="in"><span class="mk">i</span>ImVisible'
        '<span class="sub">รายงานสุขภาพเว็บ</span></div></div>'
        '<div class="wrap">'
        '<div class="hero">'
        '<div class="eyebrow">รายงานสุขภาพเว็บ · SEO · AEO · GEO</div>'
        '<h1>%s</h1><div class="url">%s · ตรวจเมื่อ %s</div>'
        '<div class="gauges">%s%s</div>'
        '<div class="verdict">%s</div>'
        '</div>'
        '<div class="sec"><h2>🟪 ความพร้อม AEO / GEO (ให้ AI แนะนำ)</h2>'
        '<div class="h2sub">schema · ตัวตนแบรนด์ · Q&amp;A/FAQ · answer-first · โครงหัวข้อ · เนื้อหา · llms.txt</div>%s</div>'
        '<div class="sec"><h2>🟦 ความพร้อม SEO (ติดอันดับ Google)</h2>%s</div>'
        '%s'
        '<div class="gate" id="rl-gate">'
        '<h3>🔧 เจอ %d จุดที่ต้องแก้ — ดูแผนเต็ม + ให้ทีมเราทำให้</h3>'
        '<p>กรอกข้อมูลเพื่อดู <b>แผนแก้จัดลำดับทั้งหมด</b> และให้ทีม ImVisible ช่วยทำให้ครบ (SEO + AEO/GEO)</p>'
        '<div class="teaser">%s</div>'
        '<form id="rl-form">'
        '<input id="rl-name" type="text" placeholder="ชื่อของคุณ *" autocomplete="name">'
        '<input id="rl-phone" type="tel" placeholder="เบอร์โทร (แนะนำ)" autocomplete="tel">'
        '<input id="rl-contact" type="text" placeholder="LINE ID หรืออีเมล (ไม่บังคับ)">'
        '<textarea id="rl-msg" placeholder="อยากให้ช่วยเรื่องอะไรเป็นพิเศษ? (ไม่บังคับ)"></textarea>'
        '<button class="btn" id="rl-btn" type="submit">ดูแผนแก้ทั้งหมด + ให้ทีมช่วย</button>'
        '<div class="fine">ฟรี · ไม่มีข้อผูกมัด · ทีมเราติดต่อกลับเพื่อประเมินให้</div>'
        '</form></div>'
        '<div class="plan" id="rl-plan"></div>'
        '<div class="foot">ตรวจจากหน้าเว็บจริง · ตัวเลขจริง ไม่กุ (no-faking) · โดย '
        '<a href="https://imvisible.tech" rel="noopener">ImVisible</a> — SEO · AEO · GEO อัตโนมัติ</div>'
        '%s</div></body></html>'
        % (page_title, meta_desc, page_title, meta_desc, _SITE_REPORT_CSS,
           business, url, _esc(generated),
           _rep_gauge(score, "🟦 SEO", "ติดอันดับ Google"),
           _rep_gauge(aeo, "🟪 AEO / GEO", "ให้ AI แนะนำ"),
           verdict,
           _rep_factor_rows(data.get("aeo_factors")),
           _rep_factor_rows(data.get("factors")),
           kw_html,
           n_fix, teaser, js)
    )


def render_lead_magnet_gate(magnet, proj) -> str:
    """หน้า gate สื่อแจกฟรี — teaser สาธารณะ (ให้ติดอันดับ) + ฟอร์มกรอกอีเมลปลดล็อกเนื้อหาเต็ม · สองภาษาตามโปรเจ็ค"""
    import json as _json
    en = str(getattr(magnet, "language", "") or getattr(proj, "language", "") or "").lower().startswith("en")

    def t(th, e):
        return e if en else th

    title = _esc(magnet.title or "")
    desc = _esc(magnet.description or "")
    teaser = magnet.teaser_html or ""
    brand = _esc(proj.name or proj.domain)
    cover = _esc(getattr(magnet, "cover_url", "") or "")
    req_share = bool(getattr(magnet, "require_share", False))
    _no_content = not str(getattr(magnet, "content_html", "") or "").strip()
    _failed = _no_content and bool(str(getattr(magnet, "error", "") or "").strip())
    if _failed:                                                      # สร้างล้ม → หน้าขอโทษ (ไม่ auto-refresh · ไม่ค้าง)
        return (
            '<!doctype html><html lang="%s"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>%s</title><link rel="icon" href="/favicon.svg"><style>%s</style></head>'
            '<body><div class="wrap" style="text-align:center;padding-top:72px">'
            '<div class="brand" style="justify-content:center"><span class="mk">i</span>%s</div>'
            '<div style="font-size:52px;margin:26px 0 6px">🛠️</div>'
            '<h1>%s</h1>'
            '<div class="card" style="max-width:440px;margin:18px auto 0"><p style="margin:0">%s</p></div>'
            '</div></body></html>'
            % ("en" if en else "th", (title or brand), _LM_CSS, brand,
               t("สื่อนี้ยังไม่พร้อม", "This resource isn't ready yet"),
               t("ขออภัย เรากำลังจัดเตรียมใหม่ — ลองกลับมาดูใหม่อีกครั้งภายหลัง",
                 "Sorry — we're preparing it again. Please check back a little later.")))
    if _no_content:                                                  # กำลังสร้างเบื้องหลัง → หน้ารอ (auto-refresh)
        return (
            '<!doctype html><html lang="%s"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="refresh" content="20"><title>%s</title>'
            '<link rel="icon" href="/favicon.svg"><style>%s</style></head><body><div class="wrap" style="text-align:center;padding-top:72px">'
            '<div class="brand" style="justify-content:center"><span class="mk">i</span>%s</div>'
            '<div style="font-size:52px;margin:26px 0 6px">🎁</div>'
            '<h1>%s</h1>'
            '<div class="card" style="max-width:440px;margin:18px auto 0"><p style="margin:0">%s</p>'
            '<p class="desc" style="margin:10px 0 0">%s</p></div>'
            '</div></body></html>'
            % ("en" if en else "th", (title or brand), _LM_CSS, brand,
               t("กำลังเตรียมสื่อให้คุณ…", "Preparing your resource…"),
               t("AI กำลังเขียนเนื้อหา + สร้างรูปประกอบตามหัวข้อ (~2-4 นาที)",
                 "AI is writing the content + generating images (~2-4 min)"),
               t("หน้านี้รีเฟรชอัตโนมัติทุก 20 วินาที — เปิดค้างไว้ได้เลย", "This page auto-refreshes every 20s — just keep it open")))
    kb = {"course": t("🎓 คอร์สเรียนฟรี", "🎓 Free course"), "guide": t("📕 คู่มือฟรี", "📕 Free guide"),
          "checklist": t("✅ เช็คลิสต์ฟรี", "✅ Free checklist"), "template": t("📝 เทมเพลตฟรี", "📝 Free template")
          }.get(magnet.kind, t("🎁 ของฟรี", "🎁 Free"))
    share_lbl = t("📤 แชร์เพื่อปลดล็อก", "📤 Share to unlock") if req_share else t("📤 แชร์ให้เพื่อน (ไม่บังคับ)", "📤 Share with a friend (optional)")
    cfg = _json.dumps({
        "token": magnet.token or "", "reqshare": req_share,
        "loading": t("กำลังปลดล็อก…", "Unlocking…"),
        "unlock": t("รับเลย — ปลดล็อกฟรี", "Get it — unlock free"),
        "bademail": t("กรุณากรอกอีเมลที่ถูกต้อง", "Please enter a valid email"),
        "sharefirst": t("กดแชร์ก่อนเพื่อปลดล็อกนะครับ", "Please share first to unlock"),
        "shared": t("✓ แชร์แล้ว", "✓ Shared"),
        "err": t("เกิดข้อผิดพลาด ลองใหม่อีกครั้ง", "Something went wrong, please try again"),
    }, ensure_ascii=False).replace("</", "<\\/")
    js = ('<script>window.LM=%s;</script>'
          '<script>(function(){var L=window.LM||{};var f=document.getElementById("lm-form"),'
          'c=document.getElementById("lm-content"),g=document.getElementById("lm-gate"),'
          'sh=document.getElementById("lm-share"),shared=false;'
          'if(sh)sh.onclick=function(){shared=true;window.open("https://www.facebook.com/sharer/sharer.php?u="'
          '+encodeURIComponent(location.href),"_blank","noopener");sh.textContent=L.shared;};'
          'if(f)f.onsubmit=function(e){e.preventDefault();var em=(document.getElementById("lm-email").value||"").trim();'
          'if(!em||em.indexOf("@")<1){alert(L.bademail);return;}if(L.reqshare&&!shared){alert(L.sharefirst);return;}'
          'var b=document.getElementById("lm-btn");b.disabled=true;b.textContent=L.loading;'
          'fetch("/api/lead/"+L.token+"/unlock",{method:"POST",headers:{"Content-Type":"application/json"},'
          'body:JSON.stringify({email:em,name:(document.getElementById("lm-name")||{}).value||"",shared:shared})})'
          '.then(function(r){return r.json();}).then(function(d){if(d&&d.content_html){c.innerHTML=d.content_html;'
          'c.style.display="block";if(g)g.style.display="none";c.scrollIntoView({behavior:"smooth"});}'
          'else{b.disabled=false;b.textContent=L.unlock;alert((d&&d.detail)||L.err);}})'
          '.catch(function(){b.disabled=false;b.textContent=L.unlock;alert(L.err);});};})();</script>'
          % cfg)
    cover_html = ('<img class="cover" src="%s" alt="%s" loading="lazy" decoding="async" width="1200" height="675">' % (cover, title)) if cover else ""
    gate_html = (
        '<div class="gate" id="lm-gate"><h3>%s</h3><p>%s</p>'
        '<form id="lm-form">%s'
        '<input id="lm-name" type="text" placeholder="%s" autocomplete="name">'
        '<input id="lm-email" type="email" required placeholder="%s" autocomplete="email">'
        '<button class="btn" id="lm-btn" type="submit">%s</button>'
        '<div style="opacity:.9;font-size:12px;margin-top:12px">%s</div></form></div>'
        % (t("กรอกอีเมลเพื่อปลดล็อกฟรีทันที", "Enter your email to unlock it free"),
           t("ปลดล็อกอ่านได้ทันทีด้านล่าง", "Unlocked to read below instantly"),
           ('<button type="button" id="lm-share" class="share">%s</button><br>' % share_lbl),
           t("ชื่อ (ไม่บังคับ)", "Name (optional)"),
           t("อีเมลของคุณ", "Your email"),
           t("รับเลย — ปลดล็อกฟรี", "Get it — unlock free"),
           t("ฟรี 100% · อ่านได้เลยด้านล่าง · ไม่สแปม", "100% free · read below now · no spam")))
    return (
        '<!doctype html><html lang="%s"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>%s</title><meta name="description" content="%s">'
        '<meta property="og:title" content="%s"><meta property="og:description" content="%s">'
        '%s<link rel="icon" href="/favicon.svg"><style>%s</style></head><body><div class="wrap">'
        '<div class="brand"><span class="mk">i</span>%s</div>'
        '<span class="kb">%s</span><h1>%s</h1><div class="desc">%s</div>'
        '%s'
        '<div class="card teaser">%s</div>'
        '%s'
        '<div class="content" id="lm-content"></div>'
        '<div class="foot">%s · %s</div>%s'
        '</div></body></html>'
        % ("en" if en else "th", title, desc, title, desc,
           (('<meta property="og:image" content="%s">' % cover) if cover else ""),
           _LM_CSS, brand, kb, title, desc, cover_html, teaser, gate_html,
           t("แจกฟรีโดย", "Free from"), brand, js)
    )


def _inject_into_head(html: str, extra: str) -> str:
    """แทรก extra ก่อน </head> (ไม่มี = หลัง <body> · ไม่มีอีก = หน้าสุด) — ไม่แตะเนื้อหาเดิม"""
    if not extra:
        return html
    m = re.search(r"(?i)</head\s*>", html)
    if m:
        return html[:m.start()] + extra + html[m.start():]
    m = re.search(r"(?i)<body[^>]*>", html)
    if m:
        return html[:m.end()] + extra + html[m.end():]
    return extra + html


def _brief_social_urls(brief: dict) -> list:
    """ดึง URL โซเชียลจาก brief → sameAs (ยืนยันตัวตนแบรนด์ให้ AI)"""
    urls = []
    for k in ("facebook", "instagram"):
        v = (brief.get(k) or "").strip()
        if v.startswith("http"):
            urls.append(v)
    ln = (brief.get("line") or "").strip()
    if ln.startswith("http"):
        urls.append(ln)
    elif ln.startswith("@"):
        urls.append("https://line.me/R/ti/p/%40" + ln[1:])
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out[:6]


def inject_aeo_geo(html: str, *, name: str, home: str, lang: str, brief: dict) -> str:
    """ฝัง 'ป้ายหุ่นยนต์' ลง home_html ที่ IM WEB สร้าง — LocalBusiness/Organization + WebSite + FAQPage
    + meta description/canonical/OG (เฉพาะที่ยังไม่มี) → เว็บ 'พร้อมให้ AI แนะนำ' ตั้งแต่นาทีแรก (ของจริง)
    additive เท่านั้น: ไม่ลบ/แทนที่ของเดิมในหน้า"""
    import json as _json
    brief = brief or {}
    lang = "en" if str(lang or "").lower().startswith("en") else "th"
    blocks = []

    address = (brief.get("address") or "").strip()
    ent = {"@context": "https://schema.org",
           "@type": "LocalBusiness" if address else "Organization",
           "name": name, "url": home}
    desc = " · ".join([x for x in [(brief.get("about") or "").strip(), (brief.get("usp") or "").strip()] if x])[:300]
    if desc:
        ent["description"] = desc
    logo = (brief.get("logo_url") or "").strip()
    if logo.startswith("http"):
        ent["logo"] = logo
        ent["image"] = logo
    sa = _brief_social_urls(brief)
    if sa:
        ent["sameAs"] = sa
    if (brief.get("phone") or "").strip():
        ent["telephone"] = brief["phone"].strip()
    if (brief.get("email") or "").strip():
        ent["email"] = brief["email"].strip()
    if address:
        ent["address"] = {"@type": "PostalAddress", "streetAddress": address}
    if (brief.get("hours") or "").strip():
        ent["openingHours"] = brief["hours"].strip()
    if (brief.get("service_area") or "").strip():
        ent["areaServed"] = brief["service_area"].strip()
    if (brief.get("map_url") or "").strip().startswith("http"):
        ent["hasMap"] = brief["map_url"].strip()
    blocks.append(ent)

    blocks.append({"@context": "https://schema.org", "@type": "WebSite",
                   "name": name, "url": home, "inLanguage": lang})

    faqs = [f for f in (brief.get("faqs") or [])
            if (f.get("q") or "").strip() and (f.get("a") or "").strip()]
    if faqs:
        blocks.append({"@context": "https://schema.org", "@type": "FAQPage",
                       "mainEntity": [{"@type": "Question", "name": (f.get("q") or "").strip(),
                                       "acceptedAnswer": {"@type": "Answer", "text": (f.get("a") or "").strip()}}
                                      for f in faqs[:12]]})

    extra = "".join('<script type="application/ld+json">%s</script>'
                    % _json.dumps(b, ensure_ascii=False).replace("</", "<\\/") for b in blocks)

    low = html.lower()                                   # เพิ่ม meta เฉพาะที่หน้ายังไม่มี (กันซ้ำ)
    if desc and "name=\"description\"" not in low and "name='description'" not in low:
        extra += '<meta name="description" content="%s">' % _esc(desc[:160])
    if home and "rel=\"canonical\"" not in low and "rel='canonical'" not in low:
        extra += '<link rel="canonical" href="%s">' % _esc(home)
    if "og:title" not in low:
        extra += '<meta property="og:title" content="%s">' % _esc(name)
    if desc and "og:description" not in low:
        extra += '<meta property="og:description" content="%s">' % _esc(desc[:200])
    if logo.startswith("http") and "og:image" not in low:
        extra += '<meta property="og:image" content="%s">' % _esc(logo)

    return _inject_into_head(html, extra)


def render_index_page(proj, arts) -> str:
    home = project_public_home(proj)
    _hh = (getattr(proj, "home_html", "") or "").strip()
    if _hh:                                       # เว็บที่ IM WEB สร้าง (โฮสต์เป็นหน้าแรกจริง) · บทความอยู่ที่ /blog/{slug}/...
        return _hh
    lang = "en" if str(proj.language).lower().startswith("en") else "th"
    en = (lang == "en")
    nm = proj.name or proj.domain
    title = ("%s — Articles & Guides" % nm) if en else ("%s — บทความ & คู่มือ" % nm)
    desc = (("Articles and guides from %s — written to answer real questions, SEO/AEO-optimized, easy to read and verifiable" % nm)
            if en else
            ("คลังบทความและคู่มือจาก %s เขียนให้ตอบคำถามจริง ถูกหลัก SEO/AEO อ่านง่าย ตรวจสอบได้" % nm))
    website_ld = json.dumps({
        "@context": "https://schema.org", "@type": "WebSite",
        "name": proj.name or proj.domain, "url": home, "inLanguage": lang,
    }, ensure_ascii=False)
    if arts:
        cards = "".join(
            '<a class="card" href="%s"><div class="cov%s">%s'
            '<span class="cov-ey">%s</span><h3 class="cov-t">%s</h3></div>'
            '<div class="cbody"><div class="x">%s</div><div class="mt">%s</div></div></a>'
            % (_esc(a.url or public_url_for(proj, a)),
               ("" if getattr(a, "cover_url", "") else " nocov"),
               ('<img class="thumb" src="%s" alt="%s" loading="lazy" decoding="async" width="400" height="225">'
                % (_esc(getattr(a, "cover_url", "") or ""), _esc(a.title)))
               if getattr(a, "cover_url", "") else "",
               _esc(getattr(a, "cluster", "") or ("Articles" if en else "บทความ")),
               _esc(a.title), _esc(_desc(a)),
               (("%d min read" % _reading_time(getattr(a, "words", 0))) if en
                else ("อ่าน ~%d นาที" % _reading_time(getattr(a, "words", 0)))))
            for a in arts)
        body = '<div class="cards">%s</div>' % cards
    else:
        body = ('<div class="empty">Articles are being prepared — the AEO system is producing them shortly</div>'
                if en else '<div class="empty">กำลังจัดเตรียมบทความ — ระบบ AEO กำลังผลิตให้เร็ว ๆ นี้</div>')
    return (
        _head(title, desc, home, lang, [website_ld], "website")
        + "<body>" + _chrome(proj, home)
        + '<main><div class="wrap">'
        + ('<header class="hero"><span class="eyebrow">%s</span>' % ("Knowledge Hub" if en else "คลังความรู้"))
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


def render_sitemap_index(slugs) -> str:
    """master sitemap index บนโดเมนหลัก — รวม sitemap ของทุกโปรเจ็ค managed
    (imvisible.tech/blog/{slug}/sitemap.xml) → ส่งให้ Google รู้จัก 'ทุกหน้า client' ในไฟล์เดียว"""
    base = settings.managed_base_domain
    scheme = settings.managed_scheme
    items = "".join(
        "<sitemap><loc>%s://%s/blog/%s/sitemap.xml</loc></sitemap>" % (scheme, base, _esc(sl))
        for sl in slugs)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</sitemapindex>' % items)


async def _index_slugs():
    """slug ของทุกโปรเจ็คที่โฮสต์บน imvisible.tech/blog/{slug} + มีบทความเผยแพร่ ≥1
    (managed เท่านั้น — โปรเจ็ค custom domain มี sitemap อยู่บนโดเมนตัวเองแล้ว)"""
    if not db.enabled():
        return []
    from app.db.models import Project, Article
    from sqlalchemy import exists
    async with db.session() as s:
        has_pub = exists().where((Article.project_id == Project.id) & (Article.status == "published"))
        rows = (await s.execute(
            select(Project.slug).where(
                Project.slug != "",
                (Project.custom_domain == "") | (Project.custom_domain.is_(None)),
                has_pub).order_by(Project.id))).scalars().all()
    return [r for r in rows if (r or "").strip()]


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
def _latest_cards(proj, arts) -> str:
    """ชิ้นส่วน HTML 'บทความล่าสุด' (การ์ด+ลิงก์จริง) สำหรับฝังในหน้า landing — inline style ไม่พึ่ง CSS ปลายทาง"""
    out = []
    for a in arts:
        url = _esc(a.url or public_url_for(proj, a))
        cover = getattr(a, "cover_url", "") or ""
        cat = _esc(getattr(a, "cluster", "") or "บทความ")
        ttl = _esc(a.title)
        desc = _esc(_desc(a)[:96])
        # magazine cover: รูปเป็นพื้นหลัง + เกลี่ยเงามืดล่าง + หัวข้อพาดบนรูป (คมชัด ดึงดูด)
        if cover:
            media = (
                '<div style="position:relative;height:194px;overflow:hidden">'
                '<img src="%s" alt="%s" loading="lazy" decoding="async" style="position:absolute;inset:0;width:100%%;height:100%%;object-fit:cover;display:block">'
                '<div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(9,19,45,.06) 0%%,rgba(9,19,45,.30) 44%%,rgba(9,19,45,.87) 100%%)"></div>'
                '<span style="position:absolute;top:12px;left:12px;background:rgba(33,84,204,.92);color:#fff;font-size:11px;font-weight:800;letter-spacing:.05em;padding:4px 11px;border-radius:999px">%s</span>'
                '<h3 style="position:absolute;left:16px;right:16px;bottom:13px;margin:0;color:#fff;font-size:18px;font-weight:800;line-height:1.3;letter-spacing:-.01em;text-shadow:0 2px 12px rgba(0,0,0,.55)">%s</h3>'
                '</div>' % (_esc(cover), ttl, cat, ttl))
        else:
            media = (
                '<div style="position:relative;height:194px;background:linear-gradient(135deg,#2154cc,#152f74);overflow:hidden">'
                '<span style="position:absolute;top:12px;left:12px;background:rgba(255,255,255,.18);color:#fff;font-size:11px;font-weight:800;letter-spacing:.05em;padding:4px 11px;border-radius:999px">%s</span>'
                '<h3 style="position:absolute;left:16px;right:16px;bottom:13px;margin:0;color:#fff;font-size:18px;font-weight:800;line-height:1.3;letter-spacing:-.01em">%s</h3>'
                '</div>' % (cat, ttl))
        out.append(
            '<a href="%s" style="display:block;text-decoration:none;color:inherit;border:1px solid #e5e9f2;'
            'border-radius:14px;overflow:hidden;background:#fff;transition:transform .15s,box-shadow .15s">%s'
            '<div style="padding:13px 16px 15px"><div style="font-size:13px;color:#5b6478;line-height:1.55">%s</div></div></a>'
            % (url, media, desc))
    return "".join(out)


# บทความล่าสุด (fragment) — ต้องมาก่อน "/blog/{project_slug}" ไม่งั้นจะถูกจับเป็น slug="_latest"
@router.get("/blog/_latest", response_class=HTMLResponse)
async def blog_latest(slug: str = "", n: int = 6):
    """ชิ้นส่วน 'บทความล่าสุด' สำหรับฝังในหน้า landing (same-origin → ไม่ติด CORS) · cache 5 นาที"""
    hdr = {"Cache-Control": "public, max-age=300"}
    proj = await _project_by_slug(slug) if slug else None
    if not proj:
        return HTMLResponse("", headers=hdr)
    arts = (await _published(proj.id))[: max(1, min(int(n or 6), 12))]
    return HTMLResponse(_latest_cards(proj, arts), headers=hdr)


# master sitemap index — ต้องมาก่อน "/blog/{project_slug}" ไม่งั้น "sitemap-index.xml" จะถูกจับเป็น slug
@router.get("/blog/sitemap-index.xml")
async def blog_sitemap_master():
    """รวม sitemap ทุก client managed ในไฟล์เดียว — ส่ง URL นี้เข้า Google Search Console
    (อยู่ใต้ /blog/* จึงเสิร์ฟจาก api ไม่โดน WordPress ดัก · ไม่ต้องแก้ Caddy)"""
    return Response_xml(render_sitemap_index(await _index_slugs()))


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
    host = _host(request)
    if host == settings.managed_base_domain.lower():      # โดเมนหลัก → master index รวมทุก client
        return Response_xml(render_sitemap_index(await _index_slugs()))
    proj = await _project_by_host(host)
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
    host = _host(request)
    base = settings.managed_base_domain.lower()
    if host == base:      # โดเมนหลัก → ชี้ Google ไป master sitemap ของ managed pages
        return PlainTextResponse(
            "User-agent: *\nAllow: /\nSitemap: %s://%s/blog/sitemap-index.xml\n"
            % (settings.managed_scheme, base))
    proj = await _project_by_host(host)
    if not proj:
        return PlainTextResponse("User-agent: *\nAllow: /\n")
    return PlainTextResponse(render_robots(proj))


@router.get("/{key}.txt", response_class=PlainTextResponse)
async def host_indexnow_key(key: str, request: Request):
    """เสิร์ฟไฟล์คีย์ IndexNow อัตโนมัติ สำหรับโดเมนที่เราโฮสต์ root (custom domain / subdomain)
    → IndexNow ยืนยันได้เอง ไม่ต้องวางไฟล์มือ · ต้องมาหลัง route .txt เฉพาะ (robots/llms) เพื่อไม่ชนกัน"""
    from app.connectors.publish import indexnow_key_for
    host = _host(request)
    if host and key and len(key) == 32 and key == indexnow_key_for(host):
        return PlainTextResponse(key)
    return PlainTextResponse("not found", status_code=404)


def Response_xml(body: str):
    from fastapi.responses import Response
    return Response(content=body, media_type="application/xml")
