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
        '<div><label class="soft small">ต้องแชร์ก่อนปลดล็อก?</label>' +
          '<label class="row" style="gap:8px;align-items:center;margin-top:9px;cursor:pointer"><input type="checkbox" id="lmShare"> <span class="small">บังคับกดแชร์ (เพิ่ม reach)</span></label></div>' +
      '</div>' +
      '<div><label class="soft small">หัวข้อสื่อ (อยากแจกเรื่องอะไร)</label>' +
      '<input class="input" id="lmTopic" placeholder="เช่น คู่มือทำ AEO ให้ธุรกิจไทยติดอันดับบน AI" style="width:100%"></div>' +
      '<div class="row between" style="align-items:center"><span class="soft small" id="lmMsg"></span>' +
      '<button class="btn btn-primary" id="lmGo">🪄 ให้ AI สร้างสื่อ</button></div>' +
      '</div>' });

    var html = head + form + '<div id="lmList" class="mb"></div><div id="lmLeads"></div>';

    return { html: html, mount: function (root) {
      var sel = root.querySelector('#lmProj');
      function loadMagnets() {
        var pid = dbId(sel.value), box = root.querySelector('#lmList');
        if (!(pid && RP.api.enabled())) { box.innerHTML = ''; return; }
        RP.api.leadMagnets(pid).then(function (d) {
          var ms = (d && d.magnets) || [];
          if (!ms.length) { box.innerHTML = ui.card({ title: 'สื่อของคุณ', body: RP.noData('ยังไม่มีสื่อ', 'สร้างชิ้นแรกด้านบนได้เลย') }); return; }
          var rows = ms.map(function (m) {
            var url = location.origin + m.path;
            return '<div class="list-row"><div class="grow"><div class="t">' + esc(m.title) + '</div>' +
              '<div class="soft small">' + esc(m.kind) + ' · ลีด ' + (m.leads_count || 0) + (m.require_share ? ' · ต้องแชร์' : '') + '</div></div>' +
              '<a href="' + esc(url) + '" target="_blank" rel="noopener" class="btn btn-sm">เปิด ↗</a> ' +
              '<button class="btn btn-sm lm-copy" data-u="' + esc(url) + '">คัดลอกลิงก์</button></div>';
          }).join('');
          box.innerHTML = ui.card({ title: 'สื่อของคุณ', sub: ms.length + ' ชิ้น', flush: true, body: rows });
          Array.prototype.forEach.call(box.querySelectorAll('.lm-copy'), function (b) {
            b.onclick = function () { try { navigator.clipboard.writeText(b.getAttribute('data-u')); } catch (e) {} b.textContent = '✓ คัดลอกแล้ว'; setTimeout(function () { b.textContent = 'คัดลอกลิงก์'; }, 1500); };
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
          require_share: root.querySelector('#lmShare').checked
        }).then(function (m) {
          go.disabled = false; go.textContent = '🪄 ให้ AI สร้างสื่อ';
          root.querySelector('#lmTopic').value = '';
          if (msg) msg.innerHTML = 'สร้างแล้ว ✓ <a href="' + esc(location.origin + m.path) + '" target="_blank" rel="noopener">เปิดหน้าแจก ↗</a>';
          ui.toast('สร้างสื่อแจกฟรีแล้ว ✓');
          loadMagnets();
        }).catch(function (e) { go.disabled = false; go.textContent = '🪄 ให้ AI สร้างสื่อ'; ui.toast('สร้างไม่ได้: ' + esc(e.message || String(e))); });
      };
    } };
  };
})(window.RP);
