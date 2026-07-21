/* ============================================================
   RankPilot AI — API client (เชื่อม frontend ↔ backend FastAPI)
   โหมด Live: เมื่อเปิด + ตั้ง base URL ของ backend แล้ว view จะดึงข้อมูลจริง
   ค่าเริ่มต้น = ปิด (ใช้ข้อมูลจำลอง) เพื่อให้เปิดไฟล์เฉย ๆ ก็ยังทำงาน
   ============================================================ */
(function (RP) {
  'use strict';
  var LS_BASE = 'rp-api-base', LS_LIVE = 'rp-live';
  function ls(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function save(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  var api = RP.api = {
    base: (ls(LS_BASE) || (location.protocol === 'file:' ? 'http://localhost:8000' : location.origin)).replace(/\/+$/, ''),
    live: (ls(LS_LIVE) !== null) ? (ls(LS_LIVE) === '1') : (location.protocol !== 'file:'),
    token: ls('rp-token') || '',

    setBase: function (u) { api.base = (u || '').trim().replace(/\/+$/, ''); save(LS_BASE, api.base); },
    setLive: function (on) { api.live = !!on; save(LS_LIVE, on ? '1' : '0'); },
    setToken: function (t) { api.token = t || ''; if (t) save('rp-token', t); else { try { localStorage.removeItem('rp-token'); } catch (e) {} } },
    enabled: function () { return !!(api.live && api.base && typeof fetch === 'function'); },
    reachable: function () { return !!(api.base && typeof fetch === 'function'); },

    _headers: function () {
      var h = { 'Content-Type': 'application/json' };
      if (api.token) h['Authorization'] = 'Bearer ' + api.token;
      return h;
    },
    _get: function (path) { return fetch(api.base + path, { headers: api._headers() }).then(chk); },
    _post: function (path, body) {
      return fetch(api.base + path, { method: 'POST', headers: api._headers(), body: JSON.stringify(body) }).then(chk);
    },
    _put: function (path, body) {
      return fetch(api.base + path, { method: 'PUT', headers: api._headers(), body: JSON.stringify(body) }).then(chk);
    },

    health: function () { return api._get('/health'); },
    integrations: function () { return api._get('/api/integrations'); },
    rankCheck: function (keyword, domain) { return api._post('/api/rank/check', { keyword: keyword, domain: domain }); },
    gsc: function (siteUrl, days) { return api._post('/api/gsc/summary', { site_url: siteUrl, days: days || 28 }); },
    citation: function (questions, brandTerms, domain, engines) {
      return api._post('/api/citation/sample', { questions: questions, brand_terms: brandTerms, domain: domain, engines: engines || ['openai', 'gemini', 'perplexity'] });
    },
    generate: function (topic, fmt, words) { return api._post('/api/content/generate', { topic: topic, fmt: fmt || 'บทความยาว', words: words || 1500 }); },
    publish: function (o) { return api._post('/api/publish', o); },
    mine: function (seed) { return api._post('/api/mine', { seed: seed }); },

    // ---- Auth (JWT จริง) ----
    register: function (email, password, name) { return api._post('/api/auth/register', { email: email, password: password, name: name || '' }); },
    signin: function (email, password) { return api._post('/api/auth/login', { email: email, password: password }); },
    me: function () { return api._get('/api/auth/me'); },
    // ---- Projects (DB จริง) ----
    projects: function () { return api._get('/api/projects'); },
    createProject: function (o) { return api._post('/api/projects', o); },
    grow: function (pid) { return api._post('/api/projects/' + pid + '/grow', {}); },
    projectArticles: function (pid) { return api._get('/api/projects/' + pid + '/articles'); },
    setPublishTarget: function (pid, o) { return api._put('/api/projects/' + pid + '/publish', o); },
    // ---- AI Citation ต่อโปรเจ็ค (บันทึกผล → สะสมเป็นแนวโน้ม) ----
    citationForProject: function (pid, questions) { return api._post('/api/projects/' + pid + '/citation/sample', { questions: questions || [] }); },
    citationHistory: function (pid) { return api._get('/api/projects/' + pid + '/citation/history'); },
    rankHistory: function (pid) { return api._get('/api/projects/' + pid + '/rank/history'); },
    insights: function (pid) { return api._get('/api/projects/' + pid + '/insights'); },
    // ---- AEO/SEO Score Engine (M3) — ตัวแปรจัดอันดับที่วัดจริง ----
    projectAeo: function (pid) { return api._get('/api/projects/' + pid + '/aeo'); },
    articleAeo: function (aid) { return api._get('/api/articles/' + aid + '/aeo'); },
    articleOptimize: function (aid) { return api._post('/api/articles/' + aid + '/optimize', {}); },
    // ---- Distribution (ช่องทางกระจาย + Log โปร่งใส) ----
    getChannels: function (pid) { return api._get('/api/projects/' + pid + '/channels'); },
    setChannel: function (pid, o) { return api._put('/api/projects/' + pid + '/channels', o); },
    articleDistribution: function (aid) { return api._get('/api/articles/' + aid + '/distribution'); },
    redistribute: function (aid) { return api._post('/api/articles/' + aid + '/distribute', {}); },
    // ---- Distribution Discovery (หาช่องกระจาย + ร่างคำตอบชุมชน) ----
    analyzeProject: function (pid) { return api._post('/api/projects/' + pid + '/analyze', {}); },
    discover: function (pid) { return api._post('/api/projects/' + pid + '/discover', {}); },
    draftReply: function (pid, o) { return api._post('/api/projects/' + pid + '/draft-reply', o); }
  };

  function chk(r) {
    if (!r.ok) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        throw new Error(j.detail || ('HTTP ' + r.status));
      });
    }
    return r.json();
  }

  // helper สำหรับ view: เรียก backend พร้อม toast error อัตโนมัติ
  RP.live = function (promise, onOk) {
    if (!api.enabled()) { RP.ui.toast('เปิด "โหมด Live" + รัน backend ในหน้า ⚙️ การตั้งค่า ก่อนครับ'); return; }
    RP.ui.toast('กำลังดึงข้อมูลจริงจาก backend…');
    promise.then(onOk).catch(function (e) {
      RP.ui.toast('เชื่อม backend ไม่ได้: ' + RP.esc(e.message || String(e)));
    });
  };

})(window.RP);
