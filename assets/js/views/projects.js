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

  function projectCard(p) {
    var isCur = p.id === RP.data.project.current;
    var setup = p.status === 'setup';
    var connected = (p.health.gsc ? 1 : 0) + (p.health.serp ? 1 : 0) + (p.health.ai ? 1 : 0) + (p.health.publish ? 1 : 0);
    return '<div class="card card-pad" style="' + (isCur ? 'border-color:var(--brand-500);box-shadow:0 0 0 2px rgba(99,102,241,.15)' : '') + '">' +
      '<div class="row between wrap" style="gap:8px">' +
      '<div class="bb" style="font-size:16px">' + esc(p.name) + (isCur ? ' ' + ui.badge('กำลังใช้งาน', 'green') : '') + '</div>' +
      ui.badge('แพ็กเกจ ' + p.plan, 'purple') + '</div>' +
      '<div class="soft small" style="margin-top:2px">🌐 ' + esc(p.domain) + ' · ' + esc(p.country) + ' · สร้างเมื่อ ' + esc(p.created) + '</div>' +
      (setup ? '<div class="hint" style="margin-top:10px">⚠️ ตั้งค่ายังไม่ครบ (' + connected + '/4) — เชื่อม AI Citation + ปลายทางเผยแพร่ให้ครบก่อนเริ่มวัดผล</div>' : '') +
      healthDots(p.health) +
      '<div class="row wrap" style="gap:18px;margin:6px 0 12px">' +
      stat('คีย์เวิร์ดติดตาม', fmt.n(p.keywords)) + stat('คลัสเตอร์', p.clusters) +
      stat('โหมด', p.mode === 'auto' ? 'Full-Auto' : 'Human Approve') + stat('Freshness', p.freshnessDays + ' วัน') +
      '</div>' +
      '<div class="row gap-s wrap">' +
      (isCur ? '<button class="btn btn-sm" disabled style="opacity:.6">● ใช้งานอยู่</button>'
             : '<button class="btn btn-primary btn-sm use-proj" data-id="' + p.id + '">เปิดใช้งานโปรเจ็คนี้</button>') +
      '<button class="btn btn-sm cfg-proj" data-id="' + p.id + '">⚙️ ตั้งค่า</button>' +
      '<button class="btn btn-sm open-dash" data-id="' + p.id + '">เปิดแดชบอร์ด →</button>' +
      '</div></div>';
  }
  function stat(l, v) { return '<div><div class="soft" style="font-size:11px">' + esc(l) + '</div><div class="bb">' + v + '</div></div>'; }

  function quotaCard() {
    var a = RP.data.account, used = RP.data.project.list.length, q = a.projectQuota;
    var full = used >= q;
    return '<div class="card mb"><div class="card-pad row between wrap" style="gap:14px">' +
      '<div style="flex:1;min-width:260px">' +
      '<div class="row gap-s" style="margin-bottom:6px"><span class="bb">แพ็กเกจ ' + esc(a.plan) + '</span>' + ui.badge(a.billingCycle, 'blue') + '</div>' +
      '<div class="soft small" style="margin-bottom:8px">ใช้ไป <b>' + used + '</b> จาก <b>' + q + '</b> โปรเจ็ค' + (full ? ' — เต็มโควตาแล้ว' : '') + '</div>' +
      ui.bar(used / q * 100, full ? 'amber' : '') + '</div>' +
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
        RP.data.project.list.push({
          id: id, name: name, domain: domain, mode: modeEl ? modeEl.value : 'approve',
          country: 'ไทย', lang: 'ภาษาไทย', plan: 'Pro', status: 'setup', created: 'เมื่อสักครู่',
          keywords: 0, clusters: 0,
          competitors: splitc(document.getElementById('np_comp').value),
          brandTerms: splitc(document.getElementById('np_brand').value),
          promptSet: 0, freshnessDays: 120, authors: 0,
          health: { gsc: false, serp: true, ai: false, publish: false }
        });
        if (RP.api && RP.api.reachable()) {   // สร้างในระบบจริง (DB) ด้วย → auto-loop เริ่มผลิตให้
          RP.api.createProject({ name: name, domain: domain, mode: modeEl ? modeEl.value : 'approve', country: 'ไทย' })
            .then(function (p) { RP.ui.toast('บันทึกลงระบบจริงแล้ว (id ' + p.id + ') ✓ ระบบจะเริ่มผลิตคอนเทนต์ให้'); })
            .catch(function (e) { RP.ui.toast('บันทึก DB ไม่ได้ (ต้องล็อกอินจริง): ' + RP.esc(e.message || String(e))); });
        }
        ui.closeModal();
        ui.toast('สร้างโปรเจ็ค <b>' + esc(name) + '</b> แล้ว — เชื่อมต่อที่เหลือในหน้าตั้งค่าเพื่อเริ่มวัดผล ✓');
        RP.go('projects'); mountNow();
      };
  }
  function splitc(s) { return (s || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean); }
  function wizSection(t, inner) { return '<div class="panel mb"><div class="panel-head">' + esc(t) + '</div><div class="panel-body">' + inner + '</div></div>'; }
  function field(l, inp) { return '<div style="margin-bottom:10px"><div class="soft small" style="margin-bottom:4px">' + esc(l) + '</div>' + inp + '</div>'; }
  function checkline(t, on) { return '<div class="list-row"><span style="color:' + (on ? 'var(--green-600)' : 'var(--text-soft)') + ';font-weight:800">' + (on ? '✓' : '○') + '</span><div class="grow t small">' + esc(t) + '</div>' + (on ? ui.badge('พร้อม', 'green') : ui.badge('ต้องเชื่อม', 'amber')) + '</div>'; }

  function mountNow() { /* re-render current view */ if (location.hash === '#/projects') { var f = RP.views.projects(); var c = document.getElementById('content'); c.innerHTML = '<div class="view">' + f.html + '</div>'; f.mount(c); } }

  RP.views.projects = function () {
    var cards = RP.data.project.list.map(projectCard).join('');
    var html =
      ui.pageHead({ eyebrow: 'ระบบ · Multi-Project', title: 'จัดการโปรเจ็ค',
        desc: 'หนึ่งบัญชีดูแลได้หลายเว็บ/หลายลูกค้า — แต่ละโปรเจ็คมีคีย์เวิร์ด คู่แข่ง ปลายทางเผยแพร่ และการวัดผลของตัวเอง (จำนวนโปรเจ็คตามแพ็กเกจ)' }) +
      quotaCard() +
      '<div class="grid grid-2">' + cards + '</div>';
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
              return { id: 'db' + p.id, name: p.name, domain: p.domain, mode: p.mode, country: p.country || 'ไทย', lang: 'ภาษาไทย', plan: 'Pro', status: 'active', created: 'จากฐานข้อมูล', keywords: 0, clusters: 0, competitors: [], brandTerms: [], promptSet: 0, freshnessDays: p.freshness_days || 120, authors: 0, health: { gsc: false, serp: false, ai: false, publish: false } };
            });
            RP.data.project.current = RP.data.project.list[0].id;
            RP.ui.toast('โหลด ' + res.projects.length + ' โปรเจ็คจากฐานข้อมูลแล้ว ✓');
            mountNow();
          }).catch(function (e) { RP.ui.toast('โหลดไม่ได้: ' + RP.esc(e.message) + ' (ต้องเข้าสู่ระบบจริง + ตั้ง DATABASE_URL)'); });
        };
        Array.prototype.forEach.call(root.querySelectorAll('.use-proj'), function (b) {
          b.onclick = function () {
            RP.data.project.current = b.getAttribute('data-id');
            var p = RP.data.project.list.filter(function (x) { return x.id === RP.data.project.current; })[0];
            ui.toast('สลับมาที่โปรเจ็ค <b>' + esc(p.name) + '</b>');
            mountNow();
          };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.cfg-proj'), function (b) {
          b.onclick = function () { RP.data.project.current = b.getAttribute('data-id'); RP.go('settings'); };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.open-dash'), function (b) {
          b.onclick = function () { RP.data.project.current = b.getAttribute('data-id'); RP.go('dashboard'); };
        });
      }
    };
  };

})(window.RP);
