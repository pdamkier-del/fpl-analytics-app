/* Cache only the connection-error page, scoped to this preview installation. */
'use strict';
const cachePrefix = 'fpl-preview-shell:' + self.registration.scope + ':';
const cacheName = cachePrefix + 'c8f00da1d779c900';
const offline = new URL('preview-offline.html', self.registration.scope).href;

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(cacheName);
    await cache.add(new Request(offline, { cache: 'reload' }));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const names = await caches.keys();
    await Promise.all(names.filter(name => name.startsWith(cachePrefix) && name !== cacheName)
      .map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || request.mode !== 'navigate' ||
      !request.url.startsWith(self.registration.scope)) return;
  event.respondWith(fetch(request, { cache: 'no-store' }).catch(async () => {
    const cache = await caches.open(cacheName);
    return await cache.match(offline) || Response.error();
  }));
});
