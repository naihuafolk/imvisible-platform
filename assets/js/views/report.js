(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  function tbl(head, rows) {
    return '<div class="tbl-wrap"><table class="tbl"><thead><tr>' +
      head + '</tr></thead><tbody>' + rows + '</tbody></table></div>';
  }

  RP.views.report = function () { return RP.isReal() ? realReport() : sampleReport(); };

  /* ============ รายงานผลงานจริง (ต่อโปรเจ็ค) — บัญชีจริงเท่านั้น ============ */
  function currentProject() {
    var list = ((RP.data.project && RP.data.project.list) || []).filter(function (p) { return /^db/.test(String(p.id)); });
    var cur = RP.data.project.current;
    return list.filter(function (x) { return x.id === cur; })[0] || list[0] || null;
  }
  function rDbId(p) { var m = /^db(\d+)$/.exec(String(p && p.id || '')); return m ? parseInt(m[1], 10) : null; }
  function gradeTone(g) { return g === 'A' ? 'green' : g === 'B' ? 'blue' : g === 'C' ? 'amber' : 'red'; }
  function rankLabel(r) { return r == null ? '<span class="soft">ไม่ติด (>100)</span>' : '#' + r; }
  function diffChip(k) {   /* ป้ายความยากในการติดอันดับ (Easy-Win Radar · ประเมินจาก SERP) */
    var lb = k && k.difficulty_label;
    if (!lb) return '';
    var c = lb === 'ง่าย' ? 'var(--green-700,#15803d)' : (lb === 'ยาก' ? 'var(--red-600,#dc2626)' : 'var(--amber-700,#b45309)');
    var bg = lb === 'ง่าย' ? 'var(--green-50,#f0fdf4)' : (lb === 'ยาก' ? 'var(--red-50,#fef2f2)' : 'var(--amber-50,#fffbeb)');
    return ' <span title="ความยากในการติดอันดับ (ประเมินจากหน้า SERP จริง)" style="font-size:10px;padding:1px 7px;border-radius:999px;white-space:nowrap;color:' + c + ';background:' + bg + '">' + esc(lb) + '</span>';
  }
  function moveCell(k) {
    var cur = k.rank, prev = k.prev_rank;
    if (cur == null && prev != null) return '<span style="color:var(--red-600)">▼ หลุด</span>';
    if (cur != null && prev == null) return '<span class="soft">ใหม่</span>';
    if (cur == null || prev == null) return '<span class="soft">—</span>';
    var d = prev - cur;                       // + = ขยับขึ้น
    if (d > 0) return '<span style="color:var(--green-600)">▲ ' + d + '</span>';
    if (d < 0) return '<span style="color:var(--red-600)">▼ ' + (-d) + '</span>';
    return '<span class="soft">—</span>';
  }
  function citTrend(cit) {
    if (cit.latest_sov == null || cit.prev_sov == null) return '<span class="soft">—</span>';
    var d = Math.round((cit.latest_sov - cit.prev_sov) * 10) / 10;
    if (d > 0) return '<span style="color:var(--green-600)">▲ +' + d + '%</span>';
    if (d < 0) return '<span style="color:var(--red-600)">▼ ' + d + '%</span>';
    return '<span class="soft">คงที่</span>';
  }

  /* 🔔 ไฮไลต์ & แจ้งเตือน — คำนวณจากอันดับจริง (เข้า 1–100 / ขึ้นหน้า 1 / Top 3 / ขยับขึ้น) */
  function renderHighlights(root, rank) {
    var el = root.querySelector('#rp_hl'); if (!el) return;
    var kws = (rank && rank.keywords) || [], wins = [];
    kws.forEach(function (k) {
      if (k.rank == null) return;
      if (k.rank <= 3) wins.push({ p: 4, ic: '🥇', tone: 'green', t: 'ติด Top 3', kw: k.keyword, sub: 'อันดับ #' + k.rank });
      else if (k.on_page1) wins.push({ p: 3, ic: '🎉', tone: 'green', t: 'ขึ้นหน้า 1 แล้ว', kw: k.keyword, sub: 'อันดับ #' + k.rank });
      else if (k.prev_rank == null) wins.push({ p: 1, ic: '✨', tone: 'brand', t: 'เข้าอันดับแล้ว', kw: k.keyword, sub: '#' + k.rank + ' (จาก 1–100)' });
      if (k.prev_rank != null && k.rank != null && (k.prev_rank - k.rank) >= 5)
        wins.push({ p: 2, ic: '📈', tone: 'brand', t: 'ขยับขึ้น ' + (k.prev_rank - k.rank) + ' อันดับ', kw: k.keyword, sub: '#' + k.prev_rank + ' → #' + k.rank });
    });
    wins.sort(function (a, b) { return b.p - a.p; });
    if (!wins.length) {
      el.innerHTML = ui.card({ title: '🔔 ไฮไลต์ & แจ้งเตือน', body: '<div class="hint">ยังไม่มีไฮไลต์ — เมื่อคีย์เวิร์ดเริ่ม<b>ติดอันดับ 1–100 / ขึ้นหน้า 1 / ถูก AI อ้างอิง</b> ระบบจะแจ้งตรงนี้ให้เห็นทันที</div>' });
      return;
    }
    var rows = wins.slice(0, 8).map(function (w) {
      var c = w.tone === 'green' ? 'var(--green-600)' : 'var(--brand-700)';
      return '<div class="list-row" style="align-items:center;gap:10px">' +
        '<div style="font-size:20px">' + w.ic + '</div>' +
        '<div class="grow"><div class="t" style="color:' + c + '">' + esc(w.t) + ' · <span>' + esc(w.kw) + '</span></div>' +
        '<div class="soft small">' + esc(w.sub) + '</div></div></div>';
    }).join('');
    el.innerHTML = ui.card({ title: '🔔 ไฮไลต์ & แจ้งเตือน', sub: 'ความเคลื่อนไหวอันดับล่าสุด (ข้อมูลจริง)', flush: true, body: rows });
  }

  /* 📊 ปัจจัยที่มีผลต่ออันดับ — จาก seo-audit จริง (schema · ลิงก์ภายใน · หน้ากำพร้า · ความสด) */
  function renderFactors(root, audit) {
    var el = root.querySelector('#rp_factors'); if (!el) return;
    if (!audit || !audit.articles) {
      el.innerHTML = ui.card({ title: '📊 ปัจจัยที่มีผลต่ออันดับ', body: RP.noData('ยังไม่มีข้อมูล', 'มีบทความเผยแพร่แล้วระบบจะวิเคราะห์ปัจจัยให้อัตโนมัติ') });
      return;
    }
    function frow(label, val, ok, hint) {
      return '<div class="list-row"><div class="grow"><div class="t"><span style="color:' + (ok ? 'var(--green-600)' : 'var(--amber-600)') + '">' + (ok ? '✔' : '⚠') + '</span> ' +
        esc(label) + ': <b>' + val + '</b></div><div class="soft small">' + esc(hint) + '</div></div></div>';
    }
    var b = frow('Schema (โครงสร้างข้อมูล AEO)', audit.schema_coverage + '%', audit.schema_coverage >= 80, 'ช่วยให้ Google/AI เข้าใจเนื้อหา → ติด rich result + ถูกอ้างอิงง่ายขึ้น') +
      frow('ลิงก์ภายในเฉลี่ย/หน้า', audit.internal_links_avg, audit.internal_links_avg >= 2, 'กระจายพลังอันดับระหว่างหน้า → ดันคีย์เวิร์ดขึ้นเร็ว') +
      frow('หน้ากำพร้า (ไม่มีลิงก์เข้า)', audit.orphan_pages, audit.orphan_pages === 0, audit.orphan_pages ? 'ควรลิงก์ถึงหน้าเหล่านี้ให้ Google เก็บ index ครบ' : 'ทุกหน้ามีลิงก์เข้า—ดีมาก') +
      frow('เนื้อหาที่ควรรีเฟรช', audit.stale_count, audit.stale_count === 0, 'ความสดของเนื้อหาเป็นสัญญาณอันดับ—ระบบรีเฟรชให้อัตโนมัติ');
    el.innerHTML = ui.card({ title: '📊 ปัจจัยที่มีผลต่ออันดับ', sub: 'วิเคราะห์จากบทความจริง ' + audit.articles + ' หน้า', flush: true, body: b });
  }

  /* 🎯 หลักฐาน AEO — ตัวอย่างจริงที่ถาม AI แล้ว AI ตอบโดยอ้างอิงเรา */
  function renderEvidence(root, ex) {
    var el = root.querySelector('#rp_evidence'); if (!el) return;
    var items = (ex && ex.examples) || [];
    if (!items.length) {
      el.innerHTML = ui.card({ title: '🎯 หลักฐาน AEO — AI อ้างอิงเราจริง', body: '<div class="hint">ยังไม่มีหลักฐาน — เมื่อ AI (ChatGPT/Gemini/Perplexity) เริ่มตอบโดย<b>อ้างอิงแบรนด์/เว็บคุณ</b> ระบบจะเก็บคำถาม+คำตอบมาโชว์เป็นหลักฐานตรงนี้ (ตั้งคำถาม AEO ให้ตรงได้ในการ์ด AI Citation)</div>' });
      return;
    }
    var badge = { openai: 'ChatGPT', gemini: 'Gemini', perplexity: 'Perplexity', anthropic: 'Claude' };
    var rows = items.map(function (e) {
      return '<div class="list-row" style="display:block">' +
        '<div class="row between" style="align-items:center"><span class="chip" style="font-weight:700;color:var(--green-700,#15803d)">' + esc(badge[e.engine] || e.engine) + ' ✓ อ้างอิงเรา</span>' +
        '<span class="soft small">' + esc((e.at || '').slice(0, 10)) + '</span></div>' +
        '<div class="t" style="margin:4px 0">ถาม: “' + esc(e.question) + '”</div>' +
        '<div class="soft small" style="border-left:3px solid var(--green-400,#4ade80);padding-left:8px">“' + esc(e.snippet) + '…”</div></div>';
    }).join('');
    el.innerHTML = ui.card({ title: '🎯 หลักฐาน AEO — AI อ้างอิงเราจริง', sub: 'ถาม AI แล้ว AI ตอบโดยอ้างถึงแบรนด์/เว็บคุณ (ตรวจสอบย้อนได้)', flush: true, body: rows });
  }

  /* 🔗 Backlink คุณภาพจริง — ดึงตามคำขอ (กดปุ่ม) เพื่อคุมค่าเครดิต DataForSEO Backlinks */
  function renderBacklinks(root, pid, p) {
    var el = root.querySelector('#rp_backlinks'); if (!el) return;
    el.innerHTML = ui.card({ title: '🔗 Backlink คุณภาพ (จริง)', sub: 'ลิงก์จากเว็บอื่นที่ชี้มาหาคุณ — ดึงสดจาก DataForSEO', flush: true,
      body: '<div class="card-pad"><div class="hint mb">กดเพื่อดึง Backlink จริงของ <b>' + esc(p && p.name || 'เว็บนี้') + '</b> <span style="color:var(--amber-600)">(ใช้เครดิต DataForSEO Backlinks)</span></div>' +
        '<button class="btn btn-primary btn-sm" id="rpBl">🔗 ดึงข้อมูล Backlink</button><div id="rpBlOut" style="margin-top:10px"></div></div>' });
    var btn = el.querySelector('#rpBl'), out = el.querySelector('#rpBlOut');
    if (!btn) return;
    btn.onclick = function () {
      if (!(pid && RP.api.enabled())) { ui.toast('เปิดโหมด Live + เชื่อม backend ก่อน'); return; }
      btn.disabled = true; btn.textContent = 'กำลังดึง…';
      RP.api.projectBacklinks(pid).then(function (d) {
        btn.disabled = false; btn.textContent = '🔄 ดึงอีกครั้ง';
        if (!d.available) { out.innerHTML = '<div class="hint" style="color:var(--amber-700,#b45309)">' + esc(d.note || 'ดึงไม่ได้') + '</div>'; return; }
        var x = d.data || {};
        function cell(l, v) { return '<div><div class="soft small">' + l + '</div><div class="bb" style="font-size:18px">' + (v != null ? fmt.n(v) : '—') + '</div></div>'; }
        out.innerHTML = '<div class="grid grid-4" style="gap:12px">' +
          cell('Backlinks ทั้งหมด', x.backlinks) + cell('โดเมนอ้างอิง', x.referring_domains) +
          cell('DoFollow', x.dofollow) + cell('Domain Rank', x.rank) + '</div>' +
          '<div class="soft small" style="margin-top:8px">คุณภาพ: Spam score ' + (x.spam_score != null ? x.spam_score + '%' : '—') +
          (x.new_referring_domains != null ? ' · โดเมนใหม่ +' + x.new_referring_domains : '') +
          (x.lost_referring_domains != null ? ' · หลุด −' + x.lost_referring_domains : '') + '</div>';
      }).catch(function (e) { btn.disabled = false; btn.textContent = '🔗 ดึงข้อมูล Backlink'; out.innerHTML = '<div class="hint" style="color:var(--red-600)">ดึงไม่ได้: ' + esc(e.message || String(e)) + '</div>'; });
    };
  }

  function fillReport(root, p, rank, cit, aeo, audit, examples) {
    rank = rank || {}; cit = cit || {}; aeo = aeo || {};
    renderHighlights(root, rank);
    renderFactors(root, audit);
    renderEvidence(root, examples);
    /* renderBacklinks ปิดไว้ก่อน — ต้องสมัคร DataForSEO Backlinks API แยก */
    var kpi = root.querySelector('#rp_kpi');
    if (kpi) kpi.innerHTML = '<div class="grid grid-4">' +
      ui.kpi({ label: 'ติดหน้า 1 (Top 10)', value: rank.page1 != null ? rank.page1 : '—', tone: 'pos', foot: rank.keywords_tracked ? ('จาก ' + rank.keywords_tracked + ' คีย์เวิร์ด') : 'ยังไม่ได้วัด' }) +
      ui.kpi({ label: 'Top 3', value: rank.top3 != null ? rank.top3 : '—', tone: 'brand' }) +
      ui.kpi({ label: 'อันดับเฉลี่ย', value: rank.avg_position != null ? rank.avg_position : '—' }) +
      ui.kpi({ label: 'AI Citation SoV', value: cit.latest_sov != null ? (cit.latest_sov + '%') : '—', tone: 'brand', foot: cit.count ? '' : 'ยังไม่ได้วัด' }) +
      '</div>';
    var rk = root.querySelector('#rp_rank');
    if (rk) {
      var kws = rank.keywords || [];
      if (!kws.length) {
        rk.innerHTML = ui.card({ title: 'อันดับ Google (ต่อคีย์เวิร์ด)',
          body: RP.noData('ยังไม่มีข้อมูลอันดับ', 'ระบบวัดอันดับให้ทุกวัน 06:00 — รอเก็บ 1–7 วัน (หรือกดตรวจสดในหน้าโปรเจ็ค)') });
      } else {
        var rows = kws.map(function (k) {
          var striking = (k.rank != null && k.rank >= 11 && k.rank <= 40 && !k.on_page1);
          var badge = k.on_page1 ? ui.badge('หน้า 1', 'green') : (striking ? ui.badge('จ่อหน้า 1 · กำลังดัน', 'amber') : '');
          return '<tr' + (striking ? ' style="background:var(--amber-50,#fffbeb)"' : '') + '>' +
            '<td><span class="t">' + esc(k.keyword) + '</span> ' + badge + diffChip(k) + '</td>' +
            '<td class="num bb">' + rankLabel(k.rank) + '</td>' +
            '<td class="num soft">' + (k.best_rank != null ? ('#' + k.best_rank) : '—') + '</td>' +
            '<td class="num">' + moveCell(k) + '</td></tr>';
        }).join('');
        rk.innerHTML = ui.card({ title: 'อันดับ Google (ต่อคีย์เวิร์ด)', sub: 'อันดับจริงจาก SERP · แถวเหลือง = จ่อหน้า 1 (กำลังดัน) · ป้าย ง่าย/ปานกลาง/ยาก = ความยากในการติด (ระบบตีตัวง่ายก่อน)', flush: true,
          body: '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>คีย์เวิร์ด</th><th class="right">อันดับ</th><th class="right">ดีสุด</th><th class="right">เปลี่ยนแปลง</th></tr></thead><tbody>' + rows + '</tbody></table></div>' });
      }
    }
    var av = root.querySelector('#rp_aeo');
    if (av) {
      var arts = aeo.articles || [];
      var pub = arts.filter(function (a) { return a.status === 'published'; }).length;
      var arows = arts.slice(0, 6).map(function (a) {
        return '<div class="list-row"><span class="t nowrap">' + esc(a.title) + '</span><div class="grow"></div>' +
          '<span class="badge ' + gradeTone(a.grade) + '">' + a.score + ' · ' + a.grade + '</span></div>';
      }).join('');
      av.innerHTML = ui.card({ title: 'คุณภาพคอนเทนต์ (AEO)',
        sub: (aeo.avg_score != null ? ('คะแนนเฉลี่ย ' + aeo.avg_score + ' · ') : '') + 'เผยแพร่ ' + pub + ' บทความ',
        body: arows || RP.noData('ยังไม่มีบทความ', 'ระบบกำลังผลิตให้ — รอสักครู่') });
    }
    var ct = root.querySelector('#rp_cite');
    if (ct) {
      var citeInner = cit.count ? (
        '<div class="row between" style="margin-bottom:6px"><span class="soft small">SoV ล่าสุด</span><span class="bb" style="font-size:20px">' + (cit.latest_sov != null ? cit.latest_sov + '%' : '—') + '</span></div>' +
        '<div class="row between"><span class="soft small">เทียบรอบก่อน</span><span>' + citTrend(cit) + '</span></div>' +
        '<div class="hint" style="margin-top:8px">วัดจาก ' + cit.count + ' รอบ · ยิงคำถามจริงไปที่ AI แล้ววัดว่าอ้างแบรนด์คุณไหม</div>'
      ) : RP.noData('ยังไม่มีข้อมูล Citation', 'ระบบสุ่มถาม AI ทุกสัปดาห์ — รอผลรอบแรก');
      ct.innerHTML = ui.card({ title: 'AEO — AI Citation', sub: 'ถูก AI (ChatGPT/Gemini/Perplexity) อ้างอิงแค่ไหน',
        body: citeInner +
          '<div class="hint" style="margin-top:10px;color:var(--amber-700,#b45309)">คำถามไม่ตรง? ตั้งคำถามแบบที่ "คนถาม AI จริง" เองได้ — ระบบจะใช้ชุดนี้ก่อน</div>' +
          '<button class="btn btn-sm" id="aeoQBtn" style="margin-top:6px">🎯 ตั้งคำถาม AEO</button>' });
      var qb = ct.querySelector('#aeoQBtn');
      if (qb) qb.onclick = function () { if (RP.openAeoQuestions) RP.openAeoQuestions(rDbId(p), p.name); else RP.go('projects'); };
    }
  }

  function realReport() {
    var p = currentProject();
    if (!p) {
      return { html: ui.pageHead({ eyebrow: 'ImVisible · รายงานผลงาน', title: 'รายงานผลงาน', desc: 'อันดับ SEO · AEO/AI Citation · ความคืบหน้า' }) +
        ui.card({ body: RP.noData('ยังไม่มีโปรเจ็ค', 'สร้างโปรเจ็คแรกก่อน แล้วระบบจะเก็บอันดับ/AEO ให้อัตโนมัติ', '<button class="btn btn-primary" id="rpNew">＋ สร้างโปรเจ็ค</button>') }),
        mount: function (root) { var b = root.querySelector('#rpNew'); if (b) b.onclick = function () { RP.go('projects'); }; } };
    }
    var pid = rDbId(p);
    var html = ui.pageHead({ eyebrow: 'ImVisible · รายงานผลงาน', title: esc(p.name),
      desc: 'อันดับ Google (1–100) · AEO/AI Citation · ความคืบหน้า — ข้อมูลจริงจากระบบ ตรวจสอบได้' }) +
      '<div class="row between wrap mb" style="gap:8px;align-items:center">' +
      '<span class="soft small">อันดับวัดอัตโนมัติทุกวัน 06:00 · กดเพื่อวัดเดี๋ยวนี้ (ต้องต่อ DataForSEO)</span>' +
      '<button class="btn btn-sm btn-primary" id="rpMeasure">🔄 วัดอันดับเดี๋ยวนี้</button></div>' +
      '<div id="rp_kpi" class="mb"><div class="hint">กำลังโหลดรายงาน…</div></div>' +
      '<div id="rp_hl" class="mb"></div>' +
      '<div id="rp_rank" class="mb"></div>' +
      '<div class="grid mb" style="grid-template-columns:1fr 1fr;gap:16px"><div id="rp_aeo"></div><div id="rp_cite"></div></div>' +
      '<div id="rp_evidence" class="mb"></div>' +
      '<div id="rp_factors" class="mb"></div>';   /* การ์ด Backlink ปิดไว้ก่อน (ต้องสมัคร Backlinks API แยก) — เปิดคืนได้ที่ renderBacklinks */
    return { html: html, mount: function (root) {
      var mb = root.querySelector('#rpMeasure');
      if (mb) mb.onclick = function () {
        mb.disabled = true; mb.textContent = 'กำลังวัด…';
        RP.api.measureAllRanks(pid).then(function (d) {
          ui.toast(d.queued ? ('สั่งวัดอันดับ ' + d.queued + ' คีย์เวิร์ดแล้ว ✓ อีกสักครู่กดรีเฟรช') : (d.note || 'ยังไม่มีบทความให้วัด'));
          mb.textContent = '⏳ กำลังวัด';
        }).catch(function (e) { mb.disabled = false; mb.textContent = '🔄 วัดอันดับเดี๋ยวนี้'; ui.toast('วัดไม่ได้: ' + esc(e.message || String(e))); });
      };
      if (!(pid && RP.api.enabled())) return;
      Promise.all([
        RP.api.rankHistory(pid).catch(function () { return null; }),
        RP.api.citationHistory(pid).catch(function () { return null; }),
        RP.api.projectAeo(pid).catch(function () { return null; }),
        RP.api.seoAudit(pid).catch(function () { return null; }),
        RP.api.citationExamples(pid).catch(function () { return null; })
      ]).then(function (r) { fillReport(root, p, r[0], r[1], r[2], r[3], r[4]); });
    } };
  }

  /* ============ รายงานแผนธุรกิจ (โหมดตัวอย่าง/พรีเซนต์เท่านั้น) ============ */
  function sampleReport() {
    var d = RP.data || {};

    // ---- 1) แถบสถิติ (facts) ----
    var facts = d.facts || [];
    var factsHtml = '<div class="grid grid-4 mb">';
    facts.forEach(function (f) {
      factsHtml +=
        '<div class="card card-pad center">' +
          '<div class="bb" style="font-size:1.8rem;line-height:1.2;color:var(--purple-700)">' + esc(f.v) + '</div>' +
          '<div class="soft small">' + esc(f.d) + '</div>' +
        '</div>';
    });
    factsHtml += '</div>';

    // ---- 2) แผนพัฒนา (Roadmap) ----
    var roadmap = d.roadmap || [];
    var rmRows = '';
    roadmap.forEach(function (r) {
      rmRows +=
        '<tr>' +
          '<td class="bb">' + esc(r.phase) + '</td>' +
          '<td>' + esc(r.scope) + '</td>' +
          '<td class="nowrap">' + esc(r.weeks) + '</td>' +
          '<td>' + ui.bar(r.progress) + ' ' + esc(String(r.progress)) + '%</td>' +
        '</tr>';
    });
    var roadmapCard = ui.card({
      title: 'แผนพัฒนา (Roadmap)',
      sub: 'แบ่งเป็น 4 เฟส',
      flush: true,
      cls: 'mb',
      body: tbl(
        '<th>เฟส</th><th>ขอบเขต</th><th>ระยะเวลา</th><th>ความคืบหน้า</th>',
        rmRows
      )
    });

    // ---- 3) ตัวชี้วัดความสำเร็จ (KPI) ----
    // บัญชีจริง: แสดงได้เฉพาะ "เป้าหมาย" (เป็นแผน ไม่ใช่ผลวัด)
    // คอลัมน์ "ปัจจุบัน" + แถบความคืบหน้า = ตัวเลขที่ยังไม่ได้วัดจริง → ห้ามโชว์
    var kpiTargets = d.kpiTargets || [];
    var kpiSampleRows = '';
    var kpiTargetRows = '';
    kpiTargets.forEach(function (k) {
      kpiSampleRows +=
        '<tr>' +
          '<td class="bb">' + esc(k.kpi) + '</td>' +
          '<td>' + esc(k.target) + '</td>' +
          '<td class="num">' + esc(k.curTxt) + '</td>' +
          '<td>' + ui.bar(k.pct) + ' ' + esc(String(k.pct)) + '%</td>' +
        '</tr>';
      kpiTargetRows +=
        '<tr>' +
          '<td class="bb">' + esc(k.kpi) + '</td>' +
          '<td>' + esc(k.target) + '</td>' +
          '<td class="soft">ยังไม่ได้วัด</td>' +
        '</tr>';
    });

    var kpiSampleBody = tbl(
      '<th>KPI</th><th>เป้าหมาย</th><th>ปัจจุบัน</th><th>ความคืบหน้า</th>',
      kpiSampleRows
    );

    var kpiBody =
      (RP.isReal()
        ? tbl('<th>KPI</th><th>เป้าหมาย</th><th>ปัจจุบัน</th>', kpiTargetRows)
        : '') +
      RP.realOr(kpiSampleBody, {
        title: 'ยังไม่มีผลวัดจริงของโปรเจ็คคุณ',
        hint: 'คอลัมน์ "ปัจจุบัน" และความคืบหน้าจะขึ้นเมื่อระบบเก็บอันดับ / Citation / ทราฟฟิกของโปรเจ็คคุณได้จริง — เราไม่แสดงตัวเลขสมมติ ตัวเลขในตารางด้านบนเป็น "เป้าหมาย" เท่านั้น',
        cta: '<button class="btn btn-sm btn-primary" id="rpKpiProjects">＋ ตั้งค่าโปรเจ็คของคุณ</button>'
      });

    var kpiCard = ui.card({
      title: 'ตัวชี้วัดความสำเร็จ (KPI) — เป้าหมาย 6 เดือน',
      action: RP.sampleBadge('ตัวเลขตัวอย่าง'),
      flush: true,
      cls: 'mb',
      body: kpiBody
    });

    // ---- 4) กลยุทธ์ที่ทำให้เห็นผลจริง ----
    var strategies = d.strategies || [];
    var stratBody = '';
    strategies.forEach(function (s) {
      stratBody +=
        '<div class="list-row"><div class="grow">' +
          '<div class="t bb">' + esc(s.t) + '</div>' +
          '<div class="s soft small">' + esc(s.d) + '</div>' +
        '</div></div>';
    });
    stratBody += '<div class="note-box">' + esc(d.strategyNote) + '</div>';
    var stratCard = ui.card({
      title: 'กลยุทธ์ที่ทำให้เห็นผลจริง',
      cls: 'mb',
      body: stratBody
    });

    // ---- 5) ประมาณการต้นทุน ----
    var costs = d.costs || [];
    var costRows = '';
    costs.forEach(function (c) {
      costRows +=
        '<tr>' +
          '<td>' + esc(c.item) + '</td>' +
          '<td class="right">' + esc(c.est) + '</td>' +
        '</tr>';
    });
    costRows +=
      '<tr>' +
        '<td class="bb">รวมโดยประมาณ</td>' +
        '<td class="bb right">' + esc(d.costTotal) + '</td>' +
      '</tr>';
    var costBody =
      tbl('<th>รายการ</th><th class="right">ประมาณการ</th>', costRows) +
      '<div class="hint">ต้นทุนต่ำกว่าจ้างนักเขียน SEO 1 คนหลายเท่า — โมเดลนี้จึงมี Margin สูง</div>';
    var costCard = ui.card({
      title: 'ประมาณการต้นทุน (ต่อ 1 โปรเจ็ค/เดือน)',
      flush: true,
      cls: 'mb',
      body: costBody
    });

    // ---- 6) สถาปัตยกรรม & เทคโนโลยี ----
    var stack = d.stack || [];
    var stackRows = '';
    stack.forEach(function (s) {
      stackRows +=
        '<tr>' +
          '<td class="bb">' + esc(s.part) + '</td>' +
          '<td>' + esc(s.tech) + '</td>' +
          '<td class="soft">' + esc(s.note) + '</td>' +
        '</tr>';
    });
    var stackCard = ui.card({
      title: 'สถาปัตยกรรม & เทคโนโลยี',
      flush: true,
      cls: 'mb',
      body: tbl(
        '<th>ส่วนประกอบ</th><th>เทคโนโลยีที่แนะนำ</th><th>หมายเหตุ</th>',
        stackRows
      )
    });

    // ---- 7) โมเดลธุรกิจ & แนวทางหารายได้ ----
    var pricing = d.pricing || [];
    var priceRows = '';
    pricing.forEach(function (p) {
      priceRows +=
        '<tr>' +
          '<td class="bb">' + esc(p.plan) + '</td>' +
          '<td>' + esc(p.detail) + '</td>' +
          '<td class="nowrap">' + esc(p.price) + '</td>' +
        '</tr>';
    });
    var priceBody =
      tbl('<th>รูปแบบ</th><th>รายละเอียด</th><th>ราคาแนะนำ</th>', priceRows) +
      '<div class="note-box">ลำดับที่แนะนำ: ใช้เองก่อนเพื่อพิสูจน์ว่า "ระบบดันเว็บติดจริง" → เก็บตัวเลขเป็น Case Study → เปิดรับลูกค้า Agency → เมื่อระบบนิ่งค่อยเปิด SaaS</div>';
    var priceCard = ui.card({
      title: 'โมเดลธุรกิจ & แนวทางหารายได้',
      flush: true,
      cls: 'mb',
      body: priceBody
    });

    // ---- 8) ความเสี่ยงที่ต้องรู้ก่อนลงมือ ----
    var risks = d.risks || [];
    var riskBody = '';
    risks.forEach(function (r) {
      riskBody +=
        '<div class="warn-box mb">' +
          '<div class="bb">⚠ ' + esc(r.t) + '</div>' +
          '<div>' + esc(r.d) + '</div>' +
        '</div>';
    });
    var riskCard = ui.card({
      title: 'ความเสี่ยงที่ต้องรู้ก่อนลงมือ',
      cls: 'mb',
      body: riskBody
    });

    // ---- 9) แหล่งอ้างอิง ----
    var references = d.references || [];
    var refBody = '';
    references.forEach(function (r) {
      refBody +=
        '<div class="list-row"><div class="grow">' +
          '<div class="t soft small">' + esc(r) + '</div>' +
        '</div></div>';
    });
    var refCard = ui.card({
      title: 'แหล่งอ้างอิง',
      cls: 'mb',
      body: refBody
    });

    var html =
      ui.pageHead({
        eyebrow: 'รายงานโครงการ',
        title: 'รายงาน & Roadmap',
        desc: 'สรุปแผนพัฒนา ตัวชี้วัดความสำเร็จ ต้นทุน สถาปัตยกรรม โมเดลธุรกิจ และความเสี่ยง (อ้างอิงหัวข้อ 7–11 ของเอกสารโครงการ)'
      }) +
      RP.sampleNotice('ตัวชี้วัด (KPI) ของหน้านี้') +
      RP.collectingNotice('ตัวชี้วัด (KPI) ของโปรเจ็คคุณ') +
      factsHtml +
      roadmapCard +
      kpiCard +
      stratCard +
      costCard +
      stackCard +
      priceCard +
      riskCard +
      refCard;

    return {
      html: html,
      mount: function (root) {
        if (!root) return;
        var b = root.querySelector('#rpKpiProjects');
        if (b) b.onclick = function () { RP.go('projects'); };
      }
    };
  };
})(window.RP);
