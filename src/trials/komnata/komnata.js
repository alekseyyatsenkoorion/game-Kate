// Испытание «Тёмная комната» (komnata): найти предметы в тёмной комнате фонарём.
// Контракт — contracts.md §11, формат задания — §12.2 (v2.3).
// Производительность (iPad Air 2): тьма — один слой с radial-gradient, нарисованный один раз;
// за фонарём двигается только transform (композитор, без перерисовки). Без filter/blur/теней.
// Тык по предмету засчитывается, только если точка в луче. Тык в темноте лишь переносит фонарь.
// Таймеры — только свои, на update(dt).

const ROOM_W = 800;            // картинка 4:3 вписана в поле 960×600 слева целиком, без обрезки
const ROOM_H = 600;
// справа от комнаты (x 808..960) — список «Найдите» и подсказка; размеры в komnata.css
const HOLE_W = ROOM_W * 2 + 40; // слой тьмы с дыркой: покрывает комнату при любом положении фонаря
const HOLE_H = ROOM_H * 2 + 40;
const HIT_SCALE = 1.2;         // запас попадания: r × 1.2 + 8 px
const HIT_PAD = 8;
const LIGHT_PAD = 6;           // запас края луча для тыка
const SOFT = 0.45;             // мягкий край луча — доля радиуса
const GLOW_MS = 2000;
const FLASH_MS = 800;
const MSG_MS = 2000;
const FINISH_MS = 2200;

const POWER_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3.2"/></svg>';
// Палитра векторной заглушки комнаты (если картинки нет)
const STUB_COLORS = ['#c58b3c', '#8c4a2f', '#5b7a8c', '#a3a35b', '#7a5b8c', '#b8664a', '#5b8c6a', '#c2b280'];

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function num01(v) { return typeof v === 'number' && isFinite(v) && v >= 0 && v <= 1; }

function validate(p) {
  if (!p || typeof p !== 'object') return 'payload';
  if (typeof p.room !== 'string' || !p.room) return 'room';
  if (typeof p.light !== 'number' || !(p.light > 0 && p.light < 0.5)) return 'light';
  if (!Array.isArray(p.objects) || !p.objects.length) return 'objects';
  const ids = {};
  for (const o of p.objects) {
    if (!o || typeof o.id !== 'string' || !o.id || ids[o.id]) return 'objects.id';
    ids[o.id] = true;
    if (typeof o.labelKey !== 'string') return 'objects.labelKey';
    if (!num01(o.x) || !num01(o.y) || !num01(o.r) || o.r <= 0) return 'objects.xyr';
    if (o.clue != null && typeof o.clue !== 'string') return 'objects.clue';
  }
  if (!Array.isArray(p.find) || !p.find.length) return 'find';
  const seen = {};
  for (const f of p.find) {
    if (!ids[f] || seen[f]) return 'find';
    seen[f] = true;
  }
  return null;
}

class KomnataTrial {
  constructor(ctx) {
    this.ctx = ctx;
    this.root = null;
    this.field = null;
    this.timers = [];          // [{left, fn, tag}] — тикают в update(dt)
    this.img = null;
    this.dead = false;
    this.paused = false;
    this.done = false;
    this.finished = false;
    this.mistakes = 0;
    this.hintsUsed = 0;
    this.powerSpent = 0;
    this.found = {};           // id → true
    this.badTapped = {};       // обманка считается ошибкой один раз
    this.clues = [];
    this.glowing = false;
    this.lx = ROOM_W / 2;      // фонарь — в центре комнаты
    this.ly = ROOM_H / 2;
    this.dirty = true;
    this.bgUrl = null;
    this.t0 = 0;
    this.timeMs = null;
    this.pausedTotal = 0;
    this.pausedAt = 0;
  }

  // ---------- жизненный цикл ----------
  async start(field, task, level) {
    this.field = field;
    this.task = task || {};
    this.level = level;
    const p = this.task.payload;
    const bad = validate(p);
    if (bad) {
      this.ctx.fail({ code: 'TASK_INVALID', module: 'komnata', message: 'payload.' + bad, details: { taskId: this.task.id } });
      return;
    }
    this.p = p;
    this.R = Math.max(24, Math.round(p.light * ROOM_W));
    this.price = (this.ctx.balance && this.ctx.balance.hintPrice) || 1;
    this.objs = p.objects.map((o) => ({
      id: o.id, labelKey: o.labelKey, clue: o.clue || null,
      x: o.x * ROOM_W, y: o.y * ROOM_H, r: o.r * ROOM_W,
      target: p.find.indexOf(o.id) >= 0
    }));
    this.byId = {};
    this.objs.forEach((o) => { this.byId[o.id] = o; });
    this._build();
    await this._loadRoom();
    if (this.dead) return;
    this._syncHintBtn();
    this.render();
    this.t0 = performance.now();
  }

  update(dt) {
    if (this.dead || this.paused || !this.timers.length) return;
    const due = [];
    this.timers = this.timers.filter((t) => { t.left -= dt; if (t.left <= 0) { due.push(t.fn); return false; } return true; });
    due.forEach((fn) => { if (!this.dead) fn(); });
  }

  render() {
    if (this.dead || !this.dirty || !this.hole) return;
    this.dirty = false;
    const tx = Math.round(this.lx - HOLE_W / 2), ty = Math.round(this.ly - HOLE_H / 2);
    this.hole.style.transform = 'translate3d(' + tx + 'px,' + ty + 'px,0)';
  }

  onInput(e) {
    if (this.dead || this.paused || this.done || !this.root || !e) return;
    const a = e.action;
    if (a === 'tap' && e.target && e.target.closest && this.root.contains(e.target) && e.target.closest('[data-km="hint"]')) {
      this._askHint();
      return;
    }
    const fx = e.fx, fy = e.fy;
    if (typeof fx !== 'number' || typeof fy !== 'number') return;
    const inRoom = fx >= 0 && fx <= ROOM_W && fy >= 0 && fy <= ROOM_H;
    if (a === 'drag-start' || a === 'drag' || a === 'drag-end' || a === 'hold') {
      if (a === 'drag-start' && !inRoom) return;     // тянуть начали не в комнате — не фонарь
      this._moveLight(fx, fy);
      return;
    }
    if (a !== 'tap' || !inRoom) return;
    const dx = fx - this.lx, dy = fy - this.ly;
    const lit = dx * dx + dy * dy <= (this.R + LIGHT_PAD) * (this.R + LIGHT_PAD);
    if (lit) this._tapAt(fx, fy);
    this._moveLight(fx, fy);
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
    if (this.img) { this.img.onerror = null; this.img.onload = null; this.img = null; }
    if (this.root && this.root.parentNode) this.root.parentNode.removeChild(this.root);
    this.root = null;
    this.hole = null;
    this.field = null;
  }

  // ---------- построение экрана ----------
  _build() {
    const t = (k, v) => this.ctx.text(k, v);
    const root = el('div', 'km-root');
    this.root = root;

    const room = el('div', 'km-room');
    this.room = room;
    this.pic = el('div', 'km-pic');
    room.appendChild(this.pic);

    // Тьма: слой вдвое больше комнаты, в центре — дырка-луч; двигается только transform
    const dark = el('div', 'km-dark');
    const hole = el('div', 'km-hole');
    const R = this.R, S = Math.round(R * (1 + SOFT));
    hole.style.width = HOLE_W + 'px';
    hole.style.height = HOLE_H + 'px';
    hole.style.background = 'radial-gradient(circle at 50% 50%, rgba(255,214,140,0.10) 0px, rgba(0,0,0,0) ' +
      Math.round(R * 0.7) + 'px, rgba(0,0,0,0.25) ' + R + 'px, rgba(0,0,0,0.96) ' + S + 'px, rgba(0,0,0,0.96) 100%)';
    dark.appendChild(hole);
    this.dark = dark;
    this.hole = hole;
    room.appendChild(dark);

    this.fx = el('div', 'km-fx');           // над тьмой: найденные, вспышки, подсказка
    room.appendChild(this.fx);
    this.caption = el('div', 'km-caption');
    room.appendChild(this.caption);
    root.appendChild(room);

    // Список «Найдите»
    const side = el('div', 'km-side');
    side.appendChild(el('div', 'km-title', t('km.findTitle')));
    this.list = el('ul', 'km-list');
    this.items = {};
    this.p.find.forEach((id) => {
      const o = this.byId[id];
      const li = el('li', 'km-item');
      li.appendChild(el('span', 'km-mark'));
      li.appendChild(el('span', 'km-label', t(o.labelKey)));
      this.list.appendChild(li);
      this.items[id] = li;
    });
    side.appendChild(this.list);
    this.count = el('div', 'km-count');
    side.appendChild(this.count);
    this.msg = el('div', 'km-msg');
    side.appendChild(this.msg);
    const btn = el('div', 'km-hintbtn');
    btn.setAttribute('data-km', 'hint');
    btn.setAttribute('role', 'button');
    btn.appendChild(el('span', 'km-hintbtn-label', t('km.hintBtn')));
    const price = el('span', 'km-price');
    price.innerHTML = POWER_ICON;
    price.appendChild(el('b', null, '−' + this.price));
    btn.appendChild(price);
    this.btn = btn;
    side.appendChild(btn);
    root.appendChild(side);
    this._syncCount();
    this.field.appendChild(root);
  }

  // Картинка комнаты: AssetLoader.image(id) → bitmap/svg; иначе — векторная заглушка
  _loadRoom() {
    const a = this.ctx.assets;
    let pr = null;
    try { pr = a && typeof a.image === 'function' ? a.image(this.p.room) : null; } catch (e) { pr = null; }
    if (!pr && a && typeof a.url === 'function') pr = Promise.resolve({ kind: 'bitmap', url: a.url(this.p.room) });
    return Promise.resolve(pr)
      .then((r) => (r && (r.kind === 'bitmap' || r.kind === 'svg') && r.url ? this._showImage(r.url) : this._showStub()))
      .catch(() => this._showStub());
  }

  _showImage(url) {
    if (this.dead) return null;
    return new Promise((resolve) => {
      const img = el('img', 'km-img');
      img.alt = '';
      img.draggable = false;
      this.img = img;
      img.onload = () => { img.onload = null; img.onerror = null; resolve(); };
      img.onerror = () => {
        img.onload = null; img.onerror = null;
        if (!this.dead && img.parentNode) img.parentNode.removeChild(img);
        this.bgUrl = null;
        this._showStub();
        resolve();
      };
      this.bgUrl = url;
      img.src = url;
      this.pic.appendChild(img);
    });
  }

  // Простая векторная комната: стены, пол, полки и цветные предметы на местах из задания
  _showStub() {
    if (this.dead) return;
    this.bgUrl = null;
    this.pic.classList.add('is-stub');
    let s = '<svg viewBox="0 0 ' + ROOM_W + ' ' + ROOM_H + '" width="' + ROOM_W + '" height="' + ROOM_H + '" aria-hidden="true">' +
      '<rect width="800" height="600" fill="#4a3a52"/>' +
      '<rect y="440" width="800" height="160" fill="#5a3d26"/>' +
      '<path d="M0 440 L800 440" stroke="#2a1a10" stroke-width="6"/>';
    [140, 270, 390].forEach((y) => {
      s += '<rect x="30" y="' + y + '" width="740" height="12" fill="#7a5232"/>';
    });
    this.objs.forEach((o, i) => {
      const c = STUB_COLORS[i % STUB_COLORS.length];
      const r = Math.max(10, Math.round(o.r));
      s += i % 2
        ? '<rect x="' + Math.round(o.x - r) + '" y="' + Math.round(o.y - r) + '" width="' + 2 * r + '" height="' + 2 * r + '" rx="' + Math.round(r / 3) + '" fill="' + c + '"/>'
        : '<circle cx="' + Math.round(o.x) + '" cy="' + Math.round(o.y) + '" r="' + r + '" fill="' + c + '"/>';
    });
    s += '</svg>';
    const old = this.pic.querySelector('svg');
    if (old) this.pic.removeChild(old);
    this.pic.insertAdjacentHTML('beforeend', s);
  }

  // ---------- фонарь и поиск ----------
  _moveLight(x, y) {
    x = Math.max(0, Math.min(ROOM_W, x));
    y = Math.max(0, Math.min(ROOM_H, y));
    if (x === this.lx && y === this.ly) return;
    this.lx = x; this.ly = y;
    this.dirty = true;
  }

  _tapAt(x, y) {
    let best = null, bestD = Infinity;
    this.objs.forEach((o) => {
      const d = Math.sqrt((x - o.x) * (x - o.x) + (y - o.y) * (y - o.y));
      const lim = o.r * HIT_SCALE + HIT_PAD;
      if (d <= lim && d / lim < bestD) { bestD = d / lim; best = o; }
    });
    if (!best) return;                        // мимо предметов — не ошибка
    if (best.target) {
      if (!this.found[best.id]) this._found(best);
      return;
    }
    this._decoy(best);
  }

  _found(o) {
    this.found[o.id] = true;
    if (o.clue && this.clues.indexOf(o.clue) < 0) this.clues.push(o.clue);
    this.ctx.audio.sfx('star');
    this._litSpot(o);
    this._flash(o, 'km-ring');
    const li = this.items[o.id];
    if (li) li.classList.add('is-found');
    this._say(this.ctx.text('km.found', { item: this.ctx.text(o.labelKey) }), false);
    if (this.glowing && this.glowId === o.id) this._stopGlow();
    this._syncCount();
    this._syncHintBtn();
    if (this.p.find.every((id) => this.found[id])) this._win();
  }

  _decoy(o) {
    this._flash(o, 'km-ring is-bad');
    this.ctx.audio.sfx('wrong');
    if (this.badTapped[o.id]) return;       // та же обманка второй раз — без штрафа
    this.badTapped[o.id] = true;
    this.mistakes++;
    this._say(this.ctx.text('km.wrong'), true);
    this.ctx.react('mistake');
  }

  // Найденный предмет остаётся освещённым: кружок с той же картинкой поверх тьмы
  _litSpot(o) {
    const r = Math.round(o.r * HIT_SCALE + 4);
    const d = el('div', 'km-lit');
    d.style.left = Math.round(o.x - r) + 'px';
    d.style.top = Math.round(o.y - r) + 'px';
    d.style.width = 2 * r + 'px';
    d.style.height = 2 * r + 'px';
    if (this.bgUrl) {
      d.style.backgroundImage = 'url("' + this.bgUrl + '")';
      d.style.backgroundSize = ROOM_W + 'px ' + ROOM_H + 'px';
      d.style.backgroundPosition = (-Math.round(o.x - r)) + 'px ' + (-Math.round(o.y - r)) + 'px';
    }
    this.fx.appendChild(d);
  }

  _flash(o, cls) {
    const r = Math.round(o.r * HIT_SCALE + 6);
    const d = el('div', cls);
    d.style.left = Math.round(o.x - r) + 'px';
    d.style.top = Math.round(o.y - r) + 'px';
    d.style.width = 2 * r + 'px';
    d.style.height = 2 * r + 'px';
    this.fx.appendChild(d);
    this.timers.push({ left: FLASH_MS, fn: () => { if (d.parentNode) d.parentNode.removeChild(d); } });
  }

  // ---------- подсказка ----------
  _left() { return this.p.find.filter((id) => !this.found[id]); }

  _askHint() {
    if (this.glowing) return;
    const left = this._left();
    if (!left.length) return;
    if (!this.ctx.power.spend(this.price, 'komnata')) {
      this._say(this.ctx.text('km.noPower'), true);
      this._shake(this.btn);
      return;
    }
    this.powerSpent += this.price;
    this.hintsUsed++;
    this.ctx.hint('glow');
    this.ctx.audio.sfx('chime');
    const id = left.length === 1 ? left[0] : this.ctx.rng.pick(left);
    this._glow(this.byId[id]);
  }

  _glow(o) {
    const r = Math.round(o.r * HIT_SCALE + 26);
    const g = el('div', 'km-glow');
    g.style.left = Math.round(o.x - r) + 'px';
    g.style.top = Math.round(o.y - r) + 'px';
    g.style.width = 2 * r + 'px';
    g.style.height = 2 * r + 'px';
    this.fx.appendChild(g);
    this.glowEl = g;
    this.glowId = o.id;
    this.glowing = true;
    this._syncHintBtn();
    this.timers.push({ left: GLOW_MS, tag: 'glow', fn: () => this._stopGlow() });
  }

  _stopGlow() {
    this.timers = this.timers.filter((t) => t.tag !== 'glow');
    if (this.glowEl && this.glowEl.parentNode) this.glowEl.parentNode.removeChild(this.glowEl);
    this.glowEl = null;
    this.glowId = null;
    this.glowing = false;
    this._syncHintBtn();
  }

  _syncHintBtn() {
    if (!this.btn) return;
    const off = this.done || !this._left().length;
    this.btn.classList.toggle('is-off', off);
    this.btn.classList.toggle('is-busy', !off && this.glowing);
  }

  _syncCount() {
    const n = this.p.find.length, k = this.p.find.filter((id) => this.found[id]).length;
    this.count.textContent = this.ctx.text('km.progress', { k: k, n: n });
  }

  _say(text, bad) {
    this.msg.textContent = text;
    this.msg.classList.toggle('is-bad', !!bad);
    this.msg.classList.add('is-on');
    this.timers = this.timers.filter((t) => t.tag !== 'msg');
    this.timers.push({ left: MSG_MS, tag: 'msg', fn: () => { if (this.msg) this.msg.classList.remove('is-on'); } });
  }

  _shake(node) {
    node.classList.remove('is-shake');
    void node.offsetWidth;             // перезапуск CSS-анимации
    node.classList.add('is-shake');
  }

  // ---------- конец ----------
  _win() {
    this.done = true;
    this.timeMs = this._activeMs();
    if (this.glowing) this._stopGlow();
    this.root.classList.add('is-done');
    this.dark.classList.add('is-off');       // комната плавно освещается целиком
    this.caption.textContent = this.ctx.text('km.solved');
    this.caption.classList.add('is-on');
    this._syncHintBtn();
    this.ctx.react('correct');
    this.timers.push({ left: FINISH_MS, fn: () => this._finish(true) });
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
      type: 'komnata',
      taskId: this.task.id,
      level: this.level,
      solved: solved,
      accuracy: Math.max(0, 1 - 0.2 * this.mistakes),
      hintsUsed: this.hintsUsed,
      powerSpent: this.powerSpent,
      mistakes: this.mistakes,
      timeMs: this.timeMs != null ? this.timeMs : this._activeMs(),
      caseClues: this.clues.slice()
    });
  }
}

export const Komnata = {
  type: 'komnata',
  schemaVersion: 1,
  create(ctx) { return new KomnataTrial(ctx); }
};
