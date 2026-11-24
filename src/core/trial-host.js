// Сцена trial — запускает испытание по контракту Trial (contracts.md §11).
import { Scene } from './scene-manager.js';
import { createRng, hashSeed } from './rng.js';
import { log } from './log.js';
import { subtitle } from './overlay.js';
import { TRIALS } from '../trials/index.js';

const cssLoaded = new Set();
function loadCss(type) {
  if (cssLoaded.has(type)) return;
  cssLoaded.add(type);
  const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = 'src/trials/' + type + '/' + type + '.css';
  document.head.appendChild(l);
}

export class TrialHost extends Scene {
  static get id() { return 'trial'; }
  async enter(root, params) {
    await super.enter(root, params);
    const app = this.app, n = +params.n, idx = +params.idx || 0;
    const ep = app.content.episode(n);
    let run = app.progress.run();
    if (!run || run.n !== n) {
      const attempt = ((app.progress.get().episodes[n] || {}).attempts || 0) + 1;
      run = { n, attempt, seed: hashSeed('ep', n, attempt), idx: 0, taskIds: [], results: [], bad: [] };
    }
    run.idx = idx;
    this.run = run; this.n = n; this.idx = idx; this.ep = ep;
    const def = ep.trials[idx];
    this.def = def;
    const mod = TRIALS[def.type];
    root.innerHTML =
      '<div class="trial-frame">' +
        '<div class="trial-top">' +
          '<button class="btn small ghost" data-action="leave">' + this.t('ui.back') + '</button>' +
          '<div class="trial-name"><span class="ep-label">' + this.t('ui.episodeN', { n }) +
            (ep.trials.length > 1 ? ' · ' + this.t('ui.partOf', { i: idx + 1, k: ep.trials.length }) : '') +
            ' · ' + this.t('ui.level', { l: def.level }) + '</span><b>' + this.t('trial.' + def.type + '.name') + '</b></div>' +
          '<div class="power" data-power>' + this.t('ui.power') + ': <b>' + app.progress.get().power + '</b></div>' +
        '</div>' +
        '<div class="trial-field"></div>' +
      '</div>';
    this.field = root.querySelector('.trial-field');
    this.powerEl = root.querySelector('[data-power] b');
    if (!mod) {
      log.warn('TRIAL_UNKNOWN_' + def.type, 'Нет модуля ' + def.type);
      this.field.innerHTML = '<div class="wip">' + this.t('ui.inDevelopment') + '</div>';
      return;
    }
    loadCss(def.type);
    await this._startTask(mod);
  }
  async _startTask(mod, tries) {
    tries = tries || 0;
    const app = this.app, run = this.run, def = this.def;
    if (tries >= 3) { this.app.scenes.replace('error', { code: 'TASK_INVALID', from: 'trial' }); return; }
    let task = null;
    const pool = await app.content.pool(def.type, def.level);
    if (run.taskIds[this.idx]) task = pool.find((t) => t.id === run.taskIds[this.idx]) || null;
    if (!task) {
      try { task = await app.content.draw(def.type, def.level, createRng(hashSeed(run.seed, this.idx, tries)), run.bad); }
      catch (e) { this.field.innerHTML = '<div class="wip">' + this.t('ui.inDevelopment') + '</div>'; return; }
      run.taskIds[this.idx] = task.id;
    }
    app.progress.saveRun(run);
    app.dayLock.markStarted(this.n);
    this.hints = 0; this.finished = false;
    const host = this;
    const ctx = {
      rng: createRng(hashSeed(run.seed, task.id)),
      audio: app.audio, assets: app.assets,
      text: (k, v) => app.content.text(k, v),
      item: (id) => app.content.item(id),
      balance: app.content.trialBalance(def.type, def.level),
      traps: app.progress.get().skeptic.pendingTraps || 0,
      power: {
        get: () => app.progress.get().power,
        spend: (k, reason) => {
          if (app.progress.get().power < k) return false;
          app.progress.update((d) => { d.power -= k; });
          host.powerEl.textContent = app.progress.get().power;
          app.audio.sfx('power');
          return true;
        }
      },
      hint: () => { host.hints++; },
      react: (kind) => host._react(kind),
      finish: (result) => host._finish(result),
      fail: (err) => {
        log.warn('TASK_INVALID_' + task.id, 'Битое задание ' + task.id);
        run.bad.push(task.id); run.taskIds[host.idx] = null;
        host._destroyInst();
        host.field.innerHTML = '';
        host._startTask(mod, tries + 1);
      }
    };
    this.inst = mod.create(ctx);
    try { await this.inst.start(this.field, task, def.level); }
    catch (e) { ctx.fail(e); }
  }
  _react(kind) {
    const app = this.app, rng = createRng(hashSeed(performance.now()));
    if (kind === 'correct') {
      const s = app.content.pickText('host.praise', rng);
      subtitle(app.content.text('char.host.name'), s, '#f1c86b');
      app.audio.praise(s);
    } else if (kind === 'mistake') {
      const s = app.content.pickText('skeptic.jab', rng);
      subtitle(app.content.text('char.skeptic.name'), s, '#ff8a65');
      app.audio.laugh(s);
    }
  }
  _finish(result) {
    if (this.finished) { log.warn('FINISH_TWICE', 'finish вызван повторно'); return; }
    this.finished = true;
    const run = this.run;
    run.results[this.idx] = result;
    this.app.progress.saveRun(run);
    const next = this.idx + 1 < this.ep.trials.length;
    this.later(() => {
      if (next) this.app.scenes.replace('trial', { n: this.n, idx: this.idx + 1 });
      else this.app.scenes.replace('result', { n: this.n });
    }, 2600);
  }
  _destroyInst() { if (this.inst) { try { this.inst.destroy(); } catch (e) { log.warn('DESTROY', String(e)); } this.inst = null; } }
  update(dt) { if (this.inst) this.inst.update(dt); }
  render() { if (this.inst) this.inst.render(); }
  onInput(e) {
    const a = e.target && e.target.closest && e.target.closest('[data-action="leave"]');
    if (a && e.action === 'tap') { this.app.scenes.replace('season'); return; }
    if (this.inst) {
      const fx = e.x - 32, fy = e.y - 132;                // поле 960×600 с отступом от рамки
      this.inst.onInput(Object.assign({}, e, { fx, fy }));
    }
  }
  pause() { if (this.inst) this.inst.pause(); }
  resume() { if (this.inst) this.inst.resume(); }
  async exit() { this._destroyInst(); await super.exit(); }
}
