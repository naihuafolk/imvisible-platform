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


_BIG_PLATFORMS = ("facebook.", "youtube.", "tiktok.", "instagram.", "twitter.", "x.com",
                  "pantip.com", "wikipedia.", "google.", "shopee.", "lazada.", "linkedin.", "medium.com")


async def find_link_opportunities(name: str, domain: str, brand_terms=None, keywords=None,
                                  language: str = "ภาษาไทย") -> dict:
    """หาโอกาสได้แบ็กลิงก์ 'white-hat' ผ่าน SERP จริง (ไม่ซื้อ ไม่สแปม):
      - mention  : เว็บที่พูดถึงแบรนด์เรา (มักยังไม่ลิงก์ → ขอลิงก์ง่ายสุด)
      - resource : หน้ารวม/แนะนำใน niche (ขอให้เพิ่มเราเข้าลิสต์)
      - guest    : เว็บที่เปิดรับบทความรับเชิญ
    คืนรายการโอกาส — คนเอาไปติดต่อเอง (ระบบไม่ยิงลิงก์ให้)"""
    brand = (name or domain or "").strip()
    terms = [t for t in (brand_terms or []) if t][:2] or [brand]
    kw = ([k for k in (keywords or []) if k] or [brand])[0]
    own = (domain or "").lower().replace("www.", "").split("/")[0]
    th = str(language).startswith("ภาษาไทย")

    async def _safe(coro):
        try:
            return await coro
        except Exception:  # noqa: BLE001
            return []

    mention_q = " OR ".join('"%s"' % t for t in terms)
    mentions = await _safe(serp.search("%s -site:%s" % (mention_q, own or "example.com"), n=10))
    resources = await _safe(serp.search(
        ("%s (แนะนำ OR รวม OR \"ที่ไหนดี\" OR เจ้าไหนดี)" % kw) if th
        else ("%s (best OR top OR recommended OR roundup)" % kw), n=8))
    guest = await _safe(serp.search(
        "%s (\"บทความรับเชิญ\" OR \"เขียนให้เรา\" OR \"write for us\" OR \"guest post\")" % kw, n=6))

    def _clean(rows, kind):
        out = []
        for r in rows:
            d = (r.get("domain") or "").lower().replace("www.", "")
            if not d or (own and own in d) or any(b in d for b in _BIG_PLATFORMS):
                continue
            out.append({"title": r.get("title"), "url": r.get("url"), "domain": r.get("domain"),
                        "snippet": (r.get("snippet") or "")[:180], "kind": kind})
        return out

    seen, opps = set(), []
    for kind, rows in (("mention", mentions), ("resource", resources), ("guest", guest)):
        for o in _clean(rows, kind):
            if o["url"] and o["url"] not in seen:
                seen.add(o["url"]); opps.append(o)
    return {"brand": brand, "opportunities": opps[:24],
            "note": "โอกาสจริงจาก SERP · white-hat (ติดต่อขอลิงก์เอง ไม่ซื้อ ไม่สแปม) — ระบบร่างข้อความให้ได้"}


async def draft_outreach(url: str, title: str, kind: str, brand: str, domain: str,
                         language: str = "ภาษาไทย") -> dict:
    """ร่างข้อความติดต่อขอแบ็กลิงก์แบบสุภาพ จริงใจ (คนเอาไปตรวจ+ส่งเอง) — ปรับตามชนิดโอกาส · ไม่เสนอเงินแลกลิงก์"""
    goal = {
        "mention": "เว็บนี้พูดถึงแบรนด์เราแล้วแต่น่าจะยังไม่ได้ลิงก์ → ขอให้เพิ่มลิงก์กลับมาที่เว็บเราอย่างสุภาพ",
        "resource": "เว็บนี้มีหน้ารวม/แนะนำใน niche → ขอให้พิจารณาเพิ่มเราเข้าลิสต์ พร้อมเหตุผลว่ามีประโยชน์ต่อผู้อ่านเขา",
        "guest": "เว็บนี้เปิดรับบทความรับเชิญ → เสนอหัวข้อบทความคุณภาพที่เราเขียนให้ พร้อมลิงก์กลับ 1 จุดที่เกี่ยวข้อง",
    }.get(kind, "ติดต่อขอความร่วมมือแบบสุภาพ มืออาชีพ")
    system = ("คุณคือผู้เชี่ยวชาญ outreach/PR สาย white-hat เขียนข้อความติดต่อที่สุภาพ จริงใจ สั้น กระชับ "
              "เน้นประโยชน์ต่อผู้รับและผู้อ่านของเขา ไม่ตื๊อ ไม่สแปม 'ห้ามเสนอเงินแลกลิงก์' (ผิดกฎ Google) "
              "เขียนเป็น%s" % language)
    user = ("แบรนด์เรา: %s (เว็บ %s)\nเว็บเป้าหมาย: %s (%s)\nเป้าหมาย: %s\n\n"
            "ส่ง 2 ส่วนตามลำดับ: บรรทัดแรก 'หัวข้อ:' (subject สั้น) แล้วเว้นบรรทัด ตามด้วยเนื้อความ 80–130 คำ "
            "เป็นกันเองแต่มืออาชีพ ระบุเหตุผลเฉพาะเจาะจงว่าทำไมจึงมีประโยชน์ต่อผู้อ่านของเขาจริง ๆ"
            % (brand, domain, title or url, url, goal))
    prov, text = await content._llm(system, user, tier="fast")
    return {"provider": prov, "text": text.strip(), "kind": kind, "url": url}


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
