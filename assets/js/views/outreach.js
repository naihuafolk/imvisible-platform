/* ============================================================
   View: 🔗 คิว Backlink (Outreach) — แหล่งที่ควรไปขอลิงก์ ต่อแคมเปญ/ลูกค้า
   ระบบเก็บอัตโนมัติรายสัปดาห์ (Competitor Backlink Gap จริง) → คนตามสถานะ + กดร่างข้อความส่งเอง
   white-hat: ไม่ auto-โพสต์ ไม่ซื้อลิงก์ · ตัวเลขจริงจาก DataForSEO
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;
  var STATUS = [['todo', 'ยังไม่ทำ', 'amber'], ['contacted', 'ติดต่อแล้ว', 'blue'], ['won', 'ได้ลิงก์ 🎉', 'green'], ['skip', 'ข้าม', '']];

  function projList() { return (RP.data && RP.data.project && RP.data.project.list) || []; }
  function realProjects() {
    var list = projList();
    if (RP.isReal && RP.isReal()) list = list.filter(function (x) { return /^db/.test(String(x.id)); });
    return list;
  }
  function dbId(p) { if (!p) return null; if (typeof p._dbid === 'number') return p._dbid; var m = /^db(\d+)$/.exec(String(p.id || '')); return m ? parseInt(m[1], 10) : null; }
  function fmtn(n) { return (n == null) ? '—' : Number(n).toLocaleString(); }
  function copyText(t) { try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); } catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); } }
  function stLabel(s) { for (var i = 0; i < STATUS.length; i++) if (STATUS[i][0] === s) return STATUS[i]; return ['todo', s, 'amber']; }

  function render(root, pid, d) {
    var slot = root.querySelector('#or_slot'); if (!slot) return;
    var items = (d && d.items) || [], c = (d && d.counts) || {};
    if (!items.length) {
      slot.innerHTML = ui.card({ body: RP.noData('ยังไม่มีโอกาส backlink ในคิว',
        'กด "🔄 สแกนหาโอกาสเพิ่ม" (ต้องตั้งโดเมนคู่แข่งของโปรเจ็ค + มีคีย์ DataForSEO Backlinks) หรือรอระบบเก็บอัตโนมัติทุกวันศุกร์') });
      return;
    }
    var rows = items.map(function (o) {
      var opts = STATUS.map(function (st) { return '<option value="' + st[0] + '"' + (o.status === st[0] ? ' selected' : '') + '>' + st[1] + '</option>'; }).join('');
      return '<tr>' +
        '<td><a href="https://' + esc(o.source_domain) + '" target="_blank" rel="noopener" class="t">' + esc(o.source_domain) + '</a></td>' +
        '<td class="right" style="font-variant-numeric:tabular-nums">' + fmtn(o.authority) + '</td>' +
        '<td class="soft small">' + esc(o.reason) + '</td>' +
        '<td><select class="input or-st" data-id="' + o.id + '" style="padding:4px 6px">' + opts + '</select></td>' +
        '<td><button class="btn btn-sm or-draft" data-dom="' + esc(o.source_domain) + '">✍️ ร่างข้อความ</button></td>' +
        '</tr>';
    }).join('');
    slot.innerHTML =
      '<div class="row wrap" style="gap:8px;margin-bottom:8px">' +
        '<span class="badge amber">ยังไม่ทำ ' + (c.todo || 0) + '</span>' +
        '<span class="badge blue">ติดต่อแล้ว ' + (c.contacted || 0) + '</span>' +
        '<span class="badge green">ได้ลิงก์ ' + (c.won || 0) + '</span>' +
        '<span class="soft small" style="margin-left:auto">รวม ' + items.length + ' แหล่ง</span></div>' +
      ui.card({ flush: true, body: '<div class="tbl-wrap"><table class="tbl"><thead><tr>' +
        '<th>เว็บที่ควรขอลิงก์</th><th class="right">backlinks</th><th>เหตุผล</th><th>สถานะ</th><th>ร่างส่ง</th></tr></thead><tbody>' +
        rows + '</tbody></table></div>' }) +
      '<div id="or_draft" style="margin-top:10px"></div>';

    slot.querySelectorAll('.or-st').forEach(function (sel) {
      sel.onchange = function () {
        RP.api.outreachUpdate(sel.getAttribute('data-id'), { status: sel.value })
          .then(function () { ui.toast('อัปเดตสถานะแล้ว ✓'); }).catch(function (e) { ui.toast('อัปเดตไม่สำเร็จ: ' + esc((e && e.message) || '')); });
      };
    });
    slot.querySelectorAll('.or-draft').forEach(function (b) {
      b.onclick = function () {
        var dom = b.getAttribute('data-dom');
        b.disabled = true; b.textContent = 'กำลังร่าง…';
        RP.api.backlinkOutreach(pid, { url: 'https://' + dom, title: dom, kind: 'resource' }).then(function (r) {
          var txt = r.draft || r.text || r.message || r.email || (typeof r === 'string' ? r : JSON.stringify(r));
          var box = root.querySelector('#or_draft');
          box.innerHTML = ui.card({ body: '<div class="bb" style="margin-bottom:6px">✍️ ร่างข้อความถึง <b>' + esc(dom) + '</b> <span class="soft small">(ปรับให้เป็นธรรมชาติก่อนส่ง · คนส่งเอง)</span></div>' +
            '<textarea class="input" id="or_dtext" rows="8" style="width:100%">' + esc(txt) + '</textarea>' +
            '<div class="row" style="margin-top:8px"><button class="btn btn-sm" id="or_copy">📋 คัดลอก</button></div>' });
          var cp = box.querySelector('#or_copy'); if (cp) cp.onclick = function () { copyText(box.querySelector('#or_dtext').value); };
          box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }).catch(function (e) { ui.toast('ร่างไม่ได้: ' + esc((e && e.message) || '')); })
          .then(function () { b.disabled = false; b.textContent = '✍️ ร่างข้อความ'; });
      };
    });
  }

  function load(root, pid, pname) {
    var slot = root.querySelector('#or_slot'); if (!slot) return;
    slot.innerHTML = '<div class="hint" style="padding:14px">กำลังโหลดคิว…</div>';
    if (!(RP.api && RP.api.reachable && RP.api.reachable())) { slot.innerHTML = ui.card({ body: RP.noData('ต้องเปิดโหมด Live', 'คิว backlink ดึงข้อมูลจริงจาก backend — เปิด Live ในหน้าตั้งค่า') }); return; }
    RP.api.outreachList(pid).then(function (d) { render(root, pid, d); })
      .catch(function (e) { slot.innerHTML = ui.card({ body: RP.noData('โหลดคิวไม่ได้', esc((e && e.message) || '')) }); });
  }

  RP.views.outreach = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · หาลูกค้า', title: '🔗 คิว Backlink (Outreach)',
      desc: 'แหล่งที่ควรไปขอลิงก์ ต่อแคมเปญ — ระบบเก็บอัตโนมัติทุกศุกร์จาก Competitor Backlink Gap จริง · กดร่างข้อความ+ตามสถานะ · white-hat (คนส่งเอง ไม่ซื้อ ไม่สแปม)' });
    var projs = realProjects();
    if (!projs.length) return { html: head + RP.noData('ยังไม่มีลูกค้า/โปรเจ็ค', 'สร้างโปรเจ็คก่อน'), mount: function () {} };
    var cur = (RP.data.project && RP.data.project.current) || null;
    var sel = projs.filter(function (x) { return x.id === cur; })[0] || projs[0];
    var selector = projs.length > 1
      ? '<select id="or_proj" class="input" style="max-width:320px">' + projs.map(function (p) { return '<option value="' + esc(p.id) + '"' + (p.id === sel.id ? ' selected' : '') + '>' + esc(p.name || p.domain || p.id) + '</option>'; }).join('') + '</select>' : '';
    var bar = '<div class="row wrap" style="gap:10px;align-items:center;margin-bottom:12px">' + selector +
      '<button class="btn btn-primary" id="or_scan">🔄 สแกนหาโอกาสเพิ่ม</button>' +
      '<span class="soft small">ต้องตั้งโดเมนคู่แข่ง (ตั้งค่าโปรเจ็ค) + คีย์ DataForSEO Backlinks</span></div>';
    return { html: head + bar + '<div id="or_slot"></div>', mount: function (root) {
      function curPid() { var dd = root.querySelector('#or_proj'); var id = dd ? dd.value : sel.id; var p = projs.filter(function (x) { return x.id === id; })[0] || sel; return { pid: dbId(p), name: p.name || p.domain }; }
      var c0 = curPid(); load(root, c0.pid, c0.name);
      var dd = root.querySelector('#or_proj'); if (dd) dd.onchange = function () { var c = curPid(); load(root, c.pid, c.name); };
      var sc = root.querySelector('#or_scan'); if (sc) sc.onclick = function () {
        var c = curPid(); sc.disabled = true; sc.textContent = 'กำลังสแกน…';
        RP.api.outreachScan(c.pid).then(function (r) { ui.toast('พบโอกาสใหม่ ' + (r.added || 0) + ' แหล่ง ✓'); load(root, c.pid, c.name); })
          .catch(function (e) { ui.toast('สแกนไม่ได้: ' + esc((e && e.message) || '')); })
          .then(function () { sc.disabled = false; sc.textContent = '🔄 สแกนหาโอกาสเพิ่ม'; });
      };
    } };
  };
})(window.RP);
