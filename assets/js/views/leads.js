/* ============================================================
   View: 📥 ลีดของลูกค้า (Leads) — กล่องลีดต่อแคมเปญ/โปรเจ็ค
   ลีดจากฟอร์มดักลูกค้าท้ายบทความ + สื่อแจกฟรี โผล่ในระบบ แยกตามลูกค้า
   เอเจนซี/ลูกค้าตามปิดการขายได้ · คัดลอกส่งลูกค้าได้ · ตัวเลขจริงจากผู้กรอกเอง ไม่กุ
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function projList() { return (RP.data && RP.data.project && RP.data.project.list) || []; }
  function realProjects() {
    var list = projList();
    if (RP.isReal && RP.isReal()) list = list.filter(function (x) { return /^db/.test(String(x.id)); });
    return list;
  }
  function dbId(p) {
    if (!p) return null;
    if (typeof p._dbid === 'number') return p._dbid;
    var m = /^db(\d+)$/.exec(String(p.id || ''));
    return m ? parseInt(m[1], 10) : null;
  }
  function fmtDate(iso) {
    if (!iso) return '—';
    var d = new Date(iso); if (isNaN(d)) return esc(iso.slice(0, 16).replace('T', ' '));
    function p(n) { return n < 10 ? '0' + n : '' + n; }
    return p(d.getDate()) + '/' + p(d.getMonth() + 1) + '/' + (d.getFullYear() + 543) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
  }
  function srcLabel(s) {
    if (/article/.test(s)) return '📝 ท้ายบทความ';
    if (/lead-magnet|magnet/.test(s)) return '🎁 สื่อแจกฟรี';
    return esc(s || '—');
  }
  function copyText(t) {
    try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); }
    catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); }
  }

  function render(root, d, pname) {
    var slot = root.querySelector('#ld_slot'); if (!slot) return;
    var leads = (d && d.leads) || [];
    if (!leads.length) {
      slot.innerHTML = ui.card({ body: RP.noData('ยังไม่มีลีด',
        'เมื่อมีคนกรอกฟอร์มดักลูกค้าท้ายบทความ หรือปลดล็อกสื่อแจกฟรีของแคมเปญนี้ ลีดจะมาโผล่ที่นี่ทันที') });
      return;
    }
    var rows = leads.map(function (l) {
      return '<tr><td class="soft small" style="white-space:nowrap">' + fmtDate(l.created_at) + '</td>' +
        '<td class="t">' + esc(l.name || '—') + '</td>' +
        '<td style="white-space:nowrap">' + (l.phone ? '<a href="tel:' + esc(l.phone) + '">' + esc(l.phone) + '</a>' : '<span class="soft">—</span>') + '</td>' +
        '<td class="soft small">' + esc(l.email || '—') + '</td>' +
        '<td class="soft small">' + srcLabel(l.source) + '</td>' +
        '<td class="soft small">' + esc(l.message || '') + '</td></tr>';
    }).join('');
    slot.innerHTML =
      '<div class="row wrap between" style="gap:8px;margin-bottom:8px;align-items:center">' +
        '<div class="bb">📥 ลีดทั้งหมด <span class="badge green">' + leads.length + '</span></div>' +
        '<button class="btn btn-sm" id="ld_copy">📋 คัดลอกลีด (ส่งลูกค้า)</button></div>' +
      ui.card({ flush: true, body: '<div class="tbl-wrap"><table class="tbl"><thead><tr>' +
        '<th>วันที่</th><th>ชื่อ</th><th>เบอร์</th><th>อีเมล</th><th>ที่มา</th><th>ข้อความ</th></tr></thead><tbody>' +
        rows + '</tbody></table></div>' });
    var cp = slot.querySelector('#ld_copy');
    if (cp) cp.onclick = function () {
      var txt = 'ลีด — ' + (pname || '') + ' (' + leads.length + ' รายชื่อ)\n' +
        leads.map(function (l) {
          return '• ' + fmtDate(l.created_at) + ' · ' + (l.name || '-') + ' · ' + (l.phone || '-') +
            (l.email ? ' · ' + l.email : '') + (l.message ? ' · "' + l.message + '"' : '');
        }).join('\n');
      copyText(txt);
    };
  }

  function load(root, pid, pname) {
    var slot = root.querySelector('#ld_slot'); if (!slot) return;
    slot.innerHTML = '<div class="hint" style="padding:14px">กำลังโหลดลีด…</div>';
    if (!(RP.api && RP.api.reachable && RP.api.reachable())) {
      slot.innerHTML = ui.card({ body: RP.noData('ต้องเปิดโหมด Live', 'กล่องลีดดึงข้อมูลจริงจาก backend — เปิด Live ในหน้าตั้งค่า') });
      return;
    }
    RP.api.projectLeads(pid).then(function (d) { render(root, d, pname); })
      .catch(function (e) { slot.innerHTML = ui.card({ body: RP.noData('โหลดลีดไม่ได้', esc((e && e.message) || '')) }); });
  }

  RP.views.leads = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · หาลูกค้า', title: '📥 ลีดของลูกค้า',
      desc: 'ลีดที่เก็บได้จากฟอร์มท้ายบทความ + สื่อแจกฟรี ของแต่ละแคมเปญ/ลูกค้า — ตามปิดการขาย + คัดลอกส่งลูกค้าได้ (ตัวเลขจริง ไม่กุ)' });
    var projs = realProjects();
    if (!projs.length) {
      return { html: head + RP.noData('ยังไม่มีลูกค้า/โปรเจ็ค', 'สร้างโปรเจ็คของลูกค้าก่อน แล้วลีดจะมาโผล่ที่นี่',
        '<button class="btn btn-primary" id="ld_go">＋ สร้างโปรเจ็ค</button>'),
        mount: function (root) { var g = root.querySelector('#ld_go'); if (g) g.onclick = function () { location.hash = '#/projects'; }; } };
    }
    var cur = (RP.data.project && RP.data.project.current) || null;
    var sel = projs.filter(function (x) { return x.id === cur; })[0] || projs[0];
    var selector = projs.length > 1
      ? '<div class="field" style="max-width:360px;margin-bottom:12px"><span class="ico">🏢</span><select id="ld_proj">' +
        projs.map(function (p) { return '<option value="' + esc(p.id) + '"' + (p.id === sel.id ? ' selected' : '') + '>' + esc(p.name || p.domain || p.id) + '</option>'; }).join('') +
        '</select></div>' : '';
    return { html: head + selector + '<div id="ld_slot"></div>', mount: function (root) {
      load(root, dbId(sel), sel.name || sel.domain);
      var dd = root.querySelector('#ld_proj');
      if (dd) dd.onchange = function () {
        var p = projs.filter(function (x) { return x.id === dd.value; })[0];
        if (p) load(root, dbId(p), p.name || p.domain);
      };
    } };
  };
})(window.RP);
