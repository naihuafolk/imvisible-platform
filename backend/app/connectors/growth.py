"""
Growth connectors — เครื่องมือดันอันดับ SEO/AEO/GEO (ต่อยอด serp.py) · สร้าง+ตรวจผ่าน workflow
ทุกฟังก์ชัน crash-safe (คืน []/{} เมื่อพัง) · ตัวเลขจริง 100% จาก DataForSEO/SERP (no-faking)
"""
import asyncio  # noqa: F401
import httpx    # noqa: F401

from app.config import settings          # noqa: F401
from app.connectors import serp          # noqa: F401
from app.connectors import citation      # noqa: F401
from app.connectors.serp import _auth_header  # noqa: F401


def _clean_domain(domain: str) -> str:
    """ตัด scheme/www/path เหลือโดเมนล้วน (ใช้ร่วมทุกฟีเจอร์)"""
    d = (domain or "").strip().lower().replace("https://", "").replace("http://", "").strip("/")
    if d.startswith("www."):
        d = d[4:]
    return d.split("/")[0].strip()



# ========== reddit_quora_radar ==========
# import ที่ต้องมีบนหัวไฟล์ backend/app/connectors/growth.py:
#   import httpx  (ยังไม่ใช้ในฟังก์ชันนี้ แต่ growth.py อื่น ๆ ใช้)
#   from app.config import settings
#   from app.connectors import serp
#   (ไม่ต้อง import _auth_header — เรียกผ่าน serp.search ซึ่งจัดการ auth ให้แล้ว)

async def social_radar(keywords,
                       sites: tuple[str, ...] = ("reddit.com", "quora.com", "medium.com"),
                       creds: dict | None = None,
                       location_code: int | None = None,
                       language_code: str | None = None) -> list[dict]:
    """🌐 GEO Radar — หากระทู้/หน้าจาก Reddit · Quora · Medium ที่ 'ติดหน้า 1 Google' สำหรับหัวข้อเรา
    AI อย่าง ChatGPT/Perplexity อ้างอิงชุมชนพวกนี้หนักมาก → ไปตอบให้มีประโยชน์จริง = ดัน GEO
    วนทุก query เรียก serp.search แล้วกรอง domain ที่อยู่ใน sites + rank<=10
    คืน [{platform, query, rank, title, url, snippet}] · crash-safe คืน []"""
    qs = [str(k).strip() for k in (keywords or []) if str(k).strip()][:8]
    allow = tuple(str(s).strip().lower().removeprefix("www.") for s in (sites or ()) if str(s).strip())
    if not qs or not allow:
        return []
    seen, out = set(), []
    for q in qs:
        try:
            rows = await serp.search(q, n=10, creds=creds,
                                     location_code=location_code, language_code=language_code)
        except Exception:  # noqa: BLE001
            continue
        for i, r in enumerate(rows):
            url = (r.get("url") or "").strip()
            dom = (r.get("domain") or "").lower().removeprefix("www.")
            platform = next((s for s in allow if s in dom), None)   # โดเมนอยู่ในลิสต์ที่สแกนไหม
            if not platform or not url or (i + 1) > 10 or url in seen:
                continue
            seen.add(url)
            out.append({"platform": platform, "query": q, "rank": i + 1,
                        "title": r.get("title") or url, "url": url,
                        "snippet": r.get("snippet") or ""})
    out.sort(key=lambda x: (x["rank"], x["platform"], x["query"]))
    return out


# ========== competitor_backlink ==========
# import ที่ต้องมีบนหัวไฟล์: asyncio, httpx, from app.config import settings, from app.connectors import serp, from app.connectors.serp import _auth_header
"""
Growth connector — เครื่องมือ "ขยายอำนาจโดเมน" ที่อิงดาต้าจริงจาก DataForSEO
#10 Competitor Backlink Mining — ขุดว่า 'ใครลิงก์หาคู่แข่ง' → เป้าที่เราควรไปขอลิงก์ (outreach)
⚠️ DataForSEO Backlinks เป็นผลิตภัณฑ์แยก คิดเครดิตต่างหากจาก SERP/Labs
ทุกฟังก์ชัน crash-safe (คืน [] เมื่อพัง) · ตัวเลขจริง 100% (no-faking)
"""
import asyncio
import httpx

from app.config import settings
from app.connectors import serp  # noqa: F401  (ใช้ auth/รูปแบบเดียวกับ SERP connector)
from app.connectors.serp import _auth_header


async def referring_domains(target_domain: str, limit: int = 100,
                            creds: dict | None = None) -> list[dict]:
    """ดึง 'โดเมนที่ลิงก์หา target' จริง (DataForSEO Backlinks) — เรียงตาม rank (โดเมนแรงก่อน)
    ⚠️ Backlinks เป็นผลิตภัณฑ์แยก คิดเครดิตต่างหาก · crash-safe คืน []
    คืน [{domain, backlinks, rank, dofollow}] — dofollow = จำนวนลิงก์ที่ไม่ใช่ nofollow (backlinks − nofollow)"""
    target = _clean_domain(target_domain)
    if not target:
        return []
    lim = max(1, min(int(limit or 100), 1000))
    try:
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post(
                "https://api.dataforseo.com/v3/backlinks/referring_domains/live",
                headers=_auth_header(creds),
                json=[{"target": target, "limit": lim,
                       "order_by": ["rank,desc"],
                       "exclude_internal_backlinks": True}])
            data = r.json()
        if r.status_code >= 400 or data.get("status_code") not in (20000, None):
            return []
        items = (((data.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}).get("items") or []
    except Exception:  # noqa: BLE001
        return []
    out: list[dict] = []
    for it in items:
        dom = _clean_domain(it.get("domain") or "")
        if not dom:
            continue
        backlinks = it.get("backlinks")
        # dofollow = ลิงก์ทั้งหมด − ที่ติด rel=nofollow (นิยามมาตรฐาน: ลิงก์เป็น nofollow หรือ dofollow อย่างใดอย่างหนึ่ง)
        nofollow = ((it.get("referring_links_attributes") or {}).get("nofollow"))
        dofollow = (backlinks - nofollow) if isinstance(backlinks, int) and isinstance(nofollow, int) else None
        out.append({
            "domain": dom,
            "backlinks": backlinks,
            "rank": it.get("rank"),
            "dofollow": dofollow,
        })
    return out


async def backlink_gaps(competitor_domains, our_domain: str = "",
                        limit: int = 100, creds: dict | None = None) -> list[dict]:
    """🎯 Backlink Gap — รวม referring domains ของคู่แข่งหลายเจ้า แล้วหา 'แหล่งที่ควร outreach'
    ตัดโดเมนตัวเอง+ตัวคู่แข่งเองออก · จัดอันดับตาม (จำนวนคู่แข่งที่ได้ลิงก์จากแหล่งนั้น) แล้วตาม rank
    = แหล่งที่ลิงก์ให้คู่แข่งหลายเจ้า → มีแนวโน้มลิงก์ให้เราด้วย · crash-safe คืน []
    คืน [{domain, rank, competitors:[โดเมนคู่แข่งที่ได้ลิงก์], competitors_count, backlinks}]"""
    comps = []
    for d in (competitor_domains or []):
        cd = _clean_domain(str(d))
        if cd and cd not in comps:
            comps.append(cd)
    comps = comps[:8]
    if not comps:
        return []
    ours = _clean_domain(our_domain)
    exclude = set(comps) | ({ours} if ours else set())
    # ดึง referring domains ของคู่แข่งทุกเจ้าพร้อมกัน (crash-safe รายเจ้า)
    results = await asyncio.gather(
        *[referring_domains(cd, limit=limit, creds=creds) for cd in comps],
        return_exceptions=True)
    agg: dict[str, dict] = {}
    for cd, res in zip(comps, results):
        if isinstance(res, BaseException) or not res:
            continue
        for row in res:
            dom = row.get("domain")
            if not dom or dom in exclude:      # ตัดโดเมนตัวเอง + ตัวคู่แข่งเอง
                continue
            cur = agg.get(dom)
            if cur is None:
                cur = {"domain": dom, "rank": row.get("rank"),
                       "backlinks": row.get("backlinks") or 0, "competitors": []}
                agg[dom] = cur
            if cd not in cur["competitors"]:
                cur["competitors"].append(cd)
            # เก็บ rank สูงสุด (แรงสุด) + backlinks มากสุดที่เห็นจากแหล่งนี้
            if (row.get("rank") or 0) > (cur["rank"] or 0):
                cur["rank"] = row.get("rank")
            if (row.get("backlinks") or 0) > (cur["backlinks"] or 0):
                cur["backlinks"] = row.get("backlinks")
    out = list(agg.values())
    for o in out:
        o["competitors_count"] = len(o["competitors"])
    # แหล่งที่ลิงก์ให้คู่แข่งหลายเจ้า = โอกาสสูงสุด → รองด้วย rank โดเมน
    out.sort(key=lambda x: (-x["competitors_count"], -(x["rank"] or 0)))
    return out[:max(1, min(int(limit or 100), 300))]


# ========== content_gap ==========
# imports ที่ต้องมีบนหัวไฟล์ backend/app/connectors/growth.py:
#   import asyncio ; import httpx ; from app.config import settings ; from app.connectors.serp import _auth_header
"""
Growth connector — เครื่องมือ 'ขยายการมองเห็น' ที่ต่อยอดจาก serp.py
#7 Content Gap Capture: หา 'คีย์ที่คู่แข่งติดอันดับ แต่เราไม่มี' = ช่องว่างคอนเทนต์ที่ผลิตแล้วแซงได้
ทุกฟังก์ชัน crash-safe (try/except คืน [] เมื่อพัง) · ตัวเลขจริง 100% จาก DataForSEO (no-faking)
"""


def _parse_ranked_item(it: dict) -> dict | None:
    """แปลง item จาก ranked_keywords → แถวมาตรฐาน (field อยู่ใต้ keyword_data + อันดับใน ranked_serp_element)
    คืน {keyword, volume, rank, difficulty} · None ถ้าไม่มีคำ"""
    kd = it.get("keyword_data") or {}
    kw = (kd.get("keyword") or "").strip()
    if not kw:
        return None
    ki = kd.get("keyword_info") or {}
    kp = kd.get("keyword_properties") or {}
    vol = ki.get("search_volume")
    # อันดับจริงบนหน้า SERP ของโดเมนนี้ (rank_absolute ก่อน → fallback rank_group)
    serp_item = (it.get("ranked_serp_element") or {}).get("serp_item") or {}
    rank = serp_item.get("rank_absolute")
    if rank is None:
        rank = serp_item.get("rank_group")
    return {
        "keyword": kw,
        "volume": int(vol) if isinstance(vol, (int, float)) else None,
        "rank": int(rank) if isinstance(rank, (int, float)) else None,
        "difficulty": kp.get("keyword_difficulty"),
    }


async def ranked_keywords(domain: str, limit: int = 100, creds: dict | None = None,
                          location_code: int | None = None,
                          language_code: str | None = None) -> list[dict]:
    """📊 คีย์เวิร์ดที่ 'โดเมนนี้ติดอันดับจริง' บน Google — DataForSEO Labs Ranked Keywords
    คืน [{keyword, volume, rank, difficulty}] เรียงตาม volume มาก→น้อย · crash-safe คืน []"""
    target = _clean_domain(domain)
    if not target:
        return []
    loc = location_code or settings.serp_location_code
    lang = language_code or settings.serp_language_code
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live",
                headers=_auth_header(creds),
                json=[{"target": target, "location_code": loc, "language_code": lang,
                       "limit": max(10, min(int(limit or 100), 1000)),
                       "order_by": ["keyword_data.keyword_info.search_volume,desc"]}])
            data = r.json()
        if r.status_code >= 400 or data.get("status_code") not in (20000, None):
            return []
        items = (((data.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}).get("items") or []
        out = [x for x in (_parse_ranked_item(it) for it in items) if x]
        out.sort(key=lambda x: (x["volume"] is None, -(x["volume"] or 0)))
        return out
    except Exception:  # noqa: BLE001
        return []


async def content_gaps(our_domain: str, competitor_domains, creds: dict | None = None,
                       limit: int = 100, location_code: int | None = None,
                       language_code: str | None = None) -> list[dict]:
    """🎯 Content Gap — คีย์ที่คู่แข่ง 'ติดหน้า 1-2 (rank<=20)' แต่ 'เราไม่ติด' = ช่องว่างที่ผลิตคอนเทนต์แซงได้
    ดึง ranked_keywords ของเรา+คู่แข่งพร้อมกัน → ลบคีย์ที่เราติดแล้วออก → เรียงตาม volume
    คืน [{keyword, volume, difficulty, rank(อันดับดีสุดของคู่แข่ง), competitor(โดเมนที่ติด)}] · crash-safe คืน []"""
    our = _clean_domain(our_domain)
    comps = [_clean_domain(d) for d in (competitor_domains or []) if _clean_domain(d)]
    comps = [d for d in comps if d != our][:5]      # กันซ้ำโดเมนเรา + จำกัดจำนวนคู่แข่ง (คุมเครดิต)
    if not comps:
        return []
    # ยิงคู่แข่ง + โดเมนเราพร้อมกัน (โดเมนเราไว้ทำ 'set คีย์ที่เราติดแล้ว')
    jobs = [ranked_keywords(d, limit=limit, creds=creds,
                            location_code=location_code, language_code=language_code) for d in comps]
    jobs.append(ranked_keywords(our, limit=limit, creds=creds,
                                location_code=location_code, language_code=language_code) if our else _empty())
    results = await asyncio.gather(*jobs, return_exceptions=True)
    comp_results = results[:-1]
    our_rows = results[-1] if not isinstance(results[-1], BaseException) else []
    # คีย์ที่ 'เราติดแล้ว' (ไม่ว่าอันดับไหน) — ตัดออกจากช่องว่าง
    ours_have = {r["keyword"].lower() for r in (our_rows or []) if r.get("keyword")}
    gaps: dict[str, dict] = {}
    for d, res in zip(comps, comp_results):
        if isinstance(res, BaseException) or not res:
            continue
        for row in res:
            rank = row.get("rank")
            if rank is None or rank > 20:            # เอาเฉพาะที่คู่แข่ง 'ติดจริง' หน้า 1-2
                continue
            k = row["keyword"].lower()
            if k in ours_have:                        # เราติดแล้ว = ไม่ใช่ช่องว่าง
                continue
            prev = gaps.get(k)
            # เก็บอันดับดีสุด (เลขน้อยสุด) ในบรรดาคู่แข่งที่ติดคีย์นี้
            if prev is None or rank < (prev.get("rank") or 999):
                gaps[k] = {"keyword": row["keyword"], "volume": row.get("volume"),
                           "difficulty": row.get("difficulty"), "rank": rank, "competitor": d}
    out = list(gaps.values())
    out.sort(key=lambda x: (x["volume"] is None, -(x["volume"] or 0)))
    return out


async def _empty() -> list[dict]:
    """placeholder job เมื่อไม่มีโดเมนเรา (our ว่าง) → คืน [] เพื่อให้ gather โครงเดียวกัน"""
    return []


# ========== featured_snippet ==========
# imports ที่ต้องมีบนหัวไฟล์ growth.py: import asyncio · import httpx · from app.config import settings · from app.connectors.serp import BASE, _auth_header
# (BASE = endpoint SERP advanced เดียวกับ serp.py — reuse ได้เลย ไม่ต้องประกาศซ้ำ)

async def _serp_items(keyword: str, creds: dict | None = None,
                      location_code: int | None = None,
                      language_code: str | None = None) -> list[dict]:
    """ยิง SERP advanced 1 call แล้วคืน 'items ดิบทุก type' (organic/featured_snippet/people_also_ask/...)
    ต่างจาก serp.search ที่กรองเหลือเฉพาะ organic — อันนี้ต้องการ block พิเศษด้วย · crash-safe คืน []"""
    payload = [{
        "keyword": keyword,
        "location_code": location_code or settings.serp_location_code,
        "language_code": language_code or settings.serp_language_code,
        "device": "desktop",
        "depth": 20,
    }]
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(BASE, headers=_auth_header(creds), json=payload)
            r.raise_for_status()
            data = r.json()
        return data["tasks"][0]["result"][0]["items"] or []
    except Exception:  # noqa: BLE001
        return []


def _snippet_guidance(has_snippet: bool, paa_count: int) -> str:
    """คำแนะนำจัดรูปแบบคอนเทนต์เพื่อ 'ชิง Position 0' — โปร่งใส ไม่กุตัวเลข (แนวทางมาตรฐาน AEO)"""
    if has_snippet:
        base = ("มี Featured Snippet อยู่แล้ว = แซงได้ด้วยการตอบตรงกว่า: วางคำตอบตรง ๆ 40-55 คำ "
                "ไว้ย่อหน้าแรกใต้ H2 ที่เป็นคำถามเป๊ะ ๆ แล้วขยายรายละเอียดด้านล่าง")
    else:
        base = ("ยังไม่มีเจ้าของ Snippet = ช่องว่างให้ชิง Position 0: ตั้ง H2 เป็นคำถามตรง ๆ "
                "แล้วตอบ 40-55 คำในย่อหน้าแรก (definition-style)")
    if paa_count:
        base += (" · มี People-Also-Ask %d ข้อ — ทำหัวข้อย่อย/FAQ ตอบทีละคำถามแบบ list หรือ table "
                 "เพื่อกวาดทั้ง PAA และ Snippet" % paa_count)
    return base


async def snippet_opportunities(keywords, creds: dict | None = None,
                                location_code: int | None = None,
                                language_code: str | None = None) -> list[dict]:
    """🎯 Featured Snippet Sniper — ต่อคีย์ ยิง SERP advanced จริง แล้วดู block พิเศษเพื่อ 'ชิง Position 0':
    (1) type=='featured_snippet' → มี/ไม่มี + โดเมนเจ้าของปัจจุบัน (2) type=='people_also_ask' → ดึงคำถาม PAA จริง
    คืน [{keyword, has_snippet, snippet_holder_domain, paa_questions:[...], guidance}] · ตัวเลข/ข้อความจริงจาก SERP (no-faking) · crash-safe คืน []"""
    ks = [str(k).strip() for k in (keywords if isinstance(keywords, (list, tuple)) else [keywords]) if str(k).strip()][:8]
    if not ks:
        return []
    # ยิงขนานทุกคีย์ (แต่ละคีย์ = 1 SERP call) — เร็วขึ้นเมื่อส่งหลายคำ
    jobs = [_serp_items(k, creds=creds, location_code=location_code, language_code=language_code) for k in ks]
    results = await asyncio.gather(*jobs, return_exceptions=True)
    out: list[dict] = []
    for kw, items in zip(ks, results):
        if isinstance(items, BaseException) or not items:
            # ยิงพลาด/ไม่มีผล → ยังคืนแถวไว้ (โปร่งใส) เพื่อไม่ให้คีย์หายเงียบ
            out.append({"keyword": kw, "has_snippet": False, "snippet_holder_domain": None,
                        "paa_questions": [], "guidance": _snippet_guidance(False, 0)})
            continue
        has_snippet = False
        holder = None
        paa: list[str] = []
        seen: set[str] = set()
        for it in items:
            t = it.get("type")
            if t == "featured_snippet":
                has_snippet = True
                holder = (it.get("domain") or "").lower().removeprefix("www.") or holder
            elif t == "people_also_ask":
                for q in it.get("items", []) or []:
                    title = (q.get("title") or "").strip()
                    key = title.lower()
                    if title and key not in seen:
                        seen.add(key)
                        paa.append(title)
        out.append({
            "keyword": kw,
            "has_snippet": has_snippet,
            "snippet_holder_domain": holder,
            "paa_questions": paa,
            "guidance": _snippet_guidance(has_snippet, len(paa)),
        })
    return out


# ========== ai_citation_engine ==========
# import ที่ต้องมีบนหัวไฟล์ backend/app/connectors/growth.py:
#   import httpx
#   from app.config import settings
#   from app.connectors import serp, citation
# (ไฟล์ growth.py ถูกสร้างให้แล้วในเรพอ — โค้ดนี้คือฟังก์ชันหลักในไฟล์นั้น)

# โดเมนที่มักเป็น 'แหล่งที่ AI/Google หยิบไปตอบ' (listicle/ฟอรัม/รีวิว) → ป้ายบอกชนิด source gap
_UGC_SOURCE = ("pantip.com", "reddit.com", "quora.com", "medium.com", "wongnai.com",
               "sanook.", "kapook.", "dek-d.", "blockdit.com", "twitter.com", "x.com",
               "youtube.com", "facebook.com", "blogspot.", "wordpress.com")


def _root_domain(domain: str) -> str:
    """ตัด scheme/www/path เหลือโดเมนแก่น (ใช้เทียบว่า 'เราอยู่ในแหล่งนั้นแล้วหรือยัง')"""
    d = (domain or "").strip().lower()
    d = d.replace("https://", "").replace("http://", "").strip("/")
    d = d.removeprefix("www.")
    return d.split("/")[0]


async def ai_citation_audit(questions, brand_terms, competitor_terms, domain: str,
                            creds: dict | None = None,
                            language: str = "ภาษาไทย") -> dict:
    """🧭 #9 AI-Citation Engine (GEO core) — วัด 2 อย่างในรอบเดียว:
      (1) 'AI แนะนำเราแค่ไหน' → สุ่มถาม AI engines จริง (reuse citation connector) แล้วนับ
          Share of Voice = คำตอบที่อ้างถึงเรา ÷ คำตอบทั้งหมด · พร้อมนับคู่แข่งที่ถูกแนะนำแทน
      (2) 'AI/Google ดึงคำตอบจากแหล่งไหน' → serp.search คำถามเดียวกัน เก็บ 'โดเมนแหล่งอ้างอิง'
          (listicle/ฟอรัม/รีวิว) ที่ 'เรายังไม่อยู่' = source gaps (ที่ต้องไปแทรกให้ AI หยิบเรา)
    คืน {sov_percent, our_mentions, competitor_mentions:{name:count}, source_gaps:[{domain,url,title}], ...}
    ผลเป็นค่าประมาณเชิงสถิติ (คำตอบ AI เปลี่ยนตามผู้ใช้/เวลา) · ตัวเลขจริงล้วน · crash-safe"""
    result: dict = {"sov_percent": None, "our_mentions": 0, "answered": 0,
                    "competitor_mentions": {}, "source_gaps": [],
                    "note": "ค่าประมาณเชิงสถิติจากการสุ่มถามจริง — คำตอบ AI เปลี่ยนได้ตามผู้ใช้/เวลา"}
    qs = [str(q).strip() for q in (questions or []) if str(q).strip()][:10]
    brands = [str(b).strip() for b in (brand_terms or []) if str(b).strip()]
    comps = [str(c).strip() for c in (competitor_terms or []) if str(c).strip()]
    if not qs:
        return result

    # ── (1) ถาม AI engines จริง (reuse citation._ENGINES) — เอนจินที่ไม่มีคีย์คืน "" แล้วข้ามเอง ──
    answered = 0
    our = 0
    comp_count: dict[str, int] = {}
    answers: list[str] = []
    for q in qs:
        for eng, fn in citation._ENGINES.items():
            try:
                ans = await fn(q)
            except Exception:  # noqa: BLE001 — เอนจินล้ม 1 ตัว ไม่ล้มทั้งชุด
                continue
            if not ans:
                continue
            answered += 1
            answers.append(ans)
            low = ans.lower()
            if citation._is_cited(ans, brands, domain):        # AI อ้างถึงเราในคำตอบนี้
                our += 1
            for c in comps:                                    # นับคู่แข่ง 'ที่รู้ชื่ออยู่แล้ว' แบบตรวจย้อนได้
                if c.lower() in low:
                    comp_count[c] = comp_count.get(c, 0) + 1

    result["answered"] = answered
    result["our_mentions"] = our
    result["sov_percent"] = round(our / answered * 100, 1) if answered else None

    # เติม 'คู่แข่งใหม่ที่ AI แนะนำ' ที่ยังไม่อยู่ในลิสต์ (สกัดด้วย LLM · reuse citation) — ไม่แต่งชื่อเกินคำตอบ
    try:
        known = {c.lower() for c in comps}
        for c in await citation._extract_competitors(answers, brands, domain, language):
            nm = str(c.get("name") or "").strip()
            if nm and nm.lower() not in known:                 # กันนับซ้ำกับที่นับด้วย substring ไปแล้ว
                comp_count[nm] = comp_count.get(nm, 0) + int(c.get("mentions") or 0)
    except Exception:  # noqa: BLE001
        pass
    # เหลือเฉพาะที่ 'ถูกเอ่ยจริง' (>0) เรียงมาก→น้อย
    result["competitor_mentions"] = dict(
        sorted(((k, v) for k, v in comp_count.items() if v > 0), key=lambda x: -x[1]))

    # ── (2) แหล่งอ้างอิงที่ Google หยิบ (page 1) ที่ 'เรายังไม่อยู่' = source gaps ──
    our_dom = _root_domain(domain)
    seen: set[str] = set()
    gaps: list[dict] = []
    for q in qs:
        try:
            rows = await serp.search(q, n=10, creds=creds)
        except Exception:  # noqa: BLE001 — ไม่มีคีย์ DataForSEO/ล้ม = ข้ามส่วน source gap (ยังคืน SoV ได้)
            continue
        for r in rows:
            dom = _root_domain(r.get("domain") or "")
            url = (r.get("url") or "").strip()
            if not dom or not url or dom in seen:
                continue
            if our_dom and (our_dom == dom or our_dom in dom):   # เราอยู่แหล่งนี้แล้ว = ไม่ใช่ gap
                continue
            seen.add(dom)
            gaps.append({"domain": dom, "url": url, "title": r.get("title") or url,
                         "kind": "ugc" if any(u in dom for u in _UGC_SOURCE) else "web"})
    result["source_gaps"] = gaps[:20]
    return result
