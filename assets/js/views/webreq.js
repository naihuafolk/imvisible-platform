/* ============================================================
   View: 🌐 คำขอทำเว็บ (Web Requests) — คิวรับงานทำเว็บจากลูกค้า
   ลูกค้าเปิดลิงก์ฟอร์ม (/build) → กรอก → submit → เข้าคิวนี้ → แอดมินกดอนุมัติ →
   ระบบสร้างโปรเจ็ค (ค้นเว็บจากลิงก์ให้เอง) + คืนลิงก์ให้ลูกค้าดูแบบ (preview)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function formLink() { return (window.location.origin || '') + '/build'; }
  function copyText(t) { try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); } catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); } }
  function fmtDate(iso) { if (!iso) return '—'; var d = new Date(iso); if (isNaN(d)) return esc(iso.slice(0, 10)); function p(n) { return n < 10 ? '0' + n : '' + n; } return p(d.getDate()) + '/' + p(d.getMonth() + 1) + '/' + (d.getFullYear() + 543); }
  function stBadge(s) { return s === 'approved' ? '<span class="badge green">อนุมัติแล้ว</span>' : s === 'rejected' ? '<span class="badge">ปฏิเสธ</span>' : '<span class="badge amber">ใหม่ · รออนุมัติ</span>'; }

  function linksHtml(raw) {
    var ls = (raw || '').split(/[\n,]/).map(function (x) { return x.trim(); }).filter(Boolean);
    if (!ls.length) return '<span class="soft">—</span>';
    return ls.map(function (l) { var u = /^https?:\/\//.test(l) ? l : 'https://' + l; return '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(l.replace(/^https?:\/\//, '').slice(0, 40)) + '</a>'; }).join(' · ');
  }

  function card(r) {
    var actions = r.status === 'new'
      ? '<button class="btn btn-sm btn-primary wr-ok" data-id="' + r.id + '">✅ อนุมัติ + สร้างเว็บ</button> ' +
        '<button class="btn btn-sm wr-no" data-id="' + r.id + '">ปฏิเสธ</button>'
      : (r.preview_url ? '<a class="btn btn-sm" href="' + esc(r.preview_url) + '" target="_blank" rel="noopener">👁️ ดูแบบเว็บ (ส่งลูกค้า)</a>' : '<span class="soft small">—</span>');
    return '<div class="card card-pad mb">' +
      '<div class="row between wrap" style="gap:8px"><div class="bb">' + esc(r.business_name || '—') + ' <span class="soft small">' + esc(r.biz_type || '') + '</span></div>' + stBadge(r.status) + '</div>' +
      '<div class="soft small" style="margin:4px 0">📞 ' + esc(r.contact || '—') + ' · 🌐 ' + (r.language === 'en' ? 'อังกฤษ' : 'ไทย') + ' · ' + fmtDate(r.created_at) + '</div>' +
      '<div class="small" style="margin:2px 0">🔗 ' + linksHtml(r.links) + '</div>' +
      (r.detail ? '<div class="soft small" style="margin:4px 0;padding:8px 10px;background:var(--bg,#f6f8fc);border-radius:8px">💬 ' + esc(r.detail) + '</div>' : '') +
      '<div style="margin-top:8px">' + actions + '</div></div>';
  }

  function render(root, d) {
    var slot = root.querySelector('#wr_slot'); if (!slot) return;
    var items = (d && d.items) || [];
    if (!items.length) { slot.innerHTML = ui.card({ body: RP.noData('ยังไม่มีคำขอทำเว็บ', 'ส่งลิงก์ฟอร์มด้านบนให้ลูกค้ากรอก — พอเขา submit จะเด้งเข้าคิวนี้ + แจ้ง LINE คุณ') }); return; }
    slot.innerHTML = items.map(card).join('');
    slot.querySelectorAll('.wr-ok').forEach(function (b) {
      b.onclick = function () {
        if (!confirm('อนุมัติ + สร้างโปรเจ็ค/เว็บให้ลูกค้ารายนี้?')) return;
        b.disabled = true; b.textContent = 'กำลังสร้าง…';
        RP.api.webRequestApprove(b.getAttribute('data-id')).then(function (r) {
          ui.toast('สร้างแล้ว ✓ — ดูแบบ: ' + (r.preview_url || '')); load(root);
        }).catch(function (e) { b.disabled = false; b.textContent = '✅ อนุมัติ + สร้างเว็บ'; ui.toast('ไม่สำเร็จ: ' + esc((e && e.message) || '')); });
      };
    });
    slot.querySelectorAll('.wr-no').forEach(function (b) {
      b.onclick = function () { RP.api.webRequestReject(b.getAttribute('data-id')).then(function () { ui.toast('ปฏิเสธแล้ว'); load(root); }).catch(function (e) { ui.toast('ไม่สำเร็จ: ' + esc((e && e.message) || '')); }); };
    });
  }

  function load(root) {
    var slot = root.querySelector('#wr_slot'); if (!slot) return;
    slot.innerHTML = '<div class="hint" style="padding:14px">กำลังโหลดคิว…</div>';
    if (!(RP.api && RP.api.reachable && RP.api.reachable())) { slot.innerHTML = ui.card({ body: RP.noData('ต้องเปิดโหมด Live', 'คิวคำขอดึงจริงจาก backend — เปิด Live ในหน้าตั้งค่า') }); return; }
    RP.api.webRequests().then(function (d) { render(root, d); }).catch(function (e) { slot.innerHTML = ui.card({ body: RP.noData('โหลดไม่ได้', esc((e && e.message) || 'เฉพาะแอดมิน (ตั้งอีเมลใน ADMIN_EMAILS)')) }); });
  }

  RP.views.webreq = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · รับงานทำเว็บ', title: '🌐 คำขอทำเว็บ',
      desc: 'ส่งลิงก์ฟอร์มให้ลูกค้ากรอก → เขา submit → เข้าคิวนี้ → กดอนุมัติ ระบบสร้างเว็บ (ค้นข้อมูลจากลิงก์ให้เอง) → ส่งลิงก์ดูแบบให้ลูกค้า' });
    var link = formLink();
    var linkCard = ui.card({ cls: 'mb', body:
      '<div class="bb" style="margin-bottom:4px">🔗 ลิงก์ฟอร์มสำหรับส่งลูกค้า</div>' +
      '<div class="soft small" style="margin-bottom:8px">ส่งลิงก์นี้ให้ลูกค้ากรอกข้อมูล (มีแค่เพจ Facebook ก็ได้ — ระบบดึงเอง)</div>' +
      '<div class="row wrap" style="gap:8px;align-items:center"><input class="input" readonly value="' + esc(link) + '" style="flex:1;min-width:220px">' +
      '<button class="btn btn-sm btn-primary" id="wr_copy">📋 คัดลอกลิงก์</button>' +
      '<a class="btn btn-sm" href="' + esc(link) + '" target="_blank" rel="noopener">👁️ เปิดฟอร์ม</a></div>' });
    return { html: head + linkCard + '<div id="wr_slot"></div>', mount: function (root) {
      var cp = root.querySelector('#wr_copy'); if (cp) cp.onclick = function () { copyText(link); };
      load(root);
    } };
  };
})(window.RP);
