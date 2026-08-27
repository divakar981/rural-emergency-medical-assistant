const CACHE='rural-med-ai-v2';
const ASSETS=['/','/static/style.css','/static/app.js','/static/manifest.json','/static/icon.svg'];
self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS))));
self.addEventListener('fetch',e=>{e.respondWith(fetch(e.request).catch(()=>caches.match(e.request).then(r=>r||caches.match('/'))));});
