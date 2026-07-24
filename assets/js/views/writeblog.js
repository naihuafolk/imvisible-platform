/* ============================================================
   View: ✍️ เขียนบล็อกเอง (Admin Compose) — Phase 1 คอมมู/บล็อกแบรนด์
   แอดมินเขียนโพสต์ (บทความ/วิดีโอ) เอง → เผยแพร่ขึ้นบล็อกจริง (slug/url/schema/ลิงก์ภายในครบ)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function dbProjects() {
    return ((RP.data.project && RP.data.project.list) || []).filter(function (p) { return /^db/.test(String(p.id)); });
  }
  function dbId(idStr) { var m = /^db(\d+)$/.exec(String(idStr || '')); return m ? parseInt(m[1], 10) : null; }

  RP.views.writeblog = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · บล็อกแบรนด์', title: '✍️ เขียนบล็อกเอง',
      desc: 'เขียนโพสต์ของคุณเอง (บทความ/วิดีโอ) → เผยแพร่ขึ้นบล็อกจริง · ได้ Schema + ลิงก์ภายใน + SEO/AEO เต็ม' });

    var projs = dbProjects();
    if (!(RP.isReal && RP.isReal())) {
      return { html: head + ui.card({ body: RP.noData('โหมดตัวอย่าง', 'เข้าสู่ระบบบัญชีจริงเพื่อเขียนบล็อก') }) };
    }
    if (!projs.length) {
      return { html: head + ui.card({ body: RP.noData('ยังไม่มีโปรเจ็ค', 'สร้างโปรเจ็ค (แบรนด์คุณ) ก่อน แล้วค่อยเขียนบล็อก', '<button class="btn btn-primary" id="wbNew">＋ สร้างโปรเจ็ค</button>') }),
        mount: function (root) { var b = root.querySelector('#wbNew'); if (b) b.onclick = function () { RP.go('projects'); }; } };
    }

    var opts = projs.map(function (p) {
      return '<option value="' + esc(p.id) + '"' + (p.id === RP.data.project.current ? ' selected' : '') + '>' + esc(p.name || p.id) + '</option>';
    }).join('');

    var form = ui.card({ title: 'เขียนโพสต์ใหม่', flush: true, cls: 'mb', body:
      '<div class="card-pad" style="display:flex;flex-direction:column;gap:12px">' +
      '<div><label class="soft small">โพสต์ลงบล็อกของ</label>' +
      '<select class="input" id="wbProj" style="width:100%">' + opts + '</select></div>' +
      '<div><label class="soft small">หัวข้อ</label>' +
      '<input class="input" id="wbTitle" placeholder="เช่น 5 เทคนิค AEO ที่คนไทยยังไม่รู้" style="width:100%"></div>' +
      '<div><label class="soft small">เนื้อหา (พิมพ์ธรรมดาได้ — ขึ้นบรรทัดใหม่ = ย่อหน้าใหม่ · หรือวาง HTML)</label>' +
      '<textarea class="input" id="wbBody" rows="12" placeholder="เขียนความรู้/มุมมองของคุณที่นี่…" style="width:100%;resize:vertical"></textarea></div>' +
      '<div class="grid" style="grid-template-columns:1fr 1fr;gap:12px">' +
        '<div><label class="soft small">รูปปก URL (ไม่บังคับ)</label><input class="input" id="wbCover" placeholder="https://…jpg" style="width:100%"></div>' +
        '<div><label class="soft small">วิดีโอ YouTube (ไม่บังคับ)</label><input class="input" id="wbVideo" placeholder="https://youtu.be/…" style="width:100%"></div>' +
      '</div>' +
      '<div class="row between" style="align-items:center;margin-top:2px">' +
        '<label class="row" style="gap:8px;align-items:center;cursor:pointer"><input type="checkbox" id="wbPub" checked> <span class="small">เผยแพร่ทันที (ไม่ติ๊ก = เก็บเป็นร่าง)</span></label>' +
        '<button class="btn btn-primary" id="wbSave">🚀 เผยแพร่โพสต์</button>' +
      '</div>' +
      '<div id="wbMsg" class="small" style="min-height:18px"></div>' +
      '</div>' });

    var html = head + form + '<div id="wbList"></div>';

    return { html: html, mount: function (root) {
      var sel = root.querySelector('#wbProj');
      function loadPosts() {
        var pid = dbId(sel.value); var box = root.querySelector('#wbList');
        if (!(pid && RP.api.enabled())) { box.innerHTML = ''; return; }
        box.innerHTML = ui.card({ body: '<div class="hint">กำลังโหลดโพสต์…</div>' });
        RP.api.projectArticles(pid).then(function (d) {
          var arts = (d.articles || d || []).slice(0, 12);
          if (!arts.length) { box.innerHTML = ui.card({ title: 'โพสต์ล่าสุด', body: RP.noData('ยังไม่มีโพสต์', 'เขียนโพสต์แรกด้านบนได้เลย') }); return; }
          var rows = arts.map(function (a) {
            var st = a.status === 'published'
              ? (a.url ? '<a href="' + esc(a.url) + '" target="_blank" rel="noopener" class="soft small">ดูหน้าเว็บ ↗</a>' : '<span class="soft small">เผยแพร่แล้ว</span>')
              : '<span class="soft small" style="color:var(--amber-600)">ร่าง</span>';
            return '<div class="list-row"><div class="grow"><div class="t">' + esc(a.title || '(ไม่มีหัวข้อ)') + '</div>' +
              '<div class="soft small">' + esc(a.fmt || '') + (a.aeo_score ? ' · AEO ' + a.aeo_score : '') + '</div></div>' + st + '</div>';
          }).join('');
          box.innerHTML = ui.card({ title: 'โพสต์ล่าสุด', sub: arts.length + ' โพสต์', flush: true, body: rows });
        }).catch(function () { box.innerHTML = ''; });
      }
      if (sel) sel.onchange = loadPosts;
      loadPosts();

      var go = root.querySelector('#wbSave'), msg = root.querySelector('#wbMsg');
      if (go) go.onclick = function () {
        var pid = dbId(sel.value);
        var title = (root.querySelector('#wbTitle').value || '').trim();
        if (!title) { ui.toast('ใส่หัวข้อก่อน'); return; }
        if (!(pid && RP.api.enabled())) { ui.toast('เปิดโหมด Live + เชื่อม backend ก่อน'); return; }
        var body = {
          title: title,
          content: root.querySelector('#wbBody').value || '',
          cover_url: (root.querySelector('#wbCover').value || '').trim(),
          video_url: (root.querySelector('#wbVideo').value || '').trim(),
          status: root.querySelector('#wbPub').checked ? 'published' : 'draft'
        };
        go.disabled = true; go.textContent = 'กำลังเผยแพร่…'; if (msg) msg.textContent = '';
        RP.api.createPost(pid, body).then(function (d) {
          go.disabled = false; go.textContent = '🚀 เผยแพร่โพสต์';
          root.querySelector('#wbTitle').value = ''; root.querySelector('#wbBody').value = '';
          root.querySelector('#wbCover').value = ''; root.querySelector('#wbVideo').value = '';
          if (msg) msg.innerHTML = d.status === 'published'
            ? 'เผยแพร่แล้ว ✓ ' + (d.url ? '<a href="' + esc(d.url) + '" target="_blank" rel="noopener">เปิดหน้าเว็บ ↗</a>' : '')
            : '<span style="color:var(--amber-600)">บันทึกเป็นร่างแล้ว ✓</span>';
          ui.toast(d.status === 'published' ? 'เผยแพร่โพสต์ขึ้นบล็อกแล้ว ✓' : 'บันทึกร่างแล้ว ✓');
          loadPosts();
        }).catch(function (e) { go.disabled = false; go.textContent = '🚀 เผยแพร่โพสต์'; ui.toast('เผยแพร่ไม่ได้: ' + esc(e.message || String(e))); });
      };
    } };
  };
})(window.RP);
