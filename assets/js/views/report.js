(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  function tbl(head, rows) {
    return '<div class="tbl-wrap"><table class="tbl"><thead><tr>' +
      head + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }

  RP.views.report = function () {
    var d = RP.data || {};

    // ---- 1) แถบสถิติ (facts) ----
    var facts = d.facts || [];
    var factsHtml = '<div class="grid grid-4 mb">';
    facts.forEach(function (f) {
      factsHtml +=
        '<div class="card card-pad center">' +
          '<div class="bb" style="font-size:1.8rem;line-height:1.2;color:var(--purple-700)">' + esc(f.v) + '</div>' +
          '<div class="soft small">' + esc(f.d) + '</div>' +
        '</div>';
    });
    factsHtml += '</div>';

    // ---- 2) แผนพัฒนา (Roadmap) ----
    var roadmap = d.roadmap || [];
    var rmRows = '';
    roadmap.forEach(function (r) {
      rmRows +=
        '<tr>' +
          '<td class="bb">' + esc(r.phase) + '</td>' +
          '<td>' + esc(r.scope) + '</td>' +
          '<td class="nowrap">' + esc(r.weeks) + '</td>' +
          '<td>' + ui.bar(r.progress) + ' ' + esc(String(r.progress)) + '%</td>' +
        '</tr>';
    });
    var roadmapCard = ui.card({
      title: 'แผนพัฒนา (Roadmap)',
      sub: 'แบ่งเป็น 4 เฟส',
      flush: true,
      cls: 'mb',
      body: tbl(
        '<th>เฟส</th><th>ขอบเขต</th><th>ระยะเวลา</th><th>ความคืบหน้า</th>',
        rmRows
      )
    });

    // ---- 3) ตัวชี้วัดความสำเร็จ (KPI) ----
    var kpiTargets = d.kpiTargets || [];
    var kpiRows = '';
    kpiTargets.forEach(function (k) {
      kpiRows +=
        '<tr>' +
          '<td class="bb">' + esc(k.kpi) + '</td>' +
          '<td>' + esc(k.target) + '</td>' +
          '<td class="num">' + esc(k.curTxt) + '</td>' +
          '<td>' + ui.bar(k.pct) + ' ' + esc(String(k.pct)) + '%</td>' +
        '</tr>';
    });
    var kpiCard = ui.card({
      title: 'ตัวชี้วัดความสำเร็จ (KPI) — เป้าหมาย 6 เดือน',
      flush: true,
      cls: 'mb',
      body: tbl(
        '<th>KPI</th><th>เป้าหมาย</th><th>ปัจจุบัน</th><th>ความคืบหน้า</th>',
        kpiRows
      )
    });

    // ---- 4) กลยุทธ์ที่ทำให้เห็นผลจริง ----
    var strategies = d.strategies || [];
    var stratBody = '';
    strategies.forEach(function (s) {
      stratBody +=
        '<div class="list-row"><div class="grow">' +
          '<div class="t bb">' + esc(s.t) + '</div>' +
          '<div class="s soft small">' + esc(s.d) + '</div>' +
        '</div></div>';
    });
    stratBody += '<div class="note-box">' + esc(d.strategyNote) + '</div>';
    var stratCard = ui.card({
      title: 'กลยุทธ์ที่ทำให้เห็นผลจริง',
      cls: 'mb',
      body: stratBody
    });

    // ---- 5) ประมาณการต้นทุน ----
    var costs = d.costs || [];
    var costRows = '';
    costs.forEach(function (c) {
      costRows +=
        '<tr>' +
          '<td>' + esc(c.item) + '</td>' +
          '<td class="right">' + esc(c.est) + '</td>' +
        '</tr>';
    });
    costRows +=
      '<tr>' +
        '<td class="bb">รวมโดยประมาณ</td>' +
        '<td class="bb right">' + esc(d.costTotal) + '</td>' +
      '</tr>';
    var costBody =
      tbl('<th>รายการ</th><th class="right">ประมาณการ</th>', costRows) +
      '<div class="hint">ต้นทุนต่ำกว่าจ้างนักเขียน SEO 1 คนหลายเท่า — โมเดลนี้จึงมี Margin สูง</div>';
    var costCard = ui.card({
      title: 'ประมาณการต้นทุน (ต่อ 1 โปรเจ็ค/เดือน)',
      flush: true,
      cls: 'mb',
      body: costBody
    });

    // ---- 6) สถาปัตยกรรม & เทคโนโลยี ----
    var stack = d.stack || [];
    var stackRows = '';
    stack.forEach(function (s) {
      stackRows +=
        '<tr>' +
          '<td class="bb">' + esc(s.part) + '</td>' +
          '<td>' + esc(s.tech) + '</td>' +
          '<td class="soft">' + esc(s.note) + '</td>' +
        '</tr>';
    });
    var stackCard = ui.card({
      title: 'สถาปัตยกรรม & เทคโนโลยี',
      flush: true,
      cls: 'mb',
      body: tbl(
        '<th>ส่วนประกอบ</th><th>เทคโนโลยีที่แนะนำ</th><th>หมายเหตุ</th>',
        stackRows
      )
    });

    // ---- 7) โมเดลธุรกิจ & แนวทางหารายได้ ----
    var pricing = d.pricing || [];
    var priceRows = '';
    pricing.forEach(function (p) {
      priceRows +=
        '<tr>' +
          '<td class="bb">' + esc(p.plan) + '</td>' +
          '<td>' + esc(p.detail) + '</td>' +
          '<td class="nowrap">' + esc(p.price) + '</td>' +
        '</tr>';
    });
    var priceBody =
      tbl('<th>รูปแบบ</th><th>รายละเอียด</th><th>ราคาแนะนำ</th>', priceRows) +
      '<div class="note-box">ลำดับที่แนะนำ: ใช้เองก่อนเพื่อพิสูจน์ว่า "ระบบดันเว็บติดจริง" → เก็บตัวเลขเป็น Case Study → เปิดรับลูกค้า Agency → เมื่อระบบนิ่งค่อยเปิด SaaS</div>';
    var priceCard = ui.card({
      title: 'โมเดลธุรกิจ & แนวทางหารายได้',
      flush: true,
      cls: 'mb',
      body: priceBody
    });

    // ---- 8) ความเสี่ยงที่ต้องรู้ก่อนลงมือ ----
    var risks = d.risks || [];
    var riskBody = '';
    risks.forEach(function (r) {
      riskBody +=
        '<div class="warn-box mb">' +
          '<div class="bb">⚠ ' + esc(r.t) + '</div>' +
          '<div>' + esc(r.d) + '</div>' +
        '</div>';
    });
    var riskCard = ui.card({
      title: 'ความเสี่ยงที่ต้องรู้ก่อนลงมือ',
      cls: 'mb',
      body: riskBody
    });

    // ---- 9) แหล่งอ้างอิง ----
    var references = d.references || [];
    var refBody = '';
    references.forEach(function (r) {
      refBody +=
        '<div class="list-row"><div class="grow">' +
          '<div class="t soft small">' + esc(r) + '</div>' +
        '</div></div>';
    });
    var refCard = ui.card({
      title: 'แหล่งอ้างอิง',
      cls: 'mb',
      body: refBody
    });

    var html =
      ui.pageHead({
        eyebrow: 'รายงานโครงการ',
        title: 'รายงาน & Roadmap',
        desc: 'สรุปแผนพัฒนา ตัวชี้วัดความสำเร็จ ต้นทุน สถาปัตยกรรม โมเดลธุรกิจ และความเสี่ยง (อ้างอิงหัวข้อ 7–11 ของเอกสารโครงการ)'
      }) +
      factsHtml +
      roadmapCard +
      kpiCard +
      stratCard +
      costCard +
      stackCard +
      priceCard +
      riskCard +
      refCard;

    return { html: html, mount: null };
  };
})(window.RP);
