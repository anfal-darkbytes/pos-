/**
 * Pulse POS — Production Progressive Web App Service Worker
 * Version: 2.0.0
 * Features: Shell caching, Stale-While-Revalidate assets, Network-First navigation with offline fallback,
 * and Background Sync coordination.
 */

const CACHE_NAME = 'pulse-pos-v3';
const OFFLINE_URL = '/offline';

const PRECACHE_ASSETS = [
  '/',
  '/pos',
  OFFLINE_URL,
  '/static/manifest.json',
  '/static/css/app.css',
  '/static/favicon.svg',
  '/static/favicon.ico',
  '/static/images/pulse-logo-icon.svg',
  '/static/images/pulse-logo-horizontal.svg',
  '/static/images/icons/icon-72.png',
  '/static/images/icons/icon-96.png',
  '/static/images/icons/icon-128.png',
  '/static/images/icons/icon-144.png',
  '/static/images/icons/icon-152.png',
  '/static/images/icons/icon-192.png',
  '/static/images/icons/icon-384.png',
  '/static/images/icons/icon-512.png',
  '/static/js/offline/db.js',
  '/static/js/offline/repository.js',
  '/static/js/offline/sync.js',
  '/static/js/pos.js',
  '/static/js/pwa.js',
  'https://cdn.tailwindcss.com?plugins=forms,typography',
  'https://unpkg.com/lucide@latest/dist/umd/lucide.min.js',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js'
];

// Install: pre-cache application shell and offline fallback with resilient cross-origin no-cors handling
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async (cache) => {
      for (const url of PRECACHE_ASSETS) {
        try {
          const isCrossDomain = url.startsWith('http://') || url.startsWith('https://');
          const request = isCrossDomain
            ? new Request(url, { mode: 'no-cors' })
            : new Request(url, { mode: 'cors', cache: 'reload' });
          const response = await fetch(request);
          if (response.status === 200 || response.type === 'opaque') {
            await cache.put(request, response);
          }
        } catch (err) {
          console.warn('[Pulse POS SW] Precache skipped for:', url, err);
        }
      }
    }).then(() => self.skipWaiting())
  );
});

// Activate: clean up older cache versions and take immediate control
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log('[Pulse POS SW] Purging deprecated cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch: Strategy based on request type
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Skip non-GET requests (mutations like /api/checkout and /api/sync/orders always go over the wire)
  if (request.method !== 'GET') {
    return;
  }

  // 2. Navigation requests (HTML document views): Network-First with Offline Fallback
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
          }
          return networkResponse;
        })
        .catch(async () => {
          // If offline, check exact URL match in cache first
          const cachedResponse = await caches.match(request);
          if (cachedResponse) {
            return cachedResponse;
          }
          // If requesting /pos, try cached /pos
          if (url.pathname === '/pos' || url.pathname === '/') {
            const cachedPos = await caches.match('/pos');
            if (cachedPos) return cachedPos;
          }
          // Fallback to offline holding page
          const offlinePage = await caches.match(OFFLINE_URL);
          return offlinePage || new Response('Offline - Pulse POS', {
            headers: { 'Content-Type': 'text/html; charset=utf-8' }
          });
        })
    );
    return;
  }

  // 3. Static Assets (CSS, JS, Fonts, Images): Stale-While-Revalidate
  const isStatic =
    url.pathname.startsWith('/static/') ||
    url.hostname.includes('cdn') ||
    url.hostname.includes('unpkg') ||
    url.hostname.includes('fonts.googleapis') ||
    url.hostname.includes('fonts.gstatic');

  if (isStatic) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        const fetchPromise = fetch(request)
          .then((networkResponse) => {
            if (networkResponse && networkResponse.status === 200) {
              const responseClone = networkResponse.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
            }
            return networkResponse;
          })
          .catch(() => cachedResponse);

        return cachedResponse || fetchPromise;
      })
    );
    return;
  }

  // 4. API endpoints: Network-first with Cache fallback for master data
  if (url.pathname.startsWith('/api/sync/bootstrap') || url.pathname.startsWith('/api/general-settings')) {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
          }
          return networkResponse;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Default: Network with Cache fallback
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// 5. Background Sync Event (where supported by browser)
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-pulsepos-orders') {
    console.log('[Pulse POS SW] Background Sync triggered: sync-pulsepos-orders');
    event.waitUntil(
      self.clients.matchAll({ type: 'window' }).then((clients) => {
        clients.forEach((client) => {
          client.postMessage({ type: 'TRIGGER_BACKGROUND_SYNC' });
        });
      })
    );
  }
});

// 6. Messages from clients
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
