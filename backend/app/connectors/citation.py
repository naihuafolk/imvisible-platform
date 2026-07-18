"""
AI Citation — Prompt Sampling (วัด 'ของจริงแต่เป็นค่าประมาณ')
ยิงชุดคำถามจริงไปที่ ChatGPT / Gemini / Perplexity แล้วอ่านคำตอบว่า
'เอ่ยถึง/อ้างอิงแบรนด์หรือโดเมนเราหรือไม่' -> นับ % = Share of Voice

*** ไม่มี API ทางการที่บอก citation ตรง ๆ — ทุกเครื่องมือในตลาด (Profound/Otterly)
ใช้วิธีสุ่มถามแบบนี้ ผลจึงเป็น 'ค่าประมาณเชิงสถิติ' คำตอบ AI เปลี่ยนตามผู้ใช้/เวลา ***
"""
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


_ENGINES = {"openai": _ask_openai, "gemini": _ask_gemini, "perplexity": _ask_perplexity}


def _is_cited(answer: str, brand_terms: list[str], domain: str) -> bool:
    text = (answer or "").lower()
    if domain and domain.lower().lstrip("www.") in text:
        return True
    return any(t.lower() in text for t in brand_terms if t)


async def sample(questions: list[str], brand_terms: list[str], domain: str,
                 engines: list[str]) -> dict:
    """คืน Share of Voice ต่อเอนจิน + ภาพรวม + รายผลต่อคำถาม"""
    per_engine: dict[str, dict] = {}
    details: list[dict] = []

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
            hit = _is_cited(ans, brand_terms, domain)
            if hit:
                cited += 1
            details.append({"engine": eng, "question": q, "cited": hit})
        sov = round(cited / answered * 100, 1) if answered else None
        per_engine[eng] = {"answered": answered, "cited": cited, "sov_percent": sov}

    valid = [e["sov_percent"] for e in per_engine.values() if e["sov_percent"] is not None]
    overall = round(sum(valid) / len(valid), 1) if valid else None

    return {
        "overall_sov_percent": overall,
        "per_engine": per_engine,
        "details": details,
        "note": "ค่าประมาณเชิงสถิติจากการสุ่มถาม — คำตอบ AI เปลี่ยนได้ตามผู้ใช้/เวลา",
    }
