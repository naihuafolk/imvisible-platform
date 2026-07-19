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
        var home = p.public_home || '';
        return '<div class="panel mb"><div class="panel-body">' +
          '<div class="row between wrap" style="gap:8px">' +
          '<div class="bb">' + esc(p.name) + ' <span class="soft small">· ' + esc(p.domain) + ' · โหมด ' + esc(p.mode) +
            ' · ' + esc(p.publish_mode === 'wordpress' ? 'WordPress ลูกค้า' : (p.publish_mode === 'none' ? 'ไม่เผยแพร่' : 'โฮสต์ให้')) + '</span></div>' +
          '<div class="row gap-s">' +
          '<button class="btn btn-sm btn-green rp-grow" data-id="' + p.id + '">🚀 ผลิตเดี๋ยวนี้</button>' +
          '<button class="btn btn-sm rp-arts" data-id="' + p.id + '">ดูบทความจริง</button>' +
          '<button class="btn btn-sm rp-chan" data-id="' + p.id + '">🔗 เชื่อมช่องทาง</button></div></div>' +
          (home ? '<div class="soft small" style="margin-top:6px">🌐 บล็อกที่เราโฮสต์ให้: <a href="' + esc(home) + '" target="_blank">' + esc(home) + '</a></div>' : '') +
          '<div class="rp-arts-out" data-for="' + p.id + '" style="margin-top:8px"></div></div></div>';
      }).join('');
      wireReal(root);
    }).catch(function (e) {
      out.innerHTML = '<div class="hint">โหลดไม่ได้: ' + esc(e.message || String(e)) + ' (ต้องล็อกอินจริง ไม่ใช่บัญชีเดโม)</div>';
    });
  }

  var CH_LABEL = { blog: 'บล็อก', wordpress: 'WordPress', indexnow: 'IndexNow',
    line: 'LINE OA', facebook: 'Facebook', telegram: 'Telegram', x: 'X', linkedin: 'LinkedIn',
    discord: 'Discord', mastodon: 'Mastodon', webhook: 'Webhook', distribution: 'การกระจาย' };

  function distStatus(st) {
    if (st === 'posted') return ui.badge('โพสต์แล้ว', 'green');
    if (st === 'failed') return ui.badge('ล้มเหลว', 'amber');
    if (st === 'skipped') return ui.badge('ข้าม', '');
    return ui.badge(esc(st), '');
  }

  function distTimeline(events) {
    if (!events.length) return '<div class="soft small">ยังไม่มีการกระจาย (บทความนี้อาจยังเป็นร่าง หรือยังไม่ถูกเผยแพร่)</div>';
    return '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ช่องทาง</th><th class="center">สถานะ</th><th>รายละเอียด</th><th class="center">ลิงก์</th></tr></thead><tbody>' +
      events.map(function (e) {
        return '<tr><td class="bb">' + esc(CH_LABEL[e.channel] || e.channel) + '</td>' +
          '<td class="center">' + distStatus(e.status) + '</td>' +
          '<td class="soft small">' + esc(e.detail || '') + '</td>' +
          '<td class="center">' + (e.url ? '<a href="' + esc(e.url) + '" target="_blank">ดู</a>' : '—') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }

  function chStatus(chs, kind) {
    var c = chs.filter(function (x) { return x.kind === kind; })[0];
    return (c && c.connected) ? '<span style="color:var(--green-600);font-weight:700">● เชื่อมแล้ว</span>' : '<span class="soft">○ ยังไม่เชื่อม</span>';
  }

  // นิยามช่องทั้งหมด — [key, label, type, placeholder] · key = token | ref
  var CH_DEFS = [
    { kind: 'telegram', name: 'Telegram', note: 'ฟรี · ง่ายสุด ⭐',
      fields: [['token', 'Bot Token', 'password', 'วางโทเคนจาก @BotFather'], ['ref', 'ปลายทาง', 'text', 'chat_id หรือ @channelname']] },
    { kind: 'line', name: 'LINE OA', note: 'ฟรี',
      fields: [['token', 'Channel Access Token', 'password', 'วางโทเคน (เว้นว่าง=คงเดิม)'], ['ref', 'ปลายทาง', 'text', 'userId/groupId หรือ broadcast']] },
    { kind: 'facebook', name: 'Facebook Page', note: 'ฟรี · ต้อง App Review',
      fields: [['ref', 'Page ID', 'text', 'เลข Page ID'], ['token', 'Page Access Token', 'password', 'วางโทเคน (เว้นว่าง=คงเดิม)']] },
    { kind: 'discord', name: 'Discord', note: 'ฟรี · webhook',
      fields: [['token', 'Webhook URL', 'password', 'https://discord.com/api/webhooks/...']] },
    { kind: 'mastodon', name: 'Mastodon', note: 'ฟรี',
      fields: [['ref', 'Instance', 'text', 'เช่น mastodon.social'], ['token', 'Access Token', 'password', 'วางโทเคน']] },
    { kind: 'x', name: 'X (Twitter)', note: 'API เสียเงิน ~$100/เดือน',
      fields: [['token', 'OAuth2 User Token', 'password', 'ต้องมีสิทธิ์ tweet.write']] },
    { kind: 'linkedin', name: 'LinkedIn', note: 'ต้องขออนุมัติ',
      fields: [['ref', 'Author URN', 'text', 'urn:li:person:xxx หรือ urn:li:organization:xxx'], ['token', 'Access Token', 'password', 'วางโทเคน']] },
    { kind: 'webhook', name: 'Webhook (Zapier/Make)', note: 'ต่อไปได้ทุกที่ · IG/TikTok/Pinterest ผ่าน Zapier',
      fields: [['token', 'Webhook URL', 'password', 'https://hooks.zapier.com/... (https เท่านั้น)']] }
  ];

  function channelModal(pid) {
    RP.api.getChannels(pid).then(function (r) { openChannelModal(pid, r.channels || []); })
      .catch(function (e) { RP.ui.toast('โหลดช่องทางไม่ได้: ' + esc(e.message || String(e))); openChannelModal(pid, []); });
  }

  function openChannelModal(pid, chs) {
    function fInput(kind, f) {
      var id = 'ch_' + kind + '_' + f[0];
      return '<div style="margin-bottom:8px"><div class="soft small" style="margin-bottom:3px">' + esc(f[1]) + '</div>' +
        '<input class="input" id="' + id + '" type="' + f[2] + '" placeholder="' + esc(f[3]) + '" style="width:100%"></div>';
    }
    var body = '<div class="hint mb">เชื่อมโซเชียล<strong>ของคุณเอง</strong> → บทความใหม่โพสต์ขึ้นทุกช่องอัตโนมัติ (โทเคน<strong>เข้ารหัสเก็บ</strong> · เว้นว่าง=คงเดิม · ไม่ยิงสแปม)</div>' +
      CH_DEFS.map(function (d) {
        return '<div class="panel mb"><div class="panel-head">' + esc(d.name) +
          ' <span class="soft small">· ' + esc(d.note) + '</span> · ' + chStatus(chs, d.kind) + '</div><div class="panel-body">' +
          d.fields.map(function (f) { return fInput(d.kind, f); }).join('') +
          '<button class="btn btn-primary btn-sm ch-save" data-kind="' + d.kind + '">บันทึก ' + esc(d.name) + '</button></div></div>';
      }).join('');
    ui.modal({ title: 'เชื่อมช่องทางกระจาย (8 ช่อง)', sub: 'โพสต์บทความใหม่ขึ้นทุกช่องของคุณอัตโนมัติ', width: 640, body: body });
    Array.prototype.forEach.call(document.querySelectorAll('.ch-save'), function (b) {
      b.onclick = function () {
        var kind = b.getAttribute('data-kind');
        var tokEl = document.getElementById('ch_' + kind + '_token');
        var refEl = document.getElementById('ch_' + kind + '_ref');
        b.disabled = true; b.textContent = 'บันทึก…';
        RP.api.setChannel(pid, { kind: kind, token: tokEl ? (tokEl.value || '') : '',
                                 ref: refEl ? (refEl.value || '').trim() : '', enabled: true })
          .then(function () { b.disabled = false; b.textContent = 'บันทึกแล้ว ✓'; RP.ui.toast('บันทึกช่อง ' + kind + ' แล้ว ✓'); })
          .catch(function (e) { b.disabled = false; b.textContent = 'ลองอีกครั้ง'; RP.ui.toast('บันทึกไม่ได้: ' + esc(e.message || String(e))); });
      };
    });
  }

  function wireReal(root) {
    Array.prototype.forEach.call(root.querySelectorAll('.rp-grow'), function (b) {
      b.onclick = function () {
        RP.ui.toast('สั่งระบบผลิตคอนเทนต์…');
        RP.api.grow(b.getAttribute('data-id'))
          .then(function () { RP.ui.toast('เข้าคิวแล้ว ✓ ระบบกำลังขุด→เขียน→เผยแพร่→กระจาย (กด "ดูบทความจริง" อีกสักครู่)'); })
          .catch(function (e) { RP.ui.toast('สั่งไม่ได้: ' + esc(e.message || String(e))); });
      };
    });
    Array.prototype.forEach.call(root.querySelectorAll('.rp-chan'), function (b) {
      b.onclick = function () { channelModal(b.getAttribute('data-id')); };
    });
    Array.prototype.forEach.call(root.querySelectorAll('.rp-arts'), function (b) {
      b.onclick = function () {
        var id = b.getAttribute('data-id');
        var box = root.querySelector('.rp-arts-out[data-for="' + id + '"]');
        box.innerHTML = '<div class="soft small">กำลังโหลด…</div>';
        RP.api.projectArticles(id).then(function (res) {
          var arts = res.articles || [];
          if (!arts.length) { box.innerHTML = '<div class="soft small">ยังไม่มีบทความ (ลองกด ผลิตเดี๋ยวนี้ แล้วรอสักครู่)</div>'; return; }
          box.innerHTML = '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>บทความ (AI เขียนจริง)</th><th class="center">สถานะ</th><th class="right">คำ</th><th class="center">ลิงก์</th><th class="center">กระจาย</th></tr></thead><tbody>' +
            arts.map(function (a) {
              return '<tr><td class="tbl-title">' + esc(a.title) + '</td>' +
                '<td class="center">' + ui.badge(esc(a.status), a.status === 'published' ? 'green' : '') + '</td>' +
                '<td class="num">' + (a.words || 0) + '</td>' +
                '<td class="center">' + (a.url ? '<a href="' + esc(a.url) + '" target="_blank">เปิด</a>' : '—') + '</td>' +
                '<td class="center"><button class="btn btn-sm rp-dist" data-id="' + a.id + '">ดู Log</button></td></tr>';
            }).join('') + '</tbody></table></div><div class="rp-dist-panel" style="margin-top:10px"></div>';
          var panel = box.querySelector('.rp-dist-panel');
          Array.prototype.forEach.call(box.querySelectorAll('.rp-dist'), function (db2) {
            db2.onclick = function () {
              var aid = db2.getAttribute('data-id');
              panel.innerHTML = '<div class="soft small">กำลังโหลด Log การกระจาย…</div>';
              RP.api.articleDistribution(aid).then(function (r) {
                panel.innerHTML = '<div class="bb" style="margin:8px 0">📡 การกระจายของบทความนี้ ' +
                  '<button class="btn btn-sm rp-redist" data-id="' + aid + '" style="margin-left:8px">กระจายซ้ำ</button></div>' +
                  distTimeline(r.events || []);
                var rd = panel.querySelector('.rp-redist');
                if (rd) rd.onclick = function () {
                  rd.disabled = true; rd.textContent = 'เข้าคิว…';
                  RP.api.redistribute(aid).then(function () { RP.ui.toast('สั่งกระจายซ้ำแล้ว ✓ กด "ดู Log" อีกครั้งสักครู่'); })
                    .catch(function (e) { rd.disabled = false; rd.textContent = 'กระจายซ้ำ'; RP.ui.toast('กระจายไม่ได้: ' + esc(e.message || String(e))); });
                };
              }).catch(function (e) { panel.innerHTML = '<div class="soft small">โหลด Log ไม่ได้: ' + esc(e.message || String(e)) + '</div>'; });
            };
          });
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
