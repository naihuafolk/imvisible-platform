# 🚀 ImVisible — Deploy Runbook (ไล่ทำตามลำดับ)

> ทำจากบนลงล่าง · คำสั่งทั้งหมดรันบน **เซิร์ฟเวอร์ BytePlus** (SSH เข้าเครื่อง ECS-I0Mr)
> โฟลเดอร์โปรเจกต์บนเซิร์ฟเวอร์: `~/imvisible-platform`

---

## ⚡ QUICK START — เทสกับแบรนด์ตัวเองก่อน (ยังไม่ต้องใส่ Stripe)

ระบบ **ขายเต็มรูปแบบอยู่ครบ** แต่ตอนเทสยัง**ไม่ต้องใส่คีย์ Stripe** — ปุ่มจ่ายเงินจะยัง
ใช้ไม่ได้เฉยๆ ทุกอย่างอื่น (ผลิต/เผยแพร่/วัดผล/คะแนน AEO) รันเต็ม และบัญชีคุณจะ**ไม่ติดโควตา**
เพราะตั้งเป็นแอดมิน

```bash
cd ~/imvisible-platform

# 1) ตั้งค่า infra (deploy/.env) — โดเมน + รหัสผ่าน + JWT + อีเมลแอดมิน (คุณ)
cp deploy/.env.example deploy/.env && nano deploy/.env
#    ตั้ง ADMIN_EMAILS=อีเมลคุณ  ·  JWT_SECRET ยาว ≥32  ·  รหัสผ่าน DB

# 2) ตั้งคีย์แอป (backend/.env) — อย่างน้อย: LLM 1 เจ้า + DataForSEO  (Stripe เว้นว่างไว้)
cp backend/.env.example backend/.env && nano backend/.env
#    ANTHROPIC_API_KEY หรือ GEMINI/OPENAI  ·  DATAFORSEO_LOGIN/PASSWORD  ·  ADMIN_EMAILS=อีเมลคุณ

# 3) ขึ้นทั้ง stack (postgres+redis+api+worker+beat+caddy)
docker compose -f deploy/docker-compose.prod.yml up -d --build

# 4) bootstrap แบรนด์ตัวเอง: สร้างบัญชี(business) + โปรเจ็ค imvisible.tech + อ่านเว็บ + เขียนบทความแรก
docker compose -f deploy/docker-compose.prod.yml exec api \
  python scripts/bootstrap_owner.py --email you@imvisible.tech --password 'ตั้งรหัส' \
  --url imvisible.tech --name ImVisible
#    → พิมพ์ลิงก์บล็อกที่โฮสต์ให้ (https://imvisible.tech/blog/imvisible)

# 5) เข้าแดชบอร์ดที่ https://app.imvisible.tech → ล็อกอินด้วยอีเมล/รหัสข้างบน → ดู M2/M3/M5
```

**คีย์ที่จำเป็นจริงเพื่อเทส:** LLM ≥1 เจ้า + DataForSEO เท่านั้น · ที่เหลือ (GSC/IndexNow/
ModelArk/SMTP/Stripe) เป็น **เสริม ใส่ทีหลังได้**

**ตอนพร้อมขายจริง** → ใส่ `STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET / STRIPE_PRICE_PRO /
STRIPE_PRICE_BUSINESS` + `APP_BASE_URL` ใน backend/.env แล้ว `restart api` · ตั้ง webhook ที่
Stripe ชี้มาที่ `https://app.imvisible.tech/api/billing/webhook` (ดู STEP บิลลิ่งท้ายไฟล์)

> ⚠️ **สำคัญ (แก้บั๊กแล้ว):** api + worker ต้องใช้ `JWT_SECRET` **ตัวเดียวกัน** ไม่งั้น worker
> จะถอดรหัสคีย์ลูกค้า (per-tenant) ไม่ได้ — compose/render จัดให้แล้ว อย่าตั้ง JWT_SECRET
> คนละค่าใน backend/.env กับ deploy/.env

---

## 🔑 STEP 0 — หมุนคีย์ที่หลุด (ทำก่อน/คู่ขนานได้เลย · สำคัญด้านความปลอดภัย)
คีย์ 2 ตัวเคยถูกพิมพ์ในแชต ต้องรีเซ็ตก่อนใช้งานจริง:
1. **DataForSEO** → https://app.dataforseo.com/api-access → **Reset password** → ได้รหัสใหม่
2. **Gemini** → https://aistudio.google.com/app/apikey → ลบคีย์เก่า → **Create API key** ใหม่ (ใช้ได้กับ `gemini-2.5-flash`)
3. อัปเดตลง `~/imvisible-platform/backend/.env` แล้ว restart:
   ```bash
   cd ~/imvisible-platform/deploy
   nano ../backend/.env      # แก้ DATAFORSEO_PASSWORD และ GEMINI_API_KEY
   docker compose -f docker-compose.prod.yml restart api worker
   ```

---

## 📥 STEP 1 — ดึงไฟล์ล่าสุด + ให้เว็บออนไลน์ (DNS → Caddy)

**1.1 อัปเดตไฟล์บนเซิร์ฟเวอร์** (มีการแก้ Caddyfile, compose, เพิ่ม landing + publisher)
```bash
cd ~/imvisible-platform
git pull            # ถ้า clone จาก GitHub
# ถ้าไม่ได้ใช้ git ให้ copy ไฟล์เหล่านี้ขึ้นเครื่องแทน:
#   deploy/Caddyfile, deploy/docker-compose.prod.yml, deploy/publish_content.py
#   content/landing/  (ทั้งโฟลเดอร์: index.html, og-cover.png, llms.txt, robots.txt, sitemap.xml)
```

**1.2 เช็ค DNS ว่าชี้มาที่เครื่องเราหรือยัง** (แทน 101.47.37.101 ด้วย IP จริงของ ECS)
```bash
dig +short imvisible.tech
dig +short www.imvisible.tech
dig +short app.imvisible.tech
```
> ต้องขึ้น IP ของ BytePlus ทั้ง 3 บรรทัด ถ้ายังเป็น IP อื่น (เช่น Porkbun parking) = DNS ยังไม่ครบ รออีก 10–30 นาที

**1.3 redeploy + ขอ SSL อัตโนมัติ**
```bash
cd ~/imvisible-platform/deploy
docker compose -f docker-compose.prod.yml up -d --build
sleep 8
docker compose -f docker-compose.prod.yml logs caddy 2>&1 | tail -15
```
> Caddy จะขอใบ SSL Let's Encrypt ให้เอง ถ้า log ขึ้น `certificate obtained` = ✅

**1.4 ทดสอบ**
```bash
curl -I https://imvisible.tech          # ควรได้ 200 + เห็น landing
curl -s https://imvisible.tech/llms.txt | head -3
```
เปิดเบราว์เซอร์: **https://imvisible.tech** → ต้องเห็น **landing พรีเมียมฟ้า-ขาว** (กดปุ่ม TH/EN ได้)

---

## 🎨 STEP 2 — ติดตั้ง WordPress (5 นาที)
> WordPress อยู่หลัง Caddy แล้ว เข้าหน้าติดตั้งผ่าน `/wp-admin`
1. เปิด **https://imvisible.tech/wp-admin/** → เลือกภาษา **ไทย**
2. ตั้งค่า: Site Title = **ImVisible** · Username แอดมิน + รหัสผ่าน (จดไว้!) + อีเมล
3. Login เข้า Dashboard

## ⚙️ STEP 3 — ตั้งค่า WP + ปลั๊กอิน
1. **Settings → Permalinks → "Post name"** (`/%postname%/`) — สำคัญต่อ SEO
2. **Settings → General** → เขตเวลา Bangkok · (ปล่อยหน้าแรกไว้ — หน้าแรกจริงคือ landing static แล้ว)
3. ลง 2 ปลั๊กอิน (Plugins → Add New):
   - **Rank Math SEO** → รัน Setup Wizard → เปิด sitemap + เชื่อม Search Console
   - **Polylang** → เพิ่มภาษา **ไทย (หลัก)** + **English** (ทำ hreflang TH/EN อัตโนมัติ)
4. (Rank Math → General → Edit robots.txt) วางไว้ให้ AI bot เข้าอ่านได้ — ก็อปจาก `content/landing/robots.txt`

## 🔗 STEP 4 — เชื่อม WordPress → ระบบ (Application Password)
1. WP: **Users → Profile → Application Passwords** → ตั้งชื่อ `ImVisible` → **Add** → **คัดลอกรหัส** (เว้นวรรคได้)
2. บนเซิร์ฟเวอร์ แก้ `backend/.env` เพิ่ม:
   ```
   WORDPRESS_BASE_URL=https://imvisible.tech
   WORDPRESS_USERNAME=<admin username>
   WORDPRESS_APP_PASSWORD=<app password ที่คัดลอกมา>
   ```
3. `docker compose -f docker-compose.prod.yml restart api worker`

## 📝 STEP 5 — ลงคอนเทนต์ 11 ชิ้นอัตโนมัติ
```bash
cd ~/imvisible-platform/deploy
python3 publish_content.py --dry-run     # ดูก่อนว่าจะลงอะไรบ้าง
python3 publish_content.py               # ลงจริง (2 หน้า + 9 บทความ 3 Pillar)
```
> สคริปต์อ่านค่า WordPress จาก `backend/.env` เอง · ถ้ามี slug อยู่แล้วจะอัปเดต (ไม่ซ้ำ)

## 🧭 STEP 6 — เมนู + ตรวจหน้าเว็บ
1. WP: **Appearance → Menus** → สร้างเมนู: หน้าแรก(imvisible.tech) · บริการ · ราคา · บทความ · ติดต่อ
2. เช็ก: บทความโผล่ที่ `imvisible.tech/what-is-aeo/` ฯลฯ · หน้าแรกยังเป็น landing พรีเมียม ✅

## 🔍 STEP 7 — ส่งเข้า Google (Search Console)
1. https://search.google.com/search-console → Add property `imvisible.tech` → ยืนยัน (Rank Math ช่วยได้)
2. **Sitemaps** → ส่ง `https://imvisible.tech/sitemap_index.xml` (Rank Math สร้างให้ รวมทุกบทความ)
3. **URL Inspection** → ขอ index หน้าแรก + บทความ Pillar สำคัญก่อน (`what-is-aeo`, `seo-price-2026`)

---

## 🌱 STEP 8 — ปั้น E-E-A-T แบบของจริง (ต่อเนื่อง · ไม่ปั้นปลอม)
คะแนน SEO/AEO จะไต่จาก 85 → 95+ เมื่อมี "ของจริง":
- [ ] ลูกค้าราย/ทดลองจริง → เก็บ **รีวิวจริง** → เพิ่ม Review + AggregateRating schema
- [ ] **กรณีศึกษา** จากผลจริงบนแดชบอร์ด (อันดับขยับ / AI citation ที่วัดได้)
- [ ] หน้า **About / ทีม** + Person schema (ตัวตนจริง)
- [ ] เปิดโซเชียลแบรนด์ (LinkedIn/FB/X) → เติม `sameAs` ใน Organization schema
- [ ] ให้ระบบผลิตคอนเทนต์ต่อเนื่อง (Freshness) → authority สะสมเอง

> จุดยืน: **ไม่โกง** — ทุกตัวเลข/รีวิว/เคส ต้องมาจากของจริงเท่านั้น (นี่คือจุดขายของแบรนด์)

---

## 🏢 STEP 9 — Managed Hosting (ลูกค้าใส่แค่ลิงก์ = เราโฮสต์บล็อกให้)

> ฟีเจอร์ครบวงจร: ลูกค้าใส่ URL → ระบบเขียน AEO + **เผยแพร่เอง** ที่ `imvisible.tech/blog/{slug}`
> (อัปเกรดเป็น `blog.ลูกค้า.com` ได้ด้วย CNAME 1 บรรทัด) — โค้ดใหม่: `backend/app/public.py`, `urls.py`, `migrate.py`, publish routing ใน `tasks.py`, `deploy/Caddyfile`

**9.1 ดึงโค้ด + validate Caddy ก่อน (สำคัญ — กัน config พังทั้งเว็บ)**
```bash
cd ~/imvisible-platform && git pull
cd deploy
# ตรวจ Caddyfile ว่าถูกต้องก่อน reload (ถ้าไม่ผ่าน อย่าเพิ่ง up)
docker compose -f docker-compose.prod.yml exec caddy caddy validate --config /etc/caddy/Caddyfile \
  || echo "!! Caddyfile ไม่ผ่าน — คอมเมนต์บล็อก https:// ท้ายไฟล์ออกก่อน แล้ว validate ใหม่"
```

**9.2 rebuild backend (api/worker/beat) + โหลด Caddy config ใหม่**
```bash
docker compose -f docker-compose.prod.yml up -d --build api worker beat
# สำคัญ: ใช้ restart (ไม่ใช่ reload) — 'caddy reload' ผ่าน exec บางที adapt สำเร็จแต่ไม่ apply จริง
docker compose -f docker-compose.prod.yml restart caddy
sleep 6
# ตรวจว่า api ขึ้นตาราง/คอลัมน์ใหม่ให้แล้ว (startup รัน migrate อัตโนมัติ)
docker compose -f docker-compose.prod.yml logs api 2>&1 | tail -20
# ยืนยัน Caddy โหลด /blog/* แล้ว (ต้องเห็น 'handle /blog/*' หรือ HTML ของ renderer)
docker compose -f docker-compose.prod.yml exec caddy grep -n blog /etc/caddy/Caddyfile
curl -s https://$DOMAIN/blog/<slug> | head -c 200 ; echo
```
> ⚠️ ถ้า `curl` ยังได้หน้า WordPress (เห็น `Rank Math`) แทน renderer เรา → `docker compose -f docker-compose.prod.yml restart caddy` อีกครั้งแล้วเทสซ้ำ (reload ไม่ apply เป็น quirk ที่เจอจริง)

**9.3 รัน migration ซ้ำแบบ manual (belt-and-suspenders — idempotent รันซ้ำได้)**
```bash
docker compose -f docker-compose.prod.yml exec api python -m app.migrate
# ควรเห็น OK ... + backfill projects/articles slug + "migration done ✓"
```

**9.4 ทดสอบ end-to-end (path-based — ใช้ได้ทันที ไม่ต้องตั้ง DNS)**
```bash
# ดู slug ของโปรเจ็คแรกจาก DB
docker compose -f docker-compose.prod.yml exec db psql -U imvisible -d imvisible -c \
  "select id,slug,publish_mode,custom_domain from projects order by id;"
# เปิดบล็อก (แทน {slug})
curl -sI https://imvisible.tech/blog/{slug}            # 200 = หน้าอินเด็กซ์บล็อก
curl -s  https://imvisible.tech/blog/{slug}/sitemap.xml | head -3
curl -s  https://imvisible.tech/blog/{slug}/llms.txt   | head -5
```
> หรือทำผ่านแดชบอร์ด: สร้างโปรเจ็คใหม่ → จะมี modal โชว์ลิงก์บล็อกที่เราโฮสต์ให้ → กด "ผลิตเดี๋ยวนี้" (ถ้าโหมด auto จะเผยแพร่ทันที · โหมด approve เก็บเป็นร่างก่อน)

**9.5 (ออปชัน) ให้บล็อกอยู่บนโดเมนลูกค้า — 2 แบบ**

*แบบ A — ซับโดเมนของเรา `{slug}.imvisible.tech` (ตั้ง DNS ฝั่งเราครั้งเดียว):*
```
ที่ DNS ของ imvisible.tech เพิ่ม wildcard:
   ชนิด A   ชื่อ *   ค่า <IP ของ ECS>      # *.imvisible.tech → เครื่องเรา
```
Caddy จะออก HTTPS ให้แต่ละซับโดเมนอัตโนมัติ (on-demand · ผ่าน /api/tls/check)

*แบบ B — โดเมนลูกค้าเอง `blog.ลูกค้า.com` (ลูกค้าตั้ง CNAME):*
1. ในแดชบอร์ด/หรือ API: ตั้ง custom_domain ให้โปรเจ็ค
   ```bash
   # ผ่าน API (ต้องมี token ลูกค้า):
   curl -X PUT https://app.imvisible.tech/api/projects/{id}/publish \
     -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
     -d '{"publish_mode":"managed","custom_domain":"blog.abccoffee.com"}'
   ```
2. ลูกค้าเพิ่ม DNS ฝั่งเขา **1 บรรทัด**:  `CNAME  blog  →  cname.imvisible.tech`
   (ให้ `cname.imvisible.tech` เป็น CNAME/A ชี้มาที่ IP ของเรา)
3. เปิด `https://blog.abccoffee.com` → Caddy ขอ SSL ให้เอง (เพราะ /api/tls/check เห็น custom_domain นี้แล้ว) → เสิร์ฟบล็อกที่ root

**9.6 หมายเหตุความปลอดภัย**
- `/api/tls/check` ปล่อยออกใบ SSL **เฉพาะ** ซับโดเมนที่มี slug จริง หรือ custom_domain ที่ลงทะเบียนไว้ (กันคนสุ่มยิงขอ cert)
- publish_mode: `managed` (เราโฮสต์) · `wordpress` (ขึ้นเว็บลูกค้า — STEP 4 creds) · `none` (เก็บใน DB เฉย ๆ)

---

## 💳 STEP 10 — เปิดระบบเก็บเงิน Stripe (ทำตอนพร้อมขายจริงเท่านั้น)

ก่อนหน้านี้ระบบรันได้เต็มโดยไม่มี Stripe (ปุ่มจ่ายเงินขึ้น "ยังไม่พร้อม") พอพร้อมขาย:

**10.1 ที่ Stripe Dashboard** (https://dashboard.stripe.com)
1. สร้าง **Product + Price** 2 ตัว (Pro / Business แบบ recurring รายเดือน) → ได้ `price_...` 2 อัน
2. Developers → **API keys** → คัดลอก **Secret key** (`sk_live_...`)
3. Developers → **Webhooks** → Add endpoint:
   - URL: `https://app.imvisible.tech/api/billing/webhook`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
   - → คัดลอก **Signing secret** (`whsec_...`)

**10.2 ใส่คีย์ใน `backend/.env`** แล้ว restart
```bash
nano ~/imvisible-platform/backend/.env
#   STRIPE_SECRET_KEY=sk_live_...
#   STRIPE_WEBHOOK_SECRET=whsec_...
#   STRIPE_PRICE_PRO=price_...
#   STRIPE_PRICE_BUSINESS=price_...
#   APP_BASE_URL=https://app.imvisible.tech     (ให้ลิงก์กลับหลังจ่ายเงินถูก)
docker compose -f deploy/docker-compose.prod.yml restart api
```

**10.3 ทดสอบ**
- เข้าแดชบอร์ด → หน้า "แพ็กเกจ" (billing) → กดอัปเกรด → ต้องเด้งไป Stripe Checkout
- จ่ายด้วยบัตรทดสอบ `4242 4242 4242 4242` (โหมด test) → กลับมาเห็นแพ็กเกจเปลี่ยนเป็น Pro/Business
- ลายเซ็น webhook ตรวจจริง (HMAC) — event ปลอมจะถูกปฏิเสธ 400

> โควตา: free = 1 โปรเจ็ค/4 บทความต่อเดือน · pro = 3/60 · business = 10/200
> (ปรับได้ที่ `backend/app/plans.py`) · อีเมลใน `ADMIN_EMAILS` = business ฟรี (สำหรับทีม/เทส)
