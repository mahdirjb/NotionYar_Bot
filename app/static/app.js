// app/static/app.js
// NotionYar Telegram Mini App v6.11.0

(function () {
  const tg = window.Telegram?.WebApp;
  const nativeFetch = window.fetch.bind(window);
  const OFFLINE_DB_NAME = "notionyar-offline";
  const OFFLINE_DB_VERSION = 1;
  const OFFLINE_QUEUE_STORE = "mutation-queue";
  const OFFLINE_CACHE_DB_NAME = "notionyar-offline-cache";
  const OFFLINE_CACHE_DB_VERSION = 1;
  const OFFLINE_CACHE_STORE = "api-responses";
  let offlineMutationQueued = false;
  let pendingQueueCount = 0;
  let originReachable = navigator.onLine;
  let currentReportPeriod = "7d";
  let currentReportData = null;
  let lifeHistorySearchTimer = null;
  const dataCache = {
    lifeHistory: null,
    lifeRadar: null,
    habits: new Map(),
    spiritual: new Map(),
    quranHistory: null,
    habitAnalytics: new Map(),
    reports: new Map(),
  };

  function invalidateDataCache(...keys) {
    keys.forEach((key) => {
      if (dataCache[key] instanceof Map) dataCache[key].clear();
      else dataCache[key] = null;
    });
  }

  const UI_ICON_MAP = {
    "#btnExportReports": "download",
    "#btnRefreshReports": "refresh-cw",
  };
  let iconObserver = null;
  let iconRefreshQueued = false;

  function installMappedIcons() {
    Object.entries(UI_ICON_MAP).forEach(([selector, iconName]) => {
      document.querySelectorAll(selector).forEach((element) => {
        if (element.querySelector(":scope > .ui-icon")) return;
        const icon = document.createElement("i");
        icon.className = "ui-icon";
        icon.setAttribute("data-lucide", iconName);
        element.prepend(icon);
      });
    });
  }

  function refreshIconography() {
    if (iconObserver) iconObserver.disconnect();
    installMappedIcons();
    if (window.lucide) {
      window.lucide.createIcons({ attrs: { "stroke-width": 1.8 } });
    }
    if (iconObserver) {
      iconObserver.observe(document.body, { childList: true, subtree: true, characterData: true });
    }
  }

  function setupIconography() {
    refreshIconography();
    iconObserver = new MutationObserver(() => {
      if (iconRefreshQueued) return;
      iconRefreshQueued = true;
      requestAnimationFrame(() => {
        iconRefreshQueued = false;
        refreshIconography();
      });
    });
    iconObserver.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  if (tg) {
    tg.ready();
    tg.expand();
  }

  function openOfflineDb() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error("IndexedDB is not available"));
        return;
      }
      const request = indexedDB.open(OFFLINE_DB_NAME, OFFLINE_DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(OFFLINE_QUEUE_STORE)) {
          db.createObjectStore(OFFLINE_QUEUE_STORE, { keyPath: "id", autoIncrement: true });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function getOfflineQueueItems() {
    const db = await openOfflineDb();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction(OFFLINE_QUEUE_STORE, "readonly");
      const request = transaction.objectStore(OFFLINE_QUEUE_STORE).getAll();
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

  async function getOfflineQueueCount() {
    try {
      return (await getOfflineQueueItems()).length;
    } catch (_) {
      return pendingQueueCount;
    }
  }

  function openOfflineCacheDb() {
    return new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        reject(new Error("IndexedDB is not available"));
        return;
      }
      const request = indexedDB.open(OFFLINE_CACHE_DB_NAME, OFFLINE_CACHE_DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(OFFLINE_CACHE_STORE)) {
          db.createObjectStore(OFFLINE_CACHE_STORE, { keyPath: "url" });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function cacheOfflineApiResponse(request, response) {
    if (!response?.ok || !request?.url) return;
    try {
      const body = await response.clone().text();
      const headers = {};
      response.headers.forEach((value, key) => { headers[key] = value; });
      const db = await openOfflineCacheDb();
      await new Promise((resolve, reject) => {
        const transaction = db.transaction(OFFLINE_CACHE_STORE, "readwrite");
        transaction.objectStore(OFFLINE_CACHE_STORE).put({
          url: request.url,
          body,
          status: response.status,
          statusText: response.statusText,
          headers,
          updatedAt: Date.now(),
        });
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
      });
      db.close();
    } catch (error) {
      console.warn("Could not cache API response for offline use", error);
    }
  }

  async function getOfflineApiResponse(url) {
    try {
      const db = await openOfflineCacheDb();
      const item = await new Promise((resolve, reject) => {
        const transaction = db.transaction(OFFLINE_CACHE_STORE, "readonly");
        const request = transaction.objectStore(OFFLINE_CACHE_STORE).get(url);
        request.onsuccess = () => resolve(request.result || null);
        request.onerror = () => reject(request.error);
      });
      db.close();
      if (!item) return null;
      return new Response(item.body, {
        status: item.status || 200,
        statusText: item.statusText || "OK",
        headers: item.headers || { "Content-Type": "application/json" },
      });
    } catch (_) {
      return null;
    }
  }

  async function clearOfflineApiCache() {
    try {
      const db = await openOfflineCacheDb();
      await new Promise((resolve, reject) => {
        const transaction = db.transaction(OFFLINE_CACHE_STORE, "readwrite");
        transaction.objectStore(OFFLINE_CACHE_STORE).clear();
        transaction.oncomplete = resolve;
        transaction.onerror = () => reject(transaction.error);
      });
      db.close();
    } catch (_) {}
  }

  async function enqueueOfflineMutation(input, init = {}) {
    const request = new Request(input, init);
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
    const db = await openOfflineDb();
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(OFFLINE_QUEUE_STORE, "readwrite");
      transaction.objectStore(OFFLINE_QUEUE_STORE).add(item);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    db.close();
    const count = await getOfflineQueueCount();
    updateSyncStatus({ online: false, count });
    return new Response(JSON.stringify({ success: true, queued: true }), {
      status: 202,
      headers: { "Content-Type": "application/json", "X-Offline-Queued": "1" },
    });
  }

  async function deleteOfflineQueueItem(id) {
    const db = await openOfflineDb();
    await new Promise((resolve, reject) => {
      const transaction = db.transaction(OFFLINE_QUEUE_STORE, "readwrite");
      transaction.objectStore(OFFLINE_QUEUE_STORE).delete(id);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    db.close();
  }

  async function flushOfflineQueueDirectly() {
    if (navigator.serviceWorker?.controller) {
      postToServiceWorker({ type: "FLUSH_QUEUE" });
      return;
    }
    const items = await getOfflineQueueItems().catch(() => []);
    if (!items.length) {
      updateSyncStatus({ online: true, count: 0 });
      return;
    }
    updateSyncStatus({ online: true, count: items.length, syncing: true });
    let synced = 0;
    for (const item of items) {
      try {
        const response = await nativeFetch(item.url, {
          method: item.method,
          headers: item.headers,
          body: item.body || undefined,
          credentials: "include",
        });
        if (response.status === 401 || response.status === 403) {
          showToast("برای همگام‌سازی دوباره وارد حساب وب شوید", "warning");
          break;
        }
        if (!response.ok) break;
        await deleteOfflineQueueItem(item.id);
        synced += 1;
      } catch (_) {
        break;
      }
    }
    const remaining = await getOfflineQueueCount();
    updateSyncStatus({ online: true, count: remaining });
    if (synced) {
      showToast(`${synced} مورد آفلاین با موفقیت همگام شد`, "success");
      initApp();
    }
  }

  function isTransientNetworkStatus(status) {
    return [408, 425, 429, 502, 503, 504, 520, 521, 522, 523, 524].includes(status);
  }

  function isOfflineEligibleRequest(request) {
    return request.url.startsWith(window.location.origin + "/api/")
      && !request.url.includes("/api/auth/")
      && ["POST", "PUT", "PATCH", "DELETE"].includes(request.method);
  }

  function isOfflineCacheEligibleRequest(request) {
    return request.url.startsWith(window.location.origin + "/api/")
      && !request.url.includes("/api/auth/")
      && request.method === "GET";
  }

  window.fetch = async (...args) => {
    try {
      const response = await nativeFetch(...args);
      const request = new Request(args[0], args[1]);
      if (response.ok && isOfflineCacheEligibleRequest(request)) {
        await cacheOfflineApiResponse(request, response);
      }
      if (response.ok && isOfflineEligibleRequest(request)) {
        invalidateDataCache("lifeHistory", "lifeRadar", "habits", "spiritual", "quranHistory", "habitAnalytics", "reports");
      }
      if (isTransientNetworkStatus(response.status) && isOfflineEligibleRequest(request)) {
        offlineMutationQueued = true;
        return await enqueueOfflineMutation(args[0], args[1]);
      }
      if (!response.ok && isOfflineCacheEligibleRequest(request)) {
        const cached = await getOfflineApiResponse(request.url);
        if (cached) {
          updateSyncStatus({ online: false });
          return cached;
        }
      }
      if (response.headers.get("X-Offline-Queued") === "1") {
        offlineMutationQueued = true;
      }
      return response;
    } catch (error) {
      const request = new Request(args[0], args[1]);
      if (isOfflineEligibleRequest(request)) {
        try {
          offlineMutationQueued = true;
          return await enqueueOfflineMutation(args[0], args[1]);
        } catch (queueError) {
          console.error("Could not queue offline mutation", queueError);
        }
      }
      if (isOfflineCacheEligibleRequest(request)) {
        const cached = await getOfflineApiResponse(request.url);
        if (cached) {
          updateSyncStatus({ online: false });
          return cached;
        }
      }
      throw error;
    }
  };

  function setAuthState(state, message = "") {
    document.body.classList.remove("auth-pending", "auth-required", "authenticated");
    document.body.classList.add(state);
    const error = document.getElementById("loginError");
    if (error) error.textContent = message;
  }

  function updateSyncStatus({ online = originReachable, count = pendingQueueCount, syncing = false } = {}) {
    const status = document.getElementById("syncStatus");
    const text = document.getElementById("syncStatusText");
    if (!status || !text) return;

    originReachable = online;
    pendingQueueCount = count;

    status.classList.toggle("is-online", online && !count && !syncing);
    status.classList.toggle("is-offline", !online);
    status.classList.toggle("has-queue", count > 0);
    status.classList.toggle("is-syncing", syncing);

    if (!online) text.textContent = count > 0 ? `${count} مورد در صف` : "آفلاین";
    else if (syncing) text.textContent = "در حال همگام‌سازی";
    else if (count > 0) text.textContent = `${count} مورد در صف`;
    else text.textContent = "همگام";
  }

  function postToServiceWorker(message) {
    if (navigator.serviceWorker?.controller) {
      navigator.serviceWorker.controller.postMessage(message);
    }
  }

  async function setupOfflineSupport() {
    updateSyncStatus();
    if (!("serviceWorker" in navigator)) return;

    try {
      await navigator.serviceWorker.register("/service-worker.js", { scope: "/" });
      await navigator.serviceWorker.ready;
      postToServiceWorker({ type: "GET_QUEUE_STATUS" });
      flushOfflineQueueDirectly();
    } catch (error) {
      console.warn("Service worker registration failed", error);
    }

    navigator.serviceWorker.addEventListener("message", (event) => {
      const data = event.data || {};
      if (data.type === "QUEUE_STATUS") {
        updateSyncStatus({ count: Number(data.count || 0) });
      } else if (data.type === "SYNC_STARTED") {
        updateSyncStatus({ online: true, count: Number(data.count || pendingQueueCount), syncing: true });
      } else if (data.type === "SYNC_COMPLETE") {
        updateSyncStatus({ online: true, count: pendingQueueCount });
        showToast(`${data.count} مورد آفلاین با موفقیت همگام شد`, "success");
        initApp();
      } else if (data.type === "SYNC_FAILED") {
        updateSyncStatus({ online: true, count: pendingQueueCount });
        showToast("بعضی موارد هنوز همگام نشده‌اند؛ دوباره تلاش کن", "warning");
      } else if (data.type === "SYNC_AUTH_REQUIRED") {
        updateSyncStatus({ count: 1 });
        showToast("برای ادامه همگام‌سازی دوباره وارد حساب وب شوید", "warning");
      } else if (data.type === "NETWORK_UNAVAILABLE") {
        updateSyncStatus({ online: false });
      } else if (data.type === "NETWORK_RESTORED") {
        updateSyncStatus({ online: true });
      }
    });
  }

  window.addEventListener("online", () => {
    if (pendingQueueCount > 0) {
      updateSyncStatus({ online: true, count: pendingQueueCount, syncing: true });
      flushOfflineQueueDirectly();
    } else {
      updateSyncStatus({ online: true, count: 0 });
    }
  });
  window.addEventListener("offline", () => updateSyncStatus({ online: false }));

  document.getElementById("syncStatus")?.addEventListener("click", () => {
    if (!navigator.onLine) {
      showToast("اتصال اینترنت هنوز برقرار نیست", "warning");
      return;
    }
    if (pendingQueueCount === 0) {
      updateSyncStatus({ online: true, count: 0 });
      showToast("همه اطلاعات همگام هستند", "success");
      return;
    }
    updateSyncStatus({ online: true, count: pendingQueueCount, syncing: true });
    flushOfflineQueueDirectly();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && navigator.onLine && pendingQueueCount > 0) {
      flushOfflineQueueDirectly();
    }
  });

  document.getElementById("webLoginForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = document.getElementById("btnWebLogin");
    const username = document.getElementById("webUsername")?.value.trim() || "";
    const password = document.getElementById("webPassword")?.value || "";
    const errorBox = document.getElementById("loginError");
    if (button) button.disabled = true;
    if (errorBox) errorBox.textContent = "";

    try {
      const response = await nativeFetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "ورود انجام نشد.");
      document.getElementById("webPassword").value = "";
      await initApp();
      postToServiceWorker({ type: "FLUSH_QUEUE" });
    } catch (error) {
      if (errorBox) errorBox.textContent = error.message;
    } finally {
      if (button) button.disabled = false;
    }
  });

  document.getElementById("btnWebLogout")?.addEventListener("click", async () => {
    try {
      await nativeFetch("/api/auth/logout", { method: "POST", credentials: "include" });
    } finally {
      postToServiceWorker({ type: "CLEAR_LOCAL_DATA" });
      await clearOfflineApiCache();
      setAuthState("auth-required");
    }
  });

  // ==========================================
  // 🌓 THEME SWITCHER (DARK / LIGHT MODE)
  // ==========================================
  function initTheme() {
    const btnToggle = document.getElementById("btnToggleTheme");
    const iconSpan = document.getElementById("themeIcon");

    function getInitialTheme() {
      const saved = localStorage.getItem("notionyar_theme_v4");
      if (saved === "light" || saved === "dark") return saved;
      return "light";
    }

    function applyTheme(theme) {
      document.documentElement.setAttribute("data-theme", theme);
      document.body.setAttribute("data-theme", theme);
      if (iconSpan) {
        iconSpan.innerHTML = `<i class="ui-icon" data-lucide="${theme === "dark" ? "sun" : "moon"}"></i>`;
        refreshIconography();
      }
      if (btnToggle) {
        btnToggle.setAttribute("title", theme === "dark" ? "تغییر به تم روشن" : "تغییر به تم تاریک");
      }

      if (tg) {
        const bgHex = theme === "dark" ? "#121816" : "#f4f7f6";
        try {
          if (typeof tg.setHeaderColor === "function") tg.setHeaderColor(bgHex);
          if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor(bgHex);
        } catch (e) {}
      }
    }

    let currentTheme = getInitialTheme();
    applyTheme(currentTheme);

    btnToggle?.addEventListener("click", () => {
      currentTheme = currentTheme === "dark" ? "light" : "dark";
      localStorage.setItem("notionyar_theme_v4", currentTheme);
      applyTheme(currentTheme);
      haptic("medium");
    });
  }

  // Run theme immediately
  setupIconography();
  initTheme();

  // ==========================================
  // 👑 ROLES PERSIAN DICTIONARY & CUSTOM DROPDOWN
  // ==========================================
  const ROLE_PERSIAN_MAP = {
    admin: "👑 مدیر کل",
    manager: "💼 مدیر تیم",
    member: "👤 عضو تیم",
    guest: "🌿 مهمان",
  };

  const ROLE_OPTIONS_MAP = {
    member: { title: "👤 عضو تیم", desc: "مشاهده گزارش" },
    manager: { title: "💼 مدیر تیم", desc: "ویرایش و حذف" },
    admin: { title: "👑 مدیر کل", desc: "دسترسی کامل به سامانه" },
    guest: { title: "🌿 مهمان", desc: "دسترسی پایه به ربات" }
  };

  function setAdminRoleDropdown(roleValue) {
    const hiddenInput = document.getElementById("adminNewUserRole");
    const selectedSpan = document.getElementById("adminRoleSelected");
    const dropdown = document.getElementById("adminRoleDropdown");
    if (!hiddenInput || !selectedSpan) return;

    const role = (roleValue in ROLE_OPTIONS_MAP) ? roleValue : "member";
    const opt = ROLE_OPTIONS_MAP[role];
    hiddenInput.value = role;
    selectedSpan.textContent = `${opt.title} (${opt.desc})`;

    if (dropdown) {
      dropdown.querySelectorAll(".custom-dropdown-item").forEach(item => {
        item.classList.toggle("active", item.getAttribute("data-value") === role);
      });
    }
  }

  function initAdminRoleDropdown() {
    const dropdown = document.getElementById("adminRoleDropdown");
    const trigger = document.getElementById("adminRoleDropdownTrigger");
    const menu = document.getElementById("adminRoleDropdownMenu");
    if (!dropdown || !trigger || !menu) return;

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      if (dropdown.classList.contains("open")) closeHistoryDropdown(dropdown);
      else openHistoryDropdown(dropdown, trigger);
      haptic("light");
    });

    menu.querySelectorAll(".custom-dropdown-item").forEach(item => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const val = item.getAttribute("data-value");
        setAdminRoleDropdown(val);
        dropdown.classList.remove("open");
        trigger.setAttribute("aria-expanded", "false");
        haptic("selection");
      });
    });

    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target)) {
        closeHistoryDropdown(dropdown);
      }
    });
  }

  // ==========================================
  // 📅 JALALI <-> GREGORIAN CONVERTER (PURE JS)
  // ==========================================
  function gregorianToJalali(gy, gm, gd) {
    const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    const gy2 = (gm > 2) ? (gy + 1) : gy;
    let days = 355666 + (365 * gy) + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) + gd + g_d_m[gm - 1];
    let jy = -1595 + (33 * Math.floor(days / 12053));
    days %= 12053;
    jy += 4 * Math.floor(days / 1461);
    days %= 1461;
    if (days > 365) {
      jy += Math.floor((days - 1) / 365);
      days = (days - 1) % 365;
    }
    const jm = (days < 186) ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
    const jd = 1 + ((days < 186) ? (days % 31) : ((days - 186) % 30));
    return [jy, jm, jd];
  }

  function jalaliToGregorian(jy, jm, jd) {
    jy -= 979;
    jm -= 1;
    jd -= 1;
    let j_day_no = 365 * jy + Math.floor(jy / 33) * 8 + Math.floor(((jy % 33) + 3) / 4);
    for (let i = 0; i < jm; ++i) j_day_no += (i < 6) ? 31 : 30;
    j_day_no += jd;
    let g_day_no = j_day_no + 79;
    let gy = 1600 + 400 * Math.floor(g_day_no / 146097);
    g_day_no = g_day_no % 146097;
    let leap = true;
    if (g_day_no >= 36525) {
      g_day_no--;
      gy += 100 * Math.floor(g_day_no / 36524);
      g_day_no = g_day_no % 36524;
      if (g_day_no >= 365) g_day_no++;
      else leap = false;
    }
    gy += 4 * Math.floor(g_day_no / 1461);
    g_day_no %= 1461;
    if (g_day_no >= 366) {
      leap = false;
      g_day_no--;
      gy += Math.floor(g_day_no / 365);
      g_day_no = g_day_no % 365;
    }
    const g_d_m = [0, 31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let gm;
    for (gm = 1; gm <= 12; gm++) {
      const dim = g_d_m[gm];
      if (g_day_no < dim) break;
      g_day_no -= dim;
    }
    const gd = g_day_no + 1;
    return [gy, gm, gd];
  }

  const PERSIAN_MONTH_NAMES = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"
  ];
  const PERSIAN_DIGITS = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];

  const EN_TO_FA_WEEKDAYS = {
    "Sat": "شنبه", "Sun": "یکشنبه", "Mon": "دوشنبه", "Tue": "سه‌شنبه",
    "Wed": "چهارشنبه", "Thu": "پنج‌شنبه", "Fri": "جمعه",
    "Saturday": "شنبه", "Sunday": "یکشنبه", "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه", "Thursday": "پنج‌شنبه", "Friday": "جمعه"
  };

  function toPersianDigits(n) {
    if (n === null || n === undefined) return "";
    return String(n).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[d]);
  }

  function formatIsoToJalaliDisplay(isoStr) {
    if (!isoStr) return "";
    const clean = String(isoStr).split("T")[0].split(" ")[0].trim();
    const parts = clean.split("-").map(Number);
    if (parts.length !== 3 || isNaN(parts[0]) || isNaN(parts[1]) || isNaN(parts[2])) return isoStr;
    const [jy, jm, jd] = gregorianToJalali(parts[0], parts[1], parts[2]);
    return `${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]} ${toPersianDigits(jy)}`;
  }

  function updateAnalyticsCustomRangeLabels(kind) {
    const isHabit = kind === "habit";
    const start = isHabit ? customHabitAnalyticsStartDate : customSpiritualReportStartDate;
    const end = isHabit ? customHabitAnalyticsEndDate : customSpiritualReportEndDate;
    const from = document.getElementById(isHabit ? "btnHabitAnalyticsFrom" : "btnSpReportFrom");
    const to = document.getElementById(isHabit ? "btnHabitAnalyticsTo" : "btnSpReportTo");
    if (from) from.textContent = start ? `📅 از ${formatIsoToJalaliDisplay(start)}` : "📅 از تاریخ";
    if (to) to.textContent = end ? `📅 تا ${formatIsoToJalaliDisplay(end)}` : "📅 تا تاریخ";
  }

  function getDateFromOffset(offset) {
    const d = new Date();
    d.setDate(d.getDate() - offset);
    return d.toISOString().split("T")[0];
  }

  // Auto-expand Textareas (no ugly resize handle, matches content height)
  function autoExpandTextareas() {
    document.querySelectorAll("textarea").forEach((el) => {
      const resize = () => {
        el.style.height = "auto";
        el.style.height = Math.max(el.scrollHeight, 42) + "px";
      };
      el.removeEventListener("input", el._autoResizeHandler || (() => {}));
      el._autoResizeHandler = resize;
      el.addEventListener("input", resize);
      resize();
    });
  }

  // ==========================================
  // ⚡ APP STATE
  // ==========================================
  let currentUser = null;
  let currentDateIso = new Date().toISOString().split("T")[0];
  let selectedLifeDate = getDateFromOffset(0);
  let selectedLifeType = null;
  let selectedLifeModes = []; // supports 0, 1, or multiple modes
  let lifeOptionsData = null;
  let allLifeEntriesCache = []; // for local fast date filtering
  let customLifeStartDate = null;
  let customLifeEndDate = null;
  let customHabitAnalyticsStartDate = null;
  let customHabitAnalyticsEndDate = null;
  let customSpiritualReportStartDate = null;
  let customSpiritualReportEndDate = null;
  let lifeHistoryView = "date";
  let lifeHistoryPage = 1;
  let lifeHistoryLoadPromise = null;
  const LIFE_HISTORY_PAGE_SIZE = 60;

  let currentHabitDateIso = getDateFromOffset(0);
  let habitDayData = null;
  let currentHabitAnalyticsPeriod = "7d";
  let isStealthMode = localStorage.getItem("notionyar_stealth") === "true";

  // Spiritual Tracker State
  let currentSpiritualDateIso = getDateFromOffset(0);
  let selectedQuranDateIso = getDateFromOffset(0);
  let spiritualDayData = null;
  let spBulkActivePreset = "last_7_days";
  let spBulkCustomFromIso = "";
  let spBulkCustomToIso = "";

  // Gratitude Builder State
  let currentGratitudeTag = "سلامتی و جسم";
  let gratitudeItems = [];

  // Persian Date Picker Modal State
  let activeDatePickerTarget = "time"; // "time" | "life" | "habits" | "spiritual" | "quran" | "life_from" | "life_to" | "spiritual_bulk_from" | "spiritual_bulk_to"


  // Header Helper
  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    return headers;
  }

  // Haptic Helper
  function haptic(type = "light") {
    try {
      if (tg?.HapticFeedback) {
        if (type === "success" || type === "error" || type === "warning") {
          tg.HapticFeedback.notificationOccurred(type);
        } else {
          tg.HapticFeedback.impactOccurred(type);
        }
      }
    } catch (e) {}
  }

  // Toast Helper
  function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    if (!toast) return;

    if (type === "success" && offlineMutationQueued) {
      message = "آفلاین ذخیره شد؛ بعد از اتصال همگام می‌شود";
      type = "info";
      offlineMutationQueued = false;
    }

    toast.className = `toast ${type} show`;
    toast.style.setProperty("--toast-duration", "2800ms");
    const icon = type === "success" ? "✅ " : type === "error" ? "❌ " : "ℹ️ ";
    toast.textContent = icon + toPersianDigits(message);
    toast.setAttribute("aria-label", toPersianDigits(message));

    if (type === "success") haptic("success");
    if (type === "error") haptic("error");

    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => {
      toast.classList.remove("show");
      toast.style.removeProperty("--toast-duration");
    }, 2800);
  }

  function renderRetryState(container, message, retry) {
    if (!container) return;
    container.innerHTML = `<div class="empty-state"><strong>⚠️ ${message}</strong><span>اطلاعات دریافت نشد.</span><button type="button" class="btn-step retry-action">🔄 تلاش دوباره</button></div>`;
    container.querySelector(".retry-action")?.addEventListener("click", () => retry(), { once: true });
  }

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".modal-backdrop").forEach((modal) => { modal.style.display = "none"; });
    document.querySelectorAll(".custom-dropdown.open").forEach((dropdown) => dropdown.classList.remove("open"));
  });

  // ==========================================
  // 1. INITIALIZATION & AUTH
  // ==========================================
  async function restoreOfflineSession(snapshot) {
    const data = snapshot || {};
    const todayIso = data.today_iso || getDateFromOffset(0);
    setAuthState("authenticated");
    currentUser = data.user || {};
    currentDateIso = todayIso;
    selectedLifeDate = todayIso;
    currentHabitDateIso = todayIso;
    currentSpiritualDateIso = todayIso;
    selectedQuranDateIso = todayIso;

    document.getElementById("userName").textContent = currentUser.first_name || "کاربر گرامی";
    document.getElementById("currentDate").textContent = toPersianDigits(data.today_jalali || formatIsoToJalaliDisplay(todayIso));
    const roleBadge = document.getElementById("userRole");
    if (roleBadge) roleBadge.textContent = ROLE_PERSIAN_MAP[currentUser.role] || "کاربر";
    const logoutButton = document.getElementById("btnWebLogout");
    if (logoutButton) logoutButton.style.display = currentUser.auth_source === "web" ? "inline-flex" : "none";
    const adminNavBtn = document.getElementById("navItemAdmin");
    if (adminNavBtn) adminNavBtn.style.display = currentUser.is_admin ? "flex" : "none";

    initAdminRoleDropdown();
    initLifeHistoryPeriodDropdown();
    initLifeHistoryFilterDropdown();
    initLifeHistoryControls();
    initLifeEditModal();
    setupStealthModeUI();
    updateDateBadge("life", 0);
    updateSpiritualDateBadge(0);
    updateQuranDateBadge(0);
    autoExpandTextareas();
    await Promise.all([
      loadLifeTrackerOptions(),
      loadHabitsForDate(currentHabitDateIso),
      loadSpiritualDay(currentSpiritualDateIso),
    ]);
    const activePanel = document.querySelector(".tab-panel.active");
    const activeSubtab = activePanel?.querySelector(".subtab-content.active")?.id;
    if (activeSubtab === "life-sub-radar") loadLifeRadar();
    if (activeSubtab === "life-sub-history") loadLifeHistory();
    if (activeSubtab === "habit-sub-analytics") loadHabitsAnalytics();
    if (activeSubtab === "spiritual-sub-quran") loadQuranHistory();
    if (activeSubtab === "spiritual-sub-report") loadSpiritualReport("7d");
  }

  async function initApp() {
    try {
      const res = await fetch("/api/me", { headers: getHeaders() });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        if ((navigator.onLine === false || res.status >= 500) && localStorage.getItem("notionyar_last_auth")) {
          await restoreOfflineSession(JSON.parse(localStorage.getItem("notionyar_last_auth")));
          updateSyncStatus({ online: false });
          showToast("حالت آفلاین فعال شد؛ آخرین داده‌های ذخیره‌شده نمایش داده می‌شوند", "info");
          return;
        }
        if (!tg?.initData && [401, 403].includes(res.status)) {
          setAuthState("auth-required", data.detail || "برای ادامه وارد حساب وب شوید.");
        } else {
          setAuthState("auth-required", data.detail || "خطا در تایید هویت کاربر");
        }
        return;
      }
      const data = await res.json();
      localStorage.setItem("notionyar_last_auth", JSON.stringify(data));
      setAuthState("authenticated");
      currentUser = data.user;
      currentDateIso = data.today_iso;
      selectedLifeDate = data.today_iso;
      currentHabitDateIso = data.today_iso;
      currentSpiritualDateIso = data.today_iso;
      selectedQuranDateIso = data.today_iso;

      document.getElementById("userName").textContent = currentUser.first_name || "کاربر گرامی";
      document.getElementById("currentDate").textContent = toPersianDigits(data.today_jalali);

      const roleBadge = document.getElementById("userRole");
      roleBadge.textContent = ROLE_PERSIAN_MAP[currentUser.role] || "کاربر";

      const logoutButton = document.getElementById("btnWebLogout");
      if (logoutButton) {
        logoutButton.style.display = currentUser.auth_source === "web" ? "inline-flex" : "none";
      }

      // Show Admin Tab if user is admin
      const adminNavBtn = document.getElementById("navItemAdmin");
      if (adminNavBtn) {
        adminNavBtn.style.display = currentUser.is_admin ? "flex" : "none";
      }

      // Initialize Custom Admin Role Dropdown
      initAdminRoleDropdown();
      initLifeHistoryPeriodDropdown();
      initLifeHistoryFilterDropdown();
      initLifeHistoryControls();
      initLifeEditModal();

      // Setup stealth mode initial UI
      setupStealthModeUI();

      // Update date badges
      updateDateBadge("life", 0);
      updateSpiritualDateBadge(0);
      updateQuranDateBadge(0);

      autoExpandTextareas();

      await Promise.all([
        loadLifeTrackerOptions(),
        loadHabitsForDate(currentHabitDateIso),
        loadSpiritualDay(currentSpiritualDateIso),
      ]);

      const activePanel = document.querySelector(".tab-panel.active");
      const activeSubtab = activePanel?.querySelector(".subtab-content.active")?.id;
      if (activeSubtab === "life-sub-radar") loadLifeRadar();
      if (activeSubtab === "life-sub-history") loadLifeHistory();
      if (activeSubtab === "habit-sub-analytics") loadHabitsAnalytics();
      if (activeSubtab === "spiritual-sub-quran") loadQuranHistory();
      if (activeSubtab === "spiritual-sub-report") loadSpiritualReport("7d");

    } catch (err) {
      console.error(err);
      try {
        const cachedAuth = localStorage.getItem("notionyar_last_auth");
        if (cachedAuth) {
          await restoreOfflineSession(JSON.parse(cachedAuth));
          updateSyncStatus({ online: false });
          showToast("اتصال برقرار نیست؛ آخرین داده‌های ذخیره‌شده فعال شدند", "info");
          return;
        }
      } catch (offlineError) {
        console.error("Offline session restore failed", offlineError);
      }
      showToast("خطا در ارتباط با سرور", "error");
    }
  }

  function updateDateBadge(target, offset = null, customIso = null) {
    let text = "";
    if (offset === 0) text = `امروز (${formatIsoToJalaliDisplay(getDateFromOffset(0))})`;
    else if (offset === 1) text = `دیروز (${formatIsoToJalaliDisplay(getDateFromOffset(1))})`;
    else if (offset === 2) text = `پریروز (${formatIsoToJalaliDisplay(getDateFromOffset(2))})`;
    else if (customIso) text = formatIsoToJalaliDisplay(customIso);

    if (target === "life") {
      const badge = document.getElementById("lifeSelectedDateBadge");
      if (badge) badge.textContent = `📅 تاریخ انتخاب‌شده: ${text}`;
    }
  }

  // ==========================================
  // 2. NAVIGATION & TABS
  // ==========================================
  const navItems = document.querySelectorAll(".nav-item");
  const tabPanels = document.querySelectorAll(".tab-panel");
  const WORKSPACE_COPY = {
    "tab-habits": ["ریتم روز", "عادت‌های امروز را آگاهانه پیش ببر", "کیفیت انجام، جزئیات و روند عادت‌ها را یک‌جا ثبت کن.", "امروز"],
    "tab-life": ["روزمرگی", "اتفاق‌های کوچک روز را از دست نده", "ثبت‌های روزمره را سریع وارد کن و فاصله‌ها را زیر نظر بگیر.", "ثبت سریع"],
    "tab-spiritual": ["مسیر معنوی", "نماز و تلاوت را با آرامش دنبال کن", "وضعیت روزانه و جزئیات مسیر معنوی در دسترس توست.", "مسیر من"],
    "tab-reports": ["گزارش‌ها", "روندها را روشن و قابل مقایسه ببین", "خلاصه و جزئیات همه بخش‌ها در بازه دلخواه.", "تحلیل"],
    "tab-admin": ["مدیریت", "سامانه و دسترسی‌ها را مدیریت کن", "وضعیت سرویس و نقش اعضا را از اینجا کنترل کن.", "مدیریت"],
  };

  function updateWorkspaceIntro(targetTabId) {
    const copy = WORKSPACE_COPY[targetTabId] || WORKSPACE_COPY["tab-habits"];
    const kicker = document.getElementById("workspaceKicker");
    const title = document.getElementById("workspaceTitle");
    const description = document.getElementById("workspaceDescription");
    const mark = document.getElementById("workspaceMark");
    if (kicker) kicker.textContent = copy[0];
    if (title) title.textContent = copy[1];
    if (description) description.textContent = copy[2];
    if (mark) mark.textContent = copy[3];
    document.body.classList.toggle("reports-view", targetTabId === "tab-reports");
    document.body.dataset.section = targetTabId.replace("tab-", "");
  }

  function activateMainTab(targetTabId, direction = 0) {
      const btn = Array.from(navItems).find((item) => item.getAttribute("data-tab") === targetTabId);
      if (!btn) return;
      navItems.forEach((i) => i.classList.remove("active"));
      tabPanels.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPanel = document.getElementById(targetTabId);
      if (targetPanel) targetPanel.classList.add("active");
      updateWorkspaceIntro(targetTabId);

      haptic("light");
      window.scrollTo({ top: 0, behavior: "smooth" });

      const lifeHistory = document.getElementById("life-sub-history");
      if (targetTabId === "tab-life" && lifeHistory?.classList.contains("active") && !dataCache.lifeHistory) {
        loadLifeHistory();
      }

      if (targetTabId === "tab-admin") {
        loadAdminPanel();
      }
      if (targetTabId === "tab-spiritual") {
        loadSpiritualDay(currentSpiritualDateIso);
      }
      if (targetTabId === "tab-reports") {
        loadReportsDashboard(currentReportPeriod);
      }
  }

  navItems.forEach((btn) => {
    btn.addEventListener("click", () => activateMainTab(btn.getAttribute("data-tab")));
  });

  let swipeStartX = 0;
  let swipeStartY = 0;
  let swipeTracking = false;
  document.getElementById("app")?.addEventListener("touchstart", (event) => {
    if (event.touches.length !== 1) return;
    swipeStartX = event.touches[0].clientX;
    swipeStartY = event.touches[0].clientY;
    swipeTracking = true;
  }, { passive: true });
  document.getElementById("app")?.addEventListener("touchend", (event) => {
    if (!swipeTracking || !event.changedTouches.length) return;
    swipeTracking = false;
    const dx = event.changedTouches[0].clientX - swipeStartX;
    const dy = event.changedTouches[0].clientY - swipeStartY;
    if (Math.abs(dx) < 56 || Math.abs(dx) < Math.abs(dy) * 1.25) return;
    const visibleItems = Array.from(navItems).filter((item) => getComputedStyle(item).display !== "none");
    const current = visibleItems.findIndex((item) => item.classList.contains("active"));
    if (current < 0 || visibleItems.length < 2) return;
    const nextIndex = dx < 0
      ? (current + 1) % visibleItems.length
      : (current - 1 + visibleItems.length) % visibleItems.length;
    activateMainTab(visibleItems[nextIndex].getAttribute("data-tab"), dx < 0 ? 1 : -1);
  }, { passive: true });
  updateWorkspaceIntro("tab-habits");

  document.querySelectorAll("[data-admin-section]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.adminSection;
      document.querySelectorAll("[data-admin-section]").forEach((item) => item.classList.toggle("active", item === button));
      document.querySelectorAll(".admin-section-card").forEach((section) => {
        section.hidden = section.id !== target;
      });
      localStorage.setItem("notionyar_admin_section", target);
      haptic("light");
    });
  });

  const savedAdminSection = localStorage.getItem("notionyar_admin_section");
  if (savedAdminSection) {
    document.querySelector(`[data-admin-section="${savedAdminSection}"]`)?.click();
  }

  // Segmented Controls (Sub-tabs)
  document.querySelectorAll(".segmented-control").forEach((segControl) => {
    segControl.querySelectorAll(".seg-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const subtabId = btn.getAttribute("data-subtab");
        // History view buttons use the same visual segmented control but are
        // not workspace subtabs. Do not let the generic handler blank the tab.
        if (!subtabId) return;
        const parentSection = btn.closest(".tab-panel");
        if (!parentSection) return;

        parentSection.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
        parentSection.querySelectorAll(".subtab-content").forEach((c) => c.classList.remove("active"));

        btn.classList.add("active");
        const targetContent = document.getElementById(subtabId);
        if (targetContent) targetContent.classList.add("active");
        if (parentSection.id) sessionStorage.setItem(`notionyar_subtab_${parentSection.id}`, subtabId);

        haptic("light");
        window.scrollTo({ top: 0, behavior: "smooth" });

        // Dynamic Loading for Analytics/Reports
        if (subtabId === "life-sub-radar") loadLifeRadar();
        if (subtabId === "life-sub-history") loadLifeHistory();
        if (subtabId === "habit-sub-analytics") loadHabitsAnalytics();
        if (subtabId === "spiritual-sub-quran") loadQuranHistory();
        if (subtabId === "spiritual-sub-report") loadSpiritualReport("7d");
      });
    });
  });

  // Restore the last workspace view so repeated daily use starts where it left off.
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    const savedSubtab = sessionStorage.getItem(`notionyar_subtab_${panel.id}`);
    if (!savedSubtab) return;
    const savedButton = panel.querySelector(`[data-subtab="${savedSubtab}"]`);
    const savedContent = document.getElementById(savedSubtab);
    if (!savedButton || !savedContent) return;
    panel.querySelectorAll(".segmented-control .seg-btn").forEach((item) => item.classList.remove("active"));
    panel.querySelectorAll(".subtab-content").forEach((item) => item.classList.remove("active"));
    savedButton.classList.add("active");
    savedContent.classList.add("active");
  });

  const scrollTopButton = document.getElementById("btnScrollTop");
  const updateScrollTopButton = () => scrollTopButton?.classList.toggle("visible", window.scrollY > 360);
  window.addEventListener("scroll", updateScrollTopButton, { passive: true });
  scrollTopButton?.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  updateScrollTopButton();


  document.getElementById("btnRefresh")?.addEventListener("click", async () => {
    haptic("medium");
    showToast("در حال بروزرسانی اطلاعات...", "info");
    await initApp();
    showToast("داده‌ها بروز شدند", "success");
  });

  // ==========================================
  // 3. PERSIAN DATE PICKER MODAL
  // ==========================================
  function initPersianDatePickerModal() {
    const modal = document.getElementById("persianDateModal");
    const daySelect = document.getElementById("shamsiDaySelect");
    const monthSelect = document.getElementById("shamsiMonthSelect");
    const yearSelect = document.getElementById("shamsiYearSelect");
    const preview = document.getElementById("shamsiDatePreview");
    const btnConfirm = document.getElementById("btnConfirmShamsiDate");
    const btnClose = document.getElementById("btnDateModalClose");

    const customDateDropdowns = {
      day: { select: daySelect, trigger: document.getElementById("shamsiDayTrigger"), label: document.getElementById("shamsiDaySelected"), menu: document.getElementById("shamsiDayMenu") },
      month: { select: monthSelect, trigger: document.getElementById("shamsiMonthTrigger"), label: document.getElementById("shamsiMonthSelected"), menu: document.getElementById("shamsiMonthMenu") },
      year: { select: yearSelect, trigger: document.getElementById("shamsiYearTrigger"), label: document.getElementById("shamsiYearSelected"), menu: document.getElementById("shamsiYearMenu") },
    };

    function syncCustomDateDropdown(kind) {
      const control = customDateDropdowns[kind];
      if (!control?.select || !control.menu || !control.label) return;
      control.menu.innerHTML = "";
      Array.from(control.select.options).forEach((option) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "custom-date-option";
        item.dataset.value = option.value;
        item.setAttribute("role", "option");
        item.setAttribute("aria-selected", String(option.value === control.select.value));
        item.textContent = option.textContent;
        item.addEventListener("click", (event) => {
          event.stopPropagation();
          control.select.value = option.value;
          control.select.dispatchEvent(new Event("change", { bubbles: true }));
          closeCustomDateDropdown(control.dropdown || control.trigger?.closest(".custom-date-dropdown"));
        });
        control.menu.appendChild(item);
      });
      const selected = control.select.options[control.select.selectedIndex];
      control.label.textContent = selected?.textContent || "انتخاب کنید";
      control.menu.querySelectorAll(".custom-date-option").forEach((item) => item.classList.toggle("active", item.dataset.value === control.select.value));
    }
    window.__notionyarSyncDateDropdown = syncCustomDateDropdown;

    function closeCustomDateDropdown(dropdown) {
      if (!dropdown) return;
      dropdown.classList.remove("open", "dropup");
      dropdown.querySelector(".custom-date-trigger")?.setAttribute("aria-expanded", "false");
      const menu = dropdown._dateMenu;
      menu?.classList.remove("portal-open");
      if (menu) menu.style.cssText = "";
    }

    Object.entries(customDateDropdowns).forEach(([kind, control]) => {
      control.dropdown = control.trigger?.closest(".custom-date-dropdown");
      if (control.dropdown) control.dropdown._dateMenu = control.menu;
      control.trigger?.addEventListener("click", (event) => {
        event.stopPropagation();
        const dropdown = control.dropdown;
        const open = dropdown.classList.toggle("open");
        document.querySelectorAll(".custom-date-dropdown.open").forEach((other) => {
          if (other !== dropdown) closeCustomDateDropdown(other);
        });
        const bounds = dropdown.getBoundingClientRect();
        if (open) {
          if (control.menu.parentElement !== document.body) document.body.appendChild(control.menu);
          control.menu.classList.add("portal-open");
          const menuHeight = Math.min(420, Math.floor(window.innerHeight * .56));
          const dropUp = bounds.bottom + menuHeight + 8 > window.innerHeight && bounds.top > menuHeight + 8;
          dropdown.classList.toggle("dropup", dropUp);
          control.menu.style.position = "fixed";
          control.menu.style.left = `${bounds.left}px`;
          control.menu.style.width = `${bounds.width}px`;
          control.menu.style.top = dropUp ? `${bounds.top - menuHeight - 6}px` : `${bounds.bottom + 6}px`;
          control.menu.style.maxHeight = `${menuHeight}px`;
          control.menu.style.zIndex = "1200";
        } else {
          closeCustomDateDropdown(dropdown);
        }
        control.trigger.setAttribute("aria-expanded", String(open));
      });
      control.select?.addEventListener("change", () => syncCustomDateDropdown(kind));
    });
    document.addEventListener("click", () => {
      document.querySelectorAll(".custom-date-dropdown.open").forEach((dropdown) => {
        closeCustomDateDropdown(dropdown);
      });
    });

    function updateDays() {
      const m = parseInt(monthSelect.value, 10);
      const maxDays = m <= 6 ? 31 : (m <= 11 ? 30 : 29);
      const currentSelectedDay = parseInt(daySelect.value, 10) || 1;

      daySelect.innerHTML = "";
      for (let d = 1; d <= maxDays; d++) {
        const opt = document.createElement("option");
        opt.value = d;
        opt.textContent = toPersianDigits(d);
        if (d === Math.min(currentSelectedDay, maxDays)) opt.selected = true;
        daySelect.appendChild(opt);
      }
      syncCustomDateDropdown("day");
      updatePreview();
    }

    function updatePreview() {
      const d = daySelect.value;
      const m = monthSelect.value;
      const y = yearSelect.value;
      preview.textContent = `${toPersianDigits(d)} ${PERSIAN_MONTH_NAMES[m - 1]} ${toPersianDigits(y)}`;
    }

    monthSelect?.addEventListener("change", updateDays);
    daySelect?.addEventListener("change", updatePreview);
    yearSelect?.addEventListener("change", updatePreview);
    syncCustomDateDropdown("day");
    syncCustomDateDropdown("month");
    window.__notionyarSyncDateDropdown?.("year");

    btnClose?.addEventListener("click", () => {
      document.querySelectorAll(".custom-date-dropdown.open").forEach(closeCustomDateDropdown);
      modal.style.display = "none";
    });

    modal?.addEventListener("click", (e) => {
      if (e.target === modal) {
        document.querySelectorAll(".custom-date-dropdown.open").forEach(closeCustomDateDropdown);
        modal.style.display = "none";
      }
    });

    btnConfirm?.addEventListener("click", () => {
      const jy = parseInt(yearSelect.value, 10);
      const jm = parseInt(monthSelect.value, 10);
      const jd = parseInt(daySelect.value, 10);

      const [gy, gm, gd] = jalaliToGregorian(jy, jm, jd);
      const isoDate = `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;

      if (activeDatePickerTarget === "life") {
        selectedLifeDate = isoDate;
        document.querySelectorAll("[data-life-offset]").forEach((b) => b.classList.remove("active"));
        updateDateBadge("life", null, isoDate);
      } else if (activeDatePickerTarget === "habits") {
        currentHabitDateIso = isoDate;
        document.querySelectorAll("[data-habit-offset]").forEach((b) => b.classList.remove("active"));
        loadHabitsForDate(currentHabitDateIso);
      } else if (activeDatePickerTarget === "spiritual") {
        currentSpiritualDateIso = isoDate;
        document.querySelectorAll("[data-spiritual-offset]").forEach((b) => b.classList.remove("active"));
        updateSpiritualDateBadge(null, isoDate);
        loadSpiritualDay(currentSpiritualDateIso);
      } else if (activeDatePickerTarget === "quran") {
        selectedQuranDateIso = isoDate;
        document.querySelectorAll("[data-quran-offset]").forEach((b) => b.classList.remove("active"));
        updateQuranDateBadge(null, isoDate);
      } else if (activeDatePickerTarget === "life_from") {
        customLifeStartDate = isoDate;
        const btn = document.getElementById("btnLifeRangeFrom");
        if (btn) btn.textContent = `📅 از ${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]}`;
        renderFilteredLifeHistory();
      } else if (activeDatePickerTarget === "life_to") {
        customLifeEndDate = isoDate;
        const btn = document.getElementById("btnLifeRangeTo");
        if (btn) btn.textContent = `📅 تا ${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]}`;
        renderFilteredLifeHistory();
      } else if (activeDatePickerTarget === "spiritual_bulk_from") {
        spBulkCustomFromIso = isoDate;
        spBulkActivePreset = null;
        document.querySelectorAll("[data-sp-bulk-preset]").forEach((b) => b.classList.remove("active"));
        const btn = document.getElementById("btnSpBulkFrom");
        if (btn) btn.innerHTML = `<span>📅 از: ${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]}</span>`;
        updateSpBulkRangeBadge();
      } else if (activeDatePickerTarget === "spiritual_bulk_to") {
        spBulkCustomToIso = isoDate;
        spBulkActivePreset = null;
        document.querySelectorAll("[data-sp-bulk-preset]").forEach((b) => b.classList.remove("active"));
        const btn = document.getElementById("btnSpBulkTo");
        if (btn) btn.innerHTML = `<span>📅 تا: ${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]}</span>`;
        updateSpBulkRangeBadge();
      } else if (activeDatePickerTarget === "habit_analytics_from") {
        customHabitAnalyticsStartDate = isoDate;
        updateAnalyticsCustomRangeLabels("habit");
        if (customHabitAnalyticsEndDate) loadHabitsAnalytics("custom");
      } else if (activeDatePickerTarget === "habit_analytics_to") {
        customHabitAnalyticsEndDate = isoDate;
        updateAnalyticsCustomRangeLabels("habit");
        if (customHabitAnalyticsStartDate) loadHabitsAnalytics("custom");
      } else if (activeDatePickerTarget === "spiritual_report_from") {
        customSpiritualReportStartDate = isoDate;
        updateAnalyticsCustomRangeLabels("spiritual");
        if (customSpiritualReportEndDate) loadSpiritualReport("custom");
      } else if (activeDatePickerTarget === "spiritual_report_to") {
        customSpiritualReportEndDate = isoDate;
        updateAnalyticsCustomRangeLabels("spiritual");
        if (customSpiritualReportStartDate) loadSpiritualReport("custom");
      } else if (activeDatePickerTarget === "edit_life") {
        const isoInput = document.getElementById("editLifeDateIso");
        const display = document.getElementById("editLifeDateDisplay");
        if (isoInput) isoInput.value = isoDate;
        if (display) display.textContent = `📅 ${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]} ${toPersianDigits(jy)}`;
      }

      document.querySelectorAll(".custom-date-dropdown.open").forEach(closeCustomDateDropdown);
      modal.style.display = "none";
      haptic("medium");
      showToast("تاریخ شمسی انتخاب شد", "success");
    });
  }

  function openPersianDatePicker(target) {
    activeDatePickerTarget = target;
    const modal = document.getElementById("persianDateModal");
    const daySelect = document.getElementById("shamsiDaySelect");
    const monthSelect = document.getElementById("shamsiMonthSelect");
    const yearSelect = document.getElementById("shamsiYearSelect");

    let currentIso = currentDateIso;
    if (target === "life") currentIso = selectedLifeDate;
    if (target === "habits") currentIso = currentHabitDateIso;
    if (target === "spiritual") currentIso = currentSpiritualDateIso;
    if (target === "quran") currentIso = selectedQuranDateIso;
    if (target === "life_from") currentIso = customLifeStartDate || currentDateIso;
    if (target === "life_to") currentIso = customLifeEndDate || currentDateIso;
    if (target === "spiritual_bulk_from") currentIso = spBulkCustomFromIso || currentDateIso;
    if (target === "spiritual_bulk_to") currentIso = spBulkCustomToIso || currentDateIso;
    if (target === "habit_analytics_from") currentIso = customHabitAnalyticsStartDate || currentDateIso;
    if (target === "habit_analytics_to") currentIso = customHabitAnalyticsEndDate || currentDateIso;
    if (target === "spiritual_report_from") currentIso = customSpiritualReportStartDate || currentDateIso;
    if (target === "spiritual_report_to") currentIso = customSpiritualReportEndDate || currentDateIso;
    if (target === "edit_life") currentIso = document.getElementById("editLifeDateIso")?.value || currentDateIso;

    if (typeof currentIso === "string") {
      currentIso = currentIso.split("T")[0].split(" ")[0].trim();
    }
    const parts = (currentIso || "").split("-").map(Number);
    let jy, jm, jd;
    if (parts.length === 3 && !isNaN(parts[0]) && !isNaN(parts[1]) && !isNaN(parts[2])) {
      [jy, jm, jd] = gregorianToJalali(parts[0], parts[1], parts[2]);
    } else {
      const todayParts = currentDateIso.split("-").map(Number);
      [jy, jm, jd] = gregorianToJalali(todayParts[0], todayParts[1], todayParts[2]);
    }

    // Populate years around current Jalali year
    yearSelect.innerHTML = "";
    for (let y = jy - 2; y <= jy + 2; y++) {
      const opt = document.createElement("option");
      opt.value = y;
      opt.textContent = toPersianDigits(y);
      if (y === jy) opt.selected = true;
      yearSelect.appendChild(opt);
    }
    window.__notionyarSyncDateDropdown?.("year");

    monthSelect.value = jm;
    window.__notionyarSyncDateDropdown?.("month");

    // Populate days
    const maxDays = jm <= 6 ? 31 : (jm <= 11 ? 30 : 29);
    daySelect.innerHTML = "";
    for (let d = 1; d <= maxDays; d++) {
      const opt = document.createElement("option");
      opt.value = d;
      opt.textContent = toPersianDigits(d);
      if (d === jd) opt.selected = true;
      daySelect.appendChild(opt);
    }
    window.__notionyarSyncDateDropdown?.("day");

    const preview = document.getElementById("shamsiDatePreview");
    preview.textContent = `${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]} ${toPersianDigits(jy)}`;

    modal.style.display = "flex";
    haptic("light");
  }

  document.getElementById("btnOpenLifePicker")?.addEventListener("click", () => openPersianDatePicker("life"));
  document.getElementById("btnOpenHabitPicker")?.addEventListener("click", () => openPersianDatePicker("habits"));
  document.getElementById("btnLifeRangeFrom")?.addEventListener("click", () => openPersianDatePicker("life_from"));
  document.getElementById("btnLifeRangeTo")?.addEventListener("click", () => openPersianDatePicker("life_to"));
  document.getElementById("btnOpenSpiritualPicker")?.addEventListener("click", () => openPersianDatePicker("spiritual"));
  document.getElementById("btnOpenQuranDatePicker")?.addEventListener("click", () => openPersianDatePicker("quran"));
  document.getElementById("btnSpBulkFrom")?.addEventListener("click", () => openPersianDatePicker("spiritual_bulk_from"));
  document.getElementById("btnSpBulkTo")?.addEventListener("click", () => openPersianDatePicker("spiritual_bulk_to"));
  document.getElementById("btnHabitAnalyticsFrom")?.addEventListener("click", () => openPersianDatePicker("habit_analytics_from"));
  document.getElementById("btnHabitAnalyticsTo")?.addEventListener("click", () => openPersianDatePicker("habit_analytics_to"));
  document.getElementById("btnSpReportFrom")?.addEventListener("click", () => openPersianDatePicker("spiritual_report_from"));
  document.getElementById("btnSpReportTo")?.addEventListener("click", () => openPersianDatePicker("spiritual_report_to"));


  initPersianDatePickerModal();

  // ==========================================
  // 5. LIFE TRACKER (MULTI-MODE & PERIOD FILTER)
  // ==========================================
  async function loadLifeTrackerOptions() {
    try {
      const res = await fetch("/api/life-tracker/options", { headers: getHeaders() });
      if (!res.ok) return;
      lifeOptionsData = await res.json();
      renderLifeGroups();
      populateHistoryFilter();
    } catch (e) {
      console.error(e);
    }
  }

  function renderLifeGroups() {
    const container = document.getElementById("lifeGroupsContainer");
    if (!container || !lifeOptionsData?.groups) return;

    container.innerHTML = "";
    lifeOptionsData.groups.forEach((grp) => {
      const groupCard = document.createElement("div");
      groupCard.className = "life-group-card";

      const header = document.createElement("div");
      header.className = "life-group-header";
      header.innerHTML = `<span>${grp.emoji}</span> <span>${grp.title}</span>`;
      groupCard.appendChild(header);

      const grid = document.createElement("div");
      grid.className = "life-tiles-grid";

      grp.types.forEach((tName) => {
        const typeMeta = lifeOptionsData.all_types[tName] || { name: tName, emoji: "🌱", modes: [] };
        const tile = document.createElement("div");
        tile.className = "life-tile";
        tile.innerHTML = `
          <span class="tile-emoji">${typeMeta.emoji}</span>
          <span class="tile-name">${typeMeta.name}</span>
        `;
        tile.addEventListener("click", () => {
          selectLifeType(typeMeta, tile);
          haptic("light");
        });
        grid.appendChild(tile);
      });

      groupCard.appendChild(grid);
      container.appendChild(groupCard);
    });
  }

  function selectLifeType(typeMeta, tileEl) {
    selectedLifeType = typeMeta.name;
    selectedLifeModes = []; // reset selected modes on new type

    document.querySelectorAll(".life-tile").forEach((t) => t.classList.remove("active"));
    tileEl.classList.add("active");

    const modesBox = document.getElementById("lifeModesContainer");
    const modesChips = document.getElementById("lifeModesChips");
    const modesLabel = document.getElementById("lifeModesLabel");

    if (typeMeta.modes && typeMeta.modes.length > 0) {
      modesBox.style.display = "block";
      modesLabel.textContent = `حالت‌های انتخابی «${typeMeta.name}»:`;
      modesChips.innerHTML = "";

      typeMeta.modes.forEach((m) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "mode-chip";
        chip.innerHTML = `<span>${m.emoji}</span> <span>${m.name}</span>`;

        chip.addEventListener("click", () => {
          const idx = selectedLifeModes.indexOf(m.name);
          if (idx > -1) {
            selectedLifeModes.splice(idx, 1);
            chip.classList.remove("active");
          } else {
            selectedLifeModes.push(m.name);
            chip.classList.add("active");
          }
          haptic("light");
          updateLifeSubmitButton();
        });
        modesChips.appendChild(chip);
      });
    } else {
      modesBox.style.display = "none";
    }

    updateLifeSubmitButton();
  }

  // Button text without sub-mode names (Item 14)
  function updateLifeSubmitButton() {
    const btn = document.getElementById("btnSubmitLife");
    if (!selectedLifeType) {
      btn.disabled = true;
      btn.innerHTML = "<span>لطفاً یک فعالیت را انتخاب کنید</span>";
      return;
    }
    btn.disabled = false;
    btn.innerHTML = `<span>ثبت ${selectedLifeType}</span> <span class="btn-arrow">←</span>`;
  }

  document.querySelectorAll("[data-life-offset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-life-offset]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const offset = parseInt(btn.getAttribute("data-life-offset"), 10);
      selectedLifeDate = getDateFromOffset(offset);
      updateDateBadge("life", offset);
      haptic("light");
    });
  });

  const formLifeTracker = document.getElementById("formLifeTracker");
  formLifeTracker?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!selectedLifeType) {
      showToast("لطفاً ابتدا نوع فعالیت را انتخاب کنید", "error");
      return;
    }

    const btnSubmit = document.getElementById("btnSubmitLife");
    btnSubmit.disabled = true;
    const origHTML = btnSubmit.innerHTML;
    btnSubmit.innerHTML = "<span>در حال ذخیره...</span>";

    const notes = document.getElementById("lifeNotes").value.trim() || null;

    try {
      const res = await fetch("/api/life-tracker/create", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          event_type: selectedLifeType,
          mode_list: selectedLifeModes,
          date_iso: selectedLifeDate,
          notes: notes,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "خطا در ثبت لاگ");

      showToast(`لاگ «${selectedLifeType}» با موفقیت ذخیره شد! 🌿`, "success");
      invalidateDataCache("lifeHistory", "lifeRadar");
      document.getElementById("lifeNotes").value = "";
      if (typeof loadLifeHistory === "function") loadLifeHistory();
      if (typeof loadLifeRadar === "function") loadLifeRadar();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = origHTML;
    }
  });

  // Routine Radar (Intervals) with Persian Digits
  async function loadLifeRadar() {
    const grid = document.getElementById("lifeRadarGrid");
    if (dataCache.lifeRadar) {
      renderLifeRadar(dataCache.lifeRadar);
      return;
    }
    grid.innerHTML = '<div class="loading-state">در حال محاسبه فواصل زمانی و وضعیت موعدها...</div>';

    try {
      const res = await fetch("/api/life-tracker/insights", { headers: getHeaders() });
      if (!res.ok) throw new Error();
      const data = await res.json();
      dataCache.lifeRadar = data;
      renderLifeRadar(data);
    } catch (e) {
      renderRetryState(grid, "خطا در دریافت گزارش رادار", loadLifeRadar);
    }
  }

  function renderLifeRadar(data) {
    const grid = document.getElementById("lifeRadarGrid");
    if (!grid) return;
      const insights = data.insights || {};

      grid.innerHTML = "";
      let goodCnt = 0, nearCnt = 0, overdueCnt = 0;

      Object.entries(insights).forEach(([tName, item]) => {
        if (!item.has_data) return;

        let statusClass = "good";
        let statusText = "به‌موقع و عادی";
        if (item.badge === "🟡") {
          statusClass = "near";
          statusText = "نزدیک به موعد";
          nearCnt++;
        } else if (item.badge === "🔴") {
          statusClass = "overdue";
          statusText = "زمانشه / گذشته از موعد";
          overdueCnt++;
        } else {
          goodCnt++;
        }

        const card = document.createElement("div");
        card.className = `radar-card ${statusClass}`;

        const datesHtml = (item.recent_dates || [])
          .map((d) => `<span class="radar-date-badge">${toPersianDigits(d)}</span>`)
          .join("");

        card.innerHTML = `
          <div class="radar-top">
            <span class="radar-name"><span>${item.emoji}</span> <span>${tName}</span></span>
            <span class="radar-status-pill ${statusClass}">${item.badge} ${statusText}</span>
          </div>
          <div class="radar-details">
            <span class="stealth-blur-target">📅 آخرین بار: <b>${toPersianDigits(item.days_ago)} روز پیش</b> (${toPersianDigits(item.last_date_shamsi)})</span>
            <span>⏱️ میانگین: <b>${item.avg_interval ? `هر ${toPersianDigits(item.avg_interval)} روز` : "—"}</b></span>
          </div>
          <div class="radar-dates stealth-blur-target">
            <span style="font-size:10px; color:var(--hint-color); align-self:center;">دفعات اخیر:</span>
            ${datesHtml}
          </div>
        `;
        grid.appendChild(card);
      });

      document.getElementById("radarGoodCount").textContent = toPersianDigits(goodCnt);
      document.getElementById("radarNearCount").textContent = toPersianDigits(nearCnt);
      document.getElementById("radarOverdueCount").textContent = toPersianDigits(overdueCnt);

      if (grid.children.length === 0) {
        grid.innerHTML = '<div class="loading-state">داده‌ای برای تحلیل فواصل یافت نشد. با ثبت فعالیت‌ها رادار فعال خواهد شد.</div>';
      }
  }

  // ==========================================
  // 🌿 LIFE TRACKER CUSTOM DROPDOWNS & HISTORY
  // ==========================================
  function getHistoryDropdownMenu(dropdown) {
    if (!dropdown) return null;
    if (!dropdown._historyMenu) dropdown._historyMenu = dropdown.querySelector(".custom-dropdown-menu");
    return dropdown._historyMenu;
  }

  function closeHistoryDropdown(dropdown) {
    if (!dropdown) return;
    dropdown.classList.remove("open");
    dropdown.querySelector(".custom-dropdown-trigger")?.setAttribute("aria-expanded", "false");
    const menu = getHistoryDropdownMenu(dropdown);
    menu?.classList.remove("history-filter-portal-menu");
    if (menu) menu.style.cssText = "";
  }

  function openHistoryDropdown(dropdown, trigger) {
    document.querySelectorAll(".history-filter-grid .custom-dropdown.open").forEach((other) => {
      if (other !== dropdown) closeHistoryDropdown(other);
    });
    const menu = getHistoryDropdownMenu(dropdown);
    if (!menu) return;
    dropdown.classList.add("open");
    const bounds = trigger.getBoundingClientRect();
    const maxHeight = Math.min(280, Math.max(150, window.innerHeight - 24));
    if (menu.parentElement !== document.body) document.body.appendChild(menu);
    menu.classList.add("history-filter-portal-menu");
    menu.style.position = "fixed";
    menu.style.left = `${Math.max(8, bounds.left)}px`;
    menu.style.top = `${Math.min(window.innerHeight - 12, bounds.bottom + 6)}px`;
    menu.style.width = `${bounds.width}px`;
    menu.style.maxHeight = `${maxHeight}px`;
    menu.style.zIndex = "1000";
    trigger.setAttribute("aria-expanded", "true");
  }

  function initLifeHistoryFilterDropdown() {
    const dropdown = document.getElementById("lifeHistoryFilterDropdown");
    const trigger = document.getElementById("lifeHistoryFilterTrigger");
    if (!dropdown || !trigger) return;

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      if (dropdown.classList.contains("open")) closeHistoryDropdown(dropdown);
      else openHistoryDropdown(dropdown, trigger);
      haptic("light");
    });

    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target)) {
        closeHistoryDropdown(dropdown);
      }
    });
  }

  function populateHistoryFilter() {
    const menu = document.getElementById("lifeHistoryFilterMenu");
    const hiddenInput = document.getElementById("lifeHistoryFilter");
    const selectedSpan = document.getElementById("lifeHistoryFilterSelected");
    const dropdown = document.getElementById("lifeHistoryFilterDropdown");
    if (!menu || !lifeOptionsData?.all_types) return;

    menu.innerHTML = `
      <div class="custom-dropdown-item active" data-value="" role="option">
        <span class="item-title">✨ تمام فعالیت‌ها</span>
      </div>
    `;

    Object.keys(lifeOptionsData.all_types).forEach((t) => {
      const typeMeta = lifeOptionsData.all_types[t];
      const item = document.createElement("div");
      item.className = "custom-dropdown-item";
      item.setAttribute("data-value", t);
      item.setAttribute("role", "option");
      item.innerHTML = `<span class="item-title">${typeMeta.emoji} ${t}</span>`;
      menu.appendChild(item);
    });

    menu.querySelectorAll(".custom-dropdown-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const val = item.getAttribute("data-value") || "";
        const title = item.querySelector(".item-title")?.textContent || item.textContent;
        if (hiddenInput) hiddenInput.value = val;
        if (selectedSpan) selectedSpan.textContent = title;

        menu.querySelectorAll(".custom-dropdown-item").forEach((it) => it.classList.remove("active"));
        item.classList.add("active");
        closeHistoryDropdown(dropdown);
        const trigger = document.getElementById("lifeHistoryFilterTrigger");
        if (trigger) trigger.setAttribute("aria-expanded", "false");

        haptic("selection");
        lifeHistoryPage = 1;
        renderFilteredLifeHistory();
      });
    });
  }

  function populateHistoryModeFilter() {
    const menu = document.getElementById("lifeHistoryModeMenu");
    if (!menu) return;
    const currentMode = document.getElementById("lifeHistoryModeFilter")?.value || "";
    const modes = [...new Set(allLifeEntriesCache.flatMap((item) => item.modes || []).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "fa"));
    menu.innerHTML = `<div class="custom-dropdown-item ${currentMode ? "" : "active"}" data-value="" role="option"><span class="item-title">🎛️ تمام حالت‌ها</span></div>`;
    modes.forEach((mode) => {
      const item = document.createElement("div");
      item.className = `custom-dropdown-item${mode === currentMode ? " active" : ""}`;
      item.dataset.value = mode;
      item.setAttribute("role", "option");
      item.innerHTML = `<span class="item-title">🎛️ ${escapeReportText(mode)}</span>`;
      menu.appendChild(item);
    });
    const hiddenInput = document.getElementById("lifeHistoryModeFilter");
    const selectedSpan = document.getElementById("lifeHistoryModeSelected");
    const dropdown = document.getElementById("lifeHistoryModeDropdown");
    const trigger = document.getElementById("lifeHistoryModeTrigger");
    menu.querySelectorAll(".custom-dropdown-item").forEach((item) => {
      item.addEventListener("click", (event) => {
        event.stopPropagation();
        const value = item.dataset.value || "";
        if (hiddenInput) hiddenInput.value = value;
        if (selectedSpan) selectedSpan.textContent = item.querySelector(".item-title")?.textContent || "🎛️ تمام حالت‌ها";
        menu.querySelectorAll(".custom-dropdown-item").forEach((entry) => entry.classList.remove("active"));
        item.classList.add("active");
        closeHistoryDropdown(dropdown);
        lifeHistoryPage = 1;
        renderFilteredLifeHistory();
      });
    });
  }

  function initLifeHistoryModeDropdown() {
    const dropdown = document.getElementById("lifeHistoryModeDropdown");
    const trigger = document.getElementById("lifeHistoryModeTrigger");
    if (!dropdown || !trigger || dropdown.dataset.ready === "1") return;
    dropdown.dataset.ready = "1";
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      if (dropdown.classList.contains("open")) closeHistoryDropdown(dropdown);
      else openHistoryDropdown(dropdown, trigger);
    });
    document.addEventListener("click", (event) => {
      if (!dropdown.contains(event.target)) {
        closeHistoryDropdown(dropdown);
      }
    });
  }

  function initLifeHistoryPeriodDropdown() {
    const dropdown = document.getElementById("lifeHistoryPeriodDropdown");
    const trigger = document.getElementById("lifeHistoryPeriodTrigger");
    const menu = document.getElementById("lifeHistoryPeriodMenu");
    const hiddenInput = document.getElementById("lifeHistoryPeriodFilter");
    const selectedSpan = document.getElementById("lifeHistoryPeriodSelected");
    const customRow = document.getElementById("lifeCustomDateRangeRow");
    if (!dropdown || !trigger || !menu || !hiddenInput || !selectedSpan) return;

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      if (dropdown.classList.contains("open")) closeHistoryDropdown(dropdown);
      else openHistoryDropdown(dropdown, trigger);
      haptic("light");
    });

    menu.querySelectorAll(".custom-dropdown-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        e.stopPropagation();
        const val = item.getAttribute("data-value") || "all";
        const title = item.querySelector(".item-title")?.textContent || item.textContent;
        hiddenInput.value = val;
        selectedSpan.textContent = title;

        menu.querySelectorAll(".custom-dropdown-item").forEach((it) => it.classList.remove("active"));
        item.classList.add("active");
        closeHistoryDropdown(dropdown);

        haptic("selection");
        if (customRow) {
          customRow.style.display = val === "custom" ? "block" : "none";
        }
        lifeHistoryPage = 1;
        renderFilteredLifeHistory();
      });
    });

    document.addEventListener("click", (e) => {
      if (!dropdown.contains(e.target)) {
        closeHistoryDropdown(dropdown);
      }
    });
  }

  function initLifeHistoryControls() {
    const root = document.getElementById("life-sub-history");
    if (!root || root.dataset.controlsReady === "1") return;
    root.dataset.controlsReady = "1";
    initLifeHistoryModeDropdown();

    const filtersPanel = document.getElementById("lifeHistoryFiltersPanel");
    filtersPanel?.addEventListener("toggle", () => {
      const state = filtersPanel.querySelector(".history-filter-state");
      if (state) state.textContent = filtersPanel.open ? "فیلترها باز هستند" : "برای نمایش گزینه‌ها باز کنید";
      if (!filtersPanel.open) {
        ["lifeHistoryFilterDropdown", "lifeHistoryPeriodDropdown", "lifeHistoryModeDropdown"].forEach((id) => {
          closeHistoryDropdown(document.getElementById(id));
        });
      }
    });

    ["lifeHistorySearch", "lifeHistorySort"].forEach((id) => {
      document.getElementById(id)?.addEventListener(id === "lifeHistorySearch" ? "input" : "change", () => {
        lifeHistoryPage = 1;
        if (id === "lifeHistorySearch") {
          clearTimeout(lifeHistorySearchTimer);
          lifeHistorySearchTimer = setTimeout(() => renderFilteredLifeHistory(), 140);
        } else {
          renderFilteredLifeHistory();
        }
      });
    });

    document.querySelectorAll("[data-life-history-view]").forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        lifeHistoryView = button.dataset.lifeHistoryView || "date";
        lifeHistoryPage = 1;
        document.querySelectorAll("[data-life-history-view]").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        loadLifeHistory().then(() => renderFilteredLifeHistory()).catch(() => {});
      });
    });

    document.getElementById("btnResetLifeHistory")?.addEventListener("click", () => {
      const search = document.getElementById("lifeHistorySearch");
      const mode = document.getElementById("lifeHistoryModeFilter");
      const sort = document.getElementById("lifeHistorySort");
      const type = document.getElementById("lifeHistoryFilter");
      const period = document.getElementById("lifeHistoryPeriodFilter");
      if (search) search.value = "";
      if (mode) mode.value = "";
      if (sort) sort.value = "newest";
      if (type) type.value = "";
      if (period) period.value = "all";
      customLifeStartDate = null;
      customLifeEndDate = null;
      lifeHistoryPage = 1;
      const customRow = document.getElementById("lifeCustomDateRangeRow");
      if (customRow) customRow.style.display = "none";
      const typeLabel = document.getElementById("lifeHistoryFilterSelected");
      const periodLabel = document.getElementById("lifeHistoryPeriodSelected");
      if (typeLabel) typeLabel.textContent = "تمام فعالیت‌ها";
      if (periodLabel) periodLabel.textContent = "تمام تاریخچه";
      const modeLabel = document.getElementById("lifeHistoryModeSelected");
      if (modeLabel) modeLabel.textContent = "🎛️ تمام حالت‌ها";
      document.querySelectorAll("#lifeHistoryModeMenu .custom-dropdown-item").forEach((item) => item.classList.toggle("active", !item.dataset.value));
      document.querySelectorAll("#lifeHistoryFilterMenu .custom-dropdown-item, #lifeHistoryPeriodMenu .custom-dropdown-item").forEach((item) => item.classList.toggle("active", !item.dataset.value || item.dataset.value === "all"));
      renderFilteredLifeHistory();
    });

    document.getElementById("btnExportLifeHistory")?.addEventListener("click", () => {
      const rows = getFilteredLifeHistory();
      if (!rows.length) {
        showToast("داده‌ای برای خروجی وجود ندارد", "warning");
        return;
      }
      const csvRows = [["تاریخ", "فعالیت", "حالت‌ها", "توضیحات"]];
      rows.forEach((item) => csvRows.push([item.date_iso || "", item.type || "", (item.modes || []).join(" | "), item.notes || ""]));
      const csv = csvRows.map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")).join("\n");
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }));
      link.download = `notionyar-life-history-${getDateFromOffset(0)}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    });
  }

  // ==========================================
  // ✏️ LIFE TRACKER EDIT ENTRY MODAL
  // ==========================================
  let editLifeSelectedModes = [];

  function renderEditLifeModes(typeVal) {
    const container = document.getElementById("editLifeModesContainer");
    const grid = document.getElementById("editLifeModesGrid");
    if (!container || !grid) return;

    const typeMeta = lifeOptionsData?.all_types?.[typeVal];
    if (typeMeta && typeMeta.modes && typeMeta.modes.length > 0) {
      container.style.display = "block";
      grid.innerHTML = "";
      typeMeta.modes.forEach((m) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "mode-chip" + (editLifeSelectedModes.includes(m.name) ? " active" : "");
        chip.innerHTML = `<span>${m.emoji || "🔹"}</span> <span>${m.name}</span>`;
        chip.addEventListener("click", () => {
          const idx = editLifeSelectedModes.indexOf(m.name);
          if (idx > -1) {
            editLifeSelectedModes.splice(idx, 1);
            chip.classList.remove("active");
          } else {
            editLifeSelectedModes.push(m.name);
            chip.classList.add("active");
          }
          haptic("light");
        });
        grid.appendChild(chip);
      });
    } else {
      container.style.display = "none";
      grid.innerHTML = "";
      editLifeSelectedModes = [];
    }
  }

  function openLifeEditModal(item) {
    const modal = document.getElementById("lifeEditModal");
    if (!modal) return;

    document.getElementById("editLifeEntryId").value = item.id;
    document.getElementById("editLifeNotes").value = item.notes || "";

    let cleanIso = (item.date_iso || "").split("T")[0].split(" ")[0].trim();
    if (!cleanIso || !/^\d{4}-\d{2}-\d{2}$/.test(cleanIso)) {
      cleanIso = currentDateIso;
    }
    document.getElementById("editLifeDateIso").value = cleanIso;

    const dateDisplay = document.getElementById("editLifeDateDisplay");
    dateDisplay.textContent = `📅 ${formatIsoToJalaliDisplay(cleanIso)}`;

    if (Array.isArray(item.modes) && item.modes.length > 0) {
      editLifeSelectedModes = [...item.modes];
    } else if (item.mode && typeof item.mode === "string") {
      editLifeSelectedModes = item.mode.split("، ").map((s) => s.trim()).filter(Boolean);
    } else {
      editLifeSelectedModes = [];
    }

    const typeHidden = document.getElementById("editLifeType");
    const typeSelected = document.getElementById("editLifeTypeSelected");
    const typeMenu = document.getElementById("editLifeTypeMenu");
    const typeDropdown = document.getElementById("editLifeTypeDropdown");

    const currentType = item.type || "";
    typeHidden.value = currentType;
    const currentMeta = lifeOptionsData?.all_types?.[currentType];
    const currentEmoji = currentMeta?.emoji || item.emoji || "🌱";
    typeSelected.textContent = `${currentEmoji} ${currentType}`;

    if (typeMenu && lifeOptionsData?.all_types) {
      typeMenu.innerHTML = "";
      Object.keys(lifeOptionsData.all_types).forEach((t) => {
        const meta = lifeOptionsData.all_types[t];
        const it = document.createElement("div");
        it.className = "custom-dropdown-item" + (t === currentType ? " active" : "");
        it.setAttribute("data-value", t);
        it.setAttribute("role", "option");
        it.innerHTML = `<span class="item-title">${meta.emoji} ${t}</span>`;
        it.addEventListener("click", (e) => {
          e.stopPropagation();
          typeHidden.value = t;
          typeSelected.textContent = `${meta.emoji} ${t}`;
          typeMenu.querySelectorAll(".custom-dropdown-item").forEach((el) => el.classList.remove("active"));
          it.classList.add("active");
          if (typeDropdown) typeDropdown.classList.remove("open");
          const trig = document.getElementById("editLifeTypeTrigger");
          if (trig) trig.setAttribute("aria-expanded", "false");
          editLifeSelectedModes = [];
          renderEditLifeModes(t);
          haptic("selection");
        });
        typeMenu.appendChild(it);
      });
    }

    renderEditLifeModes(currentType);
    modal.style.display = "flex";
    haptic("light");
  }

  function initLifeEditModal() {
    const modal = document.getElementById("lifeEditModal");
    const closeBtn = document.getElementById("btnLifeEditModalClose");
    const cancelBtn = document.getElementById("btnCancelEditLife");
    const pickDateBtn = document.getElementById("btnEditLifePickDate");
    const typeDropdown = document.getElementById("editLifeTypeDropdown");
    const typeTrigger = document.getElementById("editLifeTypeTrigger");
    const form = document.getElementById("formEditLifeEntry");
    if (!modal) return;

    if (typeTrigger && typeDropdown) {
      typeTrigger.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = typeDropdown.classList.toggle("open");
        typeTrigger.setAttribute("aria-expanded", isOpen);
        haptic("light");
      });

      document.addEventListener("click", (e) => {
        if (!typeDropdown.contains(e.target)) {
          typeDropdown.classList.remove("open");
          typeTrigger.setAttribute("aria-expanded", "false");
        }
      });
    }

    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        modal.style.display = "none";
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        modal.style.display = "none";
      });
    }

    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.style.display = "none";
      }
    });

    if (pickDateBtn) {
      pickDateBtn.addEventListener("click", () => {
        openPersianDatePicker("edit_life");
      });
    }

    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const entryId = document.getElementById("editLifeEntryId")?.value;
        const typeVal = document.getElementById("editLifeType")?.value;
        const dateIso = document.getElementById("editLifeDateIso")?.value;
        const notes = document.getElementById("editLifeNotes")?.value?.trim() || "";

        if (!entryId || !typeVal) {
          showToast("لطفاً نوع فعالیت را مشخص کنید", "warning");
          return;
        }

        const saveBtn = document.getElementById("btnSaveEditLife");
        const origText = saveBtn ? saveBtn.textContent : "";
        if (saveBtn) {
          saveBtn.disabled = true;
          saveBtn.textContent = "در حال ذخیره...";
        }

        try {
          const res = await fetch(`/api/life-tracker/update/${entryId}`, {
            method: "PUT",
            headers: getHeaders(),
            body: JSON.stringify({
              event_type: typeVal,
              date_iso: dateIso || null,
              mode_list: editLifeSelectedModes,
              notes: notes,
            }),
          });

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || "خطا در ویرایش رکورد");
          }

          showToast("لاگ روزمرگی با موفقیت به‌روزرسانی شد! ✨", "success");
          invalidateDataCache("lifeHistory", "lifeRadar");
          haptic("success");
          modal.style.display = "none";
          await loadLifeHistory();
          if (typeof loadLifeRadar === "function") loadLifeRadar();
        } catch (err) {
          console.error(err);
          showToast(err.message || "خطا در ذخیره ویرایش", "error");
          haptic("error");
        } finally {
          if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = origText;
          }
        }
      });
    }
  }

  async function loadLifeHistory() {
    const list = document.getElementById("lifeHistoryList");
    if (!list) return;
    if (dataCache.lifeHistory) {
      allLifeEntriesCache = dataCache.lifeHistory;
      populateHistoryModeFilter();
      renderFilteredLifeHistory();
      return;
    }
    if (lifeHistoryLoadPromise) return lifeHistoryLoadPromise;
    list.innerHTML = '<div class="loading-state">در حال دریافت لاگ‌ها...</div>';

    lifeHistoryLoadPromise = (async () => {
      try {
        const res = await fetch("/api/life-tracker/history", { headers: getHeaders() });
        if (!res.ok) throw new Error();
        const data = await res.json();
        allLifeEntriesCache = Array.isArray(data.entries) ? data.entries : [];
        dataCache.lifeHistory = allLifeEntriesCache;
        populateHistoryModeFilter();
        renderFilteredLifeHistory();
      } catch (e) {
        renderRetryState(list, "خطا در بارگذاری تاریخچه", () => loadLifeHistory());
        throw e;
      } finally {
        lifeHistoryLoadPromise = null;
      }
    })();
    return lifeHistoryLoadPromise;
  }

  function getFilteredLifeHistory() {
    const actFilter = document.getElementById("lifeHistoryFilter")?.value || "";
    const periodFilter = document.getElementById("lifeHistoryPeriodFilter")?.value || "all";
    const modeFilter = document.getElementById("lifeHistoryModeFilter")?.value || "";
    const search = document.getElementById("lifeHistorySearch")?.value?.trim().toLocaleLowerCase("fa") || "";
    const sort = document.getElementById("lifeHistorySort")?.value || "newest";
    const cutoff7d = getDateFromOffset(6);
    const cutoff30d = getDateFromOffset(29);
    const currentMonthPrefix = getDateFromOffset(0).slice(0, 7);

    const filtered = allLifeEntriesCache.filter((item) => {
      if (actFilter && item.type !== actFilter) return false;
      if (modeFilter && !(item.modes || []).includes(modeFilter)) return false;
      if (search) {
        const haystack = [item.type, item.mode, item.notes, item.date, ...(item.modes || [])].join(" ").toLocaleLowerCase("fa");
        if (!haystack.includes(search)) return false;
      }
      if (!item.date_iso) return true;
      if (periodFilter === "7d" && item.date_iso < cutoff7d) return false;
      if (periodFilter === "30d" && item.date_iso < cutoff30d) return false;
      if (periodFilter === "month" && !item.date_iso.startsWith(currentMonthPrefix)) return false;
      if (periodFilter === "custom") {
        if (customLifeStartDate && item.date_iso < customLifeStartDate) return false;
        if (customLifeEndDate && item.date_iso > customLifeEndDate) return false;
      }
      return true;
    });

    return filtered.sort((a, b) => {
      if (sort === "oldest") return (a.date_iso || "").localeCompare(b.date_iso || "");
      if (sort === "type") return (a.type || "").localeCompare(b.type || "", "fa") || (b.date_iso || "").localeCompare(a.date_iso || "");
      return (b.date_iso || "").localeCompare(a.date_iso || "");
    });
  }

  function createLifeHistoryRow(item) {
    const div = document.createElement("div");
    div.className = "timeline-item history-entry-row";
    div.innerHTML = `
      <div class="history-entry-main">
        <div class="history-entry-title">${escapeReportText(item.type)} ${item.mode ? `<span>${escapeReportText(item.mode)}</span>` : ""}</div>
        <div class="history-entry-meta">
          <span class="stealth-blur-target">${escapeReportText(toPersianDigits(item.date))}</span>
          ${item.notes ? `<span class="stealth-blur-target">${escapeReportText(item.notes)}</span>` : ""}
        </div>
      </div>
      <div class="history-entry-actions">
        <button type="button" class="btn-icon btn-item-edit" title="ویرایش رکورد" aria-label="ویرایش رکورد"><i data-lucide="pencil"></i></button>
        <button type="button" class="btn-icon btn-item-delete" title="حذف رکورد" aria-label="حذف رکورد"><i data-lucide="trash-2"></i></button>
      </div>`;

    div.querySelector(".btn-item-edit")?.addEventListener("click", () => openLifeEditModal(item));
    div.querySelector(".btn-item-delete")?.addEventListener("click", async () => {
      if (!confirm(`آیا از حذف لاگ «${item.type}» مطمئن هستید؟`)) return;
      haptic("warning");
      try {
        const response = await fetch(`/api/life-tracker/delete/${item.id}`, { method: "DELETE", headers: getHeaders() });
        if (!response.ok) throw new Error();
        showToast("رکورد حذف شد", "success");
        allLifeEntriesCache = allLifeEntriesCache.filter((entry) => entry.id !== item.id);
        dataCache.lifeHistory = allLifeEntriesCache;
        renderFilteredLifeHistory();
      } catch (error) {
        showToast("خطا در حذف رکورد", "error");
      }
    });
    return div;
  }

  function renderLifeHistorySummary(filtered) {
    const target = document.getElementById("lifeHistorySummary");
    if (!target) return;
    const activeDays = new Set(filtered.map((item) => item.date_iso).filter(Boolean)).size;
    const typeCounts = filtered.reduce((acc, item) => {
      acc[item.type] = (acc[item.type] || 0) + 1;
      return acc;
    }, {});
    const topType = Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0];
    target.innerHTML = `
      <div class="history-summary-item"><strong>${toPersianDigits(filtered.length)}</strong><span>رکورد</span></div>
      <div class="history-summary-item"><strong>${toPersianDigits(activeDays)}</strong><span>روز فعال</span></div>
      <div class="history-summary-item"><strong>${toPersianDigits(Object.keys(typeCounts).length)}</strong><span>فعالیت متفاوت</span></div>
      <div class="history-summary-item"><strong>${escapeReportText(topType?.[0] || "—")}</strong><span>${topType ? `${toPersianDigits(topType[1])} بار` : "پرتکرارترین"}</span></div>`;
  }

  function renderFilteredLifeHistory() {
    const list = document.getElementById("lifeHistoryList");
    if (!list) return;
    list.dataset.view = lifeHistoryView;
    const filtered = getFilteredLifeHistory();
    renderLifeHistorySummary(filtered);
    const resultCount = document.getElementById("lifeHistoryResultCount");
    if (resultCount) resultCount.textContent = `${toPersianDigits(filtered.length)} نتیجه`;
    const totalPages = Math.max(1, Math.ceil(filtered.length / LIFE_HISTORY_PAGE_SIZE));
    lifeHistoryPage = Math.min(Math.max(1, lifeHistoryPage), totalPages);
    const pageItems = filtered.slice((lifeHistoryPage - 1) * LIFE_HISTORY_PAGE_SIZE, lifeHistoryPage * LIFE_HISTORY_PAGE_SIZE);
    renderLifeHistoryPagination(totalPages, filtered.length);

    list.innerHTML = "";
    if (filtered.length === 0) {
      list.innerHTML = '<div class="loading-state">موردی متناسب با فیلتر یافت نشد</div>';
      return;
    }

    if (lifeHistoryView === "list") {
      pageItems.forEach((item) => list.appendChild(createLifeHistoryRow(item)));
      return;
    }

    try {
      const grouped = new Map();
      pageItems.forEach((item) => {
        const normalizedDate = String(item.date_iso || item.date || "").split("T")[0].split(" ")[0] || "بدون تاریخ";
        const key = lifeHistoryView === "type" ? (item.type || "بدون دسته") : normalizedDate;
        if (!grouped.has(key)) grouped.set(key, []);
        grouped.get(key).push(item);
      });
      grouped.forEach((items, key) => {
        const section = document.createElement("section");
        section.className = "history-group";
        const label = lifeHistoryView === "type" ? key : (items[0]?.date || formatIsoToJalaliDisplay(key));
        section.innerHTML = `<header><strong>${escapeReportText(toPersianDigits(label))}</strong><span>${toPersianDigits(items.length)} مورد</span></header>`;
        items.forEach((item) => section.appendChild(createLifeHistoryRow(item)));
        list.appendChild(section);
      });
      if (!list.children.length) {
        list.innerHTML = '<div class="loading-state">موردی برای این نوع نمایش وجود ندارد</div>';
      }
    } catch (error) {
      console.error("Could not render grouped life history", error);
      list.dataset.view = "list";
      pageItems.forEach((item) => list.appendChild(createLifeHistoryRow(item)));
    }
  }

  function renderLifeHistoryPagination(totalPages, totalItems) {
    const pagination = document.getElementById("lifeHistoryPagination");
    if (!pagination) return;
    pagination.hidden = totalPages <= 1;
    if (totalPages <= 1) {
      pagination.innerHTML = "";
      return;
    }
    const start = (lifeHistoryPage - 1) * LIFE_HISTORY_PAGE_SIZE + 1;
    const end = Math.min(totalItems, lifeHistoryPage * LIFE_HISTORY_PAGE_SIZE);
    pagination.innerHTML = `
      <button type="button" class="btn-step" data-history-page="prev" ${lifeHistoryPage <= 1 ? "disabled" : ""}><i data-lucide="chevron-right"></i><span>قبلی</span></button>
      <span>${toPersianDigits(start)} تا ${toPersianDigits(end)} از ${toPersianDigits(totalItems)} · صفحه ${toPersianDigits(lifeHistoryPage)} از ${toPersianDigits(totalPages)}</span>
      <button type="button" class="btn-step" data-history-page="next" ${lifeHistoryPage >= totalPages ? "disabled" : ""}><span>بعدی</span><i data-lucide="chevron-left"></i></button>`;
    pagination.querySelector('[data-history-page="prev"]')?.addEventListener("click", () => {
      lifeHistoryPage -= 1;
      renderFilteredLifeHistory();
      document.getElementById("lifeHistorySummary")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    pagination.querySelector('[data-history-page="next"]')?.addEventListener("click", () => {
      lifeHistoryPage += 1;
      renderFilteredLifeHistory();
      document.getElementById("lifeHistorySummary")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  // ==========================================
  // 6. HABITS TRACKER (STEALTH & BINARY HABITS)
  // ==========================================
  function setupStealthModeUI() {
    const tabHabits = document.getElementById("tab-habits");
    const tabSpiritual = document.getElementById("tab-spiritual");
    const btnToggle = document.getElementById("btnToggleStealth");

    function applyStealthState() {
      document.body.classList.toggle("stealth-active", isStealthMode);
      tabHabits?.classList.toggle("stealth-active", isStealthMode);
      tabSpiritual?.classList.toggle("stealth-active", isStealthMode);
      btnToggle?.classList.toggle("active", isStealthMode);
    }

    applyStealthState();

    btnToggle?.addEventListener("click", () => {
      isStealthMode = !isStealthMode;
      localStorage.setItem("notionyar_stealth", isStealthMode);
      applyStealthState();
      haptic("medium");
      showToast(isStealthMode ? "حالت مخفی فعال شد 🕶️" : "حالت عادی فعال شد 👁️", "info");

      // Reload habits, analytics, and spiritual day to reflect state
      loadHabitsForDate(currentHabitDateIso);
      loadHabitsAnalytics();
      loadSpiritualDay(currentSpiritualDateIso);
    });


    // Interactive Click-to-Reveal in Stealth Mode
    document.addEventListener("click", (e) => {
      if (!isStealthMode) return;
      const target = e.target.closest(".stealth-blur-target, .timeline-item, .life-tile, .mode-chip, .grat-item-row, .streak-value, .card-title, .section-subtitle, .analytics-section-title, .habit-cat-title, .journal-block-title, .btn-sp-magic-bulk, .btn-sp-range-bulk, .btn-sp-reset, .btn-prayer-state, .badge-ada, .badge-qaza, .badge-pending, .selected-date-badge, .sp-stat-card, .progress-hero-container, .habit-inline-detail-box");
      if (target && !e.target.closest(".btn-item-delete, button.btn-item-delete")) {
        target.classList.toggle("revealed");
        haptic("light");
      }
    });

  }

  // Habit quick offset buttons (امروز / دیروز / پریروز)
  document.querySelectorAll("[data-habit-offset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-habit-offset]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const offset = parseInt(btn.getAttribute("data-habit-offset"), 10);
      currentHabitDateIso = getDateFromOffset(offset);
      loadHabitsForDate(currentHabitDateIso);
      haptic("light");
    });
  });

  async function loadHabitsForDate(dateIso) {
    const container = document.getElementById("habitsGroupedContainer");
    if (dataCache.habits.has(dateIso)) {
      habitDayData = dataCache.habits.get(dateIso);
      renderHabitDay(habitDayData);
      return;
    }
    container.innerHTML = '<div class="loading-state">در حال دریافت وضعیت عادات...</div>';

    try {
      const res = await fetch(`/api/habits/day?date_iso=${dateIso}`, { headers: getHeaders() });
      if (!res.ok) throw new Error("خطا در دریافت اطلاعات عادات");

      habitDayData = await res.json();
      dataCache.habits.set(dateIso, habitDayData);

      // Check for daily auto-apply preset on today
      const todayIso = getDateFromOffset(0);
      const autoPresetId = localStorage.getItem("notionyar_auto_apply_preset_id");
      const lastAutoDate = localStorage.getItem("notionyar_last_auto_applied_date");

      if (dateIso === todayIso && autoPresetId && lastAutoDate !== todayIso && habitDayData?.page_id && (habitDayData.completed_count === 0)) {
        const customPresets = getCustomPresets();
        const autoPreset = customPresets.find((p) => p.id === autoPresetId);
        if (autoPreset && autoPreset.habits && Object.keys(autoPreset.habits).length > 0) {
          localStorage.setItem("notionyar_last_auto_applied_date", todayIso);
          try {
            await fetch("/api/habits/batch-update", {
              method: "POST",
              headers: getHeaders(),
              body: JSON.stringify({
                page_id: habitDayData.page_id,
                updates: autoPreset.habits
              })
            });
            showToast(`⭐ قالب خودکار «${autoPreset.title}» برای امروز اعمال شد`, "success");
            const refreshedRes = await fetch(`/api/habits/day?date_iso=${dateIso}`, { headers: getHeaders() });
            if (refreshedRes.ok) habitDayData = await refreshedRes.json();
          } catch (e) {
            console.error("Auto apply preset error:", e);
          }
        }
      }

      document.getElementById("habitDateTitle").textContent = toPersianDigits(habitDayData.jalali_title);
      document.getElementById("habitPercent").textContent = `${toPersianDigits(habitDayData.progress_percent)}٪`;
      document.getElementById("habitCountDisplay").textContent = `${toPersianDigits(habitDayData.completed_count)} از ${toPersianDigits(habitDayData.total_habits)}`;

      document.getElementById("habitCheerleader").textContent = habitDayData.cheerleader;

      const fillPct = `${habitDayData.progress_percent}%`;
      document.getElementById("habitProgressFill").style.width = fillPct;
      document.querySelector(".progress-ring-box")?.style.setProperty("--p-fill", fillPct);

      // Fill Journal Inputs (Separate full-width rows)
      const bookInput = document.getElementById("habitBook");
      if (bookInput) bookInput.value = habitDayData.book_detail || "";

      const quranInput = document.getElementById("habitQuran");
      if (quranInput) quranInput.value = habitDayData.quran_detail || "";

      const notesInput = document.getElementById("habitNotes");
      if (notesInput) notesInput.value = habitDayData.notes || "";

      // Initialize Gratitude Items
      initGratitudeItems(habitDayData);

      renderGroupedHabits(habitDayData.categories);
      autoExpandTextareas();
    } catch (err) {
      renderRetryState(container, err.message || "خطا در بارگذاری عادات", () => loadHabitsForDate(dateIso));
    }
  }

  function renderHabitDay(habitDayData) {
      document.getElementById("habitDateTitle").textContent = toPersianDigits(habitDayData.jalali_title);
      document.getElementById("habitPercent").textContent = `${toPersianDigits(habitDayData.progress_percent)}٪`;
      document.getElementById("habitCountDisplay").textContent = `${toPersianDigits(habitDayData.completed_count)} از ${toPersianDigits(habitDayData.total_habits)}`;
      document.getElementById("habitCheerleader").textContent = habitDayData.cheerleader;
      const fillPct = `${habitDayData.progress_percent}%`;
      document.getElementById("habitProgressFill").style.width = fillPct;
      document.querySelector(".progress-ring-box")?.style.setProperty("--p-fill", fillPct);
      const bookInput = document.getElementById("habitBook");
      if (bookInput) bookInput.value = habitDayData.book_detail || "";
      const quranInput = document.getElementById("habitQuran");
      if (quranInput) quranInput.value = habitDayData.quran_detail || "";
      const notesInput = document.getElementById("habitNotes");
      if (notesInput) notesInput.value = habitDayData.notes || "";
      initGratitudeItems(habitDayData);
      renderGroupedHabits(habitDayData.categories);
      autoExpandTextareas();
  }

  // Render Habits with Binary Check (Item 2) and Stealth Mode (Items 8, 11)
  function renderGroupedHabits(categories) {
    const container = document.getElementById("habitsGroupedContainer");
    container.innerHTML = "";

    Object.values(categories).forEach((cat) => {
      if (!cat.habits || cat.habits.length === 0) return;

      const groupDiv = document.createElement("div");
      groupDiv.className = "habit-cat-group";

      const title = document.createElement("div");
      title.className = "habit-cat-title";
      title.innerHTML = `<span>${cat.emoji}</span> <span>${cat.title}</span>`;
      groupDiv.appendChild(title);

      cat.habits.forEach((h) => {
        const card = document.createElement("div");
        const isDone = h.is_done;
        let cardStatusClass = isDone ? "done" : "";
        if (h.status === "2-🏃‍♂️ نیمه‌کامل" || h.status === "3-🐢 سبک") cardStatusClass = "partial";
        if (h.status === "فریز") cardStatusClass = "frozen";

        card.className = `habit-card ${cardStatusClass} stealth-blur-target`;

        const codeTag = `[${h.code || "HBT"}]`;

        // Item 2: Binary habit check (مرتب کردن تخت و سلام)
        const isBinary = h.is_binary || h.key === "mb" || h.key === "sl";

        let levelBtnText = "تنظیم کیفیت";
        if (isBinary) {
          levelBtnText = isDone ? "انجام شد ✓" : "ثبت انجام";
        } else if (h.status) {
          levelBtnText = h.status.replace(/^[0-9]-/, "");
        }

        // Stealth level mask
        const stealthLevelText = isDone ? "[OK]" : "[--]";

        card.innerHTML = `
          <div class="habit-check-circle">${isDone ? "✓" : ""}</div>
          <div class="habit-info">
            <div class="habit-name-row">
              <span class="habit-emoji">${h.emoji}</span>
              <span class="habit-title">
                <span class="habit-title-normal">${h.name}</span>
                <span class="habit-title-code">${codeTag}</span>
              </span>
            </div>
          </div>
          <div class="habit-actions-inline">
            <button class="btn-habit-level ${isDone ? "active" : ""}">
              <span class="habit-title-normal">${levelBtnText}</span>
              <span class="habit-title-code">${stealthLevelText}</span>
            </button>
          </div>
        `;

        // Tap on checkmark
        card.querySelector(".habit-check-circle").addEventListener("click", (e) => {
          e.stopPropagation();
          haptic("light");
          const nextVal = isDone ? null : "1-💪 کامل";
          setHabitStatus(h, nextVal);
        });

        // Tap on level button
        card.querySelector(".btn-habit-level").addEventListener("click", (e) => {
          e.stopPropagation();
          openHabitLevelModal(h);
        });

        // Inline input box for Quran reading (rq)
        if (h.key === "rq") {
          const detailBox = document.createElement("div");
          detailBox.className = "habit-inline-detail-box";
          const currentVal = habitDayData?.quran_detail || "";
          detailBox.innerHTML = `
            <input type="text" class="habit-inline-input" placeholder="📖 صفحه، سوره یا آیات خوانده‌شده..." value="${escapeReportText(currentVal)}">
            <button type="button" class="btn-inline-save">ذخیره</button>
          `;

          const inputEl = detailBox.querySelector(".habit-inline-input");
          const saveBtn = detailBox.querySelector(".btn-inline-save");

          saveBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const textVal = inputEl.value.trim();
            if (!habitDayData?.page_id) return;
            haptic("medium");
            saveBtn.disabled = true;
            saveBtn.textContent = "⏳...";

            try {
              const res = await fetch("/api/habits/update-text", {
                method: "POST",
                headers: getHeaders(),
                body: JSON.stringify({
                  page_id: habitDayData.page_id,
                  field: "quran",
                  text: textVal,
                  date_iso: currentHabitDateIso
                })
              });
              if (!res.ok) throw new Error("خطا در ذخیره تلاوت قرآن");
              showToast("جزئیات تلاوت قرآن در نوشن ثبت و سینک شد! 📖", "success");

              if (habitDayData) habitDayData.quran_detail = textVal;
              invalidateDataCache("habits");
              const globalQuranInput = document.getElementById("habitQuran");
              if (globalQuranInput) globalQuranInput.value = textVal;

              await loadHabitsForDate(currentHabitDateIso);
            } catch (err) {
              showToast(err.message, "error");
            } finally {
              saveBtn.disabled = false;
              saveBtn.textContent = "ذخیره";
            }
          });

          card.appendChild(detailBox);
        }

        // Inline input box for Book reading (rb)
        if (h.key === "rb") {
          const detailBox = document.createElement("div");
          detailBox.className = "habit-inline-detail-box";
          const currentVal = habitDayData?.book_detail || "";
          detailBox.innerHTML = `
            <input type="text" class="habit-inline-input" placeholder="📚 نام کتاب، فصل یا صفحات مطالعه‌شده..." value="${escapeReportText(currentVal)}">
            <button type="button" class="btn-inline-save">ذخیره</button>
          `;

          const inputEl = detailBox.querySelector(".habit-inline-input");
          const saveBtn = detailBox.querySelector(".btn-inline-save");

          saveBtn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const textVal = inputEl.value.trim();
            if (!habitDayData?.page_id) return;
            haptic("medium");
            saveBtn.disabled = true;
            saveBtn.textContent = "⏳...";

            try {
              const res = await fetch("/api/habits/update-text", {
                method: "POST",
                headers: getHeaders(),
                body: JSON.stringify({
                  page_id: habitDayData.page_id,
                  field: "book",
                  text: textVal,
                  date_iso: currentHabitDateIso
                })
              });
              if (!res.ok) throw new Error("خطا در ذخیره مطالعه کتاب");
              showToast("جزئیات مطالعه کتاب ذخیره شد! 📚", "success");
              invalidateDataCache("habits");

              if (habitDayData) habitDayData.book_detail = textVal;
              const globalBookInput = document.getElementById("habitBook");
              if (globalBookInput) globalBookInput.value = textVal;

              await loadHabitsForDate(currentHabitDateIso);
            } catch (err) {
              showToast(err.message, "error");
            } finally {
              saveBtn.disabled = false;
              saveBtn.textContent = "ذخیره";
            }
          });

          card.appendChild(detailBox);
        }

        if (h.key === "rq" || h.key === "rb") {
          card.classList.add("has-details");
          const toggle = document.createElement("button");
          toggle.type = "button";
          toggle.className = "habit-detail-toggle";
          toggle.setAttribute("aria-expanded", "false");
          toggle.innerHTML = '<span>جزئیات</span><i data-lucide="chevron-down"></i>';
          const detailBox = card.querySelector(".habit-inline-detail-box");
          const actions = card.querySelector(".habit-actions-inline");
          if (actions) actions.appendChild(toggle);
          else card.insertBefore(toggle, detailBox);

          const toggleDetails = () => {
            const isOpen = card.classList.toggle("details-open");
            toggle.setAttribute("aria-expanded", String(isOpen));
            haptic("light");
          };
          toggle.addEventListener("click", (event) => {
            event.stopPropagation();
            toggleDetails();
          });
          card.addEventListener("click", (event) => {
            if (event.target.closest("button, input")) return;
            toggleDetails();
          });
        }

        groupDiv.appendChild(card);
      });


      container.appendChild(groupDiv);
    });
  }

  async function setHabitStatus(habitObj, selectVal) {
    if (!habitDayData?.page_id) {
      showToast("خطا در یافتن روز انتخابی", "error");
      return;
    }

    // Backup for rollback on network failure
    const prevStatus = habitObj.status;
    const prevIsDone = habitObj.is_done;

    // 1. Optimistic in-memory update (0ms immediate UI response)
    const doneValues = ["1-💪 کامل", "2-🏃‍♂️ نیمه‌کامل", "3-🐢 سبک"];
    habitObj.status = selectVal;
    habitObj.is_done = doneValues.includes(selectVal);

    let doneCount = 0;
    let totalCount = 0;
    if (habitDayData.categories) {
      Object.values(habitDayData.categories).forEach((cat) => {
        (cat.habits || []).forEach((h) => {
          totalCount++;
          if (h.is_done) doneCount++;
        });
      });
    }

    const totalHabits = totalCount || 13;
    const progressPercent = Math.round((doneCount / totalHabits) * 100);
    habitDayData.completed_count = doneCount;
    habitDayData.total_habits = totalHabits;
    habitDayData.progress_percent = progressPercent;

    let cheerleader = "هر روز یک فرصت جدیده، شروع کن! 🌱";
    if (progressPercent >= 100) cheerleader = "عالی! امروز رو ترکوندی! 🎉";
    else if (progressPercent >= 70) cheerleader = "فوق‌العاده! بیش از نصف راه رو رفتی! 💪";
    else if (progressPercent >= 40) cheerleader = "خوبه، ادامه بده! قدم‌های کوچک مهمه! ✨";
    habitDayData.cheerleader = cheerleader;

    // Immediate DOM update
    renderGroupedHabits(habitDayData.categories);
    const percentEl = document.getElementById("habitPercent");
    if (percentEl) percentEl.textContent = `${toPersianDigits(progressPercent)}٪`;
    const countEl = document.getElementById("habitCountDisplay");
    if (countEl) countEl.textContent = `${toPersianDigits(doneCount)} از ${toPersianDigits(totalHabits)}`;
    const cheerEl = document.getElementById("habitCheerleader");
    if (cheerEl) cheerEl.textContent = cheerleader;

    const fillPct = `${progressPercent}%`;
    const fillEl = document.getElementById("habitProgressFill");
    if (fillEl) fillEl.style.width = fillPct;
    document.querySelector(".progress-ring-box")?.style.setProperty("--p-fill", fillPct);

    // 2. Asynchronous backend sync
    try {
      const res = await fetch("/api/habits/update-status", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          page_id: habitDayData.page_id,
          habit_prop: habitObj.prop,
          select_val: selectVal,
        }),
      });

      if (!res.ok) throw new Error();
    } catch (e) {
      // Revert optimistic changes on failure
      habitObj.status = prevStatus;
      habitObj.is_done = prevIsDone;
      renderGroupedHabits(habitDayData.categories);
      showToast("خطا در همگام‌سازی با نوشن", "error");
    }
  }

  // Bulk Complete Button
  document.getElementById("btnBulkComplete")?.addEventListener("click", async () => {
    if (!habitDayData?.page_id) return;
    if (!confirm("آیا مایلید تمام عادات امروز به عنوان «کامل» ثبت شوند؟")) return;

    haptic("medium");
    showToast("در حال تکمیل تمام عادات...", "info");

    try {
      const res = await fetch("/api/habits/bulk-complete", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ page_id: habitDayData.page_id }),
      });
      if (!res.ok) throw new Error();
      showToast("تبریک! تمام عادات ثبت شدند 🚀", "success");
      invalidateDataCache("habits", "habitAnalytics");
      loadHabitsForDate(currentHabitDateIso);
    } catch (e) {
      showToast("خطا در تکمیل خودکار عادات", "error");
    }
  });

  // Modal Level Selector with Binary Support (Item 2)
  function openHabitLevelModal(habitObj) {
    const modal = document.getElementById("habitLevelModal");
    const title = document.getElementById("modalHabitTitle");
    const body = document.getElementById("modalLevelOptions");

    title.textContent = `${habitObj.emoji} ${habitObj.name} - انتخاب وضعیت`;
    body.innerHTML = "";

    const isBinary = habitObj.is_binary || habitObj.key === "mb" || habitObj.key === "sl";

    const options = isBinary
      ? [
          { key: "1-💪 کامل", label: "💪 کامل", desc: habitObj.levels?.v1 || "انجام با بالاترین کیفیت" },
          { key: "4-❌ با دلیل", label: "❌ عدم انجام با دلیل", desc: "ثبت با عذر موجه" },
          { key: "5-⛔ بدون دلیل", label: "⛔ عدم انجام بدون دلیل", desc: "فراموشی یا تنبلی" },
          { key: null, label: "⚪ پاک کردن وضعیت", desc: "حذف کامل ثبت برای امروز" },
        ]
      : [
          { key: "1-💪 کامل", label: "💪 کامل", desc: habitObj.levels?.v1 || "انجام با بالاترین کیفیت" },
          { key: "2-🏃‍♂️ نیمه‌کامل", label: "🏃‍♂️ نیمه‌کامل", desc: habitObj.levels?.v2 || "کیفیت استاندارد" },
          { key: "3-🐢 سبک", label: "🐢 سبک", desc: habitObj.levels?.v3 || "حداقل اجرای ممکن" },
          { key: "4-❌ با دلیل", label: "❌ عدم انجام با دلیل", desc: "ثبت با عذر موجه" },
          { key: "5-⛔ بدون دلیل", label: "⛔ عدم انجام بدون دلیل", desc: "فراموشی یا تنبلی" },
          { key: null, label: "⚪ پاک کردن وضعیت", desc: "حذف کامل ثبت برای امروز" },
        ];

    options.forEach((opt) => {
      const btn = document.createElement("button");
      btn.className = "modal-option-btn";
      btn.innerHTML = `
        <div style="text-align:right;">
          <div>${opt.label}</div>
          <div style="font-size:11px; color:var(--hint-color); font-weight:normal;">${opt.desc}</div>
        </div>
        ${habitObj.status === opt.key ? "✓" : ""}
      `;
      btn.addEventListener("click", () => {
        modal.style.display = "none";
        haptic("light");
        setHabitStatus(habitObj, opt.key);
      });
      body.appendChild(btn);
    });

    modal.style.display = "flex";
  }

  document.getElementById("btnModalClose")?.addEventListener("click", () => {
    document.getElementById("habitLevelModal").style.display = "none";
  });

  // ==========================================
  // 7. HABIT PRESETS & BUILDER
  // ==========================================
  const ALL_HABIT_ITEMS = [
    { key: "bt", prop: "Brush Teeth", fa: "مسواک", emoji: "🪥", is_binary: false },
    { key: "fr", prop: "Face Routine", fa: "روتین پوستی", emoji: "🧖", is_binary: false },
    { key: "mb", prop: "Make the Bed", fa: "مرتب‌کردن تخت", emoji: "🛏️", is_binary: true },
    { key: "ex", prop: "Exercise", fa: "ورزش", emoji: "🏃", is_binary: false },
    { key: "md", prop: "Meditation", fa: "مدیتیشن", emoji: "🧘", is_binary: false },
    { key: "gr", prop: "Gratitude", fa: "شکرگزاری", emoji: "🌸", is_binary: false },
    { key: "rb", prop: "Read Book", fa: "کتاب‌خوانی", emoji: "📚", is_binary: false },
    { key: "rq", prop: "Read Holy Quran", fa: "تلاوت قرآن", emoji: "📖", is_binary: false },
    { key: "sl", prop: "Salam", fa: "سلام", emoji: "🕊️", is_binary: true },
    { key: "es", prop: "Esteghfar", fa: "استغفار", emoji: "📿", is_binary: false },
    { key: "ps", prop: "Pray After Salah", fa: "تعقیبات نماز", emoji: "🤲", is_binary: false },
    { key: "bp", prop: "Bedtime Prayer", fa: "دعای قبل خواب", emoji: "🌙", is_binary: false },
    { key: "sg", prop: "Spritual Gift", fa: "هدیه معنوی", emoji: "🎁", is_binary: false }
  ];

  const DEFAULT_PRESETS = [];

  function getCustomPresets() {
    try {
      const saved = localStorage.getItem("notionyar_habit_presets");
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      return [];
    }
  }

  function saveCustomPresets(list) {
    try {
      localStorage.setItem("notionyar_habit_presets", JSON.stringify(list));
    } catch (e) {}
  }

  const presetModal = document.getElementById("presetModal");
  let editingPresetId = null;
  let builderHabitsState = {};

  function showPresetView(view) {
    const listView = document.getElementById("presetViewList");
    const builderView = document.getElementById("presetViewBuilder");
    const modalTitle = document.getElementById("presetModalTitle");

    if (view === "builder") {
      if (listView) listView.style.display = "none";
      if (builderView) builderView.style.display = "block";
      if (modalTitle) modalTitle.textContent = editingPresetId ? "✏️ ویرایش قالب سفارشی" : "➕ ساخت قالب جدید با لیست عادات";
    } else {
      if (builderView) builderView.style.display = "none";
      if (listView) listView.style.display = "block";
      if (modalTitle) modalTitle.textContent = "📑 قالب‌های سفارشی ثبت عادات";
    }
  }

  function openPresetBuilder(presetToEdit = null) {
    editingPresetId = presetToEdit ? presetToEdit.id : null;
    builderHabitsState = presetToEdit?.habits ? { ...presetToEdit.habits } : {};

    const titleInput = document.getElementById("builderPresetTitle");
    if (titleInput) {
      titleInput.value = presetToEdit ? presetToEdit.title.replace(/^✨\s*/, "") : "";
    }

    renderPresetBuilderHabits();
    showPresetView("builder");
    haptic("light");
  }

  function renderPresetBuilderHabits() {
    const list = document.getElementById("presetBuilderHabitsList");
    if (!list) return;
    list.innerHTML = "";

    ALL_HABIT_ITEMS.forEach((h) => {
      const row = document.createElement("div");
      row.className = "preset-builder-habit-row";

      const currentVal = builderHabitsState[h.prop] || null;

      const chipsData = h.is_binary
        ? [
            { val: "1-💪 کامل", label: "💪 کامل", cls: "status-1" },
            { val: "4-❌ با دلیل", label: "❌ دلیل", cls: "status-4" },
            { val: "5-⛔ بدون دلیل", label: "⛔ بی‌دلیل", cls: "status-5" },
            { val: null, label: "⚪ خالی", cls: "status-null" },
          ]
        : [
            { val: "1-💪 کامل", label: "💪 کامل", cls: "status-1" },
            { val: "2-🏃‍♂️ نیمه‌کامل", label: "🏃 متوسط", cls: "status-2" },
            { val: "3-🐢 سبک", label: "🐢 سبک", cls: "status-3" },
            { val: "4-❌ با دلیل", label: "❌ دلیل", cls: "status-4" },
            { val: "5-⛔ بدون دلیل", label: "⛔ بی‌دلیل", cls: "status-5" },
            { val: null, label: "⚪ خالی", cls: "status-null" },
          ];

      const chipsHtml = chipsData
        .map((c) => {
          const isActive = currentVal === c.val;
          return `<button type="button" class="preset-status-chip ${c.cls} ${isActive ? "active" : ""}" data-val="${c.val || ""}">${c.label}</button>`;
        })
        .join("");

      row.innerHTML = `
        <div class="preset-builder-habit-name">
          <span>${h.emoji}</span>
          <span>${h.fa}</span>
        </div>
        <div class="preset-status-chips">
          ${chipsHtml}
        </div>
      `;

      row.querySelectorAll(".preset-status-chip").forEach((btn, idx) => {
        btn.addEventListener("click", () => {
          const chosen = chipsData[idx].val;
          if (chosen) {
            builderHabitsState[h.prop] = chosen;
          } else {
            delete builderHabitsState[h.prop];
          }
          row.querySelectorAll(".preset-status-chip").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          haptic("light");
        });
      });

      list.appendChild(row);
    });
  }

  document.getElementById("btnOpenPresetsModal")?.addEventListener("click", () => {
    showPresetView("list");
    renderPresetsList();
    presetModal.style.display = "flex";
    haptic("light");
  });

  document.getElementById("btnPresetModalClose")?.addEventListener("click", () => {
    presetModal.style.display = "none";
  });

  document.getElementById("btnOpenNewPresetBuilder")?.addEventListener("click", () => {
    openPresetBuilder(null);
  });

  document.getElementById("btnCancelPresetBuilder")?.addEventListener("click", () => {
    showPresetView("list");
    haptic("light");
  });

  document.getElementById("btnSavePresetFromBuilder")?.addEventListener("click", () => {
    const title = document.getElementById("builderPresetTitle")?.value.trim();
    if (!title) {
      showToast("لطفاً نام قالب را وارد کنید", "error");
      return;
    }

    const cleanHabits = {};
    let count = 0;
    Object.entries(builderHabitsState).forEach(([prop, val]) => {
      if (val) {
        cleanHabits[prop] = val;
        count++;
      }
    });

    if (count === 0) {
      showToast("حداقل وضعیت یک عادت را در این قالب تعیین کنید", "error");
      return;
    }

    const custom = getCustomPresets();
    if (editingPresetId) {
      const idx = custom.findIndex((p) => p.id === editingPresetId);
      if (idx !== -1) {
        custom[idx].title = "✨ " + title;
        custom[idx].desc = `${toPersianDigits(count)} عادت تعیین‌شده`;
        custom[idx].habits = cleanHabits;
      }
    } else {
      custom.push({
        id: "preset_" + Date.now(),
        title: "✨ " + title,
        desc: `${toPersianDigits(count)} عادت تعیین‌شده`,
        is_default: false,
        habits: cleanHabits
      });
    }

    saveCustomPresets(custom);
    haptic("success");
    showToast(editingPresetId ? "قالب با موفقیت ویرایش شد!" : "قالب سفارشی جدید ذخیره شد!", "success");
    showPresetView("list");
    renderPresetsList();
  });

  function renderPresetsList() {
    const listEl = document.getElementById("presetsList");
    if (!listEl) return;

    const custom = getCustomPresets();
    const allPresets = [...custom];
    const autoPresetId = localStorage.getItem("notionyar_auto_apply_preset_id") || null;

    listEl.innerHTML = "";
    if (allPresets.length === 0) {
      listEl.innerHTML = '<div class="loading-state" style="padding:24px 0;">هیچ قالب سفارشی ثبت نشده است.<br><span style="font-size:11px; color:var(--hint-color); margin-top:4px; display:inline-block;">با زدن دکمه زیر می‌توانید قالب دلخواه خود را بسازید.</span></div>';
      return;
    }

    allPresets.forEach((p) => {
      const isAuto = p.id === autoPresetId;
      const card = document.createElement("div");
      card.className = "preset-card";
      card.innerHTML = `
        <div class="preset-info">
          <div class="preset-title">
            <span>${p.title}</span>
          </div>
          <div class="preset-sub">${p.desc || Object.keys(p.habits || {}).length + " عادت"}</div>
          ${isAuto ? '<div class="preset-auto-badge">⭐ اجرای خودکار روزانه فعال است</div>' : ''}
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <button type="button" class="btn-preset-auto ${isAuto ? "active" : ""}" title="تنظیم به عنوان قالب خودکار روزانه">
            ${isAuto ? "⭐ خودکار فعال" : "⭐ خودکار"}
          </button>
          <button type="button" class="btn-preset-edit" title="ویرایش قالب">✏️</button>
          <button type="button" class="btn-preset-del" title="حذف قالب">🗑️</button>
          <button type="button" class="btn-apply-preset">اجرا ⚡</button>
        </div>
      `;

      // Auto-apply daily preset toggle
      card.querySelector(".btn-preset-auto")?.addEventListener("click", () => {
        haptic("light");
        if (isAuto) {
          localStorage.removeItem("notionyar_auto_apply_preset_id");
          showToast(`اجرای خودکار برای قالب «${p.title}» غیرفعال شد`, "info");
        } else {
          localStorage.setItem("notionyar_auto_apply_preset_id", p.id);
          showToast(`قالب «${p.title}» برای اجرای خودکار روزانه تنظیم شد ⭐`, "success");
        }
        renderPresetsList();
      });


      // Apply Preset
      card.querySelector(".btn-apply-preset").addEventListener("click", async () => {
        if (!habitDayData?.page_id) {
          showToast("ابتدا روز را در تب عادات انتخاب کنید", "error");
          return;
        }

        haptic("medium");
        showToast(`در حال اعمال قالب «${p.title}»...`, "info");
        presetModal.style.display = "none";

        try {
          const res = await fetch("/api/habits/batch-update", {
            method: "POST",
            headers: getHeaders(),
            body: JSON.stringify({
              page_id: habitDayData.page_id,
              updates: p.habits
            }),
          });

          if (!res.ok) throw new Error();
          showToast(`قالب «${p.title}» با موفقیت ثبت شد 🎉`, "success");
          loadHabitsForDate(currentHabitDateIso);
        } catch (e) {
          showToast("خطا در اعمال قالب عادات", "error");
        }
      });

      // Edit Custom Preset
      card.querySelector(".btn-preset-edit")?.addEventListener("click", () => {
        openPresetBuilder(p);
      });

      // Delete Custom Preset
      card.querySelector(".btn-preset-del")?.addEventListener("click", () => {
        if (!confirm(`آیا از حذف قالب «${p.title}» مطمئن هستید؟`)) return;
        const updated = custom.filter((item) => item.id !== p.id);
        saveCustomPresets(updated);
        renderPresetsList();
        haptic("warning");
      });

      listEl.appendChild(card);
    });
  }

  // Save Current Habits as Preset
  document.getElementById("btnSaveCurrentAsPreset")?.addEventListener("click", () => {
    if (!habitDayData?.categories) return;

    const currentHabits = {};
    let count = 0;
    Object.values(habitDayData.categories).forEach((cat) => {
      (cat.habits || []).forEach((h) => {
        if (h.status) {
          currentHabits[h.prop] = h.status;
          count++;
        }
      });
    });

    if (count === 0) {
      showToast("هیچ عادتی برای امروز ثبت نشده تا قالب ساخته شود", "error");
      return;
    }

    const name = prompt("نام این قالب سفارشی را وارد کنید:", "قالب من");
    if (!name || !name.trim()) return;

    const custom = getCustomPresets();
    custom.push({
      id: "preset_" + Date.now(),
      title: "✨ " + name.trim(),
      desc: `${toPersianDigits(count)} عادت انتخاب‌شده`,
      is_default: false,
      habits: currentHabits
    });

    saveCustomPresets(custom);
    renderPresetsList();
    haptic("success");
    showToast("قالب سفارشی جدید ذخیره شد!", "success");
  });

  // ==========================================
  // 8. HABIT ANALYTICS & STREAKS (PERSIAN WEEKDAYS)
  // ==========================================
  async function loadHabitsAnalytics(period = currentHabitAnalyticsPeriod) {
    currentHabitAnalyticsPeriod = period;
    const rangeKey = period === "custom" ? `${customHabitAnalyticsStartDate || ""}_${customHabitAnalyticsEndDate || ""}` : "";
    const cacheKey = `${period}:${rangeKey}`;
    if (dataCache.habitAnalytics.has(cacheKey)) {
      renderHabitAnalytics(dataCache.habitAnalytics.get(cacheKey));
      return;
    }
    try {
      const query = new URLSearchParams({ period });
      if (period === "custom" && customHabitAnalyticsStartDate && customHabitAnalyticsEndDate) {
        query.set("start_date", customHabitAnalyticsStartDate);
        query.set("end_date", customHabitAnalyticsEndDate);
      }
      const res = await fetch(`/api/habits/analytics?${query.toString()}`, { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      dataCache.habitAnalytics.set(cacheKey, data);
      renderHabitAnalytics(data);
    } catch (e) {
      console.error(e);
    }
  }

  function renderHabitAnalytics(data) {

      const streaks = data.streaks || {};
      const matrix = data.matrix || {};
      const periodLabel = matrix.period_label || "بازه انتخابی";
      const rankingTitle = document.getElementById("habitRankingTitle");
      const matrixTitle = document.getElementById("habitMatrixTitle");
      if (rankingTitle) rankingTitle.textContent = `رتبه‌بندی کامل عادت‌ها در ${periodLabel}`;
      if (matrixTitle) matrixTitle.textContent = `ماتریس کامل مداومت در ${periodLabel}`;

      document.getElementById("overallCurrentStreak").textContent = `${toPersianDigits(streaks.overall?.current || 0)} روز`;
      document.getElementById("overallBestStreak").textContent = `${toPersianDigits(streaks.overall?.best || 0)} روز`;

      // Render Rankings
      const rankList = document.getElementById("habitRankingsList");
      rankList.innerHTML = "";
      (matrix.habit_rankings || []).forEach((item) => {
        const div = document.createElement("div");
        div.className = "ranking-item stealth-blur-target";
        div.innerHTML = `
          <div>
            <span style="font-weight:700;">
              <span class="ranking-name-normal">${item.info?.emoji || "🎯"} ${item.info?.fa || item.key}</span>
              <span class="ranking-name-code">[${item.info?.code || item.key.toUpperCase()}]</span>
            </span>
            <div class="ranking-bar-box">
              <div class="ranking-bar-fill" style="width:${Math.round(item.pct)}%;"></div>
            </div>
          </div>
          <span style="font-weight:800; color:var(--button-color); font-size:13px;">${toPersianDigits(Math.round(item.pct))}٪</span>
        `;
        rankList.appendChild(div);
      });

      // Render 7-day consistency Heatmap with 100% Persian weekdays (Item 9)
      const heatmapContainer = document.getElementById("habitHeatmapContainer");
      if (matrix.daily_timeline && matrix.daily_timeline.length > 0) {
        const daysCount = matrix.daily_timeline.length;
        let tableHtml = `<table class="heatmap-table" style="--matrix-days:${daysCount};min-width:${Math.max(460, 112 + daysCount * 46)}px"><thead><tr><th>عادت</th>`;
        matrix.daily_timeline.forEach((day) => {
          let weekdayStr = day.weekday || "";
          if (EN_TO_FA_WEEKDAYS[weekdayStr]) weekdayStr = EN_TO_FA_WEEKDAYS[weekdayStr];
          const jDateStr = day.jalali_str ? toPersianDigits(day.jalali_str.split("/").slice(1).join("/")) : "";
          tableHtml += `
            <th title="${weekdayStr}">
              <div style="font-size:10px; font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${weekdayStr}</div>
              <div style="font-size:9px; color:var(--hint-color); font-weight:normal; white-space:nowrap;">${jDateStr}</div>
            </th>`;
        });
        tableHtml += "</tr></thead><tbody>";

        (matrix.habit_rankings || []).forEach((item) => {
          const normalLabel = `${item.info?.emoji || ""} ${item.info?.fa || item.key}`;
          const codeLabel = `[${item.info?.code || item.key.toUpperCase()}]`;

          tableHtml += `<tr><td style="text-align:right; font-weight:600;">
            <span class="ranking-name-normal">${normalLabel}</span>
            <span class="ranking-name-code">${codeLabel}</span>
          </td>`;

          matrix.daily_timeline.forEach((day) => {
            const hStatus = day.habits?.[item.key];
            let cellClass = "none";
            let cellLabel = "ثبت‌نشده";
            if (hStatus === "1-💪 کامل") cellClass = "done";
            else if (hStatus === "2-🏃‍♂️ نیمه‌کامل" || hStatus === "3-🐢 سبک") cellClass = "partial";
            else if (hStatus === "4-❌ با دلیل") cellClass = "reason";
            else if (hStatus === "5-⛔ بدون دلیل") cellClass = "missed";
            else if (day.is_frozen) cellClass = "frozen";
            if (hStatus) cellLabel = hStatus.replace(/^[0-9]-/, "");
            else if (day.is_frozen) cellLabel = "روز فریز";
            tableHtml += `<td><div class="heatmap-cell ${cellClass}" title="${escapeReportText(item.info?.fa || item.key)}، ${escapeReportText(day.weekday || "")} ${escapeReportText(day.jalali_str || "")}: ${escapeReportText(cellLabel)}"></div></td>`;
          });
          tableHtml += "</tr>";
        });

        tableHtml += "</tbody></table>";
        heatmapContainer.innerHTML = tableHtml;
      }
  }

  document.querySelectorAll("[data-habit-analytics-period]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-habit-analytics-period]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const period = button.dataset.habitAnalyticsPeriod || "7d";
      const range = document.getElementById("habitAnalyticsCustomRange");
      if (range) range.hidden = period !== "custom";
      if (period !== "custom") loadHabitsAnalytics(period);
      else updateAnalyticsCustomRangeLabels("habit");
    });
  });

  // Freeze Day Action
  const freezeModal = document.getElementById("freezeModal");
  document.getElementById("btnActionFreeze")?.addEventListener("click", () => {
    if (!habitDayData?.page_id) {
      showToast("ابتدا روز را در تب عادات انتخاب کنید", "error");
      return;
    }
    freezeModal.style.display = "flex";
    haptic("light");
  });

  document.getElementById("btnFreezeModalClose")?.addEventListener("click", () => {
    freezeModal.style.display = "none";
  });

  document.querySelectorAll("#freezeReasonOptions .modal-option-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const reason = btn.getAttribute("data-reason") || "استراحت و ریکاوری";
      freezeModal.style.display = "none";
      haptic("medium");
      showToast("در حال ثبت روز فریز...", "info");

      try {
        const res = await fetch("/api/habits/freeze-day", {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({
            page_id: habitDayData.page_id,
            reason: reason,
          }),
        });

        if (!res.ok) throw new Error();
        showToast("روز فریز با موفقیت ثبت شد ❄️", "success");
        invalidateDataCache("habits", "habitAnalytics");
        loadHabitsForDate(currentHabitDateIso);
        loadHabitsAnalytics();
      } catch (e) {
        showToast("خطا در ثبت روز فریز", "error");
      }
    });
  });

  // Reset Day Action
  document.getElementById("btnActionReset")?.addEventListener("click", async () => {
    if (!habitDayData?.page_id) return;
    if (!confirm("آیا از پاک کردن و ریست تمام عادات این روز مطمئن هستید؟")) return;

    haptic("warning");
    showToast("در حال پاکسازی عادات روز...", "info");

    try {
      const res = await fetch("/api/habits/reset-day", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ page_id: habitDayData.page_id }),
      });

      if (!res.ok) throw new Error();
      showToast("عادات روز انتخابی ریست شدند ⚪", "success");
      invalidateDataCache("habits", "habitAnalytics");
      loadHabitsForDate(currentHabitDateIso);
      loadHabitsAnalytics();
    } catch (e) {
      showToast("خطا در بازنشانی عادات", "error");
    }
  });

  // ==========================================
  // 9. GRATITUDE BUILDER & JOURNAL REFLECTIONS
  // ==========================================
  function initGratitudeItems(dayData) {
    if (dayData?.gratitude_items && dayData.gratitude_items.length > 0) {
      gratitudeItems = dayData.gratitude_items.map((it, idx) => ({
        id: Date.now() + idx,
        tag: it.tag || "سایر",
        text: it.text || "",
      }));
    } else if (dayData?.gratitude) {
      gratitudeItems = [];
      const lines = dayData.gratitude.split("\n");
      lines.forEach((line, idx) => {
        let clean = line.replace(/^[•\-\*\s]+/, "").trim();
        if (!clean || clean.includes("دفتر شکرگزاری") || clean.includes("━━━━━") || clean.startsWith("📅")) return;
        const tagMatch = clean.match(/^\[(.*?)\]\s*(.*)$/);
        if (tagMatch) {
          gratitudeItems.push({ id: Date.now() + idx, tag: tagMatch[1], text: tagMatch[2] });
        } else {
          gratitudeItems.push({ id: Date.now() + idx, tag: "سایر", text: clean });
        }
      });
    } else {
      gratitudeItems = [];
    }
    renderGratitudeList();
  }

  function renderGratitudeList() {
    const listEl = document.getElementById("gratitudeItemsList");
    if (!listEl) return;

    if (gratitudeItems.length === 0) {
      listEl.innerHTML = '<div class="loading-state" style="padding:10px;">هنوز موردی اضافه نشده است. نعمات امروز خود را ثبت کنید 🌸</div>';
      return;
    }

    listEl.innerHTML = "";
    gratitudeItems.forEach((item) => {
      const row = document.createElement("div");
      row.className = "grat-item-row";
      row.innerHTML = `
        <span class="grat-item-tag">${item.tag}</span>
        <span class="grat-item-text">${item.text}</span>
        <div class="grat-item-actions">
          <button type="button" class="btn-grat-action btn-edit" title="ویرایش">✏️</button>
          <button type="button" class="btn-grat-action btn-delete" title="حذف">🗑️</button>
        </div>
      `;

      // Edit
      row.querySelector(".btn-edit").addEventListener("click", () => {
        const newText = prompt("ویرایش متن شکرگزاری:", item.text);
        if (newText !== null && newText.trim() !== "") {
          item.text = newText.trim();
          renderGratitudeList();
          haptic("light");
        }
      });

      // Delete
      row.querySelector(".btn-delete").addEventListener("click", () => {
        gratitudeItems = gratitudeItems.filter((i) => i.id !== item.id);
        renderGratitudeList();
        haptic("light");
      });

      listEl.appendChild(row);
    });
  }

  const gratitudeDropdown = document.getElementById("gratitudeTagDropdown");
  const gratitudeTrigger = document.getElementById("gratitudeTagTrigger");
  const gratitudeMenu = document.getElementById("gratitudeTagMenu");
  const gratitudeHidden = document.getElementById("gratitudeTagFilter");
  const gratitudeSelected = document.getElementById("gratitudeTagSelected");
  gratitudeTrigger?.addEventListener("click", (event) => {
    event.stopPropagation();
    const open = gratitudeDropdown?.classList.toggle("open");
    gratitudeTrigger.setAttribute("aria-expanded", String(Boolean(open)));
  });
  gratitudeMenu?.querySelectorAll(".custom-dropdown-item").forEach((item) => {
    item.addEventListener("click", (event) => {
      event.stopPropagation();
      currentGratitudeTag = item.dataset.value || "سایر";
      if (gratitudeHidden) gratitudeHidden.value = currentGratitudeTag;
      if (gratitudeSelected) gratitudeSelected.textContent = item.querySelector(".item-title")?.textContent || currentGratitudeTag;
      gratitudeMenu.querySelectorAll(".custom-dropdown-item").forEach((entry) => entry.classList.toggle("active", entry === item));
      gratitudeDropdown?.classList.remove("open");
      gratitudeTrigger?.setAttribute("aria-expanded", "false");
      haptic("light");
    });
  });
  document.addEventListener("click", (event) => {
    if (gratitudeDropdown && !gratitudeDropdown.contains(event.target)) {
      gratitudeDropdown.classList.remove("open");
      gratitudeTrigger?.setAttribute("aria-expanded", "false");
    }
  });

  document.getElementById("btnAddGratitudeItem")?.addEventListener("click", () => {
    const input = document.getElementById("gratitudeItemInput");
    const val = input.value.trim();
    if (!val) {
      showToast("لطفاً متن شکرگزاری را وارد کنید", "error");
      return;
    }

    gratitudeItems.push({
      id: Date.now(),
      tag: currentGratitudeTag,
      text: val,
    });

    input.value = "";
    renderGratitudeList();
    haptic("light");
  });

  document.getElementById("btnSaveGratitudeJournal")?.addEventListener("click", async () => {
    if (!habitDayData?.page_id) {
      showToast("خطا در یافتن روز انتخابی", "error");
      return;
    }

    const btn = document.getElementById("btnSaveGratitudeJournal");
    btn.disabled = true;
    btn.querySelector("span").textContent = "در حال ذخیره در نوشن...";
    haptic("medium");

    try {
      const res = await fetch("/api/habits/gratitude/save", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          page_id: habitDayData.page_id,
          date_iso: currentHabitDateIso,
          items: gratitudeItems.map((i) => ({ tag: i.tag, text: i.text })),
        }),
      });

      if (!res.ok) throw new Error();
      showToast("دفتر شکرگزاری با موفقیت در نوشن ذخیره شد 🌸", "success");
      invalidateDataCache("habits");
    } catch (e) {
      showToast("خطا در ذخیره دفتر شکرگزاری", "error");
    } finally {
      btn.disabled = false;
      btn.querySelector("span").textContent = "💾 ذخیره کل شکرگزاری‌ها در نوشن";
    }
  });

  document.querySelectorAll(".journal-block .btn-action").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!habitDayData?.page_id) return;
      const field = btn.getAttribute("data-field");
      let text = "";
      if (field === "notes") text = document.getElementById("habitNotes")?.value || "";
      if (field === "book") text = document.getElementById("habitBook")?.value || "";
      if (field === "quran") text = document.getElementById("habitQuran")?.value || "";

      btn.disabled = true;
      btn.textContent = "...";
      haptic("light");

      try {
        const res = await fetch("/api/habits/update-text", {
          method: "POST",
          headers: getHeaders(),
          body: JSON.stringify({
            page_id: habitDayData.page_id,
            field: field,
            text: text.trim(),
          }),
        });
        if (!res.ok) throw new Error();
        showToast("با موفقیت در نوشن ذخیره شد ✨", "success");
      } catch (e) {
        showToast("خطا در ذخیره یادداشت", "error");
      } finally {
        btn.disabled = false;
        btn.textContent = "ذخیره";
      }
    });
  });

  // ==========================================
  // 10. ADMIN PANEL LOGIC (ITEM 6)
  // ==========================================
  async function loadAdminPanel() {
    loadAdminStats();
    loadAdminUsers();
    loadWebAuthSettings();
  }

  async function loadWebAuthSettings() {
    const usernameInput = document.getElementById("settingsWebUsername");
    const currentPasswordGroup = document.getElementById("currentWebPasswordGroup");
    const currentPasswordInput = document.getElementById("settingsCurrentPassword");
    const feedback = document.getElementById("webCredentialsFeedback");
    if (!usernameInput) return;

    try {
      const response = await fetch("/api/auth/settings", { headers: getHeaders() });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "دریافت تنظیمات ورود ممکن نشد.");
      usernameInput.value = data.username || "";
      currentPasswordGroup.style.display = data.requires_current_password ? "flex" : "none";
      currentPasswordInput.required = Boolean(data.requires_current_password);
      if (feedback) {
        feedback.textContent = data.configured
          ? "ورود مستقل وب فعال است."
          : "ورود مستقل وب هنوز فعال نشده است.";
        feedback.classList.toggle("is-warning", !data.configured);
      }
    } catch (error) {
      if (feedback) {
        feedback.textContent = error.message;
        feedback.classList.add("is-error");
      }
    }
  }

  document.getElementById("formWebCredentials")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = document.getElementById("btnSaveWebCredentials");
    const feedback = document.getElementById("webCredentialsFeedback");
    const username = document.getElementById("settingsWebUsername")?.value.trim() || "";
    const currentPassword = document.getElementById("settingsCurrentPassword")?.value || "";
    const newPassword = document.getElementById("settingsNewPassword")?.value || "";
    const confirmPassword = document.getElementById("settingsConfirmPassword")?.value || "";

    if (newPassword !== confirmPassword) {
      if (feedback) feedback.textContent = "تکرار رمز عبور با رمز جدید یکسان نیست.";
      feedback?.classList.add("is-error");
      return;
    }

    if (button) button.disabled = true;
    if (feedback) {
      feedback.textContent = "در حال ذخیره اطلاعات ورود...";
      feedback.classList.remove("is-error", "is-warning", "is-success");
    }
    try {
      const response = await nativeFetch("/api/auth/credentials", {
        method: "PUT",
        headers: getHeaders(),
        credentials: "include",
        body: JSON.stringify({
          username,
          current_password: currentPassword || null,
          new_password: newPassword,
          confirm_password: confirmPassword,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "ذخیره اطلاعات ورود ممکن نشد.");
      document.getElementById("settingsCurrentPassword").value = "";
      document.getElementById("settingsNewPassword").value = "";
      document.getElementById("settingsConfirmPassword").value = "";
      if (feedback) {
        feedback.textContent = "نام کاربری و رمز عبور با موفقیت تغییر کرد.";
        feedback.classList.add("is-success");
      }
      showToast("اطلاعات ورود وب ذخیره شد", "success");
    } catch (error) {
      if (feedback) {
        feedback.textContent = error.message;
        feedback.classList.add("is-error");
      }
      showToast(error.message, "error");
    } finally {
      if (button) button.disabled = false;
    }
  });

  async function loadAdminStats() {
    const grid = document.getElementById("adminStatsGrid");
    if (!grid) return;
    grid.innerHTML = '<div class="loading-state">در حال بررسی وضعیت سامانه...</div>';

    try {
      const res = await fetch("/api/admin/stats", { headers: getHeaders() });
      if (!res.ok) throw new Error();
      const stats = await res.json();

      grid.innerHTML = `
        <div class="admin-stat-card">
          <span class="admin-stat-val">${toPersianDigits(stats.total_users)}</span>
          <span class="admin-stat-lbl">👥 کل کاربران مجاز</span>
        </div>
        <div class="admin-stat-card">
          <span class="admin-stat-val">${toPersianDigits(stats.recent_life_count)}</span>
          <span class="admin-stat-lbl">🌱 لاگ‌های امروز</span>
        </div>
        <div class="admin-stat-card">
          <span class="admin-stat-val" style="font-size:13px; color:var(--success-color);">${stats.server_status}</span>
          <span class="admin-stat-lbl">سرور مینی‌اپ</span>
        </div>
        <div class="admin-stat-card">
          <span class="admin-stat-val" style="font-size:13px; color:var(--success-color);">${toPersianDigits(stats.scheduler_status)}</span>
          <span class="admin-stat-lbl">زمان‌بند یادآور شبانه</span>
        </div>
      `;
    } catch (e) {
      grid.innerHTML = '<div class="loading-state" style="color:var(--danger-color)">خطا در دریافت وضعیت ادمین</div>';
    }
  }

  async function loadAdminUsers() {
    const list = document.getElementById("adminUsersList");
    if (!list) return;
    list.innerHTML = '<div class="loading-state">در حال دریافت لیست کاربران...</div>';

    try {
      const res = await fetch("/api/admin/users", { headers: getHeaders() });
      if (!res.ok) throw new Error();
      const data = await res.json();
      const users = data.users || [];

      list.innerHTML = "";
      if (users.length === 0) {
        list.innerHTML = '<div class="loading-state">کاربری ثبت نشده است</div>';
        return;
      }

      users.forEach((u) => {
        const div = document.createElement("div");
        div.className = "user-item-row";
        div.innerHTML = `
          <div class="user-item-info">
            <div class="user-item-name">
              <span>${u.name}</span>
              <span class="user-role-badge-admin">${ROLE_PERSIAN_MAP[u.role] || u.role}</span>
            </div>
            <div class="user-item-id">ID: ${toPersianDigits(u.user_id)}</div>
          </div>
          <div style="display:flex; align-items:center; gap:6px;">
            <button class="btn-item-edit" title="ویرایش کاربر" style="background:transparent; border:none; color:var(--button-color); font-size:15px; cursor:pointer;">✏️</button>
            <button class="btn-item-delete" title="حذف کاربر">🗑️</button>
          </div>
        `;

        // Edit user row
        div.querySelector(".btn-item-edit").addEventListener("click", () => {
          document.getElementById("adminNewUserId").value = u.user_id;
          document.getElementById("adminNewUserId").readOnly = true;
          document.getElementById("adminNewUserName").value = u.name;
          setAdminRoleDropdown(u.role);
          const submitBtn = formAddAdminUser?.querySelector("button[type='submit']");
          if (submitBtn) submitBtn.textContent = "💾 ذخیره تغییرات کاربر";

          let cancelBtn = document.getElementById("btnCancelAdminEdit");
          if (!cancelBtn && formAddAdminUser) {
            cancelBtn = document.createElement("button");
            cancelBtn.type = "button";
            cancelBtn.id = "btnCancelAdminEdit";
            cancelBtn.className = "btn-step";
            cancelBtn.style.marginTop = "8px";
            cancelBtn.style.width = "100%";
            cancelBtn.textContent = "انصراف از ویرایش";
            cancelBtn.addEventListener("click", () => {
              formAddAdminUser.reset();
              document.getElementById("adminNewUserId").readOnly = false;
              if (submitBtn) submitBtn.textContent = "افزودن دسترسی";
              setAdminRoleDropdown("member");
              cancelBtn.remove();
            });
            formAddAdminUser.appendChild(cancelBtn);
          }
          formAddAdminUser?.scrollIntoView({ behavior: "smooth" });
          haptic("light");
        });

        // Delete user
        div.querySelector(".btn-item-delete").addEventListener("click", async () => {
          if (!confirm(`آیا از حذف دسترسی «${u.name}» مطمئن هستید؟`)) return;
          haptic("warning");
          try {
            await fetch(`/api/admin/users/${u.user_id}`, { method: "DELETE", headers: getHeaders() });
            showToast("کاربر حذف شد", "success");
            div.remove();
          } catch (e) {
            showToast("خطا در حذف کاربر", "error");
          }
        });

        list.appendChild(div);
      });
    } catch (e) {
      renderRetryState(list, "خطا در بارگذاری کاربران", loadAdminUsers);
    }
  }

  const formAddAdminUser = document.getElementById("formAddAdminUser");
  formAddAdminUser?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const uidVal = document.getElementById("adminNewUserId").value.trim();
    const nameVal = document.getElementById("adminNewUserName").value.trim();
    const roleVal = document.getElementById("adminNewUserRole").value;

    if (!uidVal || !nameVal) return;

    haptic("medium");
    try {
      const res = await fetch("/api/admin/users/save", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          user_id: parseInt(uidVal, 10),
          name: nameVal,
          role: roleVal
        })
      });

      if (!res.ok) throw new Error();
      showToast("کاربر با موفقیت ذخیره شد 🎉", "success");
      formAddAdminUser.reset();
      document.getElementById("adminNewUserId").readOnly = false;
      const submitBtn = formAddAdminUser.querySelector("button[type='submit']");
      if (submitBtn) submitBtn.textContent = "افزودن دسترسی";
      document.getElementById("btnCancelAdminEdit")?.remove();
      setAdminRoleDropdown("member");
      loadAdminUsers();
      loadAdminStats();
    } catch (e) {
      showToast("خطا در ذخیره کاربر", "error");
    }
  });

  // ==========================================
  // 11. 📿 SPIRITUAL TRACKER (SALAH, QURAN & REPORTS)
  // ==========================================
  const PRAYER_DISPLAY_META = {
    sobh: { name: "صبح", emoji: "🌅" },
    zohr: { name: "ظهر", emoji: "☀️" },
    asr: { name: "عصر", emoji: "🌤️" },
    maghreb: { name: "مغرب", emoji: "🌇" },
    eshsa: { name: "عشاء", emoji: "🌌" }
  };

  function updateSpiritualDateBadge(offset = null, customIso = null) {
    let text = "";
    if (offset === 0) text = `امروز (${formatIsoToJalaliDisplay(getDateFromOffset(0))})`;
    else if (offset === 1) text = `دیروز (${formatIsoToJalaliDisplay(getDateFromOffset(1))})`;
    else if (offset === 2) text = `پریروز (${formatIsoToJalaliDisplay(getDateFromOffset(2))})`;
    else if (customIso) text = formatIsoToJalaliDisplay(customIso);

    const badge = document.getElementById("spiritualSelectedDateBadge");
    if (badge) badge.textContent = `📅 تاریخ: ${text}`;
  }

  function updateQuranDateBadge(offset = null, customIso = null) {
    let text = "";
    if (offset === 0) text = `امروز (${formatIsoToJalaliDisplay(getDateFromOffset(0))})`;
    else if (offset === 1) text = `دیروز (${formatIsoToJalaliDisplay(getDateFromOffset(1))})`;
    else if (customIso) text = formatIsoToJalaliDisplay(customIso);

    const badge = document.getElementById("quranSelectedDateBadge");
    if (badge) badge.textContent = `📅 تاریخ: ${text}`;
  }

  async function loadSpiritualDay(dateIso) {
    const container = document.getElementById("prayersListContainer");
    if (!container) return;

    try {
      let data = dataCache.spiritual.get(dateIso);
      if (!data) {
        const res = await fetch(`/api/spiritual/day?date_iso=${dateIso}`, { headers: getHeaders() });
        if (!res.ok) throw new Error("خطا در بارگذاری روز نماز");
        data = await res.json();
        dataCache.spiritual.set(dateIso, data);
      }
      spiritualDayData = data;

      // Update Date Badge
      updateSpiritualDateBadge(null, dateIso);

      // Progress & Counters
      const pct = data.progress_percent || 0;
      const pctEl = document.getElementById("spiritualPercent");
      if (pctEl) pctEl.textContent = toPersianDigits(pct) + "٪";

      const countEl = document.getElementById("spiritualCountDisplay");
      if (countEl) countEl.textContent = `${toPersianDigits(data.completed_count || 0)} از ۵`;

      const fillEl = document.getElementById("spiritualProgressFill");
      if (fillEl) fillEl.style.width = `${pct}%`;

      const adaEl = document.getElementById("spiritualAdaCount");
      if (adaEl) adaEl.textContent = toPersianDigits(data.ada_count || 0);

      const qazaEl = document.getElementById("spiritualQazaCount");
      if (qazaEl) qazaEl.textContent = toPersianDigits(data.qaza_count || 0);

      const pendEl = document.getElementById("spiritualPendingCount");
      if (pendEl) pendEl.textContent = toPersianDigits(Math.max(0, 5 - (data.completed_count || 0)));

      // Notes
      const notesEl = document.getElementById("spiritualNotesInput");
      if (notesEl) notesEl.value = data.notes || "";

      // Render 5 prayers cards
      renderPrayersList(data);
    } catch (err) {
      console.error(err);
      renderRetryState(container, "خطا در بارگذاری نمازها", () => loadSpiritualDay(dateIso));
    }
  }

  function renderPrayersList(data) {
    const container = document.getElementById("prayersListContainer");
    if (!container) return;

    const prayers = data.prayers || {};
    container.innerHTML = "";

    const prayerKeys = ["sobh", "zohr", "asr", "maghreb", "eshsa"];

    prayerKeys.forEach((key) => {
      const p = prayers[key] || {};
      const meta = PRAYER_DISPLAY_META[key] || { name: key, emoji: "🕌" };
      const status = p.status || "none";

      const card = document.createElement("div");
      card.className = "prayer-card stealth-blur-target";
      card.setAttribute("data-prayer-key", key);

      let statusLabel = "هنوز خوانده نشده ⚪";
      if (status === "ada") statusLabel = "اداء به‌موقع 🟢";
      if (status === "qaza") statusLabel = "قضاء خارج وقت 🟡";

      card.innerHTML = `
        <div class="prayer-info">
          <span class="prayer-icon">${meta.emoji}</span>
          <div class="prayer-name-box">
            <span class="prayer-name">نماز ${meta.name}</span>
            <span class="prayer-status-label">${statusLabel}</span>
          </div>
        </div>
        <div class="prayer-toggles-row">
          <button type="button" class="btn-prayer-state state-ada ${status === 'ada' ? 'active' : ''}" data-target-status="ada" title="اداء در وقت">🟢 اداء</button>
          <button type="button" class="btn-prayer-state state-qaza ${status === 'qaza' ? 'active' : ''}" data-target-status="qaza" title="قضاء خارج وقت">🟡 قضاء</button>
          <button type="button" class="btn-prayer-state state-none ${status === 'none' ? 'active' : ''}" data-target-status="none" title="نخوانده">⚪ نخوانده</button>
        </div>
      `;

      card.querySelectorAll(".btn-prayer-state").forEach((btn) => {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          const targetStatus = btn.getAttribute("data-target-status");
          changePrayerStatus(key, targetStatus);
        });
      });

      card.addEventListener("click", () => {
        if (isStealthMode) {
          card.classList.toggle("revealed");
        }
      });

      container.appendChild(card);
    });
  }

  async function changePrayerStatus(prayerKey, targetStatus) {
    if (!spiritualDayData || !spiritualDayData.page_id) {
      showToast("شناسه روز مشخص نیست", "error");
      return;
    }

    haptic("light");

    try {
      const res = await fetch("/api/spiritual/toggle-prayer", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          page_id: spiritualDayData.page_id,
          prayer_key: prayerKey,
          target_status: targetStatus
        })
      });

      if (!res.ok) throw new Error("خطا در به‌روزرسانی نماز");

      const pName = PRAYER_DISPLAY_META[prayerKey]?.name || prayerKey;
      const statusTitle = targetStatus === "ada" ? "اداء" : (targetStatus === "qaza" ? "قضاء" : "نخوانده");
      showToast(`نماز ${pName}: ${statusTitle} ثبت شد`, "success");
      invalidateDataCache("spiritual");

      await loadSpiritualDay(currentSpiritualDateIso);
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // Bulk Ada button (single day)
  document.getElementById("btnSpiritualBulkAda")?.addEventListener("click", async () => {
    if (!spiritualDayData || !spiritualDayData.page_id) return;
    haptic("medium");

    try {
      const res = await fetch("/api/spiritual/bulk-ada", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ page_id: spiritualDayData.page_id })
      });
      if (!res.ok) throw new Error("خطا در تکمیل خودکار");
      showToast("تمام ۵ نماز با موفقیت «اداء» علامت خوردند! 🟢", "success");
      invalidateDataCache("spiritual");
      await loadSpiritualDay(currentSpiritualDateIso);
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Update Bulk Range Badge helper
  function updateSpBulkRangeBadge() {
    const badge = document.getElementById("spBulkSelectedRangeBadge");
    if (!badge) return;

    if (spBulkActivePreset) {
      const presetNames = {
        "last_7_days": "۷ روز اخیر",
        "last_14_days": "۱۴ روز اخیر",
        "last_30_days": "۳۰ روز اخیر",
        "this_month": "ماه جاری"
      };
      badge.textContent = `بازه انتخابی: ${presetNames[spBulkActivePreset] || spBulkActivePreset}`;
    } else if (spBulkCustomFromIso && spBulkCustomToIso) {
      const fParts = spBulkCustomFromIso.split("-").map(Number);
      const [fy, fm, fd] = gregorianToJalali(fParts[0], fParts[1], fParts[2]);
      const tParts = spBulkCustomToIso.split("-").map(Number);
      const [ty, tm, td] = gregorianToJalali(tParts[0], tParts[1], tParts[2]);
      badge.textContent = `بازه انتخابی: از ${toPersianDigits(fd)} ${PERSIAN_MONTH_NAMES[fm - 1]} تا ${toPersianDigits(td)} ${PERSIAN_MONTH_NAMES[tm - 1]}`;
    } else if (spBulkCustomFromIso) {
      badge.textContent = "بازه انتخابی: تاریخ شروع مشخص شد (لطفاً تا تاریخ را انتخاب کنید)";
    } else {
      badge.textContent = "لطفاً یک بازه زمانی انتخاب کنید";
    }
  }

  // Bulk Range Modal Open & Close
  const modalSpRange = document.getElementById("spiritualBulkRangeModal");
  document.getElementById("btnOpenSpiritualBulkRangeModal")?.addEventListener("click", () => {
    spBulkActivePreset = "last_7_days";
    spBulkCustomFromIso = "";
    spBulkCustomToIso = "";
    document.querySelectorAll("[data-sp-bulk-preset]").forEach((btn) => {
      btn.classList.toggle("active", btn.getAttribute("data-sp-bulk-preset") === "last_7_days");
    });
    const btnFrom = document.getElementById("btnSpBulkFrom");
    const btnTo = document.getElementById("btnSpBulkTo");
    if (btnFrom) btnFrom.innerHTML = "<span>📅 از تاریخ</span>";
    if (btnTo) btnTo.innerHTML = "<span>📅 تا تاریخ</span>";
    updateSpBulkRangeBadge();
    if (modalSpRange) modalSpRange.style.display = "flex";
    haptic("light");
  });

  document.getElementById("btnSpiritualBulkRangeClose")?.addEventListener("click", () => {
    if (modalSpRange) modalSpRange.style.display = "none";
  });

  // Preset Buttons in Modal
  document.querySelectorAll("[data-sp-bulk-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-sp-bulk-preset]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      spBulkActivePreset = btn.getAttribute("data-sp-bulk-preset");
      spBulkCustomFromIso = "";
      spBulkCustomToIso = "";
      const btnFrom = document.getElementById("btnSpBulkFrom");
      const btnTo = document.getElementById("btnSpBulkTo");
      if (btnFrom) btnFrom.innerHTML = "<span>📅 از تاریخ</span>";
      if (btnTo) btnTo.innerHTML = "<span>📅 تا تاریخ</span>";
      updateSpBulkRangeBadge();
      haptic("light");
    });
  });

  // Confirm Bulk Range Ada execution
  document.getElementById("btnConfirmSpiritualBulkRange")?.addEventListener("click", async () => {
    const btnConfirm = document.getElementById("btnConfirmSpiritualBulkRange");

    let payload = {};
    if (spBulkActivePreset) {
      payload = { preset: spBulkActivePreset };
    } else if (spBulkCustomFromIso && spBulkCustomToIso) {
      if (spBulkCustomFromIso > spBulkCustomToIso) {
        showToast("تاریخ شروع باید قبل از تاریخ پایان باشد", "warning");
        return;
      }
      payload = { start_date: spBulkCustomFromIso, end_date: spBulkCustomToIso };
    } else {
      showToast("لطفاً یک بازه زمانی یا تاریخ‌های شروع و پایان را انتخاب کنید", "warning");
      return;
    }

    if (btnConfirm) {
      btnConfirm.disabled = true;
      btnConfirm.innerHTML = "<span>⏳ در حال اعمال اداء در نوشن...</span>";
    }
    haptic("medium");

    try {
      const res = await fetch("/api/spiritual/bulk-range-ada", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "خطا در اعمال بازه زمانی");
      }

      const data = await res.json();
      const r = data.result || {};
      const total = r.total_days || 0;
      const updated = r.updated_count || 0;
      const created = r.created_count || 0;

      showToast(`⚡ با موفقیت انجام شد: ${toPersianDigits(total)} روز (${toPersianDigits(updated + created)} روز اداء ثبت شد)`, "success");
      invalidateDataCache("spiritual");

      if (modalSpRange) modalSpRange.style.display = "none";
      await loadSpiritualDay(currentSpiritualDateIso);
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      if (btnConfirm) {
        btnConfirm.disabled = false;
        btnConfirm.innerHTML = "<span>⚡ اعمال و ثبت اداء برای کل بازه</span>";
      }
    }
  });

  // Reset Day button
  document.getElementById("btnSpiritualResetDay")?.addEventListener("click", async () => {
    if (!spiritualDayData || !spiritualDayData.page_id) return;
    haptic("warning");

    try {
      const res = await fetch("/api/spiritual/bulk-reset", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ page_id: spiritualDayData.page_id })
      });
      if (!res.ok) throw new Error("خطا در بازنشانی");
      showToast("وضعیت نمازهای روز بازنشانی شد ⚪", "info");
      invalidateDataCache("spiritual");
      await loadSpiritualDay(currentSpiritualDateIso);
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Save Notes
  document.getElementById("btnSaveSpiritualNotes")?.addEventListener("click", async () => {
    if (!spiritualDayData || !spiritualDayData.page_id) return;
    const notes = document.getElementById("spiritualNotesInput")?.value || "";
    haptic("light");

    try {
      const res = await fetch("/api/spiritual/update-notes", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({ page_id: spiritualDayData.page_id, notes: notes })
      });
      if (!res.ok) throw new Error("خطا در ذخیره یادداشت");
        showToast("یادداشت معنوی در نوشن ذخیره شد 💾", "success");
        invalidateDataCache("spiritual");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  // Date pills for Spiritual
  document.querySelectorAll("[data-spiritual-offset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-spiritual-offset]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const offset = parseInt(btn.getAttribute("data-spiritual-offset"), 10);
      currentSpiritualDateIso = getDateFromOffset(offset);
      updateSpiritualDateBadge(offset);
      loadSpiritualDay(currentSpiritualDateIso);
      haptic("light");
    });
  });

  // Quran Reading Section
  document.querySelectorAll("[data-quran-offset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-quran-offset]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const offset = parseInt(btn.getAttribute("data-quran-offset"), 10);
      selectedQuranDateIso = getDateFromOffset(offset);
      updateQuranDateBadge(offset);
      haptic("light");
    });
  });

  document.getElementById("formQuranTracker")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const pages = document.getElementById("quranPagesInput")?.value.trim();
    const title = document.getElementById("quranTitleInput")?.value.trim();
    if (!pages) {
      showToast("لطفاً صفحات را وارد کنید", "warning");
      return;
    }

    const btnSubmit = document.getElementById("btnSubmitQuran");
    btnSubmit.disabled = true;
    haptic("medium");

    try {
      const res = await fetch("/api/spiritual/quran/create", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          date_iso: selectedQuranDateIso,
          pages: pages,
          session_name: title || null
        })
      });
      if (!res.ok) throw new Error("خطا در ذخیره تلاوت قرآن");

      showToast("جلسه تلاوت قرآن در نوشن ثبت شد! ✨", "success");
      invalidateDataCache("quranHistory");
      document.getElementById("quranPagesInput").value = "";
      document.getElementById("quranTitleInput").value = "";
      loadQuranHistory();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnSubmit.disabled = false;
    }
  });

  async function loadQuranHistory() {
    const container = document.getElementById("quranHistoryList");
    if (!container) return;

    try {
      let data = dataCache.quranHistory;
      if (!data) {
        const res = await fetch("/api/spiritual/quran/history", { headers: getHeaders() });
        if (!res.ok) return;
        data = await res.json();
        dataCache.quranHistory = data;
      }
      const entries = data.entries || [];

      if (entries.length === 0) {
        container.innerHTML = '<div class="loading-state">هنوز رکوردی ثبت نشده است.</div>';
        return;
      }

      container.innerHTML = "";
      entries.forEach((item) => {
        const div = document.createElement("div");
        div.className = "timeline-item stealth-blur-target";
        div.innerHTML = `
          <div>
            <div style="font-weight:700; font-size:13px;">📖 ${item.name}</div>
            <div style="font-size:12px; color:var(--button-color); margin-top:2px;">صفحات: <b>${toPersianDigits(item.pages)}</b></div>
            <div style="font-size:11px; color:var(--hint-color); margin-top:2px;">📅 ${toPersianDigits(item.shamsi_date || item.date_iso)}</div>
          </div>
          <button type="button" class="btn-text-action btn-del-quran" style="color:var(--danger-color);" data-id="${item.id}" title="حذف این رکورد">🗑</button>
        `;

        div.querySelector(".btn-del-quran")?.addEventListener("click", async (e) => {
          e.stopPropagation();
          if (confirm("آیا از حذف این رکورد تلاوت قرآن مطمئن هستید؟")) {
            await deleteQuranEntry(item.id);
          }
        });

        div.addEventListener("click", () => {
          if (isStealthMode) div.classList.toggle("revealed");
        });

        container.appendChild(div);
      });
    } catch (err) {
      console.error(err);
      renderRetryState(container, "خطا در دریافت لیست جلسات", loadQuranHistory);
    }
  }

  async function deleteQuranEntry(pageId) {
    try {
      const res = await fetch(`/api/spiritual/quran/delete/${pageId}`, {
        method: "DELETE",
        headers: getHeaders()
      });
      if (!res.ok) throw new Error("خطا در حذف رکورد");
      showToast("رکورد تلاوت قرآن حذف شد", "info");
      invalidateDataCache("quranHistory");
      loadQuranHistory();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // Spiritual Reports
  document.querySelectorAll("[data-sp-report-period]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-sp-report-period]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const period = btn.getAttribute("data-sp-report-period");
      const range = document.getElementById("spiritualReportCustomRange");
      if (range) range.hidden = period !== "custom";
      if (period !== "custom") loadSpiritualReport(period);
      else updateAnalyticsCustomRangeLabels("spiritual");
      haptic("light");
    });
  });

  async function loadSpiritualReport(period = "7d") {
    const summaryGrid = document.getElementById("spiritualReportSummaryGrid");
    const barsContainer = document.getElementById("spiritualPrayerBarsContainer");
    if (!summaryGrid || !barsContainer) return;

    summaryGrid.innerHTML = '<div class="loading-state">در حال محاسبه آمار معنوی...</div>';
    barsContainer.innerHTML = '<div class="loading-state">در حال بارگذاری تفکیک نمازها...</div>';

    try {
      const query = new URLSearchParams({ period });
      if (period === "custom" && customSpiritualReportStartDate && customSpiritualReportEndDate) {
        query.set("start_date", customSpiritualReportStartDate);
        query.set("end_date", customSpiritualReportEndDate);
      }
      const res = await fetch(`/api/spiritual/report?${query.toString()}`, { headers: getHeaders() });
      if (!res.ok) throw new Error("خطا در بارگذاری گزارش");
      const data = await res.json();
      const rep = data.report || {};

      summaryGrid.innerHTML = `
        <div class="sp-stat-card">
          <span class="sp-stat-value">${toPersianDigits(rep.overall_ada_rate || 0)}٪</span>
          <span class="sp-stat-label">نرخ ادای به‌موقع نمازها</span>
        </div>
        <div class="sp-stat-card">
          <span class="sp-stat-value">${toPersianDigits(rep.perfect_days || 0)} روز</span>
          <span class="sp-stat-label">روزهای با ۵/۵ ادای کامل</span>
        </div>
        <div class="sp-stat-card">
          <span class="sp-stat-value" style="color:#10b981;">${toPersianDigits(rep.total_ada || 0)}</span>
          <span class="sp-stat-label">مجموع نمازهای اداء</span>
        </div>
        <div class="sp-stat-card">
          <span class="sp-stat-value" style="color:#f59e0b;">${toPersianDigits(rep.total_qaza || 0)}</span>
          <span class="sp-stat-label">مجموع نمازهای قضاء</span>
        </div>
      `;

      const pStats = rep.prayer_stats || {};
      const prayerKeys = ["sobh", "zohr", "asr", "maghreb", "eshsa"];
      barsContainer.innerHTML = "";

      prayerKeys.forEach((k) => {
        const item = pStats[k] || {};
        const meta = PRAYER_DISPLAY_META[k] || { name: k, emoji: "🕌" };
        const rate = item.rate || 0;

        const barEl = document.createElement("div");
        barEl.className = "sp-bar-item";
        barEl.innerHTML = `
          <div class="sp-bar-header">
            <span>${meta.emoji} ${meta.name} (اداء: ${toPersianDigits(item.ada || 0)} | قضاء: ${toPersianDigits(item.qaza || 0)})</span>
            <span style="font-weight:700;">${toPersianDigits(rate)}٪</span>
          </div>
          <div class="sp-bar-track">
            <div class="sp-bar-fill" style="width: ${rate}%;"></div>
          </div>
        `;
        barsContainer.appendChild(barEl);
      });
    } catch (err) {
      console.error(err);
      renderRetryState(summaryGrid, "خطا در بارگذاری گزارش معنوی", () => loadSpiritualReport(period));
      barsContainer.innerHTML = '<div class="report-empty">برای نمایش تفکیک نمازها دوباره تلاش کنید.</div>';
    }
  }


  // ==========================================
  // 12. UNIFIED REPORTS CENTER
  // ==========================================
  function escapeReportText(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function renderReportRows(target, items, valueLabel, color = "var(--button-color)") {
    if (!target) return;
    if (!items.length) {
      target.innerHTML = '<div class="report-empty">برای این بازه داده‌ای ثبت نشده است.</div>';
      return;
    }
    target.innerHTML = items.map((item) => `
      <div class="report-list-row">
        <span class="report-list-name">${escapeReportText(item.label)}</span>
        <div class="report-list-track"><div class="report-list-fill" style="width:${Math.max(0, Math.min(100, item.pct || 0))}%;background:${color}"></div></div>
        <span class="report-list-value">${escapeReportText(valueLabel(item))}</span>
      </div>
    `).join("");
  }

  function renderReportsDashboard(data) {
    currentReportData = data;
    const summary = data.summary || {};
    const period = data.period || {};
    const habits = data.habits || {};
    const matrix = habits.matrix || {};
    const streaks = habits.streaks || {};
    const spiritual = data.spiritual || {};

    const caption = document.getElementById("reportsPeriodCaption");
    if (caption) {
      caption.textContent = `${period.label || "بازه انتخابی"}، از ${formatIsoToJalaliDisplay(period.start_date)} تا ${formatIsoToJalaliDisplay(period.end_date)}`;
    }

    const warnings = document.getElementById("reportsWarnings");
    const warningItems = data.warnings || [];
    if (warnings) {
      warnings.hidden = warningItems.length === 0;
      warnings.innerHTML = warningItems.map((item) => `<div>• ${escapeReportText(item)}</div>`).join("");
    }

    const kpis = document.getElementById("reportsKpiGrid");
    if (kpis) {
      kpis.innerHTML = `
        <div class="report-kpi" style="--kpi-color:var(--success-color)">
          <div class="report-kpi-top"><span>مداومت عادت‌ها</span><span class="report-kpi-icon"><i data-lucide="circle-check-big"></i></span></div>
          <strong>${toPersianDigits(summary.habit_consistency_pct || 0)}٪</strong>
          <small>${toPersianDigits(summary.habit_logged_days || 0)} روز دارای ثبت</small>
        </div>
        <div class="report-kpi" style="--kpi-color:var(--info-color)">
          <div class="report-kpi-top"><span>ثبت‌های روزمرگی</span><span class="report-kpi-icon"><i data-lucide="notebook-pen"></i></span></div>
          <strong>${toPersianDigits(summary.life_records || 0)}</strong>
          <small>در ${toPersianDigits(summary.life_active_days || 0)} روز فعال</small>
        </div>
        <div class="report-kpi" style="--kpi-color:var(--warning-color)">
          <div class="report-kpi-top"><span>نماز ادای به‌موقع</span><span class="report-kpi-icon"><i data-lucide="clock-3"></i></span></div>
          <strong>${toPersianDigits(summary.prayer_ada_rate || 0)}٪</strong>
          <small>${toPersianDigits(spiritual.perfect_days || 0)} روز کامل</small>
        </div>
        <div class="report-kpi" style="--kpi-color:var(--purple-color)">
          <div class="report-kpi-top"><span>جلسات تلاوت</span><span class="report-kpi-icon"><i data-lucide="book-open-text"></i></span></div>
          <strong>${toPersianDigits(summary.quran_sessions || 0)}</strong>
          <small>جلسه در بازه انتخابی</small>
        </div>
      `;
    }

    const timeline = data.daily_timeline || [];
    const chart = document.getElementById("reportsDailyChart");
    if (chart) {
      const maxLife = Math.max(1, ...timeline.map((day) => Number(day.life_count || 0)));
      chart.innerHTML = timeline.length ? timeline.map((day) => {
        const lifeHeight = Math.round((Number(day.life_count || 0) / maxLife) * 100);
        const prayerHeight = Math.round((Number(day.prayer_ada || 0) / 5) * 100);
        const shortDate = String(formatIsoToJalaliDisplay(day.date_iso)).split(" ")[0];
        return `
          <div class="report-chart-day" title="${escapeReportText(day.date_label)} | عادت ${toPersianDigits(day.habit_pct)}٪ | ${toPersianDigits(day.life_count)} روزمرگی | ${toPersianDigits(day.prayer_ada)} نماز اداء">
            <div class="report-chart-bars">
              <i class="report-chart-bar habit" style="height:${Math.max(2, Number(day.habit_pct || 0))}%"></i>
              <i class="report-chart-bar life" style="height:${Math.max(2, lifeHeight)}%"></i>
              <i class="report-chart-bar prayer" style="height:${Math.max(2, prayerHeight)}%"></i>
            </div>
            <span class="report-chart-label">${toPersianDigits(shortDate)}</span>
          </div>`;
      }).join("") : '<div class="report-empty">داده‌ای برای نمایش روند وجود ندارد.</div>';
      chart.scrollLeft = chart.scrollWidth;
    }

    const overall = streaks.overall || {};
    const habitStats = document.getElementById("reportsHabitStats");
    if (habitStats) {
      habitStats.innerHTML = `
        <div class="report-mini-stat"><strong>${toPersianDigits(overall.current || 0)}</strong><span>زنجیره فعلی</span></div>
        <div class="report-mini-stat"><strong>${toPersianDigits(overall.best || 0)}</strong><span>بهترین زنجیره</span></div>
        <div class="report-mini-stat"><strong>${toPersianDigits(matrix.total_completed || 0)}</strong><span>انجام موفق</span></div>`;
    }
    const habitRows = (matrix.habit_rankings || []).slice(0, 7).map((item) => ({
      label: `${item.info?.emoji || ""} ${item.info?.fa || item.key}`,
      pct: Math.round(item.pct || 0),
    }));
    renderReportRows(
      document.getElementById("reportsHabitRanking"),
      habitRows,
      (item) => `${toPersianDigits(item.pct)}٪`,
      "var(--success-color)"
    );

    const lifeRows = (data.life?.breakdown || []).slice(0, 8).map((item) => ({
      label: `${item.emoji || ""} ${item.name}`,
      pct: item.pct || 0,
      count: item.count || 0,
    }));
    renderReportRows(
      document.getElementById("reportsLifeBreakdown"),
      lifeRows,
      (item) => toPersianDigits(item.count),
      "var(--info-color)"
    );

    const spiritualStats = document.getElementById("reportsSpiritualStats");
    if (spiritualStats) {
      spiritualStats.innerHTML = `
        <div class="report-mini-stat"><strong style="color:var(--success-color)">${toPersianDigits(spiritual.total_ada || 0)}</strong><span>اداء</span></div>
        <div class="report-mini-stat"><strong style="color:var(--warning-color)">${toPersianDigits(spiritual.total_qaza || 0)}</strong><span>قضاء</span></div>
        <div class="report-mini-stat"><strong style="color:var(--danger-color)">${toPersianDigits(spiritual.total_missed || 0)}</strong><span>ثبت‌نشده</span></div>`;
    }
    const prayerContainer = document.getElementById("reportsPrayerBreakdown");
    const prayerStats = spiritual.prayer_stats || {};
    if (prayerContainer) {
      const prayerIcons = { sobh: "sunrise", zohr: "sun", asr: "cloud-sun", maghreb: "sunset", eshsa: "moon" };
      prayerContainer.innerHTML = Object.keys(prayerStats).length ? ["sobh", "zohr", "asr", "maghreb", "eshsa"].map((key) => {
        const item = prayerStats[key] || {};
        return `<div class="prayer-report-item">
          <span><i data-lucide="${prayerIcons[key]}"></i>${escapeReportText(item.name || key)}</span>
          <strong>${toPersianDigits(item.rate || 0)}٪</strong>
          <small>${toPersianDigits(item.ada || 0)} اداء · ${toPersianDigits(item.qaza || 0)} قضاء</small>
        </div>`;
      }).join("") : '<div class="report-empty">برای این بازه گزارش نماز موجود نیست.</div>';
    }
  }

  async function loadReportsDashboard(period = currentReportPeriod) {
    currentReportPeriod = period;
    const kpis = document.getElementById("reportsKpiGrid");
    if (dataCache.reports.has(period)) {
      renderReportsDashboard(dataCache.reports.get(period));
      return;
    }
    if (kpis) kpis.innerHTML = '<div class="loading-state">در حال آماده‌سازی گزارش یکپارچه...</div>';
    try {
      const response = await fetch(`/api/reports/dashboard?period=${encodeURIComponent(period)}`, { headers: getHeaders() });
      if (!response.ok) throw new Error("گزارش دریافت نشد");
      const data = await response.json();
      dataCache.reports.set(period, data);
      renderReportsDashboard(data);
    } catch (error) {
      console.error(error);
      renderRetryState(kpis, "دریافت گزارش ممکن نشد", () => loadReportsDashboard(period));
    }
  }

  document.querySelectorAll("[data-report-period]").forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll("[data-report-period]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      loadReportsDashboard(button.getAttribute("data-report-period") || "7d");
      haptic("light");
    });
  });

  document.querySelectorAll("[data-report-section-target]").forEach((button) => {
    button.addEventListener("click", () => {
      const target = button.dataset.reportSectionTarget || "overview";
      document.querySelectorAll("[data-report-section-target]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.querySelectorAll("[data-report-section]").forEach((panel) => {
        panel.hidden = panel.dataset.reportSection !== target;
      });
      document.getElementById("tab-reports")?.scrollIntoView({ behavior: "smooth", block: "start" });
      haptic("light");
    });
  });

  document.getElementById("btnRefreshReports")?.addEventListener("click", () => {
    loadReportsDashboard(currentReportPeriod);
  });

  document.getElementById("btnExportReports")?.addEventListener("click", () => {
    const rows = currentReportData?.daily_timeline || [];
    if (!rows.length) {
      showToast("داده‌ای برای خروجی گرفتن وجود ندارد", "warning");
      return;
    }
    const csvRows = [
      ["date", "habit_percent", "life_records", "prayer_ada", "prayer_qaza", "quran_sessions"],
      ...rows.map((row) => [row.date_iso, row.habit_pct, row.life_count, row.prayer_ada, row.prayer_qaza, row.quran_count]),
    ];
    const csv = "\uFEFF" + csvRows.map((row) => row.join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `notionyar-report-${currentReportPeriod}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    showToast("خروجی گزارش آماده شد", "success");
  });

  // ==========================================
  // START APPLICATION
  // ==========================================
  setupOfflineSupport();
  initApp();
})();
