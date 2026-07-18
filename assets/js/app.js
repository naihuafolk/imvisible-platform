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
      { id: 'dashboard', code: '', ico: '📊', lbl: 'แดชบอร์ดหลัก' }
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
      { id: 'report', code: '', ico: '📑', lbl: 'รายงาน & Roadmap' }
    ]},
    { section: 'ระบบ', items: [
      { id: 'projects', code: '', ico: '🗂️', lbl: 'จัดการโปรเจ็ค' },
      { id: 'settings', code: '', ico: '⚙️', lbl: 'การตั้งค่า' }
    ]}
  ];

  var TITLES = {
    dashboard: 'แดชบอร์ดหลัก',
    m1: 'M1 · ขุดคำถาม & คีย์เวิร์ด',
    m2: 'M2 · โรงงานคอนเทนต์',
    m3: 'M3 · AEO Optimizer',
    m4: 'M4 · เผยแพร่อัตโนมัติ',
    m5: 'M5 · วัดผล & Rank Tracker',
    m6: 'M6 · Learning Loop',
    report: 'รายงาน & Roadmap',
    projects: 'จัดการโปรเจ็ค',
    settings: 'การตั้งค่า'
  };

  function currentRoute() {
    var h = (location.hash || '').replace(/^#\/?/, '');
    return RP.views[h] ? h : 'dashboard';
  }

  function renderSidebar() {
    var navHtml = NAV.map(function (grp) {
      return '<div class="nav-section">' + grp.section + '</div>' +
        grp.items.map(function (it) {
          return '<button class="nav-item" data-route="' + it.id + '">' +
            '<span class="ico">' + it.ico + '</span>' +
            '<span class="lbl">' + it.lbl + '</span>' +
            (it.code ? '<span class="code">' + it.code + '</span>' : '') +
            '</button>';
        }).join('');
    }).join('');

    return '<div class="brand">' +
        '<div class="logo">I</div>' +
        '<div><div class="name">Im<span>Visible</span></div>' +
        '<div class="tag">AEO + SEO · อัตโนมัติด้วย AI</div></div>' +
      '</div>' +
      '<nav class="nav">' + navHtml + '</nav>' +
      '<div class="sidebar-foot">' + userChip() +
        '<div class="small soft">เอกสารโครงการ v' + RP.data.meta.version + ' · ระบบทำงานเองได้ ~' + RP.data.meta.autoLevel + '%</div></div>';
  }

  function userChip() {
    var u = (RP.auth && RP.auth.user()) || { email: 'ผู้ใช้เดโม' };
    var initial = (u.email || 'U').charAt(0).toUpperCase();
    return '<div class="user-chip"><div class="ua">' + initial + '</div>' +
      '<div class="uinfo"><div class="un">' + RP.esc(u.email) + '</div><div class="ur">' + RP.esc(RP.data.account.plan) + '</div></div>' +
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

  function startApp() {
    document.getElementById('sidebar').innerHTML = renderSidebar();
    wireNav(); wireUser();
    document.getElementById('scrim').onclick = closeMobileNav;

    window.removeEventListener('hashchange', mountRoute);
    window.addEventListener('hashchange', mountRoute);
    if (!location.hash) location.hash = '#/dashboard';
    mountRoute();

    // ครั้งแรก: แสดง onboarding ตามลำดับ
    if (RP.auth && !RP.auth.onboarded()) setTimeout(function () { if (RP.showOnboarding) RP.showOnboarding(); }, 350);
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
