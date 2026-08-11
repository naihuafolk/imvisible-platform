/* ============================================================
   View: 🚀 เครื่องมือโต (Growth Tools) — รวม 5 เครื่องยนต์ดันอันดับ SEO/AEO/GEO
   ในหน้าเดียว (แท็บ) โดยดึงข้อมูล "จริง" จาก backend (DataForSEO/SERP/AI):
     1) 🌐 Reddit/Quora Radar   → socialRadar   (+ ร่างคำตอบ reuse pantipReply)
     2) 🎯 Content Gap          → contentGaps
     3) 🥇 Featured Snippet     → snippetOpportunities
     4) 🔗 Competitor Backlink  → backlinkGaps
     5) 🧭 AI-Citation Audit    → aiCitationAudit(pid)  (ต้องเลือกโปรเจ็ค db)
   ห้ามกุตัวเลข — ทุกอย่างมาจาก response จริง · ทุกจุดมี .catch → RP.noData
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  /* ---------- helper ร่วม ---------- */
  function fmtn(n) { return (n == null || n === '') ? '—' : Number(n).toLocaleString(); }
  function diffColor(d) { return d == null ? '#94a3b8' : d < 30 ? '#0a7350' : d < 60 ? '#b45309' : '#c0392b'; }
  function diffLabel(d) { return d == null ? '—' : d < 30 ? 'ง่าย' : d < 60 ? 'ปานกลาง' : 'ยาก'; }
  // แยกบรรทัด/คอมมาใน textarea → array (ตัดค่าว่าง + ตัดซ้ำ รักษาลำดับ)
  function lines(v) {
    var seen = {}, out = [];
    (v || '').split(/[\n,]+/).forEach(function (s) {
      s = s.trim(); if (!s) return;
      var k = s.toLowerCase(); if (seen[k]) return; seen[k] = 1; out.push(s);
    });
    return out;
  }
  // เช็ก backend เข้าถึงได้ไหม (เหมือน pantip.js) — ไม่ถึง = toast แล้วหยุด
  function reachable() {
    if (RP.api && RP.api.reachable()) return true;
    ui.toast('เชื่อมต่อ backend ไม่ได้ — เปิดโหมด Live ในหน้าตั้งค่า'); return false;
  }
  function copyText(t) {
    try { navigator.clipboard.writeText(t); ui.toast('คัดลอกแล้ว ✓'); }
    catch (e) { var a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); try { document.execCommand('copy'); ui.toast('คัดลอกแล้ว ✓'); } catch (x) {} a.remove(); }
  }
  // ปุ่มรัน: toggle สถานะกำลังโหลด
  function busy(btn, on, label) { if (!btn) return; btn.disabled = on; btn.textContent = on ? 'กำลังทำงาน…' : label; }
  // แถวการ์ดสรุปเลข (reuse โครงเดียวกับ prospect.js)
  function statCards(items) {
    return '<div class="row wrap" style="gap:10px;margin-bottom:8px">' + items.map(function (c) {
      return '<div class="card card-pad" style="flex:1;min-width:130px"><div class="soft small">' + c[0] + '</div>' +
        '<div class="bb" style="font-size:22px;color:var(--brand-700,#4338ca)">' + c[1] + '</div></div>';
    }).join('') + '</div>';
  }
  // โปรเจ็ค db จริง (เหมือน writeblog.js) สำหรับ AI-Citation
  function dbProjects() {
    return ((RP.data.project && RP.data.project.list) || []).filter(function (p) { return /^db/.test(String(p.id)); });
  }
  function dbId(idStr) { var m = /^db(\d+)$/.exec(String(idStr || '')); return m ? parseInt(m[1], 10) : null; }

  /* ============================================================
     1) 🌐 Reddit/Quora Radar — หน้าชุมชนที่ติดหน้า 1 Google (GEO)
     ============================================================ */
  function radarThread(t, idx) {
    var col = t.rank <= 3 ? '#0a7350' : '#1a56ff';
    var badge = '<span style="display:inline-block;background:' + col + ';color:#fff;font-weight:800;font-size:.72rem;padding:2px 10px;border-radius:999px;white-space:nowrap">' + esc(t.platform || 'web') + ' · อันดับ ' + t.rank + '</span>';
    return '<div class="card card-pad" style="margin-bottom:10px">' +
      '<div style="display:flex;gap:9px;align-items:flex-start;flex-wrap:wrap">' + badge +
        '<span class="soft small" style="margin-top:1px">จากการค้น: "' + esc(t.query || '') + '"</span></div>' +
      '<a href="' + esc(t.url) + '" target="_blank" rel="noopener" style="display:inline-block;margin-top:7px;font-weight:700;color:var(--brand-700,#4338ca);text-decoration:none">' + esc(t.title || t.url) + '</a>' +
      (t.snippet ? '<div class="soft small" style="margin-top:4px;line-height:1.5">' + esc(t.snippet) + '</div>' : '') +
      '<div class="row" style="margin-top:11px;gap:8px">' +
        '<button class="btn btn-sm gr-draft" data-idx="' + idx + '">✍️ ร่างคำตอบ (ช่วยจริง)</button>' +
        '<a class="btn btn-sm" href="' + esc(t.url) + '" target="_blank" rel="noopener">เปิดหน้า →</a>' +
      '</div>' +
      '<div class="gr-reply" data-idx="' + idx + '"></div>' +
    '</div>';
  }
  function renderRadar(out, d, biz) {
    var ts = d.threads || [];
    out.innerHTML =
      '<div class="soft small" style="margin-bottom:10px">พบ <b>' + ts.length + '</b> หน้าชุมชนติดหน้า 1 Google — ตอบให้ <b>มีประโยชน์จริง</b> = ยืมทราฟฟิก + ดัน GEO (AI อ้างอิงชุมชนพวกนี้บ่อย)</div>' +
      ts.map(radarThread).join('') +
      (d.note ? '<div class="hint" style="margin-top:8px">⚠️ ' + esc(d.note) + '</div>' : '');
    ts.forEach(function (t, idx) {
      var btn = out.querySelector('.gr-draft[data-idx="' + idx + '"]');
      if (!btn) return;
      btn.onclick = function () {
        var box = out.querySelector('.gr-reply[data-idx="' + idx + '"]');
        btn.disabled = true; btn.textContent = 'กำลังร่าง…';
        box.innerHTML = '<div class="hint" style="margin-top:10px">⏳ AI กำลังร่างคำตอบที่ช่วยจริง…</div>';
        // reuse pantipReply — โครงเดียวกับ pantip.js
        RP.api.pantipReply({ url: t.url, title: t.title, snippet: t.snippet, brand: biz || '' }).then(function (r) {
          box.innerHTML = '<div style="margin-top:10px">' + ui.card({ body:
            '<div class="soft small" style="margin-bottom:6px">📝 ร่างคำตอบ (ตรวจให้เข้ากับกระทู้ก่อนโพสต์เอง · ห้ามยัดลิงก์/โฆษณา):</div>' +
            '<div style="white-space:pre-wrap;line-height:1.62">' + esc(r.reply || '') + '</div>' +
            '<div class="row" style="margin-top:11px;gap:8px"><button class="btn btn-sm gr-copy">📋 คัดลอก</button><a class="btn btn-sm btn-primary" href="' + esc(t.url) + '" target="_blank" rel="noopener">ไปโพสต์ที่หน้าเดิม →</a></div>' }) + '</div>';
          var cp = box.querySelector('.gr-copy'); if (cp) cp.onclick = function () { copyText(r.reply || ''); };
        }).catch(function (e) {
          box.innerHTML = '<div style="margin-top:10px">' + ui.card({ body: RP.noData('ร่างไม่ได้', esc(e.message || String(e))) }) + '</div>';
        }).then(function () { btn.disabled = false; btn.textContent = '✍️ ร่างใหม่'; });
      };
    });
  }

  /* ============================================================
     2) 🎯 Content Gap — คีย์ที่คู่แข่งติด แต่เราไม่ติด
     ============================================================ */
  function renderGaps(out, d) {
    var gaps = d.gaps || [], s = d.summary || {};
    out.innerHTML =
      statCards([
        ['ช่องว่างคีย์เวิร์ด', fmtn(s.count)],
        ['เข้าถึงรวม/เดือน', fmtn(s.total_monthly)],
        ['/วัน', fmtn(s.total_daily)],
        ['ยากเฉลี่ย', s.avg_difficulty == null ? '—' : s.avg_difficulty + '%']
      ]) +
      '<div class="soft small" style="margin-bottom:4px">🟢 ง่าย ' + (s.easy || 0) + ' · 🟡 ปานกลาง ' + (s.medium || 0) + ' · 🔴 ยาก ' + (s.hard || 0) + ' — <b>ยิ่งความยากต่ำ ยิ่งแซงเร็ว</b></div>' +
      ui.card({ flush: true, body:
        '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>คีย์เวิร์ด (คู่แข่งติด เราไม่ติด)</th><th class="right">ค้นหา/เดือน</th><th class="right">ความยาก</th><th class="right">อันดับคู่แข่ง</th><th>คู่แข่งที่ติด</th></tr></thead><tbody>' +
        gaps.map(function (g) {
          var dc = diffColor(g.difficulty);
          return '<tr><td><div class="t">' + esc(g.keyword) + '</div></td>' +
            '<td class="right" style="font-variant-numeric:tabular-nums">' + fmtn(g.volume) + '</td>' +
            '<td class="right"><b style="color:' + dc + '">' + (g.difficulty == null ? '—' : g.difficulty + '%') + '</b> <span class="soft small">' + diffLabel(g.difficulty) + '</span></td>' +
            '<td class="right" style="font-variant-numeric:tabular-nums">' + (g.rank == null ? '—' : '#' + g.rank) + '</td>' +
            '<td class="soft small">' + esc(g.competitor || '') + '</td></tr>';
        }).join('') + '</tbody></table></div>' }) +
      (d.note ? '<div class="hint" style="margin-top:8px">' + esc(d.note) + '</div>' : '');
  }

  /* ============================================================
     3) 🥇 Featured Snippet — ชิง Position 0 + PAA
     ============================================================ */
  function renderSnippets(out, d) {
    var ops = d.opportunities || [];
    out.innerHTML =
      '<div class="soft small" style="margin-bottom:8px">ตรวจ ' + ops.length + ' คีย์: มี Featured Snippet อยู่แล้วไหม + ใครถือครอง + คำถาม People-Also-Ask จริง → เอาไปจัดรูปแบบคอนเทนต์ชิง Position 0</div>' +
      ops.map(function (o) {
        var has = o.has_snippet;
        var badge = has
          ? '<span class="badge" style="background:#b45309;color:#fff">มี Snippet แล้ว</span>'
          : '<span class="badge" style="background:#0a7350;color:#fff">ว่าง — ชิงได้</span>';
        var paa = (o.paa_questions || []);
        return ui.card({ cls: 'mb', body:
          '<div class="row wrap between" style="gap:8px;align-items:center">' +
            '<div class="bb" style="font-size:16px">' + esc(o.keyword) + '</div>' + badge + '</div>' +
          (o.snippet_holder_domain ? '<div class="soft small" style="margin-top:4px">เจ้าของ Snippet ปัจจุบัน: <b>' + esc(o.snippet_holder_domain) + '</b></div>' : '') +
          (paa.length
            ? '<div class="soft small" style="margin-top:8px">❓ People-Also-Ask (' + paa.length + '):</div><ul style="margin:4px 0 0;padding-left:18px;line-height:1.7">' +
              paa.map(function (q) { return '<li>' + esc(q) + '</li>'; }).join('') + '</ul>'
            : '<div class="soft small" style="margin-top:6px">ไม่พบ People-Also-Ask สำหรับคีย์นี้</div>') +
          (o.guidance ? '<div class="hint" style="margin-top:9px">💡 ' + esc(o.guidance) + '</div>' : '') });
      }).join('') +
      (d.note ? '<div class="hint" style="margin-top:4px">' + esc(d.note) + '</div>' : '');
  }

  /* ============================================================
     4) 🔗 Competitor Backlink — แหล่งที่ควร outreach
     ============================================================ */
  function renderBacklinks(out, d) {
    var ops = d.opportunities || [];
    out.innerHTML =
      '<div class="soft small" style="margin-bottom:8px">พบ <b>' + ops.length + '</b> โดเมนที่ลิงก์ให้คู่แข่ง (เรียงตามจำนวนคู่แข่งที่ได้ลิงก์ → ยิ่งหลายเจ้ายิ่งมีแนวโน้มลิงก์ให้เรา) · ไปติดต่อขอลิงก์เอง (white-hat)</div>' +
      ui.card({ flush: true, body:
        '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>โดเมนที่ควรไปขอลิงก์</th><th class="right">ลิงก์ให้คู่แข่งกี่เจ้า</th><th>คู่แข่งที่ได้ลิงก์</th><th class="right">Domain Rank</th><th class="right">Backlinks</th></tr></thead><tbody>' +
        ops.map(function (o) {
          return '<tr><td><div class="t"><a href="https://' + esc(o.domain) + '" target="_blank" rel="noopener" style="color:var(--brand-700,#4338ca);text-decoration:none">' + esc(o.domain) + '</a></div></td>' +
            '<td class="right"><b>' + fmtn(o.competitors_count) + '</b></td>' +
            '<td class="soft small">' + esc((o.competitors || []).join(', ')) + '</td>' +
            '<td class="right" style="font-variant-numeric:tabular-nums">' + fmtn(o.rank) + '</td>' +
            '<td class="right" style="font-variant-numeric:tabular-nums">' + fmtn(o.backlinks) + '</td></tr>';
        }).join('') + '</tbody></table></div>' }) +
      (d.note ? '<div class="hint" style="margin-top:8px">' + esc(d.note) + '</div>' : '');
  }

  /* ============================================================
     5) 🧭 AI-Citation Audit — SoV% + คู่แข่งที่ AI แนะนำ + source gaps
     ============================================================ */
  function renderCitation(out, d) {
    var sov = d.sov_percent;
    var comps = d.competitor_mentions || {};
    var compKeys = Object.keys(comps);
    var gaps = d.source_gaps || [];
    out.innerHTML =
      statCards([
        ['Share of Voice (AI แนะนำเรา)', sov == null ? '—' : sov + '%'],
        ['คำตอบที่อ้างถึงเรา', fmtn(d.our_mentions) + ' / ' + fmtn(d.answered)],
        ['คู่แข่งที่ AI เอ่ยถึง', fmtn(compKeys.length)],
        ['ช่องว่างแหล่งอ้างอิง', fmtn(gaps.length)]
      ]) +
      (d.engines_used && d.engines_used.length ? '<div class="soft small" style="margin-bottom:8px">ถามจริงผ่าน: <b>' + esc(d.engines_used.join(' · ')) + '</b></div>' : '') +
      // คู่แข่งที่ AI แนะนำแทนเรา
      ui.card({ cls: 'mb', title: '🥊 คู่แข่งที่ AI แนะนำ', flush: true, body:
        (compKeys.length
          ? '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>คู่แข่ง</th><th class="right">ถูกเอ่ยถึง (ครั้ง)</th></tr></thead><tbody>' +
            compKeys.map(function (k) { return '<tr><td><div class="t">' + esc(k) + '</div></td><td class="right"><b>' + fmtn(comps[k]) + '</b></td></tr>'; }).join('') +
            '</tbody></table></div>'
          : '<div class="card-pad">' + RP.noData('AI ยังไม่เอ่ยถึงคู่แข่งเจาะจง', 'ดีสำหรับเรา — หรือชุดคำถาม/คีย์แบรนด์ยังแคบไป') + '</div>') }) +
      // source gaps — แหล่งที่ Google หยิบ แต่เรายังไม่อยู่
      ui.card({ title: '📍 แหล่งอ้างอิงที่ควรไปแทรก (เรายังไม่อยู่)', flush: true, body:
        (gaps.length
          ? '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>โดเมนแหล่งอ้างอิง</th><th>ชนิด</th><th>หน้า</th></tr></thead><tbody>' +
            gaps.map(function (g) {
              var kind = g.kind === 'ugc'
                ? '<span class="badge" style="background:#0a7350;color:#fff">ชุมชน/UGC</span>'
                : '<span class="badge">เว็บ</span>';
              return '<tr><td><div class="t">' + esc(g.domain) + '</div></td><td>' + kind + '</td>' +
                '<td><a href="' + esc(g.url) + '" target="_blank" rel="noopener" class="soft small">' + esc(g.title || g.url) + ' ↗</a></td></tr>';
            }).join('') + '</tbody></table></div>'
          : '<div class="card-pad">' + RP.noData('ไม่พบ source gap', 'ต้องมีคีย์ DataForSEO ในโปรเจ็คเพื่อดึงแหล่งอ้างอิง หรือเราอยู่ครบทุกแหล่งแล้ว') + '</div>') }) +
      (d.note ? '<div class="hint" style="margin-top:8px">' + esc(d.note) + '</div>' : '');
  }

  /* ============================================================
     โครงหน้า: แท็บ 5 เครื่องมือ
     ============================================================ */
  var TABS = [
    { id: 'radar', ico: '🌐', lbl: 'Reddit/Quora Radar' },
    { id: 'gap', ico: '🎯', lbl: 'Content Gap' },
    { id: 'snippet', ico: '🥇', lbl: 'Featured Snippet' },
    { id: 'backlink', ico: '🔗', lbl: 'Competitor Backlink' },
    { id: 'citation', ico: '🧭', lbl: 'AI-Citation Audit' }
  ];

  // แผงกรอกของแต่ละเครื่องมือ (คืน html string)
  function panelRadar() {
    return '<div class="gr-panel" data-panel="radar">' + ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-end">' +
      '<div style="flex:2;min-width:200px"><div class="soft small" style="margin-bottom:4px">หัวข้อ / คีย์เวิร์ด</div><input class="input" id="gr_rad_kw" placeholder="เช่น AI SEO · CRM · digital marketing agency" style="width:100%"></div>' +
      '<div style="flex:2;min-width:200px"><div class="soft small" style="margin-bottom:4px">แบรนด์/ธุรกิจ (ไม่บังคับ · ใช้ตอนร่างคำตอบ)</div><input class="input" id="gr_rad_biz" placeholder="เช่น ImVisible" style="width:100%"></div>' +
      '<button class="btn btn-primary" id="gr_rad_go">🔎 สแกน Reddit/Quora/Medium</button></div>' +
      '<div class="hint" style="margin-top:8px">หาหน้าชุมชนที่ "ติดหน้า 1 Google" จริง (DataForSEO) → ตอบให้มีประโยชน์ = ดัน GEO · ห้ามสแปม/auto</div>' }) +
      '<div id="gr_rad_out"></div></div>';
  }
  function panelGap() {
    return '<div class="gr-panel" data-panel="gap" style="display:none">' + ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-start">' +
      '<div style="flex:1;min-width:200px"><div class="soft small" style="margin-bottom:4px">โดเมนเรา</div><input class="input" id="gr_gap_dom" placeholder="เช่น imvisible.tech" style="width:100%"></div>' +
      '<div style="flex:1;min-width:220px"><div class="soft small" style="margin-bottom:4px">โดเมนคู่แข่ง (บรรทัดละ 1 · สูงสุด 5)</div><textarea class="input" id="gr_gap_comp" rows="3" placeholder="competitor1.com&#10;competitor2.com" style="width:100%;resize:vertical"></textarea></div>' +
      '</div><div class="row" style="margin-top:10px"><button class="btn btn-primary" id="gr_gap_go">🎯 หาช่องว่างคอนเทนต์</button></div>' +
      '<div class="hint" style="margin-top:8px">คีย์ที่คู่แข่งติดหน้า 1-2 แต่เรายังไม่ติด (DataForSEO Labs) · กินเครดิตต่อครั้ง</div>' }) +
      '<div id="gr_gap_out"></div></div>';
  }
  function panelSnippet() {
    return '<div class="gr-panel" data-panel="snippet" style="display:none">' + ui.card({ cls: 'mb', body:
      '<div class="soft small" style="margin-bottom:4px">คีย์เวิร์ด (บรรทัดละ 1 · สูงสุด 8)</div>' +
      '<textarea class="input" id="gr_sn_kw" rows="4" placeholder="เช่น AEO คืออะไร&#10;วิธีทำ SEO&#10;ChatGPT SEO" style="width:100%;resize:vertical"></textarea>' +
      '<div class="row" style="margin-top:10px"><button class="btn btn-primary" id="gr_sn_go">🥇 ตรวจ Featured Snippet + PAA</button></div>' +
      '<div class="hint" style="margin-top:8px">ดู SERP จริงว่ามี Featured Snippet / People-Also-Ask ไหม → ชิง Position 0 · กินเครดิตต่อคีย์</div>' }) +
      '<div id="gr_sn_out"></div></div>';
  }
  function panelBacklink() {
    return '<div class="gr-panel" data-panel="backlink" style="display:none">' + ui.card({ cls: 'mb', body:
      '<div class="row wrap" style="gap:10px;align-items:flex-start">' +
      '<div style="flex:1;min-width:220px"><div class="soft small" style="margin-bottom:4px">โดเมนคู่แข่ง (บรรทัดละ 1 · สูงสุด 8)</div><textarea class="input" id="gr_bl_comp" rows="3" placeholder="competitor1.com&#10;competitor2.com" style="width:100%;resize:vertical"></textarea></div>' +
      '<div style="flex:1;min-width:200px"><div class="soft small" style="margin-bottom:4px">โดเมนเรา (ไม่บังคับ · ตัดออกจากผล)</div><input class="input" id="gr_bl_dom" placeholder="เช่น imvisible.tech" style="width:100%"></div>' +
      '</div><div class="row" style="margin-top:10px"><button class="btn btn-primary" id="gr_bl_go">🔗 ขุดแหล่งขอลิงก์</button></div>' +
      '<div class="hint" style="margin-top:8px">⚠️ DataForSEO Backlinks เป็นแพ็กเกจแยก คิดเครดิตต่างหาก · หาโดเมนที่ลิงก์ให้คู่แข่งหลายเจ้า</div>' }) +
      '<div id="gr_bl_out"></div></div>';
  }
  function panelCitation() {
    var body;
    if (!(RP.isReal && RP.isReal())) {
      body = ui.card({ body: RP.noData('โหมดตัวอย่าง', 'เข้าสู่ระบบบัญชีจริง + เลือกโปรเจ็คเพื่อวัดว่า AI แนะนำคุณแค่ไหน') });
    } else {
      var projs = dbProjects();
      if (!projs.length) {
        body = ui.card({ body: RP.noData('ยังไม่มีโปรเจ็ค', 'สร้างโปรเจ็ค (แบรนด์คุณ) ก่อน แล้วค่อยตรวจ AI-Citation', '<button class="btn btn-primary" id="gr_ci_new">＋ สร้างโปรเจ็ค</button>') });
      } else {
        var opts = projs.map(function (p) {
          return '<option value="' + esc(p.id) + '"' + (p.id === RP.data.project.current ? ' selected' : '') + '>' + esc(p.name || p.id) + '</option>';
        }).join('');
        body = ui.card({ cls: 'mb', body:
          '<div class="row wrap" style="gap:10px;align-items:flex-end">' +
          '<div style="flex:2;min-width:220px"><div class="soft small" style="margin-bottom:4px">ตรวจโปรเจ็ค</div><select class="input" id="gr_ci_proj" style="width:100%">' + opts + '</select></div>' +
          '<button class="btn btn-primary" id="gr_ci_go">🧭 วัด AI-Citation</button></div>' +
          '<div class="hint" style="margin-top:8px">สุ่มถาม AI จริง (OpenAI/Gemini/Perplexity) ด้วยชุดคำถาม AEO ของโปรเจ็ค → SoV% + คู่แข่งที่ AI แนะนำ + แหล่งที่ต้องไปแทรก · ผลเป็นค่าประมาณเชิงสถิติ (กินเครดิต AI/SERP)</div>' });
      }
    }
    return '<div class="gr-panel" data-panel="citation" style="display:none">' + body + '<div id="gr_ci_out"></div></div>';
  }

  /* error ที่ 'ขาดคีย์ DataForSEO' → การ์ด CTA พาไปตั้งค่า (แทน error ลอย ๆ ที่ดูเหมือนพัง)
     เครื่องมือ 3 ตัวนี้ (Content Gap / Snippet / Backlink) ใช้ข้อมูลเฉพาะของ DataForSEO — ค้นเว็บฟรีแทนไม่ได้ */
  function showKeyError(container, e, kind) {
    var msg = (e && (e.message || String(e))) || '';
    if (/ยังไม่ได้ตั้งคีย์|DataForSEO|503/.test(msg)) {
      var extra = kind === 'backlink'
        ? ' <b>Backlinks เป็นแพ็กเกจแยก</b>ของ DataForSEO (คีย์ SERP อย่างเดียวใช้ไม่ได้)'
        : 'ใช้ข้อมูลเฉพาะจาก DataForSEO (ปริมาณค้นหา/คีย์ที่ติดอันดับ/แบ็กลิงก์ จริง)';
      container.innerHTML = ui.card({ body: RP.noData('ต้องต่อคีย์ DataForSEO ก่อน',
        'เครื่องมือนี้' + extra + ' — ค้นเว็บฟรีแทนไม่ได้ · ต่อคีย์ที่ ⚙️ การตั้งค่า แล้วลองใหม่',
        '<button class="btn btn-primary gr-to-settings">⚙️ ไปตั้งค่า เชื่อม DataForSEO</button>') });
    } else {
      container.innerHTML = ui.card({ body: RP.noData('ดึงไม่ได้', esc(msg)) });
    }
    var b = container.querySelector('.gr-to-settings');
    if (b) b.onclick = function () { RP.go('settings'); };
  }

  RP.views.growth = function () {
    var head = ui.pageHead({ eyebrow: 'ImVisible · เครื่องมือโต', title: '🚀 เครื่องมือโต (Growth Tools)',
      desc: '5 เครื่องยนต์ดันอันดับในหน้าเดียว: หาหน้าชุมชน GEO · ช่องว่างคอนเทนต์ · ชิง Featured Snippet · แหล่งขอ backlink · วัดว่า AI แนะนำคุณแค่ไหน — ตัวเลขจริงทั้งหมด (ไม่กุ)' });

    var tabbar = '<div class="row wrap" style="gap:6px;margin-bottom:14px">' +
      TABS.map(function (t, i) {
        return '<button class="btn btn-sm gr-tab' + (i === 0 ? ' btn-primary' : '') + '" data-tab="' + t.id + '">' + t.ico + ' ' + esc(t.lbl) + '</button>';
      }).join('') + '</div>';

    var html = head + tabbar +
      panelRadar() + panelGap() + panelSnippet() + panelBacklink() + panelCitation();

    return { html: html, mount: function (root) {
      /* ---- สลับแท็บ ---- */
      var tabs = root.querySelectorAll('.gr-tab');
      var panels = root.querySelectorAll('.gr-panel');
      Array.prototype.forEach.call(tabs, function (tb) {
        tb.onclick = function () {
          var id = tb.getAttribute('data-tab');
          Array.prototype.forEach.call(tabs, function (x) { x.classList.toggle('btn-primary', x === tb); });
          Array.prototype.forEach.call(panels, function (p) { p.style.display = (p.getAttribute('data-panel') === id) ? '' : 'none'; });
        };
      });

      /* ---- 1) Radar ---- */
      var radGo = root.querySelector('#gr_rad_go'), radOut = root.querySelector('#gr_rad_out');
      function runRadar() {
        var kw = (root.querySelector('#gr_rad_kw').value || '').trim();
        var biz = (root.querySelector('#gr_rad_biz').value || '').trim();
        if (!kw) { ui.toast('ใส่หัวข้อ/คีย์เวิร์ดก่อน'); return; }
        if (!reachable()) return;
        busy(radGo, true);
        radOut.innerHTML = '<div class="hint">⏳ ค้น Google หาหน้าชุมชนที่ติดหน้า 1… (10–20 วิ)</div>';
        RP.api.socialRadar({ keyword: kw, business: biz }).then(function (d) {
          if (!d.threads || !d.threads.length) { radOut.innerHTML = ui.card({ body: RP.noData('ไม่พบหน้าชุมชนหน้า 1', 'ลองหัวข้อกว้างขึ้น หรือคำถามภาษาอังกฤษ (Reddit/Quora ส่วนใหญ่อังกฤษ)') }); return; }
          renderRadar(radOut, d, biz);
        }).catch(function (e) {
          radOut.innerHTML = ui.card({ body: RP.noData('ดึงไม่ได้', esc(e.message || String(e))) });
        }).then(function () { busy(radGo, false, '🔎 สแกน Reddit/Quora/Medium'); });
      }
      if (radGo) radGo.onclick = runRadar;
      ['gr_rad_kw', 'gr_rad_biz'].forEach(function (id) {
        var el = root.querySelector('#' + id); if (el) el.addEventListener('keydown', function (e) { if (e.key === 'Enter') runRadar(); });
      });

      /* ---- 2) Content Gap ---- */
      var gapGo = root.querySelector('#gr_gap_go'), gapOut = root.querySelector('#gr_gap_out');
      function runGap() {
        var dom = (root.querySelector('#gr_gap_dom').value || '').trim();
        var comps = lines(root.querySelector('#gr_gap_comp').value);
        if (!dom) { ui.toast('ใส่โดเมนเราก่อน'); return; }
        if (!comps.length) { ui.toast('ใส่โดเมนคู่แข่งอย่างน้อย 1'); return; }
        if (!reachable()) return;
        busy(gapGo, true);
        gapOut.innerHTML = '<div class="hint">⏳ ดึงคีย์ที่คู่แข่งติดอันดับ + ลบที่เราติดแล้ว… (10–30 วิ)</div>';
        RP.api.contentGaps({ domain: dom, competitors: comps }).then(function (d) {
          if (!d.gaps || !d.gaps.length) { gapOut.innerHTML = ui.card({ body: RP.noData('ไม่พบช่องว่าง', 'อาจแปลว่าเราติดคีย์เหล่านั้นแล้ว หรือคู่แข่งยังไม่ติดหน้า 1-2 · ลองคู่แข่งรายอื่น') }); return; }
          renderGaps(gapOut, d);
        }).catch(function (e) {
          showKeyError(gapOut, e, 'gap');
        }).then(function () { busy(gapGo, false, '🎯 หาช่องว่างคอนเทนต์'); });
      }
      if (gapGo) gapGo.onclick = runGap;

      /* ---- 3) Featured Snippet ---- */
      var snGo = root.querySelector('#gr_sn_go'), snOut = root.querySelector('#gr_sn_out');
      function runSnippet() {
        var kws = lines(root.querySelector('#gr_sn_kw').value);
        if (!kws.length) { ui.toast('ใส่คีย์เวิร์ดอย่างน้อย 1 คำ'); return; }
        if (!reachable()) return;
        busy(snGo, true);
        snOut.innerHTML = '<div class="hint">⏳ ยิง SERP จริงดู Featured Snippet + People-Also-Ask… (10–30 วิ)</div>';
        RP.api.snippetOpportunities({ keywords: kws }).then(function (d) {
          if (!d.opportunities || !d.opportunities.length) { snOut.innerHTML = ui.card({ body: RP.noData('ไม่มีผล', 'ลองคีย์อื่น หรือเช็กเครดิต DataForSEO') }); return; }
          renderSnippets(snOut, d);
        }).catch(function (e) {
          showKeyError(snOut, e, 'snippet');
        }).then(function () { busy(snGo, false, '🥇 ตรวจ Featured Snippet + PAA'); });
      }
      if (snGo) snGo.onclick = runSnippet;

      /* ---- 4) Competitor Backlink ---- */
      var blGo = root.querySelector('#gr_bl_go'), blOut = root.querySelector('#gr_bl_out');
      function runBacklink() {
        var comps = lines(root.querySelector('#gr_bl_comp').value);
        var dom = (root.querySelector('#gr_bl_dom').value || '').trim();
        if (!comps.length) { ui.toast('ใส่โดเมนคู่แข่งอย่างน้อย 1'); return; }
        if (!reachable()) return;
        busy(blGo, true);
        blOut.innerHTML = '<div class="hint">⏳ ขุด referring domains ของคู่แข่ง (DataForSEO Backlinks)… (10–40 วิ)</div>';
        RP.api.backlinkGaps({ competitors: comps, domain: dom }).then(function (d) {
          if (!d.opportunities || !d.opportunities.length) { blOut.innerHTML = ui.card({ body: RP.noData('ไม่พบแหล่งร่วม', 'คู่แข่งอาจยังไม่มี backlink ร่วมกัน · ลองคู่แข่งที่โดเมนแรงขึ้น หรือเช็กสิทธิ์ Backlinks API') }); return; }
          renderBacklinks(blOut, d);
        }).catch(function (e) {
          showKeyError(blOut, e, 'backlink');
        }).then(function () { busy(blGo, false, '🔗 ขุดแหล่งขอลิงก์'); });
      }
      if (blGo) blGo.onclick = runBacklink;

      /* ---- 5) AI-Citation Audit (ต้องเลือกโปรเจ็ค db) ---- */
      var ciNew = root.querySelector('#gr_ci_new');
      if (ciNew) ciNew.onclick = function () { RP.go('projects'); };
      var ciGo = root.querySelector('#gr_ci_go'), ciOut = root.querySelector('#gr_ci_out');
      if (ciGo) ciGo.onclick = function () {
        var sel = root.querySelector('#gr_ci_proj');
        var pid = dbId(sel && sel.value);
        if (!(pid && RP.api && RP.api.enabled())) { ui.toast('เปิดโหมด Live + เลือกโปรเจ็คจริงก่อน'); return; }
        busy(ciGo, true);
        ciOut.innerHTML = '<div class="hint">⏳ สุ่มถาม AI จริงหลายเอนจิน + ดึงแหล่งอ้างอิง SERP… (20–60 วิ)</div>';
        RP.api.aiCitationAudit(pid).then(function (d) {
          renderCitation(ciOut, d);
        }).catch(function (e) {
          ciOut.innerHTML = ui.card({ body: RP.noData('วัดไม่ได้', esc(e.message || String(e))) });
        }).then(function () { busy(ciGo, false, '🧭 วัด AI-Citation'); });
      };
    } };
  };
})(window.RP);