/* ============================================================
   ImVisible — โหมดใช้งานจริง: สมัคร/เข้าสู่ระบบ (JWT จริง) + Onboarding สร้างโปรเจ็คจริง
   - ของจริงเป็นค่าเริ่มต้น (register/login → backend จริง → โหลดโปรเจ็คจริง)
   - โหมดเดโมยังมีให้ "ดูตัวอย่าง" แต่แยกชัดเจน (ข้อมูลสมมติ)
   ============================================================ */
(function (RP) {
  'use strict';
  var esc = RP.esc;
  function lget(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lset(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function ldel(k) { try { localStorage.removeItem(k); } catch (e) {} }

  RP.auth = {
    user: function () { try { return JSON.parse(lget('rp-user') || 'null'); } catch (e) { return null; } },
    login: function (email, real) { lset('rp-user', JSON.stringify({ email: email, real: !!real })); },
    logout: function () { ldel('rp-user'); ldel('rp-onboarded'); },
    onboarded: function () { return lget('rp-onboarded') === '1'; },
    setOnboarded: function () { lset('rp-onboarded', '1'); },
    // มี session จริง = ผู้ใช้ระบุ real + มี JWT token อยู่
    isReal: function () { var u = this.user(); return !!(u && u.real && RP.api && RP.api.token); }
  };

  function isAuthErr(msg) { return /401|403|Unauthorized|ไม่ได้รับอนุญาต|credential|token/i.test(msg || ''); }

  /* ---------- แผนที่โปรเจ็คจริง → view model ---------- */
  function mapProj(p) {
    return {
      id: 'db' + p.id, _dbid: p.id, name: p.name, domain: p.domain, mode: p.mode,
      country: p.country || 'ไทย', lang: (p.language === 'en' ? 'English' : 'ภาษาไทย'),
      plan: 'Pro', status: 'active', created: 'จากระบบจริง',
      keywords: 0, clusters: 0, competitors: [], brandTerms: [], promptSet: 0,
      freshnessDays: p.freshness_days || 120, authors: 0,
      public_home: p.public_home || '', publish_mode: p.publish_mode || 'managed', custom_domain: p.custom_domain || '',
      // ยังไม่ได้วัดสถานะเชื่อมต่อจริงต่อโปรเจ็ค → false ทั้งหมด (ห้ามโชว์ไฟเขียวที่ไม่ได้ตรวจ)
      health: { gsc: false, serp: false, ai: false, publish: false }
    };
  }

  /* บัญชีจริง: ล้างข้อมูล demo ที่แชร์ใน RP.data ทิ้งถาวร — กันหลุดแม้ gate รายหน้าพลาด/auth race
     (ตัวเลข KPI/คลัสเตอร์/ทีม/owner สมมติ ต้องไม่มีทางโผล่ให้บัญชีจริงเห็นเด็ดขาด) */
  function scrubDemo() {
    var d = RP.data; if (!d) return;
    d.kpis = []; d.clusters = []; d.facts = [];
    if (d.account) {
      d.account.team = [];
      var u = (RP.auth && RP.auth.user && RP.auth.user()) || null;
      d.account.owner = (u && u.email) || '';
      (d.account.integrations || []).forEach(function (i) { i.connected = false; i.detail = ''; });
    }
  }

  /* ---------- โหลดข้อมูลจริงจาก backend (โปรเจ็ค + สถานะการเชื่อมต่อ) ---------- */
  RP.loadRealData = function (cb) {
    if (!(RP.api && RP.api.token && RP.api.reachable())) { if (cb) cb(false, 0); return; }
    scrubDemo();   // ล้าง demo ทันทีที่รู้ว่าเป็นบัญชีจริง (ก่อน fetch เสร็จด้วย)
    RP.api.projects().then(function (res) {
      var list = (res.projects || []).map(mapProj);
      // บัญชีจริง: แทนที่ "เสมอ" แม้ยังไม่มีโปรเจ็ค — ห้ามให้โปรเจ็คตัวอย่างหลงเหลือในบัญชีจริงเด็ดขาด
      RP.data.project.list = list;
      RP.data.project.current = list.length ? list[0].id : '';
      RP.data.__real = true;
      RP.api.integrations().then(function (ir) {
        var st = {}; (ir.integrations || []).forEach(function (i) { st[i.id] = i.connected; });
        // map id ของ backend → id ใน demo dataset
        var alias = { llm: 'llm', serp: 'serp', gsc: 'gsc', citation: 'aiapi', wordpress: 'wp',
                      webflow: 'webflow', indexnow: 'indexnow', ga4: 'ga4', line: 'notify' };
        RP.data.account.integrations.forEach(function (i) {
          Object.keys(alias).forEach(function (k) { if (alias[k] === i.id && k in st) i.connected = st[k]; });
        });
      }).catch(function () {}).then(function () { if (cb) cb(true, list.length); });
    }).catch(function (e) {
      var msg = (e && e.message) || '';
      if (isAuthErr(msg)) {                      // token หมดอายุ/ไม่ถูกต้อง → ล้าง + ให้ login ใหม่
        RP.auth.logout(); if (RP.api) RP.api.setToken('');
        if (cb) cb(false, 0); return;
      }
      // สำคัญ (กฎ "ไม่ปลอม"): แม้โหลดโปรเจ็คไม่สำเร็จ (เช่น DB ล่มชั่วคราว/503) ก็ต้อง
      // ล้างโปรเจ็คตัวอย่างทิ้ง — ห้ามให้บัญชีจริงเห็นโปรเจ็คสมมติค้างอยู่เด็ดขาด
      // (ไม่งั้น Settings/M5 จะหยิบโดเมนตัวอย่างมาแสดง/ยิงเครื่องมือสด)
      RP.data.project.list = [];
      RP.data.project.current = '';
      RP.data.__real = true;                     // ต่อได้แต่ถือว่า "ยังไม่มีข้อมูล" (ดีกว่าโชว์ของปลอม)
      if (cb) cb(true, 0);
    });
  };

  /* ---------- หน้าเข้าสู่ระบบ / สมัคร (ของจริงเป็นหลัก) ---------- */
  RP.showLogin = function (onSuccess) {
    // soft-launch: ปิดรับสมัครไว้ก่อน เหลือแค่ล็อกอิน — regOpen มาจาก /health (registration_open=false = ปิด)
    var regOpen = (RP.auth && RP.auth._regOpen === true);
    var mode = 'login';
    var el = document.createElement('div');
    el.className = 'auth-screen'; el.id = 'authScreen';
    if ((!RP.auth || RP.auth._regOpen === undefined) && RP.api && RP.api.reachable()) {
      RP.api.health().then(function (h) {
        RP.auth._regOpen = !(h && h.registration_open === false);
        if (RP.auth._regOpen !== regOpen) { regOpen = RP.auth._regOpen; render(); }
      }).catch(function () {});
    }
    function field(label, type, id, ph) {
      return '<div class="auth-field"><label for="' + id + '">' + esc(label) + '</label>' +
        '<input id="' + id + '" type="' + type + '" placeholder="' + esc(ph) + '"></div>';
    }
    function render() {
      var live = RP.api && RP.api.reachable();
      el.innerHTML =
        '<div class="auth-card">' +
        '<div class="auth-brand"><div class="logo"><img src="assets/brand-logo.svg" alt="ImVisible" width="44" height="44"></div><div class="name">Im<span>Visible</span></div></div>' +
        (regOpen
          ? '<div class="auth-tabs"><button data-m="signup" class="' + (mode === 'signup' ? 'on' : '') + '">สมัครใช้งาน</button>' +
            '<button data-m="login" class="' + (mode === 'login' ? 'on' : '') + '">เข้าสู่ระบบ</button></div>'
          : '') +
        '<h2>' + (mode === 'login' ? 'ยินดีต้อนรับกลับมา 👋' : 'เริ่มใช้ ImVisible จริง') + '</h2>' +
        '<div class="sub">' + (mode === 'login' ? 'เข้าสู่ระบบเพื่อจัดการโปรเจ็คของคุณ' : 'สมัครฟรี — ใส่แค่ลิงก์เว็บ ระบบเขียน + โฮสต์บล็อกให้อัตโนมัติ') + '</div>' +
        (mode === 'signup' ? field('ชื่อ / บริษัท', 'text', 'au_name', 'เช่น ร้านกาแฟ ABC') : '') +
        field('อีเมล', 'email', 'au_email', 'you@example.com') +
        field('รหัสผ่าน', 'password', 'au_pass', 'อย่างน้อย 6 ตัวอักษร') +
        (mode === 'signup'
          ? '<label class="auth-consent" style="display:flex;gap:8px;align-items:flex-start;font-size:13px;margin:2px 0 6px;cursor:pointer">' +
            '<input type="checkbox" id="au_terms" style="margin-top:3px">' +
            '<span>ฉันยอมรับ <a href="/legal/terms" target="_blank">ข้อกำหนดการใช้บริการ</a> และ ' +
            '<a href="/legal/privacy" target="_blank">นโยบายความเป็นส่วนตัว (PDPA)</a></span></label>'
          : '') +
        '<button class="btn btn-primary btn-block" id="au_submit" style="margin-top:6px">' + (mode === 'login' ? 'เข้าสู่ระบบ' : 'สมัครและเริ่มใช้งานจริง') + '</button>' +
        (live ? '' : '<div class="hint" style="margin-top:10px">⚠️ ต่อ backend ไม่ได้ตอนนี้ — เข้าระบบจริงจะใช้ไม่ได้</div>') +
        (regOpen
          ? '<div class="auth-or">หรือ</div><button class="btn btn-block" id="au_demo">👀 ดูตัวอย่าง (ข้อมูลสมมติ · ไม่บันทึกจริง)</button>'
          : '') +
        '<div class="auth-foot">' + (regOpen
          ? 'การสมัคร/เข้าสู่ระบบ = บัญชีจริง (JWT) เชื่อมฐานข้อมูล · โหมดตัวอย่างเก็บในเบราว์เซอร์นี้เท่านั้น'
          : 'ขณะนี้ยังไม่เปิดรับสมัครทั่วไป — เข้าสู่ระบบเฉพาะบัญชีที่ได้รับเชิญ') + '</div>' +
        '</div>';
      Array.prototype.forEach.call(el.querySelectorAll('.auth-tabs button'), function (b) {
        b.onclick = function () { mode = b.getAttribute('data-m'); render(); };
      });
      el.querySelector('#au_submit').onclick = submit;
      var demoBtn = el.querySelector('#au_demo'); if (demoBtn) demoBtn.onclick = function () { finish('demo@imvisible.tech', false); };
      el.querySelector('#au_pass').addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    }
    function submit() {
      var email = (el.querySelector('#au_email').value || '').trim();
      var pass = (el.querySelector('#au_pass').value || '');
      var nameEl = el.querySelector('#au_name');
      var name = nameEl ? (nameEl.value || '').trim() : '';
      if (!email || email.indexOf('@') < 0) { RP.ui.toast('กรุณากรอกอีเมลให้ถูกต้อง'); return; }
      if (!pass || pass.length < 6) { RP.ui.toast('รหัสผ่านอย่างน้อย 6 ตัวอักษร'); return; }
      var termsEl = el.querySelector('#au_terms');
      var accepted = !!(termsEl && termsEl.checked);
      if (mode === 'signup' && !accepted) { RP.ui.toast('กรุณายอมรับข้อกำหนดและนโยบายความเป็นส่วนตัวก่อนสมัคร'); return; }
      if (!(RP.api && RP.api.reachable())) { RP.ui.toast('ต่อ backend ไม่ได้ — ลองใหม่ หรือกด "ดูตัวอย่าง"'); return; }
      var btn = el.querySelector('#au_submit'); btn.disabled = true; btn.textContent = 'กำลังดำเนินการ…';
      var p = mode === 'signup' ? RP.api.register(email, pass, name, accepted) : RP.api.signin(email, pass);
      p.then(function (res) { RP.api.setToken(res.token); finish((res.user && res.user.email) || email, true); })
        .catch(function (e) {
          btn.disabled = false; btn.textContent = (mode === 'login' ? 'เข้าสู่ระบบ' : 'สมัครและเริ่มใช้งานจริง');
          RP.ui.toast(RP.esc(e.message || 'สมัคร/เข้าสู่ระบบไม่สำเร็จ'));
        });
    }
    function finish(email, real) {
      RP.auth.login(email, real);
      el.style.opacity = '0'; el.style.transition = 'opacity .2s';
      setTimeout(function () { el.remove(); if (onSuccess) onSuccess(); }, 180);
    }
    document.body.appendChild(el);
    render();
  };

  /* ---------- Onboarding จริง: สร้างโปรเจ็คแรกด้วยลิงก์ ---------- */
  RP.showRealOnboarding = function (onDone) {
    var el = document.createElement('div'); el.className = 'onb-overlay'; el.id = 'onbReal';
    var busy = false;
    function render(out) {
      el.innerHTML =
        '<div class="onb-card"><div class="onb-hero">' +
        '<div class="ic">🌐</div><h2>สร้างโปรเจ็คแรกของคุณ</h2>' +
        '<p>ใส่แค่ลิงก์เว็บ — ระบบจะเขียนบทความ AEO แล้วโฮสต์บล็อกให้อัตโนมัติ</p></div>' +
        '<div class="onb-body">' +
        '<div style="margin-bottom:10px"><div class="soft small" style="margin-bottom:4px">ลิงก์เว็บไซต์ของคุณ *</div>' +
        '<input class="input" id="ro_url" placeholder="เช่น yourbusiness.com" style="width:100%"></div>' +
        '<div style="margin-bottom:10px"><div class="soft small" style="margin-bottom:4px">ชื่อธุรกิจ (ไม่ใส่ก็ได้)</div>' +
        '<input class="input" id="ro_name" placeholder="เช่น ร้านกาแฟ ABC" style="width:100%"></div>' +
        '<div class="row gap-s" style="gap:16px"><label class="row gap-s" style="cursor:pointer;gap:6px"><input type="radio" name="ro_lang" value="th" checked> ภาษาไทย</label>' +
        '<label class="row gap-s" style="cursor:pointer;gap:6px"><input type="radio" name="ro_lang" value="en"> English</label></div>' +
        '<div id="ro_out" style="margin-top:10px">' + (out || '') + '</div>' +
        '</div><div class="onb-foot">' +
        '<button class="btn btn-ghost" id="ro_skip">ข้ามไปก่อน</button><span class="spacer"></span>' +
        '<button class="btn btn-primary" id="ro_go">สร้าง & เริ่มผลิต</button></div></div>';
      el.querySelector('#ro_skip').onclick = close;
      el.querySelector('#ro_go').onclick = go;
      el.querySelector('#ro_url').addEventListener('keydown', function (e) { if (e.key === 'Enter') go(); });
    }
    function go() {
      if (busy) return;
      var url = (el.querySelector('#ro_url').value || '').trim();
      var name = (el.querySelector('#ro_name').value || '').trim();
      var langEl = el.querySelector('input[name="ro_lang"]:checked');
      var lang = langEl ? langEl.value : 'th';
      if (!url) { RP.ui.toast('กรุณาใส่ลิงก์เว็บไซต์'); return; }
      busy = true;
      var go = el.querySelector('#ro_go'); go.disabled = true; go.textContent = 'กำลังสร้าง…';
      RP.api.createProject({ url: url, name: name, language: lang, mode: 'approve', publish_mode: 'managed' })
        .then(function (p) {
          if (p && p.id != null) RP.data.project.list.unshift(mapProj(Object.assign({ freshness_days: 120 }, p)));
          RP.data.project.current = 'db' + p.id;
          var home = p.public_home || '';
          render(
            '<div class="note-box" style="margin-bottom:10px">✅ สร้างโปรเจ็คแล้ว! บล็อกที่เราโฮสต์ให้:</div>' +
            (home ? '<a href="' + esc(home) + '" target="_blank" class="bb" style="word-break:break-all">' + esc(home) + '</a>' : '') +
            '<div class="row gap-s" style="margin-top:12px"><button class="btn btn-green" id="ro_grow">🚀 ผลิตบทความแรกเดี๋ยวนี้</button>' +
            '<button class="btn" id="ro_done">เข้าสู่แดชบอร์ด →</button></div>' +
            '<div class="hint" style="margin-top:10px">อยากให้อยู่บนโดเมนคุณเอง (blog.' + esc((p.domain || '')) + ')? ตั้ง CNAME มาที่เรา แล้วบอกทีม</div>');
          busy = false;
          var g = el.querySelector('#ro_grow');
          if (g) g.onclick = function () {
            g.disabled = true; g.textContent = 'เข้าคิวแล้ว…';
            RP.api.grow(p.id).then(function () { RP.ui.toast('เริ่มผลิตแล้ว ✓ ดูได้ที่ M2 · โรงงานคอนเทนต์ อีกสักครู่'); })
              .catch(function (e) { RP.ui.toast('สั่งผลิตไม่ได้: ' + RP.esc(e.message || String(e))); });
          };
          var d = el.querySelector('#ro_done'); if (d) d.onclick = close;
        })
        .catch(function (e) {
          busy = false; var g = el.querySelector('#ro_go'); if (g) { g.disabled = false; g.textContent = 'สร้าง & เริ่มผลิต'; }
          RP.ui.toast('สร้างโปรเจ็คไม่ได้: ' + RP.esc(e.message || String(e)));
        });
    }
    function close() {
      RP.auth.setOnboarded();
      el.style.opacity = '0'; el.style.transition = 'opacity .2s';
      setTimeout(function () { el.remove(); if (onDone) onDone(); }, 180);
      RP.go('projects');
    }
    document.body.appendChild(el);
    render();
  };

  /* ---------- Onboarding เดโม (สำหรับโหมดดูตัวอย่างเท่านั้น) ---------- */
  RP.showOnboarding = function () {
    var step = 0;
    var STEPS = [
      { ic: '🎉', h: 'ยินดีต้อนรับสู่ ImVisible (โหมดตัวอย่าง)', p: 'นี่คือข้อมูลสมมติเพื่อให้ดูหน้าตาระบบ — สมัครบัญชีจริงเพื่อเริ่มดันเว็บของคุณเอง', body: welcomeBody },
      { ic: '🔎', h: 'ขุดคำถามจริง', p: 'ระบบหาสิ่งที่ลูกค้าถามจริงจาก Google + People Also Ask', body: welcomeBody },
      { ic: '✅', h: 'อยากใช้จริง?', p: 'กด "ออกจากระบบ" แล้วสมัครบัญชีจริง — ใส่แค่ลิงก์เว็บ ระบบทำที่เหลือให้', body: doneBody }
    ];
    var el = document.createElement('div'); el.className = 'onb-overlay'; el.id = 'onbOverlay';
    function dots() { return '<div class="step-dots">' + STEPS.map(function (_, i) { return '<i class="' + (i <= step ? 'on' : '') + '"></i>'; }).join('') + '</div>'; }
    function render() {
      var s = STEPS[step];
      el.innerHTML =
        '<div class="onb-card"><div class="onb-hero">' + dots() +
        '<div class="ic">' + s.ic + '</div><h2>' + esc(s.h) + '</h2><p>' + esc(s.p) + '</p></div>' +
        '<div class="onb-body">' + s.body() + '</div>' +
        '<div class="onb-foot">' +
        (step > 0 ? '<button class="btn" id="onb_back">ย้อนกลับ</button>' : '<button class="btn btn-ghost" id="onb_skip">ข้าม</button>') +
        '<span class="spacer"></span>' +
        '<button class="btn btn-primary" id="onb_next">' + (step === STEPS.length - 1 ? 'เข้าสู่แดชบอร์ด →' : 'ถัดไป') + '</button>' +
        '</div></div>';
      var back = el.querySelector('#onb_back'); if (back) back.onclick = function () { step--; render(); };
      var skip = el.querySelector('#onb_skip'); if (skip) skip.onclick = done;
      el.querySelector('#onb_next').onclick = function () { if (step === STEPS.length - 1) { done(); return; } step++; render(); };
    }
    function done() {
      RP.auth.setOnboarded();
      el.style.opacity = '0'; el.style.transition = 'opacity .2s';
      setTimeout(function () { el.remove(); }, 180);
      RP.go('dashboard');
    }
    document.body.appendChild(el);
    render();

    function welcomeBody() {
      return feat('🔎', 'ขุดคำถามจริง', 'หาสิ่งที่ลูกค้าถามจริงจาก Google, People Also Ask') +
        feat('🏭', 'ผลิต + เผยแพร่อัตโนมัติ', 'บทความสูตร AEO ผ่าน Fact-Check ก่อนขึ้นเว็บ') +
        feat('📈', 'วัดผลของจริง', 'อันดับ Google + การถูก AI อ้างอิง (Share of Voice)');
    }
    function doneBody() {
      return feat('🌐', 'ใส่แค่ลิงก์', 'ระบบเขียน + โฮสต์บล็อก AEO ให้อัตโนมัติ') +
        feat('🔒', 'บัญชีจริง', 'ข้อมูลเก็บในฐานข้อมูล ไม่ใช่แค่เบราว์เซอร์') +
        feat('📊', 'เห็นผลจริง', 'บทความที่ AI เขียน + ลิงก์บล็อกจริง');
    }
    function feat(ic, t, s) { return '<div class="onb-feature"><div class="fi">' + ic + '</div><div><div class="ft">' + esc(t) + '</div><div class="fs">' + esc(s) + '</div></div></div>'; }
  };

})(window.RP);
