(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  RP.views.m6 = function () {
    var d = (RP.data && RP.data.m6) || {};
    var insights = d.insights || [];
    var actions = d.actions || [];
    var wr = d.weeklyReport || {};
    var loop = (RP.data && RP.data.loop) || [];
    var isReal = RP.isReal();

    var html = ui.pageHead({
      eyebrow: 'M6 · Learning Loop',
      title: 'Learning Loop — สมองของระบบ',
      desc: 'วงจร Closed-Loop ที่ทำให้ระบบฉลาดขึ้นทุกรอบ: เรียนรู้จากผลจริงแล้วปรับการผลิตรอบถัดไปเอง'
    }) + '';

    // แถบกำกับสถานะข้อมูล (โหมดตัวอย่าง = sample / บัญชีจริง = กำลังเก็บข้อมูล)
    html += RP.sampleNotice('หน้า Learning Loop นี้');
    html += RP.collectingNotice('การเรียนรู้ของบัญชีคุณ');

    // 1) เกริ่นนำ — สมองของระบบ (อธิบายหลักการทำงาน ไม่ใช่ผลงานที่ทำไปแล้ว)
    html += '<div class="note-box purple mb">' +
      '<div class="text b">M6 คือ “สมองของระบบ”</div>' +
      '<div class="text soft small">M6 ออกแบบมาเพื่อเรียนรู้จากผลจริงของเว็บไซต์คุณว่าอะไรทำให้หน้าติด Citation/อันดับดี ' +
      '(ความยาว โครงสร้าง ชนิด Schema หัวข้อ ฯลฯ) แล้วปรับเทมเพลตการผลิตคอนเทนต์และลำดับความสำคัญของคิวงานรอบถัดไป ' +
      'ครบวงจร Discover → Create → Optimize → Publish → Measure → Learn แล้ววนกลับ<br>' +
      '<b>หมายเหตุ:</b> ระบบจะเริ่มสรุปสิ่งที่เรียนรู้ได้ก็ต่อเมื่อมีบทความเผยแพร่และมีผลวัด (อันดับ/Citation) สะสมพอสมควรแล้ว ' +
      'ก่อนหน้านั้นเราจะไม่แสดงข้อสรุปใด ๆ</div>' +
    '</div>';

    // 2) Insights — เป็น "ข้อค้นพบจากข้อมูลของบัญชีนี้" จึงต้องปิดสำหรับบัญชีจริงที่ยังไม่มีข้อมูล
    var insSample = RP.sampleBadge('ข้อมูลตัวอย่าง (ไม่ใช่ผลจากเว็บไซต์ของคุณ)');
    var insBody = (insSample ? '<div class="mb">' + insSample + '</div>' : '') + '<div class="grid grid-2">';
    for (var i = 0; i < insights.length; i++) {
      var it = insights[i] || {};
      insBody += '<div class="panel"><div class="panel-body">' +
        '<div class="text soft small">' + esc(it.t || '') + '</div>' +
        '<div class="text bb" style="font-size:20px;color:var(--purple-700)">' + esc(it.v || '') + '</div>' +
        '<div class="text soft small">' + esc(it.note || '') + '</div>' +
      '</div></div>';
    }
    insBody += '</div>';
    insBody += '<div class="hint dashed">ตัวเลขชุดนี้เป็น<b>ตัวอย่างสาธิต</b>ว่าหน้ารายงานจะหน้าตาเป็นอย่างไร ' +
      'ไม่ใช่ผลวัดจากเว็บไซต์จริงของผู้ใช้รายใด</div>';

    html += ui.card({
      title: 'สิ่งที่ระบบเรียนรู้ (Insights)',
      sub: isReal
        ? 'สรุปจากข้อมูลจริงของเว็บไซต์คุณเท่านั้น'
        : 'ตัวอย่างการแสดงผล — ลักษณะร่วมของหน้าที่ติด Citation/อันดับดี',
      body: RP.realOr(insBody, {
        title: 'ยังไม่มีข้อมูลให้สรุป',
        hint: 'ระบบจะสรุปได้ว่าอะไรทำให้หน้าของคุณติด Citation/อันดับ ก็ต่อเมื่อมีบทความที่เผยแพร่แล้วและเก็บผลวัดต่อเนื่องประมาณ 4–8 สัปดาห์ ' +
              'ระหว่างนี้เราจะไม่แสดงข้อสรุปสมมติ'
      }),
      cls: 'mb'
    });

    // 3) Auto-Tuning — อ้างว่า "ปรับแล้ว" กับบัญชีนี้ ห้ามแสดงถ้าไม่จริง
    var actSample = RP.sampleBadge('ตัวอย่างการทำงาน');
    var actBody = (actSample ? '<div class="list-row">' + actSample + '</div>' : '');
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
    actBody += '<div class="list-row"><div class="s soft">รายการข้างบนเป็น<b>ตัวอย่าง</b>ว่าระบบจะรายงานการปรับจูนอย่างไร ' +
      'ไม่ใช่การปรับที่เกิดขึ้นจริงกับบัญชีใด</div></div>';

    html += ui.card({
      title: 'การปรับอัตโนมัติรอบถัดไป (Auto-Tuning)',
      sub: isReal
        ? 'จะขึ้นรายการเมื่อระบบปรับจูนให้บัญชีคุณจริงเท่านั้น'
        : 'ตัวอย่างการแสดงผล — ระบบปรับเทมเพลต + ลำดับความสำคัญของคิวงานตามสิ่งที่เรียนรู้',
      body: RP.realOr(actBody, {
        title: 'ยังไม่มีการปรับจูนอัตโนมัติ',
        hint: 'ระบบจะปรับเทมเพลตหรือลำดับคิวงานให้ก็ต่อเมื่อมีผลวัดจริงมากพอที่จะสรุปได้ ทุกครั้งที่ปรับจริงจะบันทึกไว้ที่นี่พร้อมวันเวลา'
      }),
      flush: true,
      cls: 'mb'
    });

    // 4) รายงานสรุปรายสัปดาห์ — KPI ทั้งหมดเป็นตัวเลขของบัญชี จึงต้องปิดสำหรับบัญชีจริง
    var humanHrs = (wr.humanHours != null) ? wr.humanHours : 0;
    var autoTone = (humanHrs < 2) ? 'pos' : '';
    var repSample = RP.sampleBadge('ตัวเลขตัวอย่าง');
    var repBody = (repSample ? '<div class="mb">' + repSample + '</div>' : '') +
      '<div class="grid grid-3">' +
      ui.kpi({ label: 'เผยแพร่บทความ', value: fmt.n(wr.published || 0) + ' บทความ', tone: 'brand' }) +
      ui.kpi({ label: 'ติดหน้า 1 ใหม่', value: fmt.n(wr.newPage1 || 0) + ' คีย์เวิร์ด', tone: 'pos', foot: 'ขึ้นหน้าแรกในรอบสัปดาห์' }) +
      ui.kpi({ label: 'Citation เพิ่ม', value: '+' + fmt.n(wr.citationsGained || 0), tone: 'brand', foot: 'ถูกอ้างอิงโดย AI Answer เพิ่มขึ้น' }) +
      ui.kpi({ label: 'รีเฟรชหน้าเก่า', value: fmt.n(wr.refreshed || 0) + ' หน้า' }) +
      ui.kpi({ label: 'เวลาที่คนต้องใช้', value: fmt.n(humanHrs) + ' ชม./สัปดาห์', tone: autoTone }) +
    '</div>';
    repBody += '<div class="hint dashed">รายงานฉบับจริงจะสรุปครบทั้ง 3 คำถาม: <b>ทำอะไรไปบ้าง</b> · <b>ผลเป็นอย่างไร</b> · <b>รอบหน้าจะทำอะไร</b> ' +
      '(ตัวเลขที่เห็นตอนนี้เป็นชุดตัวอย่าง)</div>';

    html += ui.card({
      title: 'รายงานสรุปรายสัปดาห์',
      sub: isReal
        ? 'จะสรุปจากงานที่ระบบทำให้บัญชีคุณจริงเท่านั้น'
        : 'ตัวอย่างรายงาน — ฉบับจริงส่งอัตโนมัติทาง ' + (wr.sentTo || ''),
      body: RP.realOr(repBody, {
        title: 'ยังไม่มีรายงานประจำสัปดาห์',
        hint: 'รายงานฉบับแรกจะสรุปให้หลังระบบทำงานครบ 1 สัปดาห์ และจะนับเฉพาะบทความที่เผยแพร่จริง อันดับที่วัดได้จริง และ Citation ที่ตรวจพบจริงเท่านั้น'
      }),
      cls: 'mb'
    });

    // 5) วงจร AI Growth Loop — เป็นคำอธิบายขั้นตอนการทำงาน ไม่ใช่ตัวเลข/ผลลัพธ์ จึงแสดงได้ทุกโหมด
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
      loopBody += '<div class="text soft small" style="margin-top:8px">เมื่อถึงขั้น <b>Learn</b> ระบบจะวนกลับไปขั้น <b>Discover</b> — ' +
        'แผนภาพนี้อธิบาย<b>ขั้นตอนการทำงานของระบบ</b> ไม่ได้แสดงความคืบหน้าของบัญชีคุณ</div>';
      html += ui.card({
        title: 'วงจร AI Growth Loop',
        sub: 'Discover → Create → Optimize → Publish → Measure → Learn แล้ววนกลับ',
        body: loopBody
      });
    }

    return { html: html, mount: null };
  };
})(window.RP);
