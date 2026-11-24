// Service worker: всё из precache.json — в кэш, отдача из кэша (работа без сети).
// Строку VERSION переписывает tools/build-precache.js при каждой выкладке.
const VERSION = '1.1.0';
const CACHE = 's6-' + VERSION;

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const res = await fetch('precache.json', { cache: 'no-store' });
    const list = (await res.json()).files;
    const cache = await caches.open(CACHE);
    await cache.addAll(list.map((f) => new Request(f, { cache: 'no-store' })));
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.indexOf('s6-') === 0 && k !== CACHE).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

self.addEventListener('message', (e) => {
  if (!e.data) return;
  if (e.data.type === 'skipWaiting') self.skipWaiting();
  if (e.data.type === 'version' && e.source) e.source.postMessage({ version: VERSION });
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const url = new URL(req.url); url.search = '';
    const hit = await cache.match(url.href) || (req.mode === 'navigate' ? await cache.match(new URL('./', self.location).href) || await cache.match(new URL('index.html', self.location).href) : null);
    if (hit) return hit;
    try { return await fetch(req); } catch (err) { return new Response('', { status: 504 }); }
  })());
});
