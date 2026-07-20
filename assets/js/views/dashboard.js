/* ============================================================
   View: แดชบอร์ดหลัก (Main Dashboard) — ตรงกับ Wireframe หน้า 6
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  /* บล็อกที่ยังเป็นข้อมูลตัวอย่าง → บัญชีจริงเห็น "ยังไม่มีข้อมูล" ในการ์ดแทน */
  function gateCard(sampleHtml, title, hint, cta) {
    var out = RP.realOr(sampleHtml, { title: title, hint: hint, cta: cta });
    if (!RP.isReal()) return out;
    return '<div class="card mb">' + out + '</div>';
  }

  function setupCta(label) {
    return '<button class="btn btn-sm btn-primary gate-setup">' + esc(label || 'ไปที่การตั้งค่าการเชื่อมต่อ →') + '</button>';
  }

  function statusBadge(c) {
    if (c.status === 'loop') return ui.badge('● Loop ทำงานอยู่', 'green');
    if (c.status === 'producing') return ui.badge('กำลังผลิตคอนเทนต์', 'purple');
    if (c.status === 'approve') return ui.badge('รออนุมัติ ' + (c.pending || 0) + ' บทความ', 'amber');
    return ui.badge('—');
  }

  function citedCell(c) {
    if (!c.cited || !c.cited.length) return '<span class="soft">ยังไม่ติด</span>';
    return c.cited.map(function (e) {
      return '<span class="b" style="color:var(--green-600)">' + esc(e) + ' ✓</span>';
    }).join(' &nbsp; ');
  }

  function clusterTable() {
    var rows = RP.data.clusters.map(function (c) {
      return '<tr>' +
        '<td><span class="tbl-title">' + esc(c.name) + '</span></td>' +
        '<td class="num">' + c.articles + '<span class="soft">/' + c.total + '</span></td>' +
        '<td class="num">' + (c.avgRank == null ? '<span class="soft">—</span>' : c.avgRank.toFixed(1)) + '</td>' +
        '<td>' + citedCell(c) + '</td>' +
        '<td>' + statusBadge(c) + '</td>' +
        '<td class="right"><button class="link-btn" data-cluster="' + c.id + '">ดูคีย์เวิร์ด ›</button></td>' +
        '</tr>';
    }).join('');

    return '<div class="tbl-wrap"><table class="tbl">' +
      '<thead><tr><th>คลัสเตอร์</th><th>บทความ</th><th>อันดับเฉลี่ย</th><th>ถูก AI อ้างอิง</th><th>สถานะระบบ</th><th></th></tr></thead>' +
      '<tbody>' + rows + '</tbody></table></div>';
  }

  function loopStepper() {
    var steps = RP.data.loop;
    return '<div class="loop">' + steps.map(function (s, i) {
      return '<div class="step"><div class="n">' + esc(s.n) + '</div>' +
        '<div class="t">' + esc(s.t) + '</div><div class="d">' + esc(s.d) + '</div></div>' +
        (i < steps.length - 1 ? '<div class="arrow">→</div>' : '');
    }).join('') + '</div>';
  }

  function sovPanel() {
    var ci = RP.data.m5.citation;
    var rows = ci.competitors.map(function (c) {
      return '<div class="list-row"><div class="grow"><div class="t">' +
        (c.us ? '<span style="color:var(--brand-700)">★ </span>' : '') + esc(c.name) + '</div>' +
        ui.bar(c.sov * 2.2, c.us ? '' : 'green') + '</div>' +
        '<div class="bb" style="min-width:44px;text-align:right">' + c.sov + '%</div></div>';
    }).join('');
    return rows;
  }

  function weeklyPanel() {
    var w = RP.data.m6.weeklyReport;
    var items = [
      ['เผยแพร่', w.published + ' บทความ'],
      ['ติดหน้า 1 ใหม่', w.newPage1 + ' คีย์เวิร์ด'],
      ['Citation เพิ่ม', '+' + w.citationsGained],
      ['รีเฟรชหน้าเก่า', w.refreshed + ' หน้า'],
      ['เวลาที่คนใช้', w.humanHours + ' ชม.']
    ];
    return items.map(function (x) {
      return '<div class="list-row"><div class="grow"><div class="t small">' + x[0] + '</div></div>' +
        '<div class="bb">' + x[1] + '</div></div>';
    }).join('') +
      '<div class="hint" style="margin-top:10px">ส่งรายงานอัตโนมัติทาง <b>' + esc(w.sentTo) + '</b> ทุกสัปดาห์</div>';
  }

  function gettingStartedCard() {
    var steps = RP.data.onboarding;
    // บัญชีจริง: ห้ามติ๊กถูกว่า "ตั้งค่าเสร็จแล้ว" จากข้อมูลตัวอย่าง — บอกสิ่งที่ต้องทำแทน
    if (RP.isReal()) {
      return ui.card({
        title: '🚀 เริ่มต้นใช้งาน', sub: 'ตรวจสถานะการเชื่อมต่อจริงได้ในหน้าการตั้งค่า', cls: 'mb',
        action: '<button class="btn btn-sm btn-primary" id="gsGo">ไปที่การตั้งค่า →</button>',
        body: '<div class="hint">ระบบจะเริ่มวัดผลจริงได้เมื่อเชื่อมต่อครบ: SERP API (อันดับ Google), ' +
          'Google Search Console, API วัด AI Citation และปลายทางเผยแพร่ · ' +
          'เราแสดงเฉพาะสถานะจริงจากบัญชีของคุณเท่านั้น</div>'
      });
    }
    var done = steps.filter(function (s) { return s.done; }).length;
    if (done >= steps.length) return '';
    var rows = steps.map(function (s) {
      return '<div class="gs-row ' + (s.done ? 'done' : '') + '"><div class="gk ' + (s.done ? 'done' : 'todo') + '">' + (s.done ? '✓' : '○') + '</div><div class="gt">' + esc(s.t) + '</div></div>';
    }).join('');
    return ui.card({
      title: '🚀 เริ่มต้นใช้งาน', sub: 'อีก ' + (steps.length - done) + ' ขั้นก็พร้อมวัดผลจริง', cls: 'mb',
      action: '<button class="btn btn-sm btn-primary" id="gsGo">ตั้งค่าให้ครบ →</button>',
      body: '<div style="margin-bottom:12px">' + ui.bar(done / steps.length * 100) + '</div><div class="gs-list">' + rows + '</div>'
    });
  }

  function pfStat(l, v) { return '<div><div class="soft small">' + esc(l) + '</div><div class="bb" style="font-size:22px">' + v + '</div></div>'; }

  /* บัญชีจริง: เห็นเฉพาะโปรเจ็คจากฐานข้อมูลจริง (id ขึ้นต้นด้วย db) — ห้ามให้โปรเจ็คตัวอย่างหลุดเข้าบัญชีจริง */
  function visibleProjects() {
    var list = (RP.data.project && RP.data.project.list) || [];
    if (!RP.isReal()) return list;
    return list.filter(function (p) { return p && /^db/.test(String(p.id)); });
  }

  function currentProject() {
    var list = visibleProjects();
    var cur = (RP.data.project && RP.data.project.current) || '';
    return list.filter(function (x) { return x.id === cur; })[0] || null;
  }

  /* บัญชีจริง: ตัวเลขที่ระบบยังไม่ได้วัด → ขีด ไม่ใช่เลขสมมติ */
  function pfNum(v) {
    if (RP.isReal()) return '<span class="soft" title="ยังไม่มีข้อมูลจริง">—</span>';
    return v;
  }

  function newProjectCta(label) {
    return '<button class="btn btn-sm btn-primary" id="pfNew">' + esc(label || '＋ สร้างโปรเจ็คแรก') + '</button>';
  }

  function portfolioCard() {
    var list = visibleProjects();
    var real = RP.isReal();

    if (!list.length) {
      return ui.card({
        title: 'ภาพรวมทุกโปรเจ็ค', sub: 'บัญชีเดียวดูแลได้หลายเว็บ / หลายลูกค้า', cls: 'mb',
        action: '<button class="btn btn-sm" id="pfManage">จัดการโปรเจ็ค →</button>',
        body: RP.noData('ยังไม่มีโปรเจ็ค',
          'สร้างโปรเจ็คแรก (ชื่อแบรนด์ + โดเมน) เพื่อเริ่มเก็บข้อมูลจริง — เราจะไม่แสดงตัวเลขใด ๆ จนกว่าระบบจะวัดผลได้จริง',
          newProjectCta())
      });
    }

    var kw = RP.sum(list, function (p) { return p.keywords || 0; });
    var cl = RP.sum(list, function (p) { return p.clusters || 0; });
    var tiles = '<div class="row wrap" style="gap:30px">' +
      pfStat('โปรเจ็คทั้งหมด', list.length) + pfStat('คีย์เวิร์ดติดตามรวม', pfNum(fmt.n(kw))) +
      pfStat('คลัสเตอร์รวม', pfNum(cl)) +
      pfStat('แพ็กเกจ', real ? '<span class="soft">—</span>' : esc(RP.data.account.plan)) + '</div>';

    var rows = list.map(function (p) {
      var cur = p.id === RP.data.project.current, h = p.health || {};
      var dots;
      if (real) {
        // ยังไม่ได้ตรวจสถานะการเชื่อมต่อในหน้านี้ → ห้ามวาดไฟเขียวที่ไม่ได้วัด
        dots = '<span class="soft small">ยังไม่ได้ตรวจ</span>';
      } else {
        dots = [h.gsc, h.serp, h.ai, h.publish].map(function (x) {
          return '<span style="width:8px;height:8px;border-radius:50%;display:inline-block;background:' + (x ? 'var(--green-500)' : 'var(--border)') + '"></span>';
        }).join(' ');
      }
      return '<tr><td><span class="bb">' + esc(p.name) + '</span>' + (cur ? ' ' + ui.badge('กำลังใช้', 'green') : '') +
        '<div class="soft small">' + esc(p.domain) + '</div></td>' +
        '<td class="num">' + pfNum(fmt.n(p.keywords || 0)) + '</td><td class="soft">' + (p.mode === 'auto' ? 'Full-Auto' : 'Human Approve') + '</td>' +
        '<td>' + dots + '</td><td class="right">' + (cur ? '<span class="soft small">ปัจจุบัน</span>' : '<button class="link-btn pf-open" data-id="' + p.id + '">เปิด ›</button>') + '</td></tr>';
    }).join('');

    var note = real
      ? '<div class="card-pad soft small" style="padding-top:0">🔌 สถานะการเชื่อมต่อ (GSC · SERP · AI Citation · เผยแพร่): <b>ยังไม่ได้ตรวจสอบในหน้านี้</b> — ดูสถานะจริงได้ที่ ⚙️ การตั้งค่า › การเชื่อมต่อ · ' +
        'จำนวนคีย์เวิร์ด/คลัสเตอร์จะขึ้นหลังระบบเก็บข้อมูลรอบแรก</div>'
      : '';

    return ui.card({
      title: 'ภาพรวมทุกโปรเจ็ค', sub: 'บัญชีเดียวดูแลได้หลายเว็บ / หลายลูกค้า', cls: 'mb', flush: true,
      action: '<button class="btn btn-sm" id="pfManage">จัดการโปรเจ็ค →</button>',
      body: '<div class="card-pad">' + tiles + '</div>' + note +
        '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>โปรเจ็ค</th><th>คีย์เวิร์ด</th><th>โหมด</th><th>สถานะเชื่อมต่อ</th><th></th></tr></thead><tbody>' + rows + '</tbody></table></div>'
    });
  }

  function reDash() { var f = RP.views.dashboard(); var c = document.getElementById('content'); c.innerHTML = '<div class="view">' + f.html + '</div>'; f.mount(c); }

  RP.views.dashboard = function () {
    var p = currentProject();

    var projectBar;
    if (!p) {
      // ไม่มีโปรเจ็คที่แสดงได้ (บัญชีจริงที่ยังไม่สร้างโปรเจ็ค) → ห้ามโชว์ชื่อ/โดเมนสมมติเป็นตัวตนลูกค้า
      projectBar = '<div class="card mb"><div class="card-pad row between wrap" style="gap:14px">' +
        '<div class="row" style="gap:12px">' +
        '<div style="width:44px;height:44px;border-radius:12px;background:var(--border);display:grid;place-items:center;font-size:20px">🗂️</div>' +
        '<div><div class="bb" style="font-size:17px">ยังไม่มีโปรเจ็ค</div>' +
        '<div class="soft small">สร้างโปรเจ็ค (ชื่อแบรนด์ + โดเมน) ก่อน แล้วระบบจึงเริ่มเก็บข้อมูลจริงให้</div></div>' +
        '</div>' +
        '<button class="btn btn-primary" id="pbNew">＋ สร้างโปรเจ็ค</button>' +
        '</div></div>';
    } else {
      projectBar = '<div class="card mb"><div class="card-pad row between wrap" style="gap:14px">' +
        '<div class="row" style="gap:12px">' +
        '<div style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,var(--grad-start),var(--grad-end));display:grid;place-items:center;color:#fff;font-size:20px">🏥</div>' +
        '<div><div class="bb" style="font-size:17px">โปรเจ็ค: ' + esc(p.name) + '</div>' +
        '<div class="soft small">' + esc(p.domain) + ' · โหมด ' + (p.mode === 'auto' ? 'Full-Auto' : 'Auto + Human Approve') + '</div></div>' +
        '</div>' +
        '<button class="btn btn-green" id="newCluster">＋ สร้างคลัสเตอร์ใหม่ (Auto)</button>' +
        '</div></div>';
    }

    var kpiGrid = gateCard(
      '<div class="grid grid-4 mb">' + RP.data.kpis.map(function (k) { return ui.kpi(k); }).join('') + '</div>',
      'ยังไม่มีตัวเลข KPI',
      'ตัวเลขบทความที่เผยแพร่ คีย์เวิร์ดติดหน้า 1 AI Citation และทราฟฟิก จะขึ้นหลังเชื่อม SERP API + Google Search Console แล้วระบบเก็บข้อมูลประมาณ 1–7 วัน',
      setupCta()
    );

    var loopCard = ui.card({
      title: 'AI Growth Loop', sub: 'วงจรอัตโนมัติที่หมุนเองและฉลาดขึ้นทุกรอบ (Closed-Loop)',
      body: loopStepper()
    });

    var tableCard = ui.card({
      title: 'คลัสเตอร์ทั้งหมด',
      sub: RP.isReal() ? 'แสดงเฉพาะคลัสเตอร์จริงในโปรเจ็คของคุณ' : (RP.data.clusters.length + ' คลัสเตอร์ · เรียงตามความสำคัญ'),
      flush: true, cls: 'mb',
      action: RP.sampleBadge() + ' <button class="btn btn-sm" id="goM5">ดูรายงานอันดับ →</button>',
      body: RP.realOr(clusterTable(), {
        title: 'ยังไม่มีคลัสเตอร์',
        hint: 'สร้างคลัสเตอร์แรกเพื่อเริ่มผลิตคอนเทนต์ · อันดับเฉลี่ยและสถานะ "ถูก AI อ้างอิง" จะแสดงหลังระบบเก็บข้อมูลอันดับจริง 1–7 วัน',
        cta: '<button class="btn btn-sm btn-primary" id="ndCluster">＋ สร้างคลัสเตอร์ใหม่</button>'
      })
    });

    var twoCol = '<div class="grid mb" style="grid-template-columns:1.5fr 1fr">' +
      ui.card({
        title: 'AI Citation Share of Voice',
        sub: 'ส่วนแบ่งการถูกอ้างอิงบน AI เทียบคู่แข่ง',
        action: RP.sampleBadge(),
        body: RP.realOr(sovPanel(), {
          title: 'ยังไม่มีข้อมูล Share of Voice',
          hint: 'ต้องใส่ชื่อแบรนด์ คู่แข่ง และชุดคำถาม (Prompt Sampling) ก่อน — ระบบจะยิงคำถามจริงไปที่ ChatGPT / Gemini / Perplexity แล้วสรุปผลให้ในรอบถัดไป',
          cta: setupCta('ตั้งค่าคู่แข่ง & ชุดคำถาม →')
        })
      }) +
      ui.card({
        title: 'รายงานสัปดาห์นี้ (M6)',
        sub: 'สรุปอัตโนมัติจาก Learning Loop',
        action: RP.sampleBadge(),
        body: RP.realOr(weeklyPanel(), {
          title: 'ยังไม่มีรายงานสัปดาห์นี้',
          hint: 'รายงานฉบับแรกจะสรุปให้เมื่อครบ 1 สัปดาห์หลังเริ่มเผยแพร่จริง — เราไม่สรุปงานที่ระบบยังไม่ได้ทำ'
        })
      }) +
      '</div>';

    var factStrip = '<div class="grid grid-4">' + RP.data.facts.map(function (f) {
      return '<div class="card card-pad center"><div class="bb" style="font-size:24px;color:var(--purple-700)">' + esc(f.v) + '</div>' +
        '<div class="soft small" style="margin-top:4px">' + esc(f.d) + '</div></div>';
    }).join('') + '</div>';

    var html =
      ui.pageHead({ eyebrow: 'RankPilot AI — Dashboard หลัก', title: 'แดชบอร์ดหลัก',
        desc: 'ภาพรวมทุกคลัสเตอร์ในโปรเจ็คเดียว — บทความที่เผยแพร่ อันดับบน Google และการถูก AI อ้างอิง พร้อมสถานะของวงจรอัตโนมัติแต่ละคลัสเตอร์' }) +
      RP.sampleNotice('แดชบอร์ดนี้') +
      RP.collectingNotice('ของโปรเจ็คคุณ') +
      gettingStartedCard() + portfolioCard() +
      projectBar + kpiGrid + '<div class="mb">' + loopCard + '</div>' + tableCard + twoCol + factStrip;

    return {
      html: html,
      mount: function (root) {
        var nc = root.querySelector('#newCluster');
        if (nc) nc.onclick = function () { RP.go('m1'); };
        var gm5 = root.querySelector('#goM5');
        if (gm5) gm5.onclick = function () { RP.go('m5'); };
        var gsGo = root.querySelector('#gsGo'); if (gsGo) gsGo.onclick = function () { RP.go('settings'); };
        var pfM = root.querySelector('#pfManage'); if (pfM) pfM.onclick = function () { RP.go('projects'); };
        var pfN = root.querySelector('#pfNew'); if (pfN) pfN.onclick = function () { RP.go('projects'); };
        var pbN = root.querySelector('#pbNew'); if (pbN) pbN.onclick = function () { RP.go('projects'); };
        var ndC = root.querySelector('#ndCluster'); if (ndC) ndC.onclick = function () { RP.go('m1'); };
        Array.prototype.forEach.call(root.querySelectorAll('.gate-setup'), function (b) {
          b.onclick = function () { RP.go('settings'); };
        });
        Array.prototype.forEach.call(root.querySelectorAll('.pf-open'), function (b) {
          b.onclick = function () { RP.data.project.current = b.getAttribute('data-id'); RP.ui.toast('สลับโปรเจ็คแล้ว'); reDash(); };
        });
        Array.prototype.forEach.call(root.querySelectorAll('[data-cluster]'), function (b) {
          b.onclick = function () { RP.go('m1'); };
        });
      }
    };
  };

})(window.RP);
