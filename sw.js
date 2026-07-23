/* ImVisible PWA service worker — ทำให้ติดตั้งเป็นแอปได้ + เปิดไวขึ้น
   ปลอดภัย: ไม่ยุ่งกับ /api (ข้อมูลสด) · หน้าใช้ network-first (ได้ของใหม่เสมอ) · asset ใช้ stale-while-revalidate */
const CACHE = 'imvisible-v1';

self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;                 // ข้ามโดเมนอื่น (fonts ฯลฯ) → ปล่อยผ่าน
  if (url.pathname.startsWith('/api/') || url.pathname === '/health') return;   // ข้อมูลสด ห้าม cache

  if (req.mode === 'navigate') {                              // เปิดหน้า → เอาของใหม่ก่อน, ออฟไลน์ค่อย fallback
    e.respondWith((async () => {
      try {
        return await fetch(req);
      } catch (err) {
        return (await caches.match(req)) || (await caches.match('/index.html')) || Response.error();
      }
    })());
    return;
  }

  e.respondWith((async () => {                                // asset → คืน cache ทันที + อัปเดตเบื้องหลัง
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req);
    const fetching = fetch(req).then((res) => {
      if (res && res.ok && (res.type === 'basic' || res.type === 'default')) cache.put(req, res.clone());
      return res;
    }).catch(() => null);
    return cached || (await fetching) || Response.error();
  })());
});
