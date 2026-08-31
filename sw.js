/* Service Worker fuer den Stundenplan.
 *
 * Wichtig: data/*.json werden STRIKT network-first ausgeliefert, der Cache
 * dient nur als Offline-Fallback. Ein cache-first Verhalten wuerde veraltete
 * Stundenplaene anzeigen, also genau den Fehler, den dieses Projekt vermeiden
 * soll. Die App-Shell (HTML, Manifest, Icons) darf dagegen cache-first sein.
 */
const VERSION = 'v1';
const SHELL_CACHE = 'shell-' + VERSION;
const DATA_CACHE  = 'data-' + VERSION;

const SHELL_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(c => c.addAll(SHELL_ASSETS))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== SHELL_CACHE && k !== DATA_CACHE)
            .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;   // Fonts o.ae. nicht anfassen

  // Plandaten: immer zuerst aus dem Netz, Cache nur wenn offline.
  if (url.pathname.includes('/data/') && url.pathname.endsWith('.json')) {
    event.respondWith(
      fetch(req)
        .then(res => {
          const copy = res.clone();
          caches.open(DATA_CACHE).then(c => c.put(req, copy));
          return res;
        })
        .catch(() => caches.match(req).then(hit => hit || Response.error()))
    );
    return;
  }

  // App-Shell: aus dem Cache, im Hintergrund auffrischen.
  event.respondWith(
    caches.match(req).then(hit => {
      const netz = fetch(req)
        .then(res => {
          const copy = res.clone();
          caches.open(SHELL_CACHE).then(c => c.put(req, copy));
          return res;
        })
        .catch(() => hit);
      return hit || netz;
    })
  );
});
