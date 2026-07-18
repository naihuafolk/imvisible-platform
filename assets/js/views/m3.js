(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  RP.views.m3 = function () {
    var d = (RP.data && RP.data.m3) || {};
    var schema = d.schema || [];
    var llmsTxt = d.llmsTxt || {};
    var sitemap = d.sitemap || {};
    var internalLinks = d.internalLinks || {};
    var freshness = d.freshness || [];
    var audit = d.audit || [];

    var avgPct = schema.length
      ? Math.round(RP.sum(schema, function (s) { return s.pct || 0; }) / schema.length)
      : 0;

    var html = ui.pageHead({
      eyebrow: 'M3 · AEO Optimizer',
      title: 'AEO Optimizer',
      desc: 'เครื่องยนต์ติดคำตอบ — ใส่ Schema อัตโนมัติ, ดูแล llms.txt/Sitemap, สร้าง Topical Authority และรีเฟรชความสดของเนื้อหาให้ติดอันดับใน AI Answer'
    }) + '';

    // 1) KPI ROW
    html += '<div class="grid grid-4 mb">';
    html += ui.kpi({
      label: 'Schema ครอบคลุมเฉลี่ย',
      value: avgPct + '%',
      tone: 'brand',
      foot: 'ครอบคลุม ' + fmt.n(schema.length) + ' ชนิดเนื้อหา'
    });
    html += ui.kpi({
      label: 'llms.txt',
      value: fmt.n(llmsTxt.entries || 0) + ' รายการ',
      foot: 'อัปเดต ' + esc(llmsTxt.updated || '-')
    });
    html += ui.kpi({
      label: 'Sitemap URLs',
      value: fmt.n(sitemap.urls || 0),
      foot: sitemap.submitted ? 'ส่งเข้าระบบแล้ว' : 'ยังไม่ได้ส่ง'
    });
    html += ui.kpi({
      label: 'Internal Links',
      value: fmt.n(internalLinks.total || 0),
      foot: 'เฉลี่ย ' + esc(String(internalLinks.avgPerPage || 0)) + '/หน้า'
    });
    html += '</div>';

    // 2) SCHEMA COVERAGE CARD
    var schemaBody = '';
    if (schema.length) {
      schema.forEach(function (s) {
        var pct = fmt.clamp(s.pct || 0, 0, 100);
        schemaBody +=
          '<div class="list-row">' +
            '<span class="t b nowrap">' + esc(s.t) + '</span>' +
            '<div class="grow">' + ui.bar(pct) + '</div>' +
            '<span class="s right nowrap">' + fmt.n(s.pages || 0) + '/' + fmt.n(s.total || 0) +
              ' (' + pct + '%)</span>' +
          '</div>';
      });
    } else {
      schemaBody = '<div class="soft small center">ยังไม่มีข้อมูล Schema</div>';
    }
    html += ui.card({
      title: 'ความครอบคลุม Schema Markup',
      sub: 'ใส่ schema อัตโนมัติตามชนิดเนื้อหา (FAQPage, HowTo, Article, Author, Organization, Product)',
      body: schemaBody,
      cls: 'mb'
    });

    // 3) TWO-COL: files/links + technical audit
    html += '<div class="grid grid-2 mb">';

    // 3a) llms.txt · Sitemap · Internal Link
    var filesBody = '';
    filesBody +=
      '<div class="list-row">' +
        '<span class="t b">llms.txt</span>' +
        '<div class="grow s soft">อัปเดต ' + esc(llmsTxt.updated || '-') + '</div>' +
        '<span class="right">' + ui.badge('อัปเดตแล้ว', 'green') + '</span>' +
      '</div>';
    filesBody +=
      '<div class="list-row">' +
        '<span class="t b">Sitemap</span>' +
        '<div class="grow s soft">' + fmt.n(sitemap.urls || 0) + ' URLs</div>' +
        '<span class="right">' + (sitemap.submitted ? ui.badge('ส่งแล้ว', 'green') : ui.badge('ยังไม่ส่ง', 'amber')) + '</span>' +
      '</div>';
    filesBody +=
      '<div class="list-row">' +
        '<span class="t b">Internal Links</span>' +
        '<div class="grow s soft">Topical Authority ภายใน Topic Cluster</div>' +
        '<span class="right b">' + fmt.n(internalLinks.total || 0) + '</span>' +
      '</div>';
    var orphan = internalLinks.orphan || 0;
    filesBody +=
      '<div class="list-row">' +
        '<span class="t b">หน้ากำพร้า (Orphan)</span>' +
        '<div class="grow s soft">หน้าที่ยังไม่มีลิงก์ภายในชี้ถึง</div>' +
        '<span class="right">' + (orphan > 0
          ? ui.badge(fmt.n(orphan) + ' หน้า', 'amber')
          : ui.badge('0 หน้า', 'green')) + '</span>' +
      '</div>';
    html += ui.card({
      title: 'llms.txt · Sitemap · Internal Link',
      sub: 'ทำให้เว็บอ่านง่ายสำหรับ AI Crawler และสร้าง Topical Authority',
      body: filesBody
    });

    // 3b) Technical SEO Audit
    var auditBody = '';
    if (audit.length) {
      audit.forEach(function (a) {
        var mark = a.ok === true
          ? '<span class="b" style="color:var(--green,#16a34a)">✓</span>'
          : '<span class="b" style="color:var(--amber,#d97706)">⚠</span>';
        auditBody +=
          '<div class="list-row">' +
            '<span class="t b">' + esc(a.t) + '</span>' +
            '<div class="grow s soft right">' + esc(String(a.val)) + '</div>' +
            '<span class="right nowrap">' + mark + '</span>' +
          '</div>';
      });
    } else {
      auditBody = '<div class="soft small center">ยังไม่มีผล Audit</div>';
    }
    html += ui.card({
      title: 'Technical SEO Audit',
      sub: 'ตรวจอัตโนมัติ: ความเร็ว, Core Web Vitals, Mobile, Index Coverage',
      body: auditBody
    });

    html += '</div>';

    // 4) FRESHNESS ENGINE (flush table)
    var rows = '';
    if (freshness.length) {
      freshness.forEach(function (f) {
        rows +=
          '<tr>' +
            '<td>' + esc(f.title) + '</td>' +
            '<td class="num">' + esc(String(f.age)) + '</td>' +
            '<td class="center">' + ui.badge(esc(f.due), 'amber') + '</td>' +
            '<td class="right">' + ui.badge(esc(f.act), 'purple') + '</td>' +
          '</tr>';
      });
    } else {
      rows = '<tr><td colspan="4" class="center soft">ทุกหน้ายังสดใหม่ ไม่มีหน้าที่ต้องรีเฟรช</td></tr>';
    }
    var freshBody =
      '<div class="tbl-wrap"><table class="tbl">' +
        '<thead><tr>' +
          '<th>หน้า</th>' +
          '<th class="num">อายุ</th>' +
          '<th class="center">สถานะ</th>' +
          '<th class="right">การทำงาน</th>' +
        '</tr></thead>' +
        '<tbody>' + rows + '</tbody>' +
      '</table></div>' +
      '<div class="hint">Freshness Engine ตรวจอายุทุกหน้า หน้าไหนใกล้ครบ 3–6 เดือน ระบบจะรีเฟรชเนื้อหา/ตัวเลข/ปี พ.ศ. ให้อัตโนมัติ ' +
        'ความสดใหม่ของเนื้อหาสำคัญมากต่อการถูกอ้างอิงโดย AI — 83% ของ Citation มาจากหน้าที่อัปเดตภายใน 12 เดือน</div>';
    html += ui.card({
      title: 'Freshness Engine',
      sub: 'รีเฟรชหน้าที่ใกล้ครบ 3–6 เดือนอัตโนมัติ',
      action: ui.badge('83% ของ Citation มาจากหน้าที่อัปเดตใน 12 เดือน', 'blue'),
      body: freshBody,
      flush: true
    });

    return { html: html, mount: null };
  };
})(window.RP);
