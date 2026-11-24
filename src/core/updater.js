// Updater — регистрация service worker и обновление без переустановки (contracts.md §10).
import { log } from './log.js';

export class Updater {
  constructor() { this.version = '—'; this.fns = new Set(); this.waiting = null; this.ready = null; }
  async register() {
    if (!('serviceWorker' in navigator)) { log.warn('SW_OFF', 'Service worker не поддерживается'); return; }
    try {
      const reg = await navigator.serviceWorker.register('sw.js');
      const track = (w) => {
        if (!w) return;
        w.addEventListener('statechange', () => {
          if (w.state === 'installed' && navigator.serviceWorker.controller) { this.waiting = w; this._ready(); }
        });
      };
      if (reg.waiting && navigator.serviceWorker.controller) { this.waiting = reg.waiting; this._ready(); }
      reg.addEventListener('updatefound', () => track(reg.installing));
      navigator.serviceWorker.addEventListener('controllerchange', () => { if (this.applying) location.reload(); });
      navigator.serviceWorker.addEventListener('message', (e) => { if (e.data && e.data.version) this.version = e.data.version; });
      const ctrl = navigator.serviceWorker.controller;
      if (ctrl) ctrl.postMessage({ type: 'version' });
      try { await reg.update(); } catch (e) { /* без сети — остаёмся на текущей */ }
    } catch (e) { log.warn('SW_FAIL', String(e)); }
  }
  _ready() { this.ready = true; this.fns.forEach((fn) => fn()); }
  onReady(fn) { this.fns.add(fn); if (this.ready) fn(); return () => this.fns.delete(fn); }
  applyNow(sceneId) {
    if (!this.waiting || (sceneId !== 'title' && sceneId !== 'season')) return false;
    this.applying = true;
    this.waiting.postMessage({ type: 'skipWaiting' });
    return true;
  }
}
