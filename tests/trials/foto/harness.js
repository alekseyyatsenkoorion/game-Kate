// Стенд «Фото-дела»: запускает испытание foto с мок-ctx на реальных данных.
// Параметры URL: ?task=0 (номер в data/trials/foto.json) &power=3 &nophoto=1 &bad=1
// Всё, что делает испытание, пишется в window.__log.
const q = new URLSearchParams(location.search);
const log = (window.__log = []);
const ROOT = '../../../';

// ---- счётчики таймеров, rAF и слушателей ----
const orig = {
  setTimeout: window.setTimeout.bind(window), clearTimeout: window.clearTimeout.bind(window),
  setInterval: window.setInterval.bind(window), clearInterval: window.clearInterval.bind(window),
  raf: window.requestAnimationFrame.bind(window), caf: window.cancelAnimationFrame.bind(window),
  add: EventTarget.prototype.addEventListener, remove: EventTarget.prototype.removeEventListener
};
const active = { timeouts: new Set(), intervals: new Set(), rafs: new Set(), listeners: [] };
window.setTimeout = function (fn, ms, ...a) {
  const id = orig.setTimeout(function () { active.timeouts.delete(id); if (typeof fn === 'function') fn(...a); }, ms);
  active.timeouts.add(id); return id;
};
window.clearTimeout = function (id) { active.timeouts.delete(id); orig.clearTimeout(id); };
window.setInterval = function (fn, ms, ...a) { const id = orig.setInterval(fn, ms, ...a); active.intervals.add(id); return id; };
window.clearInterval = function (id) { active.intervals.delete(id); orig.clearInterval(id); };
window.requestAnimationFrame = function (fn) {
  const id = orig.raf(function (t) { active.rafs.delete(id); fn(t); });
  active.rafs.add(id); return id;
};
window.cancelAnimationFrame = function (id) { active.rafs.delete(id); orig.caf(id); };
let trackListeners = false;
EventTarget.prototype.addEventListener = function (type, fn, opt) {
  if (trackListeners && String(new Error().stack || '').indexOf('/src/') >= 0) active.listeners.push({ t: this, type, fn });
  return orig.add.call(this, type, fn, opt);
};
EventTarget.prototype.removeEventListener = function (type, fn, opt) {
  const i = active.listeners.findIndex((r) => r.t === this && r.type === type && r.fn === fn);
  if (i >= 0) active.listeners.splice(i, 1);
  return orig.remove.call(this, type, fn, opt);
};
// Math.random под запретом в испытании — считаем вызовы
const origRandom = Math.random;
let randomCalls = 0;
Math.random = function () { randomCalls++; return origRandom(); };

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
  const seed = +(q.get('seed') || 12345);
  const data = await (await fetch(ROOT + 'data/trials/foto.json')).json();
  const dict = await (await fetch('../fixtures/texts-foto.json')).json();
  let gpt = [];
  try { gpt = (await (await fetch(ROOT + 'assets/gpt/index.json')).json()).images || []; } catch (e) { gpt = []; }
  const gptSet = new Set(q.get('nophoto') === '1' ? [] : gpt);
  let task = data.tasks[taskIdx];
  if (q.get('bad') === '1') task = Object.assign({}, task, { payload: Object.assign({}, task.payload, { pick: 99 }) });
  const level = task.level;

  const text = (k, v) => {
    let s = dict[k] != null ? dict[k] : '[' + k + ']';
    if (v) Object.keys(v).forEach((n) => { s = s.split('{' + n + '}').join(String(v[n])); });
    return s;
  };
  const bar = document.getElementById('bar');
  const showPower = () => { bar.textContent = 'power: ' + power + ' · ' + task.id; };
  showPower();

  const ctx = {
    rng: lcgRng(seed + taskIdx),
    audio: { sfx: (id) => log.push({ ev: 'sfx', id }), music() {}, say: () => Promise.resolve(), stopAll() {} },
    assets: {
      has: (id) => gptSet.has(id),
      url: (id) => gptSet.has(id) ? ROOT + 'assets/gpt/' + id + '.webp' : ROOT + 'assets/art/' + id + '.svg'
    },
    text,
    item: (id) => ({ id, labelKey: 'item.' + id, art: 'item-' + id }),
    balance: { base: 100, hintCost: 15, mistakeCost: 20, par: 600000, timeBonus: 10, unsolvedFactor: 0.3, stars2: 50, stars3: 80, hintPrice: 1 },
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

  const { Foto } = await import(ROOT + 'src/trials/foto/foto.js');
  const field = document.getElementById('field');
  trackListeners = true;
  const inst = Foto.create(ctx);
  await inst.start(field, task, level);

  let last = performance.now(), alive = true;
  const loop = (t) => {
    if (!alive) return;
    const dt = Math.min(100, t - last); last = t;
    inst.update(dt); inst.render();
    orig.raf(loop);
  };
  orig.raf(loop);

  // ---- касания как в Input: tap, hold (500 мс без сдвига), drag-end ----
  const stage = document.getElementById('stage');
  let down = null, holdT = 0;
  const toStage = (e) => { const r = stage.getBoundingClientRect(); return { x: (e.clientX - r.left) * 1024 / r.width, y: (e.clientY - r.top) * 768 / r.height }; };
  const emit = (action, e, target) => {
    if (!alive) return;
    const p = toStage(e);
    inst.onInput({ action, x: p.x, y: p.y, fx: p.x - 32, fy: p.y - 132, target, t: performance.now() });
  };
  orig.add.call(stage, 'pointerdown', (e) => {
    down = { x: e.clientX, y: e.clientY, clientX: e.clientX, clientY: e.clientY, target: e.target, held: false };
    const d = down;
    orig.clearTimeout(holdT);
    holdT = orig.setTimeout(() => { if (down === d) { d.held = true; emit('hold', d, d.target); } }, 500);
  });
  orig.add.call(window, 'pointerup', (e) => {
    if (!down) return;
    orig.clearTimeout(holdT);
    const dx = e.clientX - down.x, dy = e.clientY - down.y;
    if (dx * dx + dy * dy > 100) emit('drag-end', e, down.target);
    else if (!down.held) emit('tap', e, down.target);
    down = null;
  });

  window.__h = {
    inst, ctx, field, task,
    setPower(n) { power = n; showPower(); },
    getPower: () => power,
    destroy() { alive = false; inst.destroy(); },
    counters: () => ({ timeouts: active.timeouts.size, intervals: active.intervals.size, rafs: active.rafs.size, listeners: active.listeners.length }),
    randomCalls: () => randomCalls,
    // порядок утверждений на экране: [{i, true}] по data-st
    statements: () => inst.st.map((x, i) => ({ i, true: x.s.true, key: x.s.textKey }))
  };
  window.__ready = true;
}

main().catch((e) => { console.error(e); window.__error = String(e && e.stack || e); });
