(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  /* ---- โปรเจ็คปัจจุบัน (บัญชีจริงเห็นเฉพาะโปรเจ็คจากฐานข้อมูล id=db*) ---- */
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

  function gcolor(g) { return g === 'A' ? 'green' : g === 'B' ? 'blue' : g === 'C' ? 'amber' : 'red'; }

  /* ---- พาเนลคะแนน AEO/SEO (ตัวชูโรง) — ตัวแปรจัดอันดับที่วัดจากบทความจริง ---- */
  function aeoPanel(dd, actions) {
    var sc = dd.avg_score;
    var ring = '<div class="ring" style="--p:' + (sc == null ? 0 : sc) + '"><span class="ring-val">' +
      (sc == null ? '—' : sc) + '</span></div>';
    var dist = ['A', 'B', 'C', 'D'].map(function (g) {
      return '<span class="badge ' + gcolor(g) + '">' + g + ' × ' + ((dd.grade_dist || {})[g] || 0) + '</span>';
    }).join(' ');
    var fixes = (dd.top_fixes || []).map(function (f) {
      return '<div class="list-row"><span class="t b nowrap">' + esc(f.label) + '</span>' +
        '<div class="grow s soft">' + esc(f.fix || '') + '</div>' +
        '<span class="right"><span class="badge purple">+' + f.gain + ' แต้มรวม</span></span></div>';
    }).join('') || '<div class="soft small center" style="padding:10px">ทุกปัจจัยผ่านครบแล้ว 🎉</div>';
    var arts = (dd.articles || []).slice(0, 10).map(function (a) {
      var boost = (actions && a.score < 85 && typeof a.id === 'number')
        ? ' <button class="btn btn-sm" data-opt="' + a.id + '" title="ป้อนจุดอ่อนกลับให้ AI เขียนซ่อม ดันคะแนน">🔧 ดันคะแนน</button>' : '';
      return '<div class="list-row"><span class="t b nowrap">' + esc(a.title) + '</span>' +
        '<div class="grow"></div><span class="right"><span class="badge ' + gcolor(a.grade) + '">' +
        a.score + ' · ' + a.grade + '</span>' + boost + '</span></div>';
    }).join('');
    return '<div class="row" style="gap:22px;align-items:center;flex-wrap:wrap">' + ring +
      '<div style="flex:1;min-width:210px"><div class="soft small">คะแนนเฉลี่ยทั้งโปรเจ็ค (' + (dd.count || 0) + ' บทความ)</div>' +
      '<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">' + dist + '</div>' +
      '<div class="hint" style="margin-top:8px">' + esc(dd.note || '') + '</div></div></div>' +
      '<div class="divider"></div>' +
      '<div class="soft small b" style="margin:8px 0">🔧 แก้ตรงนี้ได้คะแนนรวมมากสุด (จัดลำดับให้ติดเร็ว)</div>' + fixes +
      (arts ? ('<div class="divider"></div><div class="soft small b" style="margin:8px 0">คะแนนต่อบทความ</div>' + arts) : '');
  }

  var SAMPLE_AEO = {
    count: 12, avg_score: 78, grade_dist: { A: 4, B: 5, C: 2, D: 1 },
    note: 'คะแนนวัดจากปัจจัยจัดอันดับจริงของแต่ละบทความ',
    top_fixes: [
      { label: 'ส่วนคำถามที่พบบ่อย + FAQPage schema', fix: 'เพิ่ม H2 "คำถามที่พบบ่อย" 4-8 ข้อ + ฝัง FAQPage JSON-LD', gain: 18 },
      { label: 'ลิงก์ภายในบทความ', fix: 'ลิงก์ไปบทความอื่นในคลัสเตอร์ 2-4 จุด', gain: 9 },
      { label: 'ความลึกของเนื้อหา', fix: 'เพิ่มตัวเลข/ราคา/ตัวอย่าง อุด content gap', gain: 6 }
    ],
    articles: [
      { title: 'AEO คืออะไร ต่างจาก SEO อย่างไร', score: 92, grade: 'A' },
      { title: 'ครีมกันแดดหน้าไม่วอก ยี่ห้อไหนดี', score: 74, grade: 'B' },
      { title: 'วิธีเลือกคลินิกเลเซอร์หน้าใส', score: 58, grade: 'C' }
    ]
  };

  function aeoScoreCard() {
    return ui.card({
      title: '⚡ AEO/SEO Score Engine — ตัวแปรที่ทำให้ติดเร็ว',
      sub: 'วัดปัจจัยจัดอันดับจริงของทุกบทความ (answer-first · FAQ/schema · ลิงก์ภายใน · ความลึก · คีย์เวิร์ด · ความสด) แล้วบอกว่าจะดันคะแนนยังไง',
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'), cls: 'mb',
      body: RP.realOr(aeoPanel(SAMPLE_AEO), {
        title: 'ยังไม่มีบทความให้ให้คะแนน',
        hint: 'สร้าง/ผลิตบทความในโปรเจ็คนี้ก่อน ระบบจะวัดคะแนน AEO/SEO จริงจากบทความแต่ละชิ้น (ปัจจัยจัดอันดับ 14 ตัว) แล้วบอกว่าปรับตรงไหนได้อันดับเร็วที่สุด'
      })
    });
  }

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

    // แถบกำกับสถานะข้อมูล (ตัวอย่าง vs บัญชีจริงที่ยังไม่มีผลสแกน)
    html += RP.sampleNotice('หน้า AEO Optimizer นี้');
    html += RP.collectingNotice('จากการสแกนเว็บไซต์ของคุณ');

    // ⚡ ตัวชูโรง: คะแนน AEO/SEO จริง (เติมข้อมูลจริงตอน mount ถ้าเป็นบัญชีจริง)
    html += '<div id="aeo_score_slot">' + aeoScoreCard() + '</div>';

    // 1) KPI ROW
    var kpiSample = '<div class="grid grid-4 mb">' +
      ui.kpi({
        label: 'Schema ครอบคลุมเฉลี่ย',
        value: avgPct + '%',
        tone: 'brand',
        foot: 'ครอบคลุม ' + fmt.n(schema.length) + ' ชนิดเนื้อหา'
      }) +
      ui.kpi({
        label: 'llms.txt',
        value: fmt.n(llmsTxt.entries || 0) + ' รายการ',
        foot: 'อัปเดต ' + esc(llmsTxt.updated || '-')
      }) +
      ui.kpi({
        label: 'Sitemap URLs',
        value: fmt.n(sitemap.urls || 0),
        foot: sitemap.submitted ? 'ส่งเข้าระบบแล้ว' : 'ยังไม่ได้ส่ง'
      }) +
      ui.kpi({
        label: 'Internal Links',
        value: fmt.n(internalLinks.total || 0),
        foot: 'เฉลี่ย ' + esc(String(internalLinks.avgPerPage || 0)) + '/หน้า'
      }) +
      '</div>';

    var kpiBlock = RP.realOr(kpiSample, {
      title: 'ยังไม่มีข้อมูล',
      hint: 'ตัวเลขสรุป (Schema, llms.txt, Sitemap, Internal Links) จะขึ้นหลังระบบสแกนเว็บไซต์ของคุณครบรอบแรก — เชื่อมต่อโดเมนและกดสแกนก่อน เราจะไม่แสดงตัวเลขสมมติ'
    });
    if (RP.isReal()) kpiBlock = ui.card({ cls: 'mb', body: kpiBlock });
    html += kpiBlock;

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
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'),
      body: RP.realOr(schemaBody, {
        title: 'ยังไม่มีข้อมูล Schema',
        hint: 'เรายังไม่ได้อ่านโค้ดหน้าเว็บของคุณ เปอร์เซ็นต์ความครอบคลุมจะขึ้นหลังระบบ crawl เว็บไซต์เสร็จ (ปกติใช้เวลาไม่กี่นาทีถึง 1 วันตามจำนวนหน้า)'
      }),
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
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'),
      body: RP.realOr(filesBody, {
        title: 'ยังไม่มีข้อมูลไฟล์และลิงก์ภายใน',
        hint: 'สถานะ llms.txt, จำนวน URL ใน Sitemap, จำนวนลิงก์ภายใน และหน้ากำพร้า จะแสดงหลังระบบตรวจเว็บไซต์ของคุณจริง — ตอนนี้เรายังไม่ได้ตรวจ จึงไม่มีตัวเลขให้แสดง'
      })
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
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'),
      body: RP.realOr(auditBody, {
        title: 'ยังไม่ได้ตรวจเว็บไซต์ของคุณ',
        hint: 'ค่า LCP / Core Web Vitals / Mobile-friendly / Index Coverage ต้องวัดจากหน้าเว็บจริง ระบบจะแสดงผลหลังรันการตรวจครั้งแรกเสร็จ เราไม่แสดงคะแนนที่ยังไม่ได้วัด'
      })
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
    var freshEmpty = {
      title: 'ยังไม่มีคิวรีเฟรช',
      hint: 'รายการนี้จะขึ้นเมื่อระบบรู้จักหน้าเว็บของคุณและเริ่มนับอายุเนื้อหาได้ — เชื่อมต่อเว็บไซต์/Sitemap ก่อน แล้วหน้าที่ใกล้ครบ 3–6 เดือนจะถูกจัดคิวให้อัตโนมัติ'
    };
    html += ui.card({
      title: 'Freshness Engine',
      sub: 'รีเฟรชหน้าที่ใกล้ครบ 3–6 เดือนอัตโนมัติ',
      action: RP.isReal()
        ? ''
        : (RP.sampleBadge('ข้อมูลตัวอย่าง') + ui.badge('83% ของ Citation มาจากหน้าที่อัปเดตใน 12 เดือน', 'blue')),
      body: RP.realOr(freshBody, freshEmpty),
      flush: !RP.isReal()
    });

    return {
      html: html,
      mount: function (root) {
        // บัญชีจริง: ดึงคะแนน AEO/SEO จริงของทั้งโปรเจ็คมาแทนพาเนลตัวอย่าง
        var p = curProj();
        var pid = RP.isReal() ? dbId(p) : null;
        if (!pid || !RP.api.enabled()) return;
        var slot = root.querySelector('#aeo_score_slot');
        if (!slot) return;
        RP.api.projectAeo(pid).then(function (dd) {
          if (dd && dd.count) {
            slot.innerHTML = ui.card({
              title: '⚡ AEO/SEO Score Engine — ตัวแปรที่ทำให้ติดเร็ว',
              sub: 'วัดปัจจัยจัดอันดับจริงของทุกบทความในโปรเจ็คนี้ แล้วจัดลำดับสิ่งที่ควรแก้',
              cls: 'mb', body: aeoPanel(dd, true)
            });
            // ปุ่ม "ดันคะแนน" ต่อบทความ → ป้อนจุดอ่อนกลับให้เครื่องยนต์เขียนซ่อม (เข้าคิว)
            Array.prototype.forEach.call(slot.querySelectorAll('[data-opt]'), function (btn) {
              btn.onclick = function () {
                var aid = parseInt(btn.getAttribute('data-opt'), 10);
                btn.disabled = true; btn.textContent = 'เข้าคิวแล้ว…';
                RP.api.articleOptimize(aid).then(function () {
                  RP.ui.toast('เริ่มดันคะแนนแล้ว ✓ ระบบจะเขียนซ่อมเบื้องหลัง แล้วอัปเดตคะแนนให้');
                }).catch(function (e) {
                  btn.disabled = false; btn.textContent = '🔧 ดันคะแนน';
                  RP.ui.toast('สั่งไม่สำเร็จ: ' + RP.esc((e && e.message) || String(e)));
                });
              };
            });
          }
        }).catch(function () {});
      }
    };
  };
})(window.RP);
