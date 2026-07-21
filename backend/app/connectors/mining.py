"""
M1 — ขุดคำถามจริง (Question Mining)
แหล่งจริง:
  - Google Suggest / Autocomplete  (ฟรี ไม่ต้องมีคีย์)
  - People Also Ask + Related Searches (ผ่าน DataForSEO ถ้ามีคีย์)
แล้วจัดกลุ่มเป็น Topic Cluster (Pillar + Cluster) พร้อมจำแนกว่าเป็น 'คำถาม' หรือไม่
"""
import base64
import json
import httpx

from app.config import settings

# คำบ่งชี้ว่าเป็น "คำถาม" (ใช้ทำ Topic Cluster ฝั่งคำถามลูก)
_Q_MARKERS = ["ไหม", "อะไร", "ยังไง", "อย่างไร", "ทำไม", "ที่ไหน", "กี่", "เท่าไหร่",
              "ดีไหม", "ไหนดี", "อันไหน", "ตัวไหน", "วิธี", "รีวิว", "แนะนำ", "how", "what", "why"]


async def google_suggest(seed: str, hl: str = "th", gl: str = "th") -> list[str]:
    """Google Autocomplete (ฟรี) — คืนคำค้นที่คนพิมพ์ต่อจาก seed จริง"""
    url = "https://suggestqueries.google.com/complete/search"
    params = {"client": "firefox", "hl": hl, "gl": gl, "q": seed, "ie": "utf-8", "oe": "utf-8"}
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        raw = r.content
    # Google อาจส่ง charset ไม่ตรง — บังคับถอดรหัสให้ถูก
    for enc in ("utf-8", "windows-874", "latin-1"):
        try:
            data = json.loads(raw.decode(enc))
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            data = None
    if not isinstance(data, list) or len(data) < 2:
        return []
    return data[1]  # รูปแบบ: [seed, [s1, s2, ...]]


async def paa_related(seed: str, location_code: int | None = None,
                      language_code: str | None = None,
                      creds: dict | None = None) -> dict:
    """People Also Ask + Related Searches จริง ผ่าน DataForSEO (คีย์ลูกค้าก่อน → กลาง)"""
    login = (creds or {}).get("login") or settings.dataforseo_login
    password = (creds or {}).get("password") or settings.dataforseo_password
    if not (login and password):
        return {"paa": [], "related": []}
    token = base64.b64encode(f"{login}:{password}".encode()).decode()
    payload = [{
        "keyword": seed,
        "location_code": location_code or settings.serp_location_code,
        "language_code": language_code or settings.serp_language_code,
        "device": "desktop",
    }]
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.dataforseo.com/v3/serp/google/organic/live/advanced",
            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
            json=payload)
        r.raise_for_status()
        data = r.json()
    paa, related = [], []
    try:
        items = data["tasks"][0]["result"][0]["items"]
    except (KeyError, IndexError, TypeError):
        items = []
    for it in items:
        t = it.get("type")
        if t == "people_also_ask":
            for q in it.get("items", []):
                if q.get("title"):
                    paa.append(q["title"])
        elif t == "related_searches":
            related.extend(it.get("items", []) or [])
    return {"paa": paa, "related": related}


def _is_question(text: str) -> bool:
    return any(m in text.lower() for m in _Q_MARKERS)


async def mine(seed: str, location_code: int | None = None,
               language_code: str | None = None, creds: dict | None = None) -> dict:
    """รวมทุกแหล่งจริง -> Topic Cluster (Pillar=seed, Cluster=คำถามลูก)"""
    seed = seed.strip()
    suggest = await google_suggest(seed)
    pr = await paa_related(seed, location_code, language_code, creds)

    seen, questions = set(), []
    for src, arr in (("Google Suggest", suggest), ("People Also Ask", pr["paa"]), ("Related Searches", pr["related"])):
        for q in arr:
            key = q.strip().lower()
            if key and key not in seen and key != seed.lower():
                seen.add(key)
                questions.append({"q": q.strip(), "source": src, "is_question": _is_question(q)})

    return {
        "pillar": seed,
        "count": len(questions),
        "questions": questions,
        "sources_used": ["Google Suggest"] + (["DataForSEO PAA/Related"] if pr["paa"] or pr["related"] else []),
    }
