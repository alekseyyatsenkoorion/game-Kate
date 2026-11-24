// Испытание «Багажник» (bagazhnik): найти машину, в багажнике которой человек.
// Контракт — contracts.md §11, формат задания — §12.2.
// Главная механика — внимательность: улики sag/fog/track видны на машинах бесплатно.
// Осмотр машины (тексты улик) стоит силы. Таймеры и анимации — только на update(dt).

// Кузова: вид сбоку, корма слева, перед справа. viewBox 0 0 260 130, земля y=120.
// back — заднее стекло (может запотеть), lid — крышка багажника / задняя дверь,
// hinge — ось крышки, open — угол открытия, hole — проём, head — где покажется человек.
const BODIES = {
  sedan: {
    body: 'M26,74 Q26,64 36,63 L92,60 L114,36 Q118,33 124,33 L172,33 Q178,33 182,37 L206,60 L240,64 Q252,66 252,78 L252,96 Q252,104 244,104 L32,104 Q26,104 26,98 Z',
    back: 'M97,59 L116,38 L138,38 L138,59 Z',
    glass: ['M143,38 L170,38 Q174,38 177,41 L198,59 L143,59 Z'],
    lid: 'M26,74 Q26,64 36,63 L92,60 L93,67 L27,77 Z',
    hinge: [92, 60], open: 62,
    hole: 'M29,73 L36,65 L91,61 L91,69 Z',
    head: [58, 52], rear: 26,
    tail: [26, 78, 6, 9], tailOnLid: false, lamp: [246, 70, 6, 7],
    seams: 'M140,62 L140,100 M93,67 L93,100'
  },
  hatch: {
    body: 'M36,98 L36,64 Q36,54 42,50 L62,35 Q66,32 72,32 L162,32 Q168,32 172,36 L200,60 L236,64 Q250,66 250,78 L250,96 Q250,104 242,104 L42,104 Q36,104 36,98 Z',
    back: 'M49,59 L66,38 L98,38 L98,59 Z',
    glass: ['M104,38 L160,38 Q164,38 167,41 L192,59 L104,59 Z'],
    lid: 'M36,98 L36,64 Q36,54 42,50 L62,35 L69,35 L46,62 L46,92 Z',
    hinge: [66, 34], open: 72,
    hole: 'M38,96 L38,64 Q38,56 44,51 L62,37 L80,37 L80,96 Z',
    head: [57, 66], rear: 36,
    tail: [36, 66, 5, 11], tailOnLid: true, lamp: [244, 70, 6, 7],
    seams: 'M101,62 L101,100'
  },
  suv: {
    body: 'M28,98 L28,58 Q28,48 34,44 L48,24 Q52,18 60,18 L172,18 Q179,18 183,23 L206,52 L238,56 Q250,58 250,72 L250,96 Q250,104 242,104 L34,104 Q28,104 28,98 Z',
    back: 'M42,50 L54,26 L90,26 L90,50 Z',
    glass: ['M96,26 L132,26 L132,50 L96,50 Z', 'M138,26 L172,26 Q176,26 179,30 L197,50 L138,50 Z'],
    lid: 'M28,98 L28,58 Q28,48 34,44 L48,24 L55,24 L39,52 L39,96 Z',
    hinge: [52, 22], open: 74,
    hole: 'M30,96 L30,58 Q30,50 36,46 L50,26 L74,26 L74,96 Z',
    head: [52, 62], rear: 28,
    tail: [28, 58, 5, 13], tailOnLid: true, lamp: [244, 62, 6, 8],
    seams: 'M93,54 L93,100 M135,54 L135,100'
  },
  van: {
    body: 'M22,98 L22,26 Q22,16 32,16 L184,16 Q192,16 196,24 L214,56 L240,60 Q252,62 252,76 L252,96 Q252,104 244,104 L28,104 Q22,104 22,98 Z',
    back: 'M28,24 L45,24 L45,52 L28,52 Z', backOnLid: true,
    glass: ['M56,24 L110,24 L110,52 L56,52 Z', 'M118,24 L150,24 L150,52 L118,52 Z', 'M160,24 L186,24 Q190,24 192,28 L206,54 L160,54 Z'],
    lid: 'M22,98 L22,26 Q22,16 32,16 L50,16 L50,98 Z',
    hinge: [50, 16], open: 62,
    hole: 'M24,98 L24,26 Q24,18 32,18 L50,18 L50,98 Z',
    head: [37, 62], rear: 22,
    tail: [22, 72, 5, 13], tailOnLid: true, lamp: [245, 68, 6, 8],
    seams: 'M153,56 L153,100 M53,20 L53,100'
  }
};
const WHEELS = [72, 200];
// Ловушка скептика (ctx.traps = 1): виды ложной улики — только видимые, рисуются как настоящие.
// Текст при осмотре — существующий ключ bag.clue.<kind>.
const TRAP_KINDS = ['sag', 'fog', 'track'];

// Иконки видов улик (24×24, обводка)
const ICONS = {
  sag: '<path d="M12 3v11"/><path d="M7 9l5 5 5-5"/><path d="M4 20h16"/>',
  fog: '<path d="M8 4c-2 3-3 4.5-3 6a3 3 0 0 0 6 0c0-1.5-1-3-3-6z"/><path d="M16 10c-2 3-3 4.5-3 6a3 3 0 0 0 6 0c0-1.5-1-3-3-6z"/>',
  track: '<ellipse cx="8" cy="15" rx="3" ry="5"/><ellipse cx="16" cy="8" rx="3" ry="5"/>',
  sound: '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16 9c1.6 1.8 1.6 4.2 0 6"/><path d="M18.5 6.5c3 3 3 8 0 11"/>',
  smell: '<path d="M7 21c-2-3 2-5 0-8s2-5 0-8"/><path d="M12 21c-2-3 2-5 0-8s2-5 0-8"/><path d="M17 21c-2-3 2-5 0-8s2-5 0-8"/>'
};
const POWER_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3.2"/></svg>';
const EYE_BADGE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';

let uid = 0;

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function safeColor(c) {
  return typeof c === 'string' && /^#[0-9a-fA-F]{3,8}$/.test(c) ? c : '#6b5b8c';
}

function easeOut(p) { return 1 - (1 - p) * (1 - p) * (1 - p); }
function easeBack(p) { const s = 1.4; p -= 1; return p * p * ((s + 1) * p + s) + 1; }

function validate(p) {
  if (!p || typeof p !== 'object') return 'payload';
  if (!Array.isArray(p.cars) || p.cars.length < 2) return 'cars';
  const ids = {};
  for (const c of p.cars) {
    if (!c || typeof c.id !== 'string' || ids[c.id]) return 'cars.id';
    ids[c.id] = true;
    if (!BODIES[c.body]) return 'cars.body';
    if (c.clues != null && !Array.isArray(c.clues)) return 'cars.clues';
    if ((c.clues || []).some((k) => !k || typeof k.textKey !== 'string' || typeof k.kind !== 'string')) return 'cars.clues';
  }
  if (!ids[p.target]) return 'target';
  return null;
}

// SVG одной машины. Видимые улики: sag (корма ниже), fog (запотевшее заднее стекло), track (следы у багажника)
function carSvg(car, w, gid) {
  const b = BODIES[car.body];
  const color = safeColor(car.color);
  const kinds = {};
  (car.clues || []).forEach((k) => { kinds[k.kind] = true; });
  const shade = 'url(#bz-shade-' + gid + ')';
  const glassFill = 'url(#bz-glass-' + gid + ')';
  const back = kinds.fog
    ? '<path d="' + b.back + '" fill="#d6dde8" fill-opacity=".72"/>' +
      '<path d="' + b.back + '" fill="none" stroke="#fff" stroke-opacity=".35" stroke-width="1"/>'
    : '<path d="' + b.back + '" fill="' + glassFill + '"/>';
  const tail = '<rect x="' + b.tail[0] + '" y="' + b.tail[1] + '" width="' + b.tail[2] + '" height="' + b.tail[3] + '" rx="1.5" fill="#d23b2f"/>';
  let s = '<svg class="bz-car" viewBox="0 0 260 130" width="' + w + '" height="' + Math.round(w / 2) + '" overflow="visible" aria-hidden="true">';
  // следы у багажника
  if (kinds.track) {
    const r = b.rear;
    [[r - 9, 119], [r - 19, 123], [r - 6, 126], [r - 16, 129]].forEach((t, i) => {
      s += '<ellipse cx="' + t[0] + '" cy="' + t[1] + '" rx="6" ry="2.4" fill="#b59a74" fill-opacity=".55" transform="rotate(' + (i % 2 ? -8 : 8) + ' ' + t[0] + ' ' + t[1] + ')"/>';
    });
  }
  s += '<ellipse cx="' + (b.rear + 114) + '" cy="121" rx="' + (124 - b.rear / 2) + '" ry="5" fill="#000" fill-opacity=".55"/>';
  // кузов; при sag повернут на 2° вокруг передней оси — корма ниже на 4–5 px
  s += '<g class="bz-body"' + (kinds.sag ? ' transform="rotate(-2 ' + WHEELS[1] + ' 103)"' : '') + '>';
  s += '<path d="' + b.body + '" fill="' + color + '"/><path d="' + b.body + '" fill="' + shade + '"/>';
  s += '<path d="' + b.seams + '" fill="none" stroke="#000" stroke-opacity=".35" stroke-width="1.4"/>';
  b.glass.forEach((g) => { s += '<path d="' + g + '" fill="' + glassFill + '"/>'; });
  if (!b.backOnLid) s += back;
  if (!b.tailOnLid) s += tail;
  s += '<rect x="' + b.lamp[0] + '" y="' + b.lamp[1] + '" width="' + b.lamp[2] + '" height="' + b.lamp[3] + '" rx="1.5" fill="#f6e6a6"/>';
  WHEELS.forEach((x) => { s += '<path d="M' + (x - 21) + ',104 A21,21 0 0 1 ' + (x + 21) + ',104 Z" fill="#07060b"/>'; });
  // проём и человек (видны после открытия)
  s += '<path class="bz-hole" d="' + b.hole + '" fill="#050308" opacity="0"/>';
  const hx = b.head[0], hy = b.head[1];
  s += '<g class="bz-man" opacity="0" transform="translate(0 14)">' +
    '<ellipse cx="' + hx + '" cy="' + (hy + 4) + '" rx="22" ry="18" fill="#f1c86b" fill-opacity=".35"/>' +
    '<circle cx="' + hx + '" cy="' + hy + '" r="12" fill="#e3b58e"/>' +
    '<path d="M' + (hx - 12) + ',' + (hy - 1) + ' Q' + hx + ',' + (hy - 19) + ' ' + (hx + 12) + ',' + (hy - 1) + ' Q' + hx + ',' + (hy - 8) + ' ' + (hx - 12) + ',' + (hy - 1) + ' Z" fill="#3b2516"/>' +
    '<circle cx="' + (hx - 4) + '" cy="' + (hy + 1) + '" r="1.8" fill="#1a1020"/><circle cx="' + (hx + 4) + '" cy="' + (hy + 1) + '" r="1.8" fill="#1a1020"/>' +
    '<path d="M' + (hx - 4) + ',' + (hy + 6) + ' Q' + hx + ',' + (hy + 9.5) + ' ' + (hx + 4) + ',' + (hy + 6) + '" fill="none" stroke="#7a3b2a" stroke-width="1.5"/>' +
    '<circle cx="' + (hx + 18) + '" cy="' + (hy - 2) + '" r="5" fill="#e3b58e"/>' +
    '</g>';
  s += '<g class="bz-lid" transform="rotate(0 ' + b.hinge[0] + ' ' + b.hinge[1] + ')">' +
    '<path d="' + b.lid + '" fill="' + color + '"/><path d="' + b.lid + '" fill="' + shade + '"/>' +
    '<path d="' + b.lid + '" fill="none" stroke="#000" stroke-opacity=".3" stroke-width="1"/>' +
    (b.backOnLid ? back : '') + (b.tailOnLid ? tail : '') + '</g>';
  s += '</g>';
  // колёса стоят на месте
  WHEELS.forEach((x) => {
    s += '<circle cx="' + x + '" cy="103" r="17" fill="#121016"/><circle cx="' + x + '" cy="103" r="9" fill="#7d7a8a"/><circle cx="' + x + '" cy="103" r="3" fill="#2a2833"/>';
  });
  return s + '</svg>';
}

class BagazhnikTrial {
  constructor(ctx) {
    this.ctx = ctx;
    this.root = null;
    this.timers = [];          // [{left, fn, tag}] — тикают в update(dt)
    this.tweens = [];          // [{t, delay, dur, fn}] — анимации SVG, тоже в update(dt)
    this.dead = false;
    this.paused = false;
    this.done = false;
    this.finished = false;
    this.sel = null;
    this.inspected = {};
    this.checked = {};
    this.mistakes = 0;
    this.hintsUsed = 0;
    this.powerSpent = 0;
    this.t0 = 0;
    this.timeMs = null;
    this.pausedTotal = 0;
    this.pausedAt = 0;
    this.gid = ++uid;
  }

  // ---------- жизненный цикл ----------
  async start(field, task, level) {
    this.field = field;
    this.task = task || {};
    this.level = level;
    const p = this.task.payload;
    const bad = validate(p);
    if (bad) {
      this.ctx.fail({ code: 'TASK_INVALID', module: 'bagazhnik', message: 'payload.' + bad, details: { taskId: this.task.id } });
      return;
    }
    this.p = p;
    // Свои копии машин: задание из пула не меняем (ловушка добавляет улику)
    const cars = p.cars.map((c) => Object.assign({}, c, { clues: (c.clues || []).slice() }));
    this.cars = {};
    cars.forEach((c) => { this.cars[c.id] = c; });
    // Порядок мест — первым вызовом ctx.rng, как и раньше: при traps = 0 раскладка прежняя
    this.order = this.ctx.rng.shuffle(cars.slice());
    this.trap = null;
    if (this.ctx.traps === 1) this._plantTrap(cars);
    this.price = (this.ctx.balance && this.ctx.balance.hintPrice) || 1;
    this._build();
    this._showPick();
    this.t0 = performance.now();
  }

  update(dt) {
    if (this.dead || this.paused) return;
    if (this.tweens.length) {
      this.tweens = this.tweens.filter((tw) => {
        tw.t += dt;
        const p = Math.max(0, Math.min(1, (tw.t - tw.delay) / tw.dur));
        if (tw.t >= tw.delay) tw.fn(p);
        return p < 1;
      });
    }
    if (this.timers.length) {
      const due = [];
      this.timers = this.timers.filter((t) => { t.left -= dt; if (t.left <= 0) { due.push(t.fn); return false; } return true; });
      due.forEach((fn) => { if (!this.dead) fn(); });
    }
  }

  render() {}

  onInput(e) {
    if (this.dead || this.paused || this.done || !this.root) return;
    if (!e || e.action !== 'tap' || !e.target || !e.target.closest) return;
    if (!this.root.contains(e.target)) return;
    const btn = e.target.closest('[data-bz]');
    if (btn) {
      const a = btn.getAttribute('data-bz');
      if (a === 'inspect') this._inspect();
      else if (a === 'choose') this._choose();
      return;
    }
    const spot = e.target.closest('[data-car]');
    if (spot) this._select(spot.getAttribute('data-car'));
  }

  pause() {
    if (this.paused || this.dead) return;
    this.paused = true;
    this.pausedAt = performance.now();
    if (this.root) this.root.classList.add('is-paused');
  }

  resume() {
    if (!this.paused || this.dead) return;
    this.paused = false;
    this.pausedTotal += performance.now() - this.pausedAt;
    if (this.root) this.root.classList.remove('is-paused');
  }

  destroy() {
    if (this.dead) return;
    this.dead = true;
    this.timers = [];
    this.tweens = [];
    if (this.root && this.root.parentNode) this.root.parentNode.removeChild(this.root);
    this.root = null;
    this.field = null;
    this.spots = null;
  }

  // ---------- построение ----------
  _build() {
    const t = (k, v) => this.ctx.text(k, v);
    const root = el('div', 'bz-root');
    this.root = root;
    const g = this.gid;
    root.innerHTML =
      '<svg class="bz-defs" width="0" height="0" aria-hidden="true"><defs>' +
      '<linearGradient id="bz-shade-' + g + '" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0" stop-color="#fff" stop-opacity=".24"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/>' +
        '<stop offset="1" stop-color="#000" stop-opacity=".5"/></linearGradient>' +
      '<linearGradient id="bz-glass-' + g + '" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0" stop-color="#34445e"/><stop offset=".55" stop-color="#151c2a"/><stop offset="1" stop-color="#0b0f18"/></linearGradient>' +
      '</defs></svg>' +
      '<div class="bz-lamp bz-lamp-a"></div><div class="bz-lamp bz-lamp-b"></div>';
    const ask = el('div', 'bz-ask', t('bag.ask'));
    root.appendChild(ask);

    // Места: 2 ряда до 10 машин, 3 ряда — больше. Порядок перемешан в start.
    const order = this.order;
    const n = order.length;
    const rows = n <= 10 ? 2 : 3;
    const cols = Math.ceil(n / rows);
    const top = 50, bottom = 466;
    const spotW = 940 / cols, spotH = (bottom - top) / rows;
    const carW = Math.floor(Math.min(260, spotW - 12, (spotH - 22) * 2));
    for (let r = 0; r < rows; r++) {
      const ground = el('div', 'bz-ground');
      ground.style.top = Math.round(top + (r + 1) * spotH - 34) + 'px';
      root.appendChild(ground);
    }
    this.spots = {};
    order.forEach((car, i) => {
      const r = Math.floor(i / cols), c = i % cols;
      const inRow = Math.min(cols, n - r * cols);
      const left = 10 + (cols - inRow) * spotW / 2 + c * spotW;
      const spot = el('div', 'bz-spot');
      spot.setAttribute('data-car', car.id);
      spot.style.left = Math.round(left) + 'px';
      spot.style.top = Math.round(top + r * spotH) + 'px';
      spot.style.width = Math.round(spotW) + 'px';
      spot.style.height = Math.round(spotH) + 'px';
      spot.innerHTML = '<div class="bz-bay"></div><div class="bz-sel"></div>' +
        '<div class="bz-carwrap" style="width:' + carW + 'px;margin-left:' + (-carW / 2) + 'px">' + carSvg(car, carW, g) + '</div>' +
        '<div class="bz-badge">' + EYE_BADGE + '</div><div class="bz-cross"></div>';
      root.appendChild(spot);
      this.spots[car.id] = spot;
    });

    // Панель: мини-машина, текст, кнопки
    const panel = el('div', 'bz-panel');
    this.mini = el('div', 'bz-mini');
    this.info = el('div', 'bz-info');
    const btns = el('div', 'bz-btns');
    this.btnInspect = el('div', 'bz-btn bz-btn-inspect');
    this.btnInspect.setAttribute('data-bz', 'inspect');
    this.btnInspect.setAttribute('role', 'button');
    this.btnInspect.appendChild(el('span', null, t('bag.inspect')));
    const price = el('span', 'bz-price');
    price.innerHTML = POWER_ICON;
    price.appendChild(el('b', null, '−' + this.price));
    this.btnInspect.appendChild(price);
    this.btnChoose = el('div', 'bz-btn bz-btn-choose', t('bag.choose'));
    this.btnChoose.setAttribute('data-bz', 'choose');
    this.btnChoose.setAttribute('role', 'button');
    btns.appendChild(this.btnInspect);
    btns.appendChild(this.btnChoose);
    panel.appendChild(this.mini);
    panel.appendChild(this.info);
    panel.appendChild(btns);
    this.panel = panel;
    root.appendChild(panel);

    this.field.appendChild(root);
  }

  // ---------- ловушка скептика ----------
  // Одной машине-обманке без улик — одна ложная видимая улика. Внешне не отличается от настоящей.
  _plantTrap(cars) {
    const rng = this.ctx.rng;
    const free = cars.filter((c) => c.id !== this.p.target && !c.clues.length);
    if (!free.length) return;
    const car = rng.pick(free);
    const kind = rng.pick(TRAP_KINDS);
    car.clues.push({ kind: kind, textKey: 'bag.clue.' + kind, fake: true });
    this.trap = { car: car.id, kind: kind };
  }

  // ---------- панель ----------
  _syncPanel() {
    const has = !!this.sel && !this.done;
    this.panel.classList.toggle('has-car', has);
    this.btnInspect.classList.toggle('is-done', has && !!this.inspected[this.sel]);
    this.mini.innerHTML = has ? carSvg(this.cars[this.sel], 112, this.gid) : '';
  }

  _showPick() {
    this.info.className = 'bz-info is-pick';
    this.info.textContent = this.ctx.text('bag.pickCar');
  }

  _showClues(id) {
    const car = this.cars[id];
    const clues = car.clues || [];
    this.info.className = 'bz-info';
    this.info.textContent = '';
    if (!clues.length) { this.info.appendChild(el('div', 'bz-clue is-none', this.ctx.text('bag.nothing'))); return; }
    clues.forEach((k) => {
      const row = el('div', 'bz-clue');
      const ic = el('span', 'bz-clue-ic');
      ic.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[k.kind] || ICONS.smell) + '</svg>';
      row.appendChild(ic);
      row.appendChild(el('span', null, this.ctx.text(k.textKey)));
      this.info.appendChild(row);
    });
  }

  _showView() {
    if (this.sel && this.inspected[this.sel]) this._showClues(this.sel);
    else if (this.sel) { this.info.className = 'bz-info'; this.info.textContent = ''; }
    else this._showPick();
  }

  // Сообщение на 2 с, потом — обычный вид панели
  _flash(key, cls) {
    this.info.className = 'bz-info is-msg ' + (cls || '');
    this.info.textContent = this.ctx.text(key);
    this.timers = this.timers.filter((t) => t.tag !== 'msg');
    this.timers.push({ left: 2000, tag: 'msg', fn: () => { if (!this.done) this._showView(); } });
  }

  // ---------- действия ----------
  _select(id) {
    if (!this.cars[id] || this.checked[id]) return;
    if (this.sel === id) return;
    if (this.sel && this.spots[this.sel]) this.spots[this.sel].classList.remove('is-sel');
    this.sel = id;
    this.spots[id].classList.add('is-sel');
    this.ctx.audio.sfx('tap');
    this.timers = this.timers.filter((t) => t.tag !== 'msg');
    this._syncPanel();
    this._showView();
  }

  _inspect() {
    const id = this.sel;
    if (!id) return;
    if (this.inspected[id]) { this._showClues(id); return; }     // повторный осмотр бесплатен
    if (!this.ctx.power.spend(this.price, 'bag.inspect')) {
      this._flash('bag.noPower', 'is-bad');
      this._shake(this.btnInspect);
      return;
    }
    this.powerSpent += this.price;
    this.hintsUsed++;
    this.ctx.hint('inspect');
    this.inspected[id] = true;
    this.spots[id].classList.add('is-inspected');
    const car = this.cars[id];
    if (id === this.p.target && (car.clues || []).some((k) => k.kind === 'sound')) this.ctx.audio.sfx('knock');
    this.timers = this.timers.filter((t) => t.tag !== 'msg');
    this._syncPanel();
    this._showClues(id);
  }

  _choose() {
    const id = this.sel;
    if (!id) return;
    const spot = this.spots[id];
    this.ctx.audio.sfx('trunk');
    this._openTrunk(spot, id);
    if (id === this.p.target) {
      this.done = true;
      this.timeMs = this._activeMs();             // время — до верного ответа, без анимации
      spot.classList.add('is-found');
      this._syncPanel();
      this.timers = this.timers.filter((t) => t.tag !== 'msg');
      this.info.className = 'bz-info is-msg is-good';
      this.info.textContent = this.ctx.text('bag.found');
      this.ctx.react('correct');
      this.timers.push({ left: 1600, fn: () => this._finish(true) });
      return;
    }
    this.mistakes++;
    this.checked[id] = true;
    spot.classList.remove('is-sel');
    spot.classList.add('is-checked');
    this.sel = null;
    this._syncPanel();
    this._flash('bag.empty', 'is-bad');
    this.timers.push({ left: 260, fn: () => this.ctx.audio.sfx('wrong') });
    this.ctx.react('mistake');
  }

  _openTrunk(spot, id) {
    const b = BODIES[this.cars[id].body];
    const lid = spot.querySelector('.bz-carwrap .bz-lid');
    const hole = spot.querySelector('.bz-carwrap .bz-hole');
    const hx = b.hinge[0], hy = b.hinge[1];
    this.tweens.push({ t: 0, delay: 0, dur: 520, fn: (p) => {
      lid.setAttribute('transform', 'rotate(' + (b.open * easeBack(p)).toFixed(2) + ' ' + hx + ' ' + hy + ')');
      hole.setAttribute('opacity', Math.min(1, p * 3).toFixed(2));
    } });
    if (id === this.p.target) {
      const man = spot.querySelector('.bz-carwrap .bz-man');
      this.tweens.push({ t: 0, delay: 380, dur: 420, fn: (p) => {
        const q = easeOut(p);
        man.setAttribute('opacity', q.toFixed(2));
        man.setAttribute('transform', 'translate(0 ' + (14 * (1 - q)).toFixed(2) + ')');
      } });
    }
  }

  _shake(node) {
    node.classList.remove('is-shake');
    void node.offsetWidth;
    node.classList.add('is-shake');
  }

  _activeMs() {
    let ms = performance.now() - this.t0 - this.pausedTotal;
    if (this.paused) ms -= performance.now() - this.pausedAt;
    return Math.max(0, Math.round(ms));
  }

  _finish(solved) {
    if (this.finished || this.dead) return;
    this.finished = true;
    this.ctx.finish({
      type: 'bagazhnik',
      taskId: this.task.id,
      level: this.level,
      solved: solved,
      accuracy: Math.max(0, 1 - 0.25 * this.mistakes),
      hintsUsed: this.hintsUsed,
      powerSpent: this.powerSpent,
      mistakes: this.mistakes,
      timeMs: this.timeMs != null ? this.timeMs : this._activeMs(),
      caseClues: []
    });
  }
}

export const Bagazhnik = {
  type: 'bagazhnik',
  schemaVersion: 1,
  create(ctx) { return new BagazhnikTrial(ctx); }
};
