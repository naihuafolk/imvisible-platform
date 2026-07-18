# 🚀 Deploy ImVisible บน BytePlus ECS (ทีละสเต็ป)

VM ที่มี: **4 vCPU / 16 GB / Ubuntu / Johor** — พอเหลือ ๆ
ผลลัพธ์: `imvisible.tech` (WordPress) + `app.imvisible.tech` (แดชบอร์ด) + backend + คิวงาน + **HTTPS อัตโนมัติ**

---

## ✅ สเต็ป 0 — เตรียมบน BytePlus Console (ทำก่อน)
1. **Security Group** (เมนูซ้าย → Network & Security → Security Group) → เพิ่ม inbound rules:
   - TCP **22** (SSH) — จาก IP ตัวเอง
   - TCP **80** (HTTP) — จาก `0.0.0.0/0`
   - TCP **443** (HTTPS) — จาก `0.0.0.0/0`
2. **Public IP** — ดูที่หน้า Instances ว่า VM มี Public IP ไหม (ถ้าไม่มี ผูก EIP ให้เครื่อง)
3. **Key Pair** — มีไฟล์ private key (.pem) สำหรับ SSH

## ✅ สเต็ป 1 — ชี้โดเมนมาที่ VM
ที่ Registrar ของ `imvisible.tech` → เพิ่ม DNS **A record** 3 อัน ชี้ไปที่ **Public IP ของ VM**:
```
@      A   <PUBLIC_IP>
www    A   <PUBLIC_IP>
app    A   <PUBLIC_IP>
```
รอ DNS อัปเดต ~15 นาที (เช็คด้วย `nslookup imvisible.tech`)

## ✅ สเต็ป 2 — SSH เข้า VM + ติดตั้ง Docker
```bash
ssh -i your-key.pem ubuntu@<PUBLIC_IP>

# ติดตั้ง Docker + Compose (คำสั่งเดียว)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
```

## ✅ สเต็ป 3 — เอาโปรเจ็คขึ้น VM
**วิธี A (แนะนำ): push ขึ้น GitHub แล้ว clone**
```bash
git clone https://github.com/<คุณ>/rankpilot-ai.git
cd rankpilot-ai
```
**วิธี B: อัปโหลดจากเครื่องคุณด้วย scp**
```bash
# รันบนเครื่อง Windows (git bash) — จากโฟลเดอร์แม่ของ rankpilot-ai
scp -i your-key.pem -r "rankpilot-ai" ubuntu@<PUBLIC_IP>:~/
```

## ✅ สเต็ป 4 — ตั้งค่า (คีย์ + รหัสผ่าน)
```bash
cd ~/rankpilot-ai
# 1) คีย์ API (DataForSEO/Gemini/...) — เหมือนที่ทดสอบบนเครื่อง
cp backend/.env.example backend/.env && nano backend/.env      # ใส่คีย์ (ใช้คีย์ใหม่หลังหมุน!)
# 2) รหัส DB + โดเมน ของ deploy
cp deploy/.env.example deploy/.env && nano deploy/.env         # ตั้งรหัสยาว ๆ + DOMAIN/APP_DOMAIN
```

## ✅ สเต็ป 5 — รันทั้งสแตก (คำสั่งเดียว)
```bash
cd deploy
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
docker compose -f docker-compose.prod.yml ps        # เช็คว่าทุก service ขึ้น
```
Caddy จะขอ **SSL อัตโนมัติ** ให้ทั้ง 3 โดเมน (ต้องชี้ DNS เสร็จก่อน)

## ✅ สเต็ป 6 — ตั้ง WordPress + เชื่อมเข้าระบบ
1. เปิด **https://imvisible.tech** → wizard ตั้ง WordPress (เลือกภาษาไทย, ตั้ง admin user/password)
2. ใน WP → **Users → Profile → Application Passwords** → คัดลอกรหัส
3. แก้ `backend/.env` เพิ่ม:
   ```
   WORDPRESS_BASE_URL=https://imvisible.tech
   WORDPRESS_USERNAME=<admin>
   WORDPRESS_APP_PASSWORD=<app password>
   ```
4. รีสตาร์ท api: `docker compose -f docker-compose.prod.yml restart api worker`
5. เปิด **https://app.imvisible.tech** → แดชบอร์ด ImVisible → การตั้งค่า: base URL เว้นว่าง (proxy /api ให้แล้ว) → เปิด Live

## 🎉 เสร็จ
- `imvisible.tech` = เว็บคอนเทนต์ (WordPress) ที่จะไปติดอันดับ
- `app.imvisible.tech` = แพลตฟอร์ม ImVisible (ล็อกอิน/จัดการ)
- ระบบ **ผลิต (Gemini) → เผยแพร่ขึ้น WordPress → ติดตามอันดับ (DataForSEO)** ได้ครบวงจร

## 🔧 คำสั่งดูแลที่ใช้บ่อย
```bash
docker compose -f docker-compose.prod.yml logs -f api      # ดู log
docker compose -f docker-compose.prod.yml restart api      # รีสตาร์ท
docker compose -f docker-compose.prod.yml down             # ปิด (data ยังอยู่ใน volume)
```
