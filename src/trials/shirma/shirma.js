// Испытание «Ширма» (shirma): угадать предмет за ширмой по подсказкам.
// Контракт — contracts.md §11, формат задания — §12.2.
// Все тексты — через ctx.text, случайность не нужна. Таймеры — только свои, на update(dt).

// Иконки видов подсказок (24×24, рисуются обводкой золотом)
const ICONS = {
  silhouette: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.5 3.6-7 8-7s8 2.5 8 7"/>',
  sound: '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16 9c1.6 1.8 1.6 4.2 0 6"/><path d="M18.5 6.5c3 3 3 8 0 11"/>',
  warmth: '<path d="M12 3c3 4 6 6.5 6 11a6 6 0 0 1-12 0c0-3 1.5-5 3-6.5 0 3 1 4.5 3 4.5-1-3-1-6 0-9z"/>',
  detail: '<circle cx="10" cy="10" r="6"/><path d="M14.5 14.5L21 21"/>',
  smell: '<path d="M7 21c-2-3 2-5 0-8s2-5 0-8"/><path d="M12 21c-2-3 2-5 0-8s2-5 0-8"/><path d="M17 21c-2-3 2-5 0-8s2-5 0-8"/>'
};
const POWER_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3.2"/></svg>';

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function iconSvg(kind) {
  return '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[kind] || ICONS.detail) + '</svg>';
}

// Первая буква названия — для заглушки, если картинки нет
function firstLetter(s) {
  const m = String(s || '').match(/[\p{L}\p{N}]/u);
  return m ? m[0].toUpperCase() : '?';
}

function validate(p) {
  if (!p || typeof p !== 'object') return 'payload';
  if (!Array.isArray(p.options) || p.options.length < 2) return 'options';
  if (typeof p.answer !== 'string' || p.options.indexOf(p.answer) < 0) return 'answer';
  if (p.options.some((o) => typeof o !== 'string')) return 'options';
  if (!Array.isArray(p.hints)) return 'hints';
  if (p.hints.some((h) => !h || typeof h.textKey !== 'string')) return 'hints';
  return null;
}

class ShirmaTrial {
  constructor(ctx) {
    this.ctx = ctx;
    this.root = null;
    this.timers = [];          // [{left, fn}] — тикают в update(dt)
    this.imgs = [];            // картинки, у которых надо снять обработчики в destroy
    this.dead = false;
    this.paused = false;
    this.done = false;         // ответ найден, ввод больше не принимается
    this.finished = false;
    this.mistakes = 0;
    this.hintsUsed = 0;
    this.powerSpent = 0;
    this.opened = 0;           // сколько подсказок открыто (включая бесплатную)
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
      this.ctx.fail({ code: 'TASK_INVALID', module: 'shirma', message: 'payload.' + bad, details: { taskId: this.task.id } });
      return;
    }
    this.p = p;
    this.price = (this.ctx.balance && this.ctx.balance.hintPrice) || 1;
    this._build();
    // Первая подсказка открыта бесплатно и не считается в hintsUsed
    if (p.hints.length) this._openHint(p.hints[0], true);
    this._syncHintBtn();
    this.t0 = performance.now();
  }

  update(dt) {
    if (this.dead || this.paused || !this.timers.length) return;
    const due = [];
    this.timers = this.timers.filter((t) => { t.left -= dt; if (t.left <= 0) { due.push(t.fn); return false; } return true; });
    due.forEach((fn) => { if (!this.dead) fn(); });
  }

  render() {}

  onInput(e) {
    if (this.dead || this.paused || this.done || !this.root) return;
    if (!e || e.action !== 'tap' || !e.target || !e.target.closest) return;
    if (!this.root.contains(e.target)) return;
    const opt = e.target.closest('[data-opt]');
    if (opt) { this._choose(opt.getAttribute('data-opt'), opt); return; }
    if (e.target.closest('[data-sh="hint"]')) this._askHint();
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
    this.imgs.forEach((im) => { im.onerror = null; im.onload = null; });
    this.imgs = [];
    if (this.root && this.root.parentNode) this.root.parentNode.removeChild(this.root);
    this.root = null;
    this.field = null;
  }

  // ---------- построение экрана ----------
  _build() {
    const t = (k, v) => this.ctx.text(k, v);
    const root = el('div', 'sh-root');
    this.root = root;

    root.appendChild(el('div', 'sh-ask', t('shirma.ask')));

    // Ширма: сцена-подсветка позади, три створки с тканью, ножки
    const screen = el('div', 'sh-screen');
    const stage = el('div', 'sh-stage');
    stage.appendChild(el('div', 'sh-light'));
    this.prize = el('div', 'sh-prize');
    stage.appendChild(this.prize);
    screen.appendChild(stage);

    const cloth = el('div', 'sh-cloth');
    ['l', 'm', 'r'].forEach((s) => {
      const leaf = el('div', 'sh-leaf sh-leaf-' + s);
      const fabric = el('div', 'sh-fabric');
      leaf.appendChild(fabric);
      leaf.appendChild(el('div', 'sh-leaf-shade'));
      if (s === 'm') { this.shadowHost = el('div', 'sh-shadows'); fabric.appendChild(this.shadowHost); }
      cloth.appendChild(leaf);
    });
    ['a', 'b', 'c', 'd'].forEach((s) => cloth.appendChild(el('div', 'sh-hinge sh-hinge-' + s)));
    this.cloth = cloth;
    screen.appendChild(cloth);
    this.caption = el('div', 'sh-caption');
    screen.appendChild(this.caption);
    root.appendChild(screen);

    // Колонка подсказок
    const side = el('div', 'sh-side');
    side.appendChild(el('div', 'sh-side-title', t('shirma.hintsTitle')));
    this.list = el('ul', 'sh-hints');
    side.appendChild(this.list);
    this.msg = el('div', 'sh-msg');
    side.appendChild(this.msg);
    const btn = el('div', 'sh-hintbtn');
    btn.setAttribute('data-sh', 'hint');
    btn.setAttribute('role', 'button');
    this.btnLabel = el('span', 'sh-hintbtn-label', t('shirma.hintBtn'));
    this.btnPrice = el('span', 'sh-price');
    this.btnPrice.innerHTML = POWER_ICON;
    this.btnPrice.appendChild(el('b', null, '−' + this.price));
    btn.appendChild(this.btnLabel);
    btn.appendChild(this.btnPrice);
    this.btn = btn;
    side.appendChild(btn);
    root.appendChild(side);

    // Варианты ответа
    const opts = el('div', 'sh-options');
    const n = this.p.options.length;
    const w = Math.floor(Math.min(170, (920 - 12 * n) / n));
    this.optEls = {};
    this.p.options.forEach((id) => {
      const card = el('div', 'sh-opt');
      card.setAttribute('data-opt', id);
      card.setAttribute('role', 'button');
      card.style.width = w + 'px';
      card.appendChild(this._art(id, 80));
      card.appendChild(el('div', 'sh-opt-label', this._label(id)));
      opts.appendChild(card);
      this.optEls[id] = card;
    });
    root.appendChild(opts);

    this.field.appendChild(root);
  }

  _item(id) {
    let it = null;
    try { it = this.ctx.item ? this.ctx.item(id) : null; } catch (e) { it = null; }
    return { labelKey: (it && it.labelKey) || 'item.' + id, art: (it && it.art) || 'item-' + id };
  }

  _label(id) { return this.ctx.text(this._item(id).labelKey); }

  _url(art) {
    const a = this.ctx.assets;
    return a && typeof a.url === 'function' ? a.url(art) : 'assets/art/' + art + '.svg';
  }

  // Картинка предмета; нет файла — кружок с первой буквой названия
  _art(id, size) {
    const info = this._item(id);
    const wrap = el('div', 'sh-art');
    wrap.style.width = size + 'px';
    wrap.style.height = size + 'px';
    const img = el('img', 'sh-img');
    img.alt = '';
    img.draggable = false;
    img.onerror = () => {
      img.onerror = null;
      if (this.dead || img.parentNode !== wrap) return;
      const letter = el('div', 'sh-letter', firstLetter(this.ctx.text(info.labelKey)));
      letter.style.fontSize = Math.round(size * 0.48) + 'px';
      wrap.replaceChild(letter, img);
    };
    this.imgs.push(img);
    img.src = this._url(info.art);
    wrap.appendChild(img);
    return wrap;
  }

  // Тень предмета-ответа на ткани
  _shadow(sharp) {
    const info = this._item(this.p.answer);
    const layer = el('div', 'sh-shadow' + (sharp ? ' is-sharp' : ''));
    const img = el('img', 'sh-sil');
    img.alt = '';
    img.draggable = false;
    img.onerror = () => {
      img.onerror = null;
      if (this.dead || img.parentNode !== layer) return;
      layer.replaceChild(el('div', 'sh-sil-blob'), img);
    };
    this.imgs.push(img);
    img.src = this._url(info.art);
    layer.appendChild(img);
    this.shadowHost.appendChild(layer);
  }

  // ---------- подсказки ----------
  _openHint(h, free) {
    const kind = ICONS[h.kind] ? h.kind : 'detail';
    const li = el('li', 'sh-hint');
    const ic = el('div', 'sh-hint-ic');
    ic.innerHTML = iconSvg(kind);
    const tx = el('div', 'sh-hint-tx');
    tx.appendChild(el('b', 'sh-hint-kind', this.ctx.text('shirma.kind.' + kind)));
    tx.appendChild(el('span', null, this.ctx.text(h.textKey)));
    li.appendChild(ic);
    li.appendChild(tx);
    this.list.appendChild(li);
    this.list.scrollTop = this.list.scrollHeight;
    if (h.kind === 'silhouette') this._shadow(!free);
    this.opened++;
  }

  _askHint() {
    const hints = this.p.hints;
    if (this.opened >= hints.length) return;            // подсказки кончились
    if (!this.ctx.power.spend(this.price, 'shirma.hint')) {
      this._flash(this.ctx.text('shirma.noPower'));
      this._shake(this.btn);
      return;
    }
    const h = hints[this.opened];
    this.powerSpent += this.price;
    this.hintsUsed++;
    this.ctx.hint(h.kind);
    this.ctx.audio.sfx('cloth');
    this._openHint(h, false);
    this._syncHintBtn();
  }

  _syncHintBtn() {
    const left = this.p.hints.length - this.opened;
    if (left > 0) return;
    this.btn.classList.add('is-off');
    this.btnLabel.textContent = this.ctx.text('shirma.noMoreHints');
    this.btnPrice.style.display = 'none';
  }

  _flash(text) {
    this.msg.textContent = text;
    this.msg.classList.add('is-on');
    this.timers = this.timers.filter((t) => t.tag !== 'msg');
    this.timers.push({ left: 2000, tag: 'msg', fn: () => { this.msg.classList.remove('is-on'); } });
  }

  _shake(node) {
    node.classList.remove('is-shake');
    void node.offsetWidth;             // перезапуск CSS-анимации
    node.classList.add('is-shake');
  }

  // ---------- ответ ----------
  _choose(id, card) {
    if (card.classList.contains('is-wrong')) return;
    if (id === this.p.answer) { this._win(card); return; }
    this.mistakes++;
    card.classList.add('is-wrong');
    this._shake(card);
    this.ctx.audio.sfx('wrong');
    this.ctx.react('mistake');
  }

  _win(card) {
    this.done = true;
    this.timeMs = this._activeMs();             // время — до верного ответа, без анимации
    this.root.classList.add('is-done');
    card.classList.add('is-right');
    this.ctx.audio.sfx('cloth');
    this.cloth.classList.add('is-off');                 // ткань сдёргивается
    this.prize.appendChild(this._art(this.p.answer, 230));
    this.prize.classList.add('is-on');
    this.root.querySelector('.sh-light').classList.add('is-on');
    this.caption.textContent = this.ctx.text('shirma.reveal', { item: this._label(this.p.answer) });
    this.caption.classList.add('is-on');
    this.ctx.react('correct');
    this.timers.push({ left: 1500, fn: () => this._finish(true) });
  }

  _activeMs() {
    let ms = performance.now() - this.t0 - this.pausedTotal;
    if (this.paused) ms -= performance.now() - this.pausedAt;
    return Math.max(0, Math.round(ms));
  }

  _finish(solved) {
    if (this.finished || this.dead) return;
    this.finished = true;
    const n = this.p.options.length;
    this.ctx.finish({
      type: 'shirma',
      taskId: this.task.id,
      level: this.level,
      solved: solved,
      accuracy: Math.max(0, 1 - this.mistakes / Math.max(1, n - 1)),
      hintsUsed: this.hintsUsed,
      powerSpent: this.powerSpent,
      mistakes: this.mistakes,
      timeMs: this.timeMs != null ? this.timeMs : this._activeMs(),
      caseClues: []
    });
  }
}

export const Shirma = {
  type: 'shirma',
  schemaVersion: 1,
  create(ctx) { return new ShirmaTrial(ctx); }
};
