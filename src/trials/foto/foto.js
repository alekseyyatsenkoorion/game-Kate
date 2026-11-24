// Испытание «Фото-дело» (foto): по фотографии и вещам человека отметить верные утверждения.
// Контракт — contracts.md §11, формат задания — §12.2 (v2.3).
// Слева «полароид» и вещи, справа список утверждений. Отметить ровно pick и нажать «Проверить».
// Ошибка: неверно отмеченные зачёркиваются как ложные, mistakes +1 за проверку.
// Подсказка за силу зачёркивает одно ложное утверждение (выбор через ctx.rng).
// Удержание (или тык) по фото — фото крупно на всё поле, тык — закрыть.
// Таймеры — только свои, на update(dt). Анимации — CSS (transform/opacity).

const POWER_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3.2"/></svg>';
const CHECK_MARK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.8l4.6 4.6L19.2 7"/></svg>';
// Бирка — значок вещи без своей картинки
const TAG_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12.5V4.5A1.5 1.5 0 0 1 4.5 3h8l8.5 8.5-9.5 9.5z"/><circle cx="8" cy="8" r="1.8"/></svg>';
const ZOOM_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10" cy="10" r="6"/><path d="M14.5 14.5L21 21"/><path d="M7.5 10h5M10 7.5v5"/></svg>';
// Силуэт человека для заглушки (viewBox 0 0 100 100)
const SILHOUETTE =
  '<svg class="fo-sil" viewBox="0 0 100 100" aria-hidden="true">' +
  '<circle cx="50" cy="38" r="15"/>' +
  '<path d="M18 100 Q18 66 50 62 Q82 66 82 100 Z"/>' +
  '</svg>';

const FINISH_DELAY = 5200;     // мс от верного ответа до finish — успеть прочитать пояснения
const REVEAL_DELAY = 650;      // мс до показа пояснений
const MSG_MS = 2000;
const PARTIAL_MS = 3200;

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

// Первая буква подписи — для заглушки иконки
function firstLetter(s) {
  const m = String(s || '').match(/[\p{L}\p{N}]/u);
  return m ? m[0].toUpperCase() : '?';
}

function validate(p) {
  if (!p || typeof p !== 'object') return 'payload';
  if (typeof p.photo !== 'string' || !p.photo) return 'photo';
  if (p.items != null && !Array.isArray(p.items)) return 'items';
  if ((p.items || []).some((it) => !it || typeof it.labelKey !== 'string' || (it.art != null && typeof it.art !== 'string'))) return 'items';
  if (!Array.isArray(p.statements) || p.statements.length < 2) return 'statements';
  if (p.statements.some((s) => !s || typeof s.textKey !== 'string' || typeof s.true !== 'boolean')) return 'statements';
  const right = p.statements.filter((s) => s.true).length;
  if (typeof p.pick !== 'number' || p.pick < 1 || p.pick !== right || right >= p.statements.length) return 'pick';
  return null;
}

class FotoTrial {
  constructor(ctx) {
    this.ctx = ctx;
    this.root = null;
    this.timers = [];          // [{left, fn, tag}] — тикают в update(dt)
    this.imgs = [];            // картинки, у которых надо снять обработчики в destroy
    this.dead = false;
    this.paused = false;
    this.done = false;
    this.finished = false;
    this.zoomed = false;
    this.mistakes = 0;
    this.hintsUsed = 0;
    this.powerSpent = 0;
    this.t0 = 0;
    this.timeMs = null;
    this.pausedTotal = 0;
    this.pausedAt = 0;
    this.st = [];              // [{ s, node, marked, locked }]
  }

  // ---------- жизненный цикл ----------
  async start(field, task, level) {
    this.field = field;
    this.task = task || {};
    this.level = level;
    const p = this.task.payload;
    const bad = validate(p);
    if (bad) {
      this.ctx.fail({ code: 'TASK_INVALID', module: 'foto', message: 'payload.' + bad, details: { taskId: this.task.id } });
      return;
    }
    this.p = p;
    this.pick = p.pick;
    this.price = (this.ctx.balance && this.ctx.balance.hintPrice) || 1;
    this._build();
    this._sync();
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
    if (this.dead || this.paused || !this.root || !e) return;
    const tg = e.target && e.target.closest ? e.target : null;
    if (this.zoomed) {
      if (e.action === 'tap') this._zoom(false);
      return;
    }
    if (!tg || !this.root.contains(tg)) return;
    const onPhoto = tg.closest('[data-fo="photo"]');
    if (e.action === 'hold') { if (onPhoto) this._zoom(true); return; }
    if (e.action !== 'tap') return;
    if (onPhoto) { this._zoom(true); return; }
    if (this.done) return;
    const st = tg.closest('[data-st]');
    if (st) { this._toggle(+st.getAttribute('data-st')); return; }
    if (tg.closest('[data-fo="check"]')) { this._check(); return; }
    if (tg.closest('[data-fo="hint"]')) this._askHint();
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
    this.st = [];
  }

  // ---------- построение экрана ----------
  _build() {
    const t = (k, v) => this.ctx.text(k, v);
    const root = el('div', 'fo-root fo-lv' + (this.level || 1));
    this.root = root;

    // Полароид
    const left = el('div', 'fo-left');
    const pol = el('div', 'fo-polaroid');
    pol.setAttribute('data-fo', 'photo');
    pol.setAttribute('role', 'button');
    const frame = el('div', 'fo-photo');
    frame.appendChild(this._photo());
    frame.appendChild(el('div', 'fo-vignette'));
    const hh = el('div', 'fo-holdhint');
    hh.innerHTML = ZOOM_ICON;
    hh.appendChild(el('span', null, t('fo.holdHint')));
    frame.appendChild(hh);
    pol.appendChild(frame);
    pol.appendChild(el('div', 'fo-strip', t('fo.ask')));
    left.appendChild(pol);

    // Вещи человека
    const items = this.p.items || [];
    if (items.length) {
      const box = el('div', 'fo-items');
      box.appendChild(el('div', 'fo-items-title', t('fo.items')));
      const row = el('div', 'fo-items-row');
      items.slice(0, 3).forEach((it, i) => {
        const card = el('div', 'fo-item fo-item-' + (i % 3));
        if (it.art) card.appendChild(this._art(it.art, it.labelKey));
        else { const tag = el('div', 'fo-art fo-tag'); tag.innerHTML = TAG_ICON; card.appendChild(tag); }
        card.appendChild(el('div', 'fo-item-label', t(it.labelKey)));
        row.appendChild(card);
      });
      box.appendChild(row);
      left.appendChild(box);
    }
    root.appendChild(left);

    // Утверждения
    const side = el('div', 'fo-side');
    const head = el('div', 'fo-head');
    this.title = el('div', 'fo-title', t('fo.pickK', { k: this.pick }));
    head.appendChild(this.title);
    this.counter = el('div', 'fo-count');
    head.appendChild(this.counter);
    side.appendChild(head);
    const list = el('div', 'fo-list');
    this.list = list;
    const order = this._shuffle(this.p.statements.map((s, i) => i));
    this.st = order.map((i, n) => {
      const s = this.p.statements[i];
      const node = el('div', 'fo-st');
      node.setAttribute('data-st', String(n));
      node.setAttribute('role', 'button');
      const boxEl = el('div', 'fo-box');
      boxEl.innerHTML = CHECK_MARK;
      node.appendChild(boxEl);
      const body = el('div', 'fo-st-body');
      body.appendChild(el('div', 'fo-st-tx', t(s.textKey)));
      if (s.true && s.explainKey) body.appendChild(el('div', 'fo-st-ex', t(s.explainKey)));
      node.appendChild(body);
      list.appendChild(node);
      return { s, node, marked: false, locked: false };
    });
    side.appendChild(list);
    this.msg = el('div', 'fo-msg');
    side.appendChild(this.msg);

    const btns = el('div', 'fo-btns');
    const hint = el('div', 'fo-btn fo-hint');
    hint.setAttribute('data-fo', 'hint');
    hint.setAttribute('role', 'button');
    this.hintLabel = el('span', 'fo-hint-label', t('fo.hintBtn'));
    this.hintPrice = el('span', 'fo-price');
    this.hintPrice.innerHTML = POWER_ICON;
    this.hintPrice.appendChild(el('b', null, '−' + this.price));
    hint.appendChild(this.hintLabel);
    hint.appendChild(this.hintPrice);
    this.hintBtn = hint;
    const chk = el('div', 'fo-btn fo-check', t('fo.check'));
    chk.setAttribute('data-fo', 'check');
    chk.setAttribute('role', 'button');
    this.checkBtn = chk;
    btns.appendChild(hint);
    btns.appendChild(chk);
    side.appendChild(btns);
    root.appendChild(side);

    // Крупный просмотр
    const zoom = el('div', 'fo-zoom');
    zoom.setAttribute('data-fo', 'zoom');
    const zp = el('div', 'fo-zoom-photo');
    zp.appendChild(this._photo());
    zp.appendChild(el('div', 'fo-vignette'));
    zoom.appendChild(zp);
    zoom.appendChild(el('div', 'fo-zoom-close', t('fo.zoomClose')));
    this.zoomEl = zoom;
    root.appendChild(zoom);

    this.field.appendChild(root);
  }

  _shuffle(a) {
    const b = a.slice();
    const r = this.ctx.rng;
    for (let i = b.length - 1; i > 0; i--) {
      const j = Math.floor(r.next() * (i + 1));
      const x = b[i]; b[i] = b[j]; b[j] = x;
    }
    return b;
  }

  _url(id) {
    const a = this.ctx.assets;
    return a && typeof a.url === 'function' ? a.url(id) : 'assets/art/' + id + '.svg';
  }

  _hasPhoto(id) {
    const a = this.ctx.assets;
    if (!a) return false;
    if (typeof a.has === 'function') return !!a.has(id);
    return typeof a.url === 'function';
  }

  // Фото: картинка из ChatGPT, иначе — нарисованный «снимок» с силуэтом
  _photo() {
    const id = this.p.photo;
    if (!this._hasPhoto(id)) return this._fallbackPhoto();
    const wrap = el('div', 'fo-img-wrap');
    const img = el('img', 'fo-img');
    img.alt = '';
    img.draggable = false;
    img.onerror = () => {
      img.onerror = null;
      if (this.dead || img.parentNode !== wrap) return;
      wrap.replaceChild(this._fallbackPhoto(), img);
    };
    this.imgs.push(img);
    img.src = this._url(id);
    wrap.appendChild(img);
    return wrap;
  }

  _fallbackPhoto() {
    const fb = el('div', 'fo-fallback');
    fb.innerHTML = SILHOUETTE;
    fb.appendChild(el('div', 'fo-fallback-cap', this.ctx.text('fo.noPhoto')));
    return fb;
  }

  // art — id ассета (item-key) или id предмета из items.json (key)
  _artId(art) {
    if (/^item-/.test(art)) return art;
    let it = null;
    try { it = this.ctx.item ? this.ctx.item(art) : null; } catch (e) { it = null; }
    return (it && it.art) || 'item-' + art;
  }

  _art(art, labelKey) {
    const wrap = el('div', 'fo-art');
    const img = el('img', 'fo-art-img');
    img.alt = '';
    img.draggable = false;
    img.onerror = () => {
      img.onerror = null;
      if (this.dead || img.parentNode !== wrap) return;
      wrap.replaceChild(el('div', 'fo-letter', firstLetter(this.ctx.text(labelKey))), img);
    };
    this.imgs.push(img);
    img.src = this._url(this._artId(art));
    wrap.appendChild(img);
    return wrap;
  }

  // ---------- состояние ----------
  _markedCount() { return this.st.filter((x) => x.marked).length; }
  _falseLeft() { return this.st.filter((x) => !x.locked && !x.s.true); }

  _sync() {
    const m = this._markedCount();
    this.counter.textContent = m + ' / ' + this.pick;
    this.counter.classList.toggle('is-full', m === this.pick);
    this.checkBtn.classList.toggle('is-off', this.done || m !== this.pick);
    if (!this.done && !this._falseLeft().length) {
      this.hintBtn.classList.add('is-off');
      this.hintLabel.textContent = this.ctx.text('fo.noMoreHints');
      this.hintPrice.style.display = 'none';
    }
  }

  _toggle(i) {
    const x = this.st[i];
    if (!x || x.locked) return;
    if (!x.marked && this._markedCount() >= this.pick) {
      this._flash(this.ctx.text('fo.tooMany', { k: this.pick }), MSG_MS);
      this._shake(this.counter);
      return;
    }
    x.marked = !x.marked;
    x.node.classList.toggle('is-marked', x.marked);
    this.ctx.audio.sfx('tap');
    this._sync();
  }

  _check() {
    if (this._markedCount() !== this.pick) { this._shake(this.counter); return; }
    const marked = this.st.filter((x) => x.marked);
    const wrong = marked.filter((x) => !x.s.true);
    if (!wrong.length) { this._win(); return; }
    this.mistakes++;
    wrong.forEach((x) => {
      x.marked = false;
      x.locked = true;
      x.node.classList.remove('is-marked');
      x.node.classList.add('is-false');
      this._shake(x.node);
    });
    this.ctx.audio.sfx('wrong');
    this.ctx.react('mistake');
    this._flash(this.ctx.text('fo.partial', { k: marked.length - wrong.length, n: this.pick }), PARTIAL_MS);
    this._sync();
  }

  _askHint() {
    const left = this._falseLeft();
    if (!left.length) return;
    if (!this.ctx.power.spend(this.price, 'foto.hint')) {
      this._flash(this.ctx.text('fo.noPower'), MSG_MS);
      this._shake(this.hintBtn);
      return;
    }
    const x = left[Math.floor(this.ctx.rng.next() * left.length)] || left[0];
    this.powerSpent += this.price;
    this.hintsUsed++;
    this.ctx.hint('strike');
    this.ctx.audio.sfx('cloth');
    x.marked = false;
    x.locked = true;
    x.node.classList.remove('is-marked');
    x.node.classList.add('is-struck');
    this._sync();
  }

  _win() {
    this.done = true;
    this.timeMs = this._activeMs();
    this.root.classList.add('is-done');
    this.st.forEach((x) => { if (x.s.true) x.node.classList.add('is-right'); });
    this.timers = this.timers.filter((t) => t.tag !== 'msg');
    this.msg.classList.remove('is-on');
    this.title.textContent = this.ctx.text('fo.solved');
    this._sync();
    this.ctx.react('correct');
    this.timers.push({ left: REVEAL_DELAY, fn: () => { this.list.classList.add('is-solved'); } });
    this.timers.push({ left: FINISH_DELAY, fn: () => this._finish(true) });
  }

  _zoom(on) {
    if (on === this.zoomed || !this.zoomEl) return;
    this.zoomed = on;
    this.zoomEl.classList.toggle('is-on', on);
  }

  _flash(text, ms) {
    this.msg.textContent = text;
    this.msg.classList.add('is-on');
    this.timers = this.timers.filter((t) => t.tag !== 'msg');
    this.timers.push({ left: ms, tag: 'msg', fn: () => { if (!this.done) this.msg.classList.remove('is-on'); } });
  }

  _shake(node) {
    node.classList.remove('is-shake');
    void node.offsetWidth;             // перезапуск CSS-анимации
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
      type: 'foto',
      taskId: this.task.id,
      level: this.level,
      solved: solved,
      accuracy: Math.max(0, 1 - this.mistakes / this.pick),
      hintsUsed: this.hintsUsed,
      powerSpent: this.powerSpent,
      mistakes: this.mistakes,
      timeMs: this.timeMs != null ? this.timeMs : this._activeMs(),
      caseClues: []
    });
  }
}

export const Foto = {
  type: 'foto',
  schemaVersion: 1,
  create(ctx) { return new FotoTrial(ctx); }
};
