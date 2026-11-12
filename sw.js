// Only the public app shell is cached. Accounts, messages and attachments are network-only.
const CACHE = 'stillroom-shell-5723b149abf1b6a7';
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
  event.respondWith(fetch(event.request, {cache: 'no-cache'}).then(response => {
    if (response.ok) {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(url.pathname, copy)));
    }
    return response;
  }).catch(() => caches.match(url.pathname).then(cached => cached || new Response('Stillroom is offline. Start your server and reconnect.', {status: 503, headers: {'Content-Type': 'text/plain'}}))));
});

self.addEventListener('push', event => {
  event.waitUntil((async () => {
    try {
      const payload = event.data?.json();
      if (!payload || typeof payload.event !== 'string' || payload.event.length > 100) return;
      // Recheck permission on the server at display time: queued notifications cannot bypass quiet mode, mutes or logout.
      const response = await fetch('/api/push/check?token=' + encodeURIComponent(payload.event), {credentials: 'include', cache: 'no-store'});
      if (!response.ok) return;
      const notification = await response.json();
      if (!notification.allowed) return;
      await self.registration.showNotification(notification.title, {body: notification.body, icon: '/icons/icon-192.png', badge: '/icons/icon-192.png', tag: notification.tag, data: {peer: notification.peer}, renotify: true});
    } catch (_) { /* Fail closed when current account preferences cannot be checked. */ }
  })());
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const peer = event.notification.data?.peer;
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({type: 'window', includeUncontrolled: true});
    const existing = windows.find(client => new URL(client.url).origin === self.location.origin);
    if (existing) {
      existing.postMessage({type: 'open-chat', peer});
      return existing.focus();
    }
    return self.clients.openWindow('/' + (Number.isSafeInteger(peer) && peer > 0 ? '?chat=' + peer : '') + '#messages');
  })());
});
