/* ============================================================
   View: Google Ads — Ads Advisor
   แนะนำ 'ควรยิง Ads คีย์ไหน' จากช่องว่าง organic จริง + ร่างชุดโฆษณา (RSA) ให้
   ไม่ยิงเอง (ก็อปไปวางใน Google Ads) — ไม่ต้องขอ Google Ads API
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;
  var GADS = 'https://ads.google.com/aw/campaigns';

  function curProj() {
    var list = ((RP.data.project && RP.data.project.list) || []).filter(function (p) { return /^db/.test(String(p.id)); });
    var cur = RP.data.project.current;
    return list.filter(function (x) { return x.id === cur; })[0] || list[0] || null;
  }
  function dbId(p) { var m = /^db(\d+)$/.exec(String(p && p.id || '')); return m ? parseInt(m[1], 10) : null; }

  function copyText(t) {
    try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); }
    catch (e) {
      var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a);
      a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove();
    }
  }

  var HOWTO =
    '<div class="hint" style="line-height:1.7">' +
    '<b>ใช้ยังไง:</b> ① ดูคีย์ที่ระบบแนะนำ (คีย์มูลค่าที่ <b>ยังไม่ติดหน้า 1</b>) → ② กด <b>“สร้างชุดโฆษณา”</b> ระบบร่าง headline/คำบรรยาย + ลิงก์ให้ → ' +
    '③ <b>ก็อปไปวางใน Google Ads</b> (Search campaign) ตั้งงบ → ยิง → ④ พอคีย์ติดหน้า 1 organic ระบบจะเตือนให้ <b>ปิด Ads ประหยัดงบ</b>' +
    '</div>';

  function reasonBadge(r) {
    if (/ติดหน้า 1/.test(r)) return ui.badge('ติดหน้า 1', 'green');
    if (/จ่อหน้า 1/.test(r)) return ui.badge('จ่อหน้า 1', 'amber');
    return ui.badge('ยังไม่ติด', 'blue');
  }

  function rowsHtml(items, withBtn) {
    return items.map(function (it) {
      var land = it.url ? ('<a href="' + esc(it.url) + '" target="_blank" rel="noopener" class="soft small">หน้าปลายทาง ↗</a>')
        : '<span class="soft small">ยังไม่มีบทความ → ชี้หน้าแรก</span>';
      return '<tr>' +
        '<td><div class="t">' + esc(it.keyword) + '</div><div class="soft small">' + land + '</div></td>' +
        '<td>' + reasonBadge(it.reason) + '<div class="soft small" style="margin-top:3px">' + esc(it.reason) + '</div></td>' +
        (withBtn ? '<td class="right"><button class="btn btn-sm btn-primary mk-ad" data-kw="' + esc(it.keyword) + '">✍️ สร้างชุดโฆษณา</button></td>' : '') +
        '</tr>';
    }).join('');
  }

  function creativeModal(pid, keyword) {
    ui.modal({ title: '✍️ ชุดโฆษณา Google Ads', sub: 'คีย์เวิร์ด: ' + esc(keyword) + ' · ร่างตามสเปก RSA', width: 640,
      body: '<div id="adc_body"><div class="hint">กำลังร่างชุดโฆษณา… (AI กำลังเขียน headline/คำบรรยาย)</div></div>' });
    RP.api.adsCreative(pid, keyword).then(function (d) {
      var body = document.getElementById('adc_body'); if (!body) return;
      var hs = d.headlines || [], ds = d.descriptions || [], ps = d.paths || [];
      function line(txt, cap) {
        var n = txt.length, over = n > cap;
        return '<div class="list-row" style="align-items:center;gap:8px">' +
          '<span class="grow">' + esc(txt) + '</span>' +
          '<span class="soft small" style="font-variant-numeric:tabular-nums;color:' + (over ? 'var(--red-600)' : 'var(--faint,#8b93a7)') + '">' + n + '/' + cap + '</span>' +
          '<button class="btn btn-sm cp" data-t="' + esc(txt) + '">คัดลอก</button></div>';
      }
      var all = 'คีย์เวิร์ด: ' + keyword + '\nFinal URL: ' + (d.final_url || '') +
        '\n\n— Headlines (≤30) —\n' + hs.map(function (h, i) { return (i + 1) + '. ' + h; }).join('\n') +
        '\n\n— Descriptions (≤90) —\n' + ds.map(function (x, i) { return (i + 1) + '. ' + x; }).join('\n') +
        '\n\n— Paths —\n/' + (ps[0] || '') + '/' + (ps[1] || '');
      body.innerHTML =
        '<div class="row between wrap" style="gap:8px;margin-bottom:10px">' +
          '<div class="soft small">ปลายทาง: <a href="' + esc(d.final_url || '#') + '" target="_blank" rel="noopener">' + esc(d.final_url || '-') + '</a>' +
          (d.has_landing ? '' : ' <span style="color:var(--amber-600)">(ยังไม่มีบทความตรงคีย์ → ชี้หน้าแรก)</span>') + '</div>' +
          '<button class="btn btn-sm btn-primary" id="adcAll">คัดลอกทั้งหมด</button></div>' +
        '<div class="bb small" style="margin:6px 0">หัวข้อโฆษณา (Headlines · สูงสุด 30 ตัวอักษร)</div>' + hs.map(function (h) { return line(h, 30); }).join('') +
        '<div class="bb small" style="margin:12px 0 6px">คำบรรยาย (Descriptions · สูงสุด 90 ตัวอักษร)</div>' + ds.map(function (x) { return line(x, 90); }).join('') +
        '<div class="bb small" style="margin:12px 0 6px">Path (ต่อท้าย URL · สูงสุด 15)</div>' +
          '<div class="list-row"><span class="grow">/' + esc(ps[0] || '') + '/' + esc(ps[1] || '') + '</span></div>' +
        '<div class="hint" style="margin-top:12px;line-height:1.7">💡 <b>งบเริ่มต้น (ปรับได้):</b> ลองงบทดสอบเล็ก ๆ ต่อแคมเปญ ตั้ง bidding “Maximize clicks” ก่อน แล้วดู CPC จริงที่ Google แสดง ค่อยปรับ · เพิ่ม <b>negative keywords</b> กันคำที่ไม่เกี่ยว</div>' +
        '<div class="row" style="gap:8px;margin-top:12px"><a class="btn btn-primary" href="' + GADS + '" target="_blank" rel="noopener">เปิด Google Ads ↗</a></div>';
      var allBtn = document.getElementById('adcAll'); if (allBtn) allBtn.onclick = function () { copyText(all); };
      Array.prototype.forEach.call(body.querySelectorAll('.cp'), function (b) { b.onclick = function () { copyText(b.getAttribute('data-t')); }; });
    }).catch(function (e) {
      var body = document.getElementById('adc_body');
      if (body) body.innerHTML = '<div class="hint" style="color:var(--red-600)">ร่างไม่สำเร็จ: ' + esc(e.message || String(e)) + '</div>';
    });
  }

  /* Negative keywords มาตรฐาน (กันคลิกขยะ/ไม่ตั้งใจซื้อ) — คนไทย */
  var NEGATIVES = ['ฟรี', 'free', 'คือ', 'คืออะไร', 'วิธี', 'วิธีทำ', 'ทำเอง', 'เอง', 'เรียน', 'คอร์ส', 'course', 'สอน',
    'สมัครงาน', 'หางาน', 'เงินเดือน', 'รับสมัคร', 'ตัวอย่าง', 'ดาวน์โหลด', 'มือใหม่'];

  /* 🗺 Campaign Blueprint — ประกอบชุดแคมเปญพร้อมยิง (คีย์ + negative + ad copy + ตั้งค่า) ก็อปเข้า Google Ads */
  function blueprintModal(pid, adv) {
    var kws = (adv || []).map(function (x) { return x.keyword; }).filter(Boolean).slice(0, 12);
    if (!kws.length) kws = ['รับทำ SEO', 'รับทำ AEO'];
    var top = kws[0];
    ui.modal({ title: '🗺 Campaign Blueprint — พร้อมยิง', sub: 'ก็อปเข้า Google Ads (Search campaign) ได้เลย · คุณคุมงบเอง', width: 700,
      body: '<div id="bp_body"><div class="hint">กำลังประกอบชุดแคมเปญ + ให้ AI ร่าง ad copy… (สักครู่)</div></div>' });
    RP.api.adsCreative(pid, top).then(function (d) {
      var body = document.getElementById('bp_body'); if (!body) return;
      var hs = d.headlines || [], ds = d.descriptions || [], url = d.final_url || '';
      var kwLines = []; kws.forEach(function (k) { kwLines.push('"' + k + '"'); kwLines.push('[' + k + ']'); });
      var settings =
        '- ประเภท: Search only (ปิด Display expansion + Search Partners ช่วงแรก)\n' +
        '- พื้นที่: ประเทศไทย · ภาษา: ไทย\n' +
        '- Bidding: Maximize clicks (จนได้ conversion ~15-30 ครั้ง ค่อยสลับเป็น Maximize conversions)\n' +
        '- งบ/วัน: เริ่มเท่าที่จ่ายไหว รันต่อเนื่อง 14-30 วัน (สะสม ~100-300 คลิกก่อนประเมิน)\n' +
        '- ตั้ง conversion tracking ให้เสร็จก่อนเทงบ (ไม่งั้น Google optimize ไม่ได้)';
      var full = '===== CAMPAIGN BLUEPRINT · ImVisible =====\n\n' +
        '[1] ตั้งค่าแคมเปญ\n' + settings + '\n\n' +
        '[2] คีย์เวิร์ด (Phrase + Exact)\n' + kwLines.join('\n') + '\n\n' +
        '[3] Negative keywords (กันคลิกขยะ)\n' + NEGATIVES.map(function (n) { return '-' + n; }).join('\n') + '\n\n' +
        '[4] โฆษณา RSA' + (url ? ('\nFinal URL: ' + url) : '') + '\nHeadlines (≤30):\n' +
        hs.map(function (h, i) { return (i + 1) + '. ' + h; }).join('\n') +
        '\nDescriptions (≤90):\n' + ds.map(function (x, i) { return (i + 1) + '. ' + x; }).join('\n');
      function sec(t, inner) { return '<div class="bb small" style="margin:14px 0 6px">' + t + '</div>' + inner; }
      function copyBtn(label, txt) { return '<button class="btn btn-sm cp" data-t="' + esc(txt) + '">' + esc(label) + '</button>'; }
      body.innerHTML =
        '<div class="row between wrap" style="gap:8px;margin-bottom:6px"><div class="soft small">ชุดแคมเปญพร้อมยิง — ก็อปทีละส่วนหรือทั้งหมด</div>' +
          '<button class="btn btn-sm btn-primary" id="bpAll">📋 คัดลอกทั้ง Blueprint</button></div>' +
        sec('1 · ตั้งค่าแคมเปญ', '<div class="hint" style="white-space:pre-line;line-height:1.7">' + esc(settings) + '</div>') +
        sec('2 · คีย์เวิร์ด (' + kws.length + ' คำ × Phrase+Exact) ' + copyBtn('คัดลอกคีย์', kwLines.join('\n')),
          '<div class="soft small" style="font-family:monospace;line-height:1.9;word-break:break-word">' + kwLines.map(esc).join(' · ') + '</div>') +
        sec('3 · Negative keywords ' + copyBtn('คัดลอก negative', NEGATIVES.map(function (n) { return '-' + n; }).join('\n')),
          '<div class="soft small" style="line-height:1.9">' + NEGATIVES.map(function (n) { return '<span class="chip" style="margin:2px">-' + esc(n) + '</span>'; }).join('') + '</div>') +
        sec('4 · โฆษณา RSA (headline/คำบรรยาย)',
          '<div class="soft small" style="margin-bottom:4px">Headlines:</div>' + hs.map(function (h) { return '<div class="list-row" style="gap:8px"><span class="grow">' + esc(h) + '</span><span class="soft small">' + h.length + '/30</span>' + copyBtn('คัดลอก', h) + '</div>'; }).join('') +
          '<div class="soft small" style="margin:10px 0 4px">Descriptions:</div>' + ds.map(function (x) { return '<div class="list-row" style="gap:8px"><span class="grow">' + esc(x) + '</span><span class="soft small">' + x.length + '/90</span>' + copyBtn('คัดลอก', x) + '</div>'; }).join('')) +
        '<div class="row" style="gap:8px;margin-top:16px"><a class="btn btn-primary" href="' + GADS + '" target="_blank" rel="noopener">เปิด Google Ads ↗</a></div>';
      var allBtn = document.getElementById('bpAll'); if (allBtn) allBtn.onclick = function () { copyText(full); };
      Array.prototype.forEach.call(body.querySelectorAll('.cp'), function (b) { b.onclick = function () { copyText(b.getAttribute('data-t')); }; });
    }).catch(function (e) {
      var body = document.getElementById('bp_body');
      if (body) body.innerHTML = '<div class="hint" style="color:var(--red-600)">สร้าง Blueprint ไม่สำเร็จ: ' + esc(e.message || String(e)) + '</div>';
    });
  }

  RP.views.ads = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · Google Ads', title: '📣 Google Ads',
      desc: 'ยิงโฆษณาแบบฉลาด — จ่ายเฉพาะคีย์ที่ “ยังไม่ติด organic” แล้วถอดเมื่อติดหน้า 1 (ประหยัดสุด)' });

    if (!(RP.isReal && RP.isReal())) {
      return { html: head + ui.card({ body: RP.noData('โหมดตัวอย่าง', 'เข้าสู่ระบบบัญชีจริงเพื่อดูคีย์ที่ควรยิง Ads จากข้อมูลอันดับของคุณ') }) };
    }
    var p = curProj();
    if (!p) {
      return { html: head + ui.card({ body: RP.noData('ยังไม่มีโปรเจ็ค', 'สร้างโปรเจ็คก่อน แล้วระบบจะแนะนำคีย์ที่ควรยิง Ads ให้', '<button class="btn btn-primary" id="adNew">＋ สร้างโปรเจ็ค</button>') }),
        mount: function (root) { var b = root.querySelector('#adNew'); if (b) b.onclick = function () { RP.go('projects'); }; } };
    }
    var pid = dbId(p);
    var html = head +
      ui.card({ title: 'วิธีทำงาน', cls: 'mb', body: HOWTO }) +
      '<div id="ads_bp" class="mb"></div>' +
      '<div id="ads_adv" class="mb"><div class="hint">กำลังวิเคราะห์ช่องว่างโฆษณา…</div></div>' +
      '<div id="ads_pause" class="mb"></div>';

    return { html: html, mount: function (root) {
      if (!(pid && RP.api.enabled())) {
        var a = root.querySelector('#ads_adv'); if (a) a.innerHTML = ui.card({ body: RP.noData('ยังไม่ได้เชื่อม backend', 'เปิดโหมด Live ในหน้า ⚙️ การตั้งค่า') });
        return;
      }
      RP.api.adsRecommend(pid).then(function (d) {
        var adv = d.advertise || [], pause = d.pause || [];
        var bp = root.querySelector('#ads_bp');
        if (bp) {
          bp.innerHTML = ui.card({ body:
            '<div class="row between wrap" style="gap:12px;align-items:center">' +
            '<div style="min-width:220px"><div class="bb">🗺 Campaign Blueprint — พร้อมยิง</div>' +
            '<div class="soft small">คลิกเดียว ได้ชุดแคมเปญครบ (คีย์ Phrase+Exact · negative keywords · ad copy · ตั้งค่า+งบ) → ก็อปเข้า Google Ads เลย</div></div>' +
            '<button class="btn btn-primary" id="bpGo">🗺 สร้าง Blueprint</button></div>' });
          var bg = root.querySelector('#bpGo'); if (bg) bg.onclick = function () { blueprintModal(pid, adv); };
        }
        var a = root.querySelector('#ads_adv');
        if (a) a.innerHTML = adv.length
          ? ui.card({ title: '🎯 แนะนำให้ยิง Ads (' + adv.length + ')', sub: 'คีย์มูลค่าที่ยังไม่ติดหน้า 1 — เรียงจากจ่อหน้า 1 ก่อน', flush: true,
              body: '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>คีย์เวิร์ด</th><th>สถานะ organic</th><th></th></tr></thead><tbody>' + rowsHtml(adv, true) + '</tbody></table></div>' })
          : ui.card({ title: '🎯 แนะนำให้ยิง Ads', body: RP.noData('ยังไม่มีคีย์แนะนำ', 'ต้องมีบทความ + วัดอันดับก่อน (ระบบวัดทุกวัน 06:00) — ค่อยมาดูใหม่') });
        var pz = root.querySelector('#ads_pause');
        if (pz) pz.innerHTML = pause.length
          ? ui.card({ title: '💰 ควรปิด Ads (ติดหน้า 1 organic แล้ว · ' + pause.length + ')', sub: 'ติดฟรีอยู่แล้ว — จ่าย Ads ซ้ำไม่คุ้ม', flush: true,
              body: '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>คีย์เวิร์ด</th><th>สถานะ</th></tr></thead><tbody>' + rowsHtml(pause, false) + '</tbody></table></div>' })
          : '';
        Array.prototype.forEach.call(root.querySelectorAll('.mk-ad'), function (b) {
          b.onclick = function () { creativeModal(pid, b.getAttribute('data-kw')); };
        });
      }).catch(function (e) {
        var a = root.querySelector('#ads_adv'); if (a) a.innerHTML = ui.card({ body: RP.noData('โหลดไม่ได้', esc(e.message || String(e))) });
      });
    } };
  };
})(window.RP);
