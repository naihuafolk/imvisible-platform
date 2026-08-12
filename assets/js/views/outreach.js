/* ============================================================
   View: 🔗 คิว Backlink → Backlink Autopilot — ทำแบ็กลิงก์ 'ขาว' ให้ง่ายสุดต่อลูกค้า
   ระบบเตรียมทุกอย่างพร้อม: (1) ข้อมูลลูกค้าจัดฟอร์แมตพร้อมวาง (2) เช็กลิสต์แหล่งคุณภาพ + สถานะ
   (3) คิวขอลิงก์จากคู่แข่ง (auto ทุกศุกร์) → operator แค่ 'เปิด→วาง→submit' / 'กดส่ง'
   white-hat 100%: ไม่ auto-โพสต์ ไม่ซื้อลิงก์ ไม่ปั๊ม PBN
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;
  var STATUS = [['todo', 'ยังไม่ทำ', 'amber'], ['contacted', 'ติดต่อแล้ว', 'blue'], ['won', 'ได้ลิงก์ 🎉', 'green'], ['skip', 'ข้าม', '']];
  var TIER = { must: ['ทำก่อน · คุ้มสุด', 'green'], recommend: ['ควรทำ', 'blue'], niche: ['เฉพาะธุรกิจนี้', 'amber'] };

  function projList() { return (RP.data && RP.data.project && RP.data.project.list) || []; }
  function realProjects() {
    var list = projList();
    if (RP.isReal && RP.isReal()) list = list.filter(function (x) { return /^db/.test(String(x.id)); });
    return list;
  }
  function dbId(p) { if (!p) return null; if (typeof p._dbid === 'number') return p._dbid; var m = /^db(\d+)$/.exec(String(p.id || '')); return m ? parseInt(m[1], 10) : null; }
  function fmtn(n) { return (n == null) ? '—' : Number(n).toLocaleString(); }
  function copyText(t) { try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); } catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); } }

  /* ---------- ข้อมูลลูกค้าพร้อมวาง (NAP packet) ---------- */
  function packetText(pk) {
    var L = ['ชื่อธุรกิจ: ' + (pk.name || '')];
    if (pk.website) L.push('เว็บไซต์: ' + pk.website);
    if (pk.description_short) L.push('คำอธิบายสั้น: ' + pk.description_short);
    if (pk.description_long && pk.description_long !== pk.description_short) L.push('คำอธิบาย(ยาว): ' + pk.description_long);
    if (pk.keywords && pk.keywords.length) L.push('คำค้น/แท็ก: ' + pk.keywords.join(', '));
    if (pk.line_id) L.push('LINE: ' + pk.line_id);
    return L.join('\n');
  }
  function renderPacket(pk) {
    var todo = (pk.todo_fields || []).map(function (t) { return '<span class="badge amber">' + esc(t) + '</span>'; }).join(' ');
    return ui.card({ cls: 'mb', body:
      '<div class="row between wrap" style="gap:8px;align-items:center;margin-bottom:6px">' +
        '<div class="bb">📇 ข้อมูลลูกค้าพร้อมวาง (คัดลอกไปกรอกไดเรกทอรีได้เลย)</div>' +
        '<button class="btn btn-sm btn-primary" id="bl_pk_all">📋 คัดลอกทั้งชุด</button></div>' +
      '<pre id="bl_pk_text" style="white-space:pre-wrap;background:var(--bg,#f6f8fc);border-radius:8px;padding:10px 12px;margin:0;font-family:inherit;font-size:.92rem">' + esc(packetText(pk)) + '</pre>' +
      (todo ? '<div class="soft small" style="margin-top:8px">✍️ ช่องที่ต้องเติมเองต่อร้าน (ระบบไม่กุ): ' + todo + '</div>' : '') });
  }

  /* ---------- เช็กลิสต์ไดเรกทอรี/โซเชียล ---------- */
  function dirRow(d) {
    var t = TIER[d.tier] || TIER.recommend;
    var dof = d.dofollow ? '<span class="badge green">dofollow</span>' : '';
    var urlField = d.done
      ? '<input class="input bl-url" data-id="' + esc(d.id) + '" placeholder="วางลิงก์โปรไฟล์ที่ลงเสร็จ (ไว้ตรวจย้อน)" value="' + esc(d.submitted_url || '') + '" style="margin-top:6px;font-size:.85rem">'
      : '';
    return '<div class="list-row bl-dir" data-id="' + esc(d.id) + '" style="' + (d.done ? 'opacity:.72' : '') + '">' +
      '<div class="grow"><div class="t">' + (d.done ? '✅ ' : '') + esc(d.name) +
        ' <span class="badge">' + esc(d.region) + '</span> <span class="badge ' + t[1] + '">' + t[0] + '</span> ' + dof + '</div>' +
      '<div class="soft small">' + esc(d.note) + '</div>' + urlField + '</div>' +
      '<div style="text-align:right;white-space:nowrap;display:flex;gap:6px;align-items:flex-start">' +
        '<a class="btn btn-sm" href="' + esc(d.url) + '" target="_blank" rel="noopener">เปิด ↗</a>' +
        '<button class="btn btn-sm bl-copy" data-id="' + esc(d.id) + '">📋 ข้อมูล</button>' +
        '<label class="bl-checkl" style="display:inline-flex;align-items:center;gap:4px;font-size:.85rem;cursor:pointer">' +
          '<input type="checkbox" class="bl-done" data-id="' + esc(d.id) + '"' + (d.done ? ' checked' : '') + '> ทำแล้ว</label>' +
      '</div></div>';
  }

  function renderPlan(root, pid, plan) {
    var slot = root.querySelector('#bl_plan'); if (!slot) return;
    var pk = plan.packet || {}, dirs = plan.directories || [], pr = plan.progress || {}, oc = plan.outreach || {};
    var pct = pr.total ? Math.round((pr.done / pr.total) * 100) : 0;
    var progress =
      '<div class="card card-pad mb"><div class="row between wrap" style="gap:8px;align-items:center">' +
        '<div class="bb">🧭 ความคืบหน้าแบ็กลิงก์</div>' +
        '<div class="soft small">พื้นฐาน <b>' + (pr.done || 0) + '/' + (pr.total || 0) + '</b> · ได้ลิงก์คู่แข่ง <b>' + (oc.won || 0) + '</b> · กำลังติดต่อ <b>' + (oc.contacted || 0) + '</b></div></div>' +
      '<div style="height:10px;background:var(--bg,#eef2f8);border-radius:99px;overflow:hidden;margin-top:8px">' +
        '<div style="height:100%;width:' + pct + '%;background:linear-gradient(90deg,#1657d6,#3f86ff);border-radius:99px;transition:width .3s"></div></div>' +
      '<div class="soft small" style="margin-top:6px">ทำครบพื้นฐาน = รากฐาน authority แน่น · ที่เหลือค่อยไต่ระดับ (ชุมชน/guest/PR)</div></div>';

    var groups = { must: [], recommend: [], niche: [] };
    dirs.forEach(function (d) { (groups[d.tier] || groups.recommend).push(d); });
    function grp(key, title) {
      if (!groups[key].length) return '';
      return '<div class="soft small" style="margin:12px 0 6px;font-weight:700">' + title + '</div>' +
        ui.card({ flush: true, body: groups[key].map(dirRow).join('') });
    }
    slot.innerHTML = progress + renderPacket(pk) +
      grp('must', '🥇 พื้นฐาน (ทุกลูกค้าต้องมี — คุ้มสุด)') +
      grp('recommend', '🥈 ควรทำ (ไดเรกทอรี/โซเชียลเพิ่ม)') +
      grp('niche', '🎯 เฉพาะธุรกิจนี้');

    // คัดลอกทั้งชุด
    var pkAll = slot.querySelector('#bl_pk_all');
    if (pkAll) pkAll.onclick = function () { copyText(packetText(pk)); };
    // คัดลอกข้อมูลรายไดเรกทอรี (ชุดเดียวกัน — สะดวกตอนเปิดไดเรกทอรีนั้น)
    slot.querySelectorAll('.bl-copy').forEach(function (b) { b.onclick = function () { copyText(packetText(pk)); }; });
    // ติ๊กทำแล้ว
    slot.querySelectorAll('.bl-done').forEach(function (cb) {
      cb.onchange = function () {
        var id = cb.getAttribute('data-id'), done = cb.checked;
        cb.disabled = true;
        RP.api.backlinkDirectory(pid, { dir_id: id, done: done, url: '' }).then(function () {
          ui.toast(done ? 'ติ๊กว่าทำแล้ว ✓' : 'ยกเลิกแล้ว'); loadPlan(root, pid);
        }).catch(function (e) { cb.disabled = false; cb.checked = !done; ui.toast('บันทึกไม่ได้: ' + esc((e && e.message) || '')); });
      };
    });
    // บันทึกลิงก์โปรไฟล์ที่ลงเสร็จ (ตอน blur)
    slot.querySelectorAll('.bl-url').forEach(function (inp) {
      inp.onblur = function () {
        RP.api.backlinkDirectory(pid, { dir_id: inp.getAttribute('data-id'), done: true, url: inp.value || '' })
          .then(function () { ui.toast('บันทึกลิงก์แล้ว ✓'); }).catch(function () {});
      };
    });
  }

  function loadPlan(root, pid) {
    var slot = root.querySelector('#bl_plan'); if (!slot) return;
    if (!pid) { slot.innerHTML = ''; return; }
    slot.innerHTML = '<div class="hint" style="padding:12px">กำลังเตรียมแผนแบ็กลิงก์…</div>';
    RP.api.backlinkPlan(pid).then(function (plan) { renderPlan(root, pid, plan); })
      .catch(function (e) { slot.innerHTML = ui.card({ body: RP.noData('เตรียมแผนไม่ได้', esc((e && e.message) || '')) }); });
  }

  /* ---------- คิวขอลิงก์จากคู่แข่ง (Competitor Backlink Gap · auto) ---------- */
  function render(root, pid, d) {
    var slot = root.querySelector('#or_slot'); if (!slot) return;
    var items = (d && d.items) || [], c = (d && d.counts) || {};
    if (!items.length) {
      slot.innerHTML = ui.card({ body: RP.noData('ยังไม่มีโอกาส backlink จากคู่แข่งในคิว',
        'กด "🔄 สแกนหาโอกาสเพิ่ม" (ต้องตั้งโดเมนคู่แข่งของโปรเจ็ค + คีย์ DataForSEO Backlinks) หรือรอระบบเก็บอัตโนมัติทุกวันศุกร์') });
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
    var head = ui.pageHead({ eyebrow: 'ImVisible · Backlink Autopilot', title: '🔗 Backlink Autopilot',
      desc: 'ทำแบ็กลิงก์ "ขาว" ให้ง่ายสุด — ระบบเตรียมทุกอย่างพร้อม คุณแค่ "เปิด → วาง → submit" / "กดส่ง" · ไม่ auto-โพสต์ ไม่ซื้อลิงก์ (ปลอดภัย ไม่โดนแบน)' });
    var projs = realProjects();
    if (!projs.length) return { html: head + RP.noData('ยังไม่มีลูกค้า/โปรเจ็ค', 'สร้างโปรเจ็คก่อน'), mount: function () {} };
    var cur = (RP.data.project && RP.data.project.current) || null;
    var sel = projs.filter(function (x) { return x.id === cur; })[0] || projs[0];
    var selector = projs.length > 1
      ? '<select id="or_proj" class="input" style="max-width:320px">' + projs.map(function (p) { return '<option value="' + esc(p.id) + '"' + (p.id === sel.id ? ' selected' : '') + '>' + esc(p.name || p.domain || p.id) + '</option>'; }).join('') + '</select>' : '';
    var bar = '<div class="row wrap" style="gap:10px;align-items:center;margin-bottom:12px">' + selector +
      '<span class="soft small">เลือกลูกค้า → ระบบเตรียมแผนแบ็กลิงก์ให้เอง</span></div>';
    var queueHead = '<div class="row between wrap" style="gap:10px;align-items:center;margin:20px 0 8px">' +
      '<div class="bb">🤝 คิวขอลิงก์จากคู่แข่ง <span class="soft small">(ระบบหาให้อัตโนมัติทุกศุกร์)</span></div>' +
      '<button class="btn btn-sm btn-primary" id="or_scan">🔄 สแกนหาโอกาสเพิ่ม</button></div>';
    return { html: head + bar + '<div id="bl_plan"></div>' + queueHead + '<div id="or_slot"></div>', mount: function (root) {
      function curPid() { var dd = root.querySelector('#or_proj'); var id = dd ? dd.value : sel.id; var p = projs.filter(function (x) { return x.id === id; })[0] || sel; return { pid: dbId(p), name: p.name || p.domain }; }
      function loadAll() { var c = curPid(); loadPlan(root, c.pid); load(root, c.pid, c.name); }
      loadAll();
      var dd = root.querySelector('#or_proj'); if (dd) dd.onchange = loadAll;
      var sc = root.querySelector('#or_scan'); if (sc) sc.onclick = function () {
        var c = curPid(); sc.disabled = true; sc.textContent = 'กำลังสแกน…';
        RP.api.outreachScan(c.pid).then(function (r) { ui.toast('พบโอกาสใหม่ ' + (r.added || 0) + ' แหล่ง ✓'); load(root, c.pid, c.name); })
          .catch(function (e) { ui.toast('สแกนไม่ได้: ' + esc((e && e.message) || '')); })
          .then(function () { sc.disabled = false; sc.textContent = '🔄 สแกนหาโอกาสเพิ่ม'; });
      };
    } };
  };
})(window.RP);
