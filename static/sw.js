self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open("wellness-v1").then((cache) =>
      cache.addAll([
        "/",
        "/dashboard",
        "/static/style.css",
        "/static/manifest.webmanifest",
        "/static/icon.svg"
      ])
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== "wellness-v1").map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) =>
      cached ||
      fetch(event.request).then((response) => {
        const responseClone = response.clone();
        if (event.request.method === "GET" && response.ok) {
          caches.open("wellness-v1").then((cache) => cache.put(event.request, responseClone));
        }
        return response;
      }).catch(() => cached)
    )
  );
});
