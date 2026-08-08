/* ============================================================
   View: 📥 ลีดจากรายงาน (Report Leads) — "รายชื่อโทรตามปิดการขาย"
   รวมลีดที่ลูกค้ากรอกจากหน้ารายงานสุขภาพเว็บ (public) + ลิงก์รายงานที่พนักงานสร้างไว้
   วงจรขายตัวเอง: พนักงานสร้างลิงก์ (หน้า Readiness) → ส่งลูกค้า → ลูกค้ากรอก → เด้ง LINE + โผล่ที่นี่
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function copyText(t) {
    try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); }
    catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); }
  }

  function fmt(at) {
    if (!at) return '—';
    try { return new Date(at).toLocaleString('th-TH', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); }
    catch (e) { return String(at).slice(0, 16).replace('T', ' '); }
  }

  function scoreColor(s) { return s == null ? '#94a3b8' : s >= 85 ? '#0a7350' : s >= 55 ? '#b45309' : '#c0392b'; }

  function leadCard(l) {
    var tel = (l.phone || '').replace(/[^0-9+]/g, '');
    var link = l.public_url || l.path || '';
    return '<div class="card card-pad" style="margin-bottom:8px">' +
      '<div class="row" style="justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap">' +
        '<div><div class="bb" style="font-size:16px">👤 ' + esc(l.name || '(ไม่ระบุชื่อ)') + '</div>' +
          '<div class="soft small">🏢 ' + esc(l.business || l.domain || '-') + '</div></div>' +
        '<div class="soft small" style="text-align:right">' + esc(fmt(l.at)) +
          '<div>SEO <b style="color:' + scoreColor(l.score) + '">' + (l.score == null ? '—' : l.score) + '</b> · ' +
          'AEO <b style="color:' + scoreColor(l.aeo_score) + '">' + (l.aeo_score == null ? '—' : l.aeo_score) + '</b></div></div>' +
      '</div>' +
      '<div class="row wrap" style="gap:8px;margin-top:8px;align-items:center">' +
        (l.phone ? '<a class="btn btn-sm btn-primary" href="tel:' + esc(tel) + '">📞 ' + esc(l.phone) + '</a>' : '') +
        (l.contact ? '<span class="soft small">💬 ' + esc(l.contact) + '</span>' : '') +
        (link ? '<a class="btn btn-sm" href="' + esc(link) + '" target="_blank" rel="noopener">👁️ ดูรายงาน</a>' : '') +
      '</div>' +
      (l.message ? '<div class="soft small" style="margin-top:6px;padding:8px 10px;background:var(--wash,#f6f8fd);border-radius:8px">🗒️ ' + esc(l.message) + '</div>' : '') +
      '</div>';
  }

  function reportRow(r) {
    var link = r.public_url || r.path || '';
    return '<div class="card card-pad" style="margin-bottom:8px">' +
      '<div class="row" style="justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap">' +
        '<div><b>' + esc(r.business || r.domain || '-') + '</b>' +
          '<div class="soft small">SEO ' + (r.score == null ? '—' : r.score) + ' · AEO/GEO ' + (r.aeo_score == null ? '—' : r.aeo_score) +
          ' · สร้างเมื่อ ' + esc(fmt(r.at)) + '</div></div>' +
        '<div class="row" style="gap:6px;align-items:center">' +
          '<span class="n-tag count" title="จำนวนลีด">' + (r.leads || 0) + ' ลีด</span>' +
          '<button class="btn btn-sm rp-copy" data-link="' + esc(link) + '">📋 คัดลอกลิงก์</button>' +
          '<a class="btn btn-sm" href="' + esc(link) + '" target="_blank" rel="noopener">เปิด</a>' +
        '</div>' +
      '</div></div>';
  }

  RP.views.reports = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · หาลูกค้า', title: '📥 ลีดจากรายงาน',
      desc: 'ลูกค้าที่กรอกข้อมูลจากหน้ารายงานสุขภาพเว็บ = "รายชื่อโทรตามปิดการขาย" (เด้ง LINE ทันทีตอนกรอก) · สร้างลิงก์รายงานได้ที่หน้า 🩺 เช็กสุขภาพเว็บ' });

    return {
      html: head +
        '<div class="row" style="gap:8px;margin-bottom:10px"><button class="btn btn-sm" id="rp_refresh">🔄 รีเฟรช</button></div>' +
        '<div id="rp_leads"><div class="hint">⏳ กำลังโหลดลีด…</div></div>' +
        '<div id="rp_links" style="margin-top:18px"></div>',
      mount: function (root) {
        var leadsEl = root.querySelector('#rp_leads'), linksEl = root.querySelector('#rp_links');

        function bindCopies(scope) {
          (scope || root).querySelectorAll('.rp-copy').forEach(function (b) {
            b.onclick = function () { copyText(b.getAttribute('data-link') || ''); };
          });
        }

        function load() {
          if (!(RP.api && RP.api.reachable())) {
            leadsEl.innerHTML = ui.card({ body: RP.noData('เชื่อมต่อ backend ไม่ได้', 'เปิดโหมด Live ในหน้าตั้งค่า') });
            linksEl.innerHTML = ''; return;
          }
          leadsEl.innerHTML = '<div class="hint">⏳ กำลังโหลดลีด…</div>';
          RP.api.reportLeads().then(function (d) {
            var rows = (d && d.leads) || [];
            leadsEl.innerHTML =
              '<div class="bb" style="font-size:17px;margin-bottom:6px">🔥 ลีดใหม่ (โทรตามปิดการขาย) · ' + rows.length + '</div>' +
              (rows.length ? rows.map(leadCard).join('')
                : ui.card({ body: RP.noData('ยังไม่มีลีด', 'สร้างลิงก์รายงานที่หน้า 🩺 เช็กสุขภาพเว็บ แล้วส่งให้ลูกค้า — พอเขากรอกข้อมูล จะเด้งเข้า LINE และโผล่ที่นี่') }));
          }).catch(function (e) {
            leadsEl.innerHTML = ui.card({ body: RP.noData('โหลดลีดไม่ได้', esc(e.message || String(e))) });
          });

          RP.api.siteReports().then(function (d) {
            var rows = (d && d.reports) || [];
            linksEl.innerHTML =
              '<div class="bb" style="font-size:17px;margin-bottom:6px">📤 ลิงก์รายงานที่สร้างไว้ · ' + rows.length + '</div>' +
              (rows.length ? rows.map(reportRow).join('')
                : '<div class="soft small">ยังไม่มีลิงก์รายงาน — สร้างได้ที่หน้า 🩺 เช็กสุขภาพเว็บ</div>');
            bindCopies(linksEl);
          }).catch(function (e) {
            linksEl.innerHTML = ui.card({ body: RP.noData('โหลดลิงก์ไม่ได้', esc(e.message || String(e))) });
          });
        }

        var rf = root.querySelector('#rp_refresh');
        if (rf) rf.onclick = load;
        load();
      }
    };
  };
})(window.RP);
