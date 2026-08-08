/* ============================================================
   View: 🏗️ สร้างเว็บ (IM WEB) — AI website builder เสียบเข้า ImVisible
   กรอก brief → เรียก IM WEB API → ได้ 'HTML เว็บพร้อมใช้' หลายสไตล์ → พรีวิว
   วิชัน: สร้างเว็บที่พร้อม AEO/GEO → ต่อ SEO/AEO/GEO ให้ 'โตเอง'
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  // เปิดพรีวิว HTML เว็บที่สร้าง ในแท็บใหม่
  function previewHtml(html) {
    try {
      var w = window.open('', '_blank');
      if (!w) { ui.toast('เบราว์เซอร์บล็อก popup — อนุญาต popup แล้วลองใหม่'); return; }
      w.document.open(); w.document.write(html); w.document.close();
    } catch (e) { ui.toast('เปิดพรีวิวไม่ได้: ' + RP.esc(e.message || String(e))); }
  }

  function themeCard(t, idx) {
    var sw = (t.swatches || []).slice(0, 6).map(function (c) {
      return '<span style="display:inline-block;width:20px;height:20px;border-radius:5px;border:1px solid #0002;background:' + esc(c) + '"></span>';
    }).join(' ');
    return '<div class="card card-pad" style="margin-bottom:10px">' +
      '<div class="row" style="justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap">' +
        '<div class="bb" style="font-size:16px">🎨 ' + esc(t.styleName || t.id || ('สไตล์ ' + (idx + 1))) + '</div>' +
        '<div class="row" style="gap:5px">' + sw + '</div></div>' +
      (t.headline ? '<div class="soft" style="margin:6px 0">' + esc(t.headline) + '</div>' : '') +
      '<div class="row" style="margin-top:10px;gap:8px">' +
        '<button class="btn btn-sm btn-primary im-preview" data-idx="' + idx + '">👁️ ดูตัวอย่างเว็บ</button>' +
        '<button class="btn btn-sm im-use" data-idx="' + idx + '">✅ ใช้เว็บนี้ (บันทึก+เริ่มโต)</button>' +
      '</div></div>';
  }

  function render(out, d, brief) {
    var themes = d.themes || [];
    if (!themes.length) { out.innerHTML = ui.card({ body: RP.noData('ยังไม่ได้เว็บ', 'ลองใหม่อีกครั้ง หรือเช็ก IMWEB_API_KEY') }); return; }
    out.innerHTML =
      '<div class="soft small" style="margin-bottom:10px">✅ IM WEB สร้าง <b>' + themes.length + '</b> สไตล์ (engine: ' + esc(d.engine || 'ai') + ') — กดดูตัวอย่างได้เลย</div>' +
      themes.map(themeCard).join('') +
      '<div class="hint" style="margin-top:6px">💡 กด "ใช้เว็บนี้" เพื่อบันทึกเป็นโปรเจกต์ + เปิด SEO/AEO/GEO อัตโนมัติ (เว็บที่โตเอง)</div>';
    themes.forEach(function (t, idx) {
      var pv = out.querySelector('.im-preview[data-idx="' + idx + '"]');
      if (pv) pv.onclick = function () { previewHtml(t.html || ''); };
      var use = out.querySelector('.im-use[data-idx="' + idx + '"]');
      if (use) use.onclick = function () {
        use.disabled = true; use.textContent = 'กำลังบันทึก+เปิดโปรเจกต์…';
        RP.api.imwebSave({ html: t.html || '', brand_name: (brief && brief.brand_name) || '', language: (brief && brief.language) || 'th' }).then(function (r) {
          ui.toast('✅ เปิดโปรเจกต์แล้ว! เว็บกำลังโต');
          use.parentNode.innerHTML = '<div class="soft small" style="color:#0a7350;line-height:1.6">✅ <b>เปิดเว็บ + โปรเจกต์แล้ว</b> → <a href="' + esc(r.public_home || '#') + '" target="_blank" rel="noopener" style="color:#1a56ff;font-weight:700">' + esc(r.public_home || 'เปิดเว็บ') + '</a><br>ระบบเริ่มผลิตคอนเทนต์ + ดัน SEO/AEO/GEO ให้อัตโนมัติ (เว็บที่โตเอง)</div>';
        }).catch(function (e) {
          use.disabled = false; use.textContent = '✅ ใช้เว็บนี้ (บันทึก+เริ่มโต)';
          ui.toast('บันทึกไม่ได้: ' + esc(e.message || String(e)));
        });
      };
    });
  }

  RP.views.imweb = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · เครื่องมือสร้างเว็บ', title: '🏗️ สร้างเว็บ (IM WEB)',
      desc: 'กรอกข้อมูลธุรกิจ → AI สร้างเว็บให้ทั้งหน้า (~นาที) พร้อมโครง AEO/GEO → ต่อ SEO/AEO/GEO ให้ "โตเอง" ในระบบเรา' });
    var sel = function (id, label, opts) {
      return '<div style="flex:1;min-width:150px"><div class="soft small" style="margin-bottom:4px">' + label + '</div><select class="input" id="' + id + '" style="width:100%">' +
        opts.map(function (o) { return '<option value="' + o[0] + '">' + o[1] + '</option>'; }).join('') + '</select></div>';
    };
    var inp = function (id, label, ph, flex) {
      return '<div style="flex:' + (flex || 1) + ';min-width:180px"><div class="soft small" style="margin-bottom:4px">' + label + '</div><input class="input" id="' + id + '" placeholder="' + ph + '" style="width:100%"></div>';
    };
    var form = ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-end">' +
        inp('im_brand', 'ชื่อแบรนด์/ร้าน *', 'เช่น ร้านกาแฟบ้านหอม', 2) +
        inp('im_biz', 'ประเภทธุรกิจ', 'เช่น คาเฟ่ / คลินิกความงาม', 2) +
      '</div>' +
      '<div class="row wrap" style="gap:10px;align-items:flex-end;margin-top:10px">' +
        inp('im_about', 'เกี่ยวกับธุรกิจ', 'เช่น คาเฟ่ specialty คั่วเอง อบอุ่น', 3) +
        inp('im_products', 'สินค้า/บริการ', 'เช่น กาแฟดริป, ลาเต้, เค้ก', 2) +
      '</div>' +
      '<div class="row wrap" style="gap:10px;align-items:flex-end;margin-top:10px">' +
        inp('im_vibe', 'โทน/อารมณ์', 'เช่น อบอุ่น มินิมอล', 1) +
        inp('im_line', 'LINE (ไม่บังคับ)', '@yourshop', 1) +
        sel('im_motion', 'Animation', [['high', 'ปกติ'], ['max', 'เยอะ'], ['low', 'น้อย']]) +
        sel('im_lang', 'ภาษา', [['th', 'ไทย'], ['en', 'อังกฤษ']]) +
        sel('im_var', 'จำนวนสไตล์', [['1', '1'], ['2', '2'], ['3', '3']]) +
      '</div>' +
      '<div class="row" style="margin-top:12px"><button class="btn btn-primary" id="im_go">🏗️ สร้างเว็บ</button></div>' +
      '<div class="hint" style="margin-top:8px">ใช้ IM WEB (AI builder) สร้างเว็บทั้งหน้าจริง · ~1-3 นาที/รอบ · ต้องตั้ง IMWEB_API_KEY ในระบบก่อน</div>' });

    return { html: head + form + '<div id="im_out"></div>', mount: function (root) {
      var go = root.querySelector('#im_go'), out = root.querySelector('#im_out');
      function val(id) { var el = root.querySelector('#' + id); return el ? (el.value || '').trim() : ''; }
      function run() {
        if (!val('im_brand') && !val('im_about')) { ui.toast('ใส่ชื่อแบรนด์หรือรายละเอียดธุรกิจก่อน'); return; }
        if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live ในหน้าตั้งค่า'); return; }
        go.disabled = true; go.textContent = 'AI กำลังสร้างเว็บ… (1-3 นาที)';
        out.innerHTML = '<div class="hint">⏳ IM WEB กำลังสร้างเว็บทั้งหน้า… รอสักครู่ (อาจถึง 1-3 นาที)</div>';
        RP.api.imwebGenerate({
          brand_name: val('im_brand'), about: val('im_about'), products: val('im_products'),
          biz_type: val('im_biz'), vibe: val('im_vibe'), line: val('im_line'),
          motion_level: val('im_motion') || 'high', language: val('im_lang') || 'th',
          variants: parseInt(val('im_var') || '1', 10)
        }).then(function (d) {
          render(out, d, { brand_name: val('im_brand'), language: val('im_lang') || 'th' });
        }).catch(function (e) {
          out.innerHTML = ui.card({ body: RP.noData('สร้างเว็บไม่ได้', esc(e.message || String(e))) });
        }).then(function () { go.disabled = false; go.textContent = '🏗️ สร้างเว็บ'; });
      }
      if (go) go.onclick = run;
    } };
  };
})(window.RP);
