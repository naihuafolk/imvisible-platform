/* ============================================================
   RankPilot AI — โหมดใช้งานจริง: เข้าสู่ระบบ + Onboarding ตามลำดับ
   (เดโม: ระบบสมาชิกจำลองด้วย localStorage — ยังไม่เชื่อม auth จริง)
   ============================================================ */
(function (RP) {
  'use strict';
  var esc = RP.esc, ui = RP.ui;
  function lget(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lset(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  function ldel(k) { try { localStorage.removeItem(k); } catch (e) {} }

  RP.auth = {
    user: function () { try { return JSON.parse(lget('rp-user') || 'null'); } catch (e) { return null; } },
    login: function (email) { lset('rp-user', JSON.stringify({ email: email })); },
    logout: function () { ldel('rp-user'); },
    onboarded: function () { return lget('rp-onboarded') === '1'; },
    setOnboarded: function () { lset('rp-onboarded', '1'); }
  };

  /* ---------- หน้าเข้าสู่ระบบ ---------- */
  RP.showLogin = function (onSuccess) {
    var mode = 'login';
    var el = document.createElement('div');
    el.className = 'auth-screen'; el.id = 'authScreen';
    function render() {
      el.innerHTML =
        '<div class="auth-card">' +
        '<div class="auth-brand"><div class="logo">R</div><div class="name">Rank<span>Pilot</span> AI</div></div>' +
        '<div class="auth-tabs"><button data-m="login" class="' + (mode === 'login' ? 'on' : '') + '">เข้าสู่ระบบ</button>' +
        '<button data-m="signup" class="' + (mode === 'signup' ? 'on' : '') + '">สมัครใช้งาน</button></div>' +
        '<h2>' + (mode === 'login' ? 'ยินดีต้อนรับกลับมา 👋' : 'เริ่มใช้ RankPilot AI') + '</h2>' +
        '<div class="sub">' + (mode === 'login' ? 'เข้าสู่ระบบเพื่อจัดการโปรเจ็ค AEO + SEO ของคุณ' : 'สมัครเพื่อดันเว็บให้ติดทั้ง Google และ AI Search') + '</div>' +
        (mode === 'signup' ? field('ชื่อ / บริษัท', 'text', 'au_name', 'เช่น คลินิกความงาม ABC') : '') +
        field('อีเมล', 'email', 'au_email', 'you@example.com') +
        field('รหัสผ่าน', 'password', 'au_pass', '••••••••') +
        '<button class="btn btn-primary btn-block" id="au_submit" style="margin-top:6px">' + (mode === 'login' ? 'เข้าสู่ระบบ' : 'สมัครและเริ่มใช้งาน') + '</button>' +
        '<div class="auth-or">หรือ</div>' +
        '<button class="btn btn-block" id="au_demo">🚀 ทดลองใช้ทันที (บัญชีเดโม)</button>' +
        '<div class="auth-foot">เดโม — ระบบสมาชิกยังเป็นแบบจำลอง ข้อมูลเก็บในเบราว์เซอร์นี้เท่านั้น</div>' +
        '</div>';
      Array.prototype.forEach.call(el.querySelectorAll('.auth-tabs button'), function (b) {
        b.onclick = function () { mode = b.getAttribute('data-m'); render(); };
      });
      el.querySelector('#au_submit').onclick = submit;
      el.querySelector('#au_demo').onclick = function () { finish('demo@rankpilot.ai'); };
      var pass = el.querySelector('#au_pass');
      pass.addEventListener('keydown', function (e) { if (e.key === 'Enter') submit(); });
    }
    function field(label, type, id, ph) {
      return '<div class="auth-field"><label for="' + id + '">' + esc(label) + '</label>' +
        '<input id="' + id + '" type="' + type + '" placeholder="' + esc(ph) + '"></div>';
    }
    function submit() {
      var email = (el.querySelector('#au_email').value || '').trim();
      if (!email || email.indexOf('@') < 0) { RP.ui.toast('กรุณากรอกอีเมลให้ถูกต้อง'); return; }
      var pass = (el.querySelector('#au_pass').value || '');
      var nameEl = el.querySelector('#au_name');
      var name = nameEl ? nameEl.value : '';
      if (RP.api && RP.api.reachable() && pass) {
        RP.ui.toast('กำลังเข้าสู่ระบบ…');
        var p = mode === 'signup' ? RP.api.register(email, pass, name) : RP.api.signin(email, pass);
        p.then(function (res) { RP.api.setToken(res.token); finish((res.user && res.user.email) || email); })
          .catch(function (e) {
            var msg = e.message || '';
            if (/Failed to fetch|NetworkError|load failed|DATABASE_URL|503/i.test(msg)) {
              RP.ui.toast('ต่อ backend ไม่ได้ — เข้าสู่โหมดเดโม (ออฟไลน์)'); finish(email);
            } else { RP.ui.toast(RP.esc(msg)); }
          });
      } else { finish(email); }
    }
    function finish(email) {
      RP.auth.login(email);
      el.style.opacity = '0'; el.style.transition = 'opacity .2s';
      setTimeout(function () { el.remove(); if (onSuccess) onSuccess(); }, 180);
    }
    document.body.appendChild(el);
    render();
  };

  /* ---------- Onboarding (ตามลำดับ) ---------- */
  RP.showOnboarding = function () {
    var step = 0;
    var STEPS = [
      { ic: '🎉', h: 'ยินดีต้อนรับสู่ RankPilot AI', p: 'แพลตฟอร์มที่ดันเว็บของคุณให้ "ติดคำตอบ" ทั้งบน Google และ AI Search อัตโนมัติ มาตั้งค่า 3 ขั้นง่าย ๆ กัน', body: welcomeBody },
      { ic: '🔌', h: 'ขั้นที่ 1 — เชื่อมต่อ', p: 'เชื่อม API ที่จำเป็นก่อนระบบจะวัดผลได้จริง (ตั้งภายหลังในหน้าการตั้งค่าได้)', body: connectBody },
      { ic: '🗂️', h: 'ขั้นที่ 2 — โปรเจ็คแรกของคุณ', p: 'ใส่เว็บ/ธุรกิจที่อยากดัน — หรือใช้โปรเจ็คตัวอย่างเพื่อดูระบบก่อน', body: projectBody },
      { ic: '✅', h: 'พร้อมแล้ว!', p: 'ตั้งค่าเรียบร้อย เข้าสู่แดชบอร์ดเพื่อเริ่มวงจร AEO + SEO อัตโนมัติได้เลย', body: doneBody }
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
        (step > 0 ? '<button class="btn" id="onb_back">ย้อนกลับ</button>' : '<button class="btn btn-ghost" id="onb_skip">ข้ามการแนะนำ</button>') +
        '<span class="spacer"></span>' +
        '<button class="btn btn-primary" id="onb_next">' + (step === STEPS.length - 1 ? 'เข้าสู่แดชบอร์ด →' : 'ถัดไป') + '</button>' +
        '</div></div>';
      var back = el.querySelector('#onb_back'); if (back) back.onclick = function () { step--; render(); };
      var skip = el.querySelector('#onb_skip'); if (skip) skip.onclick = done;
      el.querySelector('#onb_next').onclick = function () {
        if (step === STEPS.length - 1) { done(); return; }
        step++; render();
      };
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
      return feat('🔎', 'ขุดคำถามจริง', 'หาสิ่งที่ลูกค้าถามจริงจาก Google, Pantip, AI') +
        feat('🏭', 'ผลิต + เผยแพร่อัตโนมัติ', 'บทความสูตร AEO ผ่าน Fact-Check ก่อนขึ้นเว็บ') +
        feat('📈', 'วัดผลของจริง', 'อันดับ Google + การถูก AI อ้างอิง (Share of Voice)');
    }
    function connectBody() {
      var req = RP.data.account.integrations.filter(function (i) { return i.required; });
      return '<div class="gs-list">' + req.map(function (i) {
        return '<div class="gs-row ' + (i.connected ? 'done' : '') + '"><div class="gk ' + (i.connected ? 'done' : 'todo') + '">' + (i.connected ? '✓' : '○') + '</div>' +
          '<div class="gt">' + esc(i.name) + '</div></div>';
      }).join('') + '</div><div class="hint" style="margin-top:10px">ตั้งค่าคีย์เหล่านี้ในหน้า "การตั้งค่า" — ตอนนี้ข้ามไปดูระบบก่อนได้</div>';
    }
    function projectBody() {
      return '<div style="margin-bottom:10px"><div class="soft small" style="margin-bottom:4px">ชื่อโปรเจ็ค</div><input class="input" id="onb_pname" placeholder="เช่น คลินิกความงาม XYZ" style="width:100%"></div>' +
        '<div><div class="soft small" style="margin-bottom:4px">โดเมนเว็บไซต์</div><input class="input" id="onb_pdom" placeholder="example.com" style="width:100%"></div>' +
        '<div class="hint" style="margin-top:10px">เว้นว่างไว้ก็ได้ — ระบบมีโปรเจ็คตัวอย่าง "เว็บคลินิกความงาม ABC" ให้ลองเล่นทันที</div>';
    }
    function doneBody() {
      return feat('🎯', 'ไปที่ M1', 'ลองขุดคำถามสำหรับสินค้า/บริการของคุณ') +
        feat('📊', 'ดูแดชบอร์ด', 'ภาพรวมทุกคลัสเตอร์และผลการวัด') +
        feat('⚙️', 'เปิดโหมด Live', 'เชื่อม backend เพื่อดึงข้อมูลจริง (ในหน้าการตั้งค่า)');
    }
    function feat(ic, t, s) { return '<div class="onb-feature"><div class="fi">' + ic + '</div><div><div class="ft">' + esc(t) + '</div><div class="fs">' + esc(s) + '</div></div></div>'; }
  };

})(window.RP);
