/* ============================================================
   View: 🏗️ สร้างเว็บ (IM WEB) — AI website builder เสียบเข้า ImVisible
   Brief Builder ละเอียด → เว็บที่ดีขึ้น + เก็บวัตถุดิบ AEO/GEO (FAQ/ที่ตั้ง/ติดต่อ)
   ตอน 'ใช้เว็บนี้' → carry brief เข้าโปรเจกต์ + ฝัง schema (LocalBusiness/Org/FAQPage) → 'โตเอง' เต็มแม็ก
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function previewHtml(html) {
    try {
      var w = window.open('', '_blank');
      if (!w) { ui.toast('เบราว์เซอร์บล็อก popup — อนุญาต popup แล้วลองใหม่'); return; }
      w.document.open(); w.document.write(html); w.document.close();
    } catch (e) { ui.toast('เปิดพรีวิวไม่ได้: ' + esc(e.message || String(e))); }
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

  function render(out, d, ctx) {
    var themes = d.themes || [];
    if (!themes.length) { out.innerHTML = ui.card({ body: RP.noData('ยังไม่ได้เว็บ', 'ลองใหม่อีกครั้ง หรือเช็ก IMWEB_API_KEY') }); return; }
    out.innerHTML =
      '<div class="soft small" style="margin-bottom:10px">✅ IM WEB สร้าง <b>' + themes.length + '</b> สไตล์ (engine: ' + esc(d.engine || 'ai') + ') — กดดูตัวอย่างได้เลย</div>' +
      themes.map(themeCard).join('') +
      '<div class="hint" style="margin-top:6px">💡 กด "ใช้เว็บนี้" → บันทึกเป็นโปรเจกต์ + ฝัง schema AEO/GEO (LocalBusiness/FAQ) ให้อัตโนมัติ + เปิดวงจรโตเอง</div>';
    themes.forEach(function (t, idx) {
      var pv = out.querySelector('.im-preview[data-idx="' + idx + '"]');
      if (pv) pv.onclick = function () { previewHtml(t.html || ''); };
      var use = out.querySelector('.im-use[data-idx="' + idx + '"]');
      if (use) use.onclick = function () {
        use.disabled = true; use.textContent = 'กำลังบันทึก+ฝัง schema…';
        RP.api.imwebSave({ html: t.html || '', brief: (ctx && ctx.brief) || {}, language: (ctx && ctx.language) || 'th' }).then(function (r) {
          ui.toast('✅ เปิดโปรเจกต์แล้ว! เว็บกำลังโต');
          var extra = (r.faqs ? (' · ฝัง FAQ ' + r.faqs + ' ข้อ') : '') + (r.aeo_injected ? ' · ฝัง schema AEO/GEO ✓' : '');
          use.parentNode.innerHTML = '<div class="soft small" style="color:#0a7350;line-height:1.6">✅ <b>เปิดเว็บ + โปรเจกต์แล้ว</b> → <a href="' + esc(r.public_home || '#') + '" target="_blank" rel="noopener" style="color:#1a56ff;font-weight:700">' + esc(r.public_home || 'เปิดเว็บ') + '</a><br>ระบบเริ่มผลิตคอนเทนต์ + ดัน SEO/AEO/GEO ให้อัตโนมัติ' + esc(extra) + '</div>';
        }).catch(function (e) {
          use.disabled = false; use.textContent = '✅ ใช้เว็บนี้ (บันทึก+เริ่มโต)';
          ui.toast('บันทึกไม่ได้: ' + esc(e.message || String(e)));
        });
      };
    });
  }

  RP.views.imwebone = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · เครื่องมือสร้างเว็บ', title: '🏗️ สร้างเว็บ (IM WEB)',
      desc: 'กรอก brief ให้ละเอียด → AI สร้างเว็บทั้งหน้า (~นาที) พร้อมโครง AEO/GEO → กด "ใช้เว็บนี้" เพื่อฝัง schema + ต่อ SEO/AEO/GEO ให้ "โตเอง" ในระบบเรา' });

    function inp(id, label, ph, flex) {
      return '<div style="flex:' + (flex || 1) + ';min-width:170px"><div class="soft small" style="margin-bottom:4px">' + label + '</div><input class="input" id="' + id + '" placeholder="' + ph + '" style="width:100%"></div>';
    }
    function ta(id, label, ph, flex) {
      return '<div style="flex:' + (flex || 1) + ';min-width:200px"><div class="soft small" style="margin-bottom:4px">' + label + '</div><textarea class="input" id="' + id + '" placeholder="' + ph + '" style="width:100%;min-height:60px;resize:vertical"></textarea></div>';
    }
    function sel(id, label, opts) {
      return '<div style="flex:1;min-width:130px"><div class="soft small" style="margin-bottom:4px">' + label + '</div><select class="input" id="' + id + '" style="width:100%">' +
        opts.map(function (o) { return '<option value="' + o[0] + '">' + o[1] + '</option>'; }).join('') + '</select></div>';
    }
    function grp(title, sub, inner) {
      return ui.card({ cls: 'mb', body:
        '<div class="bb" style="font-size:15px">' + title + '</div>' +
        (sub ? '<div class="soft small" style="margin:2px 0 10px">' + sub + '</div>' : '<div style="height:8px"></div>') +
        inner });
    }
    function rowwrap(inner) { return '<div class="row wrap" style="gap:10px;align-items:flex-end">' + inner + '</div>'; }

    var gBiz = grp('🏢 ธุรกิจ', 'ยิ่งละเอียด เว็บยิ่งตรง',
      rowwrap(inp('im_brand', 'ชื่อแบรนด์/ร้าน *', 'เช่น ร้านกาแฟบ้านหอม', 2) + inp('im_biz', 'ประเภทธุรกิจ', 'เช่น คาเฟ่ / คลินิกความงาม', 2)) +
      '<div style="height:10px"></div>' +
      rowwrap(ta('im_about', 'เกี่ยวกับธุรกิจ', 'เช่น คาเฟ่ specialty คั่วเอง บรรยากาศอบอุ่น', 3) + ta('im_usp', 'จุดเด่น / ทำไมต้องเลือกเรา', 'เช่น เมล็ดคั่วสดทุกวัน, ที่จอดรถกว้าง', 2)) +
      '<div style="height:10px"></div>' +
      rowwrap(inp('im_audience', 'กลุ่มลูกค้า', 'เช่น คนทำงาน สายคาเฟ่ฮอปปิ้ง', 2) + inp('im_products', 'สินค้า/บริการ (คั่น ,)', 'เช่น กาแฟดริป, ลาเต้, เค้ก', 2) + inp('im_price', 'ราคา/แพ็กเกจ', 'เช่น เริ่ม 65 บาท', 1)));

    var gContact = grp('📍 ติดต่อ &amp; ที่ตั้ง', '🟪 วัตถุดิบ GEO — ที่อยู่ + ติดต่อ = ทำ LocalBusiness schema (AI แนะนำ "ร้านแถวนี้")',
      rowwrap(inp('im_phone', 'เบอร์โทร', '02-xxx-xxxx', 1) + inp('im_line', 'LINE', '@yourshop', 1) + inp('im_email', 'อีเมล', 'hello@shop.com', 1)) +
      '<div style="height:10px"></div>' +
      rowwrap(inp('im_fb', 'Facebook (URL)', 'https://facebook.com/yourshop', 1) + inp('im_ig', 'Instagram (URL/handle)', '@yourshop', 1)) +
      '<div style="height:10px"></div>' +
      rowwrap(inp('im_addr', 'ที่อยู่', 'เช่น 123 ถ.สุขุมวิท กทม.', 2) + inp('im_area', 'พื้นที่ให้บริการ', 'เช่น กรุงเทพและปริมณฑล', 1)) +
      '<div style="height:10px"></div>' +
      rowwrap(inp('im_hours', 'เวลาทำการ', 'เช่น จ-ศ 8:00-18:00', 1) + inp('im_map', 'ลิงก์ Google Maps', 'https://maps.app.goo.gl/...', 2)));

    var gBrand = grp('🎯 เป้าหมาย &amp; แบรนด์', 'เป้าหมายเว็บกำหนดปุ่ม CTA + โทนดีไซน์',
      rowwrap(
        sel('im_goal', 'เป้าหมายเว็บ', [['chat', 'ทัก/สอบถาม'], ['booking', 'จอง/นัดหมาย'], ['order', 'สั่งซื้อ'], ['call', 'โทรหา'], ['leads', 'เก็บลีด']]) +
        inp('im_vibe', 'โทน/อารมณ์', 'อบอุ่น มินิมอล', 1) +
        inp('im_color', 'สีหลัก', 'เช่น #1a56ff หรือ น้ำตาลอุ่น', 1) +
        inp('im_logo', 'ลิงก์โลโก้ (ถ้ามี)', 'https://.../logo.png', 1)) +
      '<div style="height:10px"></div>' +
      rowwrap(
        sel('im_motion', 'Animation', [['high', 'ปกติ'], ['max', 'เยอะ'], ['low', 'น้อย']]) +
        sel('im_lang', 'ภาษา', [['th', 'ไทย'], ['en', 'อังกฤษ']]) +
        sel('im_var', 'จำนวนสไตล์', [['1', '1'], ['2', '2'], ['3', '3']])));

    var gAeo = grp('🟪 AEO / GEO (จุดขายเรา)', 'FAQ จริง → FAQPage schema (AI หยิบไปตอบ) · คีย์เวิร์ด → answer-first',
      rowwrap(inp('im_kw', 'คีย์เวิร์ดที่อยากติด (คั่น ,)', 'เช่น กาแฟดริป เอกมัย, คาเฟ่นั่งทำงาน', 3)) +
      '<div class="soft small" style="margin:12px 0 6px">❓ คำถามที่ลูกค้าถามบ่อย (FAQ) — ใส่ของจริง จะกลายเป็น schema ให้ AI หยิบไปแนะนำ</div>' +
      '<div id="im_faqs"></div>' +
      '<button class="btn btn-sm" id="im_addfaq" style="margin-top:6px">➕ เพิ่มคำถาม</button>');

    var form = gBiz + gContact + gBrand + gAeo +
      ui.card({ cls: 'mb', body:
        '<div class="row" style="gap:10px;align-items:center;flex-wrap:wrap"><button class="btn btn-primary" id="im_go">🏗️ สร้างเว็บ</button>' +
        '<span class="soft small">ใช้ IM WEB (AI builder) · ~1-3 นาที/รอบ · ต้องตั้ง IMWEB_API_KEY ในระบบก่อน</span></div>' });

    return { html: head + form + '<div id="im_out"></div>', mount: function (root) {
      var go = root.querySelector('#im_go'), out = root.querySelector('#im_out'), faqBox = root.querySelector('#im_faqs');

      function faqRow(q, a) {
        var row = document.createElement('div');
        row.className = 'im-faq row wrap';
        row.style.cssText = 'gap:8px;align-items:center;margin-bottom:6px';
        row.innerHTML =
          '<input class="input im-fq" placeholder="คำถาม เช่น มีที่จอดรถไหม?" style="flex:2;min-width:170px" value="' + esc(q || '') + '">' +
          '<input class="input im-fa" placeholder="คำตอบสั้น ๆ" style="flex:3;min-width:170px" value="' + esc(a || '') + '">' +
          '<button class="btn btn-sm im-frm" type="button" title="ลบ">✕</button>';
        row.querySelector('.im-frm').onclick = function () { row.remove(); };
        faqBox.appendChild(row);
      }
      faqRow('', ''); faqRow('', '');
      var addf = root.querySelector('#im_addfaq');
      if (addf) addf.onclick = function () { faqRow('', ''); };

      function v(id) { var el = root.querySelector('#' + id); return el ? (el.value || '').trim() : ''; }
      function collectBrief() {
        var faqs = [];
        root.querySelectorAll('#im_faqs .im-faq').forEach(function (r) {
          var q = (r.querySelector('.im-fq').value || '').trim();
          var a = (r.querySelector('.im-fa').value || '').trim();
          if (q) faqs.push({ q: q, a: a });
        });
        return {
          brand_name: v('im_brand'), biz_type: v('im_biz'), about: v('im_about'), usp: v('im_usp'),
          audience: v('im_audience'), products: v('im_products'), price_info: v('im_price'),
          phone: v('im_phone'), line: v('im_line'), email: v('im_email'), facebook: v('im_fb'),
          instagram: v('im_ig'), address: v('im_addr'), service_area: v('im_area'), hours: v('im_hours'),
          map_url: v('im_map'), goal: v('im_goal'), brand_color: v('im_color'), logo_url: v('im_logo'),
          vibe: v('im_vibe'),
          keywords: (v('im_kw') || '').split(',').map(function (s) { return s.trim(); }).filter(Boolean).slice(0, 12),
          faqs: faqs
        };
      }

      function run() {
        var brief = collectBrief();
        if (!brief.brand_name && !brief.about) { ui.toast('ใส่ชื่อแบรนด์หรือรายละเอียดธุรกิจก่อน'); return; }
        if (!(RP.api && RP.api.reachable())) { ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live ในหน้าตั้งค่า'); return; }
        var lang = v('im_lang') || 'th';
        go.disabled = true; go.textContent = 'AI กำลังสร้างเว็บ… (1-3 นาที)';
        out.innerHTML = '<div class="hint">⏳ IM WEB กำลังสร้างเว็บทั้งหน้า… รอสักครู่ (อาจถึง 1-3 นาที)</div>';
        RP.api.imwebGenerate({
          brief: brief, language: lang,
          motion_level: v('im_motion') || 'high', variants: parseInt(v('im_var') || '1', 10)
        }).then(function (d) {
          render(out, d, { brief: brief, language: lang });
        }).catch(function (e) {
          out.innerHTML = ui.card({ body: RP.noData('สร้างเว็บไม่ได้', esc(e.message || String(e))) });
        }).then(function () { go.disabled = false; go.textContent = '🏗️ สร้างเว็บ'; });
      }
      if (go) go.onclick = run;
    } };
  };
})(window.RP);
