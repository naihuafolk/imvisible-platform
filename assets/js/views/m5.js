/* ============================================================
   View: M5 — AI Visibility & Rank Tracker (แดชบอร์ดวัดผล)
   ฝั่ง SEO: อันดับ Google + Search Console
   ฝั่ง AEO: Prompt Sampling วัด AI Citation + Share of Voice
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt, d = RP.data.m5;

  function seoKpis() {
    var s = d.seo;
    return '<div class="grid grid-4 mb">' +
      ui.kpi({ label: 'คีย์เวิร์ดที่ติดตาม', value: fmt.n(s.keywordsTracked), foot: 'ผ่าน SERP API รายวัน' }) +
      ui.kpi({ label: 'ติดหน้า 1 Google', value: fmt.n(s.page1), tone: 'brand',
        foot: '<span class="trend-up">▲ +' + (s.page1 - s.page1Prev) + '</span> จากเดือนก่อน' }) +
      ui.kpi({ label: 'ติด Top 3', value: fmt.n(s.top3), tone: 'pos', foot: 'ตำแหน่งทองของ SERP' }) +
      ui.kpi({ label: 'อันดับเฉลี่ย', value: s.avgPosition.toFixed(1), tone: 'brand',
        foot: '<span class="trend-up">▲ ดีขึ้น ' + (s.avgPositionPrev - s.avgPosition).toFixed(1) + '</span>' }) +
      '</div>';
  }

  function seoCard() {
    var s = d.seo;
    var clicksNow = s.clicks90[s.clicks90.length - 1];
    var impNow = s.impressions90[s.impressions90.length - 1];
    return ui.card({
      title: 'ฝั่ง SEO — Google Search Console (90 วัน)', sub: 'คลิก & การมองเห็น',
      body:
        '<div class="row between wrap mb"><div><div class="soft small">คลิกรวม 90 วัน</div>' +
        '<div class="bb" style="font-size:26px;color:var(--brand-700)">' + fmt.n(clicksNow) + '</div></div>' +
        ui.spark(s.clicks90, { w: 220, h: 56, color: 'var(--brand-600)' }) + '</div>' +
        '<div class="divider"></div>' +
        '<div class="row between wrap"><div><div class="soft small">Impressions (พันครั้ง)</div>' +
        '<div class="bb" style="font-size:22px">' + fmt.n(impNow) + 'K</div></div>' +
        ui.spark(s.impressions90, { w: 220, h: 56, color: '#17b978' }) + '</div>'
    });
  }

  function citationCard() {
    var c = RP.data.m5.citation;
    return ui.card({
      title: 'ฝั่ง AEO — AI Citation Share of Voice', sub: 'สัดส่วนที่ AI หยิบเราไปอ้างอิง',
      body:
        '<div class="row" style="gap:22px;align-items:center">' +
        '<div class="ring" style="--p:' + c.sov + '"><span class="ring-val">' + c.sov + '%</span></div>' +
        '<div style="flex:1">' +
        '<div class="soft small">แนวโน้ม Citation SoV (10 สัปดาห์)</div>' +
        ui.spark(c.sovTrend, { w: 260, h: 56, color: 'var(--purple-600)' }) +
        '<div class="small" style="margin-top:6px"><span class="trend up">▲ ' + (c.sov - c.sovPrev) + '%</span> จากเดือนก่อน · เป้าหมาย 15–25%</div>' +
        '</div></div>'
    });
  }

  function enginesCard() {
    var c = RP.data.m5.citation;
    var rows = c.engines.map(function (e) {
      return '<div class="list-row"><div style="width:96px" class="b">' + esc(e.name) + '</div>' +
        '<div class="grow"><div class="bar" style="display:flex;height:20px;border-radius:8px;overflow:hidden;background:var(--bg)">' +
        '<span style="width:' + e.us + '%;background:var(--brand-600)" title="เรา ' + e.us + '%"></span>' +
        '<span style="width:' + e.comp + '%;background:#f59e0b" title="คู่แข่ง ' + e.comp + '%"></span>' +
        '<span style="width:' + e.none + '%;background:var(--border)" title="ไม่มีใคร ' + e.none + '%"></span>' +
        '</div></div>' +
        '<div class="bb" style="width:44px;text-align:right;color:var(--brand-700)">' + e.us + '%</div></div>';
    }).join('');
    return ui.card({
      title: 'การมองเห็นแยกตาม AI Engine', sub: 'เรา vs คู่แข่ง vs ไม่มีใครถูกอ้าง',
      body: rows +
        '<div class="chart-legend" style="margin-top:10px">' +
        '<span><i style="background:var(--brand-600)"></i> เรา (ABC)</span>' +
        '<span><i style="background:#f59e0b"></i> คู่แข่ง</span>' +
        '<span><i style="background:var(--border)"></i> ไม่มีใครถูกอ้าง</span></div>'
    });
  }

  function competitorCard() {
    var c = RP.data.m5.citation;
    var max = Math.max.apply(null, c.competitors.map(function (x) { return x.sov; }));
    var rows = c.competitors.map(function (x) {
      return '<div class="list-row"><div class="grow"><div class="t small">' +
        (x.us ? '<span style="color:var(--brand-700)">★ </span>' : '') + esc(x.name) + '</div>' +
        '<div class="bar ' + (x.us ? '' : 'green') + '"><span style="width:' + (x.sov / max * 100) + '%"></span></div></div>' +
        '<div class="bb" style="width:40px;text-align:right">' + x.sov + '%</div></div>';
    }).join('');
    return ui.card({ title: 'Share of Voice เทียบคู่แข่ง', sub: 'ใครถูก AI อ้างอิงมากที่สุดในหมวดนี้', body: rows });
  }

  function promptCard() {
    var check = function (ok) { return ok ? '<span style="color:var(--green-600);font-weight:800">✓</span>' : '<span class="soft">—</span>'; };
    var rows = d.prompts.map(function (p) {
      var cited = p.chatgpt || p.gemini || p.perplexity;
      return '<tr>' +
        '<td class="tbl-title">' + esc(p.q) + '</td>' +
        '<td class="center">' + check(p.chatgpt) + '</td>' +
        '<td class="center">' + check(p.gemini) + '</td>' +
        '<td class="center">' + check(p.perplexity) + '</td>' +
        '<td class="center">' + (p.pos ? '<span class="badge green">อันดับอ้างอิง ' + p.pos + '</span>' : '<span class="badge">ยังไม่ถูกอ้าง</span>') + '</td>' +
        '</tr>';
    }).join('');
    var citedCount = d.prompts.filter(function (p) { return p.chatgpt || p.gemini || p.perplexity; }).length;
    return ui.card({
      title: 'Prompt Sampling — วัด AI Citation', sub: 'ยิงชุดคำถามเป้าหมายไปที่ AI แล้ววัดว่าถูกอ้างอิงไหม',
      flush: true,
      action: '<span class="badge blue">ถูกอ้าง ' + citedCount + '/' + d.prompts.length + ' คำถาม</span>',
      body: '<div class="tbl-wrap"><table class="tbl">' +
        '<thead><tr><th>คำถามเป้าหมาย</th><th class="center">ChatGPT</th><th class="center">Gemini</th><th class="center">Perplexity</th><th class="center">สถานะ</th></tr></thead>' +
        '<tbody>' + rows + '</tbody></table></div>'
    });
  }

  function curProj() { return RP.data.project.list.filter(function (x) { return x.id === RP.data.project.current; })[0]; }

  function liveTools() {
    var p = curProj();
    return ui.card({
      title: 'โหมด Live — ดึงข้อมูลจริงจาก backend', sub: 'ใช้โดเมน/แบรนด์ของโปรเจ็คปัจจุบัน: ' + esc(p.domain), cls: 'mb',
      action: RP.api.enabled() ? ui.badge('● Live เปิด', 'green') : ui.badge('Live ปิด', 'amber'),
      body:
        '<div class="row wrap" style="gap:10px">' +
        '<div class="field" style="flex:1;min-width:240px"><span class="ico">🔎</span><input id="m5_kw" placeholder="พิมพ์คีย์เวิร์ดเพื่อตรวจอันดับ Google จริง เช่น ครีมกันแดด ยี่ห้อไหนดี"></div>' +
        '<button class="btn btn-primary" id="m5_rank">ตรวจอันดับ Google สด</button>' +
        '<button class="btn" id="m5_gsc">ดึง Search Console สด</button>' +
        '<button class="btn" id="m5_cite">รัน Prompt Sampling สด</button></div>' +
        '<div class="hint" style="margin-top:10px">ปุ่มเหล่านี้ยิงไปที่ backend จริง (SERP / GSC / AI) — ต้องเปิดโหมด Live + รัน backend + ตั้งคีย์ API ก่อน มิฉะนั้นจะแจ้งให้ไปตั้งค่า</div>'
    });
  }

  function rankModal(res) {
    var rows = (res.top10 || []).map(function (r) {
      return '<tr><td class="num">#' + r.rank + '</td><td><div class="tbl-title">' + esc(r.title || '') + '</div>' +
        '<div class="tbl-sub">' + esc(r.domain || '') + '</div></td><td class="soft small">' + esc(r.url || '') + '</td></tr>';
    }).join('');
    var banner = res.on_page1
      ? '<div class="verify-banner mb"><span class="big">✅</span><div><div class="t">อยู่หน้า 1 Google จริง — อันดับ ' + res.our_rank + '</div><div class="s">โดเมน: ' + esc(res.domain) + ' · คีย์เวิร์ด: ' + esc(res.keyword) + '</div></div></div>'
      : '<div class="warn-box mb">ยังไม่ติดหน้า 1 สำหรับ "' + esc(res.keyword) + '" (อันดับปัจจุบัน: ' + (res.our_rank || 'ไม่พบใน 100 อันดับ') + ')</div>';
    ui.modal({ title: 'ผลตรวจอันดับจริง (DataForSEO)', sub: esc(res.keyword), width: 860,
      body: banner + '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>อันดับ</th><th>หน้า / โดเมน</th><th>URL</th></tr></thead><tbody>' + rows + '</tbody></table></div>' });
  }

  function gscModal(res) {
    var rows = (res.top_queries || []).map(function (q) {
      return '<tr><td class="tbl-title">' + esc(q.query) + '</td><td class="num">' + fmt.n(q.clicks) + '</td><td class="num">' + fmt.n(q.impressions) + '</td><td class="num">' + q.ctr + '%</td><td class="num">' + q.position + '</td></tr>';
    }).join('');
    ui.modal({ title: 'Google Search Console (ข้อมูลจริง)', sub: esc(res.site_url) + ' · ' + res.period_days + ' วัน', width: 820,
      body: '<div class="grid grid-3 mb">' +
        ui.kpi({ label: 'คลิกรวม', value: fmt.n(res.clicks), tone: 'brand' }) +
        ui.kpi({ label: 'Impressions', value: fmt.n(res.impressions) }) +
        ui.kpi({ label: 'อันดับเฉลี่ย', value: res.avg_position == null ? '—' : res.avg_position }) + '</div>' +
        '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>คำค้น</th><th>คลิก</th><th>Impr.</th><th>CTR</th><th>อันดับ</th></tr></thead><tbody>' + rows + '</tbody></table></div>' });
  }

  function citeModal(res) {
    var eng = res.per_engine || {};
    var rows = Object.keys(eng).map(function (k) {
      var e = eng[k];
      return '<tr><td class="bb">' + esc(k) + '</td><td class="num">' + e.answered + '</td><td class="num">' + e.cited + '</td><td>' + (e.sov_percent == null ? '<span class="soft">—</span>' : ui.badge(e.sov_percent + '%', 'green')) + '</td></tr>';
    }).join('');
    ui.modal({ title: 'Prompt Sampling — AI Citation (ข้อมูลจริง)', sub: 'Share of Voice รวม: ' + (res.overall_sov_percent == null ? '—' : res.overall_sov_percent + '%'), width: 720,
      body: '<div class="note-box mb">' + esc(res.note || '') + '</div>' +
        '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>เอนจิน</th><th>ตอบ</th><th>อ้างอิงเรา</th><th>SoV</th></tr></thead><tbody>' + rows + '</tbody></table></div>' });
  }

  RP.views.m5 = function () {
    var html =
      ui.pageHead({ eyebrow: 'M5 · AI Visibility & Rank Tracker', title: 'วัดผล & Rank Tracker',
        desc: 'วัดผลทั้ง 2 ฝั่งในที่เดียว — ฝั่ง <b>SEO</b> ติดตามอันดับ Google รายวันและทราฟฟิกจาก Search Console · ฝั่ง <b>AEO</b> ใช้ Prompt Sampling ยิงคำถามไปที่ ChatGPT / Gemini / Perplexity เพื่อวัดว่าแบรนด์เราถูกอ้างอิงกี่เปอร์เซ็นต์ (Share of Voice)' }) +
      liveTools() +
      seoKpis() +
      '<div class="grid grid-2 mb">' + seoCard() + citationCard() + '</div>' +
      '<div class="grid grid-2 mb">' + enginesCard() + competitorCard() + '</div>' +
      promptCard() +
      '<div class="hint" style="margin-top:14px">📌 ข้อควรรู้: การวัด AI Citation ไม่มี API ทางการ ผลจึงเป็น "ค่าประมาณเชิงสถิติ" จากการสุ่มยิงคำถาม — คำตอบ AI เปลี่ยนได้ตามผู้ใช้/เวลา (ดูหน้าความเสี่ยงในรายงาน)</div>';

    return {
      html: html,
      mount: function (root) {
        var p = curProj();
        var rk = root.querySelector('#m5_rank');
        if (rk) rk.onclick = function () {
          var kw = (root.querySelector('#m5_kw').value || '').trim();
          if (!kw) { RP.ui.toast('พิมพ์คีย์เวิร์ดก่อนครับ'); return; }
          RP.live(RP.api.rankCheck(kw, p.domain), rankModal);
        };
        var gs = root.querySelector('#m5_gsc');
        if (gs) gs.onclick = function () { RP.live(RP.api.gsc('sc-domain:' + p.domain), gscModal); };
        var ct = root.querySelector('#m5_cite');
        if (ct) ct.onclick = function () {
          var qs = RP.data.m5.prompts.map(function (x) { return x.q; });
          RP.live(RP.api.citation(qs, p.brandTerms || [], p.domain), citeModal);
        };
      }
    };
  };

})(window.RP);
