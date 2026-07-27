const CACHE_NAME = 'yatirim-takip-v1';
const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/vendor/lightweight-charts.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (key) { return key !== CACHE_NAME; }).map(function (key) { return caches.delete(key); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function (event) {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;

  // API çağrıları: her zaman güncel veri - ağ öncelikli, çevrimdışıysa son bilinen yanıt
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request)
        .then(function (response) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(function (cache) { cache.put(event.request, clone); });
          return response;
        })
        .catch(function () { return caches.match(event.request); })
    );
    return;
  }

  // Statik dosyalar: önbellek öncelikli, arka planda güncelle
  event.respondWith(
    caches.match(event.request).then(function (cached) {
      const networkFetch = fetch(event.request)
        .then(function (response) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(function (cache) { cache.put(event.request, clone); });
          return response;
        })
        .catch(function () { return cached; });
      return cached || networkFetch;
    })
  );
});
