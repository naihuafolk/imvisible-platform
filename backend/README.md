# RankPilot AI — Backend (ต่อ API จริง)

Backend FastAPI ที่ **ต่อ API ของผู้ให้บริการจริง** ตาม stack ในเอกสารโครงการ (หน้า 7)
ใส่คีย์ใน `.env` แล้วรัน — endpoint จะดึงข้อมูลจริง (ไม่ใช่ mock)

---

## 🔌 ต้องต่อ API อะไร "กับใคร" (สรุปให้ครบ)

| # | ใช้ทำอะไร (โมดูล) | ต่อกับใคร (ผู้ให้บริการ) | Endpoint จริง | Auth | เอาคีย์จากไหน | ค่าใช้จ่ายโดยประมาณ |
|---|---|---|---|---|---|---|
| 1 | **อันดับ Google** (M5, M1) | **DataForSEO** (หรือ SerpAPI) | `api.dataforseo.com/v3/serp/google/organic/live/advanced` | Basic (login:password) | app.dataforseo.com › API Access | ~$0.002/คำค้น (จ่ายตามใช้) |
| 2 | **คลิก/Impression/อันดับจริง** (M5) | **Google Search Console API** | `searchconsole.googleapis.com/.../searchAnalytics/query` | OAuth2 (refresh token) | Google Cloud Console (เปิด Search Console API) | **ฟรี** |
| 3 | **ผลิต/วิเคราะห์คอนเทนต์** (M2, M6) | **Anthropic (Claude)** / OpenAI / Google Gemini | `api.anthropic.com/v1/messages` ฯลฯ | API key (header) | console.anthropic.com / platform.openai.com / aistudio.google.com | จ่ายตาม token |
| 4 | **วัด AI Citation** (M5) | **OpenAI + Google + Perplexity** | chat/completions ของแต่ละเจ้า | API key | เหมือนข้อ 3 + perplexity.ai/settings/api | จ่ายตาม token/req |
| 5 | **เผยแพร่** (M4) | **WordPress REST API** / Webflow | `เว็บคุณ/wp-json/wp/v2/posts` | Application Password (Basic) | WP: Users › Profile › Application Passwords | **ฟรี** (เว็บตัวเอง) |
| 6 | **แจ้ง Index ทันที** (M4) | **IndexNow** (Bing/Yandex) | `api.indexnow.org/indexnow` | key file บนเว็บ | สร้างคีย์เอง (สุ่ม 32 hex) | **ฟรี** |
| 7 | **Conversion/ROI** (เสริม) | **Google Analytics 4 Data API** | `analyticsdata.googleapis.com` | OAuth2 | Google Cloud | **ฟรี** |
| 8 | **แจ้งเตือน** (เสริม) | **LINE Messaging API** | `api.line.me/v2/bot/message/push` | Channel token | developers.line.biz | ฟรี (มีโควตา) |

> ⚠️ **LINE Notify ปิดบริการแล้ว (31 มี.ค. 2025)** — โค้ดนี้ใช้ **LINE Messaging API** แทน

---

## ▶️ วิธีรัน

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows (mac/linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env                               # แล้วเปิด .env ใส่คีย์จริง
uvicorn app.main:app --reload
```
เปิด **http://localhost:8000/docs** เพื่อลองยิงทุก endpoint (Swagger UI)

เช็คว่าคีย์ครบไหม (ไม่ต้องมีคีย์ก็เรียกได้):
```bash
curl http://localhost:8000/api/integrations
# → บอกว่าแต่ละ integration connected: true/false และ ready_for_measurement
```

---

## 📡 Endpoints

| Method | Path | ทำอะไร | ต้องมีคีย์ |
|---|---|---|---|
| GET  | `/health` | เช็คว่าเซิร์ฟเวอร์ทำงาน | — |
| GET  | `/api/integrations` | สถานะการเชื่อมต่อจริง (คีย์ครบไหม) | — |
| POST | `/api/mine` | M1 · ขุดคำถามจริง (Google Suggest ฟรี + PAA) | ฟรี / DataForSEO |
| POST | `/api/rank/check` | อันดับ Google ของโดเมนเรา + ติดหน้า 1 ไหม | DataForSEO |
| POST | `/api/gsc/summary` | คลิก/impression/อันดับ จริงจาก Google | GSC |
| POST | `/api/citation/sample` | AI Citation / Share of Voice (Prompt Sampling) | OpenAI/Gemini/Perplexity |
| POST | `/api/content/generate` | ผลิตบทความสูตร AEO ด้วย LLM | Claude/GPT/Gemini |
| POST | `/api/publish` | เผยแพร่ WordPress + IndexNow ping | WordPress |
| POST | `/api/auth/register` · `/api/auth/login` | สมัคร / เข้าสู่ระบบ → คืน JWT | DATABASE_URL |
| GET | `/api/auth/me` | ข้อมูลผู้ใช้ปัจจุบัน (ต้องมี Bearer token) | DATABASE_URL |
| GET / POST | `/api/projects` | โปรเจ็คของผู้ใช้ (ต้องเข้าสู่ระบบ) | DATABASE_URL |

**ตัวอย่างเช็กอันดับจริง (ตรวจสอบได้ — เสิร์ช Google เองก็เห็น):**
```bash
curl -X POST http://localhost:8000/api/rank/check \
  -H "Content-Type: application/json" \
  -d '{"keyword":"ครีมกันแดด ยี่ห้อไหนดี","domain":"abc-beautyclinic.com"}'
# → {"our_rank": 7, "on_page1": true, "top10": [...]}
```

---

## 🔗 ต่อกับแดชบอร์ด (frontend)

แดชบอร์ดตอนนี้ใช้ข้อมูลจำลองใน `assets/js/data.js` เมื่อ backend พร้อม ให้เปลี่ยนแต่ละ view
ให้ `fetch('http://localhost:8000/api/...')` แทนการอ่าน mock (backend เปิด CORS ให้แล้ว)
— บอกได้ถ้าอยากให้ผมต่อ frontend ↔ backend เป็น "Live mode" ให้เลย

---

## ⚙️ คิวงานอัตโนมัติ (Celery) — วงจรโตหมุนเอง

ตาม stack หน้า 7 (Redis + Celery) — ให้ 6 โมดูลทำงานตามตารางเวลาเอง
```bash
# ต้องมี Redis รันอยู่ (หรือใช้ docker compose ด้านล่าง)
celery -A app.worker.celery_app worker -l info      # ตัวประมวลผลงาน
celery -A app.worker.celery_app beat   -l info      # ตัวตั้งเวลา (วงจรอัตโนมัติ)
```
ตารางเวลาในตัว: เช็กอันดับทุกวัน 06:00 · Prompt Sampling ทุกจันทร์ · Freshness ทุกวัน · Learning Loop ทุกอาทิตย์
งานทั้งหมด: `discover, create_content, publish_article, measure_rank, measure_all_ranks, sample_all_citations, freshness_sweep, learning_loop`

## 🐳 ขึ้นเว็บจริงด้วยคำสั่งเดียว (Docker)

`docker-compose.yml` (ที่ root ของโปรเจ็ค) รวม **db (Postgres+pgvector) · redis · api · worker · beat · web (nginx เสิร์ฟ frontend + proxy /api)**
```bash
cd rankpilot-ai
cp backend/.env.example backend/.env     # ใส่คีย์จริง (ไม่มีก็รันได้ แต่ endpoint ที่ต้องคีย์จะแจ้ง error)
docker compose up --build
# เปิด http://localhost:8080  → เว็บจริง (frontend) + backend พร้อมใช้
```
ในหน้า "การตั้งค่า" ให้เว้น **base URL ว่างไว้** (proxy /api ให้แล้ว) เปิดโหมด Live ได้เลย

## 🔑 Auth จริง (JWT) + ฐานข้อมูล

- สมัคร/เข้าสู่ระบบได้จริง — รหัสผ่านแฮชด้วย PBKDF2 (stdlib), ออก **JWT** (PyJWT)
- ต้องตั้ง `DATABASE_URL` — ลองเร็ว ๆ ด้วย **sqlite** ก็ได้:
```bash
# Windows PowerShell
$env:DATABASE_URL="sqlite+aiosqlite:///./rankpilot.db"
pip install aiosqlite
python scripts/seed.py         # สร้างตาราง + ผู้ใช้เดโม (demo@rankpilot.ai / demo1234)
uvicorn app.main:app --reload
```
- หน้า Login ของ frontend จะเรียก `/api/auth/*` จริงถ้าต่อ backend ได้ (ต่อไม่ได้ → เข้าโหมดเดโมออฟไลน์อัตโนมัติ)
- ในหน้า "จัดการโปรเจ็ค" มีปุ่ม **"⤓ โหลดจากฐานข้อมูล"** ดึงโปรเจ็คจริงจาก DB

## 🚀 Deploy จริง (Render + Vercel + CI)

- **backend + worker + beat + redis + postgres** → [`render.yaml`](../render.yaml) (Render Blueprint — push repo แล้วกด New > Blueprint)
- **frontend (static)** → [`vercel.json`](../vercel.json) (แก้ `YOUR-BACKEND.onrender.com` เป็น URL backend จริง แล้ว `vercel --prod`)
- **CI/CD** → [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): เทสต์ frontend (jsdom) + backend (auth/DB sqlite) ทุก push · deploy อัตโนมัติเมื่อ push `main` (ตั้ง secret `RENDER_DEPLOY_HOOK`, `VERCEL_TOKEN`)

## ✅ อะไรจริง / อะไรประมาณ

- **อันดับ Google + Search Console = ของจริง ตรวจสอบเองได้ 100%** (ดึงจาก Google โดยตรง)
- **AI Citation = ของจริงแต่เป็นค่าประมาณ** (Prompt Sampling — ไม่มี API ทางการบอก citation ตรง ๆ, คำตอบ AI เปลี่ยนตามผู้ใช้/เวลา; Profound/Otterly ก็ใช้วิธีเดียวกัน)
- โค้ดนี้ **ไม่มีตัวเลข hardcode** — ทุกค่ามาจาก response จริงของ API
