# 🎨 แผนตั้งค่า WordPress + โครงเว็บ imvisible.tech

> ทำหลังเว็บขึ้น (https://imvisible.tech แสดงหน้าติดตั้ง WordPress)

## 1️⃣ ติดตั้ง WordPress (5 นาที)
1. เปิด https://imvisible.tech → เลือกภาษา **ไทย** → Continue
2. ตั้งค่าเว็บ:
   - ชื่อเว็บ: **ImVisible**
   - คำอธิบาย: *ดันเว็บให้ติดทั้ง Google และ AI Search อัตโนมัติ*
   - Username แอดมิน + รหัสผ่าน (จดไว้!) + อีเมล
3. Login เข้า `/wp-admin`

## 2️⃣ ตั้งค่าพื้นฐาน
- **Settings → Permalinks** → เลือก **"Post name"** (`/%postname%/`) — สำคัญต่อ SEO
- **Settings → General** → ตั้ง Site Title / Tagline / เขตเวลา Bangkok
- ลบโพสต์/หน้า/ปลั๊กอินตัวอย่าง (Hello World, Sample Page)

## 3️⃣ ปลั๊กอินที่ต้องมี
- **Rank Math SEO** (ทำ Schema/Meta/Sitemap อัตโนมัติ — คู่กับ AEO ของเรา)
- **(ตัวเลือก)** WP Super Cache / LiteSpeed Cache (เร็วขึ้น)

## 4️⃣ โครงเว็บ (เมนู + หน้า)
**หน้า (Pages):**
| หน้า | slug | บทบาท |
|---|---|---|
| หน้าแรก | `/` (home) | Landing หลัก + CTA |
| บริการ | `/services` | บริการ AEO+SEO ทำอะไรบ้าง |
| ราคา/แพ็กเกจ | `/pricing` | แพ็กเกจ + ราคา |
| บทความ/บล็อก | `/blog` | รวมบทความ SEO/AEO |
| ติดต่อ | `/contact` | ฟอร์มปรึกษาฟรี |

**หมวดหมู่บล็อก (Categories) = 3 Pillar:**
- `รับทำ SEO` (บริการ) · `ความรู้ SEO` · `AI Search / AEO`

**เมนูหลัก:** หน้าแรก · บริการ · ราคา · บทความ · ติดต่อ · [ปุ่ม] เริ่มใช้ฟรี

## 5️⃣ เชื่อม WordPress → ระบบ ImVisible (auto-publish)
1. ใน WP: **Users → Profile → Application Passwords** → ตั้งชื่อ "ImVisible" → Add → **คัดลอกรหัส**
2. บนเซิร์ฟเวอร์ แก้ `backend/.env` เพิ่ม (คำสั่งเดียว — ผมจะให้ตอนถึงขั้นนี้):
   ```
   WORDPRESS_BASE_URL=https://imvisible.tech
   WORDPRESS_USERNAME=<admin>
   WORDPRESS_APP_PASSWORD=<app password>
   ```
3. restart api: `docker compose -f docker-compose.prod.yml restart api worker`
→ ระบบผลิต (Gemini) → เผยแพร่ขึ้น WordPress อัตโนมัติได้เลย

## 6️⃣ ลงคอนเทนต์ (มีให้แล้วในโฟลเดอร์ content/)
- 3 หน้า Landing (home/pricing/services) → วางเป็น **Page**
- 9 บทความ (3 Pillar) → วางเป็น **Post** ในหมวดที่ตรง + ตั้ง featured/meta ด้วย Rank Math
- ลิงก์ภายในเชื่อมกันแล้ว (บทความ → หน้าราคา/บริการ)

## 🎯 ลำดับความสำคัญ (โพสต์อะไรก่อน)
1. **หน้า home + pricing + services** (ให้เว็บดูสมบูรณ์ ขายได้)
2. **บทความ Pillar 3 (AEO)** — จุดต่าง Blue Ocean: `what-is-aeo`, `get-recommended-by-ai`
3. **บทความ Pillar 1 (บริการ)** — ปิดการขาย: `seo-price-2026`
4. ที่เหลือทยอยลง (ระบบช่วยได้)
