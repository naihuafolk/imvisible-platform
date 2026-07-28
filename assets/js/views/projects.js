/* ============================================================
   View: จัดการโปรเจ็ค (Multi-Project) + สร้างโปรเจ็คใหม่ (Wizard)
   รองรับหลายโปรเจ็คตามแพ็กเกจ (Starter 1 / Pro 3 / Enterprise ไม่จำกัด)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;
  var PACKS = [10, 30, 50];   // แพ็กคีย์เวิร์ดต่อลูกค้า (ต้องตรงกับ plans.KEYWORD_PACKS ฝั่ง backend)
  var packMap = {};           // pid -> {pack, used} เติมจาก /api/projects/overview
  function normPack(n) { n = parseInt(n, 10) || 50; for (var i = 0; i < PACKS.length; i++) { if (n <= PACKS[i]) return PACKS[i]; } return PACKS[PACKS.length - 1]; }

  function healthDots(h) {
    var items = [['GSC', h.gsc], ['SERP', h.serp], ['AI Citation', h.ai], ['เผยแพร่', h.publish]];
    return '<div class="row wrap gap-s" style="margin:10px 0">' + items.map(function (x) {
      return '<span class="chip" style="gap:6px"><span style="width:8px;height:8px;border-radius:50%;background:' +
        (x[1] ? 'var(--green-500)' : 'var(--border)') + '"></span>' + esc(x[0]) + '</span>';
    }).join('') + '</div>';
  }

  /* บัญชีจริง: สถานะการเชื่อมต่อยังไม่ได้วัดในหน้านี้ → ห้ามโชว์ไฟเขียวสมมติ */
  function healthRow(h) {
    if (!RP.isReal()) return healthDots(h);
    return '<div class="soft small" style="margin:10px 0">🔌 สถานะการเชื่อมต่อ (GSC · SERP · AI Citation · เผยแพร่): ' +
      '<b>ยังไม่ได้ตรวจสอบในหน้านี้</b> — ดูสถานะจริงได้ที่ ⚙️ การตั้งค่า › การเชื่อมต่อ</div>';
  }

  /* บัญชีจริง: ตัวเลขที่ระบบยังไม่ได้เก็บ → แสดงขีด ไม่แสดงเลขสมมติ */
  function realNum(v) {
    if (!RP.isReal()) return v;
    return '<span class="soft" title="ยังไม่มีข้อมูลจริง">—</span>';
  }

  function projectCard(p) {
    var real = RP.isReal();
    var numId = String(p.id).replace(/^db/, '');
    var setup = p.status === 'setup';
    var connected = (p.health.gsc ? 1 : 0) + (p.health.serp ? 1 : 0) + (p.health.ai ? 1 : 0) + (p.health.publish ? 1 : 0);
    return '<div class="card card-pad">' +
      '<div class="row between wrap" style="gap:8px;align-items:flex-start">' +
      '<div style="min-width:0"><div class="bb" style="font-size:16px">' + esc(p.name) + '</div>' +
      '<div class="soft small" style="margin-top:2px">🌐 ' + esc(p.domain) + ' · ' + esc(p.country) +
      ' · ' + (p.mode === 'auto' ? 'Full-Auto' : 'Human Approve') + ' · Freshness ' + esc(p.freshnessDays) + ' วัน</div></div>' +
      '<div class="row gap-s wrap" style="justify-content:flex-end;gap:6px">' +
      '<span class="proj-pack" data-pid="' + esc(numId) + '"></span>' +
      '<span class="proj-status" data-pid="' + esc(numId) + '">' + (real ? '<span class="soft small">…</span>' : (p.plan ? ui.badge('แพ็กเกจ ' + p.plan, 'purple') : '')) + '</span>' +
      '</div></div>' +
      (!real && setup ? '<div class="hint" style="margin-top:10px">⚠️ ตั้งค่ายังไม่ครบ (' + connected + '/4) — เชื่อม AI Citation + ปลายทางเผยแพร่ให้ครบก่อนเริ่มวัดผล</div>' : '') +
      (real ? '' : healthRow(p.health)) +
      '<div class="soft small proj-nums" data-pid="' + esc(numId) + '" style="margin:12px 0">' + (real ? 'กำลังโหลดข้อมูล…' : '') + '</div>' +
      (real ? '<div class="soft small" style="margin:0 0 12px">🔌 สถานะการเชื่อมต่อดูที่ ⚙️ ตั้งค่า › การเชื่อมต่อ · ผลงาน/การทำงานสดดูที่ 📊 แดชบอร์ด</div>' : '') +
      '<div class="row gap-s wrap" style="align-items:center">' +
      '<button class="btn btn-primary btn-sm open-dash" data-id="' + esc(p.id) + '">📊 เปิดรายงาน</button>' +
      '<button class="btn btn-sm add-kw" data-id="' + esc(p.id) + '" data-name="' + esc(p.name) + '">＋ คีย์เวิร์ด</button>' +
      '<button class="btn btn-sm chg-pack" data-id="' + esc(p.id) + '" data-name="' + esc(p.name) + '">🎟 แพ็ก</button>' +
      '<button class="btn btn-sm aeo-q" data-id="' + esc(p.id) + '" data-name="' + esc(p.name) + '">🎯 คำถาม AEO</button>' +
      '<button class="btn btn-sm sms-alert" data-id="' + esc(p.id) + '" data-name="' + esc(p.name) + '">🔔 SMS</button>' +
      '<button class="btn btn-sm cfg-proj" data-id="' + esc(p.id) + '">⚙️ ตั้งค่า</button>' +
      '<button class="btn btn-sm del-proj" data-id="' + esc(p.id) + '" data-name="' + esc(p.name) + '" style="margin-left:auto;color:var(--red-600,#dc2626)">🗑 ลบ</button>' +
      '</div></div>';
  }

  /* ลบโปรเจ็คถาวร (ยืนยันก่อน) */
  function confirmDelete(id, name) {
    var pid = String(id).replace(/^db/, '');
    ui.modal({ title: 'ลบโปรเจ็คนี้?', sub: name, width: 460, body:
      '<div class="note-box mb" style="border:1px solid var(--red-300,#fecaca);background:var(--red-50,#fef2f2)">⚠️ ลบ <b>' + esc(name) + '</b> และข้อมูลทั้งหมด (บทความ อันดับ AI Citation ช่องทาง คีย์) <b>ออกถาวร กู้คืนไม่ได้</b></div>' +
      '<div class="row between" style="margin-top:14px"><button class="btn btn-sm" id="delCancel">ยกเลิก</button>' +
      '<button class="btn btn-sm" id="delGo" style="background:var(--red-600,#dc2626);color:#fff;border:none">ลบถาวร</button></div>' });
    var go = document.getElementById('delGo'), cc = document.getElementById('delCancel');
    if (cc) cc.onclick = function () { ui.closeModal(); };
    if (go) go.onclick = function () {
      if (!RP.api.reachable()) { ui.toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้'); return; }
      go.disabled = true; go.textContent = 'กำลังลบ…';
      RP.api.deleteProject(pid).then(function () {
        ui.closeModal();
        ui.toast('ลบโปรเจ็ค <b>' + esc(name) + '</b> แล้ว ✓');
        if (RP.data.project.current === id) RP.data.project.current = '';
        if (RP.loadRealData) RP.loadRealData(function () { mountNow(); }); else mountNow();
      }).catch(function (e) { go.disabled = false; go.textContent = 'ลบถาวร'; ui.toast('ลบไม่ได้: ' + esc(e.message || String(e))); });
    };
  }

  /* เพิ่มคีย์เวิร์ดให้โปรเจ็คที่กำลังทำงาน (ต่อท้าย ไม่กระทบงานที่ผลิตอยู่ · เพดาน = แพ็กของลูกค้า) */
  function splitLines(s, cap) {
    return (s || '').split(/[,\n]+/).map(function (x) { return x.trim(); }).filter(Boolean).slice(0, cap || 50);
  }
  function addKeywordsModal(id, name, pack) {
    var pid = String(id).replace(/^db/, '');
    var info = packMap[pid] || {}; pack = normPack(pack || info.pack || 50);
    var used = info.used || 0, room = Math.max(0, pack - used);
    ui.modal({ title: '＋ เพิ่มคีย์เวิร์ด', sub: esc(name) + ' · แพ็ก ' + pack + ' คีย์ · ใช้ไปแล้ว ' + used + '/' + pack, width: 520, body:
      '<div class="hint mb">พิมพ์คีย์เวิร์ด/หัวข้อ — คั่นด้วย <b>,</b> หรือ <b>ขึ้นบรรทัดใหม่</b> · ระบบจะทยอยเขียนบทความให้ในรอบถัดไป (แพ็กนี้รวมได้สูงสุด <b>' + pack + '</b> หัวข้อ · เพิ่มได้อีก <b>' + room + '</b>)</div>' +
      '<textarea class="input" id="ak_txt" rows="6" placeholder="รับทำ seo สายเทา ราคา&#10;จ้างทำ seo คลินิก กี่บาท&#10;seo กับ google ads ต่างกันยังไง" style="width:100%;resize:vertical"></textarea>' +
      '<div class="row between" style="margin-top:8px;align-items:center"><span class="soft small" id="ak_count">0 คีย์เวิร์ด</span>' +
      '<button class="btn btn-primary" id="ak_save">เพิ่มคีย์เวิร์ด</button></div>' });
    var txt = document.getElementById('ak_txt'), cnt = document.getElementById('ak_count'), go = document.getElementById('ak_save');
    function upd() { if (cnt) { var n = splitLines(txt.value, room).length; cnt.textContent = n + ' คีย์เวิร์ด' + (n >= room ? ' (เต็มโควตาแพ็ก)' : ''); } }
    if (txt) { txt.oninput = upd; setTimeout(function () { txt.focus(); }, 50); }
    if (go) go.onclick = function () {
      var kws = splitLines(txt ? txt.value : '', room);
      if (!kws.length) { ui.toast(room ? 'พิมพ์คีย์เวิร์ดก่อน' : 'แพ็กนี้เต็มโควตาแล้ว — เปลี่ยนแพ็กเพื่อเพิ่ม'); return; }
      if (!RP.api.reachable()) { ui.toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้'); return; }
      go.disabled = true; go.textContent = 'กำลังเพิ่ม…';
      RP.api.addKeywords(pid, kws).then(function (d) {
        ui.closeModal();
        if (packMap[pid]) packMap[pid].used = d.total || 0;
        ui.toast('เพิ่ม <b>' + (d.added || 0) + '</b> คีย์เวิร์ดแล้ว ✓ (รวม ' + (d.total || 0) + '/' + (d.cap || pack) + ') — ระบบจะทยอยเขียนให้');
        if ((d.total || 0) > (d.cap || pack)) ui.toast('⚠️ คีย์เกินโควตาแพ็ก — บางคีย์จะยังไม่ถูกวัด/ดันจนกว่าจะขยายแพ็ก');
      }).catch(function (e) { go.disabled = false; go.textContent = 'เพิ่มคีย์เวิร์ด'; ui.toast('เพิ่มไม่ได้: ' + esc(e.message || String(e))); });
    };
  }

  /* เปลี่ยนแพ็กคีย์เวิร์ดของลูกค้า (แอดมิน) — 10 / 30 / 50 */
  function changePackModal(id, name, current) {
    var pid = String(id).replace(/^db/, '');
    var info = packMap[pid] || {}; current = normPack(current || info.pack || 50);
    var used = info.used || 0;
    var opts = PACKS.map(function (pk) {
      var on = pk === current, over = used > pk;
      return '<label class="row gap-s" style="cursor:pointer;padding:10px 12px;border:1px solid ' + (on ? 'var(--brand-500,#6366f1)' : 'var(--border,#e5e7eb)') +
        ';border-radius:10px;margin-bottom:8px;background:' + (on ? 'var(--brand-50,#eef2ff)' : 'var(--card,#fff)') + '">' +
        '<input type="radio" name="pk_sel" value="' + pk + '"' + (on ? ' checked' : '') + '> ' +
        '<span class="grow"><b>แพ็ก ' + pk + ' คีย์</b>' + (on ? ' <span class="soft small">(ปัจจุบัน)</span>' : '') + '</span>' +
        (over ? '<span class="soft small" style="color:#c0392b">ใช้ไป ' + used + ' เกินแพ็กนี้</span>' : '') + '</label>';
    }).join('');
    ui.modal({ title: '🎟 เปลี่ยนแพ็กคีย์เวิร์ด', sub: esc(name) + ' · ใช้ไปแล้ว ' + used + ' คีย์', width: 460, body:
      '<div class="hint mb">โควตาจำนวนคีย์เวิร์ดที่ระบบ <b>ติดตาม + ดัน + วัดผล</b> ให้ลูกค้ารายนี้ · ไม่ลบคีย์เดิม (ถ้าลดแพ็กแล้วเกิน คีย์ส่วนเกินจะพักไว้จนขยายแพ็ก)</div>' +
      opts +
      '<div class="row between" style="margin-top:8px"><button class="btn btn-sm" id="pk_cancel">ยกเลิก</button>' +
      '<button class="btn btn-primary" id="pk_save">บันทึกแพ็ก</button></div>' });
    var cc = document.getElementById('pk_cancel'), go = document.getElementById('pk_save');
    if (cc) cc.onclick = function () { ui.closeModal(); };
    if (go) go.onclick = function () {
      var sel = document.querySelector('input[name="pk_sel"]:checked');
      var pk = sel ? parseInt(sel.value, 10) : current;
      if (!RP.api.reachable()) { ui.toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้'); return; }
      go.disabled = true; go.textContent = 'กำลังบันทึก…';
      RP.api.setPack(pid, pk).then(function (r) {
        ui.closeModal();
        packMap[pid] = { pack: r.keyword_pack || pk, used: r.keywords_used || used };
        ui.toast('ตั้งแพ็กเป็น <b>' + (r.keyword_pack || pk) + ' คีย์</b> แล้ว ✓' + (r.over_quota ? ' · มีคีย์เกินโควตา (พักไว้)' : ''));
        mountNow();
      }).catch(function (e) {
        go.disabled = false; go.textContent = 'บันทึกแพ็ก';
        var m = e.message || String(e);
        ui.toast(/403/.test(m) ? 'ตั้งแพ็กได้เฉพาะแอดมิน (อีเมลต้องอยู่ใน ADMIN_EMAILS)' : 'ตั้งแพ็กไม่ได้: ' + esc(m));
      });
    };
  }

  /* ตั้ง "คำถาม AEO" เอง — คำที่คนถาม AI จริง (ต่างจากคีย์เวิร์ด SEO) → วัด AI Citation ให้ตรง
     บันทึกแทนที่ทั้งชุด (แก้/ลบได้) · มีผลรอบวัดถัดไป ไม่กระทบบทความที่ผลิตอยู่ · เปิดจากที่ไหนก็ได้ */
  function aeoQuestionsModal(id, name) {
    var pid = String(id).replace(/^db/, '');
    ui.modal({ title: '🎯 ตั้งคำถาม AEO', sub: esc(name || '') + ' · คำที่ "คนถาม AI จริง" — วัดว่าแบรนด์ถูกอ้างอิงไหม', width: 560, body:
      '<div class="hint mb">พิมพ์ <b>คำถามแบบที่คนถาม ChatGPT/Gemini/Perplexity จริง</b> — <b>บรรทัดละ 1 คำถาม</b> · ระบบจะใช้ชุดนี้ "ก่อน" คำถามอัตโนมัติเวลาวัด AI Citation (สูงสุด 30)</div>' +
      '<textarea class="input" id="aq_txt" rows="8" placeholder="จ้างบริษัททำ SEO ที่ไหนดี ในไทย&#10;ทำ SEO เองกับจ้าง อันไหนคุ้มกว่า&#10;คลินิกความงามควรทำ SEO ยังไง" style="width:100%;resize:vertical" disabled>กำลังโหลด…</textarea>' +
      '<div class="row between" style="margin-top:8px;align-items:center"><span class="soft small" id="aq_count">…</span>' +
      '<button class="btn btn-primary" id="aq_save" disabled>บันทึกคำถาม</button></div>' });
    var txt = document.getElementById('aq_txt'), cnt = document.getElementById('aq_count'), go = document.getElementById('aq_save');
    function lines(s) { return (s || '').split(/\n+/).map(function (x) { return x.trim(); }).filter(Boolean).slice(0, 30); }
    function upd() { if (cnt && txt) { var n = lines(txt.value).length; cnt.textContent = n + ' คำถาม' + (n >= 30 ? ' (สูงสุด)' : ''); } }
    if (!RP.api.reachable()) { if (txt) { txt.value = ''; txt.disabled = false; } ui.toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้'); return; }
    RP.api.getAeoQuestions(pid).then(function (d) {
      var cur = (d.questions && d.questions.length) ? d.questions : (d.suggested || []);
      var isSug = !(d.questions && d.questions.length) && (d.suggested || []).length;
      if (txt) {
        txt.value = cur.join('\n'); txt.disabled = false;
        if (isSug) { var h = document.querySelector('#modal .hint'); if (h) h.innerHTML += ' <span style="color:var(--amber-600)">· ด้านล่างเป็นชุดแนะนำอัตโนมัติ — ปรับให้ตรงแล้วบันทึก</span>'; }
        txt.oninput = upd; upd(); setTimeout(function () { txt.focus(); }, 50);
      }
      if (go) go.disabled = false;
    }).catch(function (e) { if (txt) { txt.value = ''; txt.disabled = false; txt.oninput = upd; upd(); } if (go) go.disabled = false; ui.toast('โหลดคำถามเดิมไม่ได้: ' + esc(e.message || String(e))); });
    if (go) go.onclick = function () {
      var qs = lines(txt ? txt.value : '');
      go.disabled = true; go.textContent = 'กำลังบันทึก…';
      RP.api.setAeoQuestions(pid, qs).then(function (d) {
        ui.closeModal();
        ui.toast('บันทึก <b>' + (d.total || 0) + '</b> คำถาม AEO แล้ว ✓ — ใช้ในรอบวัด AI Citation ครั้งถัดไป');
      }).catch(function (e) { go.disabled = false; go.textContent = 'บันทึกคำถาม'; ui.toast('บันทึกไม่ได้: ' + esc(e.message || String(e))); });
    };
  }
  RP.openAeoQuestions = aeoQuestionsModal;      // ให้หน้ารายงาน/อื่น ๆ เรียกใช้ modal เดียวกันได้

  function stat(l, v) { return '<div><div class="soft" style="font-size:11px">' + esc(l) + '</div><div class="bb">' + v + '</div></div>'; }

  /* รายการโปรเจ็คที่ "แสดงได้จริง": บัญชีจริงเห็นเฉพาะโปรเจ็คจากฐานข้อมูล (id ขึ้นต้น db) */
  function visibleList() {
    var list = RP.data.project.list || [];
    if (!RP.isReal()) return list;
    return list.filter(function (p) { return /^db/.test(String(p.id)); });
  }

  function quotaCard() {
    var a = RP.data.account, used = visibleList().length, q = a.projectQuota;
    var real = RP.isReal();
    var full = !real && used >= q;   // บัญชีจริง: ยังไม่รู้โควตาจริง → ไม่ล็อกปุ่มด้วยตัวเลขสมมติ
    return '<div class="card mb"><div class="card-pad row between wrap" style="gap:14px">' +
      '<div style="flex:1;min-width:260px">' +
      (real
        ? '<div class="bb" style="margin-bottom:6px">โปรเจ็คของคุณ</div>' +
          '<div class="soft small">มีอยู่ <b>' + used + '</b> โปรเจ็ค · แพ็กเกจ/โควตายังไม่มีข้อมูล — จะแสดงเมื่อเชื่อมระบบบิลลิ่งแล้ว</div>'
        : '<div class="row gap-s" style="margin-bottom:6px"><span class="bb">แพ็กเกจ ' + esc(a.plan) + '</span>' + ui.badge(a.billingCycle, 'blue') + RP.sampleBadge() + '</div>' +
          '<div class="soft small" style="margin-bottom:8px">ใช้ไป <b>' + used + '</b> จาก <b>' + q + '</b> โปรเจ็ค' + (full ? ' — เต็มโควตาแล้ว' : '') + '</div>' +
          ui.bar(used / q * 100, full ? 'amber' : '')) +
      '</div>' +
      '<div class="row gap-s wrap">' +
      '<button class="btn" id="loadDb">⤓ โหลดจากฐานข้อมูล</button>' +
      '<button class="btn btn-green new-proj"' + (full ? ' disabled style="opacity:.55"' : '') + '>＋ สร้างโปรเจ็คใหม่</button>' +
      '</div>' +
      '</div>' +
      (full ? '<div style="padding:0 22px 16px"><div class="hint">ต้องการมากกว่า ' + q + ' โปรเจ็ค? อัปเกรดเป็น <b>Enterprise</b> (ไม่จำกัดเว็บ) ในหน้า การตั้งค่า › บัญชี & ทีม</div></div>' : '') +
      '</div>';
  }

  /* แจ้งเตือน SMS อันดับต่อโปรเจ็ค (คีย์ติด/ขยับขึ้น) — Twilio */
  function smsAlertModal(id, name) {
    var pid = String(id).replace(/^db/, '');
    ui.modal({ title: '🔔 แจ้งเตือน SMS อันดับ', sub: esc(name), width: 480, body:
      '<div class="hint mb">ส่ง SMS หา "เบอร์นี้" เมื่อมี<b>ข่าวดี</b>ของโปรเจ็ค — คีย์<b>เริ่มติดอันดับ</b> · <b>ขยับขึ้น</b> · หรือ<b>ติดหน้า 1</b> (ระบบเช็กให้อัตโนมัติ ไม่แจ้งตอนอันดับตก/ยิงรัว)</div>' +
      '<div id="sms_status" class="soft small mb">กำลังโหลด…</div>' +
      '<label class="row gap-s" style="cursor:pointer;margin-bottom:10px"><input type="checkbox" id="sms_on"> <span>เปิดแจ้งเตือน SMS สำหรับโปรเจ็คนี้</span></label>' +
      field('เบอร์รับแจ้งเตือน', '<input class="input" id="sms_to" placeholder="เช่น 0987893988" style="width:100%">') +
      '<div class="row between" style="margin-top:14px"><button class="btn btn-sm" id="sms_cancel">ยกเลิก</button>' +
      '<button class="btn btn-primary" id="sms_save">บันทึก</button></div>' });
    var st = document.getElementById('sms_status'), on = document.getElementById('sms_on'),
        to = document.getElementById('sms_to'), go = document.getElementById('sms_save'), cc = document.getElementById('sms_cancel');
    if (cc) cc.onclick = function () { ui.closeModal(); };
    if (RP.api.reachable()) {
      RP.api.getSms(pid).then(function (d) {
        if (on) on.checked = !!d.enabled;
        if (to) to.value = d.to || '';
        if (st) st.innerHTML = d.twilio_ready
          ? '✅ ระบบ Twilio พร้อมส่ง SMS แล้ว'
          : '⚠️ ยังไม่ได้ตั้งค่า Twilio ในเซิร์ฟเวอร์ — บันทึกเบอร์ไว้ได้ก่อน แต่ SMS จะยังไม่ส่งจนกว่าจะตั้งคีย์';
      }).catch(function () { if (st) st.textContent = ''; });
    } else if (st) { st.textContent = ''; }
    if (go) go.onclick = function () {
      var enabled = on && on.checked, num = (to ? to.value : '').trim();
      if (enabled && !num) { ui.toast('กรอกเบอร์รับแจ้งเตือนก่อน'); return; }
      if (!RP.api.reachable()) { ui.toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้'); return; }
      go.disabled = true; go.textContent = 'กำลังบันทึก…';
      RP.api.setSms(pid, enabled, num).then(function (r) {
        ui.closeModal();
        ui.toast(enabled ? ('เปิดแจ้งเตือน SMS แล้ว ✓ → ' + esc(r.to || num)) : 'ปิดแจ้งเตือน SMS แล้ว');
        if (enabled && r && !r.twilio_ready) ui.toast('⚠️ ตั้ง Twilio ในเซิร์ฟเวอร์ก่อน SMS จึงจะส่งจริง');
      }).catch(function (e) { go.disabled = false; go.textContent = 'บันทึก'; ui.toast('บันทึกไม่ได้: ' + esc(e.message || String(e))); });
    };
  }

  /* ---- Wizard: สร้างโปรเจ็คใหม่ (วางลิงก์ → AI คิดคีย์เวิร์ด → ติ๊กเลือก → สร้าง) ---- */
  function uniq(arr) { var s = {}, o = []; arr.forEach(function (x) { x = (x || '').trim(); if (x && !s[x.toLowerCase()]) { s[x.toLowerCase()] = 1; o.push(x); } }); return o; }
  function curLang() { var s = document.getElementById('np_country'); return (s && /อังกฤษ|en/i.test(s.value)) ? 'en' : 'th'; }
  function styleChip(el) {
    var on = el.getAttribute('data-on') === '1';
    el.style.cssText = 'display:inline-flex;align-items:center;gap:4px;cursor:pointer;user-select:none;padding:6px 12px;margin:0 6px 6px 0;border-radius:999px;font-size:13px;' +
      'border:1px solid ' + (on ? 'var(--brand-500,#6366f1)' : 'var(--border,#e5e7eb)') + ';' +
      'background:' + (on ? 'var(--brand-50,#eef2ff)' : 'var(--card,#fff)') + ';color:' + (on ? 'var(--brand-700,#4338ca)' : 'inherit');
    el.innerHTML = (on ? '✓ ' : '＋ ') + esc(el.getAttribute('data-kw'));
  }
  function renderChips(container, ks, source, preselect, onChange) {
    var warn = (source && source !== 'site')       // อ่านเว็บไม่ได้ → คีย์เป็นการเดา = ไม่ตรง (บอกตามตรง)
      ? '<div class="hint" style="margin-bottom:8px;color:var(--amber-700,#b45309)">⚠️ AI อ่านเว็บไม่ได้ — คีย์ที่แนะนำเป็น "การเดา" จากชื่อ/โดเมน · พิมพ์เองด้านล่างจะตรงกว่า</div>'
      : '';
    var head = warn + '<div class="row between wrap" style="margin-bottom:8px;gap:8px"><div class="soft small">' +
      (source === 'site' ? '🤖 AI อ่านเว็บแล้วแนะนำ — ' : '🤖 AI แนะนำ — ') + 'ติ๊ก ＋ เพื่อเพิ่มเข้าลิสต์ (เลือกได้หลายอัน)</div>' +
      '<button type="button" class="btn btn-sm" id="kwAll">เลือกให้เต็มแพ็ก</button></div>';
    var pre = Math.max(0, preselect || 0);
    var body = ks.map(function (k, i) {
      return '<span class="kw-chip" data-kw="' + esc(k.kw) + '" data-on="' + (i < pre ? '1' : '0') + '"' + (k.why ? ' title="' + esc(k.why) + '"' : '') + '></span>';
    }).join('');
    container.innerHTML = head + '<div>' + body + '</div>' +
      '<div class="soft" style="font-size:11px;margin-top:6px">ระบบจะเขียนบทความจากคีย์ที่เลือกจริง · เลือกได้ไม่เกินแพ็ก</div>';
    Array.prototype.forEach.call(container.querySelectorAll('.kw-chip'), function (el) {
      styleChip(el);
      el.onclick = function () { el.setAttribute('data-on', el.getAttribute('data-on') === '1' ? '0' : '1'); styleChip(el); if (onChange) onChange(); };
    });
    var all = container.querySelector('#kwAll');
    if (all) all.onclick = function () { Array.prototype.forEach.call(container.querySelectorAll('.kw-chip'), function (el) { el.setAttribute('data-on', '1'); styleChip(el); }); if (onChange) onChange(); };
  }
  function collectSelected() {
    var c = document.getElementById('np_kwchips'); if (!c) return [];
    var out = [];
    Array.prototype.forEach.call(c.querySelectorAll('.kw-chip'), function (el) { if (el.getAttribute('data-on') === '1') out.push(el.getAttribute('data-kw')); });
    return out;
  }

  function openWizard() {
    var body =
      '<div class="hint mb">ใส่ลิงก์เว็บลูกค้า → <b>เลือกแพ็ก</b> → เลือกคีย์เวิร์ด (ไม่เกินแพ็ก) → สร้าง · ที่เหลือระบบเขียน/เผยแพร่/วัดผลให้เอง</div>' +
      field('ลิงก์เว็บไซต์ลูกค้า', '<input class="input" id="np_url" placeholder="เช่น abccoffee.com หรือ https://abccoffee.com" style="width:100%">') +
      '<div style="margin:8px 0 18px"><div class="soft small" style="margin-bottom:8px"><b>1 · เลือกแพ็กคีย์เวิร์ดของลูกค้ารายนี้</b> <span class="soft">(โควตาที่ระบบติดตาม+ดัน+วัดผล · เปลี่ยนภายหลังได้)</span></div>' +
        '<div class="row gap-s wrap">' + PACKS.map(function (pk) {
          return '<label class="row gap-s" style="cursor:pointer;padding:10px 20px;border:1px solid var(--border,#e5e7eb);border-radius:999px"><input type="radio" name="np_pack" value="' + pk + '"' + (pk === 10 ? ' checked' : '') + '> <span><b>' + pk + '</b> คีย์</span></label>';
        }).join('') + '</div></div>' +
      '<div class="soft small" style="margin-bottom:6px"><b>2 · เลือกคีย์เวิร์ด</b> — ให้ AI ช่วยคิดจากเว็บ หรือพิมพ์เอง (ไม่เกินแพ็กที่เลือก)</div>' +
      '<div class="row wrap" style="gap:8px;margin:2px 0 10px"><button type="button" class="btn btn-primary btn-sm" id="np_suggest">🤖 ให้ AI ช่วยคิดคีย์เวิร์ด</button>' +
      '<span class="soft small" style="align-self:center">AI อ่านเว็บให้ — ติ๊ก ＋ เพื่อเพิ่มเข้าลิสต์</span></div>' +
      '<div id="np_kwchips" class="mb"></div>' +
      field('พิมพ์คีย์เวิร์ดเองเพิ่ม (1 คีย์ต่อบรรทัด หรือคั่นด้วย ,)', '<textarea class="input" id="np_kw" rows="3" placeholder="เลเซอร์หน้าใส&#10;ฟิลเลอร์&#10;ร้อยไหมละลาย" style="width:100%;resize:vertical"></textarea>') +
      '<div id="np_count" style="margin:2px 0 14px;font-weight:700;font-size:.95rem"></div>' +
      '<details style="margin:8px 0"><summary class="soft small" style="cursor:pointer">ตัวเลือกเพิ่มเติม (ชื่อโปรเจ็ค · ภาษา · โหมดเผยแพร่)</summary><div style="padding-top:12px">' +
        field('ชื่อโปรเจ็ค (เว้นว่าง = ใช้ชื่อโดเมน)', '<input class="input" id="np_name" placeholder="เช่น คลินิกความงาม XYZ" style="width:100%">') +
        field('ภาษาเนื้อหา', '<select class="select" id="np_country" style="width:100%"><option value="th">ไทย</option><option value="en">อังกฤษ</option></select>') +
        '<div class="soft small" style="margin:4px 0 6px">โหมดเผยแพร่</div>' +
        '<label class="row gap-s" style="cursor:pointer;margin-bottom:6px"><input type="radio" name="np_mode" value="approve" checked> <span>Auto + กดอนุมัติก่อนเผยแพร่ (แนะนำ)</span></label>' +
        '<label class="row gap-s" style="cursor:pointer"><input type="radio" name="np_mode" value="auto"> <span>Full-Auto 100% (เผยแพร่เองเมื่อผ่านเกณฑ์)</span></label>' +
      '</div></details>' +
      '<div class="row between" style="margin-top:16px"><span class="soft small">ปรับแต่งเพิ่มได้ภายหลังที่ การตั้งค่า</span>' +
      '<button class="btn btn-primary" id="np_create">สร้างโปรเจ็ค &amp; เริ่มให้เลย</button></div>';
    ui.modal({ title: 'สร้างโปรเจ็คใหม่', sub: 'เลือกแพ็ก → เลือกคีย์เวิร์ด (ไม่เกินแพ็ก) → สร้าง', width: 640, body: body });

    function getPack() { var e = document.querySelector('input[name="np_pack"]:checked'); return normPack(e ? e.value : 10); }
    function manualList() { return splitc(document.getElementById('np_kw') ? document.getElementById('np_kw').value : ''); }
    function totalSelected() { return uniq(collectSelected().concat(manualList())); }
    function updateCount() {
      var pack = getPack(), tot = totalSelected().length, el = document.getElementById('np_count');
      if (!el) return;
      var over = tot > pack, col = over ? '#dc2626' : (tot ? 'var(--brand-700,#4338ca)' : 'var(--text-soft,#94a3b8)');
      el.innerHTML = '📋 เลือกแล้ว <b style="color:' + col + '">' + tot + ' / ' + pack + '</b> คีย์' +
        (over ? ' <span style="color:#dc2626;font-weight:400">— เกินแพ็ก จะใช้ ' + pack + ' คีย์แรก</span>'
              : (tot >= pack && tot ? ' <span class="soft" style="font-weight:400">(เต็มแพ็ก)</span>' : ''));
    }
    function syncSelection() {   // บังคับ 'คีย์ที่เลือก ≤ แพ็ก' — ถ้าเกิน ปลดชิปท้าย ๆ ออกให้พอดี
      var pack = getPack(), c = document.getElementById('np_kwchips'), manual = manualList().length, onChips = [];
      if (c) {
        Array.prototype.forEach.call(c.querySelectorAll('.kw-chip'), function (el) { if (el.getAttribute('data-on') === '1') onChips.push(el); });
        var allow = Math.max(0, pack - manual);
        while (onChips.length > allow) { var el = onChips.pop(); el.setAttribute('data-on', '0'); styleChip(el); }
      }
      updateCount();
    }
    Array.prototype.forEach.call(document.querySelectorAll('input[name="np_pack"]'), function (r) { r.onchange = syncSelection; });
    var kwTa = document.getElementById('np_kw'); if (kwTa) kwTa.oninput = updateCount;
    updateCount();

    var sg = document.getElementById('np_suggest');
    if (sg) sg.onclick = function () {
      var url = (document.getElementById('np_url').value || '').trim();
      if (!url) { ui.toast('วางลิงก์เว็บไซต์ก่อน'); return; }
      if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ — เปิดโหมด Live ในหน้าตั้งค่าก่อน'); return; }
      var nm = (document.getElementById('np_name') && document.getElementById('np_name').value || '').trim();
      var chips = document.getElementById('np_kwchips');
      sg.disabled = true; sg.textContent = '🤖 กำลังคิด…';
      chips.innerHTML = '<div class="soft small">AI กำลังวิเคราะห์เว็บและคิดคีย์เวิร์ด… (สักครู่)</div>';
      RP.api.suggestKeywords({ url: url, name: nm, language: curLang() }).then(function (d) {
        var ks = (d && d.keywords) || [];
        if (!ks.length) { chips.innerHTML = '<div class="soft small">ยังคิดไม่ได้ ลองใหม่ หรือพิมพ์คีย์เวิร์ดเองด้านล่าง</div>'; updateCount(); }
        else { renderChips(chips, ks, d.source, Math.min(5, getPack()), syncSelection); syncSelection(); }
      }).catch(function (e) {
        chips.innerHTML = '<div class="soft small">คิดคีย์เวิร์ดไม่ได้: ' + esc(e.message || '') + ' — พิมพ์เองด้านล่างได้</div>';
      }).then(function () { sg.disabled = false; sg.textContent = '🤖 ให้ AI ช่วยคิดคีย์เวิร์ดอีกครั้ง'; });
    };

    var btn = document.getElementById('np_create');
    if (btn) btn.onclick = function () {
      var url = (document.getElementById('np_url').value || '').trim();
      if (!url) { ui.toast('วางลิงก์เว็บไซต์ก่อน'); return; }
      var name = (document.getElementById('np_name') && document.getElementById('np_name').value || '').trim();
      var modeEl = document.querySelector('input[name="np_mode"]:checked');
      var mode = modeEl ? modeEl.value : 'approve';
      var packEl = document.querySelector('input[name="np_pack"]:checked');
      var pack = normPack(packEl ? packEl.value : 50);
      var keywords = uniq(collectSelected().concat(splitc(document.getElementById('np_kw') ? document.getElementById('np_kw').value : '')));
      if (keywords.length > pack) { ui.toast('เลือก ' + keywords.length + ' คีย์ เกินแพ็ก ' + pack + ' — จะใช้ ' + pack + ' คีย์แรก'); keywords = keywords.slice(0, pack); }
      if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ — <b>ยังไม่ได้สร้างโปรเจ็ค</b>'); return; }
      btn.disabled = true; btn.textContent = 'กำลังสร้าง…';
      RP.api.createProject({ url: url, name: name, mode: mode, country: 'ไทย', language: curLang(), publish_mode: 'managed', keywords: keywords, keyword_pack: pack })
        .then(function (p) {
          var home = p.public_home || '', dom = p.domain || url;
          ui.closeModal();
          RP.ui.toast('สร้างแล้ว ✓ ระบบกำลัง<b>อ่านเว็บ + เขียนบทความแรก</b>' + (keywords.length ? (' (' + keywords.length + ' คีย์)') : '') + ' — อีก ~2-5 นาที กดรีเฟรชดูได้');
          if (RP.loadRealData) RP.loadRealData(function () { mountNow(); }); else mountNow();
          if (home) RP.ui.modal({ title: 'บล็อกของคุณพร้อมแล้ว 🎉', sub: 'ลูกค้าใส่แค่ลิงก์ — ที่เหลือเราจัดการให้', width: 560,
            body: '<div class="note-box mb">ระบบจะเขียนบทความตามสูตร AEO แล้วเผยแพร่ที่นี่ให้อัตโนมัติ (ไม่ต้องแตะอะไรเลย)</div>' +
              '<div class="soft small" style="margin-bottom:6px">บล็อกที่เราโฮสต์ให้:</div>' +
              '<a href="' + RP.esc(home) + '" target="_blank" class="bb" style="word-break:break-all">' + RP.esc(home) + '</a>' +
              '<div class="hint" style="margin-top:12px">อยากให้อยู่บนโดเมนคุณเอง (เช่น <b>blog.' + RP.esc(dom) + '</b>)? ตั้งค่า CNAME มาที่เรา 1 บรรทัด แล้วแจ้งทีม — ระบบออก HTTPS ให้อัตโนมัติ</div>' });
        })
        .catch(function (e) {
          btn.disabled = false; btn.textContent = 'สร้างโปรเจ็ค & เริ่มให้เลย';
          RP.ui.toast('สร้างไม่ได้ (ต้องล็อกอินจริง): ' + RP.esc(e.message || String(e)));
        });
    };
  }
  function splitc(s) { return (s || '').split(/[,\n]+/).map(function (x) { return x.trim(); }).filter(Boolean); }
  function wizSection(t, inner) { return '<div class="panel mb"><div class="panel-head">' + esc(t) + '</div><div class="panel-body">' + inner + '</div></div>'; }
  function field(l, inp) { return '<div style="margin-bottom:10px"><div class="soft small" style="margin-bottom:4px">' + esc(l) + '</div>' + inp + '</div>'; }
  function checkline(t, on) { return '<div class="list-row"><span style="color:' + (on ? 'var(--green-600)' : 'var(--text-soft)') + ';font-weight:800">' + (on ? '✓' : '○') + '</span><div class="grow t small">' + esc(t) + '</div>' + (on ? ui.badge('พร้อม', 'green') : ui.badge('ต้องเชื่อม', 'amber')) + '</div>'; }

  function mountNow() { /* re-render current view */ if (location.hash === '#/projects') { var f = RP.views.projects(); var c = document.getElementById('content'); c.innerHTML = '<div class="view">' + f.html + '</div>'; f.mount(c); } }

  RP.views.projects = function () {
    var list = visibleList();   // บัญชีจริง = เฉพาะโปรเจ็คจากฐานข้อมูล ไม่โชว์โปรเจ็คตัวอย่าง
    var cards = list.length
      ? '<div class="grid grid-2">' + list.map(projectCard).join('') + '</div>'
      : RP.noData('ยังไม่มีโปรเจ็ค', 'สร้างโปรเจ็คแรกด้วยปุ่ม “＋ สร้างโปรเจ็คใหม่” ด้านบน — ระบบจะเริ่มเก็บข้อมูลจริงหลังเชื่อมต่อครบ');
    var html =
      ui.pageHead({ eyebrow: 'ระบบ · Multi-Project', title: 'จัดการโปรเจ็ค',
        desc: 'หน้านี้ไว้ “จัดการ” — สร้าง ตั้งค่า และลบโปรเจ็ค · ทุกโปรเจ็คทำงานอัตโนมัติพร้อมกัน (ไม่ต้องเปิดทีละอัน) · อยากดูผลงาน/สถานะสด ไปที่ 📊 แดชบอร์ด' }) +
      RP.sampleNotice('หน้าจัดการโปรเจ็ค (โปรเจ็คตัวอย่าง คีย์เวิร์ด คลัสเตอร์ แพ็กเกจ และสถานะการเชื่อมต่อ)') +
      RP.collectingNotice('ของแต่ละโปรเจ็ค (คีย์เวิร์ด/คลัสเตอร์/สถานะการเชื่อมต่อ)') +
      quotaCard() +
      cards;
    return {
      html: html,
      mount: function (root) {
        var np = root.querySelector('.new-proj'); if (np && !np.disabled) np.onclick = openWizard;
        var ld = root.querySelector('#loadDb');
        if (ld) ld.onclick = function () {
          if (!RP.api.reachable()) { RP.ui.toast('ตั้ง base URL ของ backend ในหน้า ⚙️ การตั้งค่าก่อน'); return; }
          RP.ui.toast('กำลังโหลดจากฐานข้อมูล…');
          RP.api.projects().then(function (res) {
            if (!res.projects || !res.projects.length) { RP.ui.toast('ยังไม่มีโปรเจ็คใน DB — ลองรัน scripts/seed.py'); return; }
            RP.data.project.list = res.projects.map(function (p) {
              // plan ว่างไว้ตั้งใจ — backend ยังไม่ส่งแพ็กเกจจริงมา จึงไม่เดาว่าเป็น "Pro"
              return { id: 'db' + p.id, name: p.name, domain: p.domain, mode: p.mode, country: p.country || 'ไทย', lang: 'ภาษาไทย', plan: '', status: 'active', created: 'จากฐานข้อมูล', keywords: 0, clusters: 0, competitors: [], brandTerms: [], promptSet: 0, freshnessDays: p.freshness_days || 120, authors: 0, health: { gsc: false, serp: false, ai: false, publish: false } };
            });
            RP.data.project.current = RP.data.project.list[0].id;
            RP.ui.toast('โหลด ' + res.projects.length + ' โปรเจ็คจากฐานข้อมูลแล้ว ✓');
            mountNow();
          }).catch(function (e) { RP.ui.toast('โหลดไม่ได้: ' + RP.esc(e.message) + ' (ต้องเข้าสู่ระบบจริง + ตั้ง DATABASE_URL)'); });
        };
        Array.prototype.forEach.call(root.querySelectorAll('.cfg-proj'), function (b) {
          b.onclick = function () { RP.data.project.current = b.getAttribute('data-id'); RP.go('settings'); };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.open-dash'), function (b) {
          b.onclick = function () {
            if (RP.openProjectReport) RP.openProjectReport(b.getAttribute('data-id'));
            else { RP.data.project.current = b.getAttribute('data-id'); RP.go('dashboard'); }
          };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.add-kw'), function (b) {
          b.onclick = function () { addKeywordsModal(b.getAttribute('data-id'), b.getAttribute('data-name') || ''); };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.chg-pack'), function (b) {
          b.onclick = function () { changePackModal(b.getAttribute('data-id'), b.getAttribute('data-name') || ''); };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.sms-alert'), function (b) {
          b.onclick = function () { smsAlertModal(b.getAttribute('data-id'), b.getAttribute('data-name') || ''); };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.aeo-q'), function (b) {
          b.onclick = function () { aeoQuestionsModal(b.getAttribute('data-id'), b.getAttribute('data-name') || ''); };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.del-proj'), function (b) {
          b.onclick = function () { confirmDelete(b.getAttribute('data-id'), b.getAttribute('data-name') || ''); };
        });
        // เติมสถานะทำงานจริง + ตัวเลขจริง ลงการ์ด (จาก /api/projects/overview)
        if (RP.isReal() && RP.api.enabled()) {
          RP.api.projectsOverview().then(function (d) {
            var m = {}; (d.projects || []).forEach(function (x) { m[x.id] = x; });
            function tone(t) { return t === 'green' ? 'green' : t === 'amber' ? 'amber' : t === 'red' ? 'red' : ''; }
            Array.prototype.forEach.call(root.querySelectorAll('.proj-status'), function (el) {
              var x = m[parseInt(el.getAttribute('data-pid'), 10)]; if (!x) return;
              el.innerHTML = ui.badge((x.status_tone === 'green' || x.status_tone === 'red' ? '● ' : '') + x.status_label, tone(x.status_tone));
            });
            Array.prototype.forEach.call(root.querySelectorAll('.proj-nums'), function (el) {
              var x = m[parseInt(el.getAttribute('data-pid'), 10)]; if (!x) return;
              el.textContent = 'บทความ ' + (x.articles || 0) + ' · เผยแพร่ ' + (x.published || 0) +
                ' · ติดหน้า 1 ' + (x.page1 || 0) + (x.avg_aeo != null ? ' · AEO ' + x.avg_aeo : '');
            });
            (d.projects || []).forEach(function (x) {
              if (x.keyword_pack) packMap[String(x.id)] = { pack: x.keyword_pack, used: x.keywords_used || 0 };
            });
            Array.prototype.forEach.call(root.querySelectorAll('.proj-pack'), function (el) {
              var x = m[parseInt(el.getAttribute('data-pid'), 10)]; if (!x || !x.keyword_pack) return;
              var used = x.keywords_used || 0, pk = x.keyword_pack;
              el.innerHTML = ui.badge('🎟 ' + used + '/' + pk + ' คีย์', used > pk ? 'amber' : 'purple');
            });
          }).catch(function () {});
        }
      }
    };
  };

})(window.RP);
