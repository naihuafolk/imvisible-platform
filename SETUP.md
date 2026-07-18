# 🔌 คู่มือเชื่อมต่อ RankPilot AI (ทีละขั้น + ลิงก์)

ทุกคีย์เอาไปใส่ในไฟล์ `backend/.env` (คัดลอกจาก `backend/.env.example`)
ตัวหนา = **จำเป็น** ก่อนวัดผลจริง · ที่เหลือเป็นตัวเลือกเสริม

> 💡 เริ่มถูกสุด: **Google Suggest (ขุดคำถาม M1) ฟรีไม่ต้องมีคีย์** + **Gemini มี free tier** + **Search Console ฟรี** → เห็นระบบทำงานได้โดยแทบไม่เสียเงิน

---

## ✅ จำเป็น (5 อย่าง)

### 1) DataForSEO — อันดับ Google + ขุด People Also Ask
- สมัคร: https://app.dataforseo.com/register
- เอาคีย์ที่: https://app.dataforseo.com/api-access → คัดลอก **API Login** + **API Password** (คนละอันกับรหัสเข้าเว็บ)
- ใส่ `.env`: `DATAFORSEO_LOGIN=...` · `DATAFORSEO_PASSWORD=...`
- ราคา: จ่ายตามใช้ ~$0.0006–0.002/คำค้น (มีขั้นต่ำเติมเงินครั้งแรก)

### 2) Google Search Console — คลิก/อันดับจริงจาก Google (ฟรี)
1. ยืนยันเว็บก่อน: https://search.google.com/search-console → Add property → verify
2. สร้างโปรเจ็ค + เปิด API: https://console.cloud.google.com/apis/library/searchconsole.googleapis.com → **Enable**
3. หน้ายินยอม (ใส่อีเมลตัวเองใน Test users): https://console.cloud.google.com/apis/credentials/consent
4. สร้าง OAuth client: https://console.cloud.google.com/apis/credentials → **Create Credentials → OAuth client ID → Desktop app** → คัดลอก **Client ID** + **Client Secret**
5. ขอ refresh token (สคริปต์ช่วยให้): `cd backend && python scripts/get_gsc_token.py`
- ใส่ `.env`: `GOOGLE_CLIENT_ID=...` · `GOOGLE_CLIENT_SECRET=...` · `GOOGLE_REFRESH_TOKEN=...`
- ราคา: **ฟรี**

### 3) LLM — ผลิต/วิเคราะห์คอนเทนต์ (อย่างน้อย 1 เจ้า)
- **Anthropic (Claude)** แนะนำสำหรับงานเขียน: https://console.anthropic.com/settings/keys → `ANTHROPIC_API_KEY=...`
- **OpenAI (GPT)**: https://platform.openai.com/api-keys → `OPENAI_API_KEY=...`
- **Google Gemini** (มี free tier — เริ่มถูกสุด): https://aistudio.google.com/app/apikey → `GEMINI_API_KEY=...`
- ราคา: จ่ายตาม token (ต้องเปิด billing/เติมเครดิต ยกเว้น Gemini free tier)

### 4) AI Citation (Prompt Sampling) — วัดการถูก AI อ้างอิง
- ใช้คีย์ OpenAI/Gemini ข้อ 3 ได้เลย + เพิ่ม **Perplexity**: https://www.perplexity.ai/settings/api → `PERPLEXITY_API_KEY=...`
- ราคา: จ่ายตาม request

### 5) WordPress — เผยแพร่บทความ (ฟรี, เว็บของคุณเอง)
- ในแอดมิน WP: `https://เว็บคุณ/wp-admin/profile.php` → เลื่อนหา **Application Passwords** → ตั้งชื่อ → **Add New** → คัดลอกรหัสที่ได้
- ใส่ `.env`: `WORDPRESS_BASE_URL=https://เว็บคุณ` · `WORDPRESS_USERNAME=...` · `WORDPRESS_APP_PASSWORD=...`
- เงื่อนไข: WordPress 5.6+ และเว็บเป็น HTTPS

---

## ➕ เสริม (ตามต้องการ)

### 6) Webflow — เผยแพร่ไป Webflow
- https://webflow.com/dashboard → Site settings → **Apps & integrations** → API access → Generate token
- `.env`: `WEBFLOW_API_TOKEN=...` · `WEBFLOW_COLLECTION_ID=...`

### 7) IndexNow — แจ้ง Google/Bing ให้เก็บ index ทันที (ฟรี)
- สร้างคีย์เอง (สุ่ม 32 ตัวอักษร hex) แล้ววางไฟล์ `{key}.txt` ที่ root ของเว็บ · เอกสาร: https://www.indexnow.org/documentation
- `.env`: `INDEXNOW_KEY=...` · `INDEXNOW_HOST=เว็บคุณ.com`

### 8) Google Analytics 4 — วัด Conversion/ROI (ฟรี)
- https://analytics.google.com → Admin → Property Settings → คัดลอก **Property ID** (ตัวเลข)
- ใช้ OAuth ตัวเดียวกับข้อ 2 · `.env`: `GA4_PROPERTY_ID=...`

### 9) LINE Messaging API — แจ้งเตือน/รายงาน (ฟรี มีโควตา)
- https://developers.line.biz/console/ → Create provider → **Messaging API channel** → คัดลอก **Channel access token**
- `.env`: `LINE_CHANNEL_ACCESS_TOKEN=...` · `LINE_DEFAULT_TO=userId/groupId`
- ⚠️ LINE Notify ปิดบริการแล้ว (31 มี.ค. 2025) — ใช้ Messaging API แทน

---

## 🚀 ขึ้น cloud จริง (ถ้าจะ deploy)

1. **GitHub** — push โปรเจ็คขึ้น repo: https://github.com/new
2. **Render** (backend+worker+beat+redis+postgres): https://dashboard.render.com → **New → Blueprint** → เลือก repo (อ่าน `render.yaml` เอง) → ใส่ API keys ข้อ 1–9 ในหน้า Environment ของ service — Free tier ได้
3. **Vercel** (frontend): https://vercel.com/new → import repo (อ่าน `vercel.json` เอง) → แก้ `YOUR-BACKEND.onrender.com` ใน `vercel.json` เป็น URL ของ Render — Free
4. **CI/CD อัตโนมัติ** ทำงานเองผ่าน GitHub Actions — ถ้าจะให้ deploy อัตโนมัติ ตั้ง secret `RENDER_DEPLOY_HOOK` + `VERCEL_TOKEN` ใน repo settings

---

## 🧭 ทำตามลำดับนี้ (แนะนำ)

1. รัน backend + DB ก่อน (sqlite ก็ได้) → `python scripts/seed.py` → `uvicorn app.main:app --reload`
2. เปิด frontend → **การตั้งค่า › การเชื่อมต่อ** → ใส่ `http://localhost:8000` → เปิดโหมด Live → **ทดสอบการเชื่อมต่อ**
3. ใส่คีย์ข้อ 3 (LLM) + ข้อ 1 (DataForSEO) ก่อน → ลอง M1 "ขุดคำถามจริง" และ M5 "ตรวจอันดับสด"
4. เชื่อมข้อ 2 (Search Console) → ดูคลิก/อันดับจริง
5. เชื่อมข้อ 5 (WordPress) → ลองเผยแพร่
6. ค่อยเพิ่มข้อ 4/6/7/8/9 ตามต้องการ
