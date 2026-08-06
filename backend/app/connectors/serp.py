"""
SERP connector — ดึงผลอันดับ Google จริงผ่าน DataForSEO
เอกสาร: https://docs.dataforseo.com/v3/serp/google/organic/live/advanced/
ใช้วัด "อันดับ / ติดหน้า 1" (M5) และประกอบการขุดคำถาม (M1)
"""
import asyncio
import base64
import httpx

from app.config import settings

BASE = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"


def _auth_header(creds: dict | None = None) -> dict:
    # คีย์ของลูกค้า (per-project) ก่อน → ไม่มีค่อย fallback คีย์กลางของแพลตฟอร์ม
    login = (creds or {}).get("login") or settings.dataforseo_login
    password = (creds or {}).get("password") or settings.dataforseo_password
    if not (login and password):
        raise RuntimeError("ยังไม่ได้ตั้งค่า DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD (คีย์ลูกค้าหรือคีย์กลาง)")
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}


async def account_balance(creds: dict | None = None) -> float | None:
    """ยอดเงินคงเหลือจริงใน DataForSEO (USD) — ไว้เตือนแอดมินให้เติมเครดิต · crash-safe (None ถ้าดึงไม่ได้)"""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://api.dataforseo.com/v3/appendix/user_data", headers=_auth_header(creds))
            r.raise_for_status()
            data = r.json()
        money = (data["tasks"][0]["result"][0].get("money") or {})
        bal = money.get("balance")
        return float(bal) if bal is not None else None
    except Exception:  # noqa: BLE001
        return None


async def backlinks_summary(domain: str, creds: dict | None = None) -> dict | None:
    """สรุป Backlink 'จริง' ของโดเมน (DataForSEO Backlinks API) — จำนวนลิงก์ · โดเมนอ้างอิง ·
    dofollow · rank · spam score (= ตัวชี้คุณภาพ) · new/lost
    ⚠️ Backlinks เป็นผลิตภัณฑ์แยกของ DataForSEO คิดเครดิตต่างหาก · crash-safe
    คืน dict ผลลัพธ์ หรือ {"error": <เหตุจริงจาก DataForSEO>} เมื่อพลาด (เพื่อโชว์ให้ลูกค้ารู้เหตุ)"""
    target = (domain or "").strip().replace("https://", "").replace("http://", "").strip("/")
    if target.startswith("www."):
        target = target[4:]
    target = target.split("/")[0]
    if not target:
        return {"error": "โดเมนว่าง"}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.dataforseo.com/v3/backlinks/summary/live",
                headers=_auth_header(creds),
                json=[{"target": target, "internal_list_limit": 10,
                       "backlinks_status_type": "live", "include_subdomains": True}])
            data = r.json()
        # DataForSEO ใส่สถานะ 2 ระดับ (top + task) — ดึง 'เหตุจริง' มาบอกลูกค้า
        top_ok = data.get("status_code") in (20000, None)
        task = ((data.get("tasks") or [{}])[0]) or {}
        res = task.get("result") or []
        if r.status_code >= 400 or not top_ok:
            return {"error": data.get("status_message") or ("HTTP %s" % r.status_code)}
        if task.get("status_code") not in (20000, None) and not res:
            return {"error": task.get("status_message") or "งานไม่สำเร็จ"}
        if not res:
            return {"error": "โดเมนนี้ยังไม่มีข้อมูล backlink ในฐานข้อมูล DataForSEO"}
        d = res[0] or {}
        attr = d.get("referring_links_attributes") or {}
        return {
            "target": target,
            "backlinks": d.get("backlinks"),
            "referring_domains": d.get("referring_domains"),
            "referring_main_domains": d.get("referring_main_domains"),
            "referring_domains_nofollow": d.get("referring_domains_nofollow"),
            "dofollow": attr.get("dofollow"),
            "nofollow": attr.get("nofollow"),
            "rank": d.get("rank"),
            "spam_score": d.get("backlinks_spam_score"),
            "new_referring_domains": d.get("new_referring_domains"),
            "lost_referring_domains": d.get("lost_referring_domains"),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:200]}


# โดเมนที่ 'แข็ง' (แซงยาก) vs UGC/ฟอรัม (แซงได้ด้วยคอนเทนต์คุณภาพ) — ใช้ประเมินความยากจากหน้า SERP จริง
_HARD_DOMAINS = ("wikipedia.", "lazada.", "shopee.", "amazon.", "facebook.com",
                 "youtube.com", "google.", "tiktok.com", "central.co", "jd.co", "agoda.", "booking.")
_HARD_TLDS = (".gov", ".go.th", ".ac.th", ".edu", ".or.th")
_UGC_DOMAINS = ("pantip.com", "reddit.com", "quora.com", "medium.com", "blogspot.",
                "wordpress.com", "twitter.com", "x.com", "sanook.", "kapook.", "dek-d.")


async def keyword_difficulty(keyword: str, creds: dict | None = None,
                             location_code: int | None = None,
                             language_code: str | None = None) -> dict:
    """⚡ Easy-Win Radar — ประเมิน 'ความยากในการติดอันดับ' จากโครงหน้า SERP จริง (ใช้ SERP ที่จ่ายอยู่แล้ว 1 call)
    ไม่ใช่ค่า KD ของเวนเดอร์ — เป็น heuristic โปร่งใสจากผลหน้า 1 (โดเมนแข็ง = ยาก, ฟอรัม/UGC = แซงง่าย)
    คืน {score 0-100 (น้อย=ง่าย), label, signals} · crash-safe"""
    try:
        results = await search(keyword, n=10, location_code=location_code,
                               language_code=language_code, creds=creds)
    except Exception:  # noqa: BLE001
        return {"score": None, "label": "?", "signals": {}}
    if not results:
        return {"score": 25, "label": "ง่าย", "signals": {"organic": 0}}   # SERP โล่ง = โอกาสสูง
    top = results[:10]
    hard = ugc = homepage = 0
    for it in top:
        dom = (it.get("domain") or "").lower().removeprefix("www.")
        url = (it.get("url") or "").lower()
        if any(h in dom for h in _HARD_DOMAINS) or any(dom.endswith(t) or t in dom for t in _HARD_TLDS):
            hard += 1
        if any(u in dom for u in _UGC_DOMAINS):
            ugc += 1
        path = url.split(dom, 1)[1] if (dom and dom in url) else "/"
        if path in ("", "/"):                     # หน้าแรกของโดเมนติดอันดับ = แบรนด์แข็งกว่า
            homepage += 1
    score = 45 + hard * 7 + homepage * 2 - ugc * 6
    score = max(5, min(95, score))
    label = "ง่าย" if score < 40 else ("ปานกลาง" if score < 65 else "ยาก")
    return {"score": score, "label": label,
            "signals": {"hard": hard, "ugc": ugc, "homepage": homepage, "organic": len(top)}}


async def keyword_volume(keyword: str, creds: dict | None = None,
                         location_code: int | None = None,
                         language_code: str | None = None) -> dict | None:
    """ปริมาณการค้นหา 'จริง' (Google Ads · DataForSEO) — เฉลี่ย/เดือน + เทรนด์ 12 เดือน (มีที่มา 100% ไม่ปั้นเลข)
    ⚠️ Keywords Data เป็นผลิตภัณฑ์แยก คิดเครดิตต่อคำ · crash-safe (None ถ้าไม่มีข้อมูล/พลาด)
    คืน {"keyword","volume","monthly":[{"y","m","v"}],"source"} หรือ None"""
    kw = (keyword or "").strip()
    if not kw:
        return None
    loc = location_code or settings.serp_location_code
    lang = language_code or settings.serp_language_code
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live",
                headers=_auth_header(creds),
                json=[{"keywords": [kw], "location_code": loc, "language_code": lang}])
            data = r.json()
        if r.status_code >= 400 or data.get("status_code") not in (20000, None):
            return None
        res = ((data.get("tasks") or [{}])[0].get("result")) or []
        if not res:
            return None
        d = res[0] or {}
        vol = d.get("search_volume")
        monthly = [{"y": m.get("year"), "m": m.get("month"), "v": int(m.get("search_volume") or 0)}
                   for m in (d.get("monthly_searches") or []) if m.get("search_volume") is not None]
        monthly.sort(key=lambda x: ((x["y"] or 0), (x["m"] or 0)))
        monthly = monthly[-12:]
        if not monthly or vol is None:
            return None
        return {"keyword": kw, "volume": vol, "monthly": monthly, "source": "Google Ads · DataForSEO"}
    except Exception:  # noqa: BLE001
        return None


async def keyword_ideas(seeds, limit: int = 30, creds: dict | None = None,
                        location_code: int | None = None,
                        language_code: str | None = None) -> list[dict]:
    """💼 ดึง 'คีย์เวิร์ดที่เกี่ยวข้อง' จาก seed (คีย์+ธุรกิจ) พร้อม 'ปริมาณค้นหาจริง + ความยาก' — DataForSEO Labs Keyword Ideas
    ได้ทั้ง volume (Google Ads) + keyword_difficulty (0-100) + เทรนด์รายเดือน ใน 1 call · ตัวเลขจริง 100% (no-faking)
    คืน [{keyword, volume(/เดือน), daily, difficulty(0-100), competition, monthly:[{y,m,v}]}] เรียงจาก volume มาก→น้อย · crash-safe คืน []"""
    ks = [str(s).strip() for s in (seeds if isinstance(seeds, (list, tuple)) else [seeds]) if str(s).strip()][:20]
    if not ks:
        return []
    loc = location_code or settings.serp_location_code
    lang = language_code or settings.serp_language_code
    try:
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post(
                "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live",
                headers=_auth_header(creds),
                json=[{"keywords": ks, "location_code": loc, "language_code": lang,
                       "limit": max(20, min(int(limit or 30), 100)),
                       "order_by": ["keyword_info.search_volume,desc"]}])
            data = r.json()
        if r.status_code >= 400 or data.get("status_code") not in (20000, None):
            return []
        items = (((data.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}).get("items") or []
        out = [x for x in (_parse_kw_item(it) for it in items) if x]
        out.sort(key=lambda x: (x["volume"] is None, -(x["volume"] or 0)))
        return out
    except Exception:  # noqa: BLE001
        return []


def _parse_kw_item(it: dict) -> dict | None:
    """แปลง item จาก DataForSEO Labs → แถวคีย์เวิร์ดมาตรฐานของเรา (ใช้ร่วมทุก endpoint)"""
    kw = (it.get("keyword") or "").strip()
    if not kw:
        return None
    ki = it.get("keyword_info") or {}
    kp = it.get("keyword_properties") or {}
    sii = it.get("search_intent_info") or {}          # เจตนาการค้นหาจริงจาก DataForSEO (ML)
    vol = ki.get("search_volume")
    monthly = [{"y": m.get("year"), "m": m.get("month"), "v": int(m.get("search_volume") or 0)}
               for m in (ki.get("monthly_searches") or []) if m.get("search_volume") is not None]
    monthly.sort(key=lambda x: ((x["y"] or 0), (x["m"] or 0)))
    return {
        "keyword": kw,
        "volume": int(vol) if isinstance(vol, (int, float)) else None,
        "daily": round(vol / 30) if isinstance(vol, (int, float)) else None,
        "difficulty": kp.get("keyword_difficulty"),
        "competition": ki.get("competition"),
        "df_intent": sii.get("main_intent"),          # informational/navigational/commercial/transactional
        "monthly": monthly[-12:],
    }


async def keyword_suggestions(seed, limit: int = 30, creds: dict | None = None,
                              location_code: int | None = None,
                              language_code: str | None = None) -> list[dict]:
    """💡 คีย์เวิร์ดที่ 'มีคำ seed อยู่ข้างใน' (full-text) — recall สูงกับคีย์ไทยหางยาว
    ต่างจาก keyword_ideas ที่อิง 'หมวดหมู่' (คืน 0 ถ้า seed แคบ/เฉพาะเกิน) · crash-safe คืน []"""
    seed = str(seed or "").strip()
    if not seed:
        return []
    loc = location_code or settings.serp_location_code
    lang = language_code or settings.serp_language_code
    try:
        async with httpx.AsyncClient(timeout=45) as c:
            r = await c.post(
                "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_suggestions/live",
                headers=_auth_header(creds),
                json=[{"keyword": seed, "location_code": loc, "language_code": lang,
                       "include_seed_keyword": True,
                       "limit": max(20, min(int(limit or 30), 100)),
                       "order_by": ["keyword_info.search_volume,desc"]}])
            data = r.json()
        if r.status_code >= 400 or data.get("status_code") not in (20000, None):
            return []
        items = (((data.get("tasks") or [{}])[0].get("result") or [{}])[0] or {}).get("items") or []
        return [x for x in (_parse_kw_item(it) for it in items) if x]
    except Exception:  # noqa: BLE001
        return []


# คำนำหน้าเชิงบริการ (ไทย) ที่ทำให้ seed แคบเกินจน Labs หาไม่เจอ → ตัดออกเหลือ 'คำแก่น'
# เรียงยาว→สั้นตอนใช้ (ใน _broaden_seed) เพื่อตัดคำที่ยาวสุดก่อน · เลี่ยง 'ผลิต/ทำ' เดี่ยว ๆ ที่ตัดผิด (ผลิตภัณฑ์)
_SEED_PREFIX = ("บริการรับผลิตและออกแบบ", "รับผลิตและออกแบบ", "รับออกแบบและผลิต",
                "บริการรับผลิต", "บริการรับทำ", "บริการออกแบบ", "รับผลิต", "รับออกแบบ",
                "รับพิมพ์", "รับสกรีน", "รับขึ้นรูป", "รับกลึง", "รับเหมา", "รับสร้าง",
                "รับทำ", "รับทํา", "สั่งผลิต", "สั่งทำ", "โรงงานผลิต", "โรงงาน",
                "บริการ", "จำหน่าย", "ราคา", "ขายส่ง", "ขาย", "ร้าน", "หา")


def _broaden_seed(seed: str) -> str:
    """ตัดคำนำหน้าเชิงบริการออก เหลือคำแก่น เช่น 'รับทำแพ็คเกจจิ้ง' → 'แพ็คเกจจิ้ง'"""
    s = (seed or "").strip()
    for w in sorted(_SEED_PREFIX, key=len, reverse=True):
        if s.startswith(w) and len(s) > len(w) + 1:
            return s[len(w):].strip()
    return s


# ── แยก 'เจตนาเชิงธุรกิจ' ของคีย์เวิร์ด เพื่อทำรายงานขายที่ใช้ได้จริง (ไม่ใช่ดั๊มพ์ดิบ) ──
_INTENT_COMMERCIAL = ("รับทำ", "รับผลิต", "รับออกแบบ", "รับขึ้น", "รับงาน", "สั่งทำ", "สั่งผลิต",
                      "สั่งซื้อ", "ราคา", "ที่ไหนดี", "เจ้าไหนดี", "ที่ไหน", "แนะนำ", "รีวิว",
                      "pantip", "ถูก", "บริการ", "ขายส่ง", "โรงงาน", "ใกล้ฉัน", "จ้าง", "หาที่",
                      "รับทํา", "ทําเอง", "ทำเอง")
_INTENT_PROBLEM = ("คืออะไร", "คือ", "ยังไง", "อย่างไร", "วิธี", "ทำไม", "ประเภท", "ชนิด",
                   "ตัวอย่าง", "ไอเดีย", "idea", "ความหมาย", "หมายถึง", "แปลว่า", "ภาษาอังกฤษ",
                   "เขียนยังไง", "มีอะไรบ้าง", "ข้อดี", "ข้อเสีย", "ต่างกัน", "ขั้นตอน",
                   "เริ่มต้น", "มีกี่", "ควร", "?")
_INTENT_BRAND = ("บริษัท", "จำกัด", "จก.", "co.,ltd", "co.ltd", " ltd", "มหาชน", "(ประเทศไทย)")


def classify_intent(kw: str, df_intent: str | None = None) -> str:
    """แยกเจตนาเชิงธุรกิจ → commercial(พร้อมจ้าง)/problem(คำถาม)/brand(คู่แข่ง)/generic(หมวดสินค้า)
    ใช้ 'search intent จริงจาก DataForSEO' ก่อน (navigational=หาแบรนด์เฉพาะ=คู่แข่ง) แม่นกว่าเดาจากคำมาก
    แล้ว fallback เป็น heuristic คำ เมื่อ DataForSEO ไม่ส่ง intent มา"""
    k = (kw or "").lower()
    has_q = any(w in k for w in _INTENT_PROBLEM)
    has_buy = any(w in k for w in _INTENT_COMMERCIAL)
    di = (df_intent or "").lower()
    if di == "navigational":                       # ค้นหาชื่อแบรนด์/บริษัทเฉพาะ = คู่แข่ง (กรองออก)
        return "brand"
    if di in ("commercial", "transactional"):
        return "problem" if (has_q and not has_buy) else "commercial"
    if di == "informational":
        return "problem" if has_q else "generic"
    # ── DataForSEO ไม่ส่ง intent → ใช้ heuristic คำ ──
    if has_buy:
        return "commercial"
    if has_q:
        return "problem"
    if any(w in k for w in _INTENT_BRAND):
        return "brand"
    return "generic"


async def keyword_research(seeds, limit: int = 30, creds: dict | None = None,
                           location_code: int | None = None,
                           language_code: str | None = None) -> list[dict]:
    """💼 วิจัยคีย์เวิร์ดสำหรับขาย — รวมหลายแหล่งให้ได้ผลจริงเสมอ:
    (1) Keyword Suggestions ของ seed เต็ม (2) ของ 'คำแก่น' หลังตัดคำนำหน้า (3) Keyword Ideas เชิงหมวด
    → merge + dedupe + เรียงตาม volume · ตัวเลขจริง 100% (no-faking) · crash-safe คืน []"""
    raw = [str(s).strip() for s in (seeds if isinstance(seeds, (list, tuple)) else [seeds]) if str(s).strip()]
    if not raw:
        return []
    seedset: list[str] = []
    for s in raw:
        for cand in (s, _broaden_seed(s)):
            if cand and cand.lower() not in [x.lower() for x in seedset]:
                seedset.append(cand)
    jobs = [keyword_suggestions(s, limit=limit, creds=creds,
                                location_code=location_code, language_code=language_code)
            for s in seedset[:4]]
    jobs.append(keyword_ideas(raw, limit=limit, creds=creds,
                              location_code=location_code, language_code=language_code))
    results = await asyncio.gather(*jobs, return_exceptions=True)
    merged: dict[str, dict] = {}
    for res in results:
        if isinstance(res, BaseException) or not res:
            continue
        for row in res:
            k = row["keyword"].lower()
            prev = merged.get(k)
            if prev is None or (row.get("volume") or 0) > (prev.get("volume") or 0):
                merged[k] = row
    out = list(merged.values())
    out.sort(key=lambda x: (x["volume"] is None, -(x["volume"] or 0)))
    for row in out:
        row["intent"] = classify_intent(row["keyword"], row.get("df_intent"))
    return out[:60]


async def rank_check(keyword: str, domain: str,
                     location_code: int | None = None,
                     language_code: str | None = None,
                     creds: dict | None = None) -> dict:
    """
    ยิงคีย์เวิร์ดไปที่ Google (ผ่าน DataForSEO) แล้ว:
      - คืน top 10 (หน้า 1)
      - หา 'อันดับของโดเมนเรา' ในผลทั้งหมด
      - บอกว่า 'ติดหน้า 1 จริงไหม' (อันดับ 1–10)
    ตัวเลขนี้ตรวจสอบเองได้: เปิด Google เสิร์ชคำเดียวกันก็เห็น
    """
    payload = [{
        "keyword": keyword,
        "location_code": location_code or settings.serp_location_code,
        "language_code": language_code or settings.serp_language_code,
        "device": "desktop",
        "depth": 100,
    }]
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(BASE, headers=_auth_header(creds), json=payload)
        r.raise_for_status()
        data = r.json()

    try:
        items = data["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError, TypeError):
        return {"keyword": keyword, "domain": domain, "our_rank": None,
                "on_page1": False, "top10": [], "raw_status": data.get("status_message")}

    dom = domain.lower().removeprefix("www.")
    organic = [it for it in items if it.get("type") == "organic"]

    our_rank = None
    for it in organic:
        d = (it.get("domain") or "").lower().removeprefix("www.")
        if d == dom:
            our_rank = it.get("rank_absolute")
            break

    top10 = [{
        "rank": it.get("rank_absolute"),
        "title": it.get("title"),
        "domain": it.get("domain"),
        "url": it.get("url"),
    } for it in organic if (it.get("rank_absolute") or 999) <= 10]

    return {
        "keyword": keyword,
        "domain": domain,
        "our_rank": our_rank,
        "on_page1": our_rank is not None and our_rank <= 10,
        "top10": top10,
    }


async def search(query: str, n: int = 8,
                 location_code: int | None = None,
                 language_code: str | None = None,
                 creds: dict | None = None) -> list[dict]:
    """SERP search ทั่วไป — คืน organic results (title/url/domain/snippet)
    ใช้หา 'โอกาสกระจาย' จริง: กระทู้ Pantip / ชุมชน / ไดเรกทอรี ที่ตรง niche ลูกค้า"""
    payload = [{
        "keyword": query,
        "location_code": location_code or settings.serp_location_code,
        "language_code": language_code or settings.serp_language_code,
        "device": "desktop",
        "depth": 20,
    }]
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(BASE, headers=_auth_header(creds), json=payload)
        r.raise_for_status()
        data = r.json()
    try:
        items = data["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError, TypeError):
        return []
    organic = [it for it in items if it.get("type") == "organic"]
    return [{
        "title": it.get("title"), "url": it.get("url"),
        "domain": it.get("domain"), "snippet": it.get("description"),
    } for it in organic[:n]]


async def pantip_page1(keywords, creds: dict | None = None,
                       location_code: int | None = None,
                       language_code: str | None = None) -> list[dict]:
    """🎯 หากระทู้ Pantip ที่ 'ติดหน้า 1 Google' สำหรับหัวข้อของเรา — ไปตอบให้มีประโยชน์ = ยืมทราฟฟิก
    + ความน่าเชื่อถือที่กระทู้นั้นมีอยู่แล้ว · คืน [{query, rank(1-10), title, url, snippet}] · crash-safe คืน []"""
    qs = [str(k).strip() for k in (keywords or []) if str(k).strip()][:8]
    seen, out = set(), []
    for q in qs:
        try:
            rows = await search(q, n=10, creds=creds,
                                location_code=location_code, language_code=language_code)
        except Exception:  # noqa: BLE001
            continue
        for i, r in enumerate(rows):
            url = (r.get("url") or "").strip()
            dom = (r.get("domain") or "").lower()
            if "pantip.com" not in dom or not url or url in seen:
                continue
            seen.add(url)
            out.append({"query": q, "rank": i + 1, "title": r.get("title") or url,
                        "url": url, "snippet": r.get("snippet") or ""})
    out.sort(key=lambda x: (x["rank"], x["query"]))
    return out


async def top_competitors(keyword: str, n: int = 5,
                          location_code: int | None = None,
                          language_code: str | None = None,
                          creds: dict | None = None) -> list[dict]:
    """ดึงหน้าที่ติดอันดับต้น ๆ จริง (title + snippet + url) เพื่อป้อนเครื่องยนต์คอนเทนต์
    ใช้วิเคราะห์ content gap ใน Stage 1 (แซงคู่แข่งที่ติดอยู่แล้ว) — คืน [] ถ้าไม่มีคีย์/ล้ม"""
    payload = [{
        "keyword": keyword,
        "location_code": location_code or settings.serp_location_code,
        "language_code": language_code or settings.serp_language_code,
        "device": "desktop",
        "depth": 20,
    }]
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(BASE, headers=_auth_header(creds), json=payload)
        r.raise_for_status()
        data = r.json()
    try:
        items = data["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError, TypeError):
        return []
    organic = [it for it in items if it.get("type") == "organic"]
    return [{
        "rank": it.get("rank_absolute"),
        "title": it.get("title"),
        "snippet": it.get("description"),
        "url": it.get("url"),
        "domain": it.get("domain"),
    } for it in organic[:n]]
