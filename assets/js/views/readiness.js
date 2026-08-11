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

  function jsWarn(d) {
    if (!d.js_app) return '';
    return '<div class="card card-pad mb" style="border:1px solid var(--amber-300,#fcd34d);background:var(--amber-50,#fffbeb)">' +
      '<div class="bb" style="color:var(--amber-700,#b45309)">⚠️ เว็บนี้เป็น JavaScript app (SPA)</div>' +
      '<div class="soft small" style="margin-top:4px">เนื้อหาโหลดด้วย JavaScript — ระบบอ่าน HTML ดิบไม่ครบ <b>คะแนนอาจต่ำกว่าจริง</b> · ควรตรวจ "หน้าเนื้อหาจริง" (บทความ/บริการ) ไม่ใช่หน้าแอป/ล็อกอิน</div></div>';
  }
  function googleSec(d) {
    var g = d.google; if (!g) return '';
    var idx = g.indexed_pages;
    var idxLine = (idx == null) ? '<span class="soft">ตรวจไม่ได้ (ต้องต่อ SERP API)</span>'
      : (idx > 0 ? '<b style="color:var(--green-600)">✅ Google เก็บหน้าเว็บคุณแล้ว (พบ ' + idx + ' หน้าในผลค้นหา)</b>'
        : '<b style="color:var(--red-600,#dc2626)">❌ Google ยังไม่เก็บหน้าเว็บคุณเลย</b> = ยังไม่มีทางติดอันดับ → ต้องส่ง sitemap + ขอ index ก่อน');
    var ranks = (g.ranks || []).map(function (r) {
      var v = (r.rank == null) ? '<span style="color:var(--red-600,#dc2626)">ยังไม่ติด 100 อันดับแรก</span>'
        : '<b style="color:' + (r.on_page1 ? 'var(--green-600)' : 'var(--amber-600)') + '">อันดับ ' + r.rank + (r.on_page1 ? ' · หน้า 1 🎉' : '') + '</b>';
      return '<div class="list-row" style="padding:5px 0"><span class="grow">"' + esc(r.keyword) + '"</span>' + v + '</div>';
    }).join('');
    return ui.card({ cls: 'mb', body:
      '<div class="bb" style="font-size:16px;margin-bottom:6px">🔎 ทำไมยังไม่ติด Google? (สถานะจริง)</div>' +
      '<div style="margin-bottom:' + (ranks ? '10px' : '0') + '">' + idxLine + '</div>' +
      (ranks ? ('<div class="soft small" style="margin-bottom:2px">อันดับคีย์เวิร์ดที่อยากติดตอนนี้:</div>' + ranks) : '') });
  }
  function aiSec(d) {
    var a = d.ai_test; if (!a || !a.engines || !a.engines.length) return '';
    var rows = a.engines.map(function (e) {
      return '<div style="border-top:1px solid var(--border);padding:10px 0">' +
        '<div class="row between"><b>' + esc(e.engine) + '</b>' +
        (e.cited ? '<span class="badge green">✅ แนะนำคุณ</span>' : '<span class="badge amber">❌ ยังไม่แนะนำคุณ</span>') + '</div>' +
        '<div class="soft small" style="margin-top:4px;font-style:italic">"' + esc((e.excerpt || '').slice(0, 280)) + '…"</div></div>';
    }).join('');
    var anyCited = a.engines.some(function (e) { return e.cited; });
    return ui.card({ cls: 'mb', body:
      '<div class="bb" style="font-size:16px">🤖 AI เริ่มแนะนำคุณยัง? (ถามจริง)</div>' +
      '<div class="soft small" style="margin:2px 0 4px">ลองถาม AI ว่า: "<b>' + esc(a.question) + '</b>"</div>' + rows +
      '<div class="hint" style="margin-top:8px">' + (anyCited ? 'AI เริ่มรู้จักคุณแล้ว 🎉 — ดันต่อให้เด่นขึ้น' : 'AI ยังไม่แนะนำคุณ = โอกาส blue-ocean · เราทำ AEO/GEO ให้ AI หยิบคุณไปตอบ') + '</div>' });
  }

  function render(out, d, ctx) {
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

    // แถบเช็กลิสต์: นับปัจจัยที่ 'ผ่าน' vs ทั้งหมด (SEO + AEO/GEO) → เห็นชัดว่าขาดกี่ข้อ
    var allF = (d.factors || []).concat(d.aeo_factors || []);
    var passF = allF.filter(function (f) { return f.tone === 'ok'; }).length;
    var lackF = allF.length - passF;
    var checklistBar = allF.length
      ? ui.card({ cls: 'mb', body:
          '<div class="row between wrap" style="gap:8px"><div class="bb" style="font-size:16px">📋 เช็กลิสต์ความพร้อมเว็บ</div>' +
          '<span class="badge ' + (lackF === 0 ? 'green' : 'amber') + '" style="font-size:14px">ผ่าน ' + passF + '/' + allF.length + ' ข้อ' +
          (lackF ? ' · ต้องทำอีก ' + lackF + ' ข้อ' : ' · ครบแล้ว 🎉') + '</span></div>' +
          '<div style="margin-top:8px">' + ui.bar(passF / allF.length * 100, lackF === 0 ? 'green' : '') + '</div>' +
          '<div class="soft small" style="margin-top:6px">❌/🟡 ด้านล่างคือข้อที่ยัง "ขาด" — ทำครบเว็บพร้อมดันอันดับเต็มที่</div>' })
      : '';

    out.innerHTML =
      '<div class="row wrap" style="gap:10px;margin-bottom:8px">' +
        scoreCard('🟦 SEO (ติดอันดับ Google)', d.score, d.grade) +
        scoreCard('🟪 AEO / GEO (AI แนะนำ)', d.aeo_score, d.aeo_grade) +
      '</div>' +
      '<div class="hint" style="margin-bottom:12px">' + esc(d.aeo_summary || d.summary || '') + '</div>' +
      jsWarn(d) + googleSec(d) + aiSec(d) +
      checklistBar +

      (((d.aeo_score == null || d.aeo_score < 70) || (d.score == null || d.score < 70)) ?
        '<div class="card card-pad" style="margin-bottom:12px;background:linear-gradient(135deg,#1a56ff,#5b4ff0);color:#fff">' +
        '<div style="font-weight:800;font-size:16px">🚀 เว็บนี้ยังไม่พร้อม 100% — สร้างใหม่ให้พร้อม AEO/GEO ในตัว</div>' +
        '<div style="opacity:.92;font-size:14px;margin:4px 0 10px">IM WEB สร้างเว็บที่ฝัง schema + FAQ + llms.txt + โครง answer-first ให้ตั้งแต่แรก (~2 นาที) แล้วเอามาต่อ SEO/AEO/GEO กับเราได้ทันที</div>' +
        '<a href="https://imweb.studio" target="_blank" rel="noopener" style="display:inline-block;background:#fff;color:#1a56ff;font-weight:800;padding:9px 20px;border-radius:999px;text-decoration:none">สร้างเว็บด้วย IM WEB →</a></div>' : '') +

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
      '<div class="row wrap" style="margin-top:12px;gap:8px">' +
        '<button class="btn btn-sm" id="rd_copy">📋 คัดลอกรายงาน (ข้อความ)</button>' +
        '<button class="btn btn-sm btn-primary" id="rd_link">📤 สร้างลิงก์รายงานส่งลูกค้า (เก็บลีด)</button>' +
      '</div><div id="rd_linkbox" style="margin-top:10px"></div>';

    var cp = document.getElementById('rd_copy');
    if (cp) cp.onclick = function () { copyText(buildReport(d)); };

    var lk = document.getElementById('rd_link');
    if (lk) lk.onclick = function () {
      if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live'); return; }
      lk.disabled = true; lk.textContent = 'กำลังสร้างลิงก์…';
      RP.api.createSiteReport({
        url: (ctx && ctx.url) || d.url || '',
        keywords: (ctx && ctx.kw) || [],
        business_name: (ctx && ctx.biz) || ''
      }).then(function (r) {
        var link = r.public_url || r.path || '';
        var box = document.getElementById('rd_linkbox');
        box.innerHTML = ui.card({ body:
          '<div class="bb" style="font-size:15px;margin-bottom:6px">✅ ลิงก์รายงานพร้อมส่งลูกค้าแล้ว</div>' +
          '<div class="row wrap" style="gap:8px;align-items:center">' +
            '<input class="input" id="rd_linkval" readonly value="' + esc(link) + '" style="flex:1;min-width:220px">' +
            '<button class="btn btn-sm" id="rd_copylink">📋 คัดลอก</button>' +
            '<a class="btn btn-sm" href="' + esc(link) + '" target="_blank" rel="noopener">👁️ เปิดดู</a>' +
          '</div>' +
          '<div class="soft small" style="margin-top:8px;line-height:1.6">ส่งลิงก์นี้ให้ลูกค้า → เขาเห็นคะแนน + ปัญหาเว็บ แล้วกรอกเบอร์เพื่อดู "แผนแก้เต็ม" → คุณได้ลีดเด้งเข้า LINE ทันที 🔔</div>' });
        var cb = document.getElementById('rd_copylink');
        if (cb) cb.onclick = function () { copyText(link); };
        lk.textContent = '✅ สร้างลิงก์แล้ว';
      }).catch(function (e) {
        lk.disabled = false; lk.textContent = '📤 สร้างลิงก์รายงานส่งลูกค้า (เก็บลีด)';
        ui.toast('สร้างลิงก์ไม่ได้: ' + esc(e.message || String(e)));
      });
    };
  }

  RP.views.readiness = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · เครื่องมือแอดมิน', title: '🩺 เช็กสุขภาพเว็บ (Readiness)',
      desc: 'วางลิงก์เว็บลูกค้า → ระบบอ่านหน้าเว็บจริง แล้วบอกว่าต้องทำอะไรให้ "รองรับครบ SEO + AEO + GEO" · เอาไปโชว์ลูกค้าตอน onboard ได้เลย (ตัวเลขจริง ไม่กุ)' });
    var form = ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-end">' +
      '<div style="flex:3;min-width:220px"><div class="soft small" style="margin-bottom:4px">ลิงก์เว็บลูกค้า</div><input class="input" id="rd_url" placeholder="เช่น yourclient.com หรือ https://yourclient.com" style="width:100%"></div>' +
      '<div style="flex:2;min-width:170px"><div class="soft small" style="margin-bottom:4px">คีย์เวิร์ดที่อยากติด (ไม่บังคับ · คั่นด้วย ,)</div><input class="input" id="rd_kw" placeholder="เช่น รับทำเว็บ, คลินิก" style="width:100%"></div>' +
      '<div style="flex:2;min-width:170px"><div class="soft small" style="margin-bottom:4px">ชื่อธุรกิจลูกค้า (ไม่บังคับ)</div><input class="input" id="rd_biz" placeholder="เช่น ร้านกาแฟบ้านหอม" style="width:100%"></div>' +
      '<button class="btn btn-primary" id="rd_go">🔎 เช็กสุขภาพ</button></div>' +
      '<div class="hint" style="margin-top:8px">อ่านหน้าแรกของเว็บจริง (สาธารณะ · https) → คะแนน SEO + AEO/GEO + เช็กลิสต์ต้องทำอะไร</div>' });

    return { html: head + form + '<div id="rd_out"></div>', mount: function (root) {
      var go = root.querySelector('#rd_go'), out = root.querySelector('#rd_out');
      function run() {
        var url = (root.querySelector('#rd_url').value || '').trim();
        var kw = (root.querySelector('#rd_kw').value || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 3);
        var biz = (root.querySelector('#rd_biz').value || '').trim();
        if (!url) { ui.toast('ใส่ลิงก์เว็บก่อน'); return; }
        if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live ในหน้าตั้งค่า'); return; }
        go.disabled = true; go.textContent = 'กำลังตรวจ…';
        out.innerHTML = '<div class="hint">⏳ กำลังอ่านเว็บ + เช็ก Google + ถาม AI จริงว่าแนะนำคุณไหม… (20–40 วิ)</div>';
        RP.api.siteCheck(url, kw, biz).then(function (d) {
          render(out, d, { url: url, kw: kw, biz: biz });
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
