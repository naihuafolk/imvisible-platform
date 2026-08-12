"""
Schema Pack — สร้าง JSON-LD (structured data) 'พร้อมก็อปวาง' ให้เว็บลูกค้า
ปัญหาจริง: เว็บลูกค้าเกือบทุกเจ้ามี JSON-LD = 0 ทั้งที่มีข้อมูลครบ → Google/AI อ่านไม่ออก = เสียของฟรี
ตัวนี้ประกอบ @graph: LocalBusiness/Organization + WebSite + FAQPage จากข้อมูลจริงของโปรเจกต์
(no-faking: ใส่เฉพาะข้อมูลที่มีจริง · ช่องที่ขาดจะบอกให้เติม ไม่กุ)
FAQPage สำคัญสุด — วิจัย 2026: ถูกอ้างใน AI Overviews มากกว่า 2.1 เท่า
"""
import json


# เดาชนิดธุรกิจ → schema @type ที่เหมาะสุด (เรียงจาก 'สัญญาณเฉพาะ/แม่น' → กว้าง)
# ⚠️ ลำดับสำคัญ: packaging/manufacturing มาก่อน Restaurant (กัน 'กล่องอาหาร' แมตช์ผิดเป็นร้านอาหาร)
# และ Restaurant ต้องใช้คำเจาะจง ('ร้านอาหาร'/'คาเฟ่'/'restaurant') ไม่ใช่แค่ 'อาหาร'/'food'
_TYPE_RULES = [
    (("คลินิก", "clinic", "หมอ", "แพทย์", "ทันตกรรม", "ผิวหนัง", "เสริมความงาม",
      "medical", "dental", "รักษา", "โรงพยาบาล", "hospital"), "MedicalBusiness"),
    (("โรงแรม", "ที่พัก", "รีสอร์ท", "hotel", "resort", "hostel", "guesthouse", "โฮมสเตย์"), "LodgingBusiness"),
    (("โรงพิมพ์", "รับพิมพ์", "รับผลิต", "โรงงาน", "factory", "manufactur", "packaging", "กล่อง",
      "บรรจุภัณฑ์", "สกรีน", "ขึ้นรูป", "ผลิตภัณฑ์"), "Store"),
    (("ร้านอาหาร", "คาเฟ่", "กาแฟ", "restaurant", "cafe", "coffee shop", "บาร์เบียร์", "ก๋วยเตี๋ยว",
      "หมูกระทะ", "ชาบู", "bakery", "เบเกอรี", "ภัตตาคาร"), "Restaurant"),
    (("สอน", "คอร์สเรียน", "โรงเรียน", "ติว", "course", "school", "education", "academy",
      "หนังสือ", "book", "e-learning", "ครู"), "EducationalOrganization"),
    (("ทำเว็บ", "ซอฟต์แวร์", "แอป", "software", "saas", "แพลตฟอร์ม", "เทคโนโลยี",
      "seo", "การตลาด", "agency", "เอเจนซี", "ดิจิทัล", "digital", "รับทำ"), "ProfessionalService"),
    (("ร้าน", "ขาย", "shop", "store", "จำหน่าย", "อีคอมเมิร์ซ", "ecommerce", "ขายส่ง"), "Store"),
]


def infer_type(business_context: str = "", brand_terms: str = "", has_address: bool = False) -> str:
    hay = ((business_context or "") + " " + (brand_terms or "")).lower()
    for kws, t in _TYPE_RULES:
        if any(k in hay for k in kws):
            return t
    return "LocalBusiness" if has_address else "Organization"


def _norm_faqs(faqs) -> list:
    """รับ faq หลายรูปแบบ (list[{q,a}] / list[[q,a]] / list[str]) → [(q,a)] ที่มีทั้งคู่จริง"""
    out = []
    for f in (faqs or []):
        q = a = ""
        if isinstance(f, dict):
            q = str(f.get("q") or f.get("question") or f.get("name") or "").strip()
            a = str(f.get("a") or f.get("answer") or f.get("text") or "").strip()
        elif isinstance(f, (list, tuple)) and len(f) >= 2:
            q, a = str(f[0]).strip(), str(f[1]).strip()
        if q and a:
            out.append((q[:280], a[:900]))
    return out


def schema_pack(*, name: str, home: str, business_context: str = "", brand_terms: str = "",
                faqs=None, phone: str = "", email: str = "", address: str = "", hours: str = "",
                service_area: str = "", logo: str = "", social=None, lang: str = "th") -> dict:
    """คืน dict: {jsonld, script, types, biz_type, faq_count, missing} — พร้อมให้ลูกค้าก็อปวางใน <head>"""
    name = (name or "").strip()
    home = (home or "").strip()
    has_addr = bool((address or "").strip())
    btype = infer_type(business_context, brand_terms, has_addr)

    ent = {"@type": btype, "name": name}
    if home:
        ent["url"] = home
    desc = (business_context or "").strip()
    if desc:
        ent["description"] = desc[:300]
    if (logo or "").startswith("http"):
        ent["logo"] = logo
        ent["image"] = logo
    sa = [u for u in (social or []) if str(u).startswith("http")]
    if sa:
        ent["sameAs"] = sa
    if (phone or "").strip():
        ent["telephone"] = phone.strip()
    if (email or "").strip():
        ent["email"] = email.strip()
    if has_addr:
        ent["address"] = {"@type": "PostalAddress", "streetAddress": address.strip()}
    if (hours or "").strip():
        ent["openingHours"] = hours.strip()
    if (service_area or "").strip():
        ent["areaServed"] = service_area.strip()

    graph = [ent, {"@type": "WebSite", "name": name, "url": home,
                   "inLanguage": "en" if str(lang).lower().startswith("en") else "th"}]

    qa = _norm_faqs(faqs)
    if qa:
        graph.append({"@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qa[:12]]})

    jsonld = json.dumps({"@context": "https://schema.org", "@graph": graph},
                        ensure_ascii=False, indent=2)
    script = '<script type="application/ld+json">\n' + jsonld + '\n</script>'

    # บอกช่องที่ขาด (เติมแล้ว schema แข็งขึ้น) — โปร่งใส ไม่กุ
    missing = []
    if not has_addr:
        missing.append("ที่อยู่ → อัปเกรดเป็น LocalBusiness เต็มรูป (ดีต่อ Local SEO/แผนที่)")
    if not (phone or "").strip():
        missing.append("เบอร์โทร (telephone)")
    if not qa:
        missing.append("FAQ (คำถาม-คำตอบจริง) → ได้ FAQPage = AI หยิบไปตอบมากกว่า 2 เท่า")
    if not sa:
        missing.append("ลิงก์โซเชียล (Facebook/LINE/IG) → sameAs ช่วยยืนยันตัวตนแบรนด์")

    return {"jsonld": jsonld, "script": script,
            "types": [n["@type"] for n in graph], "biz_type": btype,
            "faq_count": len(qa), "missing": missing,
            "note": ("แปะโค้ดนี้ในส่วน <head> ของทุกหน้าเว็บลูกค้า (หรือหน้าแรก+หน้าติดต่อ) — "
                     "Google/AI จะเข้าใจธุรกิจทันที · เป็น 'ป้ายบอกข้อมูล' ที่มองไม่เห็นแต่ได้ผลจริง")}
