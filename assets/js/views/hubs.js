/* ============================================================
   Hubs — ยุบเครื่องมือที่เกี่ยวกันเป็น "แท็บเดียว" (ไม่เขียน view ใหม่ · reuse ของเดิม)
   ปรัชญา: ระบบเบทออนออโต้ (ลูกค้าใส่ลิงก์→ตั้งค่า→ปล่อยรัน) → แอดมินต้องโล่ง คุมหลายโปรเจกต์ง่าย
   tabHub(tabs) → คืน view {html, mount} ที่โหลด RP.views[<ชื่อ>] เดิมเข้าแต่ละแท็บ (lazy)
   ============================================================ */
(function (RP) {
  'use strict';

  // ใส่สไตล์แท็บครั้งเดียว (ใช้ CSS var ของแอป + fallback → ทำงานได้ทุกธีม)
  if (!document.getElementById('rp-tabhub-css')) {
    var st = document.createElement('style');
    st.id = 'rp-tabhub-css';
    st.textContent =
      '.rp-tabs{display:flex;gap:2px;flex-wrap:wrap;border-bottom:1px solid var(--line,#e5e7eb);margin-bottom:18px}' +
      '.rp-tab{appearance:none;background:transparent;border:0;border-bottom:2px solid transparent;' +
      'padding:10px 16px;font:inherit;font-size:14px;font-weight:700;color:var(--muted,#64748b);' +
      'cursor:pointer;margin-bottom:-1px;white-space:nowrap;transition:color .15s,border-color .15s}' +
      '.rp-tab:hover{color:var(--ink,#0f1830)}' +
      '.rp-tab.on{color:var(--brand,#1a56ff);border-bottom-color:var(--brand,#1a56ff)}' +
      '.rp-tabbody{min-height:120px}';
    (document.head || document.documentElement).appendChild(st);
  }

  // tabs = [{ id, label, view }] · view = ชื่อ RP.views (string) → resolve ตอนกดแท็บ
  RP.tabHub = function (tabs) {
    return function () {
      var barHtml = '<div class="rp-tabs" role="tablist">' + tabs.map(function (t, i) {
        return '<button class="rp-tab' + (i === 0 ? ' on' : '') + '" data-tab="' + t.id + '" type="button">' + t.label + '</button>';
      }).join('') + '</div><div class="rp-tabbody" id="rpTabBody"></div>';

      return {
        html: barHtml,
        mount: function (root) {
          var body = root.querySelector('#rpTabBody');
          if (!body) return;

          function load(t) {
            body.innerHTML = '';
            var f = RP.views[t.view];
            if (typeof f !== 'function') {
              body.innerHTML = '<div class="hint">ยังไม่พบเครื่องมือ: ' + RP.esc(t.view) + '</div>';
              return;
            }
            var v;
            try { v = f(); }
            catch (e) { body.innerHTML = '<div class="warn-box">โหลดไม่ได้: ' + RP.esc(e.message || String(e)) + '</div>'; return; }
            if (typeof v === 'string') { body.innerHTML = v; return; }   // เผื่อ view คืน string
            body.innerHTML = (v && v.html) || '';
            if (v && typeof v.mount === 'function') {
              try { v.mount(body); }                                     // child.mount(body) → querySelector หา element ใน body ได้
              catch (e2) { if (window.console) console.error('tab mount error:', t.view, e2); }  // ล้มแท็บเดียว ไม่ล้มทั้ง hub
            }
          }

          Array.prototype.forEach.call(root.querySelectorAll('.rp-tab'), function (b) {
            b.onclick = function () {
              Array.prototype.forEach.call(root.querySelectorAll('.rp-tab'), function (x) { x.classList.remove('on'); });
              b.classList.add('on');
              var id = b.getAttribute('data-tab');
              var t = tabs.filter(function (x) { return x.id === id; })[0];
              if (t) load(t);
            };
          });
          load(tabs[0]);
        }
      };
    };
  };

  // 🔍 หาโอกาส — คีย์เวิร์ด(ขาย) · Pantip · Growth engines
  RP.views.find = RP.tabHub([
    { id: 'prospect', label: '💼 คีย์เวิร์ด', view: 'prospect' },
    { id: 'pantip', label: '🎯 Pantip', view: 'pantip' },
    { id: 'growth', label: '🚀 Growth', view: 'growth' }
  ]);

  // 🩺 เช็ก & ลีด — เช็กเว็บ → สร้างลิงก์รายงาน → ลีด (flow เดียวจบ)
  RP.views.audit = RP.tabHub([
    { id: 'readiness', label: '🩺 เช็กสุขภาพเว็บ', view: 'readiness' },
    { id: 'reports', label: '📥 ลีดจากรายงาน', view: 'reports' }
  ]);

  // 🌐 คอนเทนต์ & ผลงาน — บล็อก · เขียนเอง · สื่อแจกฟรี · รายงานผลงาน
  RP.views.content = RP.tabHub([
    { id: 'blog', label: '🌐 บล็อก & การเข้าถึง', view: 'blog' },
    { id: 'writeblog', label: '✍️ เขียนบล็อกเอง', view: 'writeblog' },
    { id: 'leadmagnets', label: '🎁 สื่อแจกฟรี', view: 'leadmagnets' },
    { id: 'report', label: '📑 รายงานผลงาน', view: 'report' }
  ]);
})(window.RP);
