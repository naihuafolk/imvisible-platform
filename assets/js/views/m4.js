(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

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
        '<div class="hint">แนะนำเริ่มด้วย <b>Auto + Human Approve</b> — ปลอดภัยกว่าตามหน้าประเมินความเสี่ยง เพราะมีคนตรวจก่อนเผยแพร่จริง</div>';
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
      body: targetRows || '<div class="soft small">ยังไม่มีปลายทางที่เชื่อมต่อ</div>'
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
      flush: true,
      body: calBody
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
      flush: true,
      action: ui.badge('รออนุมัติ ' + fmt.n(d.pendingCount) + ' บทความ', 'amber'),
      body: approvalBody
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
      body: (pingRows || '<div class="soft small">ยังไม่มีการแจ้ง Index</div>') +
        '<div class="note-box mb-l" style="margin-top:12px;">แจ้ง Google ผ่าน Indexing/Sitemap Ping และ IndexNow ทันทีที่บทความถูกเผยแพร่</div>'
    });

    var html =
      ui.pageHead({
        eyebrow: 'M4 · Auto Publisher',
        title: 'เผยแพร่อัตโนมัติ',
        desc: 'เชื่อมต่อเว็บลูกค้าผ่าน API ตั้งตารางเผยแพร่ล่วงหน้า พร้อมแจ้ง Google ทันที และเลือกโหมดอนุมัติได้'
      }) +
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
              ui.toast('เปลี่ยนโหมดเป็น <b>' + esc(label) + '</b>');
            };
          });
        }
        if (modesWrap) wireModes();

        // 4) คิวรออนุมัติ — approve buttons
        root.querySelectorAll('button.approve').forEach(function (btn) {
          btn.onclick = function () {
            var idx = btn.getAttribute('data-idx');
            var row = root.querySelector('tr[data-row="' + idx + '"]');
            var cell = row ? row.querySelector('[data-cell="act"]') : null;
            if (cell) cell.innerHTML = ui.badge('อนุมัติแล้ว', 'green');
            ui.toast('อนุมัติและส่งเข้าคิวเผยแพร่แล้ว ✓');
          };
        });
      }
    };
  };
})(window.RP);
