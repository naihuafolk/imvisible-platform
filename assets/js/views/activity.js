/* ============================================================
   View: กิจกรรมสด (Live Activity) — ห้องทำงาน AI 2D (จำลองออฟฟิศจริง)
   หุ่นพนักงานเดินไปมาทั่วห้อง (JS sim), คุยกันด้วยหลัก SEO/AEO จริง,
   มีไวท์บอร์ด Growth Loop / โต๊ะประชุม / ตู้กดน้ำ · รีแอ็คเมื่อมี event จริง
   จาก /api/activity (ไม่ปลอมข้อมูล) · รายงานสดของจริงด้านล่าง (ทุก 8 วิ)
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

  /* พนักงานในออฟฟิศ = ขั้นตอนจริงของสาย SEO/AEO ของเรา · คำพูด = หลักการจริง (ไม่ใช่ตัวเลขปลอม) */
  var ROLES = [
    { key: 'research', name: 'นักวิจัยคีย์เวิร์ด', tool: '🔎', tone: 'blue', event: 'article',
      tips: ['intent มาก่อนคีย์เวิร์ด 💡', 'เก็บ People Also Ask', 'หา content gap คู่แข่ง', 'คีย์นี้ intent ซื้อชัด'] },
    { key: 'write', name: 'นักเขียน AEO', tool: '✍️', tone: 'violet', event: 'article',
      tips: ['answer-first 40–60 คำ', 'โครง H2 ตาม search intent', 'เขียนให้ AI หยิบไปตอบ', 'E-E-A-T ต้องแน่น'] },
    { key: 'optimize', name: 'ออปติไมเซอร์', tool: '🎨', tone: 'amber', event: 'article',
      tips: ['ใส่ FAQ schema', 'internal link ไป pillar', 'ใส่ alt ให้รูปปก', 'ตัดลิงก์ตายทิ้ง'] },
    { key: 'publish', name: 'ฝ่ายเผยแพร่', tool: '🚀', tone: 'green', event: 'distribute',
      tips: ['ping IndexNow ทันที', 'อัปเดต sitemap', 'เผยแพร่ตามเวลา'] },
    { key: 'rank', name: 'สายสืบอันดับ', tool: '📈', tone: 'cyan', event: 'rank',
      tips: ['วัดอันดับจริงทุกวัน', 'ดู SERP feature', 'ติดหน้า 1 ยัง?'] },
    { key: 'citation', name: 'ตรวจ AI Citation', tool: '🧠', tone: 'pink', event: 'citation',
      tips: ['ถาม ChatGPT อ้างเราไหม', 'วัด SoV vs คู่แข่ง', 'ตอบให้ AI เชื่อถือ'] }
  ];

  function evKey(e) { return [e.type, e.at, e.title || e.keyword || e.engine || e.channel || ''].join('|'); }

  function plainReport(e) {
    if (e.type === 'article') return 'เขียน: ' + (e.title || '') + (e.score ? ' · AEO ' + e.score : '');
    if (e.type === 'distribute') return 'เผยแพร่ ' + (e.channel || '') + ' ✓';
    if (e.type === 'rank') return 'อันดับ "' + (e.keyword || '') + '" ' + (e.rank != null ? '#' + e.rank : '—') + (e.on_page1 ? ' 🏆' : '');
    if (e.type === 'citation') return 'AI ' + (e.engine || '') + ' อ้างเรา · SoV ' + (e.sov != null ? e.sov + '%' : '—');
    return '…';
  }
  var EMOJI = { article: '📝', distribute: '🚀', rank: '📈', citation: '🤖' };
  var TONE_OF = { article: 'violet', distribute: 'green', rank: 'cyan', citation: 'pink' };

  function reportCardHtml(e) {
    var txt = '';
    if (e.type === 'article') txt = 'เขียนบทความ <b>' + esc(e.title || '') + '</b>' +
      (e.status === 'published' ? ' · เผยแพร่แล้ว' : e.status === 'draft' ? ' · ร่าง' : '') + (e.score ? ' · AEO ' + e.score : '');
    else if (e.type === 'distribute') txt = 'เผยแพร่ไป <b>' + esc(e.channel || '') + '</b> — ' + esc(e.status || '');
    else if (e.type === 'rank') txt = 'วัดอันดับ "<b>' + esc(e.keyword || '') + '</b>" → ' +
      (e.rank != null ? 'อันดับ ' + e.rank : 'ยังไม่พบใน 100 อันดับ') + (e.on_page1 ? ' 🏆 หน้า 1' : '');
    else if (e.type === 'citation') txt = 'AI <b>' + esc(e.engine || '') + '</b> อ้างอิงแบรนด์ · SoV ' + (e.sov != null ? e.sov + '%' : '—');
    return '<div class="rp-report-ic">' + (EMOJI[e.type] || '✨') + '</div>' +
      '<div class="rp-report-tx"><div class="rp-report-t">' + txt + '</div>' +
      '<div class="rp-report-m">' + esc(e.project || '') + ' · ' + esc(timeAgo(e.at)) + '</div></div>';
  }

  /* ---------- โครง DOM ห้องทำงาน ---------- */
  function robotInner(tool) {
    return '<div class="rp-antenna"></div>' +
      '<div class="rp-head"><span class="rp-eye l"></span><span class="rp-eye r"></span><span class="rp-mouth"></span></div>' +
      '<div class="rp-body"><span class="rp-chest"></span></div>' +
      '<div class="rp-tool">' + tool + '</div>' +
      '<div class="rp-legs"><span class="rp-leg l"></span><span class="rp-leg r"></span></div>';
  }
  function boardHtml() {
    var steps = ['วิจัย', 'เขียน', 'ออปติไมซ์', 'เผยแพร่', 'วัดผล', 'เรียนรู้'];
    return '<div class="rp-board-t">AEO GROWTH LOOP · หลักการทำงานของเรา</div>' +
      '<div class="rp-board-steps">' + steps.map(function (s, i) {
        return '<span>' + s + '</span>' + (i < steps.length - 1 ? '<i>→</i>' : '<i>↺</i>');
      }).join('') + '</div>';
  }
  function statsHtml() {
    return '<span class="rp-pill" id="st_article">📝 0 บทความ</span>' +
      '<span class="rp-pill" id="st_pub">🚀 0 เผยแพร่</span>' +
      '<span class="rp-pill" id="st_rank">📈 0 วัดอันดับ</span>' +
      '<span class="rp-pill" id="st_cite">🤖 0 วัด AI</span>';
  }
  function officeHtml(compact, big) {
    var showPop = !compact && !big;
    return '<div class="rp-office' + (compact ? ' rp-compact' : '') + (big ? ' rp-big' : '') + '">' +
      '<div class="rp-office-top">' +
        '<span class="rp-livebadge"><span class="rp-livedot"></span> Live</span>' +
        '<span class="rp-office-title">🏢 ออฟฟิศ ImVisible · ทีม AEO ทำงาน 24 ชม.</span>' +
        '<span class="rp-stage-meta"></span>' +
        (showPop ? '<button class="btn btn-sm rp-popout" style="margin-left:auto">⛶ เปิดหน้าต่างดูสด</button>' : '') +
      '</div>' +
      '<div class="rp-room">' +
        '<div class="rp-wall">' +
          '<span class="rp-win"></span><span class="rp-win"></span>' +
          '<span class="rp-clock">🕘</span>' +
          '<div class="rp-board">' + boardHtml() + '</div>' +
        '</div>' +
        '<div class="rp-floor2"></div>' +
        '<div class="rp-deskprop" style="left:20%"></div>' +
        '<div class="rp-deskprop" style="left:50%"></div>' +
        '<div class="rp-deskprop" style="left:80%"></div>' +
        '<div class="rp-table"></div>' +
        '<div class="rp-cooler"><span>💧</span></div>' +
        '<span class="rp-plant" style="left:3%">🪴</span>' +
        '<span class="rp-plant" style="right:2%">🌿</span>' +
        '<div class="rp-rankboard"><div class="rp-rb-title">📊 อันดับสด (ของจริง)</div>' +
          '<div class="rp-rb-list"><div class="rp-rb-empty">รอผลวัดอันดับ…</div></div></div>' +
        '<div class="rp-stats">' + statsHtml() + '</div>' +
        '<div class="rp-reports"></div>' +
      '</div>' +
    '</div>';
  }
  function logCardHtml() {
    return '<div class="rp-logcard">' +
      '<div class="rp-logcard-h"><span class="rp-livebadge"><span class="rp-livedot"></span> รายงานสด</span>' +
      '<span class="soft small">ข้อมูลจริงจากระบบ · อัปเดตทุก 8 วินาที · ไม่มีข้อมูลปลอม</span></div>' +
      '<div class="rp-log"><div class="soft small" style="padding:10px">กำลังโหลดรายงาน…</div></div></div>';
  }

  /* ---------- ตัวจำลองห้องทำงาน (เดิน + คุย + รีแอ็ค event จริง) ---------- */
  function buildOffice(host, opts) {
    opts = opts || {};
    var compact = !!opts.compact, big = !!opts.big, projectId = opts.projectId;
    if (!host) return { stop: function () {} };
    injectCss();
    host.innerHTML = officeHtml(compact, big) + (compact ? '' : logCardHtml());
    var room = host.querySelector('.rp-room');
    var roles = compact ? ROLES.slice(0, 4) : ROLES;
    var chars = [], seen = null, raf = null, timer = null, lastT = 0;
    var rankBoard = {}, celebrated = {};   // อันดับสดต่อคีย์เวิร์ด (จาก event จริง) + คีย์ที่ฉลองไปแล้ว

    roles.forEach(function (role, i) {
      var el = document.createElement('div');
      el.className = 'rp-ch'; el.setAttribute('data-tone', role.tone);
      el.innerHTML = '<div class="rp-bubble"></div>' +
        '<div class="rp-figure"><div class="rp-robot">' + robotInner(role.tool) + '</div></div>' +
        '<div class="rp-label">' + esc(role.name) + '</div>';
      room.appendChild(el);
      var x = 10 + (i / Math.max(1, roles.length - 1)) * 80;
      var c = { idx: i, role: role, el: el, bubble: el.querySelector('.rp-bubble'), fig: el.querySelector('.rp-robot'),
        x: x, y: 26, tx: x, ty: 26, moving: false, facing: 1, speed: 0.42 + Math.random() * 0.28,
        pauseUntil: 0, nextSayAt: null, busyReal: false };
      chars.push(c); render(c);
    });

    function render(c) {
      c.el.style.left = c.x + '%';
      c.el.style.bottom = c.y + '%';
      var scale = 1.12 - (c.y - 12) / 28 * 0.46;               // ใกล้ (y ต่ำ) = ใหญ่, ไกล = เล็ก
      c.el.style.zIndex = Math.round((44 - c.y) * 4) + 5;
      c.fig.style.transform = 'scale(' + scale.toFixed(3) + ') scaleX(' + c.facing + ')';
    }
    function pickTarget(c) {
      var r = Math.random();
      if (r < 0.16) { c.tx = 50; c.ty = 13; }                  // โต๊ะประชุม (หน้า-กลาง)
      else if (r < 0.28) { c.tx = 8; c.ty = 16; }              // ตู้กดน้ำ (หน้า-ซ้าย)
      else if (r < 0.48) { c.tx = [20, 50, 80][Math.floor(Math.random() * 3)]; c.ty = 36; } // โต๊ะทำงาน (หลัง)
      else { c.tx = Math.max(6, Math.min(94, c.x + (Math.random() * 46 - 23))); c.ty = 15 + Math.random() * 20; }
    }
    function step(c, dt, t) {
      if (c.nextSayAt == null) c.nextSayAt = t + 700 + c.idx * 1100 + Math.random() * 3000;
      if (c.moving) {
        var dx = c.tx - c.x, dy = c.ty - c.y, dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 0.8) {
          c.x = c.tx; c.y = c.ty; c.moving = false; c.el.classList.remove('walking');
          c.pauseUntil = t + 500 + Math.random() * 2400;
          if (Math.random() < 0.5) sayTip(c, t);
        } else {
          var sp = c.speed * (dt / 16);
          c.x += dx / dist * sp; c.y += dy / dist * sp;
          c.facing = dx >= 0 ? 1 : -1;
        }
        render(c);
      } else if (t > c.pauseUntil && !c.busyReal) {
        pickTarget(c); c.moving = true; c.el.classList.add('walking');
      }
      if (t > c.nextSayAt && !c.busyReal) sayTip(c, t);
    }
    function sayTip(c, t) {
      var tips = c.role.tips;
      say(c, tips[Math.floor(Math.random() * tips.length)]);
      c.nextSayAt = t + 6500 + Math.random() * 9000;
    }
    function say(c, text, ms) {
      c.bubble.textContent = text;
      c.bubble.classList.add('show');
      clearTimeout(c._sayT);
      c._sayT = setTimeout(function () { c.bubble.classList.remove('show'); }, ms || 2600);
    }
    function frame(t) {
      if (!document.body.contains(host)) { stop(); return; }
      var dt = lastT ? Math.min(60, t - lastT) : 16; lastT = t;
      for (var i = 0; i < chars.length; i++) step(chars[i], dt, t);
      raf = requestAnimationFrame(frame);
    }

    function charForEvent(type) {
      var map = { article: 'write', distribute: 'publish', rank: 'rank', citation: 'citation' };
      var key = map[type]; if (!key) return null;
      for (var i = 0; i < chars.length; i++) if (chars[i].role.key === key) return chars[i];
      return null;
    }
    function reactToEvent(e) {
      var c = charForEvent(e.type); if (!c) return;
      c.busyReal = true; c.el.classList.add('reacting');
      c.tx = [20, 50, 80][Math.floor(Math.random() * 3)]; c.ty = 36; c.moving = true; c.el.classList.add('walking');
      say(c, plainReport(e), 5200);
      clearTimeout(c._realT);
      c._realT = setTimeout(function () { c.busyReal = false; c.el.classList.remove('reacting'); }, 5200);
    }
    function pushReport(e) {
      if (compact) return;
      var box = host.querySelector('.rp-reports'); if (!box) return;
      var c = document.createElement('div');
      c.className = 'rp-report'; c.setAttribute('data-tone', TONE_OF[e.type] || 'blue');
      c.innerHTML = reportCardHtml(e);
      box.insertBefore(c, box.firstChild);
      while (box.children.length > 3) box.removeChild(box.lastChild);
      setTimeout(function () { c.classList.add('rp-out'); setTimeout(function () { if (c.parentNode) c.remove(); }, 520); }, 7000);
    }
    function setPill(id, txt) { var el = host.querySelector('#' + id); if (el) el.textContent = txt; }
    function updateStats(s, evs) {
      setPill('st_article', '📝 ' + (s.articles != null ? s.articles : evs.filter(function (e) { return e.type === 'article'; }).length) + ' บทความ');
      setPill('st_pub', '🚀 ' + (s.published != null ? s.published : evs.filter(function (e) { return e.type === 'distribute'; }).length) + ' เผยแพร่');
      setPill('st_rank', '📈 ' + evs.filter(function (e) { return e.type === 'rank'; }).length + ' วัดอันดับ');
      setPill('st_cite', '🤖 ' + evs.filter(function (e) { return e.type === 'citation'; }).length + ' วัด AI');
    }
    function renderRankBoard() {
      var list = host.querySelector('.rp-rb-list'); if (!list) return;
      var rows = Object.keys(rankBoard).map(function (kw) { var r = rankBoard[kw]; return { kw: kw, rank: r.rank, on_page1: r.on_page1 }; });
      rows.sort(function (a, b) { return (a.rank == null ? 999 : a.rank) - (b.rank == null ? 999 : b.rank); });
      if (!rows.length) { list.innerHTML = '<div class="rp-rb-empty">รอผลวัดอันดับ…</div>'; return; }
      list.innerHTML = rows.slice(0, 6).map(function (r) {
        var col = r.rank != null && r.rank <= 10 ? '#4ade80' : r.rank != null && r.rank <= 30 ? '#fbbf24' : '#94a3b8';
        return '<div class="rp-rb-row"><span class="rp-rb-kw">' + esc(r.kw) + '</span>' +
          (r.on_page1 ? '<span class="rp-rb-p1">🏆</span>' : '') +
          '<span class="rp-rb-rank" style="color:' + col + '">' + (r.rank != null ? '#' + r.rank : '—') + '</span></div>';
      }).join('');
    }
    function celebrate(kw) {
      if (compact) return;
      var b = document.createElement('div'); b.className = 'rp-celebrate';
      b.innerHTML = '🎉 ติดหน้า 1! <b>' + esc(kw || '') + '</b>';
      room.appendChild(b);
      setTimeout(function () { b.classList.add('rp-cel-out'); setTimeout(function () { if (b.parentNode) b.remove(); }, 600); }, 3200);
      var colors = ['#f59e0b', '#22c55e', '#3b82f6', '#ec4899', '#a855f7'];
      for (var i = 0; i < 26; i++) {
        (function () {
          var f = document.createElement('span'); f.className = 'rp-confetti';
          f.style.left = (Math.random() * 100) + '%';
          f.style.background = colors[Math.floor(Math.random() * colors.length)];
          f.style.animationDelay = (Math.random() * 0.5) + 's';
          f.style.animationDuration = (1.6 + Math.random() * 1.2) + 's';
          room.appendChild(f);
          f.addEventListener('animationend', function () { if (f.parentNode) f.remove(); });
        })();
      }
      for (var j = 0; j < chars.length; j++) if (chars[j].role.key === 'rank') {
        (function (rc) { rc.el.classList.add('cheer'); say(rc, 'ติดหน้า 1 แล้ว! 🎉', 3000); setTimeout(function () { rc.el.classList.remove('cheer'); }, 2200); })(chars[j]);
      }
    }
    function tick(d) {
      var s = d.summary || {}, evs = d.events || [];
      updateStats(s, evs);
      var meta = host.querySelector('.rp-stage-meta'); if (meta) meta.textContent = '· อัปเดต ' + new Date().toLocaleTimeString('th-TH');
      evs.forEach(function (e) {           // สร้างกระดานอันดับสดจาก event จริง (อันล่าสุดต่อคีย์เวิร์ด)
        if (e.type === 'rank' && e.keyword) {
          var cur = rankBoard[e.keyword];
          if (!cur || (e.at && (!cur.at || e.at >= cur.at))) rankBoard[e.keyword] = { rank: e.rank, on_page1: !!e.on_page1, at: e.at };
        }
      });
      renderRankBoard();
      if (seen === null) {
        seen = {}; evs.forEach(function (e) { seen[evKey(e)] = 1; });
        evs.slice(0, 2).reverse().forEach(function (e) { pushReport(e); });
      } else {
        var fresh = [];
        evs.forEach(function (e) { var k = evKey(e); if (!seen[k]) { seen[k] = 1; fresh.push(e); } });
        fresh.reverse();
        fresh.slice(-5).forEach(function (e) {
          reactToEvent(e); pushReport(e);
          if (e.type === 'rank' && e.on_page1 && e.keyword && !celebrated[e.keyword]) { celebrated[e.keyword] = 1; celebrate(e.keyword); }   // ฉลองเมื่อติดหน้า 1 (ครั้งแรกต่อคีย์)
        });
      }
      var log = host.querySelector('.rp-log');
      if (log) log.innerHTML = evs.length ? evs.map(evRow).join('')
        : '<div class="soft small" style="text-align:center;padding:14px">ยังไม่มีกิจกรรม — ระบบจะเริ่มตามรอบอัตโนมัติ (ผลิต 02:00 · วัดผล 06:00)</div>';
    }
    function load() {
      if (!document.body.contains(host)) { stop(); return; }
      RP.api.activity(50, projectId).then(function (d) { if (d) tick(d); }).catch(function () {});
    }
    function stop() {
      if (raf) { cancelAnimationFrame(raf); raf = null; }
      if (timer) { clearInterval(timer); timer = null; }
      chars.forEach(function (c) { clearTimeout(c._sayT); clearTimeout(c._realT); });
    }

    var po = host.querySelector('.rp-popout'); if (po) po.onclick = function () { openOffice(projectId); };
    raf = requestAnimationFrame(frame);
    if (RP.isReal() && RP.api.enabled()) { load(); timer = setInterval(load, 8000); }
    else { tick(SAMPLE); timer = setInterval(function () { if (!document.body.contains(host)) { stop(); return; } reactToEvent(SAMPLE.events[Math.floor(Math.random() * SAMPLE.events.length)]); }, 3400); }
    host._rpStop = stop;
    return { stop: stop };
  }

  /* ---------- หน้าต่างป๊อปอัป (ดูออฟฟิศสดเต็มจอ) ---------- */
  function openOffice(projectId) {
    injectCss();
    var ov = document.createElement('div');
    ov.className = 'rp-modal';
    ov.innerHTML = '<div class="rp-modal-win"><div class="rp-modal-bar">' +
      '<span class="rp-modal-dots"><i></i><i></i><i></i></span>' +
      '<span class="rp-modal-title">🏢 ImVisible Office — ถ่ายทอดสด</span>' +
      '<button class="rp-modal-x" title="ปิด">✕</button></div><div class="rp-modal-body"></div></div>';
    document.body.appendChild(ov);
    var sc = buildOffice(ov.querySelector('.rp-modal-body'), { projectId: projectId, big: true });
    function close() { if (sc && sc.stop) sc.stop(); if (ov.parentNode) ov.remove(); document.removeEventListener('keydown', onEsc); }
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
      txt = 'เขียนบทความ <b>' + esc(e.title || '') + '</b> ' + st + (e.score ? ' ' + ui.badge('AEO ' + e.score, 'blue') : '');
    } else if (e.type === 'distribute') {
      ic = e.status === 'posted' ? '🚀' : e.status === 'failed' ? '⚠️' : '➡️';
      txt = 'เผยแพร่/กระจายไป <b>' + esc(e.channel || '') + '</b> — ' + esc(e.status || '') +
        (e.detail ? ' <span class="soft small">(' + esc(e.detail) + ')</span>' : '');
    } else if (e.type === 'rank') {
      ic = '📈';
      txt = 'วัดอันดับ "<b>' + esc(e.keyword || '') + '</b>" → ' +
        (e.rank != null ? 'อันดับ ' + e.rank : 'ไม่พบใน 100 อันดับ') + (e.on_page1 ? ' ' + ui.badge('หน้า 1', 'green') : '');
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
      '<div class="row" style="gap:9px;align-items:center"><span class="badge green">● Live</span>' +
      '<span class="soft small">อัปเดตล่าสุด ' + new Date().toLocaleTimeString('th-TH') + '</span></div>' +
      '<div class="soft small">' + (s.projects || 0) + ' โปรเจ็ค · ' + (s.articles || 0) + ' บทความ · เผยแพร่ ' + (s.published || 0) + '</div></div>';
    var evs = d.events || [];
    var body = evs.length ? evs.map(evRow).join('')
      : (RP.noData ? RP.noData('ยังไม่มีกิจกรรม', 'พอระบบเริ่มผลิต/เผยแพร่/วัดผล รายการจะขึ้นที่นี่แบบเรียลไทม์') : '<div class="soft small center">ยังไม่มีกิจกรรม</div>');
    return ui.card({ title: 'ไทม์ไลน์ล่าสุด', sub: 'เรียงจากใหม่ → เก่า', body: head + body });
  }

  var SAMPLE = { summary: { projects: 1, articles: 12, published: 9 }, events: [
    { type: 'article', at: new Date(Date.now() - 40000).toISOString(), project: 'รับทำ SEO', title: 'รับทำ seo ราคาถูก', status: 'published', score: 88 },
    { type: 'distribute', at: new Date(Date.now() - 38000).toISOString(), project: 'รับทำ SEO', channel: 'blog', status: 'posted' },
    { type: 'rank', at: new Date(Date.now() - 900000).toISOString(), project: 'รับทำ SEO', keyword: 'รับทำ seo', rank: 7, on_page1: true },
    { type: 'citation', at: new Date(Date.now() - 3600000).toISOString(), project: 'รับทำ SEO', engine: 'gemini', sov: 33.3 }
  ]};

  RP.views.activity = function () {
    var html = ui.pageHead({ eyebrow: 'ภาพรวม · เรียลไทม์', title: '⚡ กิจกรรมสด',
      desc: 'ดูทีม AI ในออฟฟิศทำงานสด ๆ — เดินไปทำงาน คุยกันด้วยหลัก SEO/AEO และขยับเมื่อมีงานจริง · กด "เปิดหน้าต่างดูสด" เพื่อดูเต็มจอ' });
    if (!RP.isReal()) html += RP.sampleNotice('หน้ากิจกรรมสด');
    html += '<div id="act_stage"></div>';
    return { html: html, mount: function (root) {
      var hostEl = (root && root.querySelector('#act_stage')) || document.getElementById('act_stage');
      buildOffice(hostEl, { compact: false });
    } };
  };

  RP._activity = {
    card: feedCard, open: openOffice,
    mount: function (root, projectId) {
      var slot = (root && root.querySelector('#act_slot')) || document.getElementById('act_slot');
      if (!slot) return;
      buildOffice(slot, { compact: true, projectId: projectId });
    }
  };

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
    '.rp-office-title{font-weight:800;color:#1e293b;font-size:14px}.rp-stage-meta{color:#64748b;font-size:12px}',
    // room
    '.rp-room{position:relative;height:340px;border-radius:14px;overflow:hidden;border:1px solid #dde8fb}',
    '.rp-wall{position:absolute;left:0;right:0;top:0;height:56%;background:linear-gradient(180deg,#eaf2ff,#dbe7fb)}',
    '.rp-floor2{position:absolute;left:0;right:0;bottom:0;height:44%;background:linear-gradient(180deg,#cbdaf3,#b3c6e6)}',
    '.rp-floor2::before{content:"";position:absolute;inset:0;background:repeating-linear-gradient(90deg,rgba(255,255,255,.20) 0 2px,transparent 2px 70px)}',
    '.rp-win{position:absolute;top:14px;width:58px;height:42px;border-radius:8px;background:linear-gradient(160deg,#bfe0ff,#eefaff);border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.06)}',
    '.rp-win:nth-of-type(1){left:5%}.rp-win:nth-of-type(2){left:19%}',
    '.rp-clock{position:absolute;top:16px;left:33%;font-size:22px}',
    // whiteboard
    '.rp-board{position:absolute;top:12px;right:4%;width:min(360px,54%);background:#fff;border:2px solid #cbd7ee;border-radius:10px;padding:8px 10px;box-shadow:0 4px 12px rgba(2,6,23,.08)}',
    '.rp-board-t{font-size:11px;font-weight:800;color:#334155;letter-spacing:.3px;margin-bottom:6px}',
    '.rp-board-steps{display:flex;flex-wrap:wrap;align-items:center;gap:3px;font-size:11px;color:#1e293b}',
    '.rp-board-steps span{background:#eef2ff;color:#4338ca;border-radius:6px;padding:2px 6px;font-weight:700}',
    '.rp-board-steps i{color:#94a3b8;font-style:normal;font-weight:800}',
    // props
    '.rp-deskprop{position:absolute;bottom:30%;transform:translateX(-50%);width:66px;height:34px;border-radius:6px 6px 4px 4px;background:linear-gradient(180deg,#93a3c2,#6f7ea0);box-shadow:0 4px 0 rgba(0,0,0,.10);opacity:.9}',
    '.rp-deskprop::before{content:"";position:absolute;top:-12px;left:50%;transform:translateX(-50%);width:26px;height:16px;border-radius:3px;background:#0f172a;border:2px solid #cbd5e1}',
    '.rp-table{position:absolute;bottom:6%;left:50%;transform:translateX(-50%);width:130px;height:34px;border-radius:50%;background:radial-gradient(ellipse at 50% 35%,#c8d5ee,#9fb1d4);box-shadow:0 6px 14px rgba(2,6,23,.12)}',
    '.rp-cooler{position:absolute;bottom:10%;left:5%;width:20px;height:40px;border-radius:5px;background:linear-gradient(180deg,#dbeafe,#bfdbfe);border:1px solid #93c5fd;display:grid;place-items:center;font-size:12px}',
    '.rp-plant{position:absolute;bottom:5%;font-size:26px}',
    // stats strip
    '.rp-stats{position:absolute;left:10px;bottom:8px;display:flex;flex-wrap:wrap;gap:6px;z-index:40}',
    '.rp-pill{background:rgba(255,255,255,.9);border:1px solid #e2e8f0;border-radius:999px;padding:3px 9px;font-size:11px;font-weight:700;color:#334155;box-shadow:0 2px 6px rgba(2,6,23,.06)}',
    // กระดานอันดับสด (จอผนัง)
    '.rp-rankboard{position:absolute;top:12px;left:3%;width:min(230px,34%);background:linear-gradient(180deg,#0f172a,#111c34);border:2px solid #1e2b4a;border-radius:11px;padding:8px 11px;box-shadow:0 8px 20px rgba(2,6,23,.28);z-index:6}',
    '.rp-rb-title{font-size:11px;font-weight:800;color:#7dd3fc;margin-bottom:7px;letter-spacing:.02em}',
    '.rp-rb-list{display:flex;flex-direction:column;gap:4px}',
    '.rp-rb-row{display:flex;align-items:center;gap:6px;font-size:11.5px;color:#e2e8f0}',
    '.rp-rb-kw{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.rp-rb-rank{font-weight:800;font-variant-numeric:tabular-nums;min-width:34px;text-align:right}',
    '.rp-rb-p1{font-size:11px}.rp-rb-empty{font-size:10.5px;color:#64748b}',
    // ฉลอง: ป้าย + พลุ + หุ่นกระโดด
    '.rp-celebrate{position:absolute;top:42%;left:50%;transform:translate(-50%,-50%) scale(.5);background:linear-gradient(135deg,#f59e0b,#fbbf24);color:#3b2500;font-weight:800;font-size:16px;padding:10px 20px;border-radius:14px;box-shadow:0 14px 34px rgba(245,158,11,.5);z-index:95;white-space:nowrap;animation:rp-cel-in .5s cubic-bezier(.2,1.5,.4,1) forwards}',
    '.rp-celebrate.rp-cel-out{opacity:0;transform:translate(-50%,-150%) scale(1);transition:.6s}',
    '@keyframes rp-cel-in{to{transform:translate(-50%,-50%) scale(1)}}',
    '.rp-confetti{position:absolute;top:-10px;width:8px;height:13px;border-radius:2px;z-index:93;pointer-events:none;animation:rp-fall linear forwards}',
    '@keyframes rp-fall{0%{transform:translateY(0) rotate(0);opacity:1}100%{transform:translateY(370px) rotate(560deg);opacity:.15}}',
    '.rp-ch.cheer .rp-figure{animation:rp-jump .42s ease-in-out 5}',
    '@keyframes rp-jump{0%,100%{transform:translateY(0)}50%{transform:translateY(-15px)}}',
    '.rp-robot::after{content:"";position:absolute;left:50%;bottom:-3px;transform:translateX(-50%);width:34px;height:7px;border-radius:50%;background:rgba(2,6,23,.16);z-index:-1}',   // เงาใต้หุ่น (ดูมีมิติ)
    // tones
    '.rp-ch[data-tone="blue"]{--c:#2563eb;--c2:#7db0ff}.rp-ch[data-tone="violet"]{--c:#7c3aed;--c2:#b79bff}',
    '.rp-ch[data-tone="amber"]{--c:#d97706;--c2:#fbbf24}.rp-ch[data-tone="green"]{--c:#16a34a;--c2:#5fe08a}',
    '.rp-ch[data-tone="cyan"]{--c:#0891b2;--c2:#67e8f9}.rp-ch[data-tone="pink"]{--c:#db2777;--c2:#f9a8d4}',
    // character
    '.rp-ch{position:absolute;transform:translateX(-50%);transform-origin:bottom center;will-change:left,bottom}',
    '.rp-figure{position:relative}.rp-ch.walking .rp-figure{animation:rp-walkbob .4s ease-in-out infinite}',
    '.rp-robot{position:relative;width:50px;margin:0 auto;transform-origin:bottom center;transition:transform .1s linear}',
    '.rp-antenna{width:3px;height:10px;background:var(--c);margin:0 auto -1px;position:relative;border-radius:2px}',
    '.rp-antenna::after{content:"";position:absolute;top:-5px;left:50%;transform:translateX(-50%);width:7px;height:7px;border-radius:50%;background:#f59e0b;box-shadow:0 0 6px #f59e0b;animation:rp-blink 2s infinite}',
    '.rp-head{width:50px;height:40px;border-radius:14px;background:linear-gradient(160deg,var(--c2),var(--c));margin:0 auto;position:relative;box-shadow:inset 0 -5px 0 rgba(0,0,0,.10)}',
    '.rp-eye{position:absolute;top:14px;width:8px;height:8px;border-radius:50%;background:#fff;animation:rp-eyeblink 4s infinite}',
    '.rp-eye.l{left:12px}.rp-eye.r{right:12px}',
    '.rp-mouth{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);width:14px;height:4px;border-radius:0 0 7px 7px;background:rgba(255,255,255,.9)}',
    '.rp-body{width:40px;height:20px;border-radius:8px;background:linear-gradient(160deg,var(--c2),var(--c));margin:3px auto 0;position:relative}',
    '.rp-chest{position:absolute;top:5px;left:50%;transform:translateX(-50%);width:12px;height:6px;border-radius:3px;background:rgba(255,255,255,.6)}',
    '.rp-tool{position:absolute;right:0;bottom:26px;font-size:18px;filter:drop-shadow(0 2px 3px rgba(0,0,0,.18))}',
    '.rp-legs{display:flex;gap:7px;justify-content:center;margin-top:1px}',
    '.rp-leg{width:6px;height:8px;background:var(--c);border-radius:0 0 3px 3px}',
    '.rp-ch.walking .rp-leg{animation:rp-step .4s infinite}.rp-ch.walking .rp-leg.r{animation-delay:.2s}',
    '.rp-ch.reacting .rp-head{box-shadow:inset 0 -5px 0 rgba(0,0,0,.10),0 0 0 4px color-mix(in srgb,var(--c) 22%,transparent),0 0 16px 2px var(--c)}',
    '.rp-ch.reacting .rp-tool{animation:rp-toolspin .8s linear infinite}',
    '.rp-label{position:absolute;top:100%;left:50%;transform:translateX(-50%);margin-top:1px;font-size:9.5px;font-weight:700;color:#334155;white-space:nowrap;background:rgba(255,255,255,.8);padding:0 5px;border-radius:6px}',
    // speech bubble
    '.rp-bubble{position:absolute;bottom:100%;left:50%;transform:translateX(-50%) translateY(-2px);background:#fff;border:1px solid #e5e7eb;border-radius:11px;padding:4px 9px;font-size:11px;font-weight:600;color:#1e293b;white-space:nowrap;box-shadow:0 6px 16px rgba(2,6,23,.14);opacity:0;pointer-events:none;transition:opacity .25s,transform .25s;z-index:60}',
    '.rp-bubble.show{opacity:1;transform:translateX(-50%) translateY(-8px)}',
    '.rp-bubble::after{content:"";position:absolute;top:100%;left:50%;transform:translateX(-50%);border:5px solid transparent;border-top-color:#fff}',
    // reports
    '.rp-reports{position:absolute;top:8px;right:8px;width:min(300px,60%);display:flex;flex-direction:column;gap:7px;z-index:70;pointer-events:none}',
    '.rp-report{display:flex;gap:9px;align-items:flex-start;background:#fff;border:1px solid #e5e7eb;border-left:4px solid #2563eb;border-radius:11px;padding:8px 10px;box-shadow:0 8px 22px rgba(2,6,23,.14);animation:rp-report-in .45s ease;transition:opacity .5s,transform .5s}',
    '.rp-report[data-tone="green"]{border-left-color:#16a34a}.rp-report[data-tone="violet"]{border-left-color:#7c3aed}.rp-report[data-tone="cyan"]{border-left-color:#0891b2}.rp-report[data-tone="pink"]{border-left-color:#db2777}',
    '.rp-report.rp-out{opacity:0;transform:translateX(28px)}',
    '.rp-report-ic{font-size:19px;line-height:1.1;flex:none}.rp-report-t{font-size:12px;color:#0f172a;line-height:1.35}.rp-report-m{font-size:10.5px;color:#64748b;margin-top:2px}',
    // log
    '.rp-logcard{margin-top:14px;border:1px solid var(--border,#e5e7eb);border-radius:14px;background:var(--card,#fff);overflow:hidden}',
    '.rp-logcard-h{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 14px;border-bottom:1px solid var(--border,#e5e7eb)}',
    '.rp-log{padding:4px 14px 8px;max-height:360px;overflow:auto}',
    // compact + big
    '.rp-office.rp-compact{padding:10px 12px 12px}.rp-office.rp-compact .rp-room{height:220px}',
    '.rp-office.rp-compact .rp-reports,.rp-office.rp-compact .rp-board,.rp-office.rp-compact .rp-stats,.rp-office.rp-compact .rp-rankboard{display:none}',
    '.rp-office.rp-big{border:none;background:transparent;padding:0}.rp-office.rp-big .rp-room{height:min(460px,60vh)}',
    // modal
    '.rp-modal{position:fixed;inset:0;background:rgba(15,23,42,.55);z-index:9999;display:grid;place-items:center;padding:18px;animation:rp-fade .2s}',
    '.rp-modal-win{width:min(1040px,96vw);max-height:92vh;overflow:auto;background:var(--card,#fff);border-radius:16px;box-shadow:0 30px 80px rgba(2,6,23,.5)}',
    '.rp-modal-bar{display:flex;align-items:center;gap:10px;padding:11px 14px;border-bottom:1px solid var(--border,#e5e7eb);position:sticky;top:0;background:inherit;z-index:2}',
    '.rp-modal-dots{display:flex;gap:6px}.rp-modal-dots i{width:11px;height:11px;border-radius:50%;background:#e2e8f0}',
    '.rp-modal-dots i:nth-child(1){background:#ff5f57}.rp-modal-dots i:nth-child(2){background:#febc2e}.rp-modal-dots i:nth-child(3){background:#28c840}',
    '.rp-modal-title{font-weight:700;font-size:14px;color:#0f172a}',
    '.rp-modal-x{margin-left:auto;border:none;background:transparent;font-size:16px;cursor:pointer;color:#64748b;padding:4px 8px;border-radius:8px}.rp-modal-x:hover{background:rgba(100,116,139,.14)}',
    '.rp-modal-body{padding:14px}',
    // keyframes
    '@keyframes rp-walkbob{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}',
    '@keyframes rp-step{0%,100%{transform:translateY(0)}50%{transform:translateY(-4px)}}',
    '@keyframes rp-toolspin{to{transform:rotate(360deg)}}',
    '@keyframes rp-blink{0%,90%,100%{opacity:1}95%{opacity:.25}}',
    '@keyframes rp-eyeblink{0%,92%,100%{transform:scaleY(1)}96%{transform:scaleY(.12)}}',
    '@keyframes rp-report-in{from{transform:translateX(28px);opacity:0}to{transform:translateX(0);opacity:1}}',
    '@keyframes rp-fade{from{opacity:0}to{opacity:1}}',
    '@media (prefers-color-scheme:dark){',
    '.rp-office{background:#0b1222;border-color:#1e2b4a}.rp-room{border-color:#1e2b4a}',
    '.rp-wall{background:linear-gradient(180deg,#111c34,#0e1830)}.rp-floor2{background:linear-gradient(180deg,#12203c,#0d1730)}',
    '.rp-board{background:#0f172a;border-color:#25324f}.rp-board-t{color:#cbd5e1}.rp-board-steps{color:#e2e8f0}.rp-board-steps span{background:#1e293b;color:#a5b4fc}',
    '.rp-report{background:#0f172a;border-color:#1e293b}.rp-report-t{color:#e2e8f0}',
    '.rp-bubble{background:#0f172a;border-color:#1e293b;color:#e2e8f0}.rp-bubble::after{border-top-color:#0f172a}',
    '.rp-label{color:#cbd5e1;background:rgba(15,23,42,.7)}.rp-office-title{color:#cbd5e1}.rp-modal-title{color:#e2e8f0}',
    '.rp-pill{background:rgba(15,23,42,.8);border-color:#1e293b;color:#cbd5e1}.rp-logcard{background:#0f172a;border-color:#1e293b}',
    '}'
  ].join('\n');

})(window.RP);
