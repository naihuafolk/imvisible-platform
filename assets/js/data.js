/* ============================================================
   RankPilot AI — Central mock dataset (single source of truth)
   ทุก view อ่านจาก RP.data.<key> ตาม schema นี้
   *** อ้างอิงเนื้อหาจากเอกสารโครงการ (PDF) v1.0 เท่านั้น ***
   ============================================================ */
(function (RP) {
  'use strict';

  RP.data = {
    /* ---- เอกสาร/แบรนด์ ---- */
    meta: {
      product: 'RankPilot AI',
      tagline: 'แพลตฟอร์ม AEO + SEO เฉพาะทาง อัตโนมัติด้วย AI — ให้แบรนด์ "ติดคำตอบ" ทั้งบน Google และ AI Search',
      version: '1.0',
      docDate: '18 กรกฎาคม 2569',
      channels: ['Google Search', 'AI Overviews / AI Mode', 'ChatGPT', 'Gemini', 'Perplexity'],
      autoLevel: 92 // % งานที่ระบบทำเองได้ (90–95%)
    },

    /* ---- โปรเจ็ค (รองรับหลายโปรเจ็ค) ---- */
    project: {
      current: 'abc',
      list: [
        { id: 'abc', name: 'เว็บคลินิกความงาม ABC', domain: 'abc-beautyclinic.com', mode: 'approve',
          country: 'ไทย', lang: 'ภาษาไทย', plan: 'Pro', status: 'active', created: '2 เดือนก่อน',
          keywords: 312, clusters: 6, competitors: ['competitor-a.com', 'clinic-b.co.th'],
          brandTerms: ['ABC Clinic', 'คลินิกความงาม ABC', 'abc-beautyclinic.com'],
          promptSet: 48, freshnessDays: 120, authors: 2,
          health: { gsc: true, serp: true, ai: true, publish: true } },
        { id: 'derma', name: 'เดอร์มา สกินแคร์', domain: 'dermaskin.co', mode: 'auto',
          country: 'ไทย', lang: 'ภาษาไทย', plan: 'Pro', status: 'active', created: '5 สัปดาห์ก่อน',
          keywords: 174, clusters: 4, competitors: ['skinstore.co.th'],
          brandTerms: ['Derma Skincare', 'เดอร์มา', 'dermaskin.co'],
          promptSet: 30, freshnessDays: 90, authors: 1,
          health: { gsc: true, serp: true, ai: true, publish: true } },
        { id: 'wellness', name: 'เวลเนส เซ็นเตอร์ BKK', domain: 'wellnessbkk.com', mode: 'approve',
          country: 'ไทย', lang: 'ภาษาไทย', plan: 'Pro', status: 'setup', created: '3 วันก่อน',
          keywords: 40, clusters: 1, competitors: [],
          brandTerms: ['Wellness BKK', 'wellnessbkk.com'],
          promptSet: 12, freshnessDays: 120, authors: 0,
          health: { gsc: true, serp: true, ai: false, publish: false } }
      ]
    },

    /* ---- บัญชี & การเชื่อมต่อ (ระดับบัญชี ใช้ร่วมทุกโปรเจ็ค) ---- */
    account: {
      owner: 'sengmakisus@gmail.com',
      plan: 'SaaS — Pro',
      projectQuota: 3,
      billingCycle: 'รายเดือน · ต่ออายุ 1 ส.ค.',
      whiteLabel: true,
      team: [
        { name: 'คุณเจ้าของบัญชี', email: 'sengmakisus@gmail.com', role: 'เจ้าของ (Owner)' },
        { name: 'ทีมคอนเทนต์', email: 'content@abc-clinic.com', role: 'บรรณาธิการ (Editor)' },
        { name: 'ลูกค้า ABC', email: 'view@abc-clinic.com', role: 'ดูอย่างเดียว (Viewer)' }
      ],
      // การเชื่อมต่อที่ลูกค้าต้องตั้งค่า — required=true คือจำเป็นก่อนวัดผลจริง
      integrations: [
        { id: 'llm', name: 'LLM API — ผลิต & วิเคราะห์คอนเทนต์', provider: 'Anthropic Claude · OpenAI · Google Gemini', powers: 'M2 ผลิตบทความ + M6 วิเคราะห์ (Multi-Model คุมต้นทุน)', connected: true, detail: 'เชื่อม 3 โมเดล', required: true },
        { id: 'serp', name: 'SERP API — อันดับ Google', provider: 'DataForSEO / SerpAPI', powers: 'M5 ติดตามอันดับจริงรายวัน + M1 ขุดคำถาม', connected: true, detail: 'DataForSEO', required: true },
        { id: 'gsc', name: 'Google Search Console', provider: 'OAuth + ยืนยันโดเมน', powers: 'คลิก/Impressions/อันดับ ตัวเลขจริงจาก Google', connected: true, detail: 'ยืนยันโดเมนแล้ว', required: true },
        { id: 'aiapi', name: 'API วัด AI Citation (Prompt Sampling)', provider: 'OpenAI · Google · Perplexity', powers: 'M5 ยิงคำถามไปที่ AI แล้ววัด Citation / Share of Voice', connected: true, detail: '3 เอนจิน', required: true },
        { id: 'wp', name: 'WordPress REST API', provider: 'Application Password', powers: 'M4 เผยแพร่บทความอัตโนมัติ', connected: true, detail: 'abc-beautyclinic.com', required: true },
        { id: 'webflow', name: 'Webflow API', provider: 'Site API Token', powers: 'M4 เผยแพร่ไปเว็บ Webflow', connected: false, detail: 'ยังไม่เชื่อม', required: false },
        { id: 'indexnow', name: 'IndexNow', provider: 'Bing / Yandex', powers: 'แจ้ง Index ทันทีที่เผยแพร่', connected: true, detail: 'พร้อมใช้', required: false },
        { id: 'ga4', name: 'Google Analytics 4', provider: 'Measurement API', powers: 'วัด Conversion / ROI (Lead/ยอดขาย)', connected: false, detail: 'ยังไม่เชื่อม (แนะนำ)', required: false },
        { id: 'notify', name: 'LINE Notify + Email', provider: 'LINE / SMTP', powers: 'แจ้งเตือน + ส่งรายงานสรุปรายสัปดาห์', connected: true, detail: 'LINE + อีเมล', required: false }
      ]
    },

    /* ---- ขั้นตอนตั้งค่าก่อนวัดผลจริง (Onboarding) ---- */
    onboarding: [
      { t: 'สร้างโปรเจ็ค + ใส่โดเมน/ประเทศ/ภาษา', done: true },
      { t: 'เชื่อม LLM API (Claude/GPT/Gemini)', done: true },
      { t: 'เชื่อม SERP API (อันดับ Google)', done: true },
      { t: 'ยืนยันโดเมนกับ Google Search Console', done: true },
      { t: 'เชื่อม API วัด AI Citation (ChatGPT/Gemini/Perplexity)', done: true },
      { t: 'เชื่อมปลายทางเผยแพร่ (WordPress/Webflow)', done: true },
      { t: 'ใส่คีย์เวิร์ด/คู่แข่ง/ชื่อแบรนด์ + ชุดคำถาม Prompt Sampling', done: true },
      { t: 'เชื่อม GA4 เพื่อวัด Conversion/ROI', done: false },
      { t: 'ตั้งโหมดเผยแพร่ + ปฏิทินคอนเทนต์', done: true }
    ],

    /* ---- KPI แดชบอร์ดหลัก (ตรงกับ Wireframe หน้า 6) ---- */
    kpis: [
      { label: 'บทความที่เผยแพร่แล้ว', value: '128', tone: '', foot: '<span class="trend-up">▲ +14</span> ใน 30 วัน' },
      { label: 'คีย์เวิร์ดติดหน้า 1 Google', value: '41', tone: 'brand', foot: 'จาก 312 คีย์เวิร์ดที่ติดตาม' },
      { label: 'AI Citation Share of Voice', value: '23%', tone: 'brand', foot: 'ChatGPT · Gemini · Perplexity' },
      { label: 'ทราฟฟิก 90 วันล่าสุด', value: '+186%', tone: 'pos', foot: 'Organic + AI Referral' }
    ],

    /* ---- สถิติอ้างอิง (หน้า 2) ---- */
    facts: [
      { v: '52%', d: 'ของผู้ใหญ่สหรัฐฯ ใช้ LLM อย่าง ChatGPT/Gemini แล้ว' },
      { v: '~68%', d: 'ของการค้นหาบน Google จบแบบไม่คลิกเข้าเว็บ (ต้นปี 2026)' },
      { v: '4.4 เท่า', d: 'ทราฟฟิกจาก AI Search มีมูลค่าคอนเวอร์ชันสูงกว่า Organic ปกติ' },
      { v: '83%', d: 'ของ Citation เชิงพาณิชย์มาจากหน้าที่อัปเดตภายใน 12 เดือน' }
    ],

    /* ---- ปัจจัยที่ทำให้คอนเทนต์ถูก AI หยิบไปตอบ (หน้า 2.1) ---- */
    aeoFactors: [
      { t: 'ตอบตรงคำถามทันที (Answer-First)', d: 'เปิดแต่ละหัวข้อด้วยคำตอบสั้น 40–60 คำ ที่จบในตัวเอง ก่อนลงรายละเอียด' },
      { t: 'โครงสร้างหัวข้อชัดเจน', d: 'ลำดับ H2 → H3 → H4 เป็นระบบ ให้ Citation Lift สูงกว่าคอนเทนต์ไร้โครงสร้างถึง ~2.8 เท่า' },
      { t: 'Schema Markup', d: 'FAQPage, HowTo, Article, Author ที่ตรงกับเนื้อหาจริงบนหน้า' },
      { t: 'ความสดใหม่ (Freshness)', d: 'หน้าที่อัปเดตภายใน 6 เดือนครองการอ้างอิง — หน้าที่ไม่รีเฟรชเสี่ยงหลุดจาก Citation ~3 เท่า' },
      { t: 'ข้อมูลต้นฉบับ (Original Data)', d: 'สถิติ/ผลสำรวจ/ข้อมูลที่เราทำเอง ได้ Citation ที่คอนเทนต์รีไรต์ทั่วไปไม่มีวันได้' },
      { t: 'Topical Authority', d: 'ครอบคลุมคำถามทั้งคลัสเตอร์ของหัวข้อ ไม่ใช่เขียนหน้าเดียวโดด ๆ' },
      { t: 'E-E-A-T', d: 'แสดงประสบการณ์ ความเชี่ยวชาญ ตัวตนผู้เขียน และแหล่งอ้างอิงที่ตรวจสอบได้' }
    ],

    /* ---- AI Growth Loop (หน้า 3–4) ---- */
    loop: [
      { n: '1. DISCOVER', t: 'ขุดโอกาส', d: 'ขุดคำถาม/คีย์เวิร์ดเฉพาะทาง' },
      { n: '2. CREATE', t: 'ผลิตคอนเทนต์', d: 'AI ผลิตคอนเทนต์คุณภาพ E-E-A-T' },
      { n: '3. OPTIMIZE', t: 'ติดโครงสร้าง', d: 'ใส่โครงสร้าง AEO + Schema' },
      { n: '4. PUBLISH', t: 'เผยแพร่', d: 'เผยแพร่ + แจ้ง Index อัตโนมัติ' },
      { n: '5. MEASURE', t: 'วัดผล', d: 'วัดอันดับ + AI Citation' },
      { n: '6. LEARN', t: 'เรียนรู้', d: 'AI ปรับกลยุทธ์ → วนกลับข้อ 1' }
    ],

    /* ---- คลัสเตอร์ (ตารางแดชบอร์ด — แถวแรก 3 ตรงกับ Wireframe) ---- */
    clusters: [
      { id: 'laser', name: 'เลเซอร์หน้าใส', articles: 32, total: 40, avgRank: 4.2, cited: ['ChatGPT', 'Gemini'], status: 'loop', sov: 31, kd: 42, traffic90: 214 },
      { id: 'filler', name: 'ฟิลเลอร์', articles: 18, total: 35, avgRank: 8.7, cited: ['Perplexity'], status: 'producing', sov: 17, kd: 55, traffic90: 96 },
      { id: 'cosmetic-review', name: 'รีวิวเครื่องสำอาง', articles: 5, total: 50, avgRank: null, cited: [], status: 'approve', pending: 12, sov: 0, kd: 38, traffic90: 12 },
      { id: 'sunscreen', name: 'ครีมกันแดด', articles: 27, total: 45, avgRank: 5.6, cited: ['ChatGPT', 'Perplexity'], status: 'loop', sov: 24, kd: 47, traffic90: 158 },
      { id: 'skincare', name: 'ดูแลผิว / สกินแคร์', articles: 34, total: 48, avgRank: 6.1, cited: ['ChatGPT', 'Gemini', 'Perplexity'], status: 'loop', sov: 28, kd: 51, traffic90: 173 },
      { id: 'botox', name: 'โบท็อกซ์', articles: 12, total: 30, avgRank: 9.3, cited: [], status: 'producing', sov: 6, kd: 58, traffic90: 41 }
    ],

    /* ---- M1 — Question & Keyword Intelligence (หน้า 4) ----
       ขุดคำถามจริงจากหลายแหล่ง → จัดกลุ่ม Topic Cluster (Pillar + Cluster)
       → ประเมินความยาก/โอกาส → ชี้เป้าคำถามที่ AI ยังตอบได้ไม่ดี/ไม่มีแหล่งไทย */
    m1: {
      sources: ['Google People Also Ask', 'Google Suggest', 'Pantip', 'Reddit', 'คอมเมนต์โซเชียล', 'Prompt Mining (จำลองการถาม AI)'],
      questionTemplates: [
        '{kw} คืออะไร',
        '{kw} ราคาเท่าไหร่ 2026',
        '{kw} ยี่ห้อไหนดี',
        '{kw} ทำที่ไหนดี',
        'ข้อดีข้อเสียของ {kw}',
        '{kw} อันตรายไหม เจ็บไหม',
        '{kw} เหมาะกับใคร',
        '{kw} เตรียมตัวก่อนทำยังไง',
        '{kw} อยู่ได้นานแค่ไหน',
        'รีวิว {kw} จากคนใช้จริง',
        '{kw} ต่างจากทางเลือกอื่นยังไง',
        '{kw} ดูแลหลังทำยังไง'
      ]
    },
    seedExamples: ['ครีมกันแดด', 'เลเซอร์หน้าใส', 'ฟิลเลอร์ริมฝีปาก', 'ร้อยไหม', 'โบท็อกซ์'],

    /* ---- M2 — โรงงานคอนเทนต์ (หน้า 4–5) ---- */
    m2: {
      formats: ['บทความยาว', 'หน้าเปรียบเทียบ', 'หน้า "X คืออะไร"', 'รีวิว', 'Listicle', 'Programmatic'],
      queue: [
        { title: 'เลเซอร์หน้าใสยี่ห้อไหนดี 2026 เปรียบเทียบ 8 รุ่นยอดนิยม', cluster: 'เลเซอร์หน้าใส', format: 'หน้าเปรียบเทียบ', words: 1680, aeo: 96, fact: 'pass', plag: 2, status: 'ready', author: 'พญ. ธิดา (ผิวหนัง)' },
        { title: 'ฟิลเลอร์ริมฝีปากอยู่ได้นานแค่ไหน? สรุปจากงานวิจัย', cluster: 'ฟิลเลอร์', format: 'บทความยาว', words: 1420, aeo: 91, fact: 'pass', plag: 1, status: 'ready', author: 'พญ. ธิดา (ผิวหนัง)' },
        { title: 'ครีมกันแดดหน้าไม่วอก สำหรับผิวมัน ต้องดูอะไรบ้าง', cluster: 'ครีมกันแดด', format: 'บทความยาว', words: 1540, aeo: 94, fact: 'pass', plag: 3, status: 'scheduled', author: 'ภก. วิทย์ (เภสัชกร)' },
        { title: 'โบท็อกซ์กรามเจ็บไหม? รวมทุกคำถามก่อนตัดสินใจ', cluster: 'โบท็อกซ์', format: 'หน้า "X คืออะไร"', words: 1290, aeo: 78, fact: 'review', plag: 5, status: 'factcheck', author: 'พญ. ธิดา (ผิวหนัง)' },
        { title: 'รีวิวสกินแคร์ลดสิว 2026 ที่คนผิวแพ้ง่ายใช้จริง', cluster: 'ดูแลผิว / สกินแคร์', format: 'รีวิว', words: 1610, aeo: 88, fact: 'pass', plag: 2, status: 'draft', author: 'ภก. วิทย์ (เภสัชกร)' },
        { title: 'ตารางเปรียบเทียบราคาเลเซอร์แต่ละชนิด (Programmatic)', cluster: 'เลเซอร์หน้าใส', format: 'Programmatic', words: 720, aeo: 84, fact: 'pass', plag: 0, status: 'draft', author: 'ระบบ (ข้อมูลจริง)' }
      ],
      aeoChecklist: [
        { t: 'คำตอบสั้น 40–60 คำ ต้นบทความ (Answer-First)', on: true },
        { t: 'โครงสร้าง H2 → H3 → H4 เป็นระบบ', on: true },
        { t: 'มีส่วน FAQ ตรงกับ People Also Ask', on: true },
        { t: 'ตาราง/ข้อมูลเปรียบเทียบ', on: true },
        { t: 'ผูก Author Persona + แหล่งอ้างอิงจริง (E-E-A-T)', on: true },
        { t: 'AI Fact-Check ข้ามแหล่ง', on: true },
        { t: 'ตรวจความซ้ำ (Plagiarism) < 5%', on: true }
      ]
    },

    /* ---- M3 — AEO Optimizer (หน้า 5) ---- */
    m3: {
      schema: [
        { t: 'FAQPage', pages: 112, total: 128, pct: 88 },
        { t: 'Article', pages: 128, total: 128, pct: 100 },
        { t: 'HowTo', pages: 46, total: 128, pct: 36 },
        { t: 'Author', pages: 128, total: 128, pct: 100 },
        { t: 'Organization', pages: 128, total: 128, pct: 100 },
        { t: 'Product', pages: 61, total: 128, pct: 48 }
      ],
      llmsTxt: { status: 'ok', updated: 'วันนี้ 09:12', entries: 128 },
      sitemap: { status: 'ok', urls: 134, submitted: true },
      internalLinks: { total: 892, orphan: 3, avgPerPage: 7 },
      freshness: [
        { title: 'เลเซอร์หน้าใสราคาเท่าไหร่ 2026', age: '5 เดือน 20 วัน', due: 'ใกล้ครบ 6 เดือน', act: 'คิวรีเฟรช' },
        { title: 'ฟิลเลอร์ปากราคาเท่าไหร่', age: '5 เดือน 12 วัน', due: 'ใกล้ครบ 6 เดือน', act: 'คิวรีเฟรช' },
        { title: 'ครีมกันแดดยี่ห้อไหนดี 2025', age: '5 เดือน 4 วัน', due: 'อัปเดตปี พ.ศ.', act: 'คิวรีเฟรช' },
        { title: 'โบท็อกซ์กรามราคา', age: '4 เดือน 28 วัน', due: 'เฝ้าระวัง', act: 'ติดตาม' }
      ],
      audit: [
        { t: 'ความเร็ว (LCP)', val: '1.9s', ok: true },
        { t: 'Core Web Vitals', val: 'ผ่าน 124/128', ok: true },
        { t: 'Mobile-friendly', val: '100%', ok: true },
        { t: 'Index Coverage', val: '128/134', ok: false }
      ]
    },

    /* ---- M4 — Auto Publisher (หน้า 5) ---- */
    m4: {
      mode: 'approve', // 'auto' | 'approve'
      targets: [
        { name: 'abc-beautyclinic.com', type: 'WordPress REST API', status: 'เชื่อมต่อแล้ว', ok: true },
        { name: 'blog.abc-beautyclinic.com', type: 'Webflow API', status: 'เชื่อมต่อแล้ว', ok: true },
        { name: 'IndexNow', type: 'Bing / Yandex', status: 'พร้อม Ping', ok: true }
      ],
      calendar: [
        { date: 'จ. 20 ก.ค.', title: 'ครีมกันแดดหน้าไม่วอก สำหรับผิวมัน', cluster: 'ครีมกันแดด', time: '09:00' },
        { date: 'อ. 21 ก.ค.', title: 'เลเซอร์หน้าใส vs IPL ต่างกันยังไง', cluster: 'เลเซอร์หน้าใส', time: '09:00' },
        { date: 'พ. 22 ก.ค.', title: 'ฟิลเลอร์ใต้ตา อันตรายไหม', cluster: 'ฟิลเลอร์', time: '10:30' },
        { date: 'พฤ. 23 ก.ค.', title: 'รีวิวเซรั่มวิตซีลดจุดด่างดำ', cluster: 'ดูแลผิว / สกินแคร์', time: '09:00' }
      ],
      approval: [
        { title: 'รีวิวรองพื้นคุมมันสำหรับผิวผสม 2026', cluster: 'รีวิวเครื่องสำอาง', words: 1490, aeo: 90 },
        { title: 'มาสคาร่ากันน้ำ ตัวไหนไม่เป็นแพนด้า', cluster: 'รีวิวเครื่องสำอาง', words: 1230, aeo: 86 },
        { title: 'ลิปแมตต์ติดทน ยี่ห้อไหนดี', cluster: 'รีวิวเครื่องสำอาง', words: 1180, aeo: 88 }
      ],
      pendingCount: 12,
      indexPings: [
        { url: '/laser-price-2026', ts: '09:41', ok: true },
        { url: '/filler-lips-guide', ts: '09:41', ok: true },
        { url: '/sunscreen-oily-skin', ts: '08:03', ok: true }
      ]
    },

    /* ---- M5 — AI Visibility & Rank Tracker (หน้า 5) ---- */
    m5: {
      seo: {
        keywordsTracked: 312, page1: 41, page1Prev: 33, top3: 12,
        avgPosition: 11.4, avgPositionPrev: 14.8,
        clicks90: [820, 910, 1040, 1180, 1360, 1520, 1690, 1880, 2110, 2340, 2610, 2980],
        impressions90: [42, 46, 51, 58, 64, 71, 79, 88, 97, 108, 121, 138]
      },
      citation: {
        sov: 23, sovPrev: 18,
        engines: [
          { name: 'ChatGPT', us: 27, comp: 41, none: 32 },
          { name: 'Gemini', us: 21, comp: 47, none: 32 },
          { name: 'Perplexity', us: 19, comp: 44, none: 37 }
        ],
        sovTrend: [11, 13, 14, 16, 17, 18, 19, 21, 22, 23],
        competitors: [
          { name: 'เว็บเรา (ABC)', sov: 23, us: true },
          { name: 'คู่แข่ง A', sov: 34 },
          { name: 'คู่แข่ง B', sov: 19 },
          { name: 'Pantip', sov: 15 },
          { name: 'อื่น ๆ', sov: 9 }
        ]
      },
      prompts: [
        { q: 'เลเซอร์หน้าใสยี่ห้อไหนดี', chatgpt: true, gemini: true, perplexity: false, pos: 2 },
        { q: 'ฟิลเลอร์ริมฝีปากอยู่ได้นานแค่ไหน', chatgpt: true, gemini: false, perplexity: true, pos: 1 },
        { q: 'ครีมกันแดดหน้าไม่วอก แนะนำ', chatgpt: true, gemini: true, perplexity: true, pos: 1 },
        { q: 'โบท็อกซ์กรามเจ็บไหม', chatgpt: false, gemini: false, perplexity: false, pos: null },
        { q: 'เลเซอร์หน้าใสราคาเท่าไหร่', chatgpt: true, gemini: false, perplexity: false, pos: 3 },
        { q: 'สกินแคร์ลดสิวผิวแพ้ง่าย', chatgpt: false, gemini: true, perplexity: true, pos: 2 }
      ]
    },

    /* ---- M6 — Learning Loop (หน้า 5) ---- */
    m6: {
      insights: [
        { t: 'ความยาวที่ได้ Citation สูงสุด', v: '1,400–1,800 คำ', note: 'บทความสั้นกว่า 900 คำ ถูกอ้างอิงน้อยลง ~3 เท่า' },
        { t: 'มี FAQ Schema', v: 'เพิ่มโอกาส Citation +38%', note: 'AI ชอบหยิบส่วน FAQ ที่ตอบตรงคำถาม' },
        { t: 'เปิดด้วย Answer-First 40–60 คำ', v: 'Citation Lift ~2.6 เท่า', note: 'สอดคล้องกับปัจจัยหน้า 2 ของโครงการ' },
        { t: 'อัปเดตภายใน 90 วัน', v: 'ครองการอ้างอิงต่อเนื่อง', note: 'Freshness Engine จึงสำคัญมาก' }
      ],
      actions: [
        { t: 'ปรับเทมเพลต "หน้าเปรียบเทียบ" ให้ใส่ตารางสรุปด้านบนสุด', when: 'ใช้กับคิวรอบถัดไปแล้ว', ok: true },
        { t: 'เพิ่มน้ำหนักคลัสเตอร์ "ครีมกันแดด" (Citation กำลังมา)', when: 'ปรับลำดับคิวอัตโนมัติ', ok: true },
        { t: 'ลดความถี่คลัสเตอร์ "โบท็อกซ์" (แข่งสูง ยังไม่ติด)', when: 'รอผลอีก 2 สัปดาห์', ok: false }
      ],
      weeklyReport: {
        published: 14, newPage1: 8, citationsGained: 11, refreshed: 6,
        humanHours: 1.6,
        sentTo: 'อีเมล + LINE Notify'
      }
    },

    /* ---- Roadmap (หน้า 9) ---- */
    roadmap: [
      { phase: 'เฟส 1 — MVP', scope: 'M1 ขุดคำถาม + M2 โรงงานคอนเทนต์ + เผยแพร่เข้า WordPress + ติดตามอันดับพื้นฐาน', weeks: '4–6 สัปดาห์', progress: 100 },
      { phase: 'เฟส 2 — AEO Core', scope: 'M3 Schema/llms.txt/Internal Link อัตโนมัติ + M5 Prompt Sampling วัด AI Citation', weeks: '4 สัปดาห์', progress: 72 },
      { phase: 'เฟส 3 — Full Auto', scope: 'M6 Learning Loop + Freshness Engine + โหมดอัตโนมัติ 100% + แจ้งเตือน LINE', weeks: '4–5 สัปดาห์', progress: 30 },
      { phase: 'เฟส 4 — Scale', scope: 'Multi-Project, ระบบลูกค้า/สิทธิ์, รายงาน White-Label, เปิด SaaS', weeks: '4–6 สัปดาห์', progress: 8 }
    ],

    /* ---- KPI เป้าหมาย 6 เดือน (หน้า 9.1) ---- */
    kpiTargets: [
      { kpi: 'จำนวนคีย์เวิร์ดติดหน้า 1 Google', target: '30–60 คีย์เวิร์ด', current: 41, curTxt: '41', pct: 82 },
      { kpi: '% คำถามเป้าหมายที่ AI อ้างอิงเรา (Citation SoV)', target: '15–25%', current: 23, curTxt: '23%', pct: 92 },
      { kpi: 'ทราฟฟิก Organic + AI Referral', target: 'เติบโต 3–5 เท่า', current: 2.86, curTxt: '2.86 เท่า', pct: 71 },
      { kpi: 'ต้นทุนต่อบทความที่ติดหน้า 1', target: '< 500 บาท/บทความ', current: 372, curTxt: '฿372', pct: 100 },
      { kpi: 'สัดส่วนงานที่ระบบทำเอง', target: '≥ 90%', current: 92, curTxt: '92%', pct: 100 }
    ],

    /* ---- สถาปัตยกรรม/เทคโนโลยี (หน้า 7) ---- */
    stack: [
      { part: 'Frontend', tech: 'Next.js + Tailwind CSS', note: 'แดชบอร์ด + กราฟเรียลไทม์' },
      { part: 'Backend API', tech: 'Python (FastAPI)', note: 'เหมาะกับงาน AI/Data pipeline' },
      { part: 'ฐานข้อมูล', tech: 'PostgreSQL + Vector DB (pgvector)', note: 'เก็บคอนเทนต์ + Embedding วิเคราะห์คลัสเตอร์' },
      { part: 'คิวงานอัตโนมัติ', tech: 'Redis + Celery', note: 'คิวผลิต/เผยแพร่/วัดผล ทำงาน 24 ชม.' },
      { part: 'AI Engine', tech: 'LLM API (Claude, GPT, Gemini) แบบ Multi-Model', note: 'ใช้โมเดลแพงเฉพาะงานเขียน โมเดลถูกสำหรับคัดกรอง — คุมต้นทุน' },
      { part: 'ข้อมูลคีย์เวิร์ด/อันดับ', tech: 'SERP API (DataForSEO / SerpAPI) + Google Search Console API', note: 'เสถียรและถูกต้องตามเงื่อนไขบริการ' },
      { part: 'วัด AI Citation', tech: 'API ของ ChatGPT/Gemini/Perplexity ยิงชุดคำถามตามรอบ', note: 'Prompt Sampling รายสัปดาห์ต่อโปรเจ็ค' },
      { part: 'เผยแพร่', tech: 'WordPress REST API / Webflow API / IndexNow', note: 'รองรับหลายเว็บต่อบัญชี' }
    ],

    /* ---- โมเดลธุรกิจ (หน้า 8) ---- */
    pricing: [
      { plan: 'ใช้เอง (เฟสแรก)', detail: 'ดันเว็บ/ธุรกิจของเราเองให้ติดอันดับ+Citation เพื่อสร้าง Case Study จริง', price: '—' },
      { plan: 'Agency Service', detail: 'รับทำ AEO+SEO ให้ลูกค้ารายเดือน โดยใช้แพลตฟอร์มเป็นเครื่องยนต์หลังบ้าน', price: '15,000–50,000 บาท/เดือน/ลูกค้า' },
      { plan: 'SaaS — Starter', detail: '1 เว็บ, 60 บทความ/เดือน, ติดตาม 100 คีย์เวิร์ด, วัด AI Citation รายสัปดาห์', price: '2,900–4,900 บาท/เดือน' },
      { plan: 'SaaS — Pro', detail: '3 เว็บ, ไม่จำกัดบทความ, Freshness Engine, รายงาน White-Label', price: '9,900–14,900 บาท/เดือน' },
      { plan: 'SaaS — Enterprise', detail: 'ไม่จำกัดเว็บ, API, ทีม Onboarding, SLA', price: 'เริ่ม 29,900 บาท/เดือน' }
    ],

    /* ---- ต้นทุน/โปรเจ็ค/เดือน (หน้า 7.1) ---- */
    costs: [
      { item: 'LLM API (ผลิต+รีเฟรช ~40 บทความ/เดือน + วิเคราะห์)', est: '1,000–2,500 บาท' },
      { item: 'SERP API + ติดตามอันดับรายวัน (~300 คีย์เวิร์ด)', est: '700–1,500 บาท' },
      { item: 'Prompt Sampling วัด AI Citation (รายสัปดาห์)', est: '300–800 บาท' },
      { item: 'Server/Infra เฉลี่ยต่อโปรเจ็ค', est: '300–600 บาท' }
    ],
    costTotal: '~2,300–5,400 บาท/โปรเจ็ค/เดือน',

    /* ---- กลยุทธ์ที่ทำให้ "เห็นผลจริง" (หน้า 5) ---- */
    strategies: [
      { t: 'เจาะ Niche ทีละคลัสเตอร์ ไม่หว่าน', d: 'AI ให้น้ำหนัก Topical Authority — เว็บที่ตอบครบทั้งหัวข้อ 30–50 หน้าในเรื่องเดียว ชนะเว็บใหญ่ที่เขียนกระจัดกระจาย เหมาะกับการเริ่มจากศูนย์' },
      { t: 'ยึดคำถามภาษาไทยที่ยังไม่มีใครตอบดี ๆ', d: 'สนามภาษาไทยมีคู่แข่งด้าน AEO น้อยมาก การเป็น "แหล่งอ้างอิงภาษาไทยที่ดีที่สุด" ทำได้เร็วกว่าภาษาอังกฤษหลายเท่า' },
      { t: 'สร้างข้อมูลต้นฉบับ (Original Data)', d: 'ระบบรวบรวมสถิติ/ทำโพล/สรุปตัวเลขจากข้อมูลสาธารณะเป็น "รายงานต้นฉบับ" — คอนเทนต์แบบนี้ถูก AI อ้างอิงมากที่สุดและคู่แข่งลอกยาก' },
      { t: 'Freshness เป็นระบบ ไม่ใช่แคมเปญ', d: 'คู่แข่งส่วนใหญ่เขียนแล้วทิ้ง — Freshness Engine ที่รีเฟรชอัตโนมัติทำให้เราครองพื้นที่ระยะยาวโดยไม่ต้องเพิ่มแรงคน' },
      { t: 'สร้างตัวตนนอกเว็บ (Off-Page Signals)', d: 'AI มักดึงคำตอบจากแหล่งชุมชน (Pantip, Reddit, Wikipedia, YouTube) — ระบบช่วยแนะนำ/เตรียมเนื้อหาสำหรับช่องทางเหล่านี้ให้สอดคล้องกับคลัสเตอร์ที่กำลังดัน' },
      { t: 'วัดผลที่ Conversion ไม่ใช่แค่อันดับ', d: 'ทราฟฟิกจาก AI Search คอนเวิร์ตสูงกว่าปกติ ~4.4 เท่า — แดชบอร์ดผูกกับเป้าหมายธุรกิจ (Lead/ยอดขาย) เพื่อพิสูจน์ ROI ชัดเจน' }
    ],
    strategyNote: 'กรอบเวลาที่ควรคาดหวัง (ตามจริง): คีย์เวิร์ดแข่งขันต่ำเริ่มเห็นการติดอันดับ/Citation ได้ใน 4–8 สัปดาห์, คลัสเตอร์เต็มรูปแบบเห็นผลชัดเจนใน 3–6 เดือน — แพลตฟอร์มไหนที่สัญญาว่า "ติดหน้า 1 ใน 7 วัน" คือสัญญาที่ไม่จริง',

    /* ---- ความเสี่ยง (หน้า 10) ---- */
    risks: [
      { t: 'นโยบายคุณภาพของ Google', d: 'Google แบน "คอนเทนต์ไร้คุณค่าที่ผลิตจำนวนมากเพื่อปั่นอันดับ" (Scaled Content Abuse) — M2 จึงต้องมี Fact-Check + เกณฑ์คุณภาพขั้นต่ำ และควรเริ่มแบบ Auto + Human Approve ก่อน' },
      { t: 'การวัด AI Citation ไม่มี API ทางการ', d: 'ทุกเครื่องมือใช้วิธีสุ่มยิงคำถามแล้วดูคำตอบ ผลจึงเป็น "ค่าประมาณเชิงสถิติ" ไม่ใช่ตัวเลขสัมบูรณ์ และคำตอบ AI เปลี่ยนไปตามผู้ใช้/เวลา' },
      { t: 'ต้นทุน LLM ผันผวน', d: 'ออกแบบ Multi-Model ตั้งแต่แรก เพื่อสลับโมเดลตามราคา/คุณภาพได้โดยไม่ต้องรื้อระบบ' },
      { t: 'ผลลัพธ์ต้องใช้เวลา', d: 'SEO/AEO เป็นเกม 3–6 เดือน หากทำเป็นบริการลูกค้า ต้องตั้งความคาดหวังลูกค้าให้ถูกตั้งแต่เซ็นสัญญา' },
      { t: 'อย่าใช้เทคนิคสายเทา', d: 'สแปมลิงก์/รีวิวปลอม/ปั๊มหน้าซ้ำ ๆ เสี่ยงโดนลงโทษทั้งโดเมนแบบกู้คืนยาก — แพลตฟอร์มนี้ออกแบบให้ชนะด้วยคุณภาพ+ความสม่ำเสมอที่ระบบอัตโนมัติทำได้เหนือกว่ามนุษย์' }
    ],

    /* ---- แหล่งอ้างอิง (หน้า 11) ---- */
    references: [
      'AirOps — Answer Engine Optimization (AEO): Complete Guide for 2026',
      'Frase — The 10 Best AI Visibility Tools in 2026',
      'Frase — Complete AEO Guide 2026',
      'Otterly.ai — AI Search Monitoring Tool'
    ]
  };

})(window.RP);
