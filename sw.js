// Only the public app shell is cached. Accounts, messages and attachments are network-only.
const CACHE = 'stillroom-shell-63eec3f6f65107ba';
const ASSETS = ['/', '/index.html', '/app.js', '/styles.css', '/favicon.svg', '/manifest.webmanifest', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/apple-touch-icon.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith('stillroom-shell-') && key !== CACHE).map(key => caches.delete(key)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin || !ASSETS.includes(url.pathname)) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(url.pathname, copy)));
    }
    return response;
  }).catch(() => caches.match(url.pathname).then(cached => cached || new Response('Stillroom is offline. Start your server and reconnect.', {status: 503, headers: {'Content-Type': 'text/plain'}}))));
});
