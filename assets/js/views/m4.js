(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  function curProj() {
    var proj = RP.data && RP.data.project;
    var list = (proj && proj.list) || [];
    if (RP.isReal()) list = list.filter(function (p) { return p && /^db/.test(String(p.id)); });
    var cur = (proj && proj.current) || '';
    for (var i = 0; i < list.length; i++) if (list[i] && list[i].id === cur) return list[i];
    return list.length ? list[0] : null;
  }
  function dbId(p) {
    if (!p) return null;
    if (typeof p._dbid === 'number') return p._dbid;
    var m = /^db(\d+)$/.exec(String(p.id || ''));
    return m ? parseInt(m[1], 10) : null;
  }

  RP.views.m4 = function () {
    var d = RP.data.m4;

    function modeCard(mode, title, sub) {
      var on = d.mode === mode;
      var style = on
        ? ' style="border:2px solid var(--brand-600); background:var(--surface-2);"'
        : ' style="border:2px solid transparent;"';
      return '' +
        '<div class="panel mode-opt" data-mode="' + esc(mode) + '"' + style + ' role="button" tabindex="0">' +
          '<div class="panel-body">' +
            '<div class="row between wrap gap-s">' +
              '<span class="bb">' + esc(title) + '</span>' +
              (on ? ui.badge('เลือกอยู่', 'green') : ui.badge('แตะเพื่อเลือก', '')) +
            '</div>' +
            '<div class="s soft small">' + esc(sub) + '</div>' +
          '</div>' +
        '</div>';
    }

    function buildModes() {
      return '' +
        '<div class="grid grid-2 mb">' +
          modeCard('auto', 'Full-Auto 100%', 'ระบบเผยแพร่เองทันทีที่ผ่านเกณฑ์คุณภาพ') +
          modeCard('approve', 'Auto + Human Approve', 'ส่งเข้าคิวรออนุมัติทางไลน์/อีเมลก่อนเผยแพร่') +
        '</div>' +
        '<div class="hint">แนะนำเริ่มด้วย <b>Auto + Human Approve</b> — ปลอดภัยกว่าตามหน้าประเมินความเสี่ยง เพราะมีคนตรวจก่อนเผยแพร่จริง</div>' +
        (RP.isReal()
          ? '<div class="hint">หมายเหตุ: การเลือกโหมดในหน้านี้ยังไม่ถูกบันทึกเข้าระบบหลังบ้านในเวอร์ชันนี้ — แจ้งทีมงานเพื่อตั้งค่าโหมดเผยแพร่จริง</div>'
          : '');
    }

    // 1) โหมดเผยแพร่
    var modeCardHtml = ui.card({
      title: 'โหมดเผยแพร่',
      sub: 'เลือกวิธีนำคอนเทนต์ขึ้นเว็บ',
      body: '<div id="rp-m4-modes">' + buildModes() + '</div>'
    });

    // 2) ปลายทางที่เชื่อมต่อ
    var targetRows = (d.targets || []).map(function (t) {
      return '' +
        '<div class="list-row">' +
          '<div class="grow">' +
            '<div class="t bb">' + esc(t.name) + '</div>' +
            '<div class="s soft small">' + esc(t.type) + '</div>' +
          '</div>' +
          ui.badge(t.status, t.ok ? 'green' : 'amber') +
        '</div>';
    }).join('');
    var targetsCardHtml = ui.card({
      title: 'ปลายทางที่เชื่อมต่อ',
      sub: 'เชื่อมต่อ WordPress / Webflow / เว็บลูกค้าผ่าน API',
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'),
      body: RP.realOr(
        targetRows || '<div class="soft small">ยังไม่มีปลายทางที่เชื่อมต่อ</div>',
        {
          title: 'ยังไม่ได้เชื่อมต่อปลายทาง',
          hint: 'เรายังไม่ได้เชื่อมเว็บของคุณเข้ากับระบบ จึงยังไม่มีปลายทางให้แสดง — ทีมงานจะติดตั้ง WordPress REST API / Webflow API ให้ในขั้นตอน onboarding แล้วรายการนี้จะขึ้นเอง'
        }
      )
    });

    // 3) ปฏิทินคอนเทนต์
    var calRows = (d.calendar || []).map(function (c) {
      return '' +
        '<tr>' +
          '<td class="nowrap">' + esc(c.date) + '</td>' +
          '<td class="bb">' + esc(c.title) + '</td>' +
          '<td>' + ui.badge(c.cluster, 'blue') + '</td>' +
          '<td class="num">' + esc(c.time) + '</td>' +
        '</tr>';
    }).join('');
    var calBody = '' +
      '<div class="tbl-wrap"><table class="tbl">' +
        '<thead><tr>' +
          '<th>วันที่</th><th>บทความ</th><th>คลัสเตอร์</th><th class="right">เวลา</th>' +
        '</tr></thead>' +
        '<tbody>' + (calRows || '<tr><td colspan="4" class="center soft">ยังไม่มีตารางเผยแพร่</td></tr>') + '</tbody>' +
      '</table></div>';
    var calendarCardHtml = ui.card({
      title: 'ปฏิทินคอนเทนต์ (Content Calendar)',
      sub: 'ตั้งตารางเผยแพร่ล่วงหน้าอัตโนมัติ',
      flush: !RP.isReal(),
      action: RP.sampleBadge('ตารางตัวอย่าง'),
      body: RP.realOr(calBody, {
        title: 'ยังไม่มีตารางเผยแพร่',
        hint: 'ปฏิทินจะขึ้นหลังจากเชื่อมต่อเว็บปลายทางและอนุมัติแผนคอนเทนต์แล้ว — เราจะไม่แสดงหัวข้อหรือวันที่สมมติ'
      })
    });

    // 4) คิวรออนุมัติ
    function approvalRows() {
      return (d.approval || []).map(function (a, i) {
        return '' +
          '<tr data-row="' + i + '">' +
            '<td>' +
              '<div class="bb">' + esc(a.title) + '</div>' +
              '<div class="soft small">' + ui.badge(a.cluster, 'purple') + '</div>' +
            '</td>' +
            '<td class="num">' + fmt.n(a.words) + ' คำ</td>' +
            '<td class="center">' + ui.scorePill(a.aeo) + '</td>' +
            '<td class="right nowrap" data-cell="act">' +
              '<button class="btn btn-green btn-sm approve" data-idx="' + i + '">✓ อนุมัติ</button> ' +
              '<button class="btn btn-sm">แก้ไข</button>' +
            '</td>' +
          '</tr>';
      }).join('');
    }
    var approvalBody = '' +
      '<div class="tbl-wrap"><table class="tbl">' +
        '<thead><tr>' +
          '<th>บทความ</th><th class="right">จำนวนคำ</th><th class="center">AEO</th><th class="right">การจัดการ</th>' +
        '</tr></thead>' +
        '<tbody>' + (approvalRows() || '<tr><td colspan="4" class="center soft">ไม่มีบทความรออนุมัติ</td></tr>') + '</tbody>' +
      '</table></div>';
    var approvalCardHtml = ui.card({
      title: 'คิวรออนุมัติ',
      sub: 'ตรวจก่อนเผยแพร่ตามโหมด Human Approve',
      flush: !RP.isReal(),
      action: RP.isReal()
        ? ''
        : ui.badge('รออนุมัติ ' + fmt.n(d.pendingCount) + ' บทความ', 'amber') + ' ' + RP.sampleBadge('คิวตัวอย่าง'),
      body: '<div id="approval_slot">' + RP.realOr(approvalBody, {
        title: 'ยังไม่มีบทความรออนุมัติ',
        hint: 'เมื่อระบบร่างบทความให้คุณแล้ว รายการจะขึ้นที่นี่พร้อมจำนวนคำและคะแนน AEO จริง — ตอนนี้ยังไม่มีงานในคิว จึงไม่มีอะไรให้อนุมัติ'
      }) + '</div>'
    });

    // 5) แจ้ง Index
    var pingRows = (d.indexPings || []).map(function (p) {
      return '' +
        '<div class="list-row">' +
          '<div class="grow">' +
            '<div class="t">' + esc(p.url) + '</div>' +
            '<div class="s soft small">' + esc(p.ts) + '</div>' +
          '</div>' +
          (p.ok
            ? '<span class="bb" style="color:var(--green-600, #16a34a);">✓</span>'
            : ui.badge('รอ', 'amber')) +
        '</div>';
    }).join('');
    var indexCardHtml = ui.card({
      title: 'แจ้ง Index (IndexNow / Sitemap Ping)',
      sub: 'แจ้ง Google ทันทีที่เผยแพร่ผ่าน Indexing / Sitemap Ping และ IndexNow',
      action: RP.sampleBadge('ล็อกตัวอย่าง'),
      body: RP.realOr(
        (pingRows || '<div class="soft small">ยังไม่มีการแจ้ง Index</div>'),
        {
          title: 'ยังไม่มีประวัติการแจ้ง Index',
          hint: 'ล็อกนี้จะบันทึกเฉพาะ URL ที่ระบบ ping จริงหลังเผยแพร่ — เมื่อยังไม่มีบทความถูกเผยแพร่ผ่านระบบ จึงยังไม่มีรายการ'
        }
      ) +
        '<div class="note-box mb-l" style="margin-top:12px;">แจ้ง Google ผ่าน Indexing/Sitemap Ping และ IndexNow ทันทีที่บทความถูกเผยแพร่</div>'
    });

    var html =
      ui.pageHead({
        eyebrow: 'M4 · Auto Publisher',
        title: 'เผยแพร่อัตโนมัติ',
        desc: 'เชื่อมต่อเว็บลูกค้าผ่าน API ตั้งตารางเผยแพร่ล่วงหน้า พร้อมแจ้ง Google ทันที และเลือกโหมดอนุมัติได้'
      }) +
      RP.sampleNotice('หน้าเผยแพร่อัตโนมัติ (ปลายทาง ปฏิทิน คิวอนุมัติ และล็อกแจ้ง Index)') +
      RP.collectingNotice('การเชื่อมต่อและการเผยแพร่ของเว็บคุณ') +
      modeCardHtml +
      '<div class="grid grid-2 mb">' + targetsCardHtml + indexCardHtml + '</div>' +
      calendarCardHtml +
      approvalCardHtml;

    return {
      html: html,
      mount: function (root) {
        // 1) โหมดเผยแพร่ — interactive
        var modesWrap = root.querySelector('#rp-m4-modes');

        function wireModes() {
          var opts = modesWrap.querySelectorAll('.mode-opt');
          opts.forEach(function (el) {
            el.onclick = function () {
              var m = el.getAttribute('data-mode');
              if (RP.data.m4.mode === m) return;
              RP.data.m4.mode = m;
              modesWrap.innerHTML = buildModes();
              wireModes();
              var label = m === 'auto' ? 'Full-Auto 100%' : 'Auto + Human Approve';
              ui.toast(RP.isReal()
                ? 'เลือก <b>' + esc(label) + '</b> ไว้ในหน้าจอแล้ว (ยังไม่บันทึกเข้าระบบหลังบ้าน)'
                : 'เปลี่ยนโหมดเป็น <b>' + esc(label) + '</b>');
            };
          });
        }
        if (modesWrap) wireModes();

        // 4) คิวรออนุมัติ (โหมดตัวอย่าง) — จำลองการอนุมัติ
        if (!RP.isReal()) {
          root.querySelectorAll('button.approve').forEach(function (btn) {
            btn.onclick = function () {
              var idx = btn.getAttribute('data-idx');
              var row = root.querySelector('tr[data-row="' + idx + '"]');
              var cell = row ? row.querySelector('[data-cell="act"]') : null;
              if (cell) cell.innerHTML = ui.badge('อนุมัติแล้ว (ตัวอย่าง)', 'green');
              ui.toast('โหมดตัวอย่าง: จำลองการอนุมัติ — ไม่มีการเผยแพร่จริง');
            };
          });
        }

        // 4b) บัญชีจริง: โหลด "บทความรออนุมัติจริง" + ปุ่มอนุมัติที่เผยแพร่จริง
        var pid = RP.isReal() ? dbId(curProj()) : null;
        var slot = root.querySelector('#approval_slot');
        if (pid && RP.api.enabled() && slot) {
          var loadDrafts = function () {
            RP.api.drafts(pid).then(function (res) {
              var ds = (res && res.drafts) || [];
              if (!ds.length) return;   // ไม่มี draft = คงกล่อง "ยังไม่มีบทความรออนุมัติ"
              var rows = ds.map(function (a) {
                return '<tr data-aid="' + a.id + '"><td><div class="bb">' + esc(a.title) + '</div>' +
                  '<div class="soft small">' + (a.cluster ? ui.badge(esc(a.cluster), 'purple') + ' ' : '') +
                  esc(a.description || '') + '</div></td>' +
                  '<td class="num">' + fmt.n(a.words) + ' คำ</td>' +
                  '<td class="center">' + ui.scorePill(a.aeo_score || 0) + '</td>' +
                  '<td class="right nowrap" data-cell="act">' +
                  '<button class="btn btn-green btn-sm rapprove" data-aid="' + a.id + '">✓ อนุมัติ & เผยแพร่</button></td></tr>';
              }).join('');
              slot.innerHTML = '<div class="tbl-wrap"><table class="tbl"><thead><tr>' +
                '<th>บทความ</th><th class="right">จำนวนคำ</th><th class="center">AEO</th><th class="right">การจัดการ</th>' +
                '</tr></thead><tbody>' + rows + '</tbody></table></div>';
              slot.querySelectorAll('button.rapprove').forEach(function (btn) {
                btn.onclick = function () {
                  var aid = btn.getAttribute('data-aid');
                  btn.disabled = true; btn.textContent = 'กำลังเผยแพร่…';
                  RP.api.approveArticle(aid).then(function () {
                    var row = slot.querySelector('tr[data-aid="' + aid + '"] [data-cell="act"]');
                    if (row) row.innerHTML = ui.badge('อนุมัติแล้ว ✓ กำลังเผยแพร่', 'green');
                    ui.toast('อนุมัติแล้ว ✓ ระบบกำลังเผยแพร่ + แจ้ง index + กระจาย');
                    setTimeout(loadDrafts, 1200);
                  }).catch(function (e) {
                    btn.disabled = false; btn.textContent = '✓ อนุมัติ & เผยแพร่';
                    ui.toast('อนุมัติไม่สำเร็จ: ' + esc((e && e.message) || String(e)));
                  });
                };
              });
            }).catch(function () {});
          };
          loadDrafts();
        }
      }
    };
  };
})(window.RP);
