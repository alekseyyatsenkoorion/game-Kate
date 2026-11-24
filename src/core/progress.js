// Progress — единственный модуль, который трогает localStorage (contracts.md §4).
import { log } from './log.js';

const P = 's6:v2:';
const K = { progress: P + 'progress', settings: P + 'settings', draws: P + 'draws', run: P + 'run', corrupt: P + 'progress.corrupt' };
const LEGACY = 'sixth-sense-save-v1';

function clone(o) { return JSON.parse(JSON.stringify(o)); }

export class Progress {
  constructor(balance, characters) {
    this.balance = balance;
    this.rivalIds = characters.filter((c) => c.role === 'rival').map((c) => c.id);
    this.persistent = true; this.recovered = false;
    this.mem = {};
    this.fns = new Set();
    try { const k = '__s6test'; localStorage.setItem(k, '1'); localStorage.removeItem(k); }
    catch (e) { this.persistent = false; log.warn('STORAGE_OFF', 'localStorage недоступен'); }
    this.data = this._loadProgress();
    this.sets = Object.assign({ music: true, sfx: true, voice: true, test: false }, this._read(K.settings) || {});
  }
  defaults() {
    const rivals = {};
    this.rivalIds.forEach((id) => { rivals[id] = { points: 0, eliminatedAfter: null }; });
    return { schema: 2, episodes: {}, power: this.balance.startPower, totalPoints: 0, rivals,
      guest: { enabled: false, points: 0 }, case: { clues: [], links: [] }, skeptic: { pendingTraps: 0 },
      achievements: [], openedOn: {} };
  }
  _raw(key) { return this.persistent ? localStorage.getItem(key) : (this.mem[key] ?? null); }
  _write(key, val) {
    const s = JSON.stringify(val);
    if (this.persistent) {
      try { localStorage.setItem(key, s); return; }
      catch (e) { this.persistent = false; log.warn('STORAGE_FULL', 'Запись не удалась, работаем в памяти'); }
    }
    this.mem[key] = s;
  }
  _read(key) { const s = this._raw(key); if (s == null) return null; try { return JSON.parse(s); } catch (e) { return undefined; } }
  _loadProgress() {
    const raw = this._raw(K.progress);
    if (raw == null) {
      const legacy = this._raw(LEGACY);
      if (legacy) return this._migrateLegacy(legacy);
      return this.defaults();
    }
    let d;
    try { d = JSON.parse(raw); } catch (e) { d = null; }
    if (!d || typeof d !== 'object' || !d.schema) {
      try { if (this.persistent) localStorage.setItem(K.corrupt, raw); } catch (e2) {}
      this.recovered = true; log.warn('PROGRESS_CORRUPT', 'Сохранение повреждено, начато заново');
      return this.defaults();
    }
    if (d.schema > 2) { log.warn('PROGRESS_NEWER', 'Сохранение новее игры'); }
    return Object.assign(this.defaults(), d);
  }
  _migrateLegacy(raw) {
    const d = this.defaults();
    try {
      const old = JSON.parse(raw);
      Object.keys(old.done || {}).forEach((n) => {
        const e = old.done[n];
        d.episodes[n] = { firstDate: e.date, stars: e.stars || 0, points: 0, bestPoints: 0, attempts: 1 };
        d.openedOn[n] = e.date;
      });
      if (typeof old.power === 'number') d.power = old.power;
      this.sets_legacyTest = !!old.test;
    } catch (e) { log.warn('LEGACY_BAD', 'Старое сохранение не прочиталось'); }
    this._write(K.progress, d);
    return d;
  }
  get() { return this.data; }
  update(mutator) {
    const draft = clone(this.data);
    mutator(draft);
    if (typeof draft.power !== 'number' || draft.power < 0 || !draft.episodes) { log.error('PROGRESS_INVALID', 'Отклонено'); return; }
    this.data = draft;
    this._write(K.progress, draft);
    this.fns.forEach((fn) => fn(this.data));
  }
  settings() { return this.sets; }
  setSettings(patch) { this.sets = Object.assign({}, this.sets, patch); this._write(K.settings, this.sets); }
  run() { const r = this._read(K.run); return r || null; }
  saveRun(r) { this._write(K.run, r); }
  clearRun() { if (this.persistent) { try { localStorage.removeItem(K.run); } catch (e) {} } delete this.mem[K.run]; }
  draws() { return this._read(K.draws) || {}; }
  saveDraws(d) { this._write(K.draws, d); }
  recordEpisode(n, score, rivals, clues, dateKey) {
    this.update((d) => {
      const prev = d.episodes[n];
      if (!prev) {
        d.episodes[n] = { firstDate: dateKey, stars: score.stars, points: score.points, bestPoints: score.points, attempts: 1 };
        d.power += score.powerGain;
        d.totalPoints += score.points;
        (clues || []).forEach((c) => { if (d.case.clues.indexOf(c) < 0) d.case.clues.push(c); });
        if (rivals) {
          rivals.table.forEach((row) => { if (d.rivals[row.id]) d.rivals[row.id].points = row.points; });
          if (rivals.eliminated) d.rivals[rivals.eliminated].eliminatedAfter = n;
          d.skeptic.pendingTraps = rivals.skepticTraps;
        }
      } else {
        prev.attempts += 1;
        prev.stars = Math.max(prev.stars, score.stars);
        prev.bestPoints = Math.max(prev.bestPoints, score.points);
      }
    });
  }
  reset() {
    const test = this.sets.test;
    this.data = this.defaults();
    this._write(K.progress, this.data);
    this._write(K.draws, {});
    this.clearRun();
    this.setSettings({ test });
    this.fns.forEach((fn) => fn(this.data));
  }
  exportCode() { return btoa(unescape(encodeURIComponent(JSON.stringify({ p: this.data, d: this.draws() })))); }
  importCode(code) {
    try {
      const o = JSON.parse(decodeURIComponent(escape(atob(code.trim()))));
      if (!o.p || o.p.schema !== 2) return false;
      this.data = Object.assign(this.defaults(), o.p);
      this._write(K.progress, this.data); this.saveDraws(o.d || {});
      return true;
    } catch (e) { return false; }
  }
  subscribe(fn) { this.fns.add(fn); return () => this.fns.delete(fn); }
}
