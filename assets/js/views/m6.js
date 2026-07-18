(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  RP.views.m6 = function () {
    var d = (RP.data && RP.data.m6) || {};
    var insights = d.insights || [];
    var actions = d.actions || [];
    var wr = d.weeklyReport || {};
    var loop = (RP.data && RP.data.loop) || [];

    var html = ui.pageHead({
      eyebrow: 'M6 · Learning Loop',
      title: 'Learning Loop — สมองของระบบ',
      desc: 'วงจร Closed-Loop ที่ทำให้ระบบฉลาดขึ้นทุกรอบ: เรียนรู้จากผลจริงแล้วปรับการผลิตรอบถัดไปเอง'
    }) + '';

    // 1) เกริ่นนำ — สมองของระบบ
    html += '<div class="note-box purple mb">' +
      '<div class="text b">M6 คือ “สมองของระบบ”</div>' +
      '<div class="text soft small">ระบบเรียนรู้จากผลจริงว่าอะไรทำให้หน้าติด Citation/อันดับดี (ความยาว โครงสร้าง ชนิด Schema หัวข้อ ฯลฯ) ' +
      'แล้วปรับเทมเพลตการผลิตคอนเทนต์และลำดับความสำคัญของคิวงานรอบถัดไป<b> โดยอัตโนมัติ ไม่ต้องมีคนคอยวิเคราะห์</b> — ' +
      'ครบวงจร Discover → Create → Optimize → Publish → Measure → Learn แล้ววนกลับ</div>' +
    '</div>';

    // 2) Insights
    var insBody = '<div class="grid grid-2">';
    for (var i = 0; i < insights.length; i++) {
      var it = insights[i] || {};
      insBody += '<div class="panel"><div class="panel-body">' +
        '<div class="text soft small">' + esc(it.t || '') + '</div>' +
        '<div class="text bb" style="font-size:20px;color:var(--purple-700)">' + esc(it.v || '') + '</div>' +
        '<div class="text soft small">' + esc(it.note || '') + '</div>' +
      '</div></div>';
    }
    insBody += '</div>';
    html += ui.card({
      title: 'สิ่งที่ระบบเรียนรู้ (Insights)',
      sub: 'ลักษณะร่วมของหน้าที่ติด Citation/อันดับดี',
      body: insBody,
      cls: 'mb'
    });

    // 3) Auto-Tuning
    var actBody = '';
    for (var a = 0; a < actions.length; a++) {
      var ac = actions[a] || {};
      var okFlag = !!ac.ok;
      actBody += '<div class="list-row row between wrap">' +
        '<div class="grow">' +
          '<div class="t">' + esc(ac.t || '') + '</div>' +
          '<div class="s soft">' + esc(ac.when || '') + '</div>' +
        '</div>' +
        ui.badge(okFlag ? 'ปรับแล้ว' : 'กำลังรอผล', okFlag ? 'green' : 'amber') +
      '</div>';
    }
    html += ui.card({
      title: 'การปรับอัตโนมัติรอบถัดไป (Auto-Tuning)',
      sub: 'ระบบปรับเทมเพลต + ลำดับความสำคัญของคิวงานเองตามสิ่งที่เรียนรู้',
      body: actBody,
      flush: true,
      cls: 'mb'
    });

    // 4) รายงานสรุปรายสัปดาห์
    var humanHrs = (wr.humanHours != null) ? wr.humanHours : 0;
    var autoTone = (humanHrs < 2) ? 'pos' : '';
    var repBody = '<div class="grid grid-3">' +
      ui.kpi({ label: 'เผยแพร่บทความ', value: fmt.n(wr.published || 0) + ' บทความ', tone: 'brand' }) +
      ui.kpi({ label: 'ติดหน้า 1 ใหม่', value: fmt.n(wr.newPage1 || 0) + ' คีย์เวิร์ด', tone: 'pos', foot: 'ขึ้นหน้าแรกในรอบสัปดาห์' }) +
      ui.kpi({ label: 'Citation เพิ่ม', value: '+' + fmt.n(wr.citationsGained || 0), tone: 'brand', foot: 'ถูกอ้างอิงโดย AI Answer เพิ่มขึ้น' }) +
      ui.kpi({ label: 'รีเฟรชหน้าเก่า', value: fmt.n(wr.refreshed || 0) + ' หน้า' }) +
      ui.kpi({ label: 'เวลาที่คนต้องใช้', value: fmt.n(humanHrs) + ' ชม./สัปดาห์', tone: autoTone, foot: 'ระบบทำเอง ≥ 90% (คนใช้เวลา < 2 ชม.)' }) +
    '</div>';
    repBody += '<div class="hint dashed">รายงานนี้สรุปครบทั้ง 3 คำถาม: <b>ทำอะไรไปบ้าง</b> · <b>ผลเป็นอย่างไร</b> · <b>รอบหน้าจะทำอะไร</b></div>';
    html += ui.card({
      title: 'รายงานสรุปรายสัปดาห์',
      sub: 'ส่งอัตโนมัติทาง ' + esc(wr.sentTo || ''),
      body: repBody,
      cls: 'mb'
    });

    // 5) วงจร AI Growth Loop
    if (loop.length) {
      var loopBody = '<div class="row wrap gap-s">';
      for (var l = 0; l < loop.length; l++) {
        var st = loop[l] || {};
        loopBody += '<div class="chip"><b>' + esc(String(st.n)) + '</b> · ' + esc(st.t || '') +
          '<span class="text soft small"> — ' + esc(st.d || '') + '</span></div>';
        if (l < loop.length - 1) loopBody += '<span class="text muted">→</span>';
      }
      loopBody += '<span class="text muted">↻</span>';
      loopBody += '</div>';
      loopBody += '<div class="text soft small" style="margin-top:8px">เมื่อถึงขั้น <b>Learn</b> ระบบจะวนกลับไปขั้น <b>Discover</b> ทันที — วงจรนี้ทำให้ทุกรอบฉลาดกว่ารอบก่อน</div>';
      html += ui.card({
        title: 'วงจร AI Growth Loop',
        sub: 'Discover → Create → Optimize → Publish → Measure → Learn แล้ววนกลับ',
        body: loopBody
      });
    }

    return { html: html, mount: null };
  };
})(window.RP);
