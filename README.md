# RankPilot AI — แดชบอร์ด AEO + SEO อัตโนมัติ

แดชบอร์ด/รายงานแบบ **โต้ตอบได้จริง** ที่สร้างตามเอกสารโครงการ **"RankPilot AI"** (โครงการแพลตฟอร์ม AEO + SEO เฉพาะทาง อัตโนมัติด้วย AI สำหรับตลาดไทย) — ครบทั้ง 6 โมดูล + แดชบอร์ดหลัก + รายงาน

> สร้างตามเนื้อหาในไฟล์ `โครงการแพลตฟอร์ม-AEO-SEO-AI-Auto.pdf` v1.0 (ทุกตัวเลข/ข้อความอ้างอิงจากเอกสาร)

---

## ▶️ วิธีเปิด (ไม่ต้องติดตั้งอะไร)

**วิธีที่ 1 — ไฟล์เดียวจบ (ง่ายสุด):**
ดับเบิลคลิก `rankpilot-ai.standalone.html` → เปิดในเบราว์เซอร์ได้ทันที (ทำงานออฟไลน์ 100%)

**วิธีที่ 2 — เวอร์ชันแยกไฟล์ (สำหรับพัฒนาต่อ):**
ดับเบิลคลิก `index.html` หรือรันเซิร์ฟเวอร์เล็ก ๆ:
```bash
# ในโฟลเดอร์นี้
python -m http.server 8080
# แล้วเปิด http://localhost:8080
```

---

## 🧩 มีอะไรบ้าง (ตามโครงการ)

| หน้า | ตรงกับเอกสาร | ทำอะไร |
|------|--------------|--------|
| **แดชบอร์ดหลัก** | Wireframe หน้า 6 | KPI (บทความ / ติดหน้า 1 / AI Citation SoV / ทราฟฟิก), AI Growth Loop, ตารางคลัสเตอร์ + สถานะระบบ |
| **M1 · ขุดคำถาม & คีย์เวิร์ด** | หน้า 4 | ขุดคำถามจริง → จัดกลุ่ม **Topic Cluster** (Pillar + Cluster) → ประเมินความยาก/โอกาส → ชี้เป้า "AI Gap" (พิมพ์คีย์เวิร์ดแล้วกด "ขุดคำถาม") |
| **M2 · โรงงานคอนเทนต์** | หน้า 4–5 | คิวผลิตคอนเทนต์ตามสูตร AEO + คะแนน AEO + Fact-Check + Plagiarism + เช็กลิสต์ + E-E-A-T |
| **M3 · AEO Optimizer** | หน้า 5 | ความครอบคลุม Schema, llms.txt/Sitemap, Internal Link, **Freshness Engine**, Technical SEO Audit |
| **M4 · เผยแพร่อัตโนมัติ** | หน้า 5 | สลับโหมด Full-Auto / Auto+Human Approve, ปลายทาง (WordPress/Webflow/IndexNow), ปฏิทินคอนเทนต์, **คิวรออนุมัติ (กดอนุมัติได้)** |
| **M5 · วัดผล & Rank Tracker** | หน้า 5 | ฝั่ง SEO (อันดับ Google + Search Console) + ฝั่ง AEO (**Prompt Sampling** วัด AI Citation + Share of Voice เทียบคู่แข่ง) |
| **M6 · Learning Loop** | หน้า 5 | Insights ลักษณะร่วมของหน้าที่ติด Citation, Auto-Tuning, รายงานสรุปรายสัปดาห์ |
| **รายงาน & Roadmap** | หน้า 7–11 | Roadmap 4 เฟส, KPI 6 เดือน, กลยุทธ์, ต้นทุน, สถาปัตยกรรม, โมเดลธุรกิจ, ความเสี่ยง, อ้างอิง |

**ฟีเจอร์โต้ตอบ:** เลือกโปรเจ็ค · สลับโหมดเผยแพร่ · โหมดสว่าง/มืด · ค้นหา & ขุดคำถาม (M1) · เปิดรายละเอียดคำถาม · กดอนุมัติบทความ (M4) · Responsive (มือถือ/แท็บเล็ต)

---

## 📁 โครงสร้างไฟล์

```
rankpilot-ai/
├─ index.html                     # เวอร์ชันแยกไฟล์
├─ rankpilot-ai.standalone.html   # เวอร์ชันไฟล์เดียวจบ (พกพาง่าย)
├─ README.md
└─ assets/
   ├─ css/styles.css              # ระบบดีไซน์ (โทนสี/สไตล์ตามเอกสาร, รองรับ light/dark)
   └─ js/
      ├─ helpers.js               # ฟังก์ชันกลาง (ui.card, ui.kpi, ui.spark, modal, toast ...)
      ├─ data.js                  # ★ ข้อมูลทั้งหมด (แหล่งเดียว) อ้างอิงตัวเลขจาก PDF
      ├─ app.js                   # โครง + router (hash) + navigation
      └─ views/                   # dashboard, m1..m6, report
```

**แก้ข้อมูล/ตัวเลข:** แก้ที่ `assets/js/data.js` ที่เดียว ทุกหน้าจะอัปเดตตาม

---

## 🔐 โหมดใช้งานจริง (Login → Onboarding → Dashboard)

เปิดแอปจะเจอ **หน้าเข้าสู่ระบบ** ก่อน — กด **"ทดลองใช้ทันที (บัญชีเดโม)"** เพื่อเข้า
ครั้งแรกจะมี **onboarding 4 ขั้นตามลำดับ** (ยินดีต้อนรับ → เชื่อมต่อ → โปรเจ็คแรก → เข้าแดชบอร์ด)
แดชบอร์ดมี **ภาพรวมทุกโปรเจ็ค (portfolio)** + เช็กลิสต์เริ่มต้นใช้งาน · ออกจากระบบได้ที่มุมซ้ายล่าง
> เดโม: ระบบสมาชิกเป็นแบบจำลอง (เก็บใน localStorage) — ต่อ auth จริง (เช่น Clerk/Auth0/JWT) ได้ภายหลัง

## 🌐 โหมด Live — ต่อ backend จริง

หน้า **การตั้งค่า › การเชื่อมต่อ** มี "โหมด Live": ใส่ URL ของ backend แล้วเปิดสวิตช์
จากนั้น **M1** (ขุดคำถามจริง), **M2** (ผลิตด้วย AI สด), **M5** (ตรวจอันดับ/GSC/Citation สด) จะดึงข้อมูลจริง
ดูวิธีรัน backend + "ต่อ API อะไรกับใคร" ที่ [backend/README.md](backend/README.md)

## 🚀 ขึ้นเว็บจริงด้วยคำสั่งเดียว

```bash
docker compose up --build      # → http://localhost:8080 (frontend + backend + db + คิวงาน ครบ)
```
ได้ครบ: Postgres+pgvector · Redis · FastAPI · Celery worker/beat · nginx เสิร์ฟ frontend

**ขึ้น cloud จริง** (มี config ให้พร้อม):
- Backend + worker + beat + redis + postgres → **Render** ([render.yaml](render.yaml))
- Frontend static → **Vercel** ([vercel.json](vercel.json))
- **CI/CD อัตโนมัติ** (เทสต์ + deploy) → **GitHub Actions** ([.github/workflows/ci.yml](.github/workflows/ci.yml))

**Auth จริง:** สมัคร/เข้าสู่ระบบด้วย JWT (รหัสผ่านแฮช) เมื่อต่อ backend + `DATABASE_URL` · ผู้ใช้เดโมหลัง seed: `demo@rankpilot.ai / demo1234` · ต่อ backend ไม่ได้ → เข้าโหมดเดโมออฟไลน์อัตโนมัติ

## 🛠️ หมายเหตุเรื่องเทคโนโลยี

เอกสารโครงการวาง production stack เป็น **Next.js + FastAPI + PostgreSQL/pgvector + Redis/Celery + SERP/LLM APIs**
เดโมชุดนี้ทำเป็น **HTML/CSS/JS ล้วน (ไม่มี build/ไม่ต้องมี server/ไม่ต้องมี API key)** เพื่อให้ **เปิดแล้วใช้งานได้ทันที 100%** และโครงสร้าง (view-per-module + data ก้อนเดียว) วางให้พอร์ตไปเป็น Next.js ได้ในอนาคต

> ตัวเลข/ผลอันดับ/Citation เป็น **ข้อมูลจำลอง (mock)** เพื่อสาธิต UX — ในระบบจริงต่อกับ SERP API / Search Console / LLM APIs ตามสถาปัตยกรรมหน้า 7
```
