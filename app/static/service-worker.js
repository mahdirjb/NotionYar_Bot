const SHELL_CACHE = "notionyar-shell-v6.17.1";
const API_CACHE = "notionyar-api-persistent-v1";
const DB_NAME = "notionyar-offline";
const DB_VERSION = 1;
const QUEUE_STORE = "mutation-queue";

const SHELL_ASSETS = [
  "/",
  "/manifest.webmanifest",
  "/static/app.css?v=6.17.1",
  "/static/vendor/lucide.min.js?v=1.72.0",
  "/static/app.js?v=6.17.1",
  "/static/icon.svg?v=5.0.2",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    const apiCache = await caches.open(API_CACHE);
    const legacyApiCaches = keys.filter((key) => key.startsWith("notionyar-api-") && key !== API_CACHE);

    for (const cacheName of legacyApiCaches) {
      const legacyCache = await caches.open(cacheName);
      const requests = await legacyCache.keys();
      for (const request of requests) {
        if (await apiCache.match(request, { ignoreVary: true })) continue;
        const response = await legacyCache.match(request, { ignoreVary: true });
        if (response) await apiCache.put(request, response);
      }
    }

    await Promise.all(keys
      .filter((key) => (key.startsWith("notionyar-shell-") && key !== SHELL_CACHE) || legacyApiCaches.includes(key))
      .map((key) => caches.delete(key)));
    await self.clients.claim();
    await broadcastQueueCount();
  })());
});

function openQueueDb() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(QUEUE_STORE)) {
        db.createObjectStore(QUEUE_STORE, { keyPath: "id", autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withQueueStore(mode, callback) {
  const db = await openQueueDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(QUEUE_STORE, mode);
    const store = transaction.objectStore(QUEUE_STORE);
    const result = callback(store);
    transaction.oncomplete = () => {
      db.close();
      resolve(result);
    };
    transaction.onerror = () => {
      db.close();
      reject(transaction.error);
    };
  });
}

async function queueMutation(request) {
  const headers = {};
  request.headers.forEach((value, key) => {
    if (!["content-length", "host"].includes(key.toLowerCase())) headers[key] = value;
  });
  const item = {
    url: request.url,
    method: request.method,
    headers,
    body: await request.clone().text(),
    createdAt: Date.now(),
  };
  await withQueueStore("readwrite", (store) => store.add(item));
  await broadcastQueueCount();

  if (self.registration.sync) {
    try {
      await self.registration.sync.register("notionyar-sync");
    } catch (_) {}
  }
}

async function getQueuedItems() {
  const db = await openQueueDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(QUEUE_STORE, "readonly");
    const request = transaction.objectStore(QUEUE_STORE).getAll();
    request.onsuccess = () => {
      db.close();
      resolve(request.result || []);
    };
    request.onerror = () => {
      db.close();
      reject(request.error);
    };
  });
}

async function deleteQueuedItem(id) {
  const db = await openQueueDb();
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(QUEUE_STORE, "readwrite");
    transaction.objectStore(QUEUE_STORE).delete(id);
    transaction.oncomplete = () => {
      db.close();
      resolve();
    };
    transaction.onerror = () => {
      db.close();
      reject(transaction.error);
    };
  });
}

async function clearLocalData() {
  const db = await openQueueDb();
  await new Promise((resolve, reject) => {
    const transaction = db.transaction(QUEUE_STORE, "readwrite");
    transaction.objectStore(QUEUE_STORE).clear();
    transaction.oncomplete = resolve;
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
  await caches.delete(API_CACHE);
  await broadcastQueueCount();
}

async function notifyClients(message) {
  const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  clients.forEach((client) => client.postMessage(message));
}

async function broadcastQueueCount() {
  const items = await getQueuedItems().catch(() => []);
  await notifyClients({ type: "QUEUE_STATUS", count: items.length });
}

async function flushQueue() {
  const items = await getQueuedItems();
  let synced = 0;
  let failedStatus = null;

  if (items.length) await notifyClients({ type: "SYNC_STARTED", count: items.length });

  for (const item of items) {
    try {
      const response = await fetch(item.url, {
        method: item.method,
        headers: item.headers,
        body: item.body || undefined,
        credentials: "include",
      });

      if (response.status === 401 || response.status === 403) {
        await notifyClients({ type: "SYNC_AUTH_REQUIRED" });
        break;
      }
      if (!response.ok) {
        failedStatus = response.status;
        break;
      }

      await deleteQueuedItem(item.id);
      synced += 1;
    } catch (_) {
      break;
    }
  }

  await broadcastQueueCount();
  if (synced > 0) await notifyClients({ type: "SYNC_COMPLETE", count: synced });
  if (failedStatus) await notifyClients({ type: "SYNC_FAILED", status: failedStatus });
}

async function handleMutation(request) {
  try {
    const response = await fetch(request.clone());
    const transientStatuses = [408, 425, 429, 502, 503, 504, 520, 521, 522, 523, 524];
    if (transientStatuses.includes(response.status)) {
      await queueMutation(request);
      await notifyClients({ type: "NETWORK_UNAVAILABLE" });
      return new Response(JSON.stringify({ success: true, queued: true }), {
        status: 202,
        headers: {
          "Content-Type": "application/json",
          "X-Offline-Queued": "1",
        },
      });
    }
    return response;
  } catch (_) {
    await queueMutation(request);
    await notifyClients({ type: "NETWORK_UNAVAILABLE" });
    return new Response(JSON.stringify({ success: true, queued: true }), {
      status: 202,
      headers: {
        "Content-Type": "application/json",
        "X-Offline-Queued": "1",
      },
    });
  }
}

function withOfflineCacheHeader(response) {
  const headers = new Headers(response.headers);
  headers.set("X-Offline-Cache", "1");
  return new Response(response.clone().body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

async function refreshApiCache(request, cache) {
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put(request, response.clone());
    await notifyClients({ type: "NETWORK_RESTORED" });
    return response;
  } catch (_) {
    await notifyClients({ type: "NETWORK_UNAVAILABLE" });
    return null;
  }
}

async function handleApiGet(request, event) {
  const cache = await caches.open(API_CACHE);
  if (request.headers.get("X-NotionYar-Network-Only") === "1") {
    const response = await refreshApiCache(request, cache);
    if (response) return response;
  }
  const cached = await cache.match(request, { ignoreVary: true });
  if (cached) {
    event.waitUntil(refreshApiCache(request, cache));
    return withOfflineCacheHeader(cached);
  }

  const response = await refreshApiCache(request, cache);
  if (response) return response;
  return new Response(JSON.stringify({ detail: "این اطلاعات هنوز برای استفاده آفلاین ذخیره نشده‌اند." }), {
    status: 503,
    headers: { "Content-Type": "application/json" },
  });
}

async function handleNavigation(request, event) {
  const cache = await caches.open(SHELL_CACHE);
  const cached = await cache.match(request, { ignoreSearch: true }) || await cache.match("/");
  if (cached) {
    event.waitUntil((async () => {
      try {
        const response = await fetch(request);
        if (response.ok) await cache.put("/", response.clone());
      } catch (_) {}
    })());
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response.ok) await cache.put("/", response.clone());
    return response;
  } catch (_) {
    return new Response("برنامه هنوز برای استفاده آفلاین آماده نشده است.", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  const isApi = url.pathname.startsWith("/api/");
  const isAuth = url.pathname.startsWith("/api/auth/");
  const isMutation = ["POST", "PUT", "PATCH", "DELETE"].includes(request.method);

  if (isApi && isMutation && !isAuth) {
    event.respondWith(handleMutation(request));
    return;
  }
  if (isApi && request.method === "GET") {
    event.respondWith(handleApiGet(request, event));
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(handleNavigation(request, event));
    return;
  }
  if (request.method === "GET") {
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
  }
});

self.addEventListener("sync", (event) => {
  if (event.tag === "notionyar-sync") event.waitUntil(flushQueue());
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "FLUSH_QUEUE") event.waitUntil(flushQueue());
  if (event.data?.type === "GET_QUEUE_STATUS") event.waitUntil(broadcastQueueCount());
  if (event.data?.type === "CLEAR_LOCAL_DATA") event.waitUntil(clearLocalData());
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});
