// AssetLoader — картинки с правилом подмены (contracts.md §6):
// assets/gpt/<id>.webp (если есть в index.json) → assets/art/<id>.svg → рисовальщик из art-fallback.
import { log } from './log.js';
import { fallbackDrawer } from './art-fallback.js';

export class AssetLoader {
  constructor() { this.gpt = new Set(); this.cache = new Map(); }
  async init() {
    try {
      const r = await fetch('assets/gpt/index.json', { cache: 'no-cache' });
      if (r.ok) { const j = await r.json(); (j.images || []).forEach((id) => this.gpt.add(id)); }
    } catch (e) { /* нет индекса — значит картинок нет */ }
  }
  has(id) { return this.gpt.has(id); }
  url(id) {
    if (this.gpt.has(id)) return 'assets/gpt/' + id + '.webp';
    return 'assets/art/' + id + '.svg';
  }
  image(id) {
    if (this.cache.has(id)) return this.cache.get(id);
    const tryLoad = (src, kind) => new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve({ kind, img, url: src, w: img.naturalWidth || 256, h: img.naturalHeight || 256 });
      img.onerror = reject;
      img.src = src;
    });
    const p = (this.gpt.has(id) ? tryLoad('assets/gpt/' + id + '.webp', 'bitmap') : Promise.reject())
      .catch(() => tryLoad('assets/art/' + id + '.svg', 'svg'))
      .catch(() => { log.warn('ASSET_' + id, 'Нет картинки ' + id + ', рисует код'); return { kind: 'drawn', draw: fallbackDrawer(id), w: 256, h: 256 }; });
    this.cache.set(id, p);
    return p;
  }
  preload(ids) { return Promise.all(ids.map((id) => this.image(id))).then(() => {}); }
}
