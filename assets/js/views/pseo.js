/* ============================================================
   View: 📄 pSEO ชุด (ติดอันดับ) — ปั่นหลายหน้า unique 'บนโดเมนหลัก' ทีเดียว
   กรอก pattern + variants (อุตสาหกรรม/เมือง) → เพิ่มหัวข้อเข้าโปรเจกต์ → เครื่องยนต์ผลิตหน้า on-domain เอง
   white-hat: หน้าอยู่โดเมนเดียว(สะสม authority) + AI เขียนต่างกันจริงต่อ variant (ไม่ใช่ doorway/PBN)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  var PRESETS = {
    industry: ['คลินิกความงาม', 'คลินิกทันตกรรม', 'ร้านอาหาร', 'คาเฟ่', 'โรงแรม', 'รีสอร์ท',
               'อสังหาริมทรัพย์', 'ร้านเสริมสวย', 'ฟิตเนส', 'สปา', 'โรงเรียนกวดวิชา', 'ร้านค้าออนไลน์',
               'สำนักงานบัญชี', 'คลินิกสัตวแพทย์', 'ร้านทำผม', 'อู่ซ่อมรถ'],
    city: ['กรุงเทพ', 'เชียงใหม่', 'ภูเก็ต', 'ชลบุรี', 'พัทยา', 'ขอนแก่น', 'นครราชสีมา', 'หาดใหญ่',
           'อุดรธานี', 'สุราษฎร์ธานี', 'เชียงราย', 'อยุธยา']
  };

  function parseVariants(txt) {
    return (txt || '').split(/[\n,]+/).map(function (s) { return s.trim(); })
      .filter(Boolean).filter(function (v, i, a) { return a.indexOf(v) === i; }).slice(0, 30);
  }
  function mkTopic(pattern, v) {
    var p = (pattern || 'รับทำเว็บ{x}').trim();
    return (p.indexOf('{x}') >= 0 ? p.replace(/\{x\}/g, v) : (p + ' ' + v)).trim();
  }

  RP.views.pseo = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · สร้าง', title: '📄 pSEO ชุด (ติดอันดับ)',
      desc: 'ปั่นหลายหน้า unique "บนโดเมนหลัก" ทีเดียว → เครื่องยนต์เขียน+เผยแพร่หน้า on-domain ให้เอง (เนื้อหาต่างกันจริงต่อ variant · white-hat)' });

    var info = '<div class="card card-pad mb" style="border-left:3px solid #1a56ff">' +
      '<div class="soft small" style="line-height:1.7">🟢 <b>ทำไมได้ผล:</b> หน้าอยู่บนโดเมนเดียว (imvisible.tech) → สะสม authority รวมกัน ติดอันดับ long-tail · AI เขียนเนื้อหาต่างกันจริงต่ออุตสาหกรรม/เมือง<br>' +
      '🔴 <b>ต่างจาก PBN:</b> ไม่ใช่เว็บแยกลิงก์หากันเอง — เป็นหน้า unique มีประโยชน์จริง บนเว็บเดียว (Google ชอบ)</div></div>';

    var projs = ((RP.data.project && RP.data.project.list) || []);
    var projOpts = '<option value="0">เว็บหลัก (แนะนำ — โดเมนแข็งสุด)</option>' +
      projs.map(function (p) {
        var m = /^db(\d+)$/.exec(String(p.id || ''));
        return m ? '<option value="' + m[1] + '">' + esc(p.name) + '</option>' : '';
      }).join('');

    function chipRow(kind, label) {
      return '<div style="margin-top:6px"><span class="soft small" style="margin-right:6px">' + label + ':</span>' +
        PRESETS[kind].map(function (v) {
          return '<button type="button" class="ps-chip" data-v="' + esc(v) + '" style="display:inline-block;margin:3px;padding:4px 11px;border:1px solid var(--line,#e5e7eb);border-radius:999px;background:transparent;font:inherit;font-size:12.5px;cursor:pointer">+ ' + esc(v) + '</button>';
        }).join('') + '</div>';
    }

    var form = ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-end">' +
        '<div style="flex:2;min-width:200px"><div class="soft small" style="margin-bottom:4px">รูปแบบหัวข้อ (ใช้ <b>{x}</b> เป็นตัวแปร)</div><input class="input" id="ps_pattern" value="รับทำเว็บ{x}" style="width:100%"></div>' +
        '<div style="flex:1.5;min-width:170px"><div class="soft small" style="margin-bottom:4px">สร้างหน้าให้โปรเจกต์</div><select class="input" id="ps_proj" style="width:100%">' + projOpts + '</select></div>' +
      '</div>' +
      '<div style="margin-top:12px"><div class="soft small" style="margin-bottom:4px">ตัวแปร (อุตสาหกรรม/เมือง — บรรทัดละ 1 หรือคั่นด้วย ,)</div>' +
        '<textarea class="input" id="ps_vars" placeholder="คลินิกความงาม&#10;ร้านอาหาร&#10;โรงแรม" style="width:100%;min-height:90px;resize:vertical"></textarea>' +
        chipRow('industry', '🏢 อุตสาหกรรม') + chipRow('city', '📍 เมือง') +
      '</div>' +
      '<div class="row" style="margin-top:12px;gap:12px;align-items:center;flex-wrap:wrap">' +
        '<button class="btn btn-primary" id="ps_go">📄 สร้างหัวข้อ pSEO</button>' +
        '<label class="soft small" style="display:inline-flex;align-items:center;gap:6px;cursor:pointer"><input type="checkbox" id="ps_now"> เริ่มผลิตชุดแรกทันที</label>' +
        '<span class="soft small" id="ps_preview"></span>' +
      '</div>' });

    return { html: head + info + form + '<div id="ps_out"></div>', mount: function (root) {
      var go = root.querySelector('#ps_go'), out = root.querySelector('#ps_out'),
          vars = root.querySelector('#ps_vars'), pat = root.querySelector('#ps_pattern'),
          prev = root.querySelector('#ps_preview');

      function addVar(v) {
        var cur = parseVariants(vars.value);
        if (cur.indexOf(v) < 0) { vars.value = (vars.value.trim() ? vars.value.trim() + '\n' : '') + v; }
        updatePreview();
      }
      function updatePreview() {
        var vs = parseVariants(vars.value);
        prev.innerHTML = vs.length
          ? 'จะสร้าง <b>' + vs.length + '</b> หน้า · ตัวอย่าง: ' + esc(mkTopic(pat.value, vs[0]))
          : '';
      }
      root.querySelectorAll('.ps-chip').forEach(function (b) {
        b.onclick = function () { addVar(b.getAttribute('data-v')); };
      });
      vars.addEventListener('input', updatePreview);
      pat.addEventListener('input', updatePreview);

      function run() {
        var variants = parseVariants(vars.value);
        if (!variants.length) { ui.toast('ใส่ตัวแปรอย่างน้อย 1 อย่าง (กดชิป หรือพิมพ์เอง)'); return; }
        if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live'); return; }
        go.disabled = true; go.textContent = 'กำลังสร้างหัวข้อ…';
        out.innerHTML = '<div class="hint">⏳ กำลังเพิ่มหัวข้อเข้าโปรเจกต์…</div>';
        RP.api.pseoTopics({
          project_id: parseInt(root.querySelector('#ps_proj').value || '0', 10),
          pattern: (pat.value || 'รับทำเว็บ{x}').trim(),
          variants: variants,
          produce_now: !!root.querySelector('#ps_now').checked
        }).then(function (r) {
          out.innerHTML = ui.card({ body:
            '<div class="bb" style="font-size:16px;margin-bottom:6px">✅ เพิ่ม ' + (r.added || 0) + ' หน้า เข้า "' + esc(r.project || '') + '" แล้ว</div>' +
            ((r.topics && r.topics.length) ? '<ul style="margin:6px 0 0;padding-left:20px;line-height:1.8">' +
              r.topics.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>' : '') +
            '<div class="soft small" style="margin-top:8px;line-height:1.6">' + esc(r.note || '') +
            (r.producing ? '<br>🚀 เริ่มผลิตชุดแรกให้แล้ว — ที่เหลือทยอยผลิตตามรอบอัตโนมัติ' :
              '<br>⏳ จะทยอยผลิตตามรอบอัตโนมัติ (หรือกด "โต" ที่โปรเจกต์เพื่อเริ่มเลย)') + '</div>' +
            '<div class="hint" style="margin-top:8px">💡 หน้าเหล่านี้อยู่บนโดเมนหลัก = สะสมพลังอันดับรวมกัน · เพิ่มได้เรื่อย ๆ (อุตสาหกรรม × เมือง)</div>' });
        }).catch(function (e) {
          out.innerHTML = ui.card({ body: RP.noData('สร้างไม่ได้', esc(e.message || String(e))) });
        }).then(function () { go.disabled = false; go.textContent = '📄 สร้างหัวข้อ pSEO'; });
      }
      if (go) go.onclick = run;
    } };
  };
})(window.RP);
