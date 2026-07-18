#!/usr/bin/env bash
# ImVisible — รันทั้งสแตก (WordPress + แพลตฟอร์ม + DB + Auto-HTTPS)
set -e
cd ~/imvisible-platform/deploy
echo ">> กำลัง build + start (ครั้งแรกใช้เวลา ~3-5 นาที)..."
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
echo ""
echo ">> สถานะ services:"
docker compose -f docker-compose.prod.yml ps
echo ""
echo "=================================================="
echo " ✅ รันแล้ว! เปิดเว็บ:"
echo "    https://imvisible.tech       (WordPress)"
echo "    https://app.imvisible.tech   (แดชบอร์ด ImVisible)"
echo " (Caddy กำลังขอ SSL — รอ 1-2 นาทีถ้า DNS เพิ่งชี้)"
echo "=================================================="
