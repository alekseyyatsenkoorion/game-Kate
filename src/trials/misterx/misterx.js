// Испытание «Мистер Икс» (misterx): по уликам решить логическую таблицу
// и собрать портрет скрытого человека (ask).
// Контракт — contracts.md §11, формат задания — §12.2 (v2.2). Поле clues[].rule не читается.
// Отметки в таблице бесплатны: пусто → ✗ → ✓ → пусто. При ✓ остальные клетки строки
// в этой категории и столбца получают серый авто-✗ (вычисляется при каждой перерисовке).
// Таймеры — только на update(dt). Анимации — CSS (transform/opacity).

const MARK_X = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/></svg>';
const MARK_V = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.8l4.6 4.6L19.2 7"/></svg>';
const POWER_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3.2"/></svg>';
// Силуэт незнакомца в шляпе и пальто (100×120)
const STRANGER =
  '<path d="M24 74 Q36 68 43 62 L57 62 Q64 68 76 74 Q90 80 92 100 L94 120 L6 120 L8 100 Q10 80 24 74 Z"/>' +
  '<ellipse cx="50" cy="50" rx="14" ry="16"/>' +
  '<path d="M31 38 L34 21 Q42 15 50 19 Q58 15 66 21 L69 38 Z"/>' +
  '<ellipse cx="50" cy="38" rx="31" ry="5.5"/>' +
  '<path class="mx-band" d="M32.5 31 L67.5 31 L68.6 36 L31.4 36 Z"/>';

// Состояния клетки
const EMPTY = 0, MX = 1, MV = 2, HV = 3;     // пусто, ручной ✗, ручной ✓, ✓ от подсказки (закреплён)

// Раскладка поля 960×600
const L = {
  W: 960, H: 600, pad: 8, gap: 8, top: 48,
  clueMax: 340, nameW: 96, tPad: 6, grpGap: 5, catH: 28, valH: 92,
  cellMin: 30, cellMax: 50, rowMin: 34, rowMax: 52,
  aPad: 8, aTitle: 44, chipMin: 40, chipMax: 52
};

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function px(n, x, y, w, h) {
  n.style.left = Math.round(x) + 'px';
  n.style.top = Math.round(y) + 'px';
  n.style.width = Math.round(w) + 'px';
  n.style.height = Math.round(h) + 'px';
  return n;
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

function validate(p) {
  if (!p || typeof p !== 'object') return 'payload';
  if (!Array.isArray(p.people) || p.people.length < 2) return 'people';
  const pids = {};
  for (const q of p.people) {
    if (!q || typeof q.id !== 'string' || pids[q.id] || typeof q.labelKey !== 'string') return 'people';
    pids[q.id] = true;
  }
  if (!Array.isArray(p.categories) || !p.categories.length) return 'categories';
  const keys = {};
  for (const c of p.categories) {
    if (!c || typeof c.key !== 'string' || keys[c.key] || typeof c.labelKey !== 'string') return 'categories';
    keys[c.key] = true;
    if (!Array.isArray(c.values) || c.values.length !== p.people.length) return 'categories.values';
    const vids = {};
    for (const v of c.values) {
      if (!v || typeof v.id !== 'string' || vids[v.id] || typeof v.labelKey !== 'string') return 'categories.values';
      vids[v.id] = true;
    }
  }
  if (typeof p.ask !== 'string' || !pids[p.ask]) return 'ask';
  const s = p.solution && p.solution[p.ask];
  if (!s || typeof s !== 'object') return 'solution';
  for (const c of p.categories) if (!c.values.some((v) => v.id === s[c.key])) return 'solution';
  if (!Array.isArray(p.clues) || p.clues.some((k) => !k || typeof k.textKey !== 'string')) return 'clues';
  return null;
}

class MisterXTrial {
  constructor(ctx) {
    this.ctx = ctx;
    this.root = null;
    this.timers = [];          // [{left, fn, tag}] — тикают в update(dt)
    this.dead = false;
    this.paused = false;
    this.done = false;         // ответ верный, ввод больше не принимается
    this.finished = false;
    this.mistakes = 0;
    this.hintsUsed = 0;
    this.powerSpent = 0;
    this.t0 = 0;
    this.timeMs = null;
    this.pausedTotal = 0;
    this.pausedAt = 0;
    this.answer = {};          // catKey → valueId (панель ответа)
    this.lastWrong = null;     // подпись последнего неверного ответа: повторно не отправляется
  }

  // ---------- жизненный цикл ----------
  async start(field, task, level) {
    this.field = field;
    this.task = task || {};
    this.level = level;
    const p = this.task.payload;
    const bad = validate(p);
    if (bad) {
      this.ctx.fail({ code: 'TASK_INVALID', module: 'misterx', message: 'payload.' + bad, details: { taskId: this.task.id } });
      return;
    }
    this.p = p;
    this.price = (this.ctx.balance && this.ctx.balance.hintPrice) || 1;
    this.truth = p.solution[p.ask];
    // столбцы таблицы: [{ci, vi, cat, val}] подряд по категориям
    this.cols = [];
    p.categories.forEach((c, ci) => c.values.forEach((v, vi) => this.cols.push({ ci, vi, cat: c, val: v })));
    this.askRow = p.people.findIndex((q) => q.id === p.ask);
    this.grid = p.people.map(() => this.cols.map(() => EMPTY));
    // порядок подсказок — по категориям, через ctx.rng
    this.hintOrder = this.ctx.rng.shuffle(p.categories.map((c, ci) => ci));
    this._build();
    this._paint();
    this._syncButtons();
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
    const cell = e.target.closest('[data-mx-cell]');
    if (cell) { this._tapCell(cell.getAttribute('data-mx-cell')); return; }
    const chip = e.target.closest('[data-mx-chip]');
    if (chip) { this._tapChip(chip.getAttribute('data-mx-chip')); return; }
    const btn = e.target.closest('[data-mx]');
    if (btn) {
      const a = btn.getAttribute('data-mx');
      if (a === 'submit') this._submit();
      else if (a === 'hint') this._askHint();
      return;
    }
    const clue = e.target.closest('[data-mx-clue]');
    if (clue) clue.classList.toggle('is-used');          // зачеркнуть использованную улику — бесплатно
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
    if (this.root && this.root.parentNode) this.root.parentNode.removeChild(this.root);
    this.root = null;
    this.field = null;
    this.cellEls = null;
    this.chipEls = null;
  }

  // ---------- раскладка ----------
  _layout() {
    const p = this.p, nc = p.categories.length, nr = p.people.length, ncol = this.cols.length;
    const fixedW = 2 * L.tPad + L.nameW + (nc - 1) * L.grpGap;
    const freeW = L.W - 2 * L.pad - L.gap;
    let cellW = Math.floor((freeW - L.clueMax - fixedW) / ncol);
    cellW = clamp(cellW, L.cellMin, L.cellMax);
    const tableW = fixedW + ncol * cellW;
    const clueW = Math.min(L.clueMax, freeW - tableW);
    const rightW = freeW - clueW;
    const bodyH = L.H - L.top - L.pad;
    // высота: таблица сверху, панель ответа снизу
    const answerMin = 2 * L.aPad + L.aTitle + nc * L.chipMin;
    const rowH = clamp(Math.floor((bodyH - L.gap - answerMin - 2 * L.tPad - L.catH - L.valH) / nr), L.rowMin, L.rowMax);
    const tableH = 2 * L.tPad + L.catH + L.valH + nr * rowH;
    const answerH = bodyH - L.gap - tableH;
    const chipH = clamp(Math.floor((answerH - 2 * L.aPad - L.aTitle) / nc), L.chipMin, L.chipMax);
    return { cellW, rowH, tableW, tableH, clueW, rightW, answerH, chipH };
  }

  // ---------- построение ----------
  _build() {
    const t = (k, v) => this.ctx.text(k, v);
    const p = this.p;
    const g = this._layout();
    this.g = g;
    const root = el('div', 'mx-root');
    this.root = root;

    root.appendChild(el('div', 'mx-ask', t('mx.ask')));

    // ---- колонка улик ----
    const side = px(el('div', 'mx-side'), L.pad, L.top, g.clueW, L.H - L.top - L.pad);
    side.appendChild(el('div', 'mx-side-title', t('mx.cluesTitle')));
    const list = el('ol', 'mx-clues');
    p.clues.forEach((k, i) => {
      const li = el('li', 'mx-clue');
      li.setAttribute('data-mx-clue', String(i));
      li.appendChild(el('span', 'mx-clue-n', String(i + 1)));
      li.appendChild(el('span', 'mx-clue-tx', t(k.textKey)));
      list.appendChild(li);
    });
    side.appendChild(list);
    this.msg = el('div', 'mx-msg');
    side.appendChild(this.msg);
    const hb = el('div', 'mx-hintbtn');
    hb.setAttribute('data-mx', 'hint');
    hb.setAttribute('role', 'button');
    this.hintLabel = el('span', 'mx-hintbtn-label', t('mx.hintBtn'));
    this.hintPrice = el('span', 'mx-price');
    this.hintPrice.innerHTML = POWER_ICON;
    this.hintPrice.appendChild(el('b', null, '−' + this.price));
    hb.appendChild(this.hintLabel);
    hb.appendChild(this.hintPrice);
    this.hintBtn = hb;
    side.appendChild(hb);
    root.appendChild(side);

    // ---- таблица ----
    const rx = L.pad + g.clueW + L.gap;
    const table = px(el('div', 'mx-table'), rx, L.top, g.rightW, g.tableH);
    const ox = Math.floor((g.rightW - g.tableW) / 2) + L.tPad;     // сетка по центру панели
    const gx = ox + L.nameW;
    const gy = L.tPad + L.catH + L.valH;
    const colX = (j) => gx + j * g.cellW + this.cols[j].ci * L.grpGap;
    p.people.forEach((q, r) => {
      const y = gy + r * g.rowH;
      table.appendChild(px(el('div', 'mx-rowbg' + (r === this.askRow ? ' is-ask' : '') + (r % 2 ? ' is-odd' : '')),
        ox - 2, y, g.tableW - 2 * L.tPad + 4, g.rowH));
      const nm = px(el('div', 'mx-name' + (r === this.askRow ? ' is-ask' : '')), ox, y, L.nameW - 6, g.rowH);
      nm.appendChild(el('span', null, t(q.labelKey)));
      table.appendChild(nm);
    });
    p.categories.forEach((c, ci) => {
      const first = this.cols.findIndex((col) => col.ci === ci);
      const w = c.values.length * g.cellW;
      table.appendChild(px(el('div', 'mx-cat', t(c.labelKey)), colX(first), L.tPad, w, L.catH));
      // рамка группы столбцов
      table.appendChild(px(el('div', 'mx-grp'), colX(first) - 1, gy - 1, w + 2, p.people.length * g.rowH + 2));
    });
    this.cellEls = [];
    this.cols.forEach((col, j) => {
      const vh = px(el('div', 'mx-val'), colX(j), L.tPad + L.catH, g.cellW, L.valH);
      const s = el('span', null, t(col.val.labelKey));
      s.style.top = (L.valH - 6) + 'px';
      s.style.width = (L.valH - 10) + 'px';
      vh.appendChild(s);
      table.appendChild(vh);
    });
    p.people.forEach((q, r) => {
      const row = [];
      this.cols.forEach((col, j) => {
        const c = px(el('div', 'mx-cell'), colX(j), gy + r * g.rowH, g.cellW, g.rowH);
        c.setAttribute('data-mx-cell', r + ':' + j);
        c.setAttribute('role', 'button');
        c._mx = '';
        table.appendChild(c);
        row.push(c);
      });
      this.cellEls.push(row);
    });
    this.table = table;
    root.appendChild(table);

    // ---- панель ответа ----
    const ans = px(el('div', 'mx-answer'), rx, L.top + g.tableH + L.gap, g.rightW, g.answerH);
    const head = el('div', 'mx-ans-head');
    this.ansTitle = el('div', 'mx-ans-title', t('mx.answerTitle'));
    this.ansMsg = el('div', 'mx-ans-msg');
    const sb = el('div', 'mx-submit', t('mx.submit'));
    sb.setAttribute('data-mx', 'submit');
    sb.setAttribute('role', 'button');
    this.submitBtn = sb;
    head.appendChild(this.ansTitle);
    head.appendChild(this.ansMsg);
    head.appendChild(sb);
    ans.appendChild(head);
    this.chipEls = {};
    p.categories.forEach((c) => {
      const row = el('div', 'mx-ans-row');
      row.style.height = g.chipH + 'px';
      row.appendChild(el('div', 'mx-ans-cat', t(c.labelKey)));
      const chips = el('div', 'mx-chips');
      c.values.forEach((v) => {
        const ch = el('div', 'mx-chip', t(v.labelKey));
        ch.setAttribute('data-mx-chip', c.key + ':' + v.id);
        ch.setAttribute('role', 'button');
        chips.appendChild(ch);
        this.chipEls[c.key + ':' + v.id] = ch;
      });
      row.appendChild(chips);
      ans.appendChild(row);
    });
    this.ans = ans;
    root.appendChild(ans);

    this.field.appendChild(root);
  }

  // ---------- таблица: состояние и отрисовка ----------
  // Видимое состояние клетки: 'x' | 'v' | 'h' | 'ax' (авто-✗) | ''
  _view(r, j) {
    const s = this.grid[r][j];
    if (s === MX) return 'x';
    if (s === MV) return 'v';
    if (s === HV) return 'h';
    const ci = this.cols[j].ci, row = this.grid[r];
    for (let k = 0; k < this.cols.length; k++) {
      if (k !== j && this.cols[k].ci === ci && row[k] >= MV) return 'ax';
    }
    for (let q = 0; q < this.grid.length; q++) {
      if (q !== r && this.grid[q][j] >= MV) return 'ax';
    }
    return '';
  }

  _paint() {
    for (let r = 0; r < this.grid.length; r++) {
      for (let j = 0; j < this.cols.length; j++) {
        const v = this._view(r, j), c = this.cellEls[r][j];
        if (c._mx === v) continue;
        c._mx = v;
        c.className = 'mx-cell' + (v ? ' is-' + v : '');
        c.innerHTML = v === 'x' || v === 'ax' ? MARK_X : v === 'v' || v === 'h' ? MARK_V : '';
      }
    }
  }

  _tapCell(id) {
    const m = /^(\d+):(\d+)$/.exec(id || '');
    if (!m) return;
    const r = +m[1], j = +m[2];
    if (!this.grid[r] || this.grid[r][j] == null) return;
    const s = this.grid[r][j];
    if (s === HV) return;                              // открыто подсказкой — закреплено
    this.grid[r][j] = s === EMPTY ? MX : s === MX ? MV : EMPTY;
    this.ctx.audio.sfx('tap');
    this._paint();
    this._syncButtons();
  }

  // ---------- панель ответа ----------
  _tapChip(id) {
    const i = (id || '').indexOf(':');
    if (i < 0 || !this.chipEls[id]) return;
    const key = id.slice(0, i), val = id.slice(i + 1);
    if (this.answer[key] === val) return;
    this._select(key, val);
    this.ctx.audio.sfx('tap');
  }

  _select(key, val) {
    const prev = this.answer[key];
    if (prev != null && this.chipEls[key + ':' + prev]) this.chipEls[key + ':' + prev].classList.remove('is-on');
    this.answer[key] = val;
    this.chipEls[key + ':' + val].classList.add('is-on');
    this._hideAnsMsg();
    this._syncButtons();
  }

  _signature() {
    return this.p.categories.map((c) => this.answer[c.key] || '').join('|');
  }

  _complete() {
    return this.p.categories.every((c) => this.answer[c.key] != null);
  }

  _submit() {
    if (!this._complete()) { this._shake(this.submitBtn); return; }
    const sig = this._signature();
    if (sig === this.lastWrong) return;                // тот же неверный ответ повторно не считается
    const n = this.p.categories.length;
    const k = this.p.categories.filter((c) => this.answer[c.key] === this.truth[c.key]).length;
    if (k === n) { this._win(); return; }
    this.mistakes++;
    this.lastWrong = sig;
    this.ctx.audio.sfx('wrong');
    this.ctx.react('mistake');
    this._showAnsMsg(this.ctx.text('mx.partial', { k, n }));
    this._shake(this.ans);
    this._syncButtons();
  }

  _showAnsMsg(text) {
    this.ansMsg.textContent = text;
    this.ans.classList.add('has-msg');
  }

  _hideAnsMsg() {
    if (this.ans) this.ans.classList.remove('has-msg');
  }

  // ---------- подсказка ----------
  _hintCands() {
    const r = this.askRow;
    return this.hintOrder.filter((ci) => {
      const key = this.p.categories[ci].key;
      const j = this.cols.findIndex((col) => col.ci === ci && col.val.id === this.truth[key]);
      return this.grid[r][j] < MV;
    });
  }

  _askHint() {
    const cands = this._hintCands();
    if (!cands.length) return;                         // всё открыто — кнопка неактивна
    if (!this.ctx.power.spend(this.price, 'misterx')) {
      this._flash(this.ctx.text('mx.noPower'));
      this._shake(this.hintBtn);
      return;
    }
    this.powerSpent += this.price;
    this.hintsUsed++;
    this.ctx.hint('reveal');
    this.ctx.audio.sfx('chime');
    const ci = cands[0], key = this.p.categories[ci].key, r = this.askRow;
    const j = this.cols.findIndex((col) => col.ci === ci && col.val.id === this.truth[key]);
    // ✓ открыт: ручные ✓, которые ему противоречат, снимаются (они точно неверны)
    for (let k = 0; k < this.cols.length; k++) if (this.cols[k].ci === ci && this.grid[r][k] === MV) this.grid[r][k] = EMPTY;
    for (let q = 0; q < this.grid.length; q++) if (this.grid[q][j] === MV) this.grid[q][j] = EMPTY;
    this.grid[r][j] = HV;
    this._paint();
    this.cellEls[r][j].classList.add('is-new');
    this._select(key, this.truth[key]);
  }

  _syncButtons() {
    const off = !this._hintCands().length;
    this.hintBtn.classList.toggle('is-off', off);
    this.hintLabel.textContent = this.ctx.text(off ? 'mx.noMoreHints' : 'mx.hintBtn');
    this.hintPrice.style.display = off ? 'none' : '';
    this.submitBtn.classList.toggle('is-off', !this._complete() || this._signature() === this.lastWrong);
  }

  _flash(text) {
    this.msg.textContent = text;
    this.msg.classList.add('is-on');
    this.timers = this.timers.filter((t) => t.tag !== 'msg');
    this.timers.push({ left: 2000, tag: 'msg', fn: () => { this.msg.classList.remove('is-on'); } });
  }

  _shake(node) {
    node.classList.remove('mx-shake');
    void node.offsetWidth;             // перезапуск CSS-анимации
    node.classList.add('mx-shake');
  }

  // ---------- победа ----------
  _win() {
    this.done = true;
    this.timeMs = this._activeMs();             // время — до верного ответа, без анимации
    this.root.classList.add('is-done');
    this._hideAnsMsg();
    // строка ask: верные ✓
    const r = this.askRow;
    this.cols.forEach((col, j) => {
      if (col.val.id === this.truth[col.cat.key]) this.grid[r][j] = HV;
      else if (this.grid[r][j] === MV) this.grid[r][j] = EMPTY;
    });
    this._paint();
    this._reveal();
    this.ctx.audio.sfx('star');
    this.ctx.react('correct');
    this.timers.push({ left: 1800, fn: () => this._finish(true) });
  }

  _reveal() {
    const t = (k, v) => this.ctx.text(k, v);
    const box = el('div', 'mx-reveal');
    box.appendChild(el('div', 'mx-reveal-bg'));
    const card = el('div', 'mx-reveal-card');
    const fig = el('div', 'mx-figure');
    fig.innerHTML = '<svg class="mx-fig-dark" viewBox="0 0 100 120" aria-hidden="true">' + STRANGER + '</svg>' +
      '<svg class="mx-fig-gold" viewBox="0 0 100 120" aria-hidden="true">' + STRANGER + '</svg>';
    card.appendChild(fig);
    const info = el('div', 'mx-reveal-info');
    info.appendChild(el('div', 'mx-reveal-title', t('mx.solved')));
    const ul = el('ul', 'mx-traits');
    this.p.categories.forEach((c, i) => {
      const v = c.values.find((x) => x.id === this.truth[c.key]);
      const li = el('li', null);
      li.style.animationDelay = (0.55 + i * 0.12).toFixed(2) + 's';
      li.appendChild(el('span', 'mx-trait-cat', t(c.labelKey)));
      li.appendChild(el('b', null, t(v.labelKey)));
      ul.appendChild(li);
    });
    info.appendChild(ul);
    card.appendChild(info);
    box.appendChild(card);
    this.root.appendChild(box);
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
      type: 'misterx',
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

export const MisterX = {
  type: 'misterx',
  schemaVersion: 1,
  create(ctx) { return new MisterXTrial(ctx); }
};
