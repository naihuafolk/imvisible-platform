(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  function factBadge(fact) {
    if (fact === 'pass') return ui.badge('ผ่าน', 'green');
    return ui.badge('กำลังตรวจ', 'amber');
  }

  function plagBadge(plag) {
    var v = (plag == null ? 0 : plag);
    if (v < 5) return ui.badge(v + '%', 'green');
    return ui.badge(v + '%', 'amber');
  }

  function statusBadge(status) {
    if (status === 'ready') return ui.badge('พร้อมเผยแพร่', 'green');
    if (status === 'scheduled') return ui.badge('ตั้งเวลาแล้ว', 'blue');
    if (status === 'factcheck') return ui.badge('กำลัง Fact-Check', 'amber');
    return ui.badge('ฉบับร่าง', '');
  }

  function queueRow(q) {
    return '<tr>' +
      '<td><span class="bb">' + esc(q.title) + '</span>' +
        '<div class="soft small">' + esc(q.author) + '</div></td>' +
      '<td>' + ui.badge(esc(q.cluster), '') + '</td>' +
      '<td class="soft">' + esc(q.format) + '</td>' +
      '<td class="num">' + fmt.n(q.words) + '</td>' +
      '<td class="center">' + ui.scorePill(q.aeo) + '</td>' +
      '<td class="center">' + factBadge(q.fact) + '</td>' +
      '<td class="center">' + plagBadge(q.plag) + '</td>' +
      '<td class="center">' + statusBadge(q.status) + '</td>' +
    '</tr>';
  }

  function queueTable(queue) {
    if (!queue.length) {
      return '<div class="card-pad soft">ยังไม่มีบทความในคิว</div>';
    }
    var rows = '';
    for (var i = 0; i < queue.length; i++) rows += queueRow(queue[i]);
    return '<div class="tbl-wrap"><table class="tbl">' +
      '<thead><tr>' +
        '<th>บทความ</th>' +
        '<th>คลัสเตอร์</th>' +
        '<th>รูปแบบ</th>' +
        '<th class="right">จำนวนคำ</th>' +
        '<th class="center">คะแนน AEO</th>' +
        '<th class="center">Fact-Check</th>' +
        '<th class="center">ความซ้ำ</th>' +
        '<th class="center">สถานะ</th>' +
      '</tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>';
  }

  function checklistBody(list) {
    if (!list.length) return '<div class="soft">ยังไม่มีรายการตรวจสอบ</div>';
    var out = '';
    for (var i = 0; i < list.length; i++) {
      var c = list[i];
      var mark = c.on
        ? '<span class="badge green">✓</span>'
        : '<span class="soft">○</span>';
      out += '<div class="list-row">' + mark +
        '<div class="grow"><div class="t">' + esc(c.t) + '</div></div>' +
        '<div class="s">' + (c.on ? '<span class="muted small">พร้อม</span>' : '<span class="muted small">ยังไม่ผ่าน</span>') + '</div>' +
      '</div>';
    }
    return out;
  }

  function eeatBody() {
    return '' +
      '<div class="note-box purple mb">' +
        '<b>Author Persona + แหล่งอ้างอิงจริง</b><div class="soft small">' +
        'ทุกบทความผูกโปรไฟล์ผู้เขียนที่มีความเชี่ยวชาญจริง และแนบแหล่งอ้างอิงที่ระบบไปดึงมา ' +
        'เพื่อสร้างสัญญาณ E-E-A-T (ประสบการณ์ · ความเชี่ยวชาญ · ความน่าเชื่อถือ · ความไว้วางใจ)</div>' +
      '</div>' +
      '<div class="ok-box mb">' +
        '<b>AI Fact-Check ข้ามแหล่ง</b><div class="soft small">' +
        'ระบบตรวจข้อเท็จจริงอัตโนมัติโดยเทียบข้อมูลข้ามหลายแหล่ง ก่อนอนุมัติเข้าคิวเผยแพร่</div>' +
      '</div>' +
      '<div class="hint">' +
        '<b>ตรวจความซ้ำ (Plagiarism)</b> · บทความที่มีความซ้ำ ' +
        '<span class="bb">ต่ำกว่า 5%</span> จึงจะถือว่าปลอดภัยต่อการเผยแพร่' +
      '</div>';
  }

  function formatsBody(formats) {
    if (!formats.length) return '<div class="soft">ยังไม่ได้กำหนดรูปแบบคอนเทนต์</div>';
    var chips = '';
    for (var i = 0; i < formats.length; i++) {
      chips += '<span class="chip">' + esc(formats[i]) + '</span>';
    }
    return '<div class="tag-list">' + chips + '</div>';
  }

  RP.views.m2 = function () {
    var d = (RP.data && RP.data.m2) || {};
    var queue = d.queue || [];
    var formats = d.formats || [];
    var checklist = d.aeoChecklist || [];

    var total = queue.length;
    var readyCount = RP.by(queue, 'status', 'ready').length;
    var factPass = RP.by(queue, 'fact', 'pass').length;
    var avgAeo = total ? Math.round(RP.sum(queue, function (q) { return q.aeo || 0; }) / total) : 0;

    var kpis =
      ui.kpi({
        label: 'บทความในคิว',
        value: fmt.n(total),
        tone: '',
        foot: '<span class="soft">รวมทุกสถานะการผลิต</span>'
      }) +
      ui.kpi({
        label: 'พร้อมเผยแพร่',
        value: fmt.n(readyCount),
        tone: 'pos',
        foot: '<span class="soft">ผ่านทุกด่านตรวจแล้ว</span>'
      }) +
      ui.kpi({
        label: 'คะแนน AEO เฉลี่ย',
        value: total ? fmt.n(avgAeo) : '—',
        tone: 'brand',
        foot: '<span class="soft">Answer-First · โครงสร้าง · FAQ</span>'
      }) +
      ui.kpi({
        label: 'ผ่าน Fact-Check',
        value: fmt.n(factPass) + '<span class="soft"> / ' + fmt.n(total) + '</span>',
        tone: '',
        foot: '<span class="soft">ตรวจข้อเท็จจริงข้ามแหล่ง</span>'
      });

    var html =
      ui.pageHead({
        eyebrow: 'M2 · AI Content Factory',
        title: 'โรงงานคอนเทนต์',
        desc: 'ผลิตบทความตาม<b>สูตร AEO</b> — เปิดด้วยคำตอบ 40–60 คำ, โครงสร้าง H2/H3, FAQ, ตาราง, สรุปประเด็น ' +
          'พร้อมผูก Author Persona และผ่าน Fact-Check + Plagiarism ก่อนเผยแพร่'
      }) +
      liveGenCard() +
      liveRealCard() +
      '<div class="grid grid-4 mb">' + kpis + '</div>' +
      ui.card({
        title: 'คิวผลิตคอนเทนต์',
        sub: 'ผลิตตามสูตร AEO + Fact-Check + Plagiarism ก่อนเข้าคิวเผยแพร่',
        body: queueTable(queue),
        flush: true
      }) +
      '<div class="grid grid-2 mb">' +
        ui.card({
          title: 'เช็กลิสต์สูตร AEO',
          sub: 'องค์ประกอบที่ต้องมีในทุกบทความ',
          body: checklistBody(checklist)
        }) +
        ui.card({
          title: 'คุณภาพ & ความน่าเชื่อถือ (E-E-A-T)',
          sub: 'สร้างความไว้วางใจก่อนเผยแพร่',
          body: eeatBody()
        }) +
      '</div>' +
      ui.card({
        title: 'รูปแบบคอนเทนต์ที่รองรับ',
        sub: 'บทความยาว · หน้าเปรียบเทียบ · “X คืออะไร” · รีวิว · Listicle · Programmatic',
        body: formatsBody(formats)
      });

    return {
      html: html,
      mount: function (root) {
        var b = root.querySelector('#m2_gen');
        if (b) b.onclick = function () {
          var topic = (root.querySelector('#m2_topic').value || '').trim();
          if (!topic) { RP.ui.toast('พิมพ์หัวข้อบทความก่อนครับ'); return; }
          var fmtSel = root.querySelector('#m2_fmt');
          RP.live(RP.api.generate(topic, fmtSel ? fmtSel.value : 'บทความยาว', 1500), genModal);
        };
        var lr = root.querySelector('#m2_loadreal');
        if (lr) lr.onclick = function () { loadReal(root); };
      }
    };
  };

  /* ---- Live: โปรเจ็ค & บทความจริงจาก DB (ของจริง ไม่ใช่เดโม) ---- */
  function liveRealCard() {
    return ui.card({
      title: '🔴 Live — โปรเจ็ค & บทความจริงจากระบบ',
      sub: 'ดึงจาก backend จริง — โปรเจ็คที่สร้าง + บทความที่ออโต้ลูปผลิต/เผยแพร่ (ต้องเข้าสู่ระบบจริง)',
      cls: 'mb',
      action: (RP.api && RP.api.reachable()) ? ui.badge('● ต่อ backend', 'green') : ui.badge('backend ปิด', 'amber'),
      body:
        '<div class="row wrap" style="gap:10px;margin-bottom:6px">' +
        '<button class="btn btn-primary" id="m2_loadreal">โหลดโปรเจ็ค & บทความจริง</button>' +
        '<span class="soft small" style="align-self:center">ต้องล็อกอินจริง (JWT) + มีโปรเจ็คใน DB</span></div>' +
        '<div id="m2_realout"></div>'
    });
  }

  function loadReal(root) {
    var out = root.querySelector('#m2_realout');
    out.innerHTML = '<div class="soft small">กำลังโหลด…</div>';
    RP.api.projects().then(function (res) {
      var projs = res.projects || [];
      if (!projs.length) { out.innerHTML = '<div class="hint">ยังไม่มีโปรเจ็คใน DB — สร้างในหน้าจัดการโปรเจ็ค หรือรัน grow_test</div>'; return; }
      out.innerHTML = projs.map(function (p) {
        return '<div class="panel mb"><div class="panel-body">' +
          '<div class="row between wrap" style="gap:8px">' +
          '<div class="bb">' + esc(p.name) + ' <span class="soft small">· ' + esc(p.domain) + ' · โหมด ' + esc(p.mode) + '</span></div>' +
          '<div class="row gap-s">' +
          '<button class="btn btn-sm btn-green rp-grow" data-id="' + p.id + '">🚀 ผลิตเดี๋ยวนี้</button>' +
          '<button class="btn btn-sm rp-arts" data-id="' + p.id + '">ดูบทความจริง</button></div></div>' +
          '<div class="rp-arts-out" data-for="' + p.id + '" style="margin-top:8px"></div></div></div>';
      }).join('');
      wireReal(root);
    }).catch(function (e) {
      out.innerHTML = '<div class="hint">โหลดไม่ได้: ' + esc(e.message || String(e)) + ' (ต้องล็อกอินจริง ไม่ใช่บัญชีเดโม)</div>';
    });
  }

  function wireReal(root) {
    Array.prototype.forEach.call(root.querySelectorAll('.rp-grow'), function (b) {
      b.onclick = function () {
        RP.ui.toast('สั่งระบบผลิตคอนเทนต์…');
        RP.api.grow(b.getAttribute('data-id'))
          .then(function () { RP.ui.toast('เข้าคิวแล้ว ✓ ระบบกำลังขุด→เขียน→เผยแพร่ (กด "ดูบทความจริง" อีกสักครู่)'); })
          .catch(function (e) { RP.ui.toast('สั่งไม่ได้: ' + esc(e.message || String(e))); });
      };
    });
    Array.prototype.forEach.call(root.querySelectorAll('.rp-arts'), function (b) {
      b.onclick = function () {
        var id = b.getAttribute('data-id');
        var box = root.querySelector('.rp-arts-out[data-for="' + id + '"]');
        box.innerHTML = '<div class="soft small">กำลังโหลด…</div>';
        RP.api.projectArticles(id).then(function (res) {
          var arts = res.articles || [];
          if (!arts.length) { box.innerHTML = '<div class="soft small">ยังไม่มีบทความ (ลองกด ผลิตเดี๋ยวนี้ แล้วรอสักครู่)</div>'; return; }
          box.innerHTML = '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>บทความ (AI เขียนจริง)</th><th class="center">สถานะ</th><th class="right">คำ</th><th class="center">ลิงก์</th></tr></thead><tbody>' +
            arts.map(function (a) {
              return '<tr><td class="tbl-title">' + esc(a.title) + '</td>' +
                '<td class="center">' + ui.badge(esc(a.status), a.status === 'published' ? 'green' : '') + '</td>' +
                '<td class="num">' + (a.words || 0) + '</td>' +
                '<td class="center">' + (a.url ? '<a href="' + esc(a.url) + '" target="_blank">เปิด</a>' : '—') + '</td></tr>';
            }).join('') + '</tbody></table></div>';
        }).catch(function (e) { box.innerHTML = '<div class="soft small">โหลดไม่ได้: ' + esc(e.message || String(e)) + '</div>'; });
      };
    });
  }

  function liveGenCard() {
    var opts = RP.data.m2.formats.map(function (f) { return '<option>' + esc(f) + '</option>'; }).join('');
    return ui.card({
      title: 'โหมด Live — ผลิตบทความด้วย AI จริง', sub: 'ยิงไปที่ LLM (Claude/GPT/Gemini) ผ่าน backend', cls: 'mb',
      action: RP.api.enabled() ? ui.badge('● Live เปิด', 'green') : ui.badge('Live ปิด', 'amber'),
      body:
        '<div class="row wrap" style="gap:10px">' +
        '<div class="field" style="flex:1;min-width:240px"><span class="ico">✍️</span><input id="m2_topic" placeholder="หัวข้อบทความ เช่น ครีมกันแดดหน้าไม่วอก สำหรับผิวมัน"></div>' +
        '<select class="select" id="m2_fmt">' + opts + '</select>' +
        '<button class="btn btn-primary" id="m2_gen">ผลิตด้วย AI สด</button></div>' +
        '<div class="hint" style="margin-top:10px">ยิงไปที่ LLM จริงตามสูตร AEO (Answer-First 40–60 คำ + H2/H3 + FAQ) — ต้องเปิดโหมด Live + รัน backend + ตั้งคีย์ LLM ก่อน</div>'
    });
  }

  function genModal(res) {
    ui.modal({ title: 'บทความที่ผลิตด้วย AI (Live)', sub: 'โมเดล: ' + esc(res.provider || '') + ' · ' + esc(res.model || ''), width: 860,
      body: '<div class="note-box mb">ตัวอย่างผลลัพธ์จริงจาก LLM — พร้อมส่งต่อเข้าคิว/เผยแพร่ (M4)</div>' +
        '<div style="border:1px solid var(--border);border-radius:12px;padding:16px;max-height:52vh;overflow:auto">' + (res.html || '<span class="soft">ไม่มีเนื้อหา</span>') + '</div>' });
  }
})(window.RP);
