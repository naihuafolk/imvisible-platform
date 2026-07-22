/* ============================================================
   View: กิจกรรมสด (Live Activity) — ไทม์ไลน์เรียลไทม์ของบัญชี
   อ่านอย่างเดียว · เห็นเฉพาะโปรเจ็คของตัวเอง · อัปเดตอัตโนมัติทุก 8 วิ
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
          'พอระบบเริ่มผลิต/เผยแพร่/วัดผล รายการจะขึ้นที่นี่แบบเรียลไทม์ — ลองกด "ผลิตบทความ" ที่ M2 หรือรอ beat ทำงานตามเวลา')
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
      desc: 'ดูว่าระบบกำลังทำอะไรอยู่ — เขียนบทความ เผยแพร่ วัดอันดับ และวัด AI citation · อัปเดตอัตโนมัติทุก 8 วินาที'
    });
    html += '<div id="act_slot">' + (RP.isReal()
      ? '<div class="hint">กำลังโหลดกิจกรรม…</div>'
      : RP.sampleNotice('หน้ากิจกรรมสด') + feedCard(SAMPLE)) + '</div>';
    return { html: html, mount: mountLive };
  };

  RP._activity = { card: feedCard, mount: mountLive };   // ให้แดชบอร์ดเอาไปฝังการทำงานสด

  function mountLive(root) {
    if (RP._actTimer) { clearInterval(RP._actTimer); RP._actTimer = null; }
    if (!RP.isReal() || !RP.api.enabled()) return;
    function load() {
      var slot = document.getElementById('act_slot');
      if (!slot) { if (RP._actTimer) { clearInterval(RP._actTimer); RP._actTimer = null; } return; }  // ออกจากหน้าแล้ว
      RP.api.activity(50).then(function (d) {
        var s2 = document.getElementById('act_slot');
        if (s2 && d) s2.innerHTML = feedCard(d);
      }).catch(function () {});
    }
    load();
    RP._actTimer = setInterval(load, 8000);
  }
})(window.RP);
