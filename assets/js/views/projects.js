/* ============================================================
   View: จัดการโปรเจ็ค (Multi-Project) + สร้างโปรเจ็คใหม่ (Wizard)
   รองรับหลายโปรเจ็คตามแพ็กเกจ (Starter 1 / Pro 3 / Enterprise ไม่จำกัด)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

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
      '<span class="proj-status" data-pid="' + esc(numId) + '">' + (real ? '<span class="soft small">…</span>' : (p.plan ? ui.badge('แพ็กเกจ ' + p.plan, 'purple') : '')) + '</span>' +
      '</div>' +
      (!real && setup ? '<div class="hint" style="margin-top:10px">⚠️ ตั้งค่ายังไม่ครบ (' + connected + '/4) — เชื่อม AI Citation + ปลายทางเผยแพร่ให้ครบก่อนเริ่มวัดผล</div>' : '') +
      (real ? '' : healthRow(p.health)) +
      '<div class="soft small proj-nums" data-pid="' + esc(numId) + '" style="margin:12px 0">' + (real ? 'กำลังโหลดข้อมูล…' : '') + '</div>' +
      (real ? '<div class="soft small" style="margin:0 0 12px">🔌 สถานะการเชื่อมต่อดูที่ ⚙️ ตั้งค่า › การเชื่อมต่อ · ผลงาน/การทำงานสดดูที่ 📊 แดชบอร์ด</div>' : '') +
      '<div class="row gap-s wrap" style="align-items:center">' +
      '<button class="btn btn-primary btn-sm open-dash" data-id="' + esc(p.id) + '">📊 เปิดรายงาน</button>' +
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

  /* ---- Wizard: สร้างโปรเจ็คใหม่ ---- */
  function openWizard() {
    var body =
      '<div class="hint mb">การสร้างโปรเจ็คคือการบอกระบบว่า "จะดันเว็บไหน ด้วยคีย์เวิร์ด/คู่แข่งอะไร และเผยแพร่ที่ไหน" — ตั้งค่าเสร็จระบบเริ่มวงจรอัตโนมัติให้เอง</div>' +
      wizSection('1 · ข้อมูลโปรเจ็ค',
        field('ชื่อโปรเจ็ค', '<input class="input" id="np_name" placeholder="เช่น คลินิกความงาม XYZ" style="width:100%">') +
        field('โดเมนเว็บไซต์', '<input class="input" id="np_domain" placeholder="example.com" style="width:100%">') +
        field('ประเทศ / ภาษาเป้าหมาย', '<select class="select" id="np_country" style="width:100%"><option>ไทย / ภาษาไทย</option><option>ไทย / อังกฤษ</option></select>')) +
      wizSection('2 · การเชื่อมต่อที่ต้องมี (จำเป็นก่อนวัดผล)',
        checkline('SERP API — วัดอันดับ Google', true) +
        checkline('Google Search Console — ยืนยันโดเมน', false) +
        checkline('API วัด AI Citation (ChatGPT/Gemini/Perplexity)', false) +
        checkline('ปลายทางเผยแพร่ (WordPress / Webflow)', false)) +
      wizSection('3 · เป้าหมาย',
        field('คีย์เวิร์ด/หัวข้อเริ่มต้น (คั่นด้วย ,)', '<input class="input" id="np_kw" placeholder="เลเซอร์หน้าใส, ฟิลเลอร์, ครีมกันแดด" style="width:100%">') +
        field('โดเมนคู่แข่ง (คั่นด้วย ,)', '<input class="input" id="np_comp" placeholder="competitor-a.com, competitor-b.com" style="width:100%">') +
        field('ชื่อแบรนด์ที่ใช้ตรวจ AI Citation', '<input class="input" id="np_brand" placeholder="ชื่อแบรนด์ / ชื่อเว็บ" style="width:100%">')) +
      wizSection('4 · โหมดเผยแพร่',
        '<label class="row gap-s" style="cursor:pointer;margin-bottom:6px"><input type="radio" name="np_mode" value="approve" checked> <span>Auto + Human Approve (แนะนำ — กดอนุมัติก่อนเผยแพร่)</span></label>' +
        '<label class="row gap-s" style="cursor:pointer"><input type="radio" name="np_mode" value="auto"> <span>Full-Auto 100% (เผยแพร่เองเมื่อผ่านเกณฑ์คุณภาพ)</span></label>') +
      '<div class="row between" style="margin-top:18px"><span class="soft small">ตั้งค่าเพิ่มเติมได้ภายหลังที่ การตั้งค่า</span>' +
      '<button class="btn btn-primary" id="np_create">สร้างโปรเจ็ค & เริ่มวงจร</button></div>';
    ui.modal({ title: 'สร้างโปรเจ็คใหม่', sub: 'ตั้งค่าพื้นฐานให้ระบบเริ่มทำงานอัตโนมัติ', width: 720, body: body });
    var btn = document.getElementById('np_create');
    if (btn) btn.onclick = function () {
        var name = (document.getElementById('np_name').value || '').trim();
        var domain = (document.getElementById('np_domain').value || '').trim();
        if (!name || !domain) { ui.toast('กรุณากรอกชื่อโปรเจ็คและโดเมน'); return; }
        var modeEl = document.querySelector('input[name="np_mode"]:checked');
        var id = 'p' + (RP.data.project.list.length + 1);
        var real = RP.isReal();
        // บัญชีจริง + ต่อ backend ไม่ได้ → ห้ามบอกว่า "สร้างแล้ว" ทั้งที่ยังไม่ได้สร้างจริง
        if (real && !(RP.api && RP.api.reachable())) {
          ui.toast('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ — <b>ยังไม่ได้สร้างโปรเจ็ค</b> กรุณาลองใหม่อีกครั้ง');
          return;
        }
        if (!real) {   // โหมดตัวอย่างเท่านั้น: เพิ่มการ์ดสมมติในหน่วยความจำ
          RP.data.project.list.push({
            id: id, name: name, domain: domain, mode: modeEl ? modeEl.value : 'approve',
            country: 'ไทย', lang: 'ภาษาไทย', plan: 'Pro', status: 'setup', created: 'เมื่อสักครู่',
            keywords: 0, clusters: 0,
            competitors: splitc(document.getElementById('np_comp').value),
            brandTerms: splitc(document.getElementById('np_brand').value),
            promptSet: 0, freshnessDays: 120, authors: 0,
            health: { gsc: false, serp: true, ai: false, publish: false }
          });
        }
        if (RP.api && RP.api.reachable()) {   // สร้างในระบบจริง (DB) ด้วย → auto-loop เริ่มผลิต + โฮสต์บล็อกให้
          var langSel = document.getElementById('np_country');
          var language = (langSel && /อังกฤษ/.test(langSel.value)) ? 'en' : 'th';
          RP.api.createProject({ name: name, domain: domain, mode: modeEl ? modeEl.value : 'approve',
                                 country: 'ไทย', language: language, publish_mode: 'managed' })
            .then(function (p) {
              var home = p.public_home || '';
              if (RP.loadRealData) RP.loadRealData(function () { mountNow(); });   // ดึงรายการโปรเจ็คจริงกลับมาแสดง
              RP.ui.toast('สร้างในระบบจริงแล้ว ✓ ระบบจะเริ่มผลิต + โฮสต์บล็อกให้อัตโนมัติ');
              if (home) RP.ui.modal({ title: 'บล็อกของคุณพร้อมแล้ว 🎉', sub: 'ลูกค้าใส่แค่ลิงก์ — ที่เหลือเราจัดการให้', width: 560,
                body: '<div class="note-box mb">ระบบจะเขียนบทความตามสูตร AEO แล้วเผยแพร่ที่นี่ให้อัตโนมัติ (ไม่ต้องแตะอะไรเลย)</div>' +
                  '<div class="soft small" style="margin-bottom:6px">บล็อกที่เราโฮสต์ให้:</div>' +
                  '<a href="' + RP.esc(home) + '" target="_blank" class="bb" style="word-break:break-all">' + RP.esc(home) + '</a>' +
                  '<div class="hint" style="margin-top:12px">อยากให้อยู่บนโดเมนคุณเอง (เช่น <b>blog.' + RP.esc(domain) + '</b>)? ตั้งค่า CNAME มาที่เรา 1 บรรทัด แล้วแจ้งทีม — ระบบออก HTTPS ให้อัตโนมัติ</div>' });
            })
            .catch(function (e) { RP.ui.toast('บันทึก DB ไม่ได้ (ต้องล็อกอินจริง): ' + RP.esc(e.message || String(e))); });
        }
        ui.closeModal();
        ui.toast(real ? 'กำลังสร้างโปรเจ็ค <b>' + esc(name) + '</b> ในระบบ…'
                      : 'สร้างโปรเจ็ค <b>' + esc(name) + '</b> แล้ว — เชื่อมต่อที่เหลือในหน้าตั้งค่าเพื่อเริ่มวัดผล ✓');
        RP.go('projects'); mountNow();
      };
  }
  function splitc(s) { return (s || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean); }
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
          }).catch(function () {});
        }
      }
    };
  };

})(window.RP);
