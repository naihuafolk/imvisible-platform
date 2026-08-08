/* ============================================================
   View: 🩺 เช็กสุขภาพเว็บ (Readiness) — วางลิงก์เว็บลูกค้า → บอกว่าต้องทำอะไร
   ให้ 'รองรับครบ SEO + AEO + GEO' · ใช้ engine เดียวกับ /tool/ (sitecheck จริง)
   เหมาะตอน onboard ลูกค้า: โชว์ให้เห็นว่าเว็บเขาขาดอะไร (เอาไปคุยปิดการขายได้)
   ทุกคะแนนมาจากการอ่านหน้าเว็บจริง — ไม่กุ (no-faking)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function toneIcon(t) { return t === 'ok' ? '✅' : t === 'warn' ? '🟡' : '❌'; }
  function scoreColor(s) { return s == null ? '#94a3b8' : s >= 85 ? '#0a7350' : s >= 55 ? '#b45309' : '#c0392b'; }

  function copyText(t) {
    try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); }
    catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); }
  }

  function scoreCard(label, score, grade) {
    var c = scoreColor(score);
    return '<div class="card card-pad" style="flex:1;min-width:150px;text-align:center">' +
      '<div class="soft small">' + label + '</div>' +
      '<div class="bb" style="font-size:34px;line-height:1.1;color:' + c + '">' + (score == null ? '—' : score) +
      '<span style="font-size:16px;color:var(--muted,#94a3b8)">/100</span></div>' +
      '<div style="font-weight:800;color:' + c + '">เกรด ' + esc(grade || '—') + '</div></div>';
  }

  // เช็กลิสต์ปัจจัย (✅/🟡/❌ + วิธีแก้)
  function factorList(factors) {
    if (!factors || !factors.length) return '<div class="soft small">—</div>';
    return '<div class="rows">' + factors.map(function (f) {
      return '<div class="item" style="display:block;padding:10px 4px;border-top:1px solid var(--line,#eee)">' +
        '<div><span style="font-size:1.05em">' + toneIcon(f.tone) + '</span> <b>' + esc(f.label) + '</b>' +
        '<span class="soft small" style="margin-left:6px">' + esc(f.detail || '') + '</span></div>' +
        (f.tone !== 'ok' && f.fix ? '<div class="soft small" style="color:#b45309;margin-top:2px;padding-left:22px">→ ' + esc(f.fix) + '</div>' : '') +
        '</div>';
    }).join('') + '</div>';
  }

  function buildReport(d) {
    var out = 'รายงานสุขภาพเว็บ — ' + (d.url || '') + '\n' +
      'SEO ' + d.score + '/100 (' + d.grade + ') · AEO/GEO ' + d.aeo_score + '/100 (' + d.aeo_grade + ')\n' +
      (d.aeo_summary || '') + '\n\nสิ่งที่ต้องทำก่อน (ดันได้เร็วสุด):\n';
    (d.aeo_fixes || []).concat(d.top_fixes || []).slice(0, 8).forEach(function (x) {
      out += '• ' + (x.fix || x.label) + '\n';
    });
    out += '\n(ตรวจจากหน้าเว็บจริง · ตัวเลขจริง ไม่กุ)';
    return out;
  }

  function render(out, d) {
    if (!d || !d.ok) {
      out.innerHTML = ui.card({ body: RP.noData('อ่านเว็บไม่ได้', esc((d && d.note) || 'ใส่โดเมนเว็บสาธารณะที่รองรับ https')) });
      return;
    }
    // รวม fixes สำคัญ (AEO/GEO ก่อน แล้ว SEO) เรียงตาม gain
    var fixes = (d.aeo_fixes || []).concat(d.top_fixes || []);
    var fixHtml = fixes.length
      ? '<ol style="margin:6px 0 0;padding-left:20px;line-height:1.7">' +
        fixes.slice(0, 8).map(function (x) {
          return '<li><b>' + esc(x.label || '') + '</b> — ' + esc(x.fix || '') +
            (x.gain ? ' <span class="soft small">(+' + x.gain + ')</span>' : '') + '</li>';
        }).join('') + '</ol>'
      : '<div class="soft small">เว็บพื้นฐานแน่นแล้ว 🎉</div>';

    out.innerHTML =
      '<div class="row wrap" style="gap:10px;margin-bottom:8px">' +
        scoreCard('🟦 SEO (ติดอันดับ Google)', d.score, d.grade) +
        scoreCard('🟪 AEO / GEO (AI แนะนำ)', d.aeo_score, d.aeo_grade) +
      '</div>' +
      '<div class="hint" style="margin-bottom:12px">' + esc(d.aeo_summary || d.summary || '') + '</div>' +

      ui.card({ cls: 'mb', body:
        '<div class="bb" style="font-size:16px;margin-bottom:4px">🔧 ต้องทำอะไรก่อน (ดันได้เร็วสุด)</div>' + fixHtml }) +

      ui.card({ cls: 'mb', body:
        '<div class="bb" style="font-size:16px;margin-bottom:2px">🟪 ความพร้อม AEO / GEO (ให้ AI หยิบไปแนะนำ)</div>' +
        '<div class="soft small" style="margin-bottom:4px">schema · ตัวตนแบรนด์ · Q&amp;A/FAQ · answer-first · โครงหัวข้อ · เนื้อหา · llms.txt</div>' +
        factorList(d.aeo_factors) }) +

      ui.card({ cls: 'mb', body:
        '<div class="bb" style="font-size:16px;margin-bottom:2px">🟦 ความพร้อม SEO (ติดอันดับ Google)</div>' +
        factorList(d.factors) }) +

      '<div class="hint" style="margin-top:6px">' + esc(d.note || '') + '</div>' +
      '<div class="row" style="margin-top:12px;gap:8px"><button class="btn btn-sm" id="rd_copy">📋 คัดลอกรายงาน (ส่งลูกค้า)</button></div>';

    var cp = document.getElementById('rd_copy');
    if (cp) cp.onclick = function () { copyText(buildReport(d)); };
  }

  RP.views.readiness = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · เครื่องมือแอดมิน', title: '🩺 เช็กสุขภาพเว็บ (Readiness)',
      desc: 'วางลิงก์เว็บลูกค้า → ระบบอ่านหน้าเว็บจริง แล้วบอกว่าต้องทำอะไรให้ "รองรับครบ SEO + AEO + GEO" · เอาไปโชว์ลูกค้าตอน onboard ได้เลย (ตัวเลขจริง ไม่กุ)' });
    var form = ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-end">' +
      '<div style="flex:3;min-width:220px"><div class="soft small" style="margin-bottom:4px">ลิงก์เว็บลูกค้า</div><input class="input" id="rd_url" placeholder="เช่น yourclient.com หรือ https://yourclient.com" style="width:100%"></div>' +
      '<div style="flex:2;min-width:180px"><div class="soft small" style="margin-bottom:4px">คีย์เวิร์ดที่อยากติด (ไม่บังคับ · คั่นด้วย ,)</div><input class="input" id="rd_kw" placeholder="เช่น รับทำเว็บ, คลินิก" style="width:100%"></div>' +
      '<button class="btn btn-primary" id="rd_go">🔎 เช็กสุขภาพ</button></div>' +
      '<div class="hint" style="margin-top:8px">อ่านหน้าแรกของเว็บจริง (สาธารณะ · https) → คะแนน SEO + AEO/GEO + เช็กลิสต์ต้องทำอะไร</div>' });

    return { html: head + form + '<div id="rd_out"></div>', mount: function (root) {
      var go = root.querySelector('#rd_go'), out = root.querySelector('#rd_out');
      function run() {
        var url = (root.querySelector('#rd_url').value || '').trim();
        var kw = (root.querySelector('#rd_kw').value || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 3);
        if (!url) { ui.toast('ใส่ลิงก์เว็บก่อน'); return; }
        if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live ในหน้าตั้งค่า'); return; }
        go.disabled = true; go.textContent = 'กำลังตรวจ…';
        out.innerHTML = '<div class="hint">⏳ กำลังอ่านหน้าเว็บจริง + ให้คะแนน SEO/AEO/GEO… (5–15 วิ)</div>';
        RP.api.siteCheck(url, kw).then(function (d) {
          render(out, d);
        }).catch(function (e) {
          out.innerHTML = ui.card({ body: RP.noData('ตรวจไม่ได้', esc(e.message || String(e))) });
        }).then(function () { go.disabled = false; go.textContent = '🔎 เช็กสุขภาพ'; });
      }
      if (go) go.onclick = run;
      ['rd_url', 'rd_kw'].forEach(function (id) {
        var el = root.querySelector('#' + id);
        if (el) el.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(); });
      });
    } };
  };
})(window.RP);
