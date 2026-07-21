"""
Internal Linking (M3) — เปลี่ยน "ลิงก์ภายในลอย" ให้เป็นลิงก์จริงระหว่างบทความในคลัสเตอร์
================================================================================
เครื่องยนต์คอนเทนต์สั่ง LLM ใส่ internal link เป็น <a href="#"> (placeholder) — ถ้าปล่อย
ตามนั้นบทความที่เผยแพร่จะเต็มไปด้วย "ลิงก์ตาย" (เสีย UX + ไม่ช่วยอันดับเลย)

ที่นี่ทำ 2 อย่างกับ HTML ก่อนบันทึก:
  A) RESOLVE  — จับ <a href="#">anchor</a> แล้วชี้ไป "บทความพี่น้อง" ที่เกี่ยวข้องจริง
                (จับคู่ด้วยความคล้ายของ anchor กับหัวข้อ/คำแบรนด์ของบทความอื่น)
                ถ้าไม่มีคู่ที่เข้ากัน → ถอดแท็กออก (คงข้อความไว้) เพื่อไม่ให้เหลือลิงก์ตาย
  B) AUTO-LINK — ถ้าในเนื้อมีชื่อบทความอื่นโผล่เป็นข้อความล้วน (ไม่อยู่ในลิงก์/หัวข้ออยู่แล้ว)
                ลิงก์คำนั้นไปบทความนั้นให้อัตโนมัติ (จำกัดจำนวน กันสแปมลิงก์)

Internal linking = สัญญาณ on-page อันดับต้น ๆ (topical authority + crawl depth + ส่ง
link equity ทั่วคลัสเตอร์) — ทำให้ทั้งคลัสเตอร์ติดอันดับเร็วขึ้น ไม่ใช่แค่หน้าเดียว
ทุกอย่างเป็นของจริง (ลิงก์ไปหน้าจริงที่เผยแพร่แล้วเท่านั้น) ไม่มีการปลอม
"""
import html as _htmllib
import re

_A_TAG = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.I | re.S)
_HREF = re.compile(r"""href\s*=\s*("|')(.*?)\1""", re.I)
_STRIP_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")

# แท็กที่ห้าม auto-link ทับ (หัวข้อ/ตาราง/โค้ด) — ลิงก์ในนั้นดูรก + เสีย semantics
_BLOCK_OPEN = re.compile(r"<(p|li)\b", re.I)
_NOLINK_OPEN = re.compile(r"<(h[1-6]|a|table|thead|th|code|pre|blockquote)\b", re.I)
_NOLINK_CLOSE = re.compile(r"</(h[1-6]|a|table|thead|th|code|pre|blockquote)\s*>", re.I)
_BLOCK_CLOSE = re.compile(r"</(p|li)\s*>", re.I)


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip()).lower()


def _plain(s: str) -> str:
    return _WS.sub(" ", _STRIP_TAGS.sub(" ", s or "")).strip()


def _ngrams(s: str, n: int = 3) -> set:
    """char n-gram — จับความคล้ายภาษาไทยได้ (ไทยไม่มีช่องว่างระหว่างคำ)"""
    s = re.sub(r"\s+", "", _norm(s))
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def _similarity(a: str, b: str) -> float:
    """Jaccard ของ char-3gram + โบนัสถ้าเป็น substring ของกัน (0..1+)"""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    score = 0.0
    A, B = _ngrams(a), _ngrams(b)
    if A and B:
        inter = len(A & B)
        union = len(A | B)
        score = inter / union if union else 0.0
    if len(na) >= 3 and (na in nb or nb in na):   # anchor เป็นส่วนหนึ่งของหัวข้อ (หรือกลับกัน)
        score += 0.5
    return score


def _href_of(attrs: str) -> str:
    m = _HREF.search(attrs or "")
    return (m.group(2).strip() if m else "")


def _is_placeholder(href: str) -> bool:
    h = (href or "").strip().lower()
    return h in ("", "#") or h.startswith("javascript:")


def _best_sibling(anchor_text: str, sibs: list, threshold: float = 0.18):
    """เลือกบทความพี่น้องที่ตรงกับ anchor มากที่สุด (เทียบ title + cluster + keywords)"""
    best, best_score = None, 0.0
    for sib in sibs:
        cand = "%s %s %s" % (sib.get("title", ""), sib.get("cluster", ""),
                             " ".join(sib.get("keywords", []) or []))
        sc = _similarity(anchor_text, sib.get("title", "")) * 1.0
        sc = max(sc, _similarity(anchor_text, cand) * 0.8)
        if sc > best_score:
            best, best_score = sib, sc
    return (best, best_score) if best_score >= threshold else (None, best_score)


def _resolve_placeholders(html: str, sibs: list, self_title: str):
    """A) แปลง <a href="#">…</a> → ลิงก์จริง หรือถอดแท็กถ้าไม่มีคู่ที่เข้ากัน"""
    used = set()
    stats = {"resolved": 0, "unwrapped": 0}

    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        href = _href_of(attrs)
        if not _is_placeholder(href):
            return m.group(0)                              # ลิงก์ภายนอกจริง — ไม่แตะ
        anchor_text = _plain(inner)
        pick, _score = _best_sibling(anchor_text,
                                     [s for s in sibs if s.get("url") and s["url"] not in used
                                      and _norm(s.get("title", "")) != _norm(self_title)])
        if pick:
            used.add(pick["url"])
            stats["resolved"] += 1
            return '<a href="%s">%s</a>' % (_htmllib.escape(pick["url"], quote=True), inner)
        stats["unwrapped"] += 1                            # ไม่มีคู่ → ถอดลิงก์ตายทิ้ง คงข้อความ
        return inner

    return _A_TAG.sub(repl, html or ""), stats, used


def _auto_link(html: str, sibs: list, self_title: str, already_used: set, max_links: int):
    """B) ลิงก์ชื่อบทความอื่นที่โผล่เป็นข้อความล้วนในย่อหน้า (จำกัดจำนวน กันสแปม)"""
    remaining = max_links
    if remaining <= 0:
        return html, {"auto": 0}
    # ผู้สมัคร: บทความพี่น้องที่ยังไม่ถูกลิงก์ + ชื่อยาวพอจะ match แม่น (กัน false positive)
    cands = [s for s in sibs
             if s.get("url") and s["url"] not in already_used
             and len(_norm(s.get("title", ""))) >= 6
             and _norm(s.get("title", "")) != _norm(self_title)]
    cands.sort(key=lambda s: len(s.get("title", "")), reverse=True)   # ยาวสุดก่อน = เจาะจงสุด
    used = set(already_used)
    added = 0

    parts = re.split(r"(<[^>]+>)", html or "")            # สลับ ข้อความ/แท็ก
    depth_block = 0
    depth_nolink = 0
    for i, part in enumerate(parts):
        if not part:
            continue
        if part.startswith("<"):
            if _BLOCK_OPEN.match(part):
                depth_block += 1
            elif _BLOCK_CLOSE.match(part):
                depth_block = max(0, depth_block - 1)
            elif _NOLINK_OPEN.match(part):
                depth_nolink += 1
            elif _NOLINK_CLOSE.match(part):
                depth_nolink = max(0, depth_nolink - 1)
            continue
        if remaining <= 0 or depth_block <= 0 or depth_nolink > 0:
            continue                                       # ลิงก์เฉพาะข้อความในย่อหน้า ไม่อยู่ในหัวข้อ/ลิงก์
        seg = part
        low = seg.lower()
        for sib in cands:
            if sib["url"] in used:
                continue
            title = sib["title"]
            pos = low.find(_norm(title))
            # หา occurrence จริง (ตรงตัว ไม่สนตัวพิมพ์) — ใช้ตำแหน่งจาก normalized ไม่ได้ ต้องหาในต้นฉบับ
            idx = _find_ci(seg, title)
            if idx < 0:
                continue
            end = idx + len(title)
            seg = "%s<a href=\"%s\">%s</a>%s" % (
                seg[:idx], _htmllib.escape(sib["url"], quote=True), seg[idx:end], seg[end:])
            used.add(sib["url"])
            added += 1
            remaining -= 1
            break                                          # ≤1 ลิงก์ต่อ 1 segment
        parts[i] = seg
    return "".join(parts), {"auto": added}


def _find_ci(haystack: str, needle: str) -> int:
    """หา needle ใน haystack แบบไม่สนตัวพิมพ์ คืน index ในต้นฉบับ (ภาษาไทยไม่มีเคสอยู่แล้ว)"""
    if not needle:
        return -1
    return haystack.lower().find(needle.lower())


def apply(html: str, siblings: list, self_title: str = "", max_auto: int = 3):
    """ทำ internal linking จริงกับ HTML บทความ
    siblings: [{"url","title","cluster"?,"keywords"?}] = บทความอื่นที่เผยแพร่แล้วของโปรเจ็คนี้
    คืน (html_ใหม่, stats)
    """
    sibs = [s for s in (siblings or []) if s.get("url") and s.get("title")]
    if not html:
        return html or "", {"resolved": 0, "unwrapped": 0, "auto": 0, "total": 0}
    # A) เสมอ: จับ <a href="#"> → ลิงก์จริง หรือถอดทิ้ง (แม้ยังไม่มีบทความพี่น้อง = ถอดลิงก์ตายทุกอัน
    #    เพื่อบทความแรก ๆ จะได้ไม่ปล่อยลิงก์ตายออกไป)
    html2, st_a, used = _resolve_placeholders(html, sibs, self_title)
    # B) auto-link ต้องมีบทความพี่น้องก่อน
    html3, st_b = _auto_link(html2, sibs, self_title, used, max_auto) if sibs else (html2, {"auto": 0})
    stats = {"resolved": st_a["resolved"], "unwrapped": st_a["unwrapped"],
             "auto": st_b["auto"]}
    stats["total"] = stats["resolved"] + stats["auto"]
    return html3, stats
