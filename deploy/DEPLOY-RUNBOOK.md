# 🚀 ImVisible — Deploy Runbook (ไล่ทำตามลำดับ)

> ทำจากบนลงล่าง · คำสั่งทั้งหมดรันบน **เซิร์ฟเวอร์ BytePlus** (SSH เข้าเครื่อง ECS-I0Mr)
> โฟลเดอร์โปรเจกต์บนเซิร์ฟเวอร์: `~/imvisible-platform`

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
