/* ImVisible PWA service worker — ทำให้ติดตั้งเป็นแอปได้ + ออฟไลน์ fallback
   ปลอดภัย: ไม่ยุ่งกับ /api (ข้อมูลสด) · หน้า + JS/CSS ใช้ "network-first" (ได้โค้ดใหม่เสมอหลัง deploy) ·
   cache เป็นแค่ตัวสำรองตอนเน็ตหลุด — กันปัญหา 'ปุ่มใหม่ไม่ทำงานเพราะเบราว์เซอร์ยังใช้ JS เก่าในแคช' */
const CACHE = 'imvisible-v2';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));   // ล้างแคชเวอร์ชันเก่าทั้งหมด
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;                 // ข้ามโดเมนอื่น (fonts ฯลฯ) → ปล่อยผ่าน
  if (url.pathname.startsWith('/api/') || url.pathname === '/health') return;   // ข้อมูลสด ห้าม cache

  // ทุกอย่าง (หน้า + JS/CSS/รูป): เอาจากเน็ตก่อนเสมอ → ได้ของใหม่หลัง deploy ทันที
  // เก็บลงแคชไว้เป็นสำรอง แล้วค่อย fallback เมื่อออฟไลน์
  e.respondWith((async () => {
    try {
      const res = await fetch(req);
      if (res && res.ok && (res.type === 'basic' || res.type === 'default')) {
        const cache = await caches.open(CACHE);
        cache.put(req, res.clone());
      }
      return res;
    } catch (err) {                                           // ออฟไลน์ → ใช้แคชสำรอง
      const cached = await caches.match(req);
      if (cached) return cached;
      if (req.mode === 'navigate') return (await caches.match('/index.html')) || Response.error();
      return Response.error();
    }
  })());
});
