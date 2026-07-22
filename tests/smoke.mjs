/* Smoke test (CI): โหลดทุก script ใน jsdom แล้วเรนเดอร์ทุก view — ต้องไม่มี error */
import { JSDOM } from 'jsdom';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const dom = new JSDOM(html, { runScripts: 'outside-only', url: 'http://localhost/', pretendToBeVisual: true });
const { window } = dom;
const document = window.document;
if (!window.requestAnimationFrame) window.requestAnimationFrame = (cb) => setTimeout(() => cb(0), 0);

const files = [
  'assets/js/helpers.js', 'assets/js/data.js', 'assets/js/api.js', 'assets/js/onboard.js',
  'assets/js/realstate.js',
  'assets/js/views/activity.js',
  'assets/js/views/dashboard.js', 'assets/js/views/m1.js', 'assets/js/views/m2.js',
  'assets/js/views/m3.js', 'assets/js/views/m4.js', 'assets/js/views/m5.js',
  'assets/js/views/m6.js', 'assets/js/views/report.js',
  'assets/js/views/projects.js', 'assets/js/views/settings.js', 'assets/js/views/billing.js',
  'assets/js/app.js',
];

let fail = 0;
for (const f of files) {
  try { window.eval(fs.readFileSync(path.join(ROOT, f), 'utf8')); }
  catch (e) { console.error('LOAD FAIL', f, e.message); fail++; }
}

const RP = window.RP;
if (!RP || !RP.views) { console.error('RP namespace missing'); process.exit(1); }
const views = ['dashboard', 'activity', 'm1', 'm2', 'm3', 'm4', 'm5', 'm6', 'report', 'projects', 'settings', 'billing'];
for (const v of views) {
  try {
    const o = RP.views[v]();
    if (!o || typeof o.html !== 'string' || o.html.length < 200) { console.error('view too small:', v); fail++; continue; }
    const d = document.createElement('div');
    d.innerHTML = o.html;
    if (typeof o.mount === 'function') o.mount(d);
    if (o.html.indexOf('undefined') !== -1) { console.error('"undefined" leaked in', v); fail++; }
    if (/\[object Object\]/.test(o.html)) { console.error('[object Object] in', v); fail++; }
  } catch (e) { console.error('VIEW FAIL', v, e.message); fail++; }
}
// auth + api client present
if (!RP.api || typeof RP.api.signin !== 'function') { console.error('RP.api auth missing'); fail++; }
if (!RP.auth || typeof RP.auth.user !== 'function') { console.error('RP.auth missing'); fail++; }

console.log(fail ? ('SMOKE FAILED: ' + fail + ' problem(s)') : ('SMOKE OK — ' + views.length + ' views rendered, 0 errors'));
process.exit(fail ? 1 : 0);
