/* ============================================================
   View: เช็กลิสต์ลูกค้า (Setup / Onboarding)
   รับลูกค้าใหม่ → เห็นทันทีว่าต้องเสียบอะไรให้ครบ (ประกอบการขาย/ส่งมอบ)
   เสียบครบ = ระบบดันอันดับให้อัตโนมัติ · ดึงสถานะจริงจาก /api/projects/{id}/onboarding
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

  function srcTxt(it) {
    if (!it.source) return '';
    if (it.source === 'project') return '● คีย์ลูกค้ารายนี้';
    if (it.source === 'platform') return '● ใช้คีย์กลาง (แนะนำต่อคีย์ลูกค้าเองเพื่อข้อมูลตรง)';
    return 'ยังไม่เชื่อม';
  }
  function btnLabel(it) {
    if (it.done) return 'จัดการ';
    if (it.action === 'gsc_connect') return '🔗 เชื่อม Google';
    if (it.action === 'project_edit') return 'ไปกรอก';
    return 'ไปตั้งค่า';
  }

  function itemRow(it) {
    var ok = it.done;
    var st = srcTxt(it);
    return '<div class="list-row" style="align-items:flex-start;gap:10px;padding:11px 0;border-bottom:1px solid var(--border)">' +
      '<span style="font-weight:800;font-size:18px;line-height:1.3;color:' + (ok ? 'var(--green-600)' : 'var(--amber-600)') + '">' + (ok ? '✓' : '○') + '</span>' +
      '<div class="grow"><div class="t" style="font-weight:700">' + esc(it.label) +
        (it.required ? '' : ' <span class="chip" style="font-size:10px;padding:1px 6px">ไม่บังคับ</span>') + '</div>' +
      '<div class="soft small" style="margin:2px 0">' + esc(it.why) + '</div>' +
      (st ? '<div class="small" style="color:' + (ok ? 'var(--green-600)' : 'var(--amber-600)') + '">' + esc(st) + '</div>' : '') + '</div>' +
      '<button class="btn btn-sm ' + (ok ? '' : 'btn-primary') + ' ob-act" data-act="' + esc(it.action) + '" data-key="' + esc(it.key) + '" style="white-space:nowrap">' + btnLabel(it) + '</button>' +
      '</div>';
  }

  function checklistHtml(d) {
    var pct = d.ready_pct || 0;
    var proj = (d.items || []).filter(function (i) { return i.scope === 'project'; });
    var plat = (d.items || []).filter(function (i) { return i.scope === 'platform'; });
    var head = '<div class="card mb"><div class="card-pad">' +
      '<div class="row between wrap" style="gap:10px"><div><div class="bb" style="font-size:16px">' + esc(d.project.name || '') + '</div>' +
      '<div class="soft small">' + esc(d.project.domain || '') + '</div></div>' +
      '<span class="badge ' + (pct >= 100 ? 'green' : 'amber') + '" style="font-size:15px">พร้อม ' + pct + '%</span></div>' +
      '<div style="margin:10px 0">' + ui.bar(pct, pct >= 100 ? 'green' : '') + '</div>' +
      '<div class="soft small">เสร็จ ' + d.done + '/' + d.total + ' ขั้นตอนหลัก — ครบเมื่อไร ระบบเริ่มดันอันดับให้ลูกค้ารายนี้อัตโนมัติ (Sniper + วัดผล + เผยแพร่ + สั่ง index)</div>' +
      '</div></div>';
    var projCard = '<div class="card mb"><div class="card-pad">' +
      '<div class="bb">🧩 ต่อลูกค้ารายนี้ (ทำตอนรับงาน)</div>' +
      '<div class="soft small" style="margin:2px 0 8px">เสียบครั้งเดียวต่อ 1 ลูกค้า</div>' +
      proj.map(itemRow).join('') + '</div></div>';
    var platCard = '<div class="card mb"><div class="card-pad">' +
      '<div class="bb">⚙️ ตั้งครั้งเดียว (ใช้ได้ทุกลูกค้า)</div>' +
      '<div class="soft small" style="margin:2px 0 8px">ตั้งบนแพลตฟอร์มรอบเดียว ลูกค้าใหม่ทุกรายได้ประโยชน์เลย</div>' +
      plat.map(itemRow).join('') + '</div></div>';
    return head + projCard + platCard;
  }

  function load(root, pid) {
    var slot = root.querySelector('#ob_slot');
    if (!slot) return;
    slot.innerHTML = '<div class="hint" style="padding:14px">กำลังดึงสถานะจริงจาก backend…</div>';
    RP.api.onboarding(pid).then(function (d) {
      slot.innerHTML = checklistHtml(d);
      wire(root, pid);
    }).catch(function (e) {
      slot.innerHTML = '<div class="note-box" style="border:1px solid var(--amber-300,#fcd34d);background:var(--amber-50,#fffbeb);color:var(--amber-700,#b45309);padding:12px;border-radius:10px">' +
        'ดึงสถานะไม่ได้: ' + esc((e && e.message) || 'ต้องเปิดโหมด Live + เชื่อม backend') +
        '<div class="soft small" style="margin-top:6px">หน้านี้ทำงานเมื่อรัน backend จริง (ในลิงก์ artifact เบราว์เซอร์บล็อกการต่อ backend)</div></div>';
    });
  }

  function wire(root, pid) {
    root.querySelectorAll('.ob-act').forEach(function (b) {
      b.onclick = function () {
        var act = b.getAttribute('data-act');
        if (act === 'gsc_connect') {
          b.disabled = true; b.textContent = 'กำลังเปิด Google…';
          RP.api.gscConnect(pid).then(function (r) {
            if (r && r.url) { window.location.href = r.url; }
            else { b.disabled = false; b.textContent = '🔗 เชื่อม Google'; ui.toast('ผู้ดูแลยังไม่ได้ตั้งค่า OAuth (GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI)'); }
          }).catch(function (e) {
            b.disabled = false; b.textContent = '🔗 เชื่อม Google';
            ui.toast('เชื่อม Google ไม่ได้: ' + ((e && e.message) || 'OAuth ยังไม่พร้อม'));
          });
        } else if (act === 'project_edit') {
          location.hash = '#/projects';
        } else {
          location.hash = '#/settings';
        }
      };
    });
  }

  function copyText(t) { try { navigator.clipboard.writeText(t); ui.toast('คัดลอกโค้ดแล้ว ✓'); } catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกโค้ดแล้ว ✓'); } catch (x) {} a.remove(); } }

  /* 🏷️ Schema Pack — โค้ด JSON-LD ให้เว็บลูกค้าแปะ (เว็บลูกค้าส่วนใหญ่ schema=0 = Google/AI อ่านไม่ออก) */
  function renderPack(box, p) {
    if (!box) return;
    var types = (p.types || []).map(function (t) { return '<span class="chip">' + esc(t) + '</span>'; }).join(' ');
    var faqline = p.faq_source === 'articles'
      ? '<span class="badge green">รวม FAQPage จาก ' + (p.faq_count || 0) + ' คำถามจริงในบทความ</span>'
      : (p.faq_questions_available && p.faq_questions_available.length
        ? '<span class="badge amber">มีคำถามลูกค้า ' + p.faq_questions_available.length + ' ข้อ แต่ยังไม่มีคำตอบ → เติมคำตอบ (เขียนบทความ FAQ) เพื่อได้ FAQPage</span>'
        : '<span class="badge">ยังไม่มี FAQ — เพิ่มส่วนคำถาม-คำตอบในบทความ เพื่อได้ FAQPage (AI หยิบ 2 เท่า)</span>');
    var missing = (p.missing || []).length
      ? '<div class="soft small" style="margin-top:8px">➕ เติมข้อมูลนี้ schema แข็งขึ้น: ' + p.missing.map(esc).join(' · ') + '</div>' : '';
    box.innerHTML =
      '<div class="row wrap" style="gap:6px;margin-bottom:8px">' + types + ' ' + faqline + '</div>' +
      '<textarea class="input" id="sp_code" rows="12" readonly style="width:100%;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.82rem;line-height:1.45">' + esc(p.script || '') + '</textarea>' +
      '<div class="row wrap" style="margin-top:8px;gap:8px;align-items:center"><button class="btn btn-primary btn-sm" id="sp_copy">📋 คัดลอกโค้ด</button>' +
      '<span class="soft small">' + esc(p.note || 'แปะในส่วน <head> ของทุกหน้า') + '</span></div>' + missing;
    var cp = box.querySelector('#sp_copy'); if (cp) cp.onclick = function () { copyText(p.script || ''); };
  }

  function schemaCard(root, pid) {
    var slot = root.querySelector('#sp_slot'); if (!slot) return;
    if (!pid) { slot.innerHTML = ''; return; }
    slot.innerHTML = '<div class="card mb"><div class="card-pad">' +
      '<div class="bb">🏷️ Schema Pack — โค้ดให้เว็บลูกค้าแปะ</div>' +
      '<div class="soft small" style="margin:4px 0 10px">เว็บลูกค้าส่วนใหญ่ Google/AI “อ่านไม่ออก” เพราะไม่มี schema — สร้างโค้ด JSON-LD (ข้อมูลธุรกิจ + FAQ จริง) ให้ก็อปวางใน &lt;head&gt; → Google โชว์สวย + AI หยิบไปแนะนำ · ของฟรี ทำครั้งเดียว</div>' +
      '<button class="btn btn-primary" id="sp_gen">🏷️ สร้าง Schema Pack</button>' +
      '<div id="sp_out" style="margin-top:12px"></div></div></div>';
    var gen = slot.querySelector('#sp_gen');
    gen.onclick = function () {
      if (!(RP.api && RP.api.reachable && RP.api.reachable())) { ui.toast('เปิดโหมด Live ก่อน'); return; }
      gen.disabled = true; gen.textContent = 'กำลังสร้าง…';
      RP.api.schemaPack(pid).then(function (p) { renderPack(slot.querySelector('#sp_out'), p); })
        .catch(function (e) { ui.toast('สร้างไม่ได้: ' + esc((e && e.message) || '')); })
        .then(function () { gen.disabled = false; gen.textContent = '🏷️ สร้างใหม่'; });
    };
  }

  RP.views.setup = function () {
    var projs = realProjects();
    if (!projs.length) {
      return {
        html: RP.noData('ยังไม่มีลูกค้า/โปรเจ็ค',
          'สร้างโปรเจ็คของลูกค้าก่อน แล้วหน้านี้จะบอกทีละขั้นว่าต้องเสียบอะไรให้ครบก่อนเริ่มดันอันดับ',
          '<button class="btn btn-primary" id="ob_go">＋ สร้างโปรเจ็คลูกค้า</button>'),
        mount: function (root) {
          var g = root.querySelector('#ob_go'); if (g) g.onclick = function () { location.hash = '#/projects'; };
        }
      };
    }
    var cur = (RP.data.project && RP.data.project.current) || null;
    var sel = projs.filter(function (x) { return x.id === cur; })[0] || projs[0];
    var selector = projs.length > 1
      ? '<div class="field" style="max-width:360px;margin-bottom:12px"><span class="ico">🏢</span>' +
        '<select id="ob_proj">' + projs.map(function (p) {
          return '<option value="' + esc(p.id) + '"' + (p.id === sel.id ? ' selected' : '') + '>' + esc(p.name || p.domain || p.id) + '</option>';
        }).join('') + '</select></div>'
      : '';
    var html =
      '<div class="card mb"><div class="card-pad">' +
      '<div class="bb" style="font-size:16px">🚀 เช็กลิสต์เซ็ตอัพลูกค้า</div>' +
      '<div class="soft small" style="margin-top:4px">รับลูกค้าใหม่ → เสียบให้ครบทีละขั้น → ระบบดันอันดับให้อัตโนมัติ · สถานะดึงจริงจาก backend (ไม่ติ๊กถูกมั่ว)</div>' +
      '</div></div>' + selector +
      '<div id="ob_slot"></div><div id="sp_slot"></div>';
    return {
      html: html,
      mount: function (root) {
        var pick = sel;
        load(root, dbId(pick));
        schemaCard(root, dbId(pick));
        var dd = root.querySelector('#ob_proj');
        if (dd) dd.onchange = function () {
          var p = projs.filter(function (x) { return x.id === dd.value; })[0];
          if (p) { load(root, dbId(p)); schemaCard(root, dbId(p)); }
        };
      }
    };
  };
})(window.RP);
