/* ============================================================
   ImVisible — Real vs Sample state (จุดยืน "ไม่โกง")
   กฎเหล็ก: บัญชีจริง = แสดงข้อมูลจริง หรือ "ยังไม่มีข้อมูล" เท่านั้น
            ห้ามโชว์ตัวเลขตัวอย่างให้บัญชีจริงเด็ดขาด
   โหมดตัวอย่าง (ยังไม่ล็อกอินจริง) = โชว์ sample ได้ แต่ต้องติดป้ายชัดเจน
   ============================================================ */
(function (RP) {
  'use strict';

  /** บัญชีจริง (มี JWT จริง) หรือไม่ */
  RP.isReal = function () {
    try { return !!(RP.auth && RP.auth.isReal && RP.auth.isReal()); } catch (e) { return false; }
  };

  /** ป้าย "ข้อมูลตัวอย่าง" — ใส่กำกับทุกบล็อกที่ยังเป็น sample (โหมดตัวอย่างเท่านั้น) */
  RP.sampleBadge = function (label) {
    if (RP.isReal()) return '';
    return '<span class="badge amber" title="ตัวเลขชุดนี้เป็นตัวอย่างเพื่อสาธิตหน้าตาระบบ ไม่ใช่ข้อมูลจริง">' +
      RP.esc(label || 'ข้อมูลตัวอย่าง') + '</span>';
  };

  /** กล่อง "ยังไม่มีข้อมูล" สำหรับบัญชีจริงที่ระบบยังเก็บข้อมูลไม่พอ */
  RP.noData = function (title, hint, cta) {
    return '<div class="nodata" style="padding:30px 20px;text-align:center">' +
      '<div style="font-size:30px;line-height:1;margin-bottom:8px">📭</div>' +
      '<div class="bb">' + RP.esc(title || 'ยังไม่มีข้อมูล') + '</div>' +
      (hint ? '<div class="soft small" style="margin-top:5px;max-width:52ch;margin-left:auto;margin-right:auto">' +
        RP.esc(hint) + '</div>' : '') +
      (cta ? '<div style="margin-top:12px">' + cta + '</div>' : '') +
      '</div>';
  };

  /**
   * ตัวช่วยหลักของทุก view:
   *   RP.realOr(sampleHtml, { title, hint, cta })
   * - บัญชีจริง → คืนกล่อง "ยังไม่มีข้อมูล" (ไม่โชว์ตัวเลขปลอม)
   * - โหมดตัวอย่าง → คืน sample ตามเดิม
   */
  RP.realOr = function (sampleHtml, empty) {
    if (!RP.isReal()) return sampleHtml;
    empty = empty || {};
    return RP.noData(empty.title, empty.hint, empty.cta);
  };

  /** แถบเตือนบนสุดของหน้า (โหมดตัวอย่าง) */
  RP.sampleNotice = function (what) {
    if (RP.isReal()) return '';
    return '<div class="warn-box mb">👀 <b>โหมดตัวอย่าง</b> — ตัวเลขใน' + RP.esc(what || 'หน้านี้') +
      'เป็น<b>ข้อมูลสมมติ</b>เพื่อสาธิตหน้าตาระบบ ไม่ใช่ผลจริง · สมัครบัญชีจริงเพื่อเริ่มเก็บข้อมูลของคุณเอง</div>';
  };

  /** แถบแจ้งบัญชีจริงที่ยังไม่มีข้อมูล (ให้ลูกค้าเข้าใจว่าทำไมว่าง) */
  RP.collectingNotice = function (what) {
    if (!RP.isReal()) return '';
    return '<div class="hint mb">⏳ ระบบกำลังเก็บข้อมูล' + RP.esc(what || '') +
      ' — ตัวเลขจะขึ้นเมื่อมีผลจริง (เราไม่แสดงตัวเลขสมมติ)</div>';
  };

})(window.RP);
