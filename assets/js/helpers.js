/* ============================================================
   RankPilot AI — Shared helpers
   Global namespace: window.RP = { data, views, ui, fmt, ... }
   All view modules read RP.data and use RP.ui.* helpers.
   Load order: helpers.js -> data.js -> views/*.js -> app.js
   ============================================================ */
window.RP = window.RP || { data: {}, views: {}, ui: {} };

(function (RP) {
  'use strict';

  /* ---- number / text formatting ---- */
  RP.fmt = {
    n: function (v) {
      if (v === null || v === undefined || v === '') return '—';
      return Number(v).toLocaleString('en-US');
    },
    pct: function (v, d) { return (d != null ? Number(v).toFixed(d) : v) + '%'; },
    baht: function (v) { return '฿' + Number(v).toLocaleString('en-US'); },
    clamp: function (v, a, b) { return Math.max(a, Math.min(b, v)); }
  };

  /* ---- html escape ---- */
  RP.esc = function (s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  };

  /* ---- component builders (return HTML strings) ---- */
  var ui = RP.ui;

  ui.pageHead = function (o) {
    return '<div class="page-head">' +
      (o.eyebrow ? '<div class="eyebrow">' + RP.esc(o.eyebrow) + '</div>' : '') +
      '<h1>' + RP.esc(o.title) + '</h1>' +
      (o.desc ? '<p>' + o.desc + '</p>' : '') +
      '<div class="accent-bar"></div></div>';
  };

  ui.kpi = function (o) {
    var cls = o.tone === 'pos' ? 'pos' : (o.tone === 'brand' ? 'brand' : '');
    return '<div class="kpi"><div class="k-label">' + RP.esc(o.label) + '</div>' +
      '<div class="k-value ' + cls + '">' + o.value + '</div>' +
      (o.foot ? '<div class="k-foot">' + o.foot + '</div>' : '') + '</div>';
  };

  ui.badge = function (text, tone, dot) {
    return '<span class="badge ' + (tone || '') + (dot ? ' dot' : '') + '">' + text + '</span>';
  };

  ui.card = function (o) {
    var head = '';
    if (o.title) {
      head = '<div class="card-head"><h3>' + RP.esc(o.title) + '</h3>' +
        (o.sub ? '<span class="sub">' + RP.esc(o.sub) + '</span>' : '') +
        '<span class="spacer"></span>' + (o.action || '') + '</div>';
    }
    return '<div class="card ' + (o.cls || '') + '">' + head +
      '<div class="' + (o.flush ? '' : 'card-pad') + '">' + (o.body || '') + '</div></div>';
  };

  ui.bar = function (pct, tone) {
    return '<div class="bar ' + (tone || '') + '"><span style="width:' +
      RP.fmt.clamp(pct, 0, 100) + '%"></span></div>';
  };

  ui.trend = function (dir, txt) {
    if (dir === 'up') return '<span class="trend up">▲ ' + RP.esc(txt) + '</span>';
    if (dir === 'down') return '<span class="trend down">▼ ' + RP.esc(txt) + '</span>';
    return '<span class="trend same">– ' + RP.esc(txt) + '</span>';
  };

  ui.scorePill = function (score) {
    var c = score >= 70 ? 'hi' : (score >= 45 ? 'mid' : 'low');
    return '<span class="score-pill ' + c + '">' + score + '</span>';
  };

  // opportunity score -> difficulty label
  ui.diffLabel = function (kd) {
    if (kd <= 30) return { t: 'แข่งขันต่ำ', c: 'green' };
    if (kd <= 55) return { t: 'แข่งขันกลาง', c: 'amber' };
    return { t: 'แข่งขันสูง', c: 'red' };
  };

  /* ---- sparkline (inline svg) ---- */
  ui.spark = function (values, opts) {
    opts = opts || {};
    var w = opts.w || 120, h = opts.h || 34, pad = 3;
    var min = Math.min.apply(null, values), max = Math.max.apply(null, values);
    var span = (max - min) || 1;
    var step = (w - pad * 2) / (values.length - 1);
    var pts = values.map(function (v, i) {
      var x = pad + i * step;
      var y = h - pad - ((v - min) / span) * (h - pad * 2);
      return x.toFixed(1) + ',' + y.toFixed(1);
    });
    var color = opts.color || 'var(--brand-600)';
    var last = pts[pts.length - 1].split(',');
    return '<svg class="spark" width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + ' ' + h + '">' +
      '<polyline fill="none" stroke="' + color + '" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="' + pts.join(' ') + '"/>' +
      '<circle cx="' + last[0] + '" cy="' + last[1] + '" r="2.6" fill="' + color + '"/></svg>';
  };

  /* ---- vertical bar chart ---- */
  ui.vbars = function (items) { // items: [{cap, val, max, label}]
    var max = Math.max.apply(null, items.map(function (i) { return i.max || i.val; }));
    return '<div class="vbars">' + items.map(function (i) {
      var pct = (i.val / (max || 1)) * 100;
      return '<div class="col"><div class="val">' + (i.label || i.val) + '</div>' +
        '<div class="bar-v" style="height:' + RP.fmt.clamp(pct, 2, 100) + '%"></div>' +
        '<div class="cap">' + RP.esc(i.cap) + '</div></div>';
    }).join('') + '</div>';
  };

  /* ---- modal ---- */
  var modalEl = null;
  ui.modal = function (o) {
    ui.closeModal();
    modalEl = document.createElement('div');
    modalEl.className = 'modal-back';
    modalEl.innerHTML =
      '<div class="modal" style="max-width:' + (o.width || 720) + 'px" role="dialog" aria-modal="true">' +
      '<div class="modal-head"><div><h3>' + o.title + '</h3>' +
      (o.sub ? '<div class="sub">' + o.sub + '</div>' : '') + '</div>' +
      '<button class="icon-btn modal-close" aria-label="ปิด">✕</button></div>' +
      '<div class="modal-body">' + o.body + '</div></div>';
    document.body.appendChild(modalEl);
    modalEl.querySelector('.modal-close').onclick = ui.closeModal;
    modalEl.onclick = function (e) { if (e.target === modalEl) ui.closeModal(); };
    requestAnimationFrame(function () { modalEl.classList.add('open'); });
    document.addEventListener('keydown', escClose);
  };
  function escClose(e) { if (e.key === 'Escape') ui.closeModal(); }
  ui.closeModal = function () {
    if (!modalEl) return;
    var el = modalEl; modalEl = null;
    el.classList.remove('open');
    document.removeEventListener('keydown', escClose);
    setTimeout(function () { el.remove(); }, 180);
  };

  /* ---- toast ---- */
  ui.toast = function (msg, ms) {
    var wrap = document.querySelector('.toast-wrap');
    if (!wrap) { wrap = document.createElement('div'); wrap.className = 'toast-wrap'; document.body.appendChild(wrap); }
    var t = document.createElement('div'); t.className = 'toast'; t.innerHTML = msg;
    wrap.appendChild(t);
    setTimeout(function () { t.style.opacity = '0'; t.style.transition = 'opacity .3s'; setTimeout(function () { t.remove(); }, 320); }, ms || 2400);
  };

  /* ---- small helpers ---- */
  RP.by = function (arr, key, val) { return arr.filter(function (x) { return x[key] === val; }); };
  RP.sum = function (arr, f) { return arr.reduce(function (a, x) { return a + f(x); }, 0); };

})(window.RP);
