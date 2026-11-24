// Scene (базовый класс) и SceneManager — contracts.md §1, §2.
import { log, gameError } from './log.js';

export const SCENE_IDS = ['title', 'season', 'intro', 'trial', 'result', 'diary', 'settings', 'debug', 'error'];

export class Scene {
  constructor(app) { this.app = app; this.root = null; this.params = {}; this._timers = []; }
  async enter(root, params) { this.root = root; this.params = params || {}; }
  update(dtMs) {}
  render() {}
  onInput(e) {}
  pause() {}
  resume() {}
  async exit() { this._timers.forEach((t) => clearTimeout(t)); this._timers = []; }
  // помощник: таймер, который сам снимется при exit
  later(fn, ms) { const t = setTimeout(fn, ms); this._timers.push(t); return t; }
  t(key, vars) { return this.app.content.text(key, vars); }
}

export class SceneManager {
  constructor(app, host) {
    this.app = app; this.host = host;
    this.classes = new Map();
    this.stack = [];
    this.cur = null; this.curId = null; this.curParams = {};
    this.busy = false; this.queued = null;
    this.fns = new Set();
  }
  register(cls) {
    const id = cls.id;
    if (!SCENE_IDS.includes(id) || this.classes.has(id)) throw gameError('SCENE_REGISTER', 'SceneManager', 'Bad scene id: ' + id);
    this.classes.set(id, cls);
  }
  current() { return { id: this.curId, params: this.curParams }; }
  onChange(fn) { this.fns.add(fn); return () => this.fns.delete(fn); }

  go(id, params) { return this._switch(id, params, 'push'); }
  replace(id, params) { return this._switch(id, params, 'replace'); }
  back() {
    const prev = this.stack.pop();
    return prev ? this._switch(prev.id, prev.params, 'none') : this._switch('title', {}, 'none');
  }
  async finish(result) {
    const fromId = this.curId;
    await this.back();
    if (this.cur && this.cur.onReturn) this._safe(() => this.cur.onReturn(fromId, result || {}));
  }

  async _switch(id, params, mode) {
    if (!this.classes.has(id)) { log.error('SCENE_UNKNOWN', 'Unknown scene ' + id); return; }
    if (this.busy) { this.queued = [id, params, mode]; return; }
    this.busy = true;
    this.app.input.setEnabled(false);
    try {
      if (this.cur) {
        if (mode === 'push') { this.stack.push({ id: this.curId, params: this.curParams }); if (this.stack.length > 10) this.stack.shift(); }
        try { await this.cur.exit(); } catch (e) { log.error('SCENE_EXIT', String(e)); }
        this.host.classList.add('fading');
        await new Promise((r) => setTimeout(r, 150));
      }
      this.host.innerHTML = '';
      const root = document.createElement('div');
      root.className = 'scene scene-' + id;
      this.host.appendChild(root);
      const Cls = this.classes.get(id);
      this.cur = new Cls(this.app); this.curId = id; this.curParams = params || {};
      await this.cur.enter(root, this.curParams);
      this.host.classList.remove('fading');
      this.fns.forEach((fn) => fn(id));
    } catch (e) {
      this._crash(e);
    } finally {
      this.busy = false;
      this.app.input.setEnabled(true);
      if (this.queued) { const q = this.queued; this.queued = null; this._switch(q[0], q[1], q[2]); }
    }
  }
  _crash(e) {
    log.error('SCENE_CRASH', String(e && e.stack || e));
    this.host.classList.remove('fading');
    if (this.curId === 'error') return;
    const from = this.curId || '';
    this.cur = null;
    setTimeout(() => this.replace('error', { code: (e && e.code) || 'SCENE_CRASH', from }), 0);
  }
  _safe(fn) { try { fn(); } catch (e) { this._crash(e); } }
  update(dt) { if (this.cur && !this.busy) this._safe(() => this.cur.update(dt)); }
  render() { if (this.cur && !this.busy) this._safe(() => this.cur.render()); }
  input(e) { if (this.cur && !this.busy) this._safe(() => this.cur.onInput(e)); }
  pause() { if (this.cur) this._safe(() => this.cur.pause()); }
  resume() { if (this.cur) this._safe(() => this.cur.resume()); }
}
