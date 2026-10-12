'use strict';

const CACHE_PREFIX = 'dj-kuami-public-';
const CACHE_NAME = CACHE_PREFIX + 'v1';
const OFFLINE_URL = '/static/offline.html';
const PRECACHE_URLS = [
  OFFLINE_URL,
  '/static/css/main.css',
  '/static/js/main.js',
  '/static/js/pwa.js',
  '/static/images/pwa-icon-192.png',
  '/static/images/pwa-icon-512.png'
];

function isPrivatePath(pathname) {
  return /^\/(portal|dashboard|admin|accounts|bookings|chat)(\/|$)/.test(pathname);
}

function isPublicPage(pathname) {
  return pathname === '/' ||
    pathname === '/about/' ||
    /^\/music\/(mixes|tracks|categories)(\/|$)/.test(pathname) ||
    /^\/(videos|gallery)(\/|$)/.test(pathname);
}

function canCache(response) {
  if (!response || !response.ok || response.type !== 'basic') return false;
  const directives = response.headers.get('Cache-Control') || '';
  return !/(private|no-store)/i.test(directives);
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (
    request.method !== 'GET' ||
    url.origin !== self.location.origin ||
    isPrivatePath(url.pathname)
  ) return;

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.open(CACHE_NAME).then((cache) =>
        cache.match(request).then((cached) => {
          if (cached) return cached;
          return fetch(request).then((response) => {
            if (canCache(response)) cache.put(request, response.clone());
            return response;
          });
        })
      )
    );
    return;
  }

  if (!isPublicPage(url.pathname) || url.search) return;
  event.respondWith((async () => {
    try {
      const response = await fetch(request);
      if (canCache(response) && response.headers.get('Content-Type')?.includes('text/html')) {
        await caches.open(CACHE_NAME).then((cache) => cache.put(request, response.clone()));
      }
      return response;
    } catch (error) {
      return (await caches.match(request)) || caches.match(OFFLINE_URL);
    }
  })());
});
