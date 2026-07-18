"""
Content generation — ผลิตบทความสูตร AEO ด้วย LLM จริง (Multi-Model)
ลำดับความชอบ: Anthropic (Claude) -> OpenAI -> Gemini (ใช้ตัวที่มีคีย์)
"""
import re
import httpx

from app.config import settings


def _strip_fence(text: str) -> str:
    """ตัด code fence ```html ... ``` ที่ LLM บางตัวห่อมาให้"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()

_AEO_SYSTEM = (
    "คุณเป็นนักเขียนคอนเทนต์ AEO ภาษาไทย เขียนบทความที่เปิดด้วยคำตอบสั้น 40–60 คำ "
    "(Answer-First) จากนั้นใช้โครงสร้างหัวข้อ H2/H3 เป็นระบบ มีส่วน FAQ และสรุปประเด็น "
    "อ้างอิงข้อเท็จจริงที่ตรวจสอบได้ และเขียนให้ AI หยิบไปตอบได้ง่าย"
)


def _prompt(topic: str, fmt: str, words: int) -> str:
    return (f"เขียนคอนเทนต์รูปแบบ '{fmt}' หัวข้อ: {topic}\n"
            f"ความยาวประมาณ {words} คำ ภาษาไทย ตามสูตร AEO ข้างต้น\n"
            f"ส่งกลับ 'เฉพาะ HTML เนื้อหาบทความ' เท่านั้น — ใช้แท็ก <h2>, <h3>, <p>, <ul>, <table> "
            f"และมีส่วน FAQ ท้ายบทความ · ห้ามใส่ <html>, <head>, <style>, <body> หรือ markdown code fence "
            f"(เริ่มด้วย <h2> ได้เลย)")


async def generate(topic: str, fmt: str = "บทความยาว", words: int = 1500) -> dict:
    if settings.anthropic_api_key:
        html = await _anthropic(topic, fmt, words)
        return {"model": settings.anthropic_model, "provider": "anthropic", "html": _strip_fence(html)}
    if settings.openai_api_key:
        html = await _openai(topic, fmt, words)
        return {"model": settings.openai_model, "provider": "openai", "html": _strip_fence(html)}
    if settings.gemini_api_key:
        html = await _gemini(topic, fmt, words)
        return {"model": settings.gemini_model, "provider": "gemini", "html": _strip_fence(html)}
    raise RuntimeError("ยังไม่ได้ตั้งค่าคีย์ LLM ตัวใดเลย (ANTHROPIC/OPENAI/GEMINI)")


async def _anthropic(topic: str, fmt: str, words: int) -> str:
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.anthropic_api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": settings.anthropic_model, "max_tokens": 4096,
                  "system": _AEO_SYSTEM,
                  "messages": [{"role": "user", "content": _prompt(topic, fmt, words)}]},
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))


async def _openai(topic: str, fmt: str, words: int) -> str:
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": settings.openai_model,
                  "messages": [{"role": "system", "content": _AEO_SYSTEM},
                               {"role": "user", "content": _prompt(topic, fmt, words)}]},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _gemini(topic: str, fmt: str, words: int) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}")
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(url, json={
            "system_instruction": {"parts": [{"text": _AEO_SYSTEM}]},
            "contents": [{"parts": [{"text": _prompt(topic, fmt, words)}]}],
        })
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
