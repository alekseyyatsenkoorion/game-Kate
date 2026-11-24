// Проверка зоны (spec.md §10, §11 п.3): менялись ли только файлы своей зоны.
//   npm run check-zone -- <A|B|C|D|O> [база]
//   npm run check-zone -- <зона> --files f1 f2 …   — проверить явный список файлов (свой отчёт агента)
// База — коммит или ветка, от которой считать изменения (по умолчанию HEAD).
// Изменённые = git diff --name-only <база> (коммиты после базы + индекс + рабочая папка) + неотслеживаемые файлы.
// Код выхода 1 — есть файлы чужой зоны или вне карты зон.
// Внимание: если несколько агентов работают в одной рабочей папке, их изменения видны все вместе —
// нарушения печатаются с зоной-владельцем, чтобы было видно, чьи это файлы.
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const CFG = JSON.parse(fs.readFileSync(path.join(__dirname, 'zones.json'), 'utf8'));
const argv = process.argv.slice(2).filter((a) => a !== '--');
const fi = argv.indexOf('--files');
const listed = fi >= 0 ? argv.slice(fi + 1) : null;
const args = fi >= 0 ? argv.slice(0, fi) : argv;
const zone = (args[0] || '').toUpperCase();
const base = listed ? 'список --files' : args[1] || 'HEAD';

if (!CFG.zones[zone]) {
  console.error('Укажи зону: npm run check-zone -- <' + Object.keys(CFG.zones).join('|') + '> [база]');
  process.exit(2);
}

function toRe(glob) {
  let re = '';
  for (let i = 0; i < glob.length; i++) {
    const c = glob[i];
    if (c === '*' && glob[i + 1] === '*') { re += glob[i + 2] === '/' ? '(?:.*/)?' : '.*'; i += glob[i + 2] === '/' ? 2 : 1; }
    else if (c === '*') re += '[^/]*';
    else if (c === '?') re += '[^/]';
    else re += c.replace(/[.+^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp('^' + re + '$');
}
const matcher = (globs) => { const rs = globs.map(toRe); return (f) => rs.some((r) => r.test(f)); };
const ignored = matcher(CFG.ignore || []);
const owners = Object.keys(CFG.zones).map((z) => [z, matcher(CFG.zones[z].files)]);
const owner = (f) => (owners.find(([, m]) => m(f)) || [null])[0];
const mine = matcher(CFG.zones[zone].files);

function git(a) {
  try { return execFileSync('git', a, { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }); }
  catch (e) { console.error('git ' + a.join(' ') + ': ' + (e.stderr || e.message).trim()); process.exit(2); }
}
// -z: имена с пробелами и кириллицей без кавычек и экранирования
const split = (s) => s.split('\0').filter(Boolean);
const changed = new Set(listed ? listed.map((f) => path.relative(ROOT, path.resolve(f)).split(path.sep).join('/')) : [
  ...split(git(['diff', '--name-only', '--no-renames', '-z', base])),
  ...split(git(['ls-files', '--others', '--exclude-standard', '-z']))
]);

const files = [...changed].filter((f) => !ignored(f)).sort();
const bad = files.filter((f) => !mine(f));
console.log('check-zone ' + zone + ' (' + CFG.zones[zone].name + '), база ' + base + ': изменено файлов ' + files.length + ', чужих ' + bad.length);
if (bad.length) {
  const by = {};
  bad.forEach((f) => { const o = owner(f) || 'вне карты зон'; (by[o] = by[o] || []).push(f); });
  Object.keys(by).sort().forEach((o) => {
    console.log('  ' + (CFG.zones[o] ? 'зона ' + o + ' (' + CFG.zones[o].name + ')' : o) + ':');
    by[o].forEach((f) => console.log('    ✗ ' + f));
  });
  process.exit(1);
}
console.log('  ✓ все изменения в своей зоне');
