"""
AI Citation — Prompt Sampling (วัด 'ของจริงแต่เป็นค่าประมาณ')
ยิงชุดคำถามจริงไปที่ ChatGPT / Gemini / Perplexity แล้วอ่านคำตอบว่า
'เอ่ยถึง/อ้างอิงแบรนด์หรือโดเมนเราหรือไม่' -> นับ % = Share of Voice

*** ไม่มี API ทางการที่บอก citation ตรง ๆ — ทุกเครื่องมือในตลาด (Profound/Otterly)
ใช้วิธีสุ่มถามแบบนี้ ผลจึงเป็น 'ค่าประมาณเชิงสถิติ' คำตอบ AI เปลี่ยนตามผู้ใช้/เวลา ***
"""
import json

import httpx

from app.config import settings


async def _ask_openai(question: str) -> str:
    if not settings.openai_api_key:
        return ""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": settings.openai_model,
                  "messages": [{"role": "user", "content": question}]},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _ask_gemini(question: str) -> str:
    if not settings.gemini_api_key:
        return ""
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(url, json={"contents": [{"parts": [{"text": question}]}]})
        r.raise_for_status()
        try:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            return ""


async def _ask_anthropic(question: str) -> str:
    if not settings.anthropic_api_key:
        return ""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.anthropic_api_key,
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": settings.anthropic_model, "max_tokens": 1024,
                  "messages": [{"role": "user", "content": question}]},
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))


async def _ask_perplexity(question: str) -> str:
    if not settings.perplexity_api_key:
        return ""
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            "https://api.perplexity.ai/chat/completions",
            headers={"Authorization": f"Bearer {settings.perplexity_api_key}"},
            json={"model": settings.perplexity_model,
                  "messages": [{"role": "user", "content": question}]},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


_ENGINES = {"openai": _ask_openai, "gemini": _ask_gemini,
            "perplexity": _ask_perplexity, "anthropic": _ask_anthropic}


def _is_cited(answer: str, brand_terms: list[str], domain: str) -> bool:
    text = (answer or "").lower()
    if domain and domain.lower().lstrip("www.") in text:
        return True
    return any(t.lower() in text for t in brand_terms if t)


async def _extract_competitors(answers: list[str], brand_terms: list[str],
                               domain: str, language: str = "ภาษาไทย") -> list[dict]:
    """ดึง 'ชื่อแบรนด์/บริษัทที่ AI แนะนำ' จากคำตอบ (ยกเว้นแบรนด์เรา) → นับความถี่
    = คู่แข่งที่ AI แนะนำแทนเรา (รู้ว่าต้องแซงใครในสนาม AEO) · ไม่แต่งชื่อที่ไม่มีในคำตอบ"""
    text = "\n---\n".join(a for a in answers if a).strip()[:6000]
    if not text:
        return []
    from app.connectors import content
    ours = ", ".join([b for b in (brand_terms or []) if b] + ([domain] if domain else [])) or "-"
    sysmsg = ("คุณคือนักวิเคราะห์ที่ดึง 'ชื่อแบรนด์/บริษัท/ผู้ให้บริการ' ที่ถูกแนะนำในคำตอบ AI เท่านั้น "
              "เอาเฉพาะชื่อจริงที่เป็นแบรนด์ (ไม่เอาคำทั่วไป/คำอธิบาย) · ห้ามรวมแบรนด์เรา (%s) "
              "ห้ามแต่งชื่อที่ไม่ได้อยู่ในคำตอบ · ตอบ JSON เท่านั้น ห้าม markdown fence · ภาษา%s" % (ours, language))
    usermsg = ("คำตอบจาก AI (หลายคำถามรวมกัน):\n%s\n\n"
               "ดึงชื่อแบรนด์/บริษัทที่ 'ถูกแนะนำ' + นับว่าถูกเอ่ยกี่ครั้ง (เรียงมาก→น้อย) ยกเว้นแบรนด์เรา\n"
               'ส่ง JSON: {"competitors":[{"name":"ชื่อแบรนด์","mentions":3}]}' % text)
    try:
        _prov, out = await content._llm(sysmsg, usermsg, tier="fast")
        raw = content._strip_fence(out).strip()
        i, j = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[i:j + 1]) if (i >= 0 and j > i) else {}
        ours_low = [x.lower() for x in ([b for b in (brand_terms or []) if b] + ([domain] if domain else []))]
        res = []
        for c in (data.get("competitors") or []):
            if isinstance(c, dict) and str(c.get("name") or "").strip():
                nm = str(c["name"]).strip()[:80]
                if nm.lower() in ours_low:                 # กันแบรนด์เราหลุดเข้ามา
                    continue
                try:
                    m = int(c.get("mentions") or 1)
                except (TypeError, ValueError):
                    m = 1
                res.append({"name": nm, "mentions": max(1, m)})
        return sorted(res, key=lambda x: -x["mentions"])[:8]
    except Exception:  # noqa: BLE001
        return []


async def sample(questions: list[str], brand_terms: list[str], domain: str,
                 engines: list[str], language: str = "ภาษาไทย") -> dict:
    """คืน Share of Voice ต่อเอนจิน + ภาพรวม + รายผลต่อคำถาม + คู่แข่งที่ AI แนะนำแทนเรา"""
    per_engine: dict[str, dict] = {}
    details: list[dict] = []
    answers: list[str] = []

    for eng in engines:
        fn = _ENGINES.get(eng)
        if not fn:
            continue
        cited = 0
        answered = 0
        for q in questions:
            try:
                ans = await fn(q)
            except Exception as e:  # noqa: BLE001 — เก็บ error ต่อคำถาม ไม่ให้ล้มทั้งชุด
                details.append({"engine": eng, "question": q, "error": str(e)})
                continue
            if not ans:
                continue
            answered += 1
            answers.append(ans)                          # เก็บคำตอบไว้สกัด 'คู่แข่งที่ AI แนะนำ'
            hit = _is_cited(ans, brand_terms, domain)
            if hit:
                cited += 1
                # เก็บ snippet คำตอบ = 'หลักฐาน' ว่า AI อ้างอิงเราจริง (ไว้โชว์ลูกค้า)
                details.append({"engine": eng, "question": q, "cited": True,
                                "snippet": " ".join((ans or "").split())[:280]})
            else:
                details.append({"engine": eng, "question": q, "cited": False})
        sov = round(cited / answered * 100, 1) if answered else None
        per_engine[eng] = {"answered": answered, "cited": cited, "sov_percent": sov}

    valid = [e["sov_percent"] for e in per_engine.values() if e["sov_percent"] is not None]
    overall = round(sum(valid) / len(valid), 1) if valid else None
    competitors = await _extract_competitors(answers, brand_terms, domain, language)

    return {
        "overall_sov_percent": overall,
        "per_engine": per_engine,
        "details": details,
        "competitors": competitors,
        "note": "ค่าประมาณเชิงสถิติจากการสุ่มถาม — คำตอบ AI เปลี่ยนได้ตามผู้ใช้/เวลา",
    }
