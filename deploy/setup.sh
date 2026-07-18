#!/usr/bin/env bash
# ImVisible — one-line setup: โหลดโค้ด + สุ่มรหัส + เตรียมไฟล์คีย์
set -e
echo ">> ติดตั้ง git/openssl..."
apt-get update -y >/dev/null 2>&1 && apt-get install -y git openssl >/dev/null 2>&1 || true

cd ~
if [ ! -d imvisible-platform ]; then
  echo ">> โหลดโค้ดจาก GitHub..."
  git clone https://github.com/naihuafolk/imvisible-platform.git
fi
cd imvisible-platform
git pull -q || true

if [ ! -f deploy/.env ]; then
  echo ">> สร้าง deploy/.env (สุ่มรหัส DB อัตโนมัติ)..."
  cat > deploy/.env <<EOF
DOMAIN=imvisible.tech
APP_DOMAIN=app.imvisible.tech
WORDPRESS_DB_PASSWORD=$(openssl rand -hex 16)
MARIADB_ROOT_PASSWORD=$(openssl rand -hex 16)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 32)
EOF
fi
[ -f backend/.env ] || cp backend/.env.example backend/.env

echo ""
echo "=================================================="
echo " ✅ เสร็จ! โหลดโค้ด + ตั้งค่าอัตโนมัติเรียบร้อย"
echo ""
echo " ต่อไปทำ 2 ขั้น:"
echo "   1) ใส่คีย์:   nano ~/imvisible-platform/backend/.env"
echo "   2) รันเว็บ:   bash ~/imvisible-platform/deploy/up.sh"
echo "=================================================="
