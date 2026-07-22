/* ============================================================
   RankPilot AI — App shell / router / navigation
   View contract:
     RP.views.<id> = function () {
        return { html: '<...>', mount: function(rootEl){ attach listeners } };
     }
   ============================================================ */
(function (RP) {
  'use strict';

  var NAV = [
    { section: 'ภาพรวม', items: [
      { id: 'dashboard', code: '', ico: '📊', lbl: 'แดชบอร์ดหลัก' },
      { id: 'activity', code: '', ico: '⚡', lbl: 'กิจกรรมสด' }
    ]},
    { section: 'โมดูลของแพลตฟอร์ม', items: [
      { id: 'm1', code: 'M1', ico: '🔎', lbl: 'ขุดคำถาม & คีย์เวิร์ด' },
      { id: 'm2', code: 'M2', ico: '🏭', lbl: 'โรงงานคอนเทนต์' },
      { id: 'm3', code: 'M3', ico: '⚙️', lbl: 'AEO Optimizer' },
      { id: 'm4', code: 'M4', ico: '🚀', lbl: 'เผยแพร่อัตโนมัติ' },
      { id: 'm5', code: 'M5', ico: '📈', lbl: 'วัดผล & Rank Tracker' },
      { id: 'm6', code: 'M6', ico: '🧠', lbl: 'Learning Loop' }
    ]},
    { section: 'รายงาน', items: [
      { id: 'report', code: '', ico: '📑', lbl: 'รายงานผลงาน' },
      { id: 'blog', code: '', ico: '🌐', lbl: 'บล็อก & การเข้าถึง' }
    ]},
    { section: 'ระบบ', items: [
      { id: 'projects', code: '', ico: '🗂️', lbl: 'จัดการโปรเจ็ค' },
      { id: 'settings', code: '', ico: '⚙️', lbl: 'การตั้งค่า' }
    ]}
  ];

  var TITLES = {
    dashboard: 'แดชบอร์ดหลัก',
    activity: 'กิจกรรมสด',
    m1: 'M1 · ขุดคำถาม & คีย์เวิร์ด',
    m2: 'M2 · โรงงานคอนเทนต์',
    m3: 'M3 · AEO Optimizer',
    m4: 'M4 · เผยแพร่อัตโนมัติ',
    m5: 'M5 · วัดผล & Rank Tracker',
    m6: 'M6 · Learning Loop',
    report: 'รายงานผลงาน',
    blog: 'บล็อก & การเข้าถึง',
    projects: 'จัดการโปรเจ็ค',
    settings: 'การตั้งค่า'
  };

  function currentRoute() {
    var h = (location.hash || '').replace(/^#\/?/, '');
    return RP.views[h] ? h : 'dashboard';
  }

  /* เมนูตามบัญชี: บัญชีจริง = มินิมอลสุด (ภาพรวม + จัดการ + ตั้งค่า) · M1–M6 = เครื่องยนต์เบื้องหลัง ยุบไว้ใต้ "ขั้นสูง" */
  function navGroups() {
    if (!(RP.isReal && RP.isReal())) return NAV;   // โหมดตัวอย่าง = โชว์ครบเพื่อพรีวิว
    var by = {};
    NAV.forEach(function (g) { g.items.forEach(function (it) { by[it.id] = it; }); });
    return [
      { section: 'ภาพรวม', items: [by.dashboard, by.report, by.blog, by.activity] },
      { section: 'โปรเจ็ค', items: [by.projects] },
      { section: 'ระบบ', items: [by.settings] },
      { section: 'เครื่องมือ (ขั้นสูง)', collapsed: true, items: [by.m1, by.m2, by.m3, by.m4, by.m5, by.m6] }
    ];
  }

  function projCount() {
    return ((RP.data.project && RP.data.project.list) || []).filter(function (p) {
      return !(RP.isReal && RP.isReal()) || /^db/.test(String(p && p.id));
    }).length;
  }
  function navTag(id) {
    if (id === 'activity') return '<span class="n-tag live">Live</span>';
    if (id === 'projects' || id === 'blog') { var n = projCount(); if (n) return '<span class="n-tag count">' + n + '</span>'; }
    return '';
  }
  function renderSidebar() {
    var navHtml = navGroups().map(function (grp) {
      var items = grp.items.filter(Boolean).map(function (it) {
        return '<button class="nav-item" data-route="' + it.id + '">' +
          '<span class="ico">' + it.ico + '</span>' +
          '<span class="lbl">' + it.lbl + '</span>' +
          navTag(it.id) +
          (it.code ? '<span class="code">' + it.code + '</span>' : '') +
          '</button>';
      }).join('');
      if (grp.collapsed) {
        return '<details class="nav-adv"><summary class="nav-section" style="cursor:pointer;list-style:disclosure-closed">' +
          grp.section + '</summary>' + items + '</details>';
      }
      return '<div class="nav-section">' + grp.section + '</div>' + items;
    }).join('');

    return '<div class="brand">' +
        '<div class="logo">I</div>' +
        '<div><div class="name">Im<span>Visible</span></div>' +
        '<div class="tag">AEO + SEO · อัตโนมัติด้วย AI</div></div>' +
      '</div>' +
      '<nav class="nav">' + navHtml + '</nav>' +
      '<div class="sidebar-foot">' + userChip() +
        '<div class="small soft">ImVisible · AEO + SEO อัตโนมัติด้วย AI</div></div>';
  }

  function userChip() {
    var u = (RP.auth && RP.auth.user()) || { email: 'ผู้ใช้เดโม', real: false };
    var initial = (u.email || 'U').charAt(0).toUpperCase();
    var badge = u.real
      ? '<span style="color:var(--green-600);font-weight:700">● บัญชีจริง</span>'
      : '<span style="color:var(--amber-600);font-weight:700">● โหมดตัวอย่าง</span>';
    return '<div class="user-chip"><div class="ua">' + initial + '</div>' +
      '<div class="uinfo"><div class="un">' + RP.esc(u.email) + '</div><div class="ur">' + badge + '</div></div>' +
      '<button class="icon-btn" id="logoutBtn" title="ออกจากระบบ" style="width:32px;height:32px">⎋</button></div>';
  }

  function projectSelector() {
    var p = RP.data.project;
    return '<select class="select" id="projSel" aria-label="เลือกโปรเจ็ค">' +
      p.list.map(function (x) {
        return '<option value="' + x.id + '"' + (x.id === p.current ? ' selected' : '') + '>โปรเจ็ค: ' + RP.esc(x.name) + '</option>';
      }).join('') + '</select>';
  }

  function modePill() {
    var cur = RP.data.project.list.filter(function (x) { return x.id === RP.data.project.current; })[0];
    var auto = cur && cur.mode === 'auto';
    return '<span class="mode-pill" id="modePill" title="สลับโหมดเผยแพร่">' +
      '<span class="dot" style="background:' + (auto ? 'var(--green-500)' : 'var(--amber-500)') + '"></span>' +
      (auto ? 'Full-Auto 100%' : 'Auto + Human Approve') + '</span>';
  }

  function renderTopbar(route) {
    return '<button class="icon-btn mobile-nav-btn" id="mNav" aria-label="เมนู">☰</button>' +
      '<div class="crumbs">ImVisible <span class="soft">/</span> <b>' + (TITLES[route] || '') + '</b></div>' +
      '<span class="spacer"></span>' +
      projectSelector() +
      modePill() +
      '<button class="icon-btn" id="themeBtn" aria-label="สลับธีม" title="สลับสว่าง/มืด">🌙</button>';
  }

  function mountRoute() {
    var route = currentRoute();
    var contentEl = document.getElementById('content');
    var topbarEl = document.getElementById('topbar');

    topbarEl.innerHTML = renderTopbar(route);
    wireTopbar();

    // active nav
    Array.prototype.forEach.call(document.querySelectorAll('.nav-item'), function (b) {
      b.classList.toggle('active', b.getAttribute('data-route') === route);
    });

    var factory = RP.views[route];
    var out;
    try {
      out = factory();
    } catch (e) {
      out = { html: errorCard(route, e), mount: null };
      console.error('View render error:', route, e);
    }
    contentEl.innerHTML = '<div class="view">' + (out && out.html ? out.html : '') + '</div>';
    if (out && typeof out.mount === 'function') {
      try { out.mount(contentEl); } catch (e2) { console.error('View mount error:', route, e2); }
    }
    contentEl.scrollTop = 0;
    window.scrollTo(0, 0);
    closeMobileNav();
  }

  function errorCard(route, e) {
    return '<div class="warn-box"><b>โหลดหน้า "' + route + '" ไม่สำเร็จ</b><br>' +
      RP.esc(e && e.message ? e.message : String(e)) + '</div>';
  }

  /* ---- interactions ---- */
  function wireNav() {
    Array.prototype.forEach.call(document.querySelectorAll('.nav-item'), function (b) {
      b.onclick = function () { location.hash = '#/' + b.getAttribute('data-route'); };
    });
  }

  function wireTopbar() {
    var sel = document.getElementById('projSel');
    if (sel) sel.onchange = function () {
      RP.data.project.current = sel.value;
      RP.ui.toast('สลับโปรเจ็คเป็น <b>' + RP.esc(sel.options[sel.selectedIndex].text.replace('โปรเจ็ค: ', '')) + '</b>');
      document.getElementById('modePill').outerHTML = modePill();
      mountRoute();
    };
    var mp = document.getElementById('modePill');
    if (mp) mp.onclick = function () {
      var cur = RP.data.project.list.filter(function (x) { return x.id === RP.data.project.current; })[0];
      if (!cur) { RP.ui.toast('เลือกโปรเจ็คก่อน'); return; }   // กัน null-deref เมื่อยังไม่มีโปรเจ็ค
      cur.mode = cur.mode === 'auto' ? 'approve' : 'auto';
      mp.outerHTML = modePill();
      RP.ui.toast('โหมดเผยแพร่: <b>' + (cur.mode === 'auto' ? 'Full-Auto 100%' : 'Auto + Human Approve') + '</b>');
      wireTopbar();
    };
    var tb = document.getElementById('themeBtn');
    if (tb) {
      tb.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙';
      tb.onclick = toggleTheme;
    }
    var mn = document.getElementById('mNav');
    if (mn) mn.onclick = openMobileNav;
  }

  function toggleTheme() {
    var root = document.documentElement;
    var dark = root.getAttribute('data-theme') === 'dark';
    root.setAttribute('data-theme', dark ? 'light' : 'dark');
    try { localStorage.setItem('rp-theme', dark ? 'light' : 'dark'); } catch (e) {}
    document.getElementById('themeBtn').textContent = dark ? '🌙' : '☀️';
  }

  function openMobileNav() {
    document.querySelector('.sidebar').classList.add('open');
    document.getElementById('scrim').classList.add('show');
  }
  function closeMobileNav() {
    var sb = document.querySelector('.sidebar'); if (sb) sb.classList.remove('open');
    var sc = document.getElementById('scrim'); if (sc) sc.classList.remove('show');
  }

  /* ---- boot ---- */
  function boot() {
    try {
      var saved = localStorage.getItem('rp-theme');
      if (saved) document.documentElement.setAttribute('data-theme', saved);
    } catch (e) {}

    // โหมดใช้งานจริง: ต้องเข้าสู่ระบบก่อน
    if (RP.auth && !RP.auth.user()) { RP.showLogin(startApp); return; }
    startApp();
  }

  function renderShell() {
    document.getElementById('sidebar').innerHTML = renderSidebar();
    wireNav(); wireUser();
    document.getElementById('scrim').onclick = closeMobileNav;

    window.removeEventListener('hashchange', mountRoute);
    window.addEventListener('hashchange', mountRoute);
    if (!location.hash) location.hash = '#/dashboard';
    mountRoute();
  }

  function startApp() {
    // บัญชีจริง → โหลดโปรเจ็ค/สถานะจริงจาก backend ก่อนค่อยเรนเดอร์
    if (RP.auth && RP.auth.isReal() && RP.loadRealData) {
      RP.loadRealData(function (ok, n) {
        if (!ok && (!RP.auth.isReal())) { RP.showLogin(startApp); return; }  // token หมดอายุ → login ใหม่
        renderShell();
        if (ok && !n && RP.showRealOnboarding) setTimeout(function () { RP.showRealOnboarding(); }, 300);
      });
      return;
    }
    // โหมดตัวอย่าง (เดโม)
    renderShell();
    if (RP.auth && !RP.auth.onboarded() && RP.showOnboarding) setTimeout(function () { RP.showOnboarding(); }, 350);
  }

  function wireUser() {
    var lo = document.getElementById('logoutBtn');
    if (lo) lo.onclick = function () { if (RP.auth) RP.auth.logout(); if (RP.api) RP.api.setToken(''); location.reload(); };
  }

  RP.go = function (route) { location.hash = '#/' + route; };
  RP.boot = boot;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else { boot(); }

})(window.RP);
