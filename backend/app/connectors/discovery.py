"""
Distribution Discovery — หา "ฐานกระจาย" ต่อลูกค้าอัตโนมัติ (ขาว ปลอดภัย)
  - หากระทู้ Pantip / ชุมชน (reddit/blockdit) / ไดเรกทอรี ที่ตรง niche ลูกค้า (ผ่าน SERP จริง)
  - AI ร่างคำตอบที่ "มีประโยชน์จริง ไม่ขายของ ไม่สแปม" ให้ → คนเอาไปโพสต์เอง (ไม่ auto-ยิง = ไม่โดนแบน)
เราไม่โพสต์ให้อัตโนมัติในชุมชน — นั่นคือสแปม; เราแค่ "ชี้เป้า + ร่างให้"
"""
from app.connectors import serp, content


async def discover(name: str, domain: str, keywords, language: str = "ภาษาไทย") -> dict:
    """คืนแผนที่กระจายต่อลูกค้า: pantip / communities / directories (ผลจริงจาก SERP)"""
    kws = [k for k in (keywords or []) if k][:3] or [name or domain]
    top = kws[0]

    async def _safe(coro):
        try:
            return await coro
        except Exception:  # noqa: BLE001
            return []

    pantip = await _safe(serp.search("site:pantip.com %s" % top, n=8))
    communities = await _safe(serp.search("%s (reddit OR blockdit OR \"กลุ่ม facebook\")" % top, n=8))
    directories = await _safe(serp.search("%s ไดเรกทอรี OR directory OR รวมรายชื่อ" % top, n=6))

    def _clean(rows, drop_own=True):
        out = []
        for r in rows:
            d = (r.get("domain") or "").lower()
            if drop_own and domain and domain.lower() in d:
                continue
            out.append({"title": r.get("title"), "url": r.get("url"),
                        "domain": r.get("domain"), "snippet": (r.get("snippet") or "")[:180]})
        return out

    return {
        "keywords_used": kws,
        "pantip": _clean(pantip),
        "communities": _clean(communities),
        "directories": _clean(directories),
    }


async def draft_reply(question: str, snippet: str, blog_url: str, brand: str,
                      language: str = "ภาษาไทย") -> dict:
    """ร่างคำตอบชุมชนแบบจริงใจ มีประโยชน์ ไม่ขายของ (คนเอาไปตรวจ+โพสต์เอง)"""
    system = ("คุณเป็นผู้เชี่ยวชาญที่ตอบในฟอรัม/ชุมชนออนไลน์อย่างจริงใจ เป็นมนุษย์ มีประโยชน์จริง "
              "ห้ามขายของ ห้ามสแปม ห้ามยัดลิงก์ เขียนเป็น%s ตอบคำถามให้ตรงและครบก่อน "
              "แล้วค่อยแนบลิงก์อ้างอิงเฉพาะถ้าเกี่ยวข้องจริง ๆ (แนบครั้งเดียวพอ หรือไม่แนบเลยถ้าไม่จำเป็น)" % language)
    user = ("กระทู้/คำถาม: %s\nบริบทเพิ่มเติม: %s\nแบรนด์ (ห้ามโฆษณาโต้งๆ): %s\n"
            "ลิงก์บทความอ้างอิงที่ใส่ได้ถ้าเกี่ยวจริง: %s\n\n"
            "เขียนคำตอบยาว 120–200 คำ ที่คนอ่านแล้วรู้สึกว่าช่วยจริง ไม่ใช่การตลาด"
            % (question or "-", snippet or "-", brand or "-", blog_url or "-"))
    prov, text = await content._llm(system, user, tier="fast")
    return {"provider": prov, "text": text.strip()}
