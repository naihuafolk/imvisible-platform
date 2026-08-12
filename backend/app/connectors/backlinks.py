"""
Backlink Autopilot — ทำแบ็กลิงก์ 'ขาว' ให้ง่ายสุดต่อลูกค้า
หลักการ: ระบบเตรียม 'ทุกอย่างพร้อม' (ข้อมูลลูกค้าจัดฟอร์แมต + ลิสต์แหล่งคุณภาพ + สถานะ) → operator แค่
'เปิด → วาง → submit' หรือ 'กดส่ง' · white-hat 100%: ไม่ auto-โพสต์ ไม่ซื้อลิงก์ ไม่ปั๊ม PBN
(การ auto-โพสต์/ปั๊มลิงก์ = Google ลงโทษ = เว็บลูกค้าตาย → เราจึงทำ 'กึ่งอัตโนมัติแบบปลอดภัย' แทน)
"""
import json


# ── แหล่งแบ็กลิงก์ 'ขาว' คุณภาพ (foundational + directory + social + niche) ──────────────
# tier: must (ทำก่อน คุ้มสุด) · recommend (ควรทำ) · niche (เฉพาะบางธุรกิจ — โชว์เมื่อ match)
# match: คำที่ทำให้แหล่ง niche 'เกี่ยว' (ว่าง = เกี่ยวทุกธุรกิจ)
DIRECTORIES: list[dict] = [
    # ── foundational (ทุกลูกค้าต้องมี — ผลกับ Local SEO สูงสุด) ──
    {"id": "gbp", "name": "Google Business Profile", "url": "https://business.google.com/create",
     "cat": "foundational", "tier": "must", "dofollow": False, "region": "TH/Global",
     "note": "สำคัญสุดสำหรับ Local SEO — โปรไฟล์ธุรกิจบน Google Maps/Search (ยืนยันที่อยู่/เบอร์)"},
    {"id": "bing-places", "name": "Bing Places for Business", "url": "https://www.bingplaces.com/",
     "cat": "foundational", "tier": "must", "dofollow": False, "region": "Global",
     "note": "โปรไฟล์ธุรกิจบน Bing — AI-search (ChatGPT/Copilot) ใช้ Bing เป็นฐาน"},
    {"id": "facebook", "name": "Facebook Page", "url": "https://www.facebook.com/pages/create",
     "cat": "social", "tier": "must", "dofollow": False, "region": "TH/Global",
     "note": "เพจธุรกิจ + ใส่ลิงก์เว็บในช่อง About/เว็บไซต์"},
    {"id": "line-oa", "name": "LINE Official Account", "url": "https://manager.line.biz/",
     "cat": "social", "tier": "must", "dofollow": False, "region": "TH",
     "note": "ช่องทางหลักคนไทย — ใส่ลิงก์เว็บในโปรไฟล์/rich menu"},
    # ── directory (ไทย) ──
    {"id": "thai-yellowpages", "name": "Thailand YellowPages", "url": "https://www.yellowpages.co.th/",
     "cat": "directory", "tier": "recommend", "dofollow": True, "region": "TH",
     "note": "ไดเรกทอรีธุรกิจไทยเก่าแก่ — ลงหมวดให้ตรง"},
    {"id": "thaitambon", "name": "ไทยตำบล (ThaiTambon)", "url": "https://www.thaitambon.com/",
     "cat": "directory", "tier": "recommend", "dofollow": True, "region": "TH",
     "note": "ไดเรกทอรีสินค้า/ร้านค้าไทยรายตำบล"},
    {"id": "longdo-map", "name": "Longdo Map", "url": "https://map.longdo.com/",
     "cat": "directory", "tier": "recommend", "dofollow": False, "region": "TH",
     "note": "แผนที่ไทย — ปักหมุดธุรกิจ + เว็บไซต์"},
    # ── social profiles (foundational links เพิ่มเติม) ──
    {"id": "youtube", "name": "YouTube Channel", "url": "https://www.youtube.com/channel_switcher",
     "cat": "social", "tier": "recommend", "dofollow": False, "region": "Global",
     "note": "ช่อง + ใส่ลิงก์เว็บใน About/Links (คลิปสั้นก็ได้)"},
    {"id": "tiktok", "name": "TikTok Business", "url": "https://www.tiktok.com/business/",
     "cat": "social", "tier": "recommend", "dofollow": False, "region": "TH/Global",
     "note": "โปรไฟล์ธุรกิจ + ลิงก์เว็บใน bio"},
    {"id": "linkedin", "name": "LinkedIn Company Page", "url": "https://www.linkedin.com/company/setup/new/",
     "cat": "social", "tier": "recommend", "dofollow": False, "region": "Global",
     "note": "เพจบริษัท — ดีต่อ B2B/บริการองค์กร"},
    # ── review / niche (โชว์เมื่อธุรกิจเกี่ยว) ──
    {"id": "wongnai", "name": "Wongnai", "url": "https://www.wongnai.com/business-owners",
     "cat": "niche", "tier": "niche", "dofollow": False, "region": "TH",
     "match": ["ร้าน", "อาหาร", "คาเฟ่", "กาแฟ", "restaurant", "cafe", "food", "บาร์", "โรงแรม",
               "สปา", "ความงาม", "คลินิก", "beauty", "salon", "ที่พัก"],
     "note": "รีวิวร้านอาหาร/คาเฟ่/ความงาม/ที่เที่ยว — โปรไฟล์ธุรกิจ + เว็บ"},
    {"id": "tripadvisor", "name": "Tripadvisor", "url": "https://www.tripadvisor.com/Owners",
     "cat": "niche", "tier": "niche", "dofollow": False, "region": "Global",
     "match": ["โรงแรม", "ที่พัก", "ทัวร์", "ท่องเที่ยว", "ร้านอาหาร", "hotel", "resort", "tour",
               "travel", "restaurant", "bar", "cafe", "beach", "รีสอร์ท", "บาร์"],
     "note": "ท่องเที่ยว/ที่พัก/ร้านอาหาร — เคลมธุรกิจ + ใส่เว็บ"},
    {"id": "trustpilot", "name": "Trustpilot", "url": "https://business.trustpilot.com/signup",
     "cat": "review", "tier": "niche", "dofollow": False, "region": "Global",
     "match": ["ร้าน", "ขาย", "บริการ", "shop", "store", "service", "อีคอมเมิร์ซ", "ecommerce"],
     "note": "รีวิวความน่าเชื่อถือ — โปรไฟล์ + ลิงก์เว็บ"},
    {"id": "crunchbase", "name": "Crunchbase", "url": "https://www.crunchbase.com/register",
     "cat": "niche", "tier": "niche", "dofollow": False, "region": "Global",
     "match": ["ai", "tech", "software", "startup", "แพลตฟอร์ม", "เทคโนโลยี", "saas", "app", "แอป"],
     "note": "โปรไฟล์บริษัทเทค/สตาร์ทอัพ — dofollow ในบางหน้า"},
]


def _url(domain: str) -> str:
    d = (domain or "").strip()
    if not d:
        return ""
    return d if d.startswith("http") else "https://" + d


def nap_packet(p) -> dict:
    """เตรียม 'ข้อมูลลูกค้าจัดฟอร์แมตพร้อมวาง' ลงไดเรกทอรี (NAP = Name/Address/Phone + เว็บ + คำอธิบาย)
    ใช้ข้อมูลจริงจากโปรเจ็คเท่านั้น — ไม่กุ (เบอร์/ที่อยู่ที่ระบบไม่มี → เว้นให้ operator เติม)"""
    name = (p.name or "").strip()
    biz = (getattr(p, "business_context", "") or "").strip()
    lang = "en" if str(getattr(p, "language", "") or "").lower().startswith("en") else "th"
    brand = [t.strip() for t in (getattr(p, "brand_terms", "") or "").split(",") if t.strip()]
    line_id = (getattr(p, "lead_line_to", "") or "").strip()
    # คำอธิบาย: จากบริบทธุรกิจจริง (ตัดให้พอดีช่องไดเรกทอรี) — ถ้าไม่มีบริบท ใช้ชื่อแบรนด์
    short = (biz[:150].strip() or name)
    long = (biz.strip() or name)
    return {
        "name": name,
        "website": _url(getattr(p, "domain", "") or getattr(p, "custom_domain", "")),
        "description_short": short,             # สำหรับช่อง ~150 ตัวอักษร
        "description_long": long,               # สำหรับช่องยาว
        "keywords": brand[:8],                  # แท็ก/คำค้น
        "language": lang,
        "line_id": line_id,
        # ช่องที่ระบบ 'ไม่มีข้อมูล' → บอกให้ operator เติม (ไม่กุขึ้นมา)
        "todo_fields": ["เบอร์โทร", "ที่อยู่/พื้นที่ให้บริการ", "เวลาทำการ", "รูปโลโก้/หน้าร้าน"],
    }


def _relevant(d: dict, hay: str) -> bool:
    m = d.get("match")
    if not m:
        return True                             # ไม่มีเงื่อนไข = เกี่ยวทุกธุรกิจ
    return any(k in hay for k in m)


def _merge(d: dict, state: dict) -> dict:
    st = (state or {}).get(d["id"]) or {}
    out = {k: d[k] for k in ("id", "name", "url", "cat", "tier", "dofollow", "region", "note")}
    out["done"] = bool(st.get("done"))
    out["submitted_url"] = st.get("url", "")    # ลิงก์โปรไฟล์/หน้าที่ลงเสร็จ (ไว้ตรวจ)
    out["at"] = st.get("at", "")
    return out


_TIER_ORDER = {"must": 0, "recommend": 1, "niche": 2}


def build_plan(p) -> dict:
    """รวม 'แผนแบ็กลิงก์พร้อมทำ' ต่อโปรเจ็ค: ข้อมูลลูกค้าพร้อมวาง + ลิสต์แหล่งคุณภาพ + สถานะ + ความคืบหน้า"""
    try:
        state = json.loads(getattr(p, "backlink_state", "") or "{}")
        if not isinstance(state, dict):
            state = {}
    except Exception:  # noqa: BLE001
        state = {}
    hay = ((getattr(p, "business_context", "") or "") + " " + (p.name or "") + " " +
           (getattr(p, "brand_terms", "") or "")).lower()
    items = [_merge(d, state) for d in DIRECTORIES if _relevant(d, hay)]
    items.sort(key=lambda x: (x["done"], _TIER_ORDER.get(x["tier"], 9), x["name"]))
    done = sum(1 for it in items if it["done"])
    return {
        "packet": nap_packet(p),
        "directories": items,
        "progress": {"done": done, "total": len(items)},
    }


def set_directory(p, dir_id: str, done: bool, url: str = "", now_iso: str = "") -> str:
    """อัปเดตสถานะไดเรกทอรี 1 รายการ → คืน JSON string ใหม่ของ backlink_state"""
    try:
        state = json.loads(getattr(p, "backlink_state", "") or "{}")
        if not isinstance(state, dict):
            state = {}
    except Exception:  # noqa: BLE001
        state = {}
    if not any(d["id"] == dir_id for d in DIRECTORIES):
        raise ValueError("ไม่รู้จักไดเรกทอรีนี้")
    if done:
        state[dir_id] = {"done": True, "url": (url or "").strip(), "at": now_iso}
    else:
        state.pop(dir_id, None)
    return json.dumps(state, ensure_ascii=False)
