/* ============================================================
   View: 🎁 สื่อแจกฟรี (Lead Magnet Studio)
   AI สร้างคอร์ส/คู่มือ/เช็คลิสต์/เทมเพลต → หน้า gate แจกแลกอีเมล/แชร์ → เก็บลีดไปตามขาย
   teaser สาธารณะช่วยติดอันดับ · เนื้อหาเต็มปลดล็อกด้วยอีเมล
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function dbProjects() {
    return ((RP.data.project && RP.data.project.list) || []).filter(function (p) { return /^db/.test(String(p.id)); });
  }
  function dbId(idStr) { var m = /^db(\d+)$/.exec(String(idStr || '')); return m ? parseInt(m[1], 10) : null; }

  RP.views.leadmagnets = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · สื่อแจกฟรี', title: '🎁 สื่อแจกฟรี (Lead Magnet)',
      desc: 'ให้ AI สร้างคอร์ส/คู่มือ/เช็คลิสต์ → แจกแลกอีเมล/แชร์ → เก็บลีดไปตามขาย · teaser สาธารณะช่วยติดอันดับด้วย' });

    if (!(RP.isReal && RP.isReal())) {
      return { html: head + ui.card({ body: RP.noData('โหมดตัวอย่าง', 'เข้าสู่ระบบบัญชีจริงเพื่อสร้างสื่อแจกฟรี') }) };
    }
    var projs = dbProjects();
    if (!projs.length) {
      return { html: head + ui.card({ body: RP.noData('ยังไม่มีโปรเจ็ค', 'สร้างโปรเจ็คก่อน แล้วค่อยสร้างสื่อแจกฟรี',
        '<button class="btn btn-primary" id="lmNew">＋ สร้างโปรเจ็ค</button>') }),
        mount: function (root) { var b = root.querySelector('#lmNew'); if (b) b.onclick = function () { RP.go('projects'); }; } };
    }
    var opts = projs.map(function (p) {
      return '<option value="' + esc(p.id) + '"' + (p.id === RP.data.project.current ? ' selected' : '') + '>' + esc(p.name || p.id) + '</option>';
    }).join('');

    var form = ui.card({ title: 'สร้างสื่อแจกฟรีใหม่', flush: true, cls: 'mb', body:
      '<div class="card-pad" style="display:flex;flex-direction:column;gap:12px">' +
      '<div><label class="soft small">สร้างในโปรเจ็ค</label>' +
      '<select class="input" id="lmProj" style="width:100%">' + opts + '</select></div>' +
      '<div class="grid" style="grid-template-columns:1fr 1fr;gap:12px">' +
        '<div><label class="soft small">ชนิดสื่อ</label><select class="input" id="lmKind" style="width:100%">' +
          '<option value="guide">📕 คู่มือ / ebook</option><option value="course">🎓 มินิคอร์ส</option>' +
          '<option value="checklist">✅ เช็คลิสต์</option><option value="template">📝 เทมเพลต</option></select></div>' +
        '<div><label class="soft small">การปลดล็อก</label>' +
          '<label class="row" style="gap:8px;align-items:center;margin-top:9px;cursor:pointer"><input type="checkbox" id="lmShare"> <span class="small">บังคับกดแชร์ก่อน <span class="soft">(ไม่แนะนำ)</span></span></label>' +
          '<div class="soft" style="font-size:11px;margin-top:4px">ค่าเริ่มต้น = <b>กรอกอีเมลอย่างเดียว</b> (ได้ลีดเยอะกว่า · การแชร์เป็นของแถม nofollow ไม่ช่วยอันดับ)</div></div>' +
      '</div>' +
      '<div><label class="soft small">ภาษาของสื่อ</label><select class="input" id="lmLang" style="width:100%">' +
        '<option value="">ตามภาษาโปรเจ็ค</option><option value="th">🇹🇭 ไทย</option><option value="en">🇬🇧 English</option><option value="both">🇹🇭+🇬🇧 ทั้งไทย &amp; อังกฤษ</option></select></div>' +
      '<div><label class="soft small">หัวข้อสื่อ (อยากแจกเรื่องอะไร)</label>' +
      '<input class="input" id="lmTopic" placeholder="เช่น คู่มือทำ AEO ให้ธุรกิจไทยติดอันดับบน AI" style="width:100%"></div>' +
      '<div class="row between" style="align-items:center"><span class="soft small" id="lmMsg"></span>' +
      '<button class="btn btn-primary" id="lmGo">🪄 ให้ AI สร้างสื่อ</button></div>' +
      '</div>' });

    var html = head + form + '<div id="lmList" class="mb"></div><div id="lmLeads"></div>';

    return { html: html, mount: function (root) {
      var sel = root.querySelector('#lmProj');
      var pollTimer = null;                              // auto-refresh ตอนมีชิ้นที่ 'กำลังสร้าง' (งานรันใน worker ไม่หายแม้ปิดหน้า)
      function managePoll(any) {
        if (any && !pollTimer) pollTimer = setInterval(loadMagnets, 6000);
        else if (!any && pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      }
      function loadMagnets() {
        var pid = dbId(sel.value), box = root.querySelector('#lmList');
        if (box && !document.body.contains(box)) { managePoll(false); return; }   // ออกจากหน้าแล้ว → หยุด poll
        if (!(pid && RP.api.enabled())) { if (box) box.innerHTML = ''; managePoll(false); return; }
        RP.api.leadMagnets(pid).then(function (d) {
          var ms = (d && d.magnets) || [];
          if (!ms.length) { box.innerHTML = ui.card({ title: 'สื่อของคุณ', body: RP.noData('ยังไม่มีสื่อ', 'สร้างชิ้นแรกด้านบนได้เลย') }); managePoll(false); return; }
          managePoll(ms.some(function (m) { return m.building; }));
          var rows = ms.map(function (m) {
            var url = location.origin + m.path;
            var right = m.failed
              ? '<span class="soft small" style="color:#c0392b">⚠️ สร้างไม่สำเร็จ</span> ' +
                '<button class="btn btn-sm lm-retry" data-id="' + m.id + '">ลองใหม่</button>'
              : m.building
              ? '<span class="soft small" style="color:var(--brand-700,#4338ca);white-space:nowrap">' + esc(m.stage || '⏳ กำลังสร้าง…') + '</span>'
              : '<a href="' + esc(url) + '" target="_blank" rel="noopener" class="btn btn-sm">เปิด ↗</a> ' +
                '<button class="btn btn-sm lm-copy" data-u="' + esc(url) + '">คัดลอกลิงก์</button> ' +
                '<button class="btn btn-sm lm-split" data-id="' + m.id + '" title="แตกแต่ละบทเป็นบทความ SEO (ร่าง)">✂️ แตกเป็นบทความ</button>';
            return '<div class="list-row"><div class="grow"><div class="t">' + esc(m.title) + '</div>' +
              '<div class="soft small">' + esc(m.kind) + ' · ' + (m.language === 'en' ? '🇬🇧 EN' : '🇹🇭 TH') + ' · ลีด ' + (m.leads_count || 0) + (m.require_share ? ' · ต้องแชร์' : '') + '</div></div>' + right + '</div>';
          }).join('');
          var _nb = ms.filter(function (m) { return m.building; }).length;
          box.innerHTML = ui.card({ title: 'สื่อของคุณ', flush: true, body: rows,
            sub: ms.length + ' ชิ้น' + (_nb ? ' · ⏳ กำลังสร้าง ' + _nb + ' (ปิดหน้าได้ ระบบทำต่อเบื้องหลังจนเสร็จ · อัปเดตให้อัตโนมัติ)' : '') });
          Array.prototype.forEach.call(box.querySelectorAll('.lm-copy'), function (b) {
            b.onclick = function () { try { navigator.clipboard.writeText(b.getAttribute('data-u')); } catch (e) {} b.textContent = '✓ คัดลอกแล้ว'; setTimeout(function () { b.textContent = 'คัดลอกลิงก์'; }, 1500); };
          });
          Array.prototype.forEach.call(box.querySelectorAll('.lm-retry'), function (b) {
            b.onclick = function () {
              b.disabled = true; b.textContent = 'กำลังสั่ง…';
              RP.api.retryLeadMagnet(b.getAttribute('data-id')).then(function () {
                ui.toast('สั่งสร้างใหม่แล้ว — สักครู่'); setTimeout(loadMagnets, 1200);
              }).catch(function () { b.disabled = false; b.textContent = 'ลองใหม่'; ui.toast('สั่งไม่สำเร็จ'); });
            };
          });
          Array.prototype.forEach.call(box.querySelectorAll('.lm-split'), function (b) {
            b.onclick = function () {
              b.disabled = true; b.textContent = 'กำลังแตก…';
              RP.api.leadMagnetToArticles(b.getAttribute('data-id')).then(function (r) {
                b.disabled = false; b.textContent = '✂️ แตกเป็นบทความ';
                var n = (r && r.created) || 0;
                ui.toast(n ? ('แตกเป็น <b>' + n + '</b> บทความ (ร่าง) แล้ว ✓ — ไปตรวจ/อนุมัติที่คิวรออนุมัติ') : 'ไม่มีบทใหม่ให้แตก (อาจแตกไปแล้ว)');
              }).catch(function (e) { b.disabled = false; b.textContent = '✂️ แตกเป็นบทความ'; ui.toast('แตกไม่สำเร็จ: ' + esc(e.message || String(e))); });
            };
          });
        }).catch(function () {});
      }
      function loadLeads() {
        var pid = dbId(sel.value), box = root.querySelector('#lmLeads');
        if (!(pid && RP.api.enabled())) { box.innerHTML = ''; return; }
        RP.api.leads(pid).then(function (d) {
          var ls = (d && d.leads) || [];
          if (!ls.length) { box.innerHTML = ui.card({ title: '📧 ลีดที่เก็บได้', body: RP.noData('ยังไม่มีลีด', 'เมื่อมีคนกรอกอีเมลรับสื่อ รายชื่อจะขึ้นที่นี่ — เอาไปตามขายบริการได้') }); return; }
          var rows = ls.map(function (l) {
            return '<div class="list-row"><span class="t nowrap">' + esc(l.email) + '</span><div class="grow"></div>' +
              '<span class="soft small">' + esc((l.at || '').slice(0, 10)) + (l.shared ? ' · แชร์แล้ว' : '') + '</span></div>';
          }).join('');
          box.innerHTML = ui.card({ title: '📧 ลีดที่เก็บได้', sub: ls.length + ' อีเมล · เอาไปตามขายบริการ', flush: true, body: rows });
        }).catch(function () {});
      }
      if (sel) sel.onchange = function () { loadMagnets(); loadLeads(); };
      loadMagnets(); loadLeads();

      var go = root.querySelector('#lmGo'), msg = root.querySelector('#lmMsg');
      if (go) go.onclick = function () {
        var pid = dbId(sel.value);
        var topic = (root.querySelector('#lmTopic').value || '').trim();
        if (!topic) { ui.toast('ใส่หัวข้อสื่อก่อน'); return; }
        if (!(pid && RP.api.enabled())) { ui.toast('เปิดโหมด Live ก่อน'); return; }
        go.disabled = true; go.textContent = 'AI กำลังสร้าง… (สักครู่)'; if (msg) msg.textContent = '';
        RP.api.createLeadMagnet(pid, {
          kind: root.querySelector('#lmKind').value,
          topic: topic,
          require_share: root.querySelector('#lmShare').checked,
          lang: root.querySelector('#lmLang').value
        }).then(function (d) {
          go.disabled = false; go.textContent = '🪄 ให้ AI สร้างสื่อ';
          root.querySelector('#lmTopic').value = '';
          var n = (d && d.count) || 1;
          if (msg) msg.innerHTML = 'เริ่มสร้าง ' + n + ' เวอร์ชัน ⏳ AI กำลังเขียน + ใส่รูปประกอบ (~2-4 นาที/ชิ้น) — จะโผล่ในลิสต์เมื่อเสร็จ';
          ui.toast('เริ่มสร้างสื่อแล้ว ✓ (' + n + ' เวอร์ชัน)');
          loadMagnets();
          setTimeout(loadMagnets, 30000); setTimeout(loadMagnets, 80000); setTimeout(loadMagnets, 140000);   // อัปเดตเมื่อสร้างเสร็จ
        }).catch(function (e) { go.disabled = false; go.textContent = '🪄 ให้ AI สร้างสื่อ'; ui.toast('สร้างไม่ได้: ' + esc(e.message || String(e))); });
      };
    } };
  };
})(window.RP);
