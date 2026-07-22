/* ============================================================
   View: กิจกรรมสด (Live Activity) — ฉากการ์ตูน 2D หุ่นยนต์ทำงานจริง
   หุ่นแต่ละตัว = ขั้นตอนจริงของระบบ (เขียน · เผยแพร่ · วัดอันดับ · วัด AI Citation)
   ขับด้วย event จริงจาก /api/activity เท่านั้น — หุ่นจะขยับ + เด้งการ์ดรายงาน
   เมื่อมีงานจริงเกิดขึ้น (ไม่ปลอมข้อมูล) · อัปเดตอัตโนมัติทุก 8 วินาที
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc;

  function timeAgo(iso) {
    if (!iso) return '';
    var t = new Date(iso).getTime();
    if (isNaN(t)) return '';
    var s = Math.floor((Date.now() - t) / 1000);
    if (s < 4) return 'เมื่อกี้';
    if (s < 60) return s + ' วินาทีที่แล้ว';
    var m = Math.floor(s / 60); if (m < 60) return m + ' นาทีที่แล้ว';
    var h = Math.floor(m / 60); if (h < 24) return h + ' ชม.ที่แล้ว';
    return Math.floor(h / 24) + ' วันที่แล้ว';
  }

  /* ---------- นิยามสถานี (หุ่นแต่ละตัว) ---------- */
  var STN = {
    article:    { name: 'นักเขียน AI',      verb: 'กำลังเขียนบทความ…', tool: '✍️', particle: '📄', tone: 'blue',   emoji: '📝' },
    distribute: { name: 'ฝ่ายเผยแพร่',      verb: 'กำลังเผยแพร่…',      tool: '📡', particle: '🚀', tone: 'green',  emoji: '🚀' },
    rank:       { name: 'สายสืบอันดับ',     verb: 'กำลังวัดอันดับ…',    tool: '🔭', particle: '📊', tone: 'violet', emoji: '📈' },
    citation:   { name: 'ตรวจ AI Citation', verb: 'กำลังถาม AI…',       tool: '🧠', particle: '⭐', tone: 'amber',  emoji: '🤖' }
  };
  var ORDER = ['article', 'distribute', 'rank', 'citation'];

  function evKey(e) { return [e.type, e.at, e.title || e.keyword || e.engine || e.channel || ''].join('|'); }

  function reportCardHtml(e) {
    var m = STN[e.type] || {}, txt = '';
    if (e.type === 'article') {
      txt = 'เขียนบทความ <b>' + esc(e.title || '') + '</b>' +
        (e.status === 'published' ? ' · เผยแพร่แล้ว' : e.status === 'draft' ? ' · ร่าง' : '') +
        (e.score ? ' · AEO ' + e.score : '');
    } else if (e.type === 'distribute') {
      txt = 'เผยแพร่ไป <b>' + esc(e.channel || '') + '</b> — ' + esc(e.status || '');
    } else if (e.type === 'rank') {
      txt = 'วัดอันดับ "<b>' + esc(e.keyword || '') + '</b>" → ' +
        (e.rank != null ? 'อันดับ ' + e.rank : 'ยังไม่พบใน 100 อันดับ') + (e.on_page1 ? ' 🏆 หน้า 1' : '');
    } else if (e.type === 'citation') {
      txt = 'AI <b>' + esc(e.engine || '') + '</b> อ้างอิงแบรนด์ · SoV ' + (e.sov != null ? e.sov + '%' : '—');
    }
    return '<div class="rp-report-ic">' + (m.emoji || '✨') + '</div>' +
      '<div class="rp-report-tx"><div class="rp-report-t">' + txt + '</div>' +
      '<div class="rp-report-m">' + esc(e.project || '') + ' · ' + esc(timeAgo(e.at)) + '</div></div>';
  }

  /* ---------- โครง DOM ของฉาก ---------- */
  function stationHtml(role) {
    var m = STN[role];
    return '<div class="rp-st" data-role="' + role + '" data-tone="' + m.tone + '">' +
      '<div class="rp-emit"></div>' +
      '<div class="rp-bot">' +
        '<div class="rp-antenna"></div>' +
        '<div class="rp-head"><span class="rp-eye l"></span><span class="rp-eye r"></span><span class="rp-mouth"></span></div>' +
        '<div class="rp-body"><span class="rp-chest"></span></div>' +
        '<div class="rp-tool">' + m.tool + '</div>' +
      '</div>' +
      '<div class="rp-desk"></div>' +
      '<div class="rp-st-name">' + esc(m.name) + '</div>' +
      '<div class="rp-st-status">พร้อมทำงาน</div>' +
      '<div class="rp-st-count"><b>0</b> <span>ชิ้น</span></div>' +
    '</div>';
  }

  function sceneHtml(compact) {
    return '<div class="rp-stage' + (compact ? ' rp-compact' : '') + '">' +
      '<div class="rp-stage-top">' +
        '<span class="rp-livebadge"><span class="rp-livedot"></span> Live</span>' +
        '<span class="rp-stage-title">โรงงาน AEO · ทำงานอัตโนมัติ 24 ชม.</span>' +
        '<span class="rp-stage-meta"></span>' +
      '</div>' +
      '<div class="rp-reports"></div>' +
      '<div class="rp-floor">' +
        '<div class="rp-stations">' + ORDER.map(stationHtml).join('') + '</div>' +
        '<div class="rp-belt"></div>' +
      '</div>' +
    '</div>';
  }

  /* ---------- ตัวควบคุมฉาก (สร้างครั้งเดียว แล้วอัปเดตทีละ event) ---------- */
  function buildScene(host, opts) {
    opts = opts || {};
    var compact = !!opts.compact, projectId = opts.projectId;
    if (!host) return { stop: function () {} };
    injectCss();
    if (RP._actTimer) { clearInterval(RP._actTimer); RP._actTimer = null; }
    host.innerHTML = sceneHtml(compact) +
      (compact ? '' : '<details class="rp-logwrap"><summary>📋 ดูบันทึกแบบข้อความ (log)</summary><div class="rp-log"></div></details>');

    var seen = null, timer = null, busy = {};
    function q(s) { return host.querySelector(s); }
    function stEl(role) { return host.querySelector('.rp-st[data-role="' + role + '"]'); }
    function setCount(role, n) { var el = stEl(role); if (!el) return; var b = el.querySelector('.rp-st-count b'); if (b) b.textContent = (n == null ? 0 : n); }
    function setBusy(role, on) {
      var el = stEl(role); if (!el) return;
      el.classList.toggle('working', on);
      var s = el.querySelector('.rp-st-status');
      if (s) s.textContent = on ? ((STN[role] || {}).verb || 'กำลังทำงาน…') : 'พร้อมทำงาน';
    }
    function emit(role) {
      var el = stEl(role); if (!el) return;
      var wrap = el.querySelector('.rp-emit'); if (!wrap) return;
      var ch = (STN[role] || {}).particle || '✨';
      for (var i = 0; i < 3; i++) {
        (function (i) {
          var p = document.createElement('span');
          p.className = 'rp-particle'; p.textContent = ch;
          p.style.left = (22 + i * 22) + '%';
          p.style.animationDelay = (i * 0.13) + 's';
          wrap.appendChild(p);
          p.addEventListener('animationend', function () { if (p.parentNode) p.remove(); });
        })(i);
      }
    }
    function pushReport(e) {
      if (compact) return;
      var box = q('.rp-reports'); if (!box) return;
      var c = document.createElement('div');
      c.className = 'rp-report'; c.setAttribute('data-tone', (STN[e.type] || {}).tone || 'blue');
      c.innerHTML = reportCardHtml(e);
      box.insertBefore(c, box.firstChild);
      while (box.children.length > 4) box.removeChild(box.lastChild);
      setTimeout(function () {
        c.classList.add('rp-out');
        setTimeout(function () { if (c.parentNode) c.remove(); }, 520);
      }, 7000);
    }
    function fireWork(role) {
      setBusy(role, true); emit(role);
      if (busy[role]) clearTimeout(busy[role]);
      busy[role] = setTimeout(function () { setBusy(role, false); }, 6500);
    }
    function tick(d) {
      var s = d.summary || {}, evs = d.events || [];
      var meta = q('.rp-stage-meta');
      if (meta) meta.textContent = '· อัปเดต ' + new Date().toLocaleTimeString('th-TH');
      setCount('article', s.articles != null ? s.articles : evs.filter(function (e) { return e.type === 'article'; }).length);
      setCount('distribute', s.published != null ? s.published : evs.filter(function (e) { return e.type === 'distribute'; }).length);
      setCount('rank', evs.filter(function (e) { return e.type === 'rank'; }).length);
      setCount('citation', evs.filter(function (e) { return e.type === 'citation'; }).length);
      if (seen === null) {
        seen = {}; evs.forEach(function (e) { seen[evKey(e)] = 1; });
        evs.slice(0, 3).reverse().forEach(function (e) { pushReport(e); });   // โชว์ล่าสุดสั้น ๆ ตอนเปิด
      } else {
        var fresh = [];
        evs.forEach(function (e) { var k = evKey(e); if (!seen[k]) { seen[k] = 1; fresh.push(e); } });
        fresh.reverse();
        fresh.slice(-6).forEach(function (e) { if (STN[e.type]) { fireWork(e.type); pushReport(e); } });
      }
      var log = q('.rp-log');
      if (log) log.innerHTML = evs.length ? evs.map(evRow).join('')
        : '<div class="soft small" style="text-align:center;padding:14px">ยังไม่มีกิจกรรม — ระบบจะเริ่มตามรอบอัตโนมัติ (ผลิต 02:00 · วัดผล 06:00)</div>';
    }
    function load() {
      if (!document.body.contains(host)) { stop(); return; }
      RP.api.activity(50, projectId).then(function (d) { if (d) tick(d); }).catch(function () {});
    }
    function stop() {
      if (timer) { clearInterval(timer); timer = null; }
      Object.keys(busy).forEach(function (k) { clearTimeout(busy[k]); });
      if (RP._actTimer === timer) RP._actTimer = null;
    }

    if (RP.isReal() && RP.api.enabled()) { load(); timer = setInterval(load, 8000); }
    else { tick(SAMPLE); demoLoop(); }     // ไฟล์/เดโม: วนให้หุ่นขยับโชว์ UI
    RP._actTimer = timer;
    host._rpStop = stop;
    return { stop: stop };

    function demoLoop() {
      var i = 0;
      timer = setInterval(function () {
        if (!document.body.contains(host)) { stop(); return; }
        fireWork(ORDER[i % ORDER.length]);
        pushReport(SAMPLE.events[i % SAMPLE.events.length]);
        i++;
      }, 2800);
    }
  }

  /* ---------- บันทึกแบบข้อความ (log) — ใช้ในกล่องพับ + export เดิม ---------- */
  function evRow(e) {
    var ic = '•', txt = '';
    if (e.type === 'article') {
      ic = '📝';
      var st = e.status === 'published' ? ui.badge('เผยแพร่แล้ว', 'green')
        : e.status === 'draft' ? ui.badge('ร่าง', 'amber') : ui.badge(esc(e.status || ''), '');
      txt = 'เขียนบทความ <b>' + esc(e.title || '') + '</b> ' + st +
        (e.score ? ' ' + ui.badge('AEO ' + e.score, 'blue') : '');
    } else if (e.type === 'distribute') {
      ic = e.status === 'posted' ? '🚀' : e.status === 'failed' ? '⚠️' : '➡️';
      txt = 'เผยแพร่/กระจายไป <b>' + esc(e.channel || '') + '</b> — ' + esc(e.status || '') +
        (e.detail ? ' <span class="soft small">(' + esc(e.detail) + ')</span>' : '');
    } else if (e.type === 'rank') {
      ic = '📈';
      txt = 'วัดอันดับ "<b>' + esc(e.keyword || '') + '</b>" → ' +
        (e.rank != null ? 'อันดับ ' + e.rank : 'ไม่พบใน 100 อันดับ') +
        (e.on_page1 ? ' ' + ui.badge('หน้า 1', 'green') : '');
    } else if (e.type === 'citation') {
      ic = '🤖';
      txt = 'AI Citation — <b>' + esc(e.engine || '') + '</b>: ' + (e.sov != null ? 'SoV ' + e.sov + '%' : '—');
    }
    return '<div class="list-row" style="align-items:flex-start;gap:12px">' +
      '<div style="font-size:18px;line-height:1.5;flex:none">' + ic + '</div>' +
      '<div class="grow"><div class="t">' + txt + '</div>' +
      '<div class="soft small" style="margin-top:2px">' + esc(e.project || '') + ' · ' + esc(timeAgo(e.at)) + '</div></div></div>';
  }

  function feedCard(d) {
    var s = d.summary || {};
    var head = '<div class="row between wrap" style="margin-bottom:10px">' +
      '<div class="row" style="gap:9px;align-items:center">' +
      '<span class="badge green">● Live</span>' +
      '<span class="soft small">อัปเดตล่าสุด ' + new Date().toLocaleTimeString('th-TH') + '</span></div>' +
      '<div class="soft small">' + (s.projects || 0) + ' โปรเจ็ค · ' + (s.articles || 0) + ' บทความ · เผยแพร่ ' + (s.published || 0) + '</div></div>';
    var evs = d.events || [];
    var body = evs.length ? evs.map(evRow).join('')
      : (RP.noData ? RP.noData('ยังไม่มีกิจกรรม',
          'พอระบบเริ่มผลิต/เผยแพร่/วัดผล รายการจะขึ้นที่นี่แบบเรียลไทม์')
          : '<div class="soft small center">ยังไม่มีกิจกรรม</div>');
    return ui.card({ title: 'ไทม์ไลน์ล่าสุด', sub: 'เรียงจากใหม่ → เก่า', body: head + body });
  }

  var SAMPLE = { summary: { projects: 1, articles: 12, published: 9 }, events: [
    { type: 'article', at: new Date(Date.now() - 40000).toISOString(), project: 'รับทำ SEO', title: 'รับทำ seo ราคาถูก', status: 'published', score: 88 },
    { type: 'distribute', at: new Date(Date.now() - 38000).toISOString(), project: 'รับทำ SEO', channel: 'blog', status: 'posted' },
    { type: 'rank', at: new Date(Date.now() - 900000).toISOString(), project: 'รับทำ SEO', keyword: 'รับทำ seo', rank: 7, on_page1: true },
    { type: 'citation', at: new Date(Date.now() - 3600000).toISOString(), project: 'รับทำ SEO', engine: 'gemini', sov: 33.3 }
  ]};

  /* ---------- หน้าเต็ม: กิจกรรมสด = ฉากการ์ตูน ---------- */
  RP.views.activity = function () {
    var html = ui.pageHead({
      eyebrow: 'ภาพรวม · เรียลไทม์', title: '⚡ กิจกรรมสด',
      desc: 'ดูหุ่น AI ของคุณทำงานสด ๆ — เขียนบทความ เผยแพร่ วัดอันดับ วัด AI Citation · หุ่นจะขยับเมื่อมีงานจริงเกิดขึ้น'
    });
    if (!RP.isReal()) html += RP.sampleNotice('หน้ากิจกรรมสด');
    html += '<div id="act_stage"></div>';
    return {
      html: html,
      mount: function (root) {
        var host = (root && root.querySelector('#act_stage')) || document.getElementById('act_stage');
        buildScene(host, { compact: false });
      }
    };
  };

  // ให้แดชบอร์ดฝัง "การทำงานสด" แบบกะทัดรัด (ต่อโปรเจ็ค)
  RP._activity = {
    card: feedCard,
    mount: function (root, projectId) {
      var slot = (root && root.querySelector('#act_slot')) || document.getElementById('act_slot');
      if (!slot) return;
      buildScene(slot, { compact: true, projectId: projectId });
    }
  };

  /* ---------- CSS ของฉาก (ฉีดครั้งเดียว) ---------- */
  function injectCss() {
    if (document.getElementById('rp-scene-css')) return;
    var st = document.createElement('style');
    st.id = 'rp-scene-css';
    st.textContent = SCENE_CSS;
    (document.head || document.documentElement).appendChild(st);
  }

  var SCENE_CSS = [
    '.rp-stage{position:relative;border-radius:18px;padding:14px 16px 20px;background:linear-gradient(180deg,#eef4ff,#f7fbff 60%,#fff);border:1px solid #e3ecff;overflow:hidden;min-height:300px}',
    '.rp-stage-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;position:relative;z-index:2}',
    '.rp-livebadge{display:inline-flex;align-items:center;gap:6px;background:#dcfce7;color:#166534;font-weight:800;font-size:12px;padding:3px 10px;border-radius:999px}',
    '.rp-livedot{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:rp-blink 1.4s infinite}',
    '.rp-stage-title{font-weight:800;color:#1e293b;font-size:14px}',
    '.rp-stage-meta{color:#64748b;font-size:12px}',
    '.rp-reports{position:absolute;top:44px;right:12px;width:min(330px,74%);display:flex;flex-direction:column;gap:8px;z-index:6;pointer-events:none}',
    '.rp-report{display:flex;gap:10px;align-items:flex-start;background:#fff;border:1px solid #e5e7eb;border-left:4px solid #2563eb;border-radius:12px;padding:9px 11px;box-shadow:0 8px 24px rgba(2,6,23,.12);animation:rp-report-in .45s ease;transition:opacity .5s,transform .5s}',
    '.rp-report[data-tone="green"]{border-left-color:#16a34a}.rp-report[data-tone="violet"]{border-left-color:#7c3aed}.rp-report[data-tone="amber"]{border-left-color:#d97706}',
    '.rp-report.rp-out{opacity:0;transform:translateX(30px)}',
    '.rp-report-ic{font-size:20px;line-height:1.2;flex:none}',
    '.rp-report-t{font-size:12.5px;color:#0f172a;line-height:1.35}',
    '.rp-report-m{font-size:11px;color:#64748b;margin-top:2px}',
    '.rp-floor{position:relative;margin-top:58px;z-index:1}',
    '.rp-stations{display:flex;justify-content:space-around;align-items:flex-end;gap:10px;flex-wrap:wrap}',
    '.rp-st{position:relative;flex:1 1 120px;max-width:172px;text-align:center;padding-bottom:6px}',
    '.rp-st[data-tone="blue"]{--c:#2563eb;--c2:#7db0ff}.rp-st[data-tone="green"]{--c:#16a34a;--c2:#5fe08a}',
    '.rp-st[data-tone="violet"]{--c:#7c3aed;--c2:#b79bff}.rp-st[data-tone="amber"]{--c:#d97706;--c2:#fbbf24}',
    '.rp-bot{position:relative;width:76px;margin:0 auto;animation:rp-bob 3s ease-in-out infinite;transform-origin:bottom center}',
    '.rp-antenna{width:3px;height:12px;background:var(--c);margin:0 auto -1px;position:relative;border-radius:2px}',
    '.rp-antenna::after{content:"";position:absolute;top:-6px;left:50%;transform:translateX(-50%);width:8px;height:8px;border-radius:50%;background:#f59e0b;box-shadow:0 0 7px #f59e0b;animation:rp-blink 2s infinite}',
    '.rp-head{width:56px;height:46px;border-radius:15px;background:linear-gradient(160deg,var(--c2),var(--c));margin:0 auto;position:relative;box-shadow:inset 0 -6px 0 rgba(0,0,0,.10)}',
    '.rp-eye{position:absolute;top:17px;width:10px;height:10px;border-radius:50%;background:#fff;animation:rp-eyeblink 4s infinite}',
    '.rp-eye.l{left:13px}.rp-eye.r{right:13px}',
    '.rp-mouth{position:absolute;bottom:9px;left:50%;transform:translateX(-50%);width:16px;height:5px;border-radius:0 0 8px 8px;background:rgba(255,255,255,.9)}',
    '.rp-body{width:46px;height:23px;border-radius:9px;background:linear-gradient(160deg,var(--c2),var(--c));margin:3px auto 0;position:relative}',
    '.rp-chest{position:absolute;top:6px;left:50%;transform:translateX(-50%);width:14px;height:8px;border-radius:3px;background:rgba(255,255,255,.6)}',
    '.rp-tool{position:absolute;right:4px;bottom:32px;font-size:22px;filter:drop-shadow(0 2px 3px rgba(0,0,0,.18))}',
    '.rp-desk{width:78px;height:11px;border-radius:0 0 11px 11px;background:linear-gradient(180deg,var(--c2),var(--c));margin:3px auto 0;opacity:.85}',
    '.rp-st-name{margin-top:10px;font-weight:700;font-size:13px;color:#0f172a}',
    '.rp-st-status{font-size:11.5px;color:#64748b;min-height:15px}',
    '.rp-st.working .rp-st-status{color:var(--c);font-weight:700}',
    '.rp-st-count{margin-top:1px;font-size:11px;color:#475569}.rp-st-count b{font-size:15px;color:var(--c)}',
    '.rp-emit{position:absolute;left:0;right:0;top:0;bottom:34px;pointer-events:none;z-index:3}',
    '.rp-particle{position:absolute;bottom:0;font-size:18px;animation:rp-rise 1.5s ease-out forwards}',
    '.rp-st.working .rp-bot{animation:rp-work .5s ease-in-out infinite}',
    '.rp-st.working .rp-head{box-shadow:inset 0 -6px 0 rgba(0,0,0,.10),0 0 0 4px color-mix(in srgb,var(--c) 22%,transparent),0 0 20px 2px var(--c)}',
    '.rp-st.working .rp-tool{animation:rp-toolspin .8s linear infinite}',
    '.rp-st.working .rp-desk{filter:brightness(1.12)}',
    '.rp-belt{margin-top:14px;height:14px;border-radius:8px;background:repeating-linear-gradient(90deg,#dbe4f5 0 10px,#c7d4ee 10px 20px);background-size:40px 100%;animation:rp-belt 1s linear infinite}',
    '.rp-logwrap{margin-top:14px;border:1px solid var(--border,#e5e7eb);border-radius:12px;padding:6px 12px;background:var(--card,#fff)}',
    '.rp-logwrap>summary{cursor:pointer;font-size:13px;font-weight:600;color:#334155;padding:6px 0;list-style:none}',
    '.rp-logwrap>summary::-webkit-details-marker{display:none}',
    '.rp-log{padding-top:4px}',
    '.rp-stage.rp-compact{min-height:auto;padding:12px 12px 14px}',
    '.rp-stage.rp-compact .rp-reports{display:none}',
    '.rp-stage.rp-compact .rp-floor{margin-top:30px}',
    '.rp-stage.rp-compact .rp-belt{display:none}',
    '.rp-stage.rp-compact .rp-bot{width:64px}.rp-stage.rp-compact .rp-head{width:48px;height:40px}',
    '.rp-stage.rp-compact .rp-body{width:40px}.rp-stage.rp-compact .rp-desk{width:66px}',
    '@keyframes rp-bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}',
    '@keyframes rp-work{0%{transform:translateY(0) rotate(-4deg)}25%{transform:translateY(-4px) rotate(3deg)}50%{transform:translateY(0) rotate(-3deg)}75%{transform:translateY(-4px) rotate(4deg)}100%{transform:translateY(0) rotate(-4deg)}}',
    '@keyframes rp-toolspin{to{transform:rotate(360deg)}}',
    '@keyframes rp-blink{0%,90%,100%{opacity:1}95%{opacity:.25}}',
    '@keyframes rp-eyeblink{0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.12)}}',
    '@keyframes rp-rise{0%{transform:translateY(0) scale(.7);opacity:0}20%{opacity:1}100%{transform:translateY(-74px) scale(1.12);opacity:0}}',
    '@keyframes rp-belt{to{background-position:-40px 0}}',
    '@keyframes rp-report-in{from{transform:translateX(30px);opacity:0}to{transform:translateX(0);opacity:1}}',
    '@media (prefers-color-scheme:dark){',
    '.rp-stage{background:linear-gradient(180deg,#0f1830,#0b1222 60%,#0a0f1e);border-color:#1e2b4a}',
    '.rp-report{background:#0f172a;border-color:#1e293b}.rp-report-t{color:#e2e8f0}',
    '.rp-st-name{color:#e2e8f0}.rp-stage-title{color:#cbd5e1}',
    '.rp-belt{background:repeating-linear-gradient(90deg,#1e293b 0 10px,#0f172a 10px 20px);background-size:40px 100%}',
    '.rp-logwrap{background:#0f172a;border-color:#1e293b}.rp-logwrap>summary{color:#cbd5e1}',
    '}'
  ].join('\n');

})(window.RP);
