// Собирает precache.json и проставляет версию в sw.js. Запуск: node tools/build-precache.js [версия]
// Заодно проверяет бюджет веса (≤ 15 МБ).
const fs = require('fs');
const path = require('path');
const ROOT = path.join(__dirname, '..');
const SKIP_DIR = new Set(['.git', 'tests', 'tools', 'legacy', 'node_modules', 'schemas']);
const SKIP_FILE = new Set(['sw.js', 'precache.json', 'package.json', 'package-lock.json', 'playwright.config.js']);
const LIMIT = 15 * 1024 * 1024;

const files = []; let bytes = 0;
(function walk(dir) {
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name), rel = path.relative(ROOT, full).split(path.sep).join('/');
    const st = fs.statSync(full);
    if (st.isDirectory()) { if (!SKIP_DIR.has(name)) walk(full); continue; }
    if (SKIP_FILE.has(rel) || name.endsWith('.md') || name.startsWith('.')) continue;
    if (rel.startsWith('assets/gpt/') && !(name.endsWith('.webp') || name === 'index.json')) continue;
    files.push(rel); bytes += st.size;
  }
})(ROOT);
files.sort();

const swPath = path.join(ROOT, 'sw.js');
let sw = fs.readFileSync(swPath, 'utf8');
const CHECK = process.argv.includes('--check');
let version = process.argv.filter((a) => !a.startsWith('--'))[2];
if (!version) {
  const m = sw.match(/const VERSION = '(\d+)\.(\d+)\.(\d+)'/);
  version = m ? m[1] + '.' + m[2] + '.' + (+m[3] + 1) : '0.1.0';
}
sw = sw.replace(/const VERSION = '[^']*'/, "const VERSION = '" + version + "'");
if (!CHECK) fs.writeFileSync(swPath, sw);
if (!CHECK) fs.writeFileSync(path.join(ROOT, 'precache.json'), JSON.stringify({ version, files: ['./'].concat(files) }, null, 1));
console.log('version', version, 'files', files.length, 'size', (bytes / 1024 / 1024).toFixed(2) + ' MB');
if (bytes > LIMIT) { console.error('Превышен бюджет веса 15 МБ'); process.exit(1); }
