// Стенд зоны B: запускает испытание с мок-ctx. Параметры URL:
// ?type=shirma|bagazhnik|misterx&task=0&power=3&traps=0&texts=1&level=1
// traps=0|1 — ловушка скептика; turn=1 — режим «Гость» (ctx.turn); с texts=1 подгружает тексты ловушек; seed=N — свой seed для ctx.rng
// Всё, что делает испытание, пишется в window.__log.

const q = new URLSearchParams(location.search);
const log = (window.__log = []);

// ---- счётчики таймеров, rAF и слушателей (до загрузки испытания) ----
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
  // считаем только слушатели, которые ставит код игры (src/): служебные слушатели Playwright не в счёт
  if (trackListeners && String(new Error().stack || '').indexOf('/src/') >= 0) active.listeners.push({ t: this, type, fn });
  return orig.add.call(this, type, fn, opt);
};
EventTarget.prototype.removeEventListener = function (type, fn, opt) {
  const i = active.listeners.findIndex((r) => r.t === this && r.type === type && r.fn === fn);
  if (i >= 0) active.listeners.splice(i, 1);
  return orig.remove.call(this, type, fn, opt);
};

// ---- простой LCG ----
function lcgRng(seed) {
  let s = seed >>> 0;
  const next = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
  return {
    next,
    int(min, max) { return min + Math.floor(next() * (max - min + 1)); },
    pick(a) { return a[Math.floor(next() * a.length)]; },
    shuffle(a) {
      const b = a.slice();
      for (let i = b.length - 1; i > 0; i--) { const j = Math.floor(next() * (i + 1)); const t = b[i]; b[i] = b[j]; b[j] = t; }
      return b;
    }
  };
}

async function main() {
  const type = q.get('type') || 'shirma';
  const taskIdx = +(q.get('task') || 0);
  let power = q.has('power') ? +q.get('power') : 3;
  const useTexts = q.get('texts') === '1';
  const level = +(q.get('level') || 1);

  // CSS испытания — как trial-host
  const link = document.createElement('link');
  link.rel = 'stylesheet'; link.href = '../../src/trials/' + type + '/' + type + '.css';
  document.head.appendChild(link);
  await new Promise((r) => { link.onload = r; link.onerror = r; });

  const { TRIALS } = await import('../../src/trials/index.js');
  const data = await (await fetch('fixtures/' + type + '.json')).json();
  let dict = useTexts ? (await (await fetch('fixtures/texts-sample.json')).json()).texts : null;
  // Мистер Икс: свои ключи mx.* (плоский файл) и тексты заданий-фикстур
  if (dict && type === 'misterx') {
    const ui = await (await fetch('fixtures/texts-misterx.json')).json();
    const tt = (await (await fetch('fixtures/texts-misterx-tasks.json')).json()).texts;
    dict = Object.assign({}, dict, ui, tt);
  }
  // Ловушки скептика: тексты шаблонов (fixtures/texts-traps.json) и существующие bag.clue.* из data/texts.json
  if (dict && q.get('traps') === '1') {
    const base = (await (await fetch('../../data/texts.json')).json()).texts;
    const tr = (await (await fetch('fixtures/texts-traps.json')).json()).texts;
    dict = Object.assign({}, base, dict, tr);
  }
  let task = data.tasks[taskIdx];
  // ?bad=1 — испорченное задание для проверки ctx.fail
  if (q.get('bad') === '1') task = Object.assign({}, task, { payload: Object.assign({}, task.payload, { answer: 'zzz', target: 'zzz', ask: 'zzz' }) });

  const text = (k, v) => {
    if (!dict) return k;
    let s = dict[k] != null ? dict[k] : '[' + k + ']';
    if (v) Object.keys(v).forEach((n) => { s = s.split('{' + n + '}').join(String(v[n])); });
    return s;
  };
  const bar = document.getElementById('bar');
  const showPower = () => { bar.textContent = 'power: ' + power; };
  showPower();

  const ctx = {
    rng: lcgRng(q.has('seed') ? +q.get('seed') : 12345 + taskIdx),
    audio: { sfx: (id) => log.push({ ev: 'sfx', id }), music() {}, say: () => Promise.resolve(), stopAll() {} },
    assets: { url: (art) => 'fixtures/art/' + art + '.svg' },
    text,
    item: (id) => ({ labelKey: 'item.' + id, art: 'item-' + id }),
    balance: { base: 100, hintCost: 15, mistakeCost: 20, par: 90000, timeBonus: 20, unsolvedFactor: 0.3, stars2: 50, stars3: 80 },
    traps: +(q.get('traps') || 0),
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

  // ?turn=1 — режим «Гость»: ходы по очереди, первый у игрока; смена хода пишется в лог
  if (q.get('turn') === '1') {
    ctx.turn = { who: 'player', next() { this.who = this.who === 'player' ? 'guest' : 'player'; log.push({ ev: 'turn', who: this.who }); } };
  }

  const field = document.getElementById('field');
  trackListeners = true;
  const inst = TRIALS[type].create(ctx);
  await inst.start(field, task, level);

  // ---- цикл кадров (своим, не считаемым rAF) ----
  let last = performance.now(), alive = true;
  const loop = (t) => {
    if (!alive) return;
    const dt = Math.min(100, t - last); last = t;
    inst.update(dt); inst.render();
    orig.raf(loop);
  };
  orig.raf(loop);

  // ---- касания: как Input (только tap по быстрому отпусканию без сдвига) ----
  const stage = document.getElementById('stage');
  let down = null;
  const toStage = (e) => { const r = stage.getBoundingClientRect(); return { x: (e.clientX - r.left) * 1024 / r.width, y: (e.clientY - r.top) * 768 / r.height }; };
  const emit = (action, e, target) => {
    const p = toStage(e);
    inst.onInput({ action, x: p.x, y: p.y, fx: p.x - 32, fy: p.y - 132, target, t: performance.now() });
  };
  orig.add.call(stage, 'pointerdown', (e) => { down = { x: e.clientX, y: e.clientY, target: e.target }; });
  orig.add.call(window, 'pointerup', (e) => {
    if (!down) return;
    const dx = e.clientX - down.x, dy = e.clientY - down.y;
    emit(dx * dx + dy * dy > 100 ? 'drag-end' : 'tap', e, down.target);
    down = null;
  });

  window.__h = {
    inst, ctx, field, task, TRIALS,
    setPower(n) { power = n; showPower(); },
    getPower: () => power,
    destroy() { alive = false; inst.destroy(); },
    counters: () => ({ timeouts: active.timeouts.size, intervals: active.intervals.size, rafs: active.rafs.size, listeners: active.listeners.length }),
    listenerInfo: () => active.listeners.map((r) => r.type + '@' + ((r.t && r.t.constructor && r.t.constructor.name) || '?')),
    tick(ms) { inst.update(ms); }
  };
  window.__ready = true;
}

main().catch((e) => { console.error(e); window.__error = String(e && e.stack || e); });
