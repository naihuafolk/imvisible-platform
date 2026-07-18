/* ============================================================
   View: M1 — Question & Keyword Intelligence (ขุดโอกาส)
   ตามโครงการ (หน้า 4):
   - กรอกหัวข้อธุรกิจ/สินค้า → AI ขุด "คำถามจริงที่คนถาม" จากหลายแหล่ง
     (Google PAA, Google Suggest, Pantip, Reddit, คอมเมนต์โซเชียล, Prompt Mining)
   - จัดกลุ่มเป็น Topic Cluster อัตโนมัติ: หัวข้อแม่ (Pillar) + คำถามลูก (Cluster)
     พร้อมประเมินความยาก/โอกาสของแต่ละคำ
   - ชี้เป้า "คำถามที่ AI ยังตอบได้ไม่ดี/ยังไม่มีแหล่งภาษาไทย" = โอกาสติด Citation ง่ายที่สุด
   ============================================================ */
(function (RP) {
  'use strict';
  var ui = RP.ui, esc = RP.esc, fmt = RP.fmt;

  var state = { seed: 'ครีมกันแดด', cluster: null };

  /* ---- stable pseudo-random from string ---- */
  function hash(s) {
    var h = 2166136261 >>> 0;
    for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function rnd(s, mod) { return hash(s) % mod; }

  /* ---- ขุดคำถาม + จัดกลุ่ม Topic Cluster สำหรับหัวข้อแม่ (Pillar) ---- */
  function mine(seed) {
    seed = (seed || '').trim() || 'ครีมกันแดด';
    var srcs = RP.data.m1.sources;
    var questions = RP.data.m1.questionTemplates.map(function (t) {
      var q = t.replace('{kw}', seed);
      var kd = 16 + rnd(q, 66);                       // ความยาก 16–81
      var vol = 260 + rnd(q + 'v', 9400);             // ปริมาณค้นหา/เดือน
      var opp = fmt.clamp(Math.round(97 - kd * 0.82 + rnd(q + 'o', 20)), 20, 99);
      var aiGap = opp >= 70 && rnd(q + 'g', 100) < 62; // AI ยังตอบไม่ดี/ไม่มีแหล่งไทย
      return { q: q, kd: kd, vol: vol, opp: opp, aiGap: aiGap, source: srcs[rnd(q + 's', srcs.length)] };
    });
    questions.sort(function (a, b) { return b.opp - a.opp; });
    return { pillar: seed, questions: questions };
  }

  /* ---- สรุปตัวเลข ---- */
  function summaryKpis() {
    var c = state.cluster;
    var avgKd = Math.round(RP.sum(c.questions, function (q) { return q.kd; }) / c.questions.length);
    var gaps = c.questions.filter(function (q) { return q.aiGap; }).length;
    var vol = RP.sum(c.questions, function (q) { return q.vol; });
    return '<div class="grid grid-4 mb">' +
      ui.kpi({ label: 'คำถามที่ขุดได้', value: fmt.n(c.questions.length), foot: 'จาก ' + RP.data.m1.sources.length + ' แหล่ง' }) +
      ui.kpi({ label: 'โอกาสทอง (AI Gap)', value: fmt.n(gaps), tone: 'brand', foot: 'AI ยังตอบได้ไม่ดี/ไม่มีแหล่งไทย' }) +
      ui.kpi({ label: 'ปริมาณค้นหารวม', value: fmt.n(vol), foot: 'ครั้ง/เดือน (โดยประมาณ)' }) +
      ui.kpi({ label: 'ความยากเฉลี่ย (KD)', value: avgKd, tone: (avgKd <= 40 ? 'pos' : ''), foot: ui.diffLabel(avgKd).t }) +
      '</div>';
  }

  /* ---- แถวคำถามลูก (Cluster) ---- */
  function qRow(q) {
    var d = ui.diffLabel(q.kd);
    var gap = q.aiGap ? ' <span class="badge amber" title="AI ยังตอบได้ไม่ดี/ไม่มีแหล่งไทย">🎯 โอกาสทอง</span>' : '';
    return '<div class="kw-row">' +
      '<span class="badge purple nowrap">Cluster</span>' +
      '<div class="kw"><div class="txt">' + esc(q.q) + gap + '</div>' +
      '<div class="meta">' +
        '<span>🔍 ~' + fmt.n(q.vol) + '/เดือน</span>' +
        '<span class="badge ' + d.c + '">' + d.t + ' · KD ' + q.kd + '</span>' +
        '<span>โอกาส ' + ui.scorePill(q.opp) + '</span>' +
        '<span class="soft">ขุดจาก: ' + esc(q.source) + '</span>' +
      '</div></div>' +
      '<button class="btn btn-sm q-detail" data-q="' + esc(q.q) + '">รายละเอียด</button>' +
      '</div>';
  }

  function clusterCard() {
    var c = state.cluster;
    var rows = c.questions.map(qRow).join('');
    return '<div class="intent-col mb">' +
      '<div class="intent-head rec">' +
      '<span class="ic">🗂️</span>' +
      '<div><div class="h">Topic Cluster: ' + esc(c.pillar) + '</div>' +
      '<div class="c">หัวข้อแม่ (Pillar) + คำถามลูก (Cluster) ' + c.questions.length + ' คำถาม จัดกลุ่มอัตโนมัติ</div></div>' +
      '<span class="count">Pillar</span></div>' +
      '<div>' + rows + '</div>' +
      '</div>';
  }

  function sourcesCard() {
    var chips = RP.data.m1.sources.map(function (s) { return '<span class="chip">🌐 ' + esc(s) + '</span>'; }).join('');
    return ui.card({
      title: 'แหล่งขุดคำถาม (Question Mining)', sub: 'ระบบรวบรวมคำถามจริงที่คนถามจากหลายแหล่ง',
      body: '<div class="tag-list mb">' + chips + '</div>' +
        '<div class="hint">🎯 ชี้เป้า: <b>คำถามที่ AI ยังตอบได้ไม่ดี หรือยังไม่มีแหล่งภาษาไทยอ้างอิง</b> = โอกาสติด Citation ง่ายที่สุด (ตามกลยุทธ์หน้า 5 ของโครงการ)'
    });
  }

  function howCard() {
    return ui.card({
      title: 'M1 ทำงานอย่างไร', sub: 'ขุดคำถามจริง → จัดกลุ่ม Topic Cluster → ชี้โอกาส',
      body:
        '<div class="grid grid-3" style="gap:14px">' +
        howStep('1', '🔎', 'ขุดคำถามจริง', 'รวบรวมจาก Google People Also Ask, Google Suggest, Pantip, Reddit, คอมเมนต์โซเชียล และจำลองการถาม AI (Prompt Mining)') +
        howStep('2', '🗂️', 'จัดกลุ่ม Topic Cluster', 'จัดเป็นหัวข้อแม่ (Pillar) + คำถามลูก (Cluster) อัตโนมัติ พร้อมประเมินความยาก/โอกาสของแต่ละคำ') +
        howStep('3', '🎯', 'ชี้เป้าโอกาสทอง', 'ไฮไลต์คำถามที่ AI ยังตอบได้ไม่ดี/ไม่มีแหล่งไทย — สร้างก่อนได้เปรียบ ติด Citation ง่ายสุด') +
        '</div>'
    });
  }

  function howStep(n, ic, t, d) {
    return '<div class="panel"><div class="panel-body">' +
      '<div class="row gap-s" style="margin-bottom:6px"><span style="font-size:20px">' + ic + '</span>' +
      '<span class="badge purple">ขั้นที่ ' + n + '</span></div>' +
      '<div class="bb" style="margin-bottom:3px">' + esc(t) + '</div>' +
      '<div class="soft small">' + esc(d) + '</div></div></div>';
  }

  /* ---- modal: รายละเอียดคำถาม (ขุดจากไหน / ทำไมเป็นโอกาส / รูปแบบที่แนะนำ) ---- */
  function openDetail(qText) {
    var q = state.cluster.questions.filter(function (x) { return x.q === qText; })[0];
    if (!q) return;
    var variations = [
      qText,
      qText + ' pantip',
      qText.replace(state.cluster.pillar, state.cluster.pillar + ' 2026'),
      'อยากรู้ ' + qText
    ];
    var fmts = RP.data.m2.formats;
    var recFmt = fmts[rnd(qText + 'f', fmts.length)];
    var d = ui.diffLabel(q.kd);
    var body =
      '<div class="grid grid-2 mb">' +
      ui.card({ title: 'ข้อมูลคีย์เวิร์ด', body:
        '<div class="list-row"><div class="grow t small">ปริมาณค้นหา</div><div class="bb">~' + fmt.n(q.vol) + '/เดือน</div></div>' +
        '<div class="list-row"><div class="grow t small">ความยาก (KD)</div><div>' + ui.badge(d.t + ' · ' + q.kd, d.c) + '</div></div>' +
        '<div class="list-row"><div class="grow t small">คะแนนโอกาส</div><div>' + ui.scorePill(q.opp) + '</div></div>' +
        '<div class="list-row"><div class="grow t small">ขุดจากแหล่ง</div><div class="b">' + esc(q.source) + '</div></div>'
      }) +
      ui.card({ title: 'คำแนะนำการผลิต', body:
        '<div class="small" style="margin-bottom:8px">รูปแบบคอนเทนต์ที่แนะนำ:</div>' +
        '<div class="mb"><span class="badge blue">' + esc(recFmt) + '</span></div>' +
        (q.aiGap
          ? '<div class="ok-box">🎯 <b>โอกาสทอง</b> — AI ยังตอบคำถามนี้ได้ไม่ดีหรือยังไม่มีแหล่งภาษาไทยที่ดี ถ้าเราสร้างคอนเทนต์คุณภาพก่อน มีโอกาสถูก AI หยิบไปอ้างอิงสูง</div>'
          : '<div class="hint">คำถามนี้มีคู่แข่งอยู่บ้าง เน้นทำให้ครบและสดใหม่กว่าเดิมเพื่อแย่ง Citation</div>')
      }) +
      '</div>' +
      ui.card({ title: 'รูปแบบคำถามที่พบ (People Also Ask / Suggest)', body:
        variations.map(function (v) { return '<div class="list-row"><span>💬</span><div class="grow t small">' + esc(v) + '</div></div>'; }).join('')
      });
    ui.modal({ title: 'รายละเอียดคำถาม', sub: esc(qText), width: 760, body: body });
  }

  /* ---- main view ---- */
  RP.views.m1 = function () {
    state.cluster = mine(state.seed);

    var searchCard =
      '<div class="card mb"><div class="card-pad">' +
      '<div class="row wrap" style="gap:10px">' +
      '<div class="field" style="flex:1;min-width:240px"><span class="ico">🔎</span>' +
      '<input id="seedInput" placeholder="กรอกหัวข้อธุรกิจ / สินค้า / บริการ เช่น ครีมกันแดด" value="' + esc(state.seed) + '"></div>' +
      '<button class="btn btn-primary" id="genBtn">ขุดคำถาม & จัดกลุ่ม (Auto)</button>' +
      '</div>' +
      '<div class="row wrap" style="gap:8px;margin-top:12px">' +
      '<span class="soft small">ตัวอย่าง:</span>' +
      RP.data.seedExamples.map(function (s) { return '<button class="chip seed-eg" data-seed="' + esc(s) + '">' + esc(s) + '</button>'; }).join('') +
      '</div></div></div>';

    var html =
      ui.pageHead({ eyebrow: 'M1 · Question & Keyword Intelligence', title: 'ขุดคำถาม & คีย์เวิร์ด',
        desc: 'กรอกหัวข้อธุรกิจ/สินค้าเพียงหัวข้อเดียว ระบบจะขุด "คำถามจริงที่คนถาม" จากหลายแหล่ง แล้วจัดกลุ่มเป็น <b>Topic Cluster</b> อัตโนมัติ (หัวข้อแม่ Pillar + คำถามลูก Cluster) พร้อมประเมินความยาก/โอกาส และชี้เป้าคำถามที่ AI ยังตอบได้ไม่ดี' }) +
      searchCard +
      liveMineCard() +
      '<div id="mineOut">' + summaryKpis() + '<div class="grid mb" style="grid-template-columns:1.6fr 1fr">' +
        clusterCard() + sourcesCard() + '</div></div>' +
      howCard();

    return {
      html: html,
      mount: function (root) {
        function refresh() {
          root.querySelector('#mineOut').innerHTML =
            summaryKpis() + '<div class="grid mb" style="grid-template-columns:1.6fr 1fr">' + clusterCard() + sourcesCard() + '</div>';
          wireDetails(root);
        }
        function doGen() {
          var v = root.querySelector('#seedInput').value.trim();
          if (!v) { RP.ui.toast('กรุณากรอกหัวข้อก่อน'); return; }
          state.seed = v; state.cluster = mine(v);
          refresh();
          RP.ui.toast('ขุดคำถามสำหรับ <b>"' + esc(v) + '"</b> แล้ว — จัดกลุ่ม Topic Cluster เรียบร้อย ✓');
        }
        root.querySelector('#genBtn').onclick = doGen;
        root.querySelector('#seedInput').addEventListener('keydown', function (e) { if (e.key === 'Enter') doGen(); });
        Array.prototype.forEach.call(root.querySelectorAll('.seed-eg'), function (b) {
          b.onclick = function () { root.querySelector('#seedInput').value = b.getAttribute('data-seed'); doGen(); };
        });
        var mn = root.querySelector('#m1_mine');
        if (mn) mn.onclick = function () {
          var v = (root.querySelector('#seedInput').value || '').trim() || state.seed;
          RP.live(RP.api.mine(v), mineModal);
        };
        wireDetails(root);
      }
    };
  };

  function liveMineCard() {
    return ui.card({
      title: 'โหมด Live — ขุดคำถามจริง', sub: 'ดึงจาก Google Suggest + People Also Ask ผ่าน backend', cls: 'mb',
      action: RP.api.enabled() ? ui.badge('● Live เปิด', 'green') : ui.badge('Live ปิด', 'amber'),
      body: '<div class="row wrap" style="gap:10px"><div class="soft small" style="flex:1;min-width:200px">ใช้คีย์เวิร์ดในช่องด้านบน แล้วกดปุ่มนี้เพื่อขุด "คำถามจริงที่คนค้นบน Google"</div>' +
        '<button class="btn btn-primary" id="m1_mine">ขุดคำถามจริง (Live)</button></div>' +
        '<div class="hint" style="margin-top:10px">Google Suggest ใช้ได้ฟรี (ไม่ต้องมีคีย์) · People Also Ask ต้องมีคีย์ DataForSEO — ต้องเปิดโหมด Live + รัน backend</div>'
    });
  }

  function mineModal(res) {
    var rows = (res.questions || []).map(function (q) {
      return '<tr><td>' + (q.is_question ? ui.badge('คำถาม', 'purple') : ui.badge('คีย์เวิร์ด', '')) + '</td>' +
        '<td class="tbl-title">' + esc(q.q) + '</td><td class="soft small">' + esc(q.source) + '</td></tr>';
    }).join('');
    ui.modal({ title: 'ผลขุดคำถามจริง — ' + esc(res.pillar), sub: 'พบ ' + res.count + ' รายการ · แหล่ง: ' + (res.sources_used || []).join(', '), width: 760,
      body: '<div class="tbl-wrap"><table class="tbl"><thead><tr><th>ประเภท</th><th>คำถาม / คีย์เวิร์ด</th><th>แหล่ง</th></tr></thead><tbody>' + rows + '</tbody></table></div>' });
  }

  function wireDetails(root) {
    Array.prototype.forEach.call(root.querySelectorAll('.q-detail'), function (b) {
      b.onclick = function () { openDetail(b.getAttribute('data-q')); };
    });
  }

})(window.RP);
