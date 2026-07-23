/* ImVisible PWA — ลงทะเบียน service worker + ปุ่มติดตั้งแอปบนมือถือ/เดสก์ท็อป */
(function () {
  'use strict';
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js').catch(function () {});
    });
  }

  var standalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  if (standalone) return;                       // ติดตั้งไปแล้ว = ไม่ต้องชวนซ้ำ

  // ---- Android / Chrome / Edge : ปุ่มติดตั้งจริง ----
  var deferred = null;
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault(); deferred = e; showInstallBtn();
  });
  window.addEventListener('appinstalled', function () {
    var b = document.getElementById('pwaInstall'); if (b) b.remove();
    try { localStorage.setItem('rp-pwa-installed', '1'); } catch (e) {}
  });

  function showInstallBtn() {
    if (document.getElementById('pwaInstall')) return;
    var b = document.createElement('button');
    b.id = 'pwaInstall';
    b.type = 'button';
    b.innerHTML = '⬇️ ติดตั้งแอป';
    b.setAttribute('aria-label', 'ติดตั้ง ImVisible เป็นแอป');
    b.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:99999;padding:11px 17px;border:0;' +
      'border-radius:999px;background:linear-gradient(135deg,#3d6bff,#5b4ff0);color:#fff;font:700 14px/1 ' +
      '"Sarabun","Segoe UI",system-ui,sans-serif;box-shadow:0 8px 24px rgba(61,107,255,.42);cursor:pointer';
    b.onclick = function () {
      if (!deferred) return;
      deferred.prompt();
      deferred.userChoice.finally(function () { deferred = null; b.remove(); });
    };
    document.body.appendChild(b);
  }

  // ---- iOS Safari : ไม่มี prompt → แนะนำ 'แชร์ → เพิ่มลงหน้าจอโฮม' (โชว์ครั้งเดียว) ----
  var ua = navigator.userAgent || '';
  var isIOS = /iphone|ipad|ipod/i.test(ua);
  var isSafari = /safari/i.test(ua) && !/crios|fxios|edgios/i.test(ua);
  if (isIOS && isSafari) {
    var seen = false;
    try { seen = localStorage.getItem('rp-ios-a2hs') === '1'; } catch (e) {}
    if (!seen) {
      window.addEventListener('load', function () {
        setTimeout(function () {
          var bar = document.createElement('div');
          bar.style.cssText = 'position:fixed;left:12px;right:12px;bottom:12px;z-index:99999;padding:12px 14px;' +
            'border-radius:14px;background:#101627;color:#fff;font:500 13.5px/1.5 "Sarabun","Segoe UI",system-ui,sans-serif;' +
            'box-shadow:0 10px 30px rgba(0,0,0,.4);display:flex;gap:10px;align-items:center';
          bar.innerHTML = '<span style="font-size:20px">📲</span><span style="flex:1">ติดตั้งเป็นแอป: แตะ ' +
            '<b>แชร์</b> <span style="opacity:.8">(กล่องมีลูกศรขึ้น)</span> แล้วเลือก <b>“เพิ่มลงหน้าจอโฮม”</b></span>' +
            '<button aria-label="ปิด" style="border:0;background:transparent;color:#9aa4b8;font-size:20px;cursor:pointer">×</button>';
          bar.querySelector('button').onclick = function () {
            bar.remove();
            try { localStorage.setItem('rp-ios-a2hs', '1'); } catch (e) {}
          };
          document.body.appendChild(bar);
        }, 2500);
      });
    }
  }
})();
