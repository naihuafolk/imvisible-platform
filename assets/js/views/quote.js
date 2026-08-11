/* ============================================================
   View: 🧾 ใบเสนอราคา (Quotation) — ออกใบเสนอราคาแพ็กเกจ SEO/AEO/GEO 6 เดือน
   เลือกลูกค้า + แพ็กคีย์เวิร์ด → ได้ใบเสนอราคาพร้อมพิมพ์/บันทึก PDF (ส่งลูกค้าได้เลย)
   ราคาอิงฐาน 10 คีย์ = 69,000 (6 เดือน) + ส่วนลดตามจำนวนคีย์
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  // แพ็กเกจ 6 เดือน — แก้ราคา/คอนเทนต์ได้ที่นี่จุดเดียว
  var PACKAGES = [
    { keys: 10, price: 69000, articles: 8, tier: 'S' },
    { keys: 20, price: 129000, articles: 14, tier: 'M' },
    { keys: 30, price: 185000, articles: 20, tier: 'L' },
    { keys: 40, price: 235000, articles: 26, tier: 'XL' },
    { keys: 50, price: 279000, articles: 32, tier: 'XXL' }
  ];
  var MONTHS = 6;

  function baht(n) { return Number(Math.round(n)).toLocaleString('th-TH'); }
  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function fmtDate(d) { return pad(d.getDate()) + '/' + pad(d.getMonth() + 1) + '/' + (d.getFullYear() + 543); }
  function pkgByKeys(k) { for (var i = 0; i < PACKAGES.length; i++) if (PACKAGES[i].keys === k) return PACKAGES[i]; return PACKAGES[0]; }

  function scopeLines(p) {
    return [
      'ตรวจเว็บ (Audit) + แก้ Technical/On-page SEO + ฝัง Schema, FAQ, E-E-A-T, llms.txt (AEO/GEO)',
      'ติดตามคีย์เวิร์ดเป้าหมาย <b>' + p.keys + ' คำ</b> (ตกลงร่วมกัน — แนบท้าย)',
      'ผลิต + เผยแพร่คอนเทนต์ SEO+AEO <b>' + p.articles + ' บทความ/เดือน</b> (รวม ' + (p.articles * MONTHS) + ' บทความ)',
      'เร่งให้ติด Google เร็ว: IndexNow + Google Indexing API',
      'ดันอันดับอัตโนมัติทุกวัน (Striking-Distance) + Internal Linking + CTR Optimization',
      'วัดการถูกแนะนำโดย AI (ChatGPT / Gemini / Perplexity — Share of Voice)',
      'ดักลีดอัตโนมัติ (CTA/ฟอร์ม) + แจ้งเตือนลีดเข้า LINE ทันที',
      'รายงานผลทุกเดือน — ตัวเลขจริงจาก Google Search Console (โปร่งใส ตรวจย้อนได้)'
    ];
  }

  function buildDoc(d) {
    var p = d.pkg;
    var sub = p.price;
    var disc = Math.round(sub * (d.discountPct / 100));
    var afterDisc = sub - disc;
    var vat = d.vat ? Math.round(afterDisc * 0.07) : 0;
    var grand = afterDisc + vat;
    var perMonth = grand / MONTHS;
    var rows =
      '<tr><td><b>บริการ SEO + AEO + GEO — แพ็กเกจ 6 เดือน (' + p.tier + ')</b>' +
        '<div class="muted">คีย์เวิร์ดเป้าหมาย ' + p.keys + ' คำ · คอนเทนต์ ' + p.articles + ' บทความ/เดือน · การันตีคืนเงินตามเงื่อนไข</div></td>' +
        '<td class="r">1</td><td class="r">' + baht(sub) + '</td><td class="r">' + baht(sub) + '</td></tr>';
    var totals =
      '<tr><td colspan="3" class="r">รวม</td><td class="r">' + baht(sub) + '</td></tr>' +
      (disc ? '<tr><td colspan="3" class="r">ส่วนลด ' + d.discountPct + '%</td><td class="r">-' + baht(disc) + '</td></tr>' : '') +
      (d.vat ? '<tr><td colspan="3" class="r">ภาษีมูลค่าเพิ่ม 7%</td><td class="r">' + baht(vat) + '</td></tr>' : '') +
      '<tr class="grand"><td colspan="3" class="r">ยอดสุทธิ (บาท)</td><td class="r">' + baht(grand) + '</td></tr>';

    var scope = scopeLines(p).map(function (s) { return '<li>' + s + '</li>'; }).join('');

    return '<!doctype html><html lang="th"><head><meta charset="utf-8">' +
      '<meta name="viewport" content="width=device-width,initial-scale=1">' +
      '<title>ใบเสนอราคา ' + esc(d.quoteNo) + '</title><style>' +
      '*{box-sizing:border-box}body{font-family:"Sarabun","Segoe UI",Tahoma,sans-serif;color:#0f1b2d;margin:0;background:#eef2f8;line-height:1.6}' +
      '.page{max-width:800px;margin:18px auto;background:#fff;padding:40px 44px;box-shadow:0 6px 30px rgba(0,0,0,.12)}' +
      '.top{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:3px solid #1657d6;padding-bottom:16px;margin-bottom:20px;gap:16px}' +
      '.brand{font-size:24px;font-weight:800;color:#1657d6;letter-spacing:-.5px}.brand span{color:#0f1b2d}' +
      '.brand .tag{font-size:12px;font-weight:600;color:#55647c;letter-spacing:1px;margin-top:2px}' +
      '.doc{ text-align:right}.doc h1{font-size:22px;margin:0 0 4px;letter-spacing:2px;color:#0f1b2d}.doc .m{font-size:13px;color:#55647c}' +
      '.meta{display:flex;justify-content:space-between;gap:20px;margin-bottom:18px;font-size:14px}' +
      '.meta .box{flex:1}.meta .lbl{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#8a97ab;font-weight:700;margin-bottom:3px}' +
      '.meta b{font-size:15px}' +
      'table{width:100%;border-collapse:collapse;margin:10px 0;font-size:14px}' +
      'th{background:#1657d6;color:#fff;padding:9px 12px;text-align:left;font-size:12px;letter-spacing:.4px}th.r,td.r{text-align:right}' +
      'td{padding:11px 12px;border-bottom:1px solid #e3e9f2;vertical-align:top}.muted{color:#55647c;font-size:12.5px;margin-top:3px}' +
      'tr.grand td{background:#eaf1ff;font-weight:800;font-size:16px;color:#0e3fa0;border:none}' +
      '.permo{text-align:right;color:#55647c;font-size:13px;margin:2px 0 16px}' +
      '.scope{background:#f6f8fc;border:1px solid #e3e9f2;border-radius:10px;padding:14px 16px;margin:14px 0}' +
      '.scope h3{margin:0 0 8px;font-size:14px;color:#0e3fa0}.scope ul{margin:0;padding-left:20px}.scope li{margin:5px 0;font-size:13.5px}' +
      '.guar{background:#e7f6ee;border:1px solid #0f8a55;border-radius:10px;padding:12px 15px;margin:14px 0;font-size:13.5px}.guar b{color:#0f8a55}' +
      '.terms{font-size:12.5px;color:#55647c;margin-top:16px}.terms li{margin:3px 0}' +
      '.sig{display:flex;gap:40px;margin-top:34px}.sig .s{flex:1;border-top:1px solid #0f1b2d;padding-top:6px;font-size:13px;color:#55647c;margin-top:44px}' +
      '.foot{text-align:center;color:#8a97ab;font-size:11.5px;margin-top:22px;border-top:1px solid #e3e9f2;padding-top:12px}' +
      '.pbar{max-width:800px;margin:0 auto 0;text-align:center;padding:10px}' +
      '.pbar button{background:#1657d6;color:#fff;border:none;border-radius:8px;padding:11px 26px;font-size:15px;font-weight:700;cursor:pointer;font-family:inherit}' +
      '@media print{.pbar{display:none}body{background:#fff}.page{box-shadow:none;margin:0;max-width:none;padding:24px}}' +
      '</style></head><body>' +
      '<div class="pbar"><button onclick="window.print()">🖨️ พิมพ์ / บันทึกเป็น PDF</button></div>' +
      '<div class="page">' +
        '<div class="top"><div><div class="brand">Im<span>Visible</span></div><div class="tag">AEO + SEO + GEO · อัตโนมัติด้วย AI</div>' +
          '<div class="muted" style="margin-top:6px">' + esc(d.fromInfo) + '</div></div>' +
          '<div class="doc"><h1>ใบเสนอราคา</h1><div class="m">QUOTATION</div>' +
          '<div class="m" style="margin-top:6px">เลขที่ ' + esc(d.quoteNo) + '</div></div></div>' +
        '<div class="meta"><div class="box"><div class="lbl">เสนอแก่ (ลูกค้า)</div><b>' + esc(d.client || '____________') + '</b>' +
          (d.website ? '<div class="muted">' + esc(d.website) + '</div>' : '') + '</div>' +
          '<div class="box" style="text-align:right"><div class="lbl">วันที่ / ยืนราคาถึง</div><b>' + esc(d.date) + '</b>' +
          '<div class="muted">ยืนราคาถึง ' + esc(d.validUntil) + '</div></div></div>' +
        '<table><thead><tr><th>รายการ</th><th class="r">จำนวน</th><th class="r">ราคา/หน่วย</th><th class="r">รวม (บาท)</th></tr></thead>' +
        '<tbody>' + rows + totals + '</tbody></table>' +
        '<div class="permo">เฉลี่ยเดือนละ ' + baht(perMonth) + ' บาท × 6 เดือน' + (d.discountPct ? ' (หลังส่วนลด)' : '') + '</div>' +
        '<div class="scope"><h3>ขอบเขตบริการ (รวมทุกอย่างตลอด 6 เดือน)</h3><ul>' + scope + '</ul></div>' +
        '<div class="guar"><b>🛡️ การันตีคืนเงิน:</b> หากครบ 6 เดือน อันดับ/การมองเห็นของคีย์เวิร์ดเป้าหมายไม่ดีขึ้นตามเกณฑ์ที่วัดจาก Google Search Console (เทียบ baseline เดือนแรก) โดยลูกค้าทำตามหน้าที่ครบ → คืนค่าบริการตามเงื่อนไขในสัญญาบริการ</div>' +
        (d.note ? '<div class="scope"><h3>หมายเหตุ</h3><div style="font-size:13.5px">' + esc(d.note).replace(/\n/g, '<br>') + '</div></div>' : '') +
        '<ul class="terms"><li>ราคานี้ยังไม่รวมต้นทุนบุคคลที่สาม (ค่าโฆษณา/โดเมน/โฮสต์) หากมี</li>' +
          '<li>เริ่มงานเมื่อยืนยันสั่งซื้อ + ชำระตามเงื่อนไข + ลูกค้าเชื่อม Google Search Console ภายใน 7 วัน</li>' +
          '<li>รายละเอียดการันตี/หน้าที่ลูกค้า/การคืนเงิน เป็นไปตาม "สัญญาบริการ 6 เดือน" ที่แนบ</li></ul>' +
        '<div class="sig"><div class="s">ผู้เสนอราคา (ImVisible)</div><div class="s">ผู้อนุมัติสั่งซื้อ (ลูกค้า)</div></div>' +
        '<div class="foot">ImVisible · ' + esc(d.fromInfo) + ' · ตัวเลขผลงานทุกตัวมาจากข้อมูลจริง ไม่มีการกุ</div>' +
      '</div></body></html>';
  }

  function gather(root) {
    var keys = parseInt(root.querySelector('#q_pkg').value, 10);
    return {
      pkg: pkgByKeys(keys),
      client: (root.querySelector('#q_client').value || '').trim(),
      website: (root.querySelector('#q_web').value || '').trim(),
      quoteNo: (root.querySelector('#q_no').value || '').trim(),
      date: (root.querySelector('#q_date').value || '').trim(),
      validUntil: (root.querySelector('#q_valid').value || '').trim(),
      discountPct: Math.max(0, Math.min(100, parseFloat(root.querySelector('#q_disc').value) || 0)),
      vat: root.querySelector('#q_vat').checked,
      fromInfo: (root.querySelector('#q_from').value || '').trim(),
      note: (root.querySelector('#q_note').value || '').trim()
    };
  }

  RP.views.quote = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · เครื่องมือขาย', title: '🧾 ใบเสนอราคา (Quotation)',
      desc: 'เลือกลูกค้า + แพ็กเกจคีย์เวิร์ด → ออกใบเสนอราคา 6 เดือน พร้อมพิมพ์/บันทึก PDF ส่งลูกค้าได้เลย (ราคา + ส่วนลด + VAT + การันตี ครบ)' });

    var now = new Date();
    var valid = new Date(now.getTime() + 15 * 86400000);
    var qno = 'QT-' + now.getFullYear() + pad(now.getMonth() + 1) + pad(now.getDate()) + '-' + pad(Math.floor((now.getHours() * 60 + now.getMinutes()) % 100));

    var opts = PACKAGES.map(function (p) {
      return '<option value="' + p.keys + '">' + p.tier + ' · ' + p.keys + ' คีย์ · ' + p.articles + ' บทความ/ด. · ' + baht(p.price) + ' บาท</option>';
    }).join('');

    function inp(id, label, val, ph) {
      return '<div style="flex:1;min-width:170px"><div class="soft small" style="margin-bottom:4px">' + label + '</div>' +
        '<input class="input" id="' + id + '" value="' + esc(val || '') + '" placeholder="' + esc(ph || '') + '" style="width:100%"></div>';
    }

    var form = ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:12px">' +
        '<div style="flex:2;min-width:240px"><div class="soft small" style="margin-bottom:4px">แพ็กเกจ</div>' +
          '<select class="input" id="q_pkg" style="width:100%">' + opts + '</select></div>' +
        inp('q_client', 'ชื่อลูกค้า / บริษัท', '', 'เช่น บริษัท เอบีซี จำกัด') +
        inp('q_web', 'เว็บไซต์ลูกค้า', '', 'abccompany.com') +
      '</div>' +
      '<div class="row wrap" style="gap:12px;margin-top:10px">' +
        inp('q_no', 'เลขที่ใบเสนอราคา', qno) +
        inp('q_date', 'วันที่', fmtDate(now)) +
        inp('q_valid', 'ยืนราคาถึง', fmtDate(valid)) +
        '<div style="flex:1;min-width:120px"><div class="soft small" style="margin-bottom:4px">ส่วนลด (%)</div>' +
          '<input class="input" id="q_disc" type="number" value="0" min="0" max="100" style="width:100%"></div>' +
        '<div style="flex:1;min-width:120px;display:flex;align-items:flex-end;padding-bottom:8px"><label class="row gap-s" style="cursor:pointer"><input type="checkbox" id="q_vat"> <span>+ VAT 7%</span></label></div>' +
      '</div>' +
      '<div style="margin-top:10px">' + inp('q_from', 'ข้อมูลผู้ออก (ชื่อ/เบอร์/เลขผู้เสียภาษี)', 'ImVisible · imvisible.tech · โทร ____ · เลขผู้เสียภาษี ____') + '</div>' +
      '<div style="margin-top:10px"><div class="soft small" style="margin-bottom:4px">หมายเหตุ (ไม่บังคับ)</div>' +
        '<textarea class="input" id="q_note" rows="2" placeholder="เช่น เงื่อนไขชำระ 50/50 · เริ่มงานภายใน 7 วัน" style="width:100%"></textarea></div>' +
      '<div class="row" style="gap:8px;margin-top:14px"><button class="btn btn-primary" id="q_make">🧾 สร้าง + พิมพ์ใบเสนอราคา</button>' +
        '<button class="btn" id="q_prev">👁️ ดูตัวอย่าง</button></div>' +
      '<div class="hint" style="margin-top:8px">กด "สร้าง+พิมพ์" จะเปิดหน้าใบเสนอราคาในแท็บใหม่ → กดพิมพ์ หรือ Save as PDF ได้เลย</div>' });

    return { html: head + form + '<div id="q_preview" style="margin-top:6px"></div>', mount: function (root) {
      function openDoc() {
        var d = gather(root);
        if (!d.client) { ui.toast('ใส่ชื่อลูกค้าก่อน'); root.querySelector('#q_client').focus(); return; }
        var w = window.open('', '_blank');
        if (!w) { ui.toast('เบราว์เซอร์บล็อกป๊อปอัพ — อนุญาตป๊อปอัพแล้วลองใหม่'); return; }
        w.document.open(); w.document.write(buildDoc(d)); w.document.close();
      }
      function preview() {
        var d = gather(root);
        var box = root.querySelector('#q_preview');
        box.innerHTML = '<div class="card" style="padding:0;overflow:hidden"><iframe style="width:100%;height:900px;border:0;background:#eef2f8" id="q_iframe"></iframe></div>';
        var f = root.querySelector('#q_iframe');
        var doc = f.contentDocument || f.contentWindow.document;
        doc.open(); doc.write(buildDoc(d)); doc.close();
      }
      var mk = root.querySelector('#q_make'); if (mk) mk.onclick = openDoc;
      var pv = root.querySelector('#q_prev'); if (pv) pv.onclick = preview;
      // preview อัตโนมัติเมื่อเปลี่ยนแพ็ก
      var sel = root.querySelector('#q_pkg'); if (sel) sel.onchange = function () { if (root.querySelector('#q_iframe')) preview(); };
    } };
  };
})(window.RP);
