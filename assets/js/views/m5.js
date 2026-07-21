/* ============================================================
   View: M5 — AI Visibility & Rank Tracker (แดชบอร์ดวัดผล)
   ฝั่ง SEO: อันดับ Google + Search Console
   ฝั่ง AEO: Prompt Sampling วัด AI Citation + Share of Voice
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt, d = RP.data.m5;

  /* KPI อันดับ 'ของจริง' จากประวัติ RankSnapshot (beat เก็บรายวัน) */
  function realSeoKpis(h) {
    var trend = (h.page1_trend && h.page1_trend.length > 1)
      ? ui.spark(h.page1_trend, { w: 96, h: 22, color: 'var(--brand-600)' }) : 'เก็บรายวัน';
    return '<div class="grid grid-4 mb">' +
      ui.kpi({ label: 'คีย์เวิร์ดที่ติดตาม', value: fmt.n(h.keywords_tracked), foot: 'จาก SERP API จริง' }) +
      ui.kpi({ label: 'ติดหน้า 1 Google', value: fmt.n(h.page1), tone: 'brand', foot: trend }) +
      ui.kpi({ label: 'ติด Top 3', value: fmt.n(h.top3), tone: 'pos', foot: 'ตำแหน่งทองของ SERP' }) +
      ui.kpi({ label: 'อันดับเฉลี่ย', value: h.avg_position == null ? '—' : Number(h.avg_position).toFixed(1),
        tone: 'brand', foot: 'อันดับจริงเฉลี่ย' }) +
      '</div>';
  }

  function seoKpis() {
    var s = d.seo;
    var sample = '<div class="grid grid-4 mb">' +
      ui.kpi({ label: 'คีย์เวิร์ดที่ติดตาม', value: fmt.n(s.keywordsTracked), foot: 'ผ่าน SERP API รายวัน' }) +
      ui.kpi({ label: 'ติดหน้า 1 Google', value: fmt.n(s.page1), tone: 'brand',
        foot: '<span class="trend-up">▲ +' + (s.page1 - s.page1Prev) + '</span> จากเดือนก่อน' }) +
      ui.kpi({ label: 'ติด Top 3', value: fmt.n(s.top3), tone: 'pos', foot: 'ตำแหน่งทองของ SERP' }) +
      ui.kpi({ label: 'อันดับเฉลี่ย', value: s.avgPosition.toFixed(1), tone: 'brand',
        foot: '<span class="trend-up">▲ ดีขึ้น ' + (s.avgPositionPrev - s.avgPosition).toFixed(1) + '</span>' }) +
      '</div>';
    return '<div id="seo_kpi_slot">' + RP.realOr(sample, {
      title: 'ยังไม่มีข้อมูลอันดับ',
      hint: 'เรายังไม่ได้เก็บอันดับของโปรเจ็คนี้ ระบบจะแสดงอันดับจริงหลังเก็บข้อมูลต่อเนื่อง 1–7 วัน หรือกด "ตรวจอันดับ Google สด" ด้านบนเพื่อดูผลจริงทันทีทีละคีย์เวิร์ด'
    }) + '</div>';
  }

  function seoCard() {
    var s = d.seo;
    var clicksNow = s.clicks90[s.clicks90.length - 1];
    var impNow = s.impressions90[s.impressions90.length - 1];
    var sample =
      '<div class="row between wrap mb"><div><div class="soft small">คลิกรวม 90 วัน</div>' +
      '<div class="bb" style="font-size:26px;color:var(--brand-700)">' + fmt.n(clicksNow) + '</div></div>' +
      ui.spark(s.clicks90, { w: 220, h: 56, color: 'var(--brand-600)' }) + '</div>' +
      '<div class="divider"></div>' +
      '<div class="row between wrap"><div><div class="soft small">Impressions (พันครั้ง)</div>' +
      '<div class="bb" style="font-size:22px">' + fmt.n(impNow) + 'K</div></div>' +
      ui.spark(s.impressions90, { w: 220, h: 56, color: '#17b978' }) + '</div>';
    return ui.card({
      title: RP.isReal()
        ? 'ฝั่ง SEO — Google Search Console'
        : 'ฝั่ง SEO — Google Search Console (90 วัน)',
      sub: RP.isReal() ? 'ต้องเชื่อมต่อ Search Console ก่อน' : 'คลิก & การมองเห็น',
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'),
      body: RP.realOr(sample, {
        title: 'ยังไม่มีข้อมูลจาก Search Console',
        hint: 'กราฟนี้จะแสดงเฉพาะตัวเลขที่ดึงจากบัญชี Google Search Console ของคุณจริง ๆ เท่านั้น — เชื่อมต่อ GSC ในหน้าตั้งค่า แล้วกดปุ่ม "ดึง Search Console สด" ด้านบน'
      })
    });
  }

  /* กราฟแนวโน้ม SoV 'ของจริง' — สร้างจากประวัติที่บันทึกไว้ (GET .../citation/history)
     นี่คือสิ่งที่ทำให้คำสัญญา "รันแล้วจะสะสมเป็นแนวโน้ม" เป็นจริง (ไม่ใช่ตัวเลขสมมติ) */
  function realTrendBody(h) {
    var sov = h.latest_sov;
    var trend = (h.trend && h.trend.length) ? h.trend : (sov == null ? [] : [sov]);
    var deltaHtml = '';
    if (sov != null && h.prev_sov != null) {
      var dv = Math.round((sov - h.prev_sov) * 10) / 10;
      var cls = dv > 0 ? 'up' : (dv < 0 ? 'down' : '');
      var arw = dv > 0 ? '▲ +' : (dv < 0 ? '▼ ' : '• ');
      deltaHtml = '<span class="trend ' + cls + '">' + arw + dv + '%</span> จากรอบก่อน · ';
    }
    return '<div class="row" style="gap:22px;align-items:center">' +
      '<div class="ring" style="--p:' + (sov == null ? 0 : sov) + '"><span class="ring-val">' +
      (sov == null ? '—' : sov + '%') + '</span></div>' +
      '<div style="flex:1">' +
      '<div class="soft small">แนวโน้ม Citation SoV (จาก ' + h.count + ' รอบที่สุ่มถามจริง)</div>' +
      ui.spark(trend, { w: 260, h: 56, color: 'var(--purple-600)' }) +
      '<div class="small" style="margin-top:6px">' + deltaHtml + 'เป้าหมาย 15–25%</div>' +
      '</div></div>' +
      '<div class="hint" style="margin-top:10px">' + esc(h.note || '') + '</div>';
  }

  function citationCard() {
    var c = RP.data.m5.citation;
    var sample =
      '<div class="row" style="gap:22px;align-items:center">' +
      '<div class="ring" style="--p:' + c.sov + '"><span class="ring-val">' + c.sov + '%</span></div>' +
      '<div style="flex:1">' +
      '<div class="soft small">แนวโน้ม Citation SoV (10 สัปดาห์)</div>' +
      ui.spark(c.sovTrend, { w: 260, h: 56, color: 'var(--purple-600)' }) +
      '<div class="small" style="margin-top:6px"><span class="trend up">▲ ' + (c.sov - c.sovPrev) + '%</span> จากเดือนก่อน · เป้าหมาย 15–25%</div>' +
      '</div></div>';
    return ui.card({
      title: 'ฝั่ง AEO — AI Citation Share of Voice', sub: 'สัดส่วนที่ AI หยิบเราไปอ้างอิง',
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'),
      // ห่อด้วย slot เพื่อให้ตอน mount เติม "แนวโน้มจริง" ทับได้ถ้ามีประวัติสะสมแล้ว
      body: '<div id="cite_trend_slot">' + RP.realOr(sample, {
        title: 'ยังไม่มีค่า Share of Voice',
        hint: 'SoV คำนวณจากผลการรัน Prompt Sampling จริงหลายรอบ — รันชุดคำถามด้วยปุ่ม "รัน Prompt Sampling สด" ด้านบนอย่างน้อย 1 ครั้ง แล้วค่าจะเริ่มสะสมเป็นแนวโน้ม'
      }) + '</div>'
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
    var sample = rows +
      '<div class="chart-legend" style="margin-top:10px">' +
      '<span><i style="background:var(--brand-600)"></i> เรา (ABC)</span>' +
      '<span><i style="background:#f59e0b"></i> คู่แข่ง</span>' +
      '<span><i style="background:var(--border)"></i> ไม่มีใครถูกอ้าง</span></div>';
    return ui.card({
      title: 'การมองเห็นแยกตาม AI Engine', sub: 'เรา vs คู่แข่ง vs ไม่มีใครถูกอ้าง',
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'),
      body: RP.realOr(sample, {
        title: 'ยังไม่มีผลแยกตาม AI Engine',
        hint: 'ตัวเลขแยก ChatGPT / Gemini / Perplexity จะขึ้นหลังรัน Prompt Sampling จริงกับโปรเจ็คนี้ — เราจะไม่เดาสัดส่วนให้'
      })
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
    return ui.card({
      title: 'Share of Voice เทียบคู่แข่ง', sub: 'ใครถูก AI อ้างอิงมากที่สุดในหมวดนี้',
      action: RP.sampleBadge('ข้อมูลตัวอย่าง'),
      body: RP.realOr(rows, {
        title: 'ยังไม่มีข้อมูลเทียบคู่แข่ง',
        hint: 'ต้องตั้งรายชื่อคู่แข่งในหน้าตั้งค่าโปรเจ็ค แล้วรัน Prompt Sampling จริง ระบบจึงจะนับได้ว่าใครถูก AI อ้างอิงมากกว่ากัน'
      })
    });
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
    var sample = '<div class="tbl-wrap"><table class="tbl">' +
      '<thead><tr><th>คำถามเป้าหมาย</th><th class="center">ChatGPT</th><th class="center">Gemini</th><th class="center">Perplexity</th><th class="center">สถานะ</th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>';
    return ui.card({
      title: 'Prompt Sampling — วัด AI Citation', sub: 'ยิงชุดคำถามเป้าหมายไปที่ AI แล้ววัดว่าถูกอ้างอิงไหม',
      flush: true,
      action: RP.isReal()
        ? RP.sampleBadge('')
        : '<span class="badge blue">ถูกอ้าง ' + citedCount + '/' + d.prompts.length + ' คำถาม</span> ' + RP.sampleBadge('ข้อมูลตัวอย่าง'),
      body: RP.realOr(sample, {
        title: 'ยังไม่มีผล Prompt Sampling',
        hint: 'ตารางนี้จะแสดงเฉพาะผลที่ยิงคำถามไปที่ AI จริงเท่านั้น — ใส่ชุดคำถามในกล่องด้านบน แล้วกด "รัน Prompt Sampling สด" ผลแต่ละเอนจินจะขึ้นทันทีหลังรันเสร็จ'
      })
    });
  }

  /* หาโปรเจ็คปัจจุบันแบบปลอดภัย — บัญชีจริงอาจยังไม่มีโปรเจ็คเลย (list = [])
     ห้ามคืนโปรเจ็คตัวอย่างให้บัญชีจริงเด็ดขาด เพราะจะกลายเป็นการตรวจโดเมนของคนอื่น */
  function curProj() {
    var proj = RP.data && RP.data.project;
    var list = (proj && proj.list) || [];
    // บัญชีจริง: กรองเหลือเฉพาะโปรเจ็คจากฐานข้อมูล (id ขึ้นต้น db) — กันเครื่องมือสด (ตรวจอันดับ/
    // GSC/Prompt Sampling) ยิงไปที่โดเมนของโปรเจ็คตัวอย่าง (โดเมนคนอื่น) โดยเด็ดขาด
    if (RP.isReal()) list = list.filter(function (p) { return p && /^db/.test(String(p.id)); });
    var cur = (proj && proj.current) || '';
    var i;
    for (i = 0; i < list.length; i++) {
      if (list[i] && list[i].id === cur) return list[i];
    }
    return list.length ? list[0] : null;
  }

  /* คำแบรนด์ที่ใช้ตรวจว่า AI อ้างถึงเราไหม
     โปรเจ็คจริงมักมี brandTerms = [] → fallback เป็นชื่อโปรเจ็ค + โดเมน (ไม่งั้นผลจะเป็น 0 เสมอ) */
  function brandTermsOf(p) {
    var out = [];
    var i, t;
    var src = (p && p.brandTerms) || [];
    for (i = 0; i < src.length; i++) {
      t = String(src[i] || '').trim();
      if (t) out.push(t);
    }
    if (out.length) return out;
    if (p && p.name) out.push(String(p.name).trim());
    if (p && p.domain) {
      out.push(String(p.domain).trim());
      // ชื่อแบรนด์คร่าว ๆ จากโดเมน เช่น abc-beautyclinic.com → abc-beautyclinic
      t = String(p.domain).replace(/^www\./, '').split('.')[0];
      if (t && out.indexOf(t) < 0) out.push(t);
    }
    return out.filter(function (x) { return !!x; });
  }

  function noProjectTools() {
    return ui.card({
      title: 'โหมด Live — ดึงข้อมูลจริงจาก backend',
      sub: 'ยังไม่มีโปรเจ็คให้ตรวจ', cls: 'mb',
      action: RP.api.enabled() ? ui.badge('● Live เปิด', 'green') : ui.badge('Live ปิด', 'amber'),
      body: RP.noData(
        'ยังไม่มีโปรเจ็ค',
        'สร้างโปรเจ็คก่อนถึงจะตรวจได้ — เครื่องมือ Live (ตรวจอันดับ Google / ดึง Search Console / รัน Prompt Sampling) ต้องผูกกับโดเมนของคุณเอง เราจะไม่ตรวจโดเมนที่คุณไม่ได้เป็นเจ้าของ',
        '<button class="btn btn-primary" id="m5_newproj">+ สร้างโปรเจ็ค</button>'
      )
    });
  }

  function liveTools() {
    var p = curProj();
    if (!p) return noProjectTools();
    var noBrand = !((p && p.brandTerms) || []).length;
    var sampleQs = RP.isReal() ? '' : RP.data.m5.prompts.map(function (x) { return x.q; }).join('\n');
    var dom = String((p && p.domain) || '').trim();
    return ui.card({
      title: 'โหมด Live — ดึงข้อมูลจริงจาก backend',
      sub: dom ? ('ใช้โดเมน/แบรนด์ของโปรเจ็คปัจจุบัน: ' + esc(dom)) : 'โปรเจ็คนี้ยังไม่ได้ตั้งโดเมน',
      cls: 'mb',
      action: RP.api.enabled() ? ui.badge('● Live เปิด', 'green') : ui.badge('Live ปิด', 'amber'),
      body:
        (dom ? '' : '<div class="warn-box mb">⚠️ โปรเจ็คนี้ยังไม่ได้ตั้งโดเมน — ตั้งโดเมนในหน้าตั้งค่าโปรเจ็คก่อน ระบบจึงจะตรวจอันดับ/GSC ให้ได้</div>') +
        '<div class="row wrap" style="gap:10px">' +
        '<div class="field" style="flex:1;min-width:240px"><span class="ico">🔎</span><input id="m5_kw" placeholder="พิมพ์คีย์เวิร์ดเพื่อตรวจอันดับ Google จริง เช่น ครีมกันแดด ยี่ห้อไหนดี"></div>' +
        '<button class="btn btn-primary" id="m5_rank"' + (dom ? '' : ' disabled') + '>ตรวจอันดับ Google สด</button>' +
        '<button class="btn" id="m5_gsc"' + (dom ? '' : ' disabled') + '>ดึง Search Console สด</button></div>' +
        '<div style="margin-top:12px"><div class="soft small" style="margin-bottom:5px">ชุดคำถามสำหรับ Prompt Sampling (บรรทัดละ 1 คำถาม)</div>' +
        '<textarea id="m5_qs" rows="4" style="width:100%" placeholder="เช่น&#10;ครีมกันแดดหน้าไม่วอก แนะนำ&#10;คลินิกเลเซอร์หน้าใส ที่ไหนดี">' + esc(sampleQs) + '</textarea>' +
        '<div class="row wrap" style="gap:10px;margin-top:8px"><button class="btn" id="m5_cite"' + (dom ? '' : ' disabled') + '>รัน Prompt Sampling สด</button>' +
        '<span class="soft small" style="align-self:center">คำแบรนด์ที่ใช้ตรวจ: ' + esc(brandTermsOf(p).join(', ') || '—') + '</span></div></div>' +
        (noBrand ? '<div class="warn-box" style="margin-top:10px">⚠️ โปรเจ็คนี้ยังไม่ได้ตั้ง "คำแบรนด์" — ระบบจะใช้ชื่อโปรเจ็คและโดเมนแทนชั่วคราว แนะนำให้ไปตั้งคำแบรนด์จริง (รวมชื่อภาษาไทย/ชื่อเล่นของแบรนด์) ที่หน้าตั้งค่า เพื่อให้ผลการตรวจแม่นขึ้น</div>' : '') +
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
      RP.sampleNotice('หน้าวัดผล & Rank Tracker นี้') +
      (curProj() ? RP.collectingNotice('อันดับ Google และ AI Citation ของโปรเจ็คนี้') : '') +
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
        var np = root.querySelector('#m5_newproj');
        if (np) np.onclick = function () { RP.go('projects'); };

        /* id โปรเจ็คในระบบ = ตัวเลข (เก็บใน _dbid) แต่ id ใน view เป็น 'db{n}' — ต้องแปลงก่อนยิง API */
        function dbId(pp) {
          if (!pp) return null;
          if (typeof pp._dbid === 'number') return pp._dbid;
          var m = /^db(\d+)$/.exec(String(pp.id || ''));
          return m ? parseInt(m[1], 10) : null;
        }
        var realPid = RP.isReal() ? dbId(p) : null;

        /* บัญชีจริง: ดึง "แนวโน้ม SoV ที่สะสมไว้จริง" มาเติมทับกล่อง "ยังไม่มีข้อมูล"
           → คำสัญญา "รันแล้วจะสะสมเป็นแนวโน้ม" กลายเป็นของจริงที่ตรวจสอบได้ */
        function refreshCiteTrend() {
          if (!realPid || !RP.api.enabled()) return;
          var slot = root.querySelector('#cite_trend_slot');
          if (!slot) return;
          RP.api.citationHistory(realPid).then(function (h) {
            if (h && h.count && (h.latest_sov != null || (h.trend && h.trend.length))) {
              slot.innerHTML = realTrendBody(h);
            }
          }).catch(function () {});
        }
        refreshCiteTrend();

        /* บัญชีจริง: เติม KPI อันดับจริงจากประวัติ RankSnapshot (beat เก็บรายวัน) */
        function refreshRank() {
          if (!realPid || !RP.api.enabled()) return;
          var slot = root.querySelector('#seo_kpi_slot');
          if (!slot) return;
          RP.api.rankHistory(realPid).then(function (h) {
            if (h && h.count) slot.innerHTML = realSeoKpis(h);
          }).catch(function () {});
        }
        refreshRank();

        /* ไม่มีโปรเจ็ค / ไม่มีโดเมน = ห้ามยิง API เด็ดขาด (กันการตรวจโดเมนของคนอื่น) */
        var dom = String((p && p.domain) || '').trim();
        if (!dom) return;

        var rk = root.querySelector('#m5_rank');
        if (rk) rk.onclick = function () {
          var kw = (root.querySelector('#m5_kw').value || '').trim();
          if (!kw) { RP.ui.toast('พิมพ์คีย์เวิร์ดก่อนครับ'); return; }
          if (realPid) {   // บัญชีจริง → ใช้โดเมน+คีย์ DataForSEO ของลูกค้า + บันทึกเข้าประวัติอันดับ
            RP.live(RP.api.projectRankCheck(realPid, kw), function (res) { rankModal(res); refreshRank(); });
          } else {
            RP.live(RP.api.rankCheck(kw, dom), rankModal);
          }
        };
        var gs = root.querySelector('#m5_gsc');
        if (gs) gs.onclick = function () {
          if (realPid) RP.live(RP.api.projectGsc(realPid), gscModal);   // บัญชี GSC ของลูกค้า
          else RP.live(RP.api.gsc('sc-domain:' + dom), gscModal);
        };
        var ct = root.querySelector('#m5_cite');
        if (ct) ct.onclick = function () {
          var ta = root.querySelector('#m5_qs');
          var raw = ta ? (ta.value || '') : '';
          var qs = raw.split('\n').map(function (x) { return x.trim(); }).filter(function (x) { return !!x; });
          if (!qs.length) { RP.ui.toast('ใส่ชุดคำถามอย่างน้อย 1 บรรทัดก่อนครับ'); return; }
          var terms = brandTermsOf(p);
          if (!terms.length) { RP.ui.toast('ตั้งคำแบรนด์ของโปรเจ็คในหน้าตั้งค่าก่อนครับ'); return; }
          if (realPid) {
            /* บัญชีจริง → ยิง endpoint ที่ 'บันทึกผล' (คำแบรนด์/โดเมนดึงจากโปรเจ็คฝั่ง server)
               เสร็จแล้วรีเฟรชกราฟให้เห็นแนวโน้มสะสมทันที */
            RP.live(RP.api.citationForProject(realPid, qs), function (res) {
              citeModal(res); refreshCiteTrend();
            });
          } else {
            /* โหมดตัวอย่าง/Live-ยังไม่ล็อกอินจริง → ยิงแบบไม่บันทึก (เหมือนเดิม) */
            RP.live(RP.api.citation(qs, terms, dom), citeModal);
          }
        };
      }
    };
  };

})(window.RP);
