/* ============================================================
   View: การตั้งค่า (Settings)
   แท็บ: การเชื่อมต่อ · ตั้งค่าโปรเจ็คนี้ · บัญชี & ทีม · การวัดผลทำงานยังไง (ของจริง)
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  var curTab = 'connect';
  var TABS = [
    { id: 'connect', t: '🔌 การเชื่อมต่อ' },
    { id: 'project', t: '🎯 ตั้งค่าโปรเจ็คนี้' },
    { id: 'account', t: '👤 บัญชี & ทีม' },
    { id: 'measure', t: '📏 การวัดผลทำงานยังไง' }
  ];

  var liveInt = null; // สถานะ integration จริงจาก backend (ถ้าดึงมาแล้ว)
  var ID_MAP = { serp: 'serp', gsc: 'gsc', llm: 'llm', aiapi: 'citation', wp: 'wordpress', webflow: 'webflow', indexnow: 'indexnow', ga4: 'ga4', notify: 'line' };
  function liveConnected(mockId) {
    if (!liveInt) return null;
    var f = liveInt.filter(function (x) { return x.id === ID_MAP[mockId]; })[0];
    return f ? f.connected : null;
  }

  function liveCard() {
    var on = RP.api.live;
    return '<div class="card mb"><div class="card-pad">' +
      '<div class="row between wrap" style="gap:10px">' +
      '<div><div class="bb">โหมดข้อมูล: ' + (on ? '<span style="color:var(--green-600)">● Live (ดึงสดจาก backend)</span>' : 'จำลอง (Mock)') + '</div>' +
      '<div class="soft small">เปิด Live เพื่อให้แดชบอร์ดดึงข้อมูลจริงจาก backend FastAPI — ต้องรัน <code>uvicorn app.main:app</code> ก่อน</div></div>' +
      '<label class="row gap-s" style="cursor:pointer"><input type="checkbox" id="liveToggle"' + (on ? ' checked' : '') + '> <span class="b">เปิดโหมด Live</span></label></div>' +
      '<div class="row wrap" style="gap:8px;margin-top:12px">' +
      '<div class="field" style="flex:1;min-width:220px"><span class="ico">🖥️</span><input id="apiBase" value="' + esc(RP.api.base) + '" placeholder="http://localhost:8000"></div>' +
      '<button class="btn" id="apiTest">ทดสอบการเชื่อมต่อ</button>' +
      '<button class="btn btn-primary" id="apiPull">ดึงสถานะจริงจาก backend</button></div>' +
      '<div class="hint" style="margin-top:10px">💡 โหมด Live ทำงานเมื่อเปิดจากเครื่อง (index.html / standalone) ที่รัน backend อยู่ — ในลิงก์ artifact เบราว์เซอร์จะบล็อกการต่อ localhost (CSP) จึงใช้ข้อมูลจำลอง</div>' +
      '</div></div>';
  }

  // บัญชีจริงอาจยังไม่มีโปรเจ็คเลย → list ว่างได้ ห้าม deref ตรง ๆ
  function projList() { return (RP.data && RP.data.project && RP.data.project.list) || []; }
  function curProj() {
    var list = projList();
    // บัญชีจริง: เห็นเฉพาะโปรเจ็คจากฐานข้อมูล (id ขึ้นต้น db) — กันโปรเจ็คตัวอย่างหลุด
    if (RP.isReal()) list = list.filter(function (x) { return /^db/.test(String(x.id)); });
    if (!list.length) return null;
    var cur = RP.data.project.current;
    var f = list.filter(function (x) { return x.id === cur; })[0];
    return f || null;
  }
  function noProjectBox(title) {
    return RP.noData(title || 'ยังไม่มีโปรเจ็ค',
      'สร้างโปรเจ็คแรกของคุณก่อน แล้วค่อยตั้งค่าเป้าหมาย/คู่แข่ง/การวัดผลของโปรเจ็คนั้น',
      '<button class="btn btn-primary" id="s_goProjects">＋ สร้างโปรเจ็คแรก</button>');
  }
  function chips(arr, empty) {
    if (!arr || !arr.length) return '<span class="soft small">' + (empty || 'ยังไม่มี') + '</span>';
    return '<div class="tag-list">' + arr.map(function (x) { return '<span class="chip">' + esc(x) + '</span>'; }).join('') + '</div>';
  }

  function dbId(p) {
    if (!p) return null;
    if (typeof p._dbid === 'number') return p._dbid;
    var m = /^db(\d+)$/.exec(String(p.id || ''));
    return m ? parseInt(m[1], 10) : null;
  }
  function srcText(s) { return s === 'project' ? '● คีย์ของคุณ' : s === 'platform' ? '● ใช้คีย์กลาง' : 'ยังไม่เชื่อม'; }

  function usageBar(lbl, used, limit) {
    var pct = limit ? Math.min(100, Math.round(used / limit * 100)) : 0;
    return '<div style="margin:8px 0"><div class="row between"><span class="soft small">' + esc(lbl) + '</span>' +
      '<span class="bb">' + used + ' / ' + limit + '</span></div>' + ui.bar(pct, pct >= 100 ? 'amber' : '') + '</div>';
  }
  function renderUsageCard(u) {
    return ui.card({
      title: 'แพ็กเกจ & การใช้งาน',
      action: '<button class="btn btn-sm btn-primary" id="s_upgrade2">อัปเกรด</button>',
      body: '<div class="bb" style="font-size:19px;color:var(--purple-700);margin-bottom:8px">' + esc(u.plan_label) + '</div>' +
        usageBar('โปรเจ็ค', u.projects.used, u.projects.limit) +
        usageBar('บทความเดือนนี้', u.articles_month.used, u.articles_month.limit) +
        '<div class="hint" style="margin-top:8px">โควตาจริงตามแพ็กเกจ — ถึงเพดานแล้วอัปเกรดเพื่อเพิ่ม</div>'
    });
  }

  /* ---------- Per-tenant: เชื่อมคีย์ของลูกค้าเอง (ต่อโปรเจ็ค) ---------- */
  var CRED_FORMS = [
    { kind: 'dataforseo', label: 'DataForSEO — ตรวจอันดับ Google / ขุดคำถาม',
      fields: [['login', 'อีเมล/login ของ DataForSEO'], ['password', 'password']] },
    { kind: 'wordpress', label: 'WordPress — เผยแพร่ขึ้นเว็บของคุณเอง',
      fields: [['base_url', 'https://บล็อกของคุณ.com'], ['username', 'ชื่อผู้ใช้ WordPress'], ['app_password', 'Application Password']] },
    { kind: 'gsc', label: 'Google Search Console — คลิก/Impression จริง',
      fields: [['client_id', 'client_id'], ['client_secret', 'client_secret'], ['refresh_token', 'refresh_token']] }
  ];
  function credInput(kind, f, ph) {
    var secret = /password|secret|token/.test(f);
    return '<input class="input" data-cf="' + kind + ':' + f + '"' + (secret ? ' type="password"' : '') +
      ' placeholder="' + esc(ph) + '" autocomplete="off" style="width:100%;margin:4px 0">';
  }
  function projectCredsCard() {
    var forms = CRED_FORMS.map(function (c) {
      return '<div class="card card-pad" style="margin-top:10px">' +
        '<div class="row between wrap" style="gap:8px"><div class="bb">' + esc(c.label) + '</div>' +
        '<span class="pcreds-src badge amber" data-src="' + c.kind + '">—</span></div>' +
        c.fields.map(function (f) { return credInput(c.kind, f[0], f[1]); }).join('') +
        '<div class="row" style="margin-top:6px"><button class="btn btn-sm btn-primary pcreds-save" data-kind="' + c.kind + '">บันทึกคีย์</button></div></div>';
    }).join('');
    return ui.card({
      title: '🔑 เชื่อมคีย์ของคุณเอง (ต่อโปรเจ็คนี้)',
      sub: 'ใช้คีย์ของคุณแทนคีย์กลางของแพลตฟอร์ม — เก็บเข้ารหัสฝั่งเซิร์ฟเวอร์ ไม่ส่งค่ากลับ · เว้นว่าง = ใช้คีย์กลางเดิม',
      cls: 'mb',
      body: '<div id="pcreds_slot" class="hint" style="margin-bottom:4px">กำลังโหลดสถานะ…</div>' + forms
    });
  }

  /* ---------- TAB 1: การเชื่อมต่อ ---------- */
  function tabConnect() {
    var a = RP.data.account;
    var steps = RP.data.onboarding || [];
    var progress;
    if (RP.isReal()) {
      // บัญชีจริง: ห้ามติ๊กถูกว่า "ตั้งค่าเสร็จแล้ว" จากข้อมูลตัวอย่าง — บอกสิ่งที่ยังต้องเชื่อมแทน
      progress =
        '<div class="card mb"><div class="card-pad">' +
        '<div class="bb">ความพร้อมก่อนวัดผลจริง</div>' +
        '<div class="hint" style="margin-top:10px">ระบบจะเริ่มวัดผลจริงได้เมื่อเชื่อมต่อครบ: SERP API (อันดับ Google), ' +
        'Google Search Console, API วัด AI Citation และปลายทางเผยแพร่ · ' +
        'สถานะด้านล่างมาจากบัญชีของคุณจริง ๆ เท่านั้น — กด "ดึงสถานะจริงจาก backend" เพื่ออัปเดต</div>' +
        '</div></div>';
    } else {
      var done = steps.filter(function (o) { return o.done; }).length;
      var total = steps.length || 1;
      progress =
        '<div class="card mb"><div class="card-pad">' +
        '<div class="row between wrap"><div class="bb">ความพร้อมก่อนวัดผลจริง (Onboarding) ' + RP.sampleBadge('ตัวอย่าง') + '</div>' +
        '<span class="badge ' + (done === total ? 'green' : 'amber') + '">' + done + '/' + total + ' ขั้นตอน</span></div>' +
        '<div style="margin:10px 0">' + ui.bar(done / total * 100, done === total ? 'green' : '') + '</div>' +
        '<div class="grid grid-2" style="gap:4px 18px">' +
        steps.map(function (o) {
          return '<div class="list-row" style="padding:6px 0"><span style="color:' + (o.done ? 'var(--green-600)' : 'var(--amber-600)') + ';font-weight:800">' +
            (o.done ? '✓' : '○') + '</span><div class="grow t small">' + esc(o.t) + '</div></div>';
        }).join('') + '</div></div></div>';
    }

    function intCard(i) {
      var lc = liveConnected(i.id);
      // บัญชีจริงที่ยังไม่เคยดึงสถานะ = ยังไม่ได้วัด → ห้ามโชว์ไฟเขียวจากข้อมูลตัวอย่าง
      var unverified = (lc === null) && RP.isReal() && !RP.data.__real;
      var conn = lc === null ? (unverified ? false : i.connected) : lc;
      var src = lc === null
        ? (unverified ? 'ยังไม่ได้ตรวจสอบสถานะ — กด "ดึงสถานะจริงจาก backend"' : i.detail)
        : (conn ? 'เชื่อมแล้ว (จาก backend)' : 'ยังไม่ตั้งคีย์ (จาก backend)');
      return '<div class="card card-pad">' +
        '<div class="row between wrap" style="gap:8px"><div class="bb">' + esc(i.name) + '</div>' +
        ui.badge(conn ? '● เชื่อมแล้ว' : 'ต้องเชื่อม', conn ? 'green' : 'amber') + '</div>' +
        '<div class="soft small" style="margin:2px 0 8px">ผู้ให้บริการ: ' + esc(i.provider) + (i.required ? ' · <b style="color:var(--red-text)">จำเป็น</b>' : ' · เสริม') + '</div>' +
        '<div class="small" style="margin-bottom:12px">⚙️ ใช้กับ: ' + esc(i.powers) + '</div>' +
        '<div class="row between"><span class="soft small">' + esc(src) + '</span>' +
        '<button class="btn btn-sm ' + (conn ? '' : 'btn-primary') + ' int-btn" data-id="' + i.id + '">' + (conn ? 'จัดการ' : 'เชื่อมต่อ') + '</button></div></div>';
    }
    var required = a.integrations.filter(function (i) { return i.required; });
    var optional = a.integrations.filter(function (i) { return !i.required; });
    // บัญชีจริง: การ์ดเชื่อมคีย์ของลูกค้าเอง (per-tenant) — มาก่อนสถานะคีย์กลาง
    return liveCard() + (RP.isReal() && curProj() ? projectCredsCard() : '') + progress +
      '<div class="bb mb" style="font-size:15px">การเชื่อมต่อที่จำเป็น</div>' +
      '<div class="grid grid-2 mb-l">' + required.map(intCard).join('') + '</div>' +
      '<div class="bb mb" style="font-size:15px">การเชื่อมต่อเสริม</div>' +
      '<div class="grid grid-2">' + optional.map(intCard).join('') + '</div>' +
      '<div class="hint" style="margin-top:14px">🔒 คีย์และโทเคนทั้งหมดถูกเก็บเข้ารหัสฝั่งเซิร์ฟเวอร์ · ค่าใช้จ่าย API เรียกตามการใช้งานจริงของแต่ละโปรเจ็ค (~2,300–5,400 บาท/โปรเจ็ค/เดือน ตามเอกสาร)</div>';
  }

  /* ---------- TAB 2: ตั้งค่าโปรเจ็คนี้ ---------- */
  function tabProject() {
    var p = curProj();
    if (!p) return noProjectBox('ยังไม่มีโปรเจ็ค');
    function row(l, v) { return '<div class="list-row"><div class="grow"><div class="soft small">' + esc(l) + '</div><div class="t">' + v + '</div></div></div>'; }
    var left = ui.card({ title: 'ข้อมูลโปรเจ็ค', body:
      '<div style="margin-bottom:10px"><div class="soft small" style="margin-bottom:4px">ชื่อโปรเจ็ค</div><input class="input" id="s_name" value="' + esc(p.name) + '" style="width:100%"></div>' +
      '<div style="margin-bottom:10px"><div class="soft small" style="margin-bottom:4px">โดเมน</div><input class="input" id="s_domain" value="' + esc(p.domain) + '" style="width:100%"></div>' +
      '<div style="margin-bottom:10px"><div class="soft small" style="margin-bottom:4px">ประเทศ / ภาษา</div><input class="input" value="' + esc(p.country + ' / ' + p.lang) + '" style="width:100%"></div>' +
      '<div><div class="soft small" style="margin-bottom:4px">โหมดเผยแพร่</div>' +
      '<select class="select" id="s_mode" style="width:100%"><option value="approve"' + (p.mode === 'approve' ? ' selected' : '') + '>Auto + Human Approve</option><option value="auto"' + (p.mode === 'auto' ? ' selected' : '') + '>Full-Auto 100%</option></select></div>'
    });
    var right = ui.card({ title: 'เป้าหมาย & การวัดผล', body:
      row('คีย์เวิร์ดที่ติดตาม', fmt.n(p.keywords) + ' คำ · ' + p.clusters + ' คลัสเตอร์') +
      '<div class="divider"></div>' +
      '<div class="soft small" style="margin-bottom:5px">โดเมนคู่แข่ง (เทียบ Share of Voice)</div>' + chips(p.competitors, 'ยังไม่ได้ตั้งคู่แข่ง') +
      '<div class="divider"></div>' +
      '<div class="soft small" style="margin-bottom:5px">ชื่อแบรนด์ที่ใช้ตรวจ AI Citation</div>' + chips(p.brandTerms) +
      '<div class="divider"></div>' +
      row('ชุดคำถาม Prompt Sampling', p.promptSet + ' คำถาม/รอบ') +
      row('เกณฑ์ Freshness', 'รีเฟรชเมื่อหน้าเก่ากว่า ' + p.freshnessDays + ' วัน') +
      row('Author Personas (E-E-A-T)', p.authors + ' โปรไฟล์')
    });
    return '<div class="hint mb">กำลังตั้งค่าโปรเจ็ค: <b>' + esc(p.name) + '</b> — ค่าเหล่านี้คือสิ่งที่ระบบใช้ "ขุดคำถาม → ผลิต → เผยแพร่ → วัดผล" ของโปรเจ็คนี้โดยเฉพาะ</div>' +
      '<div class="grid grid-2 mb">' + left + right + '</div>' +
      '<div class="row"><button class="btn btn-primary" id="s_save">บันทึกการตั้งค่า</button></div>';
  }

  /* ---------- TAB 3: บัญชี & ทีม ---------- */
  function tabAccount() {
    var a = RP.data.account;
    if (RP.isReal()) {
      // บัญชีจริง: แสดงแพ็กเกจ + การใช้งานจริง (เติมตอน mount จาก /api/usage)
      var planReal = '<div id="usage_slot">' + ui.card({ title: 'แพ็กเกจ & การใช้งาน', flush: true, body:
        RP.noData('กำลังโหลดแพ็กเกจ…', 'เปิดโหมด Live เพื่อดูแพ็กเกจและโควตาการใช้งานจริงของคุณ',
          '<button class="btn btn-sm" id="s_upgrade">ดูแพ็กเกจ</button>')
      }) + '</div>';
      var teamReal = ui.card({ title: 'สมาชิกทีม & สิทธิ์', sub: 'เหมาะกับ Agency ที่ให้ลูกค้าเข้าดูรายงานได้', flush: true,
        action: '<button class="btn btn-sm btn-primary" id="s_invite">＋ เชิญสมาชิก</button>',
        body: RP.noData('ทีม ยังไม่มีข้อมูล',
          'จะแสดงเมื่อเชื่อมระบบบิลลิ่ง/เชิญสมาชิกจริง — รายชื่อในระบบจะขึ้นเฉพาะคนที่ตอบรับคำเชิญแล้ว')
      });
      return planReal + '<div class="mb"></div>' + teamReal +
        '<div class="note-box" style="margin-top:14px">💡 <b>White-Label (Pro/Enterprise):</b> ใส่โลโก้/โดเมนของเอเจนซีเอง ส่งรายงานให้ลูกค้าในนามแบรนด์คุณ — ลูกค้าเห็นเฉพาะโปรเจ็คของตัวเองด้วยสิทธิ์ "ดูอย่างเดียว"</div>';
    }
    var plan = ui.card({ title: 'แพ็กเกจปัจจุบัน', body:
      '<div class="row between wrap" style="gap:10px"><div><div class="bb" style="font-size:20px;color:var(--purple-700)">' + esc(a.plan) + '</div>' +
      '<div class="soft small">' + esc(a.billingCycle) + ' · ' + a.projectQuota + ' โปรเจ็ค' + (a.whiteLabel ? ' · White-Label' : '') + '</div></div>' +
      '<button class="btn btn-sm" id="s_upgrade">อัปเกรด/จัดการแพ็กเกจ</button></div>' +
      '<div class="divider"></div>' +
      '<div class="grid grid-3" style="gap:10px">' +
      planTile('Starter', '2,900–4,900', '1 เว็บ · 60 บทความ/ด.', a.plan.indexOf('Starter') >= 0) +
      planTile('Pro', '9,900–14,900', '3 เว็บ · ไม่จำกัด · White-Label', a.plan.indexOf('Pro') >= 0) +
      planTile('Enterprise', 'เริ่ม 29,900', 'ไม่จำกัดเว็บ · API · SLA', a.plan.indexOf('Enterprise') >= 0) +
      '</div>'
    });
    var team = ui.card({ title: 'สมาชิกทีม & สิทธิ์', sub: 'เหมาะกับ Agency ที่ให้ลูกค้าเข้าดูรายงานได้', flush: true,
      action: '<button class="btn btn-sm btn-primary" id="s_invite">＋ เชิญสมาชิก</button>',
      body: '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>สมาชิก</th><th>อีเมล</th><th>สิทธิ์</th></tr></thead><tbody>' +
        a.team.map(function (m) {
          var tone = m.role.indexOf('เจ้าของ') >= 0 ? 'purple' : (m.role.indexOf('Editor') >= 0 ? 'blue' : '');
          return '<tr><td class="bb">' + esc(m.name) + '</td><td class="soft">' + esc(m.email) + '</td><td>' + ui.badge(m.role, tone) + '</td></tr>';
        }).join('') + '</tbody></table></div>'
    });
    return plan + '<div class="mb"></div>' + team +
      '<div class="note-box" style="margin-top:14px">💡 <b>White-Label (Pro/Enterprise):</b> ใส่โลโก้/โดเมนของเอเจนซีเอง ส่งรายงานให้ลูกค้าในนามแบรนด์คุณ — ลูกค้าเห็นเฉพาะโปรเจ็คของตัวเองด้วยสิทธิ์ "ดูอย่างเดียว"</div>';
  }
  function planTile(name, price, d, cur) {
    return '<div class="panel" style="' + (cur ? 'border-color:var(--brand-500);background:var(--surface-2)' : '') + '"><div class="panel-body">' +
      '<div class="row between"><span class="bb">' + name + '</span>' + (cur ? ui.badge('ปัจจุบัน', 'green') : '') + '</div>' +
      '<div class="bb" style="color:var(--purple-700);margin:4px 0">฿' + price + '<span class="soft" style="font-size:11px">/ด.</span></div>' +
      '<div class="soft small">' + esc(d) + '</div></div></div>';
  }

  /* ---------- TAB 4: การวัดผลทำงานยังไง (ของจริง) ---------- */
  function tabMeasure() {
    var block = function (icon, title, tone, real, body) {
      return '<div class="card card-pad">' +
        '<div class="row between wrap"><div class="row gap-s"><span style="font-size:20px">' + icon + '</span><span class="bb">' + esc(title) + '</span></div>' +
        ui.badge(real, tone) + '</div><div class="small" style="margin-top:10px;line-height:1.7">' + body + '</div></div>';
    };
    var table =
      '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ตัวชี้วัด</th><th>แหล่งข้อมูลจริง</th><th>ตรวจสอบได้ไหม</th></tr></thead><tbody>' +
      mrow('อันดับ Google / ติดหน้า 1', 'SERP API + Search Console', 'ของจริง — เสิร์ชเองก็เห็น', 'green') +
      mrow('คลิก / Impressions / CTR', 'Google Search Console (first-party)', 'ของจริง — ข้อมูลจาก Google เอง', 'green') +
      mrow('AI Citation / Share of Voice', 'Prompt Sampling (ยิงถาม AI จริง)', 'ค่าประมาณเชิงสถิติ (สุ่มถาม)', 'amber') +
      mrow('ทราฟฟิก / Conversion / ROI', 'GA4 + ฟอร์ม/CRM', 'ของจริง — วัด Lead/ยอดขาย', 'green') +
      mrow('บทความ / คะแนน AEO', 'ข้อเท็จจริงจากระบบ', 'ของจริง — นับ/คำนวณจริง', 'green') +
      '</tbody></table></div>';
    var topNote = RP.isReal()
      ? '<div class="hint mb">📌 <b>บัญชีของคุณแสดงเฉพาะข้อมูลจริงเท่านั้น</b> — ตัวเลขจะขึ้นเมื่อเชื่อม API/บัญชีในแท็บ "การเชื่อมต่อ" และระบบเก็บผลได้แล้ว ระหว่างนี้เราจะแสดงว่า "ยังไม่มีข้อมูล" ไม่ใส่ตัวเลขสมมติ</div>'
      : '<div class="warn-box mb" style="border-left-color:var(--amber-500);background:var(--amber-bg)">⚠️ <b>ความจริงที่ต้องรู้:</b> ตัวเลขที่เห็นในเดโมตอนนี้เป็น <b>ข้อมูลจำลอง</b> เพื่อสาธิต UX — เมื่อเชื่อม API/บัญชีจริงในแท็บ "การเชื่อมต่อ" ตัวเลขจะถูกแทนที่ด้วยข้อมูลที่ <b>ดึงสดจากแหล่งจริง</b> ทั้งหมด</div>';
    return topNote +
      '<div class="grid grid-3 mb">' +
      block('🔎', 'ฝั่ง SEO', 'green', 'ของจริง · ตรวจสอบได้', 'วัดจาก <b>SERP API</b> (ยิงคีย์เวิร์ด+ประเทศ+ภาษา ได้ผลอันดับ Google จริง) และ <b>Google Search Console</b> (คลิก/impression/อันดับ ตัวเลขจริงจาก Google เอง) — คุณเปิด Google เสิร์ชเองก็ตรวจได้ทันที ไม่มีทางปลอม') +
      block('🤖', 'ฝั่ง AEO (AI Citation)', 'amber', 'ของจริง · แต่เป็นค่าประมาณ', '<b>Prompt Sampling</b>: ระบบยิงชุดคำถามจริงไปที่ ChatGPT/Gemini/Perplexity ตามรอบ แล้ว "อ่านคำตอบ" ว่าเอ่ยถึง/อ้างอิงโดเมนเราไหม → นับ % = Share of Voice · เป็นการวัดจริง (ถามจริง อ่านจริง) แต่เป็น <b>ตัวอย่างเชิงสถิติ</b> เพราะ AI ตอบต่างกันตามผู้ใช้/เวลา และไม่มี API ทางการบอก citation ตรง ๆ') +
      block('💰', 'Conversion / ROI', 'green', 'ของจริง', 'เชื่อม <b>GA4</b> + ฟอร์ม/CRM เพื่อผูกทราฟฟิก Organic + AI Referral เข้ากับ <b>Lead/ยอดขายจริง</b> — พิสูจน์ ROI ได้ ไม่ใช่แค่ดูอันดับ') +
      '</div>' +
      ui.card({ title: 'สรุป: อะไรจริง / อะไรประมาณ', flush: true, body: table }) +
      '<div class="note-box" style="margin-top:14px">📌 <b>พูดตรง ๆ:</b> ฝั่ง SEO วัดได้จริงและตรวจสอบเองได้ 100% · ฝั่ง AI Citation วัดได้จริงแต่เป็นค่าประมาณจากการสุ่มถาม — <b>ไม่มีเครื่องมือไหนในโลก</b> (Profound, Otterly ก็ตาม) มีเลข AI citation แบบ absolute เพราะ AI ไม่เปิด API บอกตรง ๆ · เราจึงเน้นดู <b>แนวโน้ม</b> มากกว่าเลขเป๊ะจุดเดียว</div>';
  }
  function mrow(k, s, v, tone) {
    return '<tr><td class="bb">' + esc(k) + '</td><td class="soft">' + esc(s) + '</td><td>' + ui.badge(v, tone) + '</td></tr>';
  }

  function bodyFor(tab) {
    if (tab === 'connect') return tabConnect();
    if (tab === 'project') return tabProject();
    if (tab === 'account') return tabAccount();
    return tabMeasure();
  }

  function tabsBar() {
    return '<div class="row wrap gap-s mb" role="tablist">' + TABS.map(function (t) {
      return '<button class="chip set-tab' + (t.id === curTab ? ' on' : '') + '" data-tab="' + t.id + '">' + t.t + '</button>';
    }).join('') + '</div>';
  }

  function wire(root) {
    Array.prototype.forEach.call(root.querySelectorAll('.set-tab'), function (b) {
      b.onclick = function () {
        curTab = b.getAttribute('data-tab');
        root.querySelector('#setTabs').outerHTML = wrapTabs();
        root.querySelector('#setBody').innerHTML = bodyFor(curTab);
        wire(root);
      };
    });
    // tab-specific
    var gp = root.querySelector('#s_goProjects');
    if (gp) gp.onclick = function () { if (RP.go) RP.go('projects'); };
    var save = root.querySelector('#s_save'); if (save) save.onclick = function () {
      var p = curProj();
      if (!p) { ui.toast('ยังไม่มีโปรเจ็คให้บันทึก — สร้างโปรเจ็คก่อน'); return; }
      var n = root.querySelector('#s_name'); if (n) p.name = n.value.trim() || p.name;
      var d = root.querySelector('#s_domain'); if (d) p.domain = d.value.trim() || p.domain;
      var m = root.querySelector('#s_mode'); if (m) p.mode = m.value;
      ui.toast('บันทึกการตั้งค่าโปรเจ็ค <b>' + esc(p.name) + '</b> แล้ว ✓');
    };
    Array.prototype.forEach.call(root.querySelectorAll('.int-btn'), function (b) {
      b.onclick = function () {
        var i = RP.data.account.integrations.filter(function (x) { return x.id === b.getAttribute('data-id'); })[0];
        if (!i) return;
        ui.toast(i.connected ? 'เปิดหน้าจัดการ <b>' + esc(i.name) + '</b>' : 'เปิดหน้าเชื่อมต่อ <b>' + esc(i.name) + '</b> (ใส่ API key / OAuth)');
      };
    });
    // per-tenant: เชื่อมคีย์ของลูกค้าเอง (ต่อโปรเจ็ค)
    var pcSlot = root.querySelector('#pcreds_slot');
    if (pcSlot) {
      var pcPid = dbId(curProj());
      var loadCreds = function () {
        if (!pcPid || !RP.api.enabled()) {
          pcSlot.innerHTML = 'เปิด "โหมด Live" ด้านบนก่อน จึงจะบันทึก/ตรวจสถานะคีย์ของโปรเจ็คได้'; return;
        }
        RP.api.getCredentials(pcPid).then(function (res) {
          var st = res.status || {};
          pcSlot.innerHTML = 'สถานะการเชื่อมต่อของโปรเจ็คนี้ (โปร่งใส): ' +
            Object.keys(st).map(function (k) { return '<b>' + esc(k) + '</b> ' + esc(srcText(st[k].source)); }).join(' · ');
          Array.prototype.forEach.call(root.querySelectorAll('.pcreds-src'), function (b) {
            var s = (st[b.getAttribute('data-src')] || {}).source;
            b.textContent = srcText(s);
            b.className = 'pcreds-src badge ' + (s === 'project' ? 'green' : s === 'platform' ? 'blue' : 'amber');
          });
        }).catch(function () { pcSlot.innerHTML = 'ดึงสถานะไม่ได้ (ตรวจ backend/โหมด Live)'; });
      };
      loadCreds();
      Array.prototype.forEach.call(root.querySelectorAll('.pcreds-save'), function (b) {
        b.onclick = function () {
          if (!pcPid || !RP.api.enabled()) { ui.toast('เปิด "โหมด Live" ก่อนครับ'); return; }
          var kind = b.getAttribute('data-kind'), fields = {};
          Array.prototype.forEach.call(root.querySelectorAll('[data-cf^="' + kind + ':"]'), function (inp) {
            fields[inp.getAttribute('data-cf').split(':')[1]] = inp.value;
          });
          b.disabled = true; b.textContent = 'บันทึก…';
          RP.api.setCredential(pcPid, kind, fields).then(function () {
            ui.toast('บันทึกคีย์ <b>' + esc(kind) + '</b> แล้ว ✓ (เข้ารหัสเก็บฝั่งเซิร์ฟเวอร์)');
            b.disabled = false; b.textContent = 'บันทึกคีย์';
            Array.prototype.forEach.call(root.querySelectorAll('[data-cf^="' + kind + ':"]'), function (inp) { inp.value = ''; });
            loadCreds();
          }).catch(function (e) {
            b.disabled = false; b.textContent = 'บันทึกคีย์';
            ui.toast('บันทึกไม่ได้: ' + esc((e && e.message) || String(e)));
          });
        };
      });
    }
    ['s_upgrade', 's_invite', 's_upgrade2'].forEach(function (id) {
      var el = root.querySelector('#' + id); if (el) el.onclick = function () { if (RP.views && RP.views.billing && RP.go) RP.go('billing'); else ui.toast('เปิดหน้าจัดการแพ็กเกจ'); };
    });
    // บัญชีจริง: เติมแพ็กเกจ+การใช้งานจริง
    var uslot = root.querySelector('#usage_slot');
    if (uslot && RP.isReal() && RP.api.enabled()) {
      RP.api.usage().then(function (u) { if (u && u.plan) uslot.innerHTML = renderUsageCard(u); }).catch(function () {});
    }
    // โหมด Live
    var ab = root.querySelector('#apiBase');
    if (ab) ab.onchange = function () { RP.api.setBase(ab.value); };
    var lt = root.querySelector('#liveToggle');
    if (lt) lt.onchange = function () {
      if (ab) RP.api.setBase(ab.value);
      RP.api.setLive(lt.checked);
      ui.toast('โหมด Live: ' + (lt.checked ? '<b>เปิด</b>' : 'ปิด'));
      root.querySelector('#setBody').innerHTML = bodyFor(curTab); wire(root);
    };
    var at = root.querySelector('#apiTest');
    if (at) at.onclick = function () {
      if (ab) RP.api.setBase(ab.value);
      ui.toast('กำลังทดสอบการเชื่อมต่อ…');
      RP.api.health().then(function (h) { ui.toast('เชื่อม backend สำเร็จ ✓ (' + esc(h.service || 'ok') + ')'); })
        .catch(function (e) { ui.toast('เชื่อมไม่ได้: ' + esc(e.message)); });
    };
    var ap = root.querySelector('#apiPull');
    if (ap) ap.onclick = function () {
      if (ab) RP.api.setBase(ab.value);
      ui.toast('กำลังดึงสถานะจาก backend…');
      RP.api.integrations().then(function (res) {
        liveInt = res.integrations;
        ui.toast('ดึงสถานะจริงแล้ว — พร้อมวัดผล: ' + (res.ready_for_measurement ? '✓ ครบ' : 'ยังไม่ครบ'));
        root.querySelector('#setBody').innerHTML = bodyFor(curTab); wire(root);
      }).catch(function (e) { ui.toast('ดึงไม่ได้: ' + esc(e.message)); });
    };
  }
  function wrapTabs() { return '<div id="setTabs">' + tabsBar() + '</div>'; }

  RP.views.settings = function () {
    var p = curProj();
    var html =
      ui.pageHead({ eyebrow: 'ระบบ · Settings', title: 'การตั้งค่า',
        desc: 'ตั้งค่าการเชื่อมต่อ (API/บัญชี) ที่จำเป็นก่อนระบบจะวัดผลได้จริง ตั้งค่าเฉพาะโปรเจ็ค จัดการทีม/แพ็กเกจ และดูว่า "การวัดผลทำงานยังไงของจริง"' +
          (p ? ' — โปรเจ็คปัจจุบัน: <b>' + esc(p.name) + '</b>' : ' — <b>ยังไม่มีโปรเจ็ค</b>') }) +
      RP.sampleNotice('หน้าการตั้งค่า (แพ็กเกจ · ทีม · สถานะ Onboarding)') +
      wrapTabs() +
      '<div id="setBody">' + bodyFor(curTab) + '</div>';
    return { html: html, mount: function (root) { wire(root); } };
  };

})(window.RP);
