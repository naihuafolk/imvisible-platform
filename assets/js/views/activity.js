/* ============================================================
   View: กิจกรรมสด (Live Activity) — ออฟฟิศการ์ตูน 2D
   หุ่นพนักงานเดินทำงานในออฟฟิศ (มีขาเดิน + พนักงานส่งเอกสารเดินข้ามห้อง)
   หุ่นแต่ละตัว = ขั้นตอนจริง (เขียน · เผยแพร่ · วัดอันดับ · วัด AI Citation)
   ขับด้วย event จริงจาก /api/activity เท่านั้น (ไม่ปลอมข้อมูล)
   + เปิดเป็น "หน้าต่าง" ป๊อปอัปดูสดได้ + รายงานสดของจริงด้านล่าง (ทุก 8 วิ)
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

  var STN = {
    article:    { name: 'นักเขียน AI',      verb: 'กำลังเขียนบทความ…', tool: '✍️', particle: '📄', tone: 'blue',   emoji: '📝', unit: 'บทความ' },
    distribute: { name: 'ฝ่ายเผยแพร่',      verb: 'กำลังเผยแพร่…',      tool: '📡', particle: '🚀', tone: 'green',  emoji: '🚀', unit: 'เผยแพร่' },
    rank:       { name: 'สายสืบอันดับ',     verb: 'กำลังวัดอันดับ…',    tool: '🔭', particle: '📊', tone: 'violet', emoji: '📈', unit: 'วัดอันดับ' },
    citation:   { name: 'ตรวจ AI Citation', verb: 'กำลังถาม AI…',       tool: '🧠', particle: '⭐', tone: 'amber',  emoji: '🤖', unit: 'วัด AI' }
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

  /* ---------- ชิ้นส่วนหุ่น ---------- */
  function robotBody(tool, legs) {
    return '<div class="rp-antenna"></div>' +
      '<div class="rp-head"><span class="rp-eye l"></span><span class="rp-eye r"></span><span class="rp-mouth"></span></div>' +
      '<div class="rp-body"><span class="rp-chest"></span></div>' +
      (tool ? '<div class="rp-tool">' + tool + '</div>' : '') +
      (legs ? '<div class="rp-legs"><span class="rp-leg l"></span><span class="rp-leg r"></span></div>' : '');
  }
  function miniBot(tool) {
    return '<div class="rp-mbot"><div class="rp-antenna"></div>' +
      '<div class="rp-head"><span class="rp-eye l"></span><span class="rp-eye r"></span></div>' +
      '<div class="rp-body"></div>' +
      '<div class="rp-legs"><span class="rp-leg l"></span><span class="rp-leg r"></span></div>' +
      '<span class="rp-mtool">' + tool + '</span></div>';
  }

  function stationHtml(role) {
    var m = STN[role];
    return '<div class="rp-st" data-role="' + role + '" data-tone="' + m.tone + '">' +
      '<div class="rp-emit"></div>' +
      '<div class="rp-worker">' + robotBody(m.tool, true) + '</div>' +
      '<div class="rp-desk2"><span class="rp-monitor"></span></div>' +
      '<div class="rp-plate">' + esc(m.name) + '</div>' +
      '<div class="rp-st-status">พร้อมทำงาน</div>' +
      '<div class="rp-st-count"><b>0</b> <span>' + esc(m.unit) + '</span></div>' +
    '</div>';
  }

  function officeHtml(compact, big) {
    var showPop = !compact && !big;
    return '<div class="rp-office' + (compact ? ' rp-compact' : '') + (big ? ' rp-big' : '') + '">' +
      '<div class="rp-office-top">' +
        '<span class="rp-livebadge"><span class="rp-livedot"></span> Live</span>' +
        '<span class="rp-office-title">🏢 ออฟฟิศ ImVisible · ทำงานอัตโนมัติ 24 ชม.</span>' +
        '<span class="rp-stage-meta"></span>' +
        (showPop ? '<button class="btn btn-sm rp-popout" style="margin-left:auto">⛶ เปิดหน้าต่างดูสด</button>' : '') +
      '</div>' +
      '<div class="rp-room">' +
        '<div class="rp-wall"><span class="rp-win"></span><span class="rp-win"></span><span class="rp-win"></span>' +
          '<span class="rp-clock">🕘</span></div>' +
        '<div class="rp-floor2"></div>' +
        '<span class="rp-plant">🪴</span>' +
        '<div class="rp-reports"></div>' +
        '<div class="rp-messenger" data-tone="slate"><div class="rp-msg-i">' + miniBot('📋') + '</div></div>' +
        '<div class="rp-messenger two" data-tone="green"><div class="rp-msg-i">' + miniBot('📦') + '</div></div>' +
        '<div class="rp-stations">' + ORDER.map(stationHtml).join('') + '</div>' +
      '</div>' +
    '</div>';
  }

  function logCardHtml() {
    return '<div class="rp-logcard">' +
      '<div class="rp-logcard-h"><span class="rp-livebadge"><span class="rp-livedot"></span> รายงานสด</span>' +
      '<span class="soft small">ข้อมูลจริงจากระบบ · อัปเดตทุก 8 วินาที · ไม่มีข้อมูลปลอม</span></div>' +
      '<div class="rp-log"><div class="soft small" style="padding:10px">กำลังโหลดรายงาน…</div></div></div>';
  }

  /* ---------- ตัวควบคุมฉาก ---------- */
  function buildScene(host, opts) {
    opts = opts || {};
    var compact = !!opts.compact, big = !!opts.big, projectId = opts.projectId;
    if (!host) return { stop: function () {} };
    injectCss();
    host.innerHTML = officeHtml(compact, big) + (compact ? '' : logCardHtml());

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
      var box = q('.rp-reports'); if (!box) return;
      var c = document.createElement('div');
      c.className = 'rp-report'; c.setAttribute('data-tone', (STN[e.type] || {}).tone || 'blue');
      c.innerHTML = reportCardHtml(e);
      box.insertBefore(c, box.firstChild);
      while (box.children.length > 3) box.removeChild(box.lastChild);
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
        evs.slice(0, 2).reverse().forEach(function (e) { pushReport(e); });
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
    }

    var po = q('.rp-popout'); if (po) po.onclick = function () { openOffice(projectId); };
    if (RP.isReal() && RP.api.enabled()) { load(); timer = setInterval(load, 8000); }
    else { tick(SAMPLE); demoLoop(); }
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

  /* ---------- หน้าต่างป๊อปอัป (เปิดดูออฟฟิศสดเต็มจอ) ---------- */
  function openOffice(projectId) {
    injectCss();
    var ov = document.createElement('div');
    ov.className = 'rp-modal';
    ov.innerHTML = '<div class="rp-modal-win"><div class="rp-modal-bar">' +
      '<span class="rp-modal-dots"><i></i><i></i><i></i></span>' +
      '<span class="rp-modal-title">🏢 ImVisible Office — ถ่ายทอดสด</span>' +
      '<button class="rp-modal-x" title="ปิด">✕</button></div>' +
      '<div class="rp-modal-body"></div></div>';
    document.body.appendChild(ov);
    var sc = buildScene(ov.querySelector('.rp-modal-body'), { projectId: projectId, big: true });
    function close() {
      if (sc && sc.stop) sc.stop();
      if (ov.parentNode) ov.remove();
      document.removeEventListener('keydown', onEsc);
    }
    ov.querySelector('.rp-modal-x').onclick = close;
    ov.addEventListener('click', function (e) { if (e.target === ov) close(); });
    function onEsc(e) { if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onEsc);
  }

  /* ---------- บันทึกแบบข้อความ (log) ---------- */
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
      : (RP.noData ? RP.noData('ยังไม่มีกิจกรรม', 'พอระบบเริ่มผลิต/เผยแพร่/วัดผล รายการจะขึ้นที่นี่แบบเรียลไทม์')
          : '<div class="soft small center">ยังไม่มีกิจกรรม</div>');
    return ui.card({ title: 'ไทม์ไลน์ล่าสุด', sub: 'เรียงจากใหม่ → เก่า', body: head + body });
  }

  var SAMPLE = { summary: { projects: 1, articles: 12, published: 9 }, events: [
    { type: 'article', at: new Date(Date.now() - 40000).toISOString(), project: 'รับทำ SEO', title: 'รับทำ seo ราคาถูก', status: 'published', score: 88 },
    { type: 'distribute', at: new Date(Date.now() - 38000).toISOString(), project: 'รับทำ SEO', channel: 'blog', status: 'posted' },
    { type: 'rank', at: new Date(Date.now() - 900000).toISOString(), project: 'รับทำ SEO', keyword: 'รับทำ seo', rank: 7, on_page1: true },
    { type: 'citation', at: new Date(Date.now() - 3600000).toISOString(), project: 'รับทำ SEO', engine: 'gemini', sov: 33.3 }
  ]};

  RP.views.activity = function () {
    var html = ui.pageHead({
      eyebrow: 'ภาพรวม · เรียลไทม์', title: '⚡ กิจกรรมสด',
      desc: 'ดูออฟฟิศ AI ของคุณทำงานสด ๆ — หุ่นจะเดินทำงานและขยับเมื่อมีงานจริงเกิดขึ้น · กด "เปิดหน้าต่างดูสด" เพื่อดูเต็มจอ'
    });
    if (!RP.isReal()) html += RP.sampleNotice('หน้ากิจกรรมสด');
    html += '<div id="act_stage"></div>';
    return {
      html: html,
      mount: function (root) {
        var hostEl = (root && root.querySelector('#act_stage')) || document.getElementById('act_stage');
        buildScene(hostEl, { compact: false });
      }
    };
  };

  RP._activity = {
    card: feedCard,
    open: openOffice,
    mount: function (root, projectId) {
      var slot = (root && root.querySelector('#act_slot')) || document.getElementById('act_slot');
      if (!slot) return;
      buildScene(slot, { compact: true, projectId: projectId });
    }
  };

  /* ---------- CSS ---------- */
  function injectCss() {
    if (document.getElementById('rp-scene-css')) return;
    var st = document.createElement('style');
    st.id = 'rp-scene-css'; st.textContent = SCENE_CSS;
    (document.head || document.documentElement).appendChild(st);
  }

  var SCENE_CSS = [
    '.rp-office{position:relative;border-radius:18px;padding:14px 16px 16px;background:#f6f9ff;border:1px solid #e3ecff}',
    '.rp-office-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px}',
    '.rp-livebadge{display:inline-flex;align-items:center;gap:6px;background:#dcfce7;color:#166534;font-weight:800;font-size:12px;padding:3px 10px;border-radius:999px}',
    '.rp-livedot{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:rp-blink 1.4s infinite}',
    '.rp-office-title{font-weight:800;color:#1e293b;font-size:14px}',
    '.rp-stage-meta{color:#64748b;font-size:12px}',
    // room
    '.rp-room{position:relative;height:300px;border-radius:14px;overflow:hidden;border:1px solid #dde8fb}',
    '.rp-wall{position:absolute;left:0;right:0;top:0;height:58%;background:linear-gradient(180deg,#eaf2ff,#dbe7fb)}',
    '.rp-floor2{position:absolute;left:0;right:0;bottom:0;height:42%;background:linear-gradient(180deg,#cbdaf3,#b6c8e8)}',
    '.rp-floor2::before{content:"";position:absolute;inset:0;background:repeating-linear-gradient(90deg,rgba(255,255,255,.22) 0 2px,transparent 2px 64px)}',
    '.rp-floor2::after{content:"";position:absolute;left:0;right:0;top:0;height:3px;background:rgba(255,255,255,.5)}',
    '.rp-win{position:absolute;top:16px;width:66px;height:48px;border-radius:8px;background:linear-gradient(160deg,#bfe0ff,#eefaff);border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.06)}',
    '.rp-win:nth-of-type(1){left:7%}.rp-win:nth-of-type(2){left:31%}.rp-win:nth-of-type(3){left:55%}',
    '.rp-clock{position:absolute;top:16px;right:7%;font-size:26px}',
    '.rp-plant{position:absolute;left:10px;bottom:6px;font-size:30px;z-index:3}',
    // tone vars
    '.rp-st[data-tone="blue"],[data-tone="blue"]{--c:#2563eb;--c2:#7db0ff}.rp-st[data-tone="green"],[data-tone="green"]{--c:#16a34a;--c2:#5fe08a}',
    '.rp-st[data-tone="violet"]{--c:#7c3aed;--c2:#b79bff}.rp-st[data-tone="amber"]{--c:#d97706;--c2:#fbbf24}[data-tone="slate"]{--c:#64748b;--c2:#cbd5e1}',
    // stations row
    '.rp-stations{position:absolute;left:0;right:0;bottom:6px;display:flex;justify-content:space-around;align-items:flex-end;gap:8px;padding:0 6px;z-index:2}',
    '.rp-st{position:relative;flex:1 1 100px;max-width:160px;text-align:center}',
    // robot
    '.rp-worker{position:relative;width:72px;margin:0 auto;animation:rp-pace 4.2s ease-in-out infinite}',
    '.rp-st:nth-child(2) .rp-worker{animation-duration:5s}.rp-st:nth-child(3) .rp-worker{animation-duration:3.6s}.rp-st:nth-child(4) .rp-worker{animation-duration:4.6s}',
    '.rp-antenna{width:3px;height:11px;background:var(--c);margin:0 auto -1px;position:relative;border-radius:2px}',
    '.rp-antenna::after{content:"";position:absolute;top:-6px;left:50%;transform:translateX(-50%);width:8px;height:8px;border-radius:50%;background:#f59e0b;box-shadow:0 0 7px #f59e0b;animation:rp-blink 2s infinite}',
    '.rp-head{width:54px;height:44px;border-radius:15px;background:linear-gradient(160deg,var(--c2),var(--c));margin:0 auto;position:relative;box-shadow:inset 0 -6px 0 rgba(0,0,0,.10)}',
    '.rp-eye{position:absolute;top:16px;width:9px;height:9px;border-radius:50%;background:#fff;animation:rp-eyeblink 4s infinite}',
    '.rp-eye.l{left:13px}.rp-eye.r{right:13px}',
    '.rp-mouth{position:absolute;bottom:9px;left:50%;transform:translateX(-50%);width:15px;height:5px;border-radius:0 0 8px 8px;background:rgba(255,255,255,.9)}',
    '.rp-body{width:44px;height:22px;border-radius:9px;background:linear-gradient(160deg,var(--c2),var(--c));margin:3px auto 0;position:relative}',
    '.rp-chest{position:absolute;top:6px;left:50%;transform:translateX(-50%);width:14px;height:7px;border-radius:3px;background:rgba(255,255,255,.6)}',
    '.rp-tool{position:absolute;right:2px;bottom:30px;font-size:21px;filter:drop-shadow(0 2px 3px rgba(0,0,0,.18))}',
    '.rp-legs{display:flex;gap:8px;justify-content:center;margin-top:1px}',
    '.rp-leg{width:7px;height:9px;background:var(--c);border-radius:0 0 3px 3px;animation:rp-step .5s infinite}',
    '.rp-leg.r{animation-delay:.25s}',
    // desk + nameplate
    '.rp-desk2{width:80px;height:14px;border-radius:4px 4px 8px 8px;background:linear-gradient(180deg,#8a99b8,#6f7ea0);margin:2px auto 0;position:relative;box-shadow:0 3px 0 rgba(0,0,0,.12)}',
    '.rp-monitor{position:absolute;top:-11px;left:50%;transform:translateX(-50%);width:22px;height:14px;border-radius:3px;background:#0f172a;border:2px solid #cbd5e1}',
    '.rp-plate{margin-top:6px;font-weight:700;font-size:12.5px;color:#0f172a}',
    '.rp-st-status{font-size:11px;color:#475569;min-height:14px}',
    '.rp-st.working .rp-st-status{color:var(--c);font-weight:700}',
    '.rp-st-count{font-size:10.5px;color:#64748b}.rp-st-count b{font-size:14px;color:var(--c)}',
    // work state
    '.rp-st.working .rp-worker{animation:rp-work .5s ease-in-out infinite}',
    '.rp-st.working .rp-head{box-shadow:inset 0 -6px 0 rgba(0,0,0,.10),0 0 0 4px color-mix(in srgb,var(--c) 22%,transparent),0 0 18px 2px var(--c)}',
    '.rp-st.working .rp-tool{animation:rp-toolspin .8s linear infinite}',
    '.rp-st.working .rp-monitor{background:var(--c)}',
    // particles
    '.rp-emit{position:absolute;left:0;right:0;top:-6px;bottom:60px;pointer-events:none;z-index:4}',
    '.rp-particle{position:absolute;bottom:0;font-size:17px;animation:rp-rise 1.5s ease-out forwards}',
    // messenger (walking across)
    '.rp-messenger{position:absolute;bottom:14px;z-index:3;animation:rp-cross 17s linear infinite}',
    '.rp-messenger.two{bottom:2px;animation:rp-cross-rev 23s linear infinite}',
    '.rp-msg-i{animation:rp-walkbob .45s ease-in-out infinite}',
    '.rp-mbot{position:relative;transform:scale(.6);transform-origin:bottom center}',
    '.rp-messenger.two .rp-mbot{transform:scale(.6) scaleX(-1)}',
    '.rp-mbot .rp-body{width:40px;height:20px}',
    '.rp-mtool{position:absolute;top:8px;right:-4px;font-size:15px}',
    // reports
    '.rp-reports{position:absolute;top:8px;right:8px;width:min(300px,66%);display:flex;flex-direction:column;gap:7px;z-index:6;pointer-events:none}',
    '.rp-report{display:flex;gap:9px;align-items:flex-start;background:#fff;border:1px solid #e5e7eb;border-left:4px solid #2563eb;border-radius:11px;padding:8px 10px;box-shadow:0 8px 22px rgba(2,6,23,.14);animation:rp-report-in .45s ease;transition:opacity .5s,transform .5s}',
    '.rp-report[data-tone="green"]{border-left-color:#16a34a}.rp-report[data-tone="violet"]{border-left-color:#7c3aed}.rp-report[data-tone="amber"]{border-left-color:#d97706}',
    '.rp-report.rp-out{opacity:0;transform:translateX(28px)}',
    '.rp-report-ic{font-size:19px;line-height:1.1;flex:none}',
    '.rp-report-t{font-size:12px;color:#0f172a;line-height:1.35}',
    '.rp-report-m{font-size:10.5px;color:#64748b;margin-top:2px}',
    // log card
    '.rp-logcard{margin-top:14px;border:1px solid var(--border,#e5e7eb);border-radius:14px;background:var(--card,#fff);overflow:hidden}',
    '.rp-logcard-h{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 14px;border-bottom:1px solid var(--border,#e5e7eb)}',
    '.rp-log{padding:4px 14px 8px;max-height:360px;overflow:auto}',
    // compact (dashboard)
    '.rp-office.rp-compact{padding:10px 12px 12px}.rp-office.rp-compact .rp-room{height:210px}',
    '.rp-office.rp-compact .rp-reports{display:none}',
    // big (modal)
    '.rp-office.rp-big{border:none;background:transparent;padding:0}.rp-office.rp-big .rp-room{height:min(440px,58vh)}',
    // modal window
    '.rp-modal{position:fixed;inset:0;background:rgba(15,23,42,.55);z-index:9999;display:grid;place-items:center;padding:18px;animation:rp-fade .2s}',
    '.rp-modal-win{width:min(1040px,96vw);max-height:92vh;overflow:auto;background:var(--card,#fff);border-radius:16px;box-shadow:0 30px 80px rgba(2,6,23,.5)}',
    '.rp-modal-bar{display:flex;align-items:center;gap:10px;padding:11px 14px;border-bottom:1px solid var(--border,#e5e7eb);position:sticky;top:0;background:inherit;z-index:2}',
    '.rp-modal-dots{display:flex;gap:6px}.rp-modal-dots i{width:11px;height:11px;border-radius:50%;background:#e2e8f0}',
    '.rp-modal-dots i:nth-child(1){background:#ff5f57}.rp-modal-dots i:nth-child(2){background:#febc2e}.rp-modal-dots i:nth-child(3){background:#28c840}',
    '.rp-modal-title{font-weight:700;font-size:14px;color:#0f172a}',
    '.rp-modal-x{margin-left:auto;border:none;background:transparent;font-size:16px;cursor:pointer;color:#64748b;padding:4px 8px;border-radius:8px}',
    '.rp-modal-x:hover{background:rgba(100,116,139,.14)}',
    '.rp-modal-body{padding:14px}',
    // keyframes
    '@keyframes rp-pace{0%,100%{transform:translateX(-13px)}50%{transform:translateX(13px)}}',
    '@keyframes rp-work{0%{transform:translateY(0) rotate(-4deg)}25%{transform:translateY(-4px) rotate(3deg)}50%{transform:translateY(0) rotate(-3deg)}75%{transform:translateY(-4px) rotate(4deg)}100%{transform:translateY(0) rotate(-4deg)}}',
    '@keyframes rp-step{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}',
    '@keyframes rp-walkbob{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}',
    '@keyframes rp-toolspin{to{transform:rotate(360deg)}}',
    '@keyframes rp-blink{0%,90%,100%{opacity:1}95%{opacity:.25}}',
    '@keyframes rp-eyeblink{0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.12)}}',
    '@keyframes rp-rise{0%{transform:translateY(0) scale(.7);opacity:0}20%{opacity:1}100%{transform:translateY(-70px) scale(1.1);opacity:0}}',
    '@keyframes rp-cross{0%{left:-70px}100%{left:calc(100% + 10px)}}',
    '@keyframes rp-cross-rev{0%{left:calc(100% + 10px)}100%{left:-70px}}',
    '@keyframes rp-report-in{from{transform:translateX(28px);opacity:0}to{transform:translateX(0);opacity:1}}',
    '@keyframes rp-fade{from{opacity:0}to{opacity:1}}',
    '@media (prefers-color-scheme:dark){',
    '.rp-office{background:#0b1222;border-color:#1e2b4a}',
    '.rp-room{border-color:#1e2b4a}',
    '.rp-wall{background:linear-gradient(180deg,#111c34,#0e1830)}',
    '.rp-floor2{background:linear-gradient(180deg,#12203c,#0d1730)}',
    '.rp-report{background:#0f172a;border-color:#1e293b}.rp-report-t{color:#e2e8f0}',
    '.rp-plate{color:#e2e8f0}.rp-office-title{color:#cbd5e1}.rp-modal-title{color:#e2e8f0}',
    '.rp-logcard{background:#0f172a;border-color:#1e293b}',
    '}'
  ].join('\n');

})(window.RP);
