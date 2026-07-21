/* ============================================================
   View: Billing — แพ็กเกจ & ชำระเงิน (Stripe subscription จริง)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function money(n) { try { return Number(n || 0).toLocaleString('th-TH'); } catch (e) { return String(n || 0); } }

  RP.views.billing = function () {
    var html = ui.pageHead({
      eyebrow: 'บัญชี · แพ็กเกจ', title: 'แพ็กเกจ & การเรียกเก็บเงิน',
      desc: 'อัปเกรดเพื่อเพิ่มจำนวนโปรเจ็คและบทความต่อเดือน · ชำระเงินปลอดภัยผ่าน Stripe'
    }) + '<div id="billing_slot"><div class="hint">กำลังโหลดแพ็กเกจ…</div></div>';

    return {
      html: html,
      mount: function (root) {
        var slot = root.querySelector('#billing_slot');

        function planCard(p, cur) {
          var isCur = cur === p.key;
          var btn = p.key === 'free'
            ? (isCur ? '<button class="btn btn-sm" disabled>แพ็กเกจปัจจุบัน</button>' : '<span class="soft small">แพ็กเกจเริ่มต้น</span>')
            : (isCur ? '<button class="btn btn-sm" disabled>✓ แพ็กเกจปัจจุบัน</button>'
                     : '<button class="btn btn-sm btn-primary bill-up" data-plan="' + p.key + '">อัปเกรดเป็น ' + esc(p.label) + '</button>');
          return '<div class="panel" style="' + (isCur ? 'border-color:var(--brand-500);background:var(--surface-2)' : '') + '"><div class="panel-body">' +
            '<div class="row between"><span class="bb" style="font-size:18px">' + esc(p.label) + '</span>' + (isCur ? ui.badge('ปัจจุบัน', 'green') : '') + '</div>' +
            '<div class="bb" style="color:var(--purple-700);font-size:22px;margin:6px 0">฿' + money(p.price_thb) + '<span class="soft" style="font-size:12px">/เดือน</span></div>' +
            '<ul style="margin:8px 0 12px;padding-left:18px">' + (p.features || []).map(function (f) { return '<li class="small">' + esc(f) + '</li>'; }).join('') + '</ul>' +
            btn + '</div></div>';
        }

        if (!RP.api.enabled()) {
          slot.innerHTML = RP.noData ? RP.noData('เปิดโหมด Live ก่อน', 'ต้องต่อ backend (โหมด Live ในหน้าตั้งค่า) เพื่อดูแพ็กเกจและชำระเงินจริง') : 'เปิดโหมด Live ก่อน';
          return;
        }
        RP.api.plans().then(function (pl) {
          var plans = (pl && pl.plans) || [];
          RP.api.billingStatus().then(function (st) {
            var cur = (st && st.plan) || 'free';
            var note = (st && !st.stripe_enabled)
              ? '<div class="warn-box mb">⚠️ ระบบชำระเงินยังไม่ถูกตั้งค่าโดยผู้ดูแล (Stripe) — ปุ่มอัปเกรดจะยังใช้ไม่ได้จนกว่าจะตั้งคีย์</div>' : '';
            slot.innerHTML = note + '<div class="grid grid-3">' + plans.map(function (p) { return planCard(p, cur); }).join('') + '</div>' +
              '<div class="hint" style="margin-top:14px">🔒 ชำระเงินผ่าน Stripe (บัตร) · ยกเลิกได้ทุกเมื่อ · ใบเสร็จส่งอัตโนมัติ</div>';
            Array.prototype.forEach.call(slot.querySelectorAll('.bill-up'), function (b) {
              b.onclick = function () {
                b.disabled = true; b.textContent = 'กำลังไปหน้าชำระเงิน…';
                RP.api.billingCheckout(b.getAttribute('data-plan')).then(function (r) {
                  if (r && r.url) { window.location.href = r.url; }
                  else { b.disabled = false; b.textContent = 'อัปเกรด'; RP.ui.toast('สร้างลิงก์ชำระเงินไม่ได้'); }
                }).catch(function (e) {
                  b.disabled = false; b.textContent = 'อัปเกรด';
                  RP.ui.toast('ชำระเงินไม่ได้: ' + esc((e && e.message) || String(e)));
                });
              };
            });
          }).catch(function () { slot.innerHTML = 'ดึงสถานะแพ็กเกจไม่ได้'; });
        }).catch(function () { slot.innerHTML = 'ดึงรายการแพ็กเกจไม่ได้'; });
      }
    };
  };
})(window.RP);
