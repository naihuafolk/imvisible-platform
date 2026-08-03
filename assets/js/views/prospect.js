/* ============================================================
   View: รายงานคีย์เวิร์ด (ขายลูกค้า) — Prospecting Report
   ใส่คีย์+ธุรกิจ → ดึงคีย์ที่เกี่ยว 20+ พร้อม ปริมาณค้นหาจริง/เดือน+วัน + % ความยากติดหน้า 1
   ตัวเลขจริงจาก DataForSEO (no-faking) — เอาไปโชว์ปิดการขาย
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function diffColor(d) { return d == null ? '#94a3b8' : d < 30 ? '#0a7350' : d < 60 ? '#b45309' : '#c0392b'; }
  function diffLabel(d) { return d == null ? '—' : d < 30 ? 'ง่าย' : d < 60 ? 'ปานกลาง' : 'ยาก'; }
  function fmtn(n) { return (n == null) ? '—' : Number(n).toLocaleString(); }

  function copyText(t) {
    try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); }
    catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); }
  }

  function renderReport(out, d) {
    var kws = d.keywords || [], s = d.summary || {};
    var cards = [
      ['คีย์เวิร์ดที่เกี่ยว', fmtn(s.count)],
      ['เข้าถึงรวม/เดือน', fmtn(s.total_monthly)],
      ['เข้าถึงรวม/วัน', fmtn(s.total_daily)],
      ['ความยากเฉลี่ย', s.avg_difficulty == null ? '—' : s.avg_difficulty + '%']
    ].map(function (c) {
      return '<div class="card card-pad" style="flex:1;min-width:140px"><div class="soft small">' + c[0] + '</div><div class="bb" style="font-size:23px;color:var(--brand-700,#4338ca)">' + c[1] + '</div></div>';
    }).join('');
    var rows = kws.map(function (k) {
      var dc = diffColor(k.difficulty);
      return '<tr>' +
        '<td><div class="t">' + esc(k.keyword) + '</div></td>' +
        '<td class="right" style="font-variant-numeric:tabular-nums">' + fmtn(k.volume) + '</td>' +
        '<td class="right" style="font-variant-numeric:tabular-nums">' + fmtn(k.daily) + '</td>' +
        '<td class="right"><b style="color:' + dc + '">' + (k.difficulty == null ? '—' : k.difficulty + '%') + '</b> <span class="soft small">' + diffLabel(k.difficulty) + '</span></td>' +
        '</tr>';
    }).join('');
    out.innerHTML =
      '<div class="row wrap" style="gap:10px;margin-bottom:12px">' + cards + '</div>' +
      '<div class="soft small" style="margin-bottom:10px">🟢 ง่าย ' + (s.easy || 0) + ' · 🟡 ปานกลาง ' + (s.medium || 0) + ' · 🔴 ยาก ' + (s.hard || 0) + ' — <b>ยิ่งความยากต่ำ ยิ่งทำติดหน้า 1 เร็ว</b></div>' +
      ui.card({ flush: true, body:
        '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>คีย์เวิร์ด</th><th class="right">ค้นหา/เดือน</th><th class="right">/วัน</th><th class="right">ความยากติดหน้า 1</th></tr></thead><tbody>' + rows + '</tbody></table></div>' }) +
      '<div class="hint" style="margin-top:10px">' + esc(d.note || '') + '</div>' +
      '<div class="row" style="margin-top:12px;gap:8px"><button class="btn btn-sm" id="kr_copy">📋 คัดลอกรายงาน (สำหรับส่งลูกค้า)</button></div>';
    var cp = document.getElementById('kr_copy');
    if (cp) cp.onclick = function () {
      var head = 'รายงานโอกาสคีย์เวิร์ด — ' + (d.keyword || d.business || '') +
        '\nเข้าถึงรวม ' + fmtn(s.total_monthly) + '/เดือน (' + fmtn(s.total_daily) + '/วัน) · ความยากเฉลี่ย ' + (s.avg_difficulty == null ? '—' : s.avg_difficulty + '%') +
        '\n(ที่มา: Google Ads · DataForSEO — ตรวจสอบย้อนได้)\n\n';
      var body = kws.map(function (k) {
        return '• ' + k.keyword + ' — ' + fmtn(k.volume) + '/เดือน · ' + fmtn(k.daily) + '/วัน · ยาก ' + (k.difficulty == null ? '—' : k.difficulty + '%') + ' (' + diffLabel(k.difficulty) + ')';
      }).join('\n');
      copyText(head + body);
    };
  }

  RP.views.prospect = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · เครื่องมือขาย', title: '💼 รายงานคีย์เวิร์ด (ขายลูกค้า)',
      desc: 'ใส่คีย์เวิร์ด + ธุรกิจ → ดึงคีย์ที่เกี่ยว 20+ คำ พร้อม "ปริมาณค้นหาจริง/เดือน+วัน" และ "% ความยากติดหน้า 1" (DataForSEO) — เอาไปโชว์ปิดการขาย' });
    var form = ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-end">' +
      '<div style="flex:2;min-width:200px"><div class="soft small" style="margin-bottom:4px">คีย์เวิร์ดหลัก</div><input class="input" id="kr_kw" placeholder="เช่น รับทำ seo · คลินิกความงาม · ติวเตอร์" style="width:100%"></div>' +
      '<div style="flex:2;min-width:200px"><div class="soft small" style="margin-bottom:4px">ธุรกิจ (ไม่บังคับ · ช่วยให้ตรงขึ้น)</div><input class="input" id="kr_biz" placeholder="เช่น คลินิกความงามย่านทองหล่อ" style="width:100%"></div>' +
      '<button class="btn btn-primary" id="kr_go">🔎 สร้างรายงาน</button></div>' +
      '<div class="hint" style="margin-top:8px">ดึงข้อมูลค้นหาจริง + ความยากจาก DataForSEO (กินเครดิตต่อครั้ง) · เหมาะสำหรับทำ proposal เสนอลูกค้า</div>' });
    return { html: head + form + '<div id="kr_out"></div>', mount: function (root) {
      var go = root.querySelector('#kr_go'), out = root.querySelector('#kr_out');
      function run() {
        var kw = (root.querySelector('#kr_kw').value || '').trim(), biz = (root.querySelector('#kr_biz').value || '').trim();
        if (!kw && !biz) { ui.toast('ใส่คีย์เวิร์ดหรือธุรกิจก่อน'); return; }
        if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live ในหน้าตั้งค่า'); return; }
        go.disabled = true; go.textContent = 'กำลังดึง…';
        out.innerHTML = '<div class="hint">⏳ ดึงคีย์เวิร์ด + ปริมาณค้นหา + ความยาก จาก DataForSEO… (10–30 วิ)</div>';
        RP.api.keywordReport({ keyword: kw, business: biz }).then(function (d) {
          if (!d.keywords || !d.keywords.length) { out.innerHTML = ui.card({ body: RP.noData('ไม่พบข้อมูล', 'ลองคีย์อื่น หรือเช็กเครดิต DataForSEO') }); return; }
          renderReport(out, d);
        }).catch(function (e) {
          out.innerHTML = ui.card({ body: RP.noData('ดึงไม่ได้', esc(e.message || String(e))) });
        }).then(function () { go.disabled = false; go.textContent = '🔎 สร้างรายงาน'; });
      }
      if (go) go.onclick = run;
      ['kr_kw', 'kr_biz'].forEach(function (id) {
        var el = root.querySelector('#' + id);
        if (el) el.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(); });
      });
    } };
  };
})(window.RP);
