/* ============================================================
   View: เรดาร์ Pantip — หากระทู้ที่ติดหน้า 1 Google (SERP จริง)
   → AI ร่างคำตอบ "ช่วยจริง ไม่ขายของ" → คน 'ตรวจ + โพสต์เอง'
   ขาว 100% · ไม่โพสต์อัตโนมัติ (auto-post = สแปม = โดนแบน)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function copyText(t) {
    try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); }
    catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); }
  }

  function threadCard(t, idx) {
    var col = t.rank <= 3 ? '#0a7350' : '#1a56ff';
    var badge = '<span style="display:inline-block;background:' + col + ';color:#fff;font-weight:800;font-size:.72rem;padding:2px 10px;border-radius:999px;white-space:nowrap">หน้า 1 · อันดับ ' + t.rank + '</span>';
    return '<div class="card card-pad" style="margin-bottom:10px">' +
      '<div style="display:flex;gap:9px;align-items:flex-start;flex-wrap:wrap">' + badge +
        '<span class="soft small" style="margin-top:1px">จากการค้น: “' + esc(t.query) + '”</span></div>' +
      '<a href="' + esc(t.url) + '" target="_blank" rel="noopener" style="display:inline-block;margin-top:7px;font-weight:700;color:var(--brand-700,#4338ca);text-decoration:none">' + esc(t.title) + '</a>' +
      (t.snippet ? '<div class="soft small" style="margin-top:4px;line-height:1.5">' + esc(t.snippet) + '</div>' : '') +
      '<div class="row" style="margin-top:11px;gap:8px">' +
        '<button class="btn btn-sm pt-draft" data-idx="' + idx + '">✍️ ร่างคำตอบ (ช่วยจริง)</button>' +
        '<a class="btn btn-sm" href="' + esc(t.url) + '" target="_blank" rel="noopener">เปิดกระทู้ →</a>' +
      '</div>' +
      '<div class="pt-reply" data-idx="' + idx + '"></div>' +
    '</div>';
  }

  function render(out, d, biz) {
    var ts = d.threads || [];
    out.innerHTML =
      '<div class="soft small" style="margin-bottom:10px">พบ <b>' + ts.length + '</b> กระทู้ Pantip ติดหน้า 1 Google — ตอบให้ <b>มีประโยชน์จริง</b> = ยืมทราฟฟิก+ความน่าเชื่อถือที่กระทู้มีอยู่แล้ว</div>' +
      ts.map(threadCard).join('') +
      '<div class="hint" style="margin-top:8px">⚠️ ' + esc(d.note || '') + '</div>';
    ts.forEach(function (t, idx) {
      var btn = out.querySelector('.pt-draft[data-idx="' + idx + '"]');
      if (!btn) return;
      btn.onclick = function () {
        var box = out.querySelector('.pt-reply[data-idx="' + idx + '"]');
        btn.disabled = true; btn.textContent = 'กำลังร่าง…';
        box.innerHTML = '<div class="hint" style="margin-top:10px">⏳ AI กำลังร่างคำตอบที่ช่วยจริง…</div>';
        RP.api.pantipReply({ url: t.url, title: t.title, snippet: t.snippet, brand: biz || '' }).then(function (r) {
          box.innerHTML = '<div style="margin-top:10px">' + ui.card({ body:
            '<div class="soft small" style="margin-bottom:6px">📝 ร่างคำตอบ (ตรวจให้เข้ากับกระทู้ก่อนโพสต์เอง · ห้ามยัดลิงก์/โฆษณา):</div>' +
            '<div style="white-space:pre-wrap;line-height:1.62">' + esc(r.reply || '') + '</div>' +
            '<div class="row" style="margin-top:11px;gap:8px"><button class="btn btn-sm pt-copy">📋 คัดลอกคำตอบ</button><a class="btn btn-sm btn-primary" href="' + esc(t.url) + '" target="_blank" rel="noopener">ไปโพสต์ที่กระทู้ →</a></div>' }) + '</div>';
          var cp = box.querySelector('.pt-copy');
          if (cp) cp.onclick = function () { copyText(r.reply || ''); };
        }).catch(function (e) {
          box.innerHTML = '<div style="margin-top:10px">' + ui.card({ body: RP.noData('ร่างไม่ได้', esc(e.message || String(e))) }) + '</div>';
        }).then(function () { btn.disabled = false; btn.textContent = '✍️ ร่างใหม่'; });
      };
    });
  }

  RP.views.pantip = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · เครื่องมือโต', title: '🎯 เรดาร์ Pantip',
      desc: 'ใส่หัวข้อ → หากระทู้ Pantip ที่ "ติดหน้า 1 Google" จริง แล้วให้ AI ร่างคำตอบที่ช่วยจริง ไม่ขายของ → คุณตรวจแล้วโพสต์เอง (ยืมทราฟฟิก+ความน่าเชื่อถือ ไม่สแปม ไม่ auto)' });
    var form = ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-end">' +
      '<div style="flex:2;min-width:200px"><div class="soft small" style="margin-bottom:4px">หัวข้อ / คีย์เวิร์ด</div><input class="input" id="pt_kw" placeholder="เช่น รับทำ SEO · การตลาด AI · ChatGPT SEO" style="width:100%"></div>' +
      '<div style="flex:2;min-width:200px"><div class="soft small" style="margin-bottom:4px">แบรนด์/ธุรกิจ (ไม่บังคับ · ใช้ตอนร่างคำตอบ)</div><input class="input" id="pt_biz" placeholder="เช่น ImVisible" style="width:100%"></div>' +
      '<button class="btn btn-primary" id="pt_go">🔎 หากระทู้</button></div>' +
      '<div class="hint" style="margin-top:8px">ดึงผล Google จริงจาก DataForSEO · ตอบให้มีประโยชน์จริงก่อนค่อยแนบลิงก์ · <b>ห้ามโพสต์อัตโนมัติ = โดนแบน</b></div>' });
    return { html: head + form + '<div id="pt_out"></div>', mount: function (root) {
      var go = root.querySelector('#pt_go'), out = root.querySelector('#pt_out');
      function run() {
        var kw = (root.querySelector('#pt_kw').value || '').trim(), biz = (root.querySelector('#pt_biz').value || '').trim();
        if (!kw) { ui.toast('ใส่หัวข้อ/คีย์เวิร์ดก่อน'); return; }
        if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live ในหน้าตั้งค่า'); return; }
        go.disabled = true; go.textContent = 'กำลังหา…';
        out.innerHTML = '<div class="hint">⏳ ค้น Google หากระทู้ Pantip ที่ติดหน้า 1… (10–20 วิ)</div>';
        RP.api.pantipRadar({ keyword: kw, business: biz }).then(function (d) {
          if (!d.threads || !d.threads.length) { out.innerHTML = ui.card({ body: RP.noData('ไม่พบกระทู้ Pantip หน้า 1', 'ลองหัวข้อกว้างขึ้น เช่น “SEO” “การตลาดออนไลน์” หรือคำถามที่คนมักถามกัน') }); return; }
          render(out, d, biz);
        }).catch(function (e) {
          out.innerHTML = ui.card({ body: RP.noData('ดึงไม่ได้', esc(e.message || String(e))) });
        }).then(function () { go.disabled = false; go.textContent = '🔎 หากระทู้'; });
      }
      if (go) go.onclick = run;
      ['pt_kw', 'pt_biz'].forEach(function (id) {
        var el = root.querySelector('#' + id);
        if (el) el.addEventListener('keydown', function (e) { if (e.key === 'Enter') run(); });
      });
    } };
  };
})(window.RP);
