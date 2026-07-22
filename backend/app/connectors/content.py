"""
ImVisible Content Engine — เครื่องยนต์ผลิตคอนเทนต์ AEO/SEO ระดับโลก (multi-stage, multi-model)
ออกแบบโดยทีมผู้เชี่ยวชาญ 5 มุม (On-Page SEO · AEO · E-E-A-T · SERP-competitive · Thai)

Pipeline 3 LLM calls + lint โค้ด:
  Stage 1  Strategic Blueprint (SERP gap + intent + topical map)  → JSON  [โมเดลแรง]
  Stage 2  Answer-First HTML Draft (เขียนตามพิมพ์เขียว)            → HTML  [โมเดลเร็ว/ถูก]
  Stage 3  Master Editor (self-critique + depth + AEO + humanize + schema) [Claude พรีเมียม]
  Stage 4  Lint & Guardrail (โค้ด — strip/ตรวจ ก่อนส่ง)

ลำดับโมเดลอัตโนมัติ: premium/strong → Claude > GPT > Gemini · fast → Gemini > Claude > GPT
(ใส่ ANTHROPIC_API_KEY = ระบบใช้ Claude เขียน/บรรณาธิการทันที)
"""
import datetime
import json
import re

import httpx

from app.config import settings


# ============ utils ============

def _strip_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-zA-Z]*\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _fill(template: str, **kw) -> str:
    """แทน {var} เฉพาะคีย์ที่ให้ (ปลอดภัยกับ { } อื่นในพรอมป์ต์ที่ไม่ใช่ตัวแปร)"""
    out = template
    for k, v in kw.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def _this_year() -> str:
    try:
        return str(datetime.date.today().year)
    except Exception:
        return "2026"


def _wordcount(html: str) -> int:
    """นับคำหยาบ ๆ จาก HTML (strip แท็กก่อน) — ใช้ guard บทความว่าง/สั้น"""
    return len(re.sub(r"<[^>]+>", " ", html or "").split())


# ============ master system prompt ============

MASTER_SYSTEM = """คุณคือ "ImVisible Content Engine" — บรรณาธิการและนักกลยุทธ์ AEO/SEO ภาษาไทยระดับโลก ที่ผลิตบทความซึ่ง (1) ติดอันดับ Google หน้าแรกจริงในปี {year} และ (2) ถูก AI (ChatGPT / Gemini / Perplexity / Google AI Overviews) หยิบไปอ้างอิงเป็นคำตอบ ถ้าบทความไม่ดีพอ ลูกค้าไม่ติดอันดับ = ธุรกิจตาย คุณจึงเขียนด้วยมาตรฐาน "ชนะหน้าที่ติดอยู่แล้ว" และ "มีประโยชน์จริงกับคนอ่าน" ไม่ใช่แค่ "ครบสูตร"

หลักการที่ยึดเสมอ (ranking + citation ปี {year}):
1. INTENT-FIRST — รู้ว่าคนพิมพ์คำนี้ต้องการอะไรจริง แล้วตอบตรงทุก sub-intent จาก People Also Ask + Google Suggest คนไทยค้นแบบ "ถามเพื่อน + กลัวโดนหลอก" คำถามเงิน (ราคาเท่าไหร่/คุ้มไหม/เจ้าไหนดี/เทียบ/ข้อเสีย) ต้องตอบตรง
2. TOPICAL COMPLETENESS — ครอบทุก entity/หัวข้อย่อยที่หน้าอันดับต้นมี แล้วเติมสิ่งที่ทุกเจ้าขาด (content gap) จน user ไม่ต้องกดกลับไปค้นต่อ
3. ANSWER-FIRST + self-contained chunk — ทุก H2/H3 ที่เป็นคำถามเปิดด้วยคำตอบตรง 40-60 คำ เป็น statement ที่อ่านแยกเดี่ยวเข้าใจครบ ขึ้นต้นด้วย subject/entity ชัด (เช่น "AEO คือ...") ห้ามสรรพนามลอย ("มัน","สิ่งนี้") — quotable ก็อปไปตอบได้ทันที
4. INFORMATION GAIN + E-E-A-T — มีอย่างน้อย 3-5 อย่างที่คู่แข่งไม่มี: ตัวเลข/สถิติ, ช่วงราคาจริง, ปี {year}, ตัวอย่างไทย, ขั้นตอนทำตามได้, ข้อผิดพลาดที่คนพลาด, เกณฑ์ตัดสินใจ แสดงประสบการณ์จริง บอกทั้งข้อดี-ข้อเสีย (คนไทยเชื่อความโปร่งใส)
5. VERIFIABILITY & ANTI-HALLUCINATION — แทนคำกว้าง ("เร็วขึ้นมาก","หลากหลาย","โดยทั่วไป") ด้วยข้อมูลเจาะจง ห้ามแต่งตัวเลข/ข้อเท็จจริงปลอมเด็ดขาด ไม่มีข้อมูลจริงให้ใส่ [ต้องเติม: ...] หรือช่วง+"ขึ้นกับ..."
6. ENTITY CLARITY — ใช้คำเรียก entity หลักคำเดียวตลอด + ประโยคนิยาม "X คือ Y" ในจุดที่ AI ต้องการ definition
7. โครงสร้าง — เริ่ม H2, H3 ซ้อนใต้ H2 เท่านั้น ห้ามข้ามชั้น ห้าม H1 (ธีมใส่เอง) ย่อหน้าสั้น 2-4 บรรทัด ใช้ <ul>/<ol> เมื่อมีขั้นตอน ใช้ <table> (≤4 คอลัมน์) เมื่อเปรียบเทียบ/ราคา
8. KEYWORD ธรรมชาติ — primary ใน H2 แรก + 100 คำแรก + title; secondary/LSI กระจาย ไม่ stuffing (≤3%)
9. ภาษาไทยธรรมชาติ — เหมือนผู้เชี่ยวชาญคนไทยเล่าให้ฟัง ประโยคสั้นสลับยาว ห้ามกลิ่นแปลเครื่อง ห้ามสำนวนแข็ง ("มันเป็นสิ่งที่","ในการที่จะ") ห้ามคำเชื่อม AI ซ้ำ ("อย่างไรก็ตาม","โดยสรุปแล้ว","ในยุคดิจิทัล") YMYL (การเงิน/สุขภาพ/กฎหมาย) ต้องน่าเชื่อถือ + แหล่งอ้างอิง + disclaimer

กติกา OUTPUT (เมื่อสั่งให้ส่ง HTML): เริ่มด้วย <p> answer-first หรือ <h2> · ห้าม <html>/<head>/<body>/<style>/<script> (ยกเว้น JSON-LD ที่สั่งชัด) · ห้าม markdown fence · ใช้เฉพาะ <h2><h3><p><ul><ol><li><table><thead><tbody><tr><th><td><strong><a> · ห้าม inline style/class · เมื่อสั่งให้ส่ง JSON ให้ส่ง JSON valid เท่านั้น"""


# ============ generic model callers ============

async def _anthropic_chat(system: str, user: str, max_tokens: int = 8000) -> str:
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": settings.anthropic_api_key,
                     "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": settings.anthropic_model, "max_tokens": max_tokens,
                  "system": system, "messages": [{"role": "user", "content": user}]},
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))


async def _openai_chat(system: str, user: str) -> str:
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": settings.openai_model,
                  "messages": [{"role": "system", "content": system},
                               {"role": "user", "content": user}]},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _gemini_chat(system: str, user: str) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}")
    async with httpx.AsyncClient(timeout=180) as c:
        r = await c.post(url, json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.7},
        })
        r.raise_for_status()
        cands = r.json().get("candidates", [])
        return "".join(p.get("text", "") for p in cands[0]["content"]["parts"]) if cands else ""


async def _llm(system: str, user: str, tier: str = "fast") -> tuple[str, str]:
    """เลือกโมเดลตาม tier + คีย์ที่มี · คืน (provider, text) · ถ้าคืนค่าว่าง (เช่น safety block) = ล้มเหลว → ลองตัวถัดไป"""
    has = {"anthropic": bool(settings.anthropic_api_key),
           "openai": bool(settings.openai_api_key),
           "gemini": bool(settings.gemini_api_key)}
    callers = {"anthropic": _anthropic_chat, "openai": _openai_chat, "gemini": _gemini_chat}
    order = (["anthropic", "openai", "gemini"] if tier in ("premium", "strong")
             else ["gemini", "anthropic", "openai"])
    for prov in order:
        if not has[prov]:
            continue
        try:
            text = await callers[prov](system, user)
        except Exception:
            continue
        if text and text.strip():
            return prov, text
    raise RuntimeError("LLM ทุกตัวคืนค่าว่าง/ล้มเหลว (ตรวจคีย์ ANTHROPIC/OPENAI/GEMINI)")


async def suggest_keywords(domain: str, name: str = "", language: str = "ภาษาไทย", n: int = 12) -> list[dict]:
    """AI เสนอคีย์เวิร์ด/หัวข้อที่ธุรกิจนี้ควรทำ (เร็ว 1 คอล) — ช่วยลูกค้าที่คิดคีย์เวิร์ดไม่ออก
    หมายเหตุ: ไม่แต่งตัวเลขปริมาณค้นหา/สถิติ ให้เฉพาะ intent เชิงคุณภาพ (เป็นคำแนะนำ ไม่ใช่ค่าที่วัดจริง)"""
    sysmsg = ("คุณคือนักวางกลยุทธ์ SEO/AEO ที่เข้าใจพฤติกรรมการค้นหาของคนไทย "
              "เสนอคีย์เวิร์ด/หัวข้อที่ 'คนค้นหาจริงเพื่อตัดสินใจ' (ไม่ใช่ชื่อแบรนด์) "
              "ห้ามแต่งตัวเลขปริมาณการค้นหา/สถิติใด ๆ ตอบเป็น JSON valid เท่านั้น ห้าม markdown fence")
    usermsg = ("ธุรกิจ/เว็บไซต์: %s (โดเมน %s) · ภาษา %s\n"
               "เสนอคีย์เวิร์ด/หัวข้อ %d รายการ ที่ควรทำคอนเทนต์เพื่อดึงลูกค้าเป้าหมาย "
               "คละ intent (หาข้อมูล / เปรียบเทียบ / พร้อมซื้อ)\n"
               'ส่ง JSON เท่านั้น: {"keywords":[{"kw":"คีย์เวิร์ด","intent":"ซื้อ|เทียบ|หาข้อมูล","why":"เหตุผลสั้นมาก"}]}'
               % ((name or domain), domain, language, n))
    _prov, text = await _llm(sysmsg, usermsg, tier="fast")
    raw = _strip_fence(text).strip()
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        i, j = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[i:j + 1]) if (i >= 0 and j > i) else {}
    items = data.get("keywords") if isinstance(data, dict) else (data if isinstance(data, list) else [])
    out, seen = [], set()
    for it in items or []:
        if isinstance(it, dict):
            kw = str(it.get("kw") or it.get("keyword") or "").strip()
            intent = str(it.get("intent") or "").strip()[:16]
            why = str(it.get("why") or "").strip()[:140]
        elif isinstance(it, str):
            kw, intent, why = it.strip(), "", ""
        else:
            continue
        if kw and kw.lower() not in seen:
            seen.add(kw.lower())
            out.append({"kw": kw[:120], "intent": intent, "why": why})
    return out[:n]


# ============ stage prompts ============

_S1_SYSTEM = ("คุณคือ SEO/AEO strategist ที่ reverse-engineer หน้า SERP ไทยได้แม่นยำ และอ่านใจคนไทยที่กำลังค้นหาเพื่อตัดสินใจซื้อ "
             "ออกแบบ 'พิมพ์เขียว' บทความที่จะแซงหน้าที่ติดอันดับอยู่แล้ว โดยบังคับให้ทุก content gap และทุก PAA ถูก assign ลงโครง "
             "ห้ามเขียนมั่วจากความรู้โมเดลเอง ตอบเป็น JSON valid เท่านั้น ห้ามข้อความอื่น ห้าม markdown fence")

_S1_USER = """สร้าง Strategic Blueprint เป็น JSON สำหรับบทความภาษา {language} · ปีปัจจุบัน {year}

หัวข้อหลัก / คีย์เวิร์ดหลัก: {topic}
โดเมนลูกค้า: {domain} (ธุรกิจ: {business_context})
คำถามที่คนค้นหาจริง (People Also Ask + Google Suggest):
{questions}
คู่แข่งที่ติดอันดับ (ถ้ามี): {competitors}

ทำแล้วส่ง JSON คีย์: primary_intent (info|commercial|transactional|navigational + เหตุผล 1 ประโยค), thai_persona {who, real_worry, decision_factor}, target_keywords {primary, secondary[3-6], entities[>=10]}, entity_glossary (คำเรียก entity หลักที่ใช้เหมือนกันตลอด), content_gaps[3-5] (สิ่งที่คู่แข่งยังขาด เจาะจง), outline[] แต่ละ H2 = {h2_text (ถ้าเป็นคำถามใช้ภาษาคนไทยพิมพ์จริง), intent_covered, answer_seed (คำตอบตรง 40-60 คำ statement ขึ้นต้นด้วย subject/entity), must_include_facts (ตัวเลข/ปี/ราคา — ไม่รู้จริงใส่ [ต้องเติม: ...] ห้ามแต่ง), format (paragraph|table_price|table_compare|numbered_steps|checklist), covers (คำถาม/gap ที่รับผิดชอบ), cta (none|soft), h3_subpoints[]}, faq[4-8] {q, answer_seed}, suggested_meta {title_tag<=60, meta_description 150-160, url_slug}, internal_link_anchors[3-5], word_count_target
สำคัญ: ต้อง assign ทุก content_gap และทุกคำถามข้างบนลง H2/H3 อย่างน้อย 1 จุด รวม H2 ปิดท้าย 'คำถามที่พบบ่อย' · ส่งเฉพาะ JSON"""

_S2_SYSTEM_ADD = "\n\nคุณกำลังเติมเนื้อตามพิมพ์เขียวที่วางมาแล้ว ห้ามเพิ่ม/ลด/สลับ H2 จาก outline ห้ามคิดโครงใหม่ เขียนให้ครบทุกหัวข้อและทุก must_include_facts"

_S2_USER = """เขียนบทความภาษา {language} เป็น HTML ตามพิมพ์เขียวนี้แบบเป๊ะ · ปีปัจจุบัน {year}:
{blueprint_json}

กฎ (ห้ามละเมิด):
- เปิดด้วย <p> answer-first 40-60 คำ ตอบคำถามหลักตรง ๆ แล้วขึ้น <h2> ตัวแรก
- ใต้ทุก H2/H3 คำถาม: ย่อหน้าแรกตอบตาม answer_seed 40-60 คำ statement อ่านแยกเดี่ยวได้ ขึ้นต้นด้วย subject/entity (ห้ามสรรพนามลอย) ใส่ตัวเลข/ปี {year}/หน่วยตาม must_include_facts แล้วขยายด้วย <p>/<ul>/<ol>
- ทุก chunk self-contained · ใช้ entity ตาม entity_glossary เหมือนกันทุกที่
- must_include_facts ที่เป็น [ต้องเติม] คงไว้ ห้ามแต่งตัวเลขปลอม
- format table_* สร้าง <table> จริง (≤4 คอลัมน์ เซลล์สั้น); numbered_steps/checklist ใช้ <ol>/<ul> แต่ละข้อประโยคสมบูรณ์
- เติม content_gaps ทุกข้อ + สัญญาณ E-E-A-T ('จากเคสที่พบบ่อย...','ข้อผิดพลาดที่เจอบ่อย...', ข้อดี-ข้อเสีย)
- primary keyword ใน H2 แรก + 100 คำแรก ธรรมชาติ; secondary กระจาย
- internal link ตาม internal_link_anchors ด้วย <a href="#"> anchor ไทยกลมกลืน (ห้าม 'คลิกที่นี่')
- ปิดท้าย <h2>คำถามที่พบบ่อย</h2> + <h3>คำถาม</h3><p>คำตอบ 40-60 คำ</p> ตาม faq
- ย่อหน้า 2-4 บรรทัด ภาษาไทยธรรมชาติ ห้ามคำลอย
เอาต์พุต: HTML ล้วน เริ่ม <p>/<h2> ห้าม fence ห้าม <style>/class"""

_S3_SYSTEM = ("คุณคือบรรณาธิการอาวุโสภาษาไทย + AEO editor + conversion copywriter ที่โหดกับความตื้นและความ generic "
             "ยกร่างให้ (1) ลึก เป็นรูปธรรม information gain เหนือคู่แข่ง (2) ถูก AI/Google หยิบไปเป็นคำตอบ "
             "(3) อ่านลื่นเหมือนผู้เชี่ยวชาญคนไทยเขียนเอง (4) เปลี่ยนผู้อ่านเป็นลูกค้าแบบไม่ก้าวร้าว "
             "โดยไม่ทำลาย SEO และไม่เปลี่ยนข้อเท็จจริง/ตัวเลขเดิม ห้ามแต่งข้อมูลปลอม (ใช้ [ต้องเติม] แทน)")

_S3_USER = """ร่าง HTML + พิมพ์เขียว · ปีปัจจุบัน {year} · โดเมน {domain} · สินค้า/ปลายทาง {target_url}

พิมพ์เขียว: {blueprint_json}
ร่าง HTML: {draft_html}

ขั้นที่ 1 (คิดในใจ): ให้คะแนน 1-5 และหาจุดอ่อน — ย่อหน้าไหน generic/ลอย? จุดไหนควรมีตัวเลข/ราคา/ตัวอย่างแต่ยังกว้าง? content_gap/คำถามข้อไหนตอบไม่ครบ? ทุก H2/H3 คำถามมี answer-block 40-60 คำ quotable self-contained ไม่มีสรรพนามลอยครบไหม? มี E-E-A-T/information gain จริงไหม? ภาษาไทยตรงไหนแข็ง/แปลเครื่อง?

ขั้นที่ 2: เขียนใหม่ทั้งฉบับแก้ทุกจุดอ่อน:
A) แทนย่อหน้า generic ด้วยเนื้อเจาะจง เติมตัวเลข/ราคา/ตัวอย่างไทย/ขั้นตอน/ข้อควรระวัง อุด content_gap กระชับส่วนน้ำ ห้ามลดความครบของคำถาม
B) บีบทุก answer-block ใต้หัวข้อให้ตรง 40-60 คำ statement ก็อปไปตอบได้ทันที ขึ้นต้นด้วย subject/entity ตัดคำเกริ่น; ล่าสรรพนามลอยแก้ให้อ่านแยกเดี่ยวได้; entity ตาม glossary สม่ำเสมอ; เพิ่มนิยาม 'X คือ Y' ที่ยังขาด
C) รีไรต์ภาษาไทยให้ลื่น มีจังหวะ ตัดสำนวนแข็งและคำเชื่อม AI ซ้ำ — ตัวเลข/ความหมายเดิมห้ามเพี้ยน
D) เสริม E-E-A-T เนียน (ประสบการณ์จริง ข้อดี-ข้อเสีย) + CTA เนียน 2-3 จุด (ให้คุณค่าก่อนแล้วชวน) <a href> ไป {target_url} anchor ธรรมชาติ; internal link 2-4 จุด
E) keyword: primary ใน H2 แรก + answer-first ธรรมชาติ ≤3% ใช้ LSI; มือถือ: ย่อหน้า ≤4 บรรทัด ตาราง ≤4 คอลัมน์
F) YMYL: เพิ่มแหล่งอ้างอิง + disclaimer

ส่ง 3 บล็อกตามลำดับเป๊ะ:
<!--ARTICLE-->
(HTML สุดท้าย เริ่ม <p> answer-first หรือ <h2> ตามกฎ output)
<!--SCHEMA-->
(JSON-LD ใน <script type="application/ld+json">: Article/BlogPosting [headline, description, author, inLanguage th, datePublished {year}] + FAQPage [ทุกคำถามใน 'คำถามที่พบบ่อย' acceptedAnswer ตรงเนื้อ 100%])
<!--NOTES-->
(placeholder [ต้องเติม] ที่เหลือ + สิ่งที่คนควรตรวจก่อน publish)"""


# ============ stages ============

async def _stage1(topic, questions, domain, competitors, language, year, business_context):
    user = _fill(_S1_USER, language=language, year=year, topic=topic, domain=domain or "-",
                 business_context=business_context or "-", questions=questions or topic,
                 competitors=competitors or "(ไม่มีข้อมูล — วางโครงจาก intent + คำถามจริง)")
    prov, text = await _llm(_S1_SYSTEM, user, tier="strong")
    return _strip_fence(text)


async def _stage2(blueprint_json, language, year):
    sysp = _fill(MASTER_SYSTEM, year=year) + _S2_SYSTEM_ADD
    user = _fill(_S2_USER, language=language, year=year, blueprint_json=blueprint_json)
    prov, text = await _llm(sysp, user, tier="strong")   # ร่างด้วยโมเดลแรง (Claude) → คุณภาพสูงตั้งแต่ต้น
    return prov, _strip_fence(text)


async def _stage3(blueprint_json, draft_html, domain, target_url, year):
    user = _fill(_S3_USER, year=year, domain=domain or "-", target_url=target_url or ("https://" + (domain or "")),
                 blueprint_json=blueprint_json, draft_html=draft_html)
    prov, text = await _llm(_S3_SYSTEM, user, tier="premium")
    return prov, text


def _split_blocks(text: str):
    """แยก <!--ARTICLE--> / <!--SCHEMA--> / <!--NOTES--> · ตัด article ที่ marker ทั้ง SCHEMA และ NOTES
    (กัน NOTES/placeholder หลุดเข้าบทความเมื่อ LLM ไม่ใส่ marker SCHEMA)"""
    t = _strip_fence(text)
    after = re.split(r"<!--\s*ARTICLE\s*-->", t)[-1]
    art = re.split(r"<!--\s*(?:SCHEMA|NOTES)\s*-->", after)[0].strip()
    schema, notes = "", ""
    m = re.search(r"<!--\s*SCHEMA\s*-->(.*?)(<!--\s*NOTES\s*-->|$)", t, re.S)
    if m:
        schema = m.group(1).strip()
    n = re.search(r"<!--\s*NOTES\s*-->(.*)$", t, re.S)
    if n:
        notes = n.group(1).strip()
    return art, schema, notes


def _lint(html: str) -> str:
    """Stage 4 (โค้ด): strip fence/แท็กต้องห้าม/HTML comment + ตัดหัวข้อ intro ที่ไม่ใช่ <p>/<h2>"""
    h = _strip_fence(html)
    h = re.sub(r"<!--.*?-->", "", h, flags=re.S)   # ตัด HTML comment (กัน NOTES/marker หลุดเข้าบทความ)
    h = re.sub(r"</?(?:html|head|body|style|script)[^>]*>", "", h, flags=re.I)
    h = re.sub(r"^```[a-zA-Z]*|```$", "", h).strip()
    # ตัดข้อความก่อน <p> หรือ <h2> ตัวแรก (กันคำเกริ่นหลุด)
    m = re.search(r"<(p|h2)\b", h, flags=re.I)
    if m and m.start() > 0:
        h = h[m.start():]
    return h.strip()


# ============ main API (คงลายเซ็นเดิม + รับ context เพิ่มได้) ============

async def generate(topic: str, fmt: str = "บทความยาว", words: int = 1500, *,
                   questions=None, domain: str = "", language: str = "ภาษาไทย",
                   competitors: str = "", business_context: str = "",
                   target_url: str = "", year: str | None = None) -> dict:
    year = year or _this_year()
    q = "\n".join(questions) if isinstance(questions, (list, tuple)) else (questions or topic)

    # --- Stage 1: Blueprint (ถ้าล้ม ใช้พิมพ์เขียวย่อ) ---
    try:
        blueprint = await _stage1(topic, q, domain, competitors, language, year, business_context)
        json.loads(blueprint)  # validate parse
    except Exception:
        blueprint = json.dumps({"topic": topic, "target_keywords": {"primary": topic},
                                "questions": (questions or [])[:8]}, ensure_ascii=False)

    # --- Stage 2: Draft ---
    prov2, draft = await _stage2(blueprint, language, year)

    # --- Stage 3: Master Editor (Claude ถ้ามีคีย์) — ถ้าล้ม ใช้ร่าง ---
    provider, schema, notes = prov2, "", ""
    try:
        prov3, edited = await _stage3(blueprint, draft, domain, target_url, year)
        article, schema, notes = _split_blocks(edited)
        if len(article) > 200:
            draft = article
            provider = prov3
    except Exception:
        pass

    html = _lint(draft)
    if _wordcount(html) < 120:   # guard: ห้ามคืน/เผยแพร่บทความว่าง/สั้น (auto-loop จะจับเป็น error)
        raise RuntimeError("เนื้อหาที่ได้สั้น/ว่างเกินไป (%d คำ)" % _wordcount(html))
    model = {"anthropic": settings.anthropic_model, "openai": settings.openai_model,
             "gemini": settings.gemini_model}.get(provider, "")
    return {"provider": provider, "model": model, "html": html,
            "schema": schema, "notes": notes, "blueprint": blueprint,
            "engine": "imvisible-content-engine-v2"}


# ============ optimize (feedback loop จาก AEO Score → เขียนซ่อมให้คะแนนขึ้น) ============

_IMPROVE_SYSTEM = ("คุณคือบรรณาธิการ AEO/SEO ภาษาไทยระดับโลก งานนี้คือ 'ซ่อมบทความเดิม' ให้แข็งขึ้นตามจุดอ่อนที่ระบุ "
                   "เพื่อดันอันดับ + โอกาสถูก AI อ้างอิง โดยห้ามเปลี่ยนข้อเท็จจริง/ตัวเลขเดิม ห้ามแต่งข้อมูลปลอม "
                   "(ไม่รู้จริงใช้ [ต้องเติม: ...]) รักษาความถูกต้องภาษาไทยและโครง H2/H3 ที่ดีไว้ ปรับเฉพาะสิ่งที่ทำให้ดีขึ้น")

_IMPROVE_USER = """ซ่อมบทความ HTML ภาษา {language} ให้แข็งขึ้น · ปีปัจจุบัน {year} · หัวข้อ: {title}

จุดอ่อนที่วัดได้ (แก้ให้ครบทุกข้อ ตามลำดับความสำคัญ):
{weaknesses}

บทความเดิม:
{html}

กติกา:
- แก้ตามจุดอ่อนข้างบนให้ครบ: ถ้าขาด answer-first ให้เปิดด้วยย่อหน้าตอบตรง 40-60 คำ; ถ้าขาด 'คำถามที่พบบ่อย' ให้เพิ่ม H2 คำถามที่พบบ่อย 4-8 ข้อพร้อมคำตอบ; ถ้าขาดนิยามให้เพิ่มประโยค 'X คือ...'; ถ้าตื้นให้เพิ่มความลึก (ตัวเลข/ราคา/ตัวอย่าง/ขั้นตอน) ห้ามน้ำ; ถ้าขาด list/ตารางให้ใส่เมื่อเหมาะ; วางคีย์เวิร์ดหลักในย่อหน้าแรกและ H2 อย่างเป็นธรรมชาติ
- คงข้อเท็จจริง/ตัวเลข/ลิงก์ <a href> เดิมไว้ (ห้ามเปลี่ยนปลายทางลิงก์) · ห้าม H1 · ใช้เฉพาะแท็กที่อนุญาต
- ห้ามทำให้สั้นลงหรือตัดหัวข้อที่ดีอยู่แล้วทิ้ง

ส่ง 2 บล็อกตามลำดับเป๊ะ:
<!--ARTICLE-->
(HTML ที่ซ่อมแล้ว เริ่ม <p> answer-first หรือ <h2>)
<!--SCHEMA-->
(JSON-LD ใน <script type="application/ld+json">: Article/BlogPosting + FAQPage ทุกคำถามใน 'คำถามที่พบบ่อย')"""


async def improve(html: str, title: str, weaknesses: str,
                  language: str = "ภาษาไทย", year: str | None = None) -> dict:
    """ซ่อมบทความเดิมให้ปิดจุดอ่อน AEO/SEO ที่วัดได้ — คืน html/schema ใหม่ (ล้ม/สั้น = คงเดิม)"""
    year = year or _this_year()
    user = _fill(_IMPROVE_USER, language=language, year=year, title=title,
                 weaknesses=weaknesses or "-", html=html)
    prov, text = await _llm(_IMPROVE_SYSTEM, user, tier="premium")
    article, schema, _notes = _split_blocks(text)
    new_html = _lint(article)
    if _wordcount(new_html) < 120:            # กันผลลัพธ์ว่าง/สั้น → ถือว่าซ่อมไม่สำเร็จ
        return {"html": html, "schema": "", "provider": prov, "changed": False}
    return {"html": new_html, "schema": schema or "", "provider": prov, "changed": True}
