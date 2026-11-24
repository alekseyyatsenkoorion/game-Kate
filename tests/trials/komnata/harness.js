// Стенд «Тёмной комнаты»: модуль испытания напрямую (реестр правит оркестратор), мок-ctx,
// настоящий Input из src/core/input.js. Параметры URL: ?task=0&power=3&noimg=1
// Всё, что делает испытание, пишется в window.__log.
const q = new URLSearchParams(location.search);
const log = (window.__log = []);

// ---- счётчики таймеров, rAF и слушателей ----
const orig = {
  setTimeout: window.setTimeout.bind(window), clearTimeout: window.clearTimeout.bind(window),
  setInterval: window.setInterval.bind(window), clearInterval: window.clearInterval.bind(window),
  raf: window.requestAnimationFrame.bind(window), caf: window.cancelAnimationFrame.bind(window),
  add: EventTarget.prototype.addEventListener, remove: EventTarget.prototype.removeEventListener
};
const active = { timeouts: new Set(), intervals: new Set(), rafs: new Set(), listeners: [] };
let track = false;
window.setTimeout = function (fn, ms, ...a) {
  if (!track) return orig.setTimeout(fn, ms, ...a);
  const id = orig.setTimeout(function () { active.timeouts.delete(id); if (typeof fn === 'function') fn(...a); }, ms);
  active.timeouts.add(id); return id;
};
window.clearTimeout = function (id) { active.timeouts.delete(id); orig.clearTimeout(id); };
window.setInterval = function (fn, ms, ...a) { const id = orig.setInterval(fn, ms, ...a); if (track) active.intervals.add(id); return id; };
window.clearInterval = function (id) { active.intervals.delete(id); orig.clearInterval(id); };
window.requestAnimationFrame = function (fn) {
  const id = orig.raf(function (t) { active.rafs.delete(id); fn(t); });
  active.rafs.add(id); return id;
};
window.cancelAnimationFrame = function (id) { active.rafs.delete(id); orig.caf(id); };
EventTarget.prototype.addEventListener = function (type, fn, opt) {
  if (track) active.listeners.push({ t: this, type, fn });
  return orig.add.call(this, type, fn, opt);
};
EventTarget.prototype.removeEventListener = function (type, fn, opt) {
  const i = active.listeners.findIndex((r) => r.t === this && r.type === type && r.fn === fn);
  if (i >= 0) active.listeners.splice(i, 1);
  return orig.remove.call(this, type, fn, opt);
};

function lcgRng(seed) {
  let s = seed >>> 0;
  const next = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
  return {
    next,
    int(min, max) { return min + Math.floor(next() * (max - min + 1)); },
    pick(a) { return a[Math.floor(next() * a.length)]; },
    shuffle(a) { const b = a.slice(); for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(next() * (i + 1)); const t = b[i]; b[i] = b[j]; b[j] = t; } return b; }
  };
}

async function main() {
  const taskIdx = +(q.get('task') || 0);
  let power = q.has('power') ? +q.get('power') : 3;
  const noImg = q.get('noimg') === '1';

  const link = document.createElement('link');
  link.rel = 'stylesheet'; link.href = '../../../src/trials/komnata/komnata.css';
  document.head.appendChild(link);
  await new Promise((r) => { link.onload = r; link.onerror = r; });

  const { Komnata } = await import('../../../src/trials/komnata/komnata.js');
  const { Input } = await import('../../../src/core/input.js');
  const data = await (await fetch('../../../data/trials/komnata.json')).json();
  const dict = await (await fetch('../fixtures/texts-komnata.json')).json();
  let task = data.tasks[taskIdx];
  if (q.get('bad') === '1') task = Object.assign({}, task, { payload: Object.assign({}, task.payload, { find: ['zzz'] }) });

  const text = (k, v) => {
    let s = dict[k] != null ? dict[k] : '[' + k + ']';
    if (v) Object.keys(v).forEach((n) => { s = s.split('{' + n + '}').join(String(v[n])); });
    return s;
  };
  const bar = document.getElementById('bar');
  const showPower = () => { bar.textContent = 'power: ' + power + ' · ' + task.id; };
  showPower();

  // AssetLoader-подобный мок: image(id) → { kind, url }
  const assets = {
    has: (id) => !noImg,
    url: (id) => '../../../assets/gpt/' + id + '.webp',
    image: (id) => noImg ? Promise.resolve({ kind: 'drawn', draw() {}, w: 256, h: 256 }) : new Promise((res) => {
      const img = new Image();
      img.onload = () => res({ kind: 'bitmap', img, url: img.src, w: img.naturalWidth, h: img.naturalHeight });
      img.onerror = () => res({ kind: 'drawn', draw() {}, w: 256, h: 256 });
      img.src = '../../../assets/gpt/' + id + '.webp';
    })
  };

  const ctx = {
    rng: lcgRng(12345 + taskIdx),
    audio: { sfx: (id) => log.push({ ev: 'sfx', id }), music() {}, say: () => Promise.resolve(), stopAll() {} },
    assets, text,
    item: (id) => ({ id, labelKey: 'item.' + id, art: 'item-' + id }),
    balance: { base: 100, hintCost: 15, mistakeCost: 20, par: 150000, timeBonus: 10, unsolvedFactor: 0.3, stars2: 50, stars3: 80, hintPrice: 1 },
    traps: 0,
    power: {
      get: () => power,
      spend: (n, reason) => {
        if (power < n) { log.push({ ev: 'spend', n, reason, ok: false }); return false; }
        power -= n; showPower(); log.push({ ev: 'spend', n, reason, ok: true }); return true;
      }
    },
    hint: (kind) => log.push({ ev: 'hint', kind }),
    react: (kind) => log.push({ ev: 'react', kind }),
    finish: (result) => log.push({ ev: 'finish', result }),
    fail: (err) => log.push({ ev: 'fail', err })
  };

  const field = document.getElementById('field');
  const stage = document.getElementById('stage');
  const input = new Input(stage);                       // до слежки: слушатели Input не считаются
  track = true;
  const inst = Komnata.create(ctx);
  await inst.start(field, task, +task.level);

  // ---- цикл кадров и счётчик FPS ----
  let last = performance.now(), alive = true, frames = 0, fpsT0 = 0, worst = 0;
  const loop = (t) => {
    if (!alive) return;
    const dt = Math.min(100, t - last); worst = Math.max(worst, t - last); last = t;
    frames++;
    inst.update(dt); inst.render();
    orig.raf(loop);
  };
  orig.raf(loop);

  input.onEvent((e) => {
    if (!alive) return;
    log.push({ ev: 'in', action: e.action });
    inst.onInput(Object.assign({}, e, { fx: e.x - 32, fy: e.y - 132 }));
  });

  window.__h = {
    inst, ctx, field, task,
    setPower(n) { power = n; showPower(); },
    getPower: () => power,
    destroy() { alive = false; inst.destroy(); },
    counters: () => ({ timeouts: active.timeouts.size, intervals: active.intervals.size, rafs: active.rafs.size, listeners: active.listeners.length }),
    tick(ms) { inst.update(ms); },
    // прямой вызов события ввода (координаты поля)
    send(action, fx, fy, target) { inst.onInput({ action, x: fx + 32, y: fy + 132, fx, fy, target: target || null, t: performance.now() }); inst.render(); },
    light: () => ({ x: inst.lx, y: inst.ly, R: inst.R }),
    fpsStart() { frames = 0; worst = 0; fpsT0 = performance.now(); },
    fpsStop() { const ms = performance.now() - fpsT0; return { fps: frames * 1000 / ms, frames, ms, worst }; }
  };
  window.__ready = true;
}

main().catch((e) => { console.error(e); window.__error = String(e && e.stack || e); });
