/* FPL mobile shell only. API and forecasts are always network-only. */
const CACHE='fpl-mobile-shell-20261009-v1';
const SHELL=['./mobile.html','./manifest.webmanifest','./icons/fpl-icon.svg'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(SHELL)));self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('fpl-mobile-shell-')&&k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim()});
self.addEventListener('fetch',event=>{const u=new URL(event.request.url);if(event.request.method!=='GET'||u.origin!==location.origin||u.pathname.includes('/api/')||/\/(data\.js|role-data\.js|expert-lineups\.js)$/.test(u.pathname))return;if(event.request.mode==='navigate'){event.respondWith(fetch(event.request).catch(()=>caches.match('./mobile.html')));return}if(SHELL.some(x=>u.pathname.endsWith(x.replace('./','')))){event.respondWith(fetch(event.request).catch(()=>caches.match(event.request)))}});
