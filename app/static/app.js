// app/static/app.js
// NotionYar Telegram Mini App v2.5 - Rich UI, Persian Date Picker, Stealth Mode & Gratitude Builder

(function () {
  const tg = window.Telegram?.WebApp;

  if (tg) {
    tg.ready();
    tg.expand();
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

  function toPersianDigits(n) {
    return String(n).replace(/[0-9]/g, (d) => PERSIAN_DIGITS[d]);
  }

  function formatIsoToJalaliDisplay(isoStr) {
    if (!isoStr) return "";
    const parts = isoStr.split("-").map(Number);
    if (parts.length !== 3) return isoStr;
    const [jy, jm, jd] = gregorianToJalali(parts[0], parts[1], parts[2]);
    return `${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]} ${toPersianDigits(jy)}`;
  }

  function getDateFromOffset(offset) {
    const d = new Date();
    d.setDate(d.getDate() - offset);
    return d.toISOString().split("T")[0];
  }

  // ==========================================
  // ⚡ APP STATE
  // ==========================================
  let currentUser = null;
  let currentDateIso = new Date().toISOString().split("T")[0];
  let selectedTimeDate = getDateFromOffset(0);
  let selectedTimeSatisfaction = "5";

  let selectedLifeDate = getDateFromOffset(0);
  let selectedLifeType = null;
  let selectedLifeModes = []; // supports 0, 1, or multiple modes
  let lifeOptionsData = null;

  let currentHabitDateIso = getDateFromOffset(0);
  let habitDayData = null;
  let isStealthMode = localStorage.getItem("notionyar_stealth") === "true";

  // Gratitude Builder State
  let currentGratitudeTag = "سلامتی و جسم";
  let gratitudeItems = [];

  // Persian Date Picker Modal State
  let activeDatePickerTarget = "time"; // "time" | "life" | "habits"

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

    toast.className = `toast ${type} show`;
    const icon = type === "success" ? "✅ " : type === "error" ? "❌ " : "ℹ️ ";
    toast.textContent = icon + message;

    if (type === "success") haptic("success");
    if (type === "error") haptic("error");

    setTimeout(() => {
      toast.classList.remove("show");
    }, 2800);
  }

  // ==========================================
  // 1. INITIALIZATION & AUTH
  // ==========================================
  async function initApp() {
    try {
      const res = await fetch("/api/me", { headers: getHeaders() });
      if (!res.ok) {
        showToast("خطا در تایید هویت کاربر", "error");
        return;
      }
      const data = await res.json();
      currentUser = data.user;
      currentDateIso = data.today_iso;
      selectedTimeDate = data.today_iso;
      selectedLifeDate = data.today_iso;
      currentHabitDateIso = data.today_iso;

      document.getElementById("userName").textContent = currentUser.first_name || "کاربر گرامی";
      document.getElementById("currentDate").textContent = data.today_jalali;

      const roleBadge = document.getElementById("userRole");
      const roleMap = {
        admin: "👑 مدیر کل",
        manager: "💼 مدیر تیم",
        member: "👤 عضو تیم",
        guest: "🌿 مهمان",
      };
      roleBadge.textContent = roleMap[currentUser.role] || "کاربر";

      // Setup stealth mode initial UI
      setupStealthModeUI();

      // Update date badges
      updateDateBadge("time", 0);
      updateDateBadge("life", 0);

      await Promise.all([
        loadTimeTrackerMeta(),
        loadLifeTrackerOptions(),
        loadHabitsForDate(currentHabitDateIso),
        loadRecentLogs(),
      ]);
    } catch (err) {
      console.error(err);
      showToast("خطا در ارتباط با سرور", "error");
    }
  }

  function updateDateBadge(target, offset = null, customIso = null) {
    let text = "";
    if (offset === 0) text = `امروز (${formatIsoToJalaliDisplay(getDateFromOffset(0))})`;
    else if (offset === 1) text = `دیروز (${formatIsoToJalaliDisplay(getDateFromOffset(1))})`;
    else if (offset === 2) text = `پریروز (${formatIsoToJalaliDisplay(getDateFromOffset(2))})`;
    else if (customIso) text = formatIsoToJalaliDisplay(customIso);

    if (target === "time") {
      const badge = document.getElementById("timeSelectedDateBadge");
      if (badge) badge.textContent = `📅 تاریخ انتخاب‌شده: ${text}`;
    } else if (target === "life") {
      const badge = document.getElementById("lifeSelectedDateBadge");
      if (badge) badge.textContent = `📅 تاریخ انتخاب‌شده: ${text}`;
    }
  }

  // ==========================================
  // 2. NAVIGATION & TABS
  // ==========================================
  const navItems = document.querySelectorAll(".nav-item");
  const tabPanels = document.querySelectorAll(".tab-panel");

  navItems.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetTabId = btn.getAttribute("data-tab");
      navItems.forEach((i) => i.classList.remove("active"));
      tabPanels.forEach((p) => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPanel = document.getElementById(targetTabId);
      if (targetPanel) targetPanel.classList.add("active");

      haptic("light");
    });
  });

  // Segmented Controls (Sub-tabs)
  document.querySelectorAll(".segmented-control").forEach((segControl) => {
    segControl.querySelectorAll(".seg-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const subtabId = btn.getAttribute("data-subtab");
        const parentSection = btn.closest(".tab-panel");
        if (!parentSection) return;

        parentSection.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
        parentSection.querySelectorAll(".subtab-content").forEach((c) => c.classList.remove("active"));

        btn.classList.add("active");
        const targetContent = document.getElementById(subtabId);
        if (targetContent) targetContent.classList.add("active");

        haptic("light");

        // Dynamic Loading for Analytics/Reports
        if (subtabId === "life-sub-radar") loadLifeRadar();
        if (subtabId === "life-sub-history") loadLifeHistory();
        if (subtabId === "habit-sub-analytics") loadHabitsAnalytics();
      });
    });
  });

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

    btnClose?.addEventListener("click", () => {
      modal.style.display = "none";
    });

    btnConfirm?.addEventListener("click", () => {
      const jy = parseInt(yearSelect.value, 10);
      const jm = parseInt(monthSelect.value, 10);
      const jd = parseInt(daySelect.value, 10);

      const [gy, gm, gd] = jalaliToGregorian(jy, jm, jd);
      const isoDate = `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;

      if (activeDatePickerTarget === "time") {
        selectedTimeDate = isoDate;
        document.querySelectorAll("[data-date-offset]").forEach((b) => b.classList.remove("active"));
        updateDateBadge("time", null, isoDate);
      } else if (activeDatePickerTarget === "life") {
        selectedLifeDate = isoDate;
        document.querySelectorAll("[data-life-offset]").forEach((b) => b.classList.remove("active"));
        updateDateBadge("life", null, isoDate);
      } else if (activeDatePickerTarget === "habits") {
        currentHabitDateIso = isoDate;
        document.querySelectorAll("[data-habit-offset]").forEach((b) => b.classList.remove("active"));
        loadHabitsForDate(currentHabitDateIso);
      }

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
    if (target === "time") currentIso = selectedTimeDate;
    if (target === "life") currentIso = selectedLifeDate;
    if (target === "habits") currentIso = currentHabitDateIso;

    const parts = currentIso.split("-").map(Number);
    const [jy, jm, jd] = gregorianToJalali(parts[0], parts[1], parts[2]);

    // Populate years around current Jalali year
    yearSelect.innerHTML = "";
    for (let y = jy - 2; y <= jy + 2; y++) {
      const opt = document.createElement("option");
      opt.value = y;
      opt.textContent = toPersianDigits(y);
      if (y === jy) opt.selected = true;
      yearSelect.appendChild(opt);
    }

    monthSelect.value = jm;

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

    const preview = document.getElementById("shamsiDatePreview");
    preview.textContent = `${toPersianDigits(jd)} ${PERSIAN_MONTH_NAMES[jm - 1]} ${toPersianDigits(jy)}`;

    modal.style.display = "flex";
    haptic("light");
  }

  document.getElementById("btnOpenTimePicker")?.addEventListener("click", () => openPersianDatePicker("time"));
  document.getElementById("btnOpenLifePicker")?.addEventListener("click", () => openPersianDatePicker("life"));
  document.getElementById("btnOpenHabitPicker")?.addEventListener("click", () => openPersianDatePicker("habits"));

  initPersianDatePickerModal();

  // ==========================================
  // 4. TIME TRACKER
  // ==========================================
  async function loadTimeTrackerMeta() {
    try {
      const res = await fetch("/api/time-tracker/meta", { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();

      const select = document.getElementById("timePerson");
      select.innerHTML = '<option value="">انتخاب انجام‌دهنده (اختیاری)</option>';

      if (data.persons?.length > 0) {
        data.persons.forEach((p) => {
          const opt = document.createElement("option");
          opt.value = p.id;
          opt.textContent = p.name;
          select.appendChild(opt);
        });
      }
    } catch (e) {
      console.error(e);
    }
  }

  document.querySelectorAll("[data-date-offset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-date-offset]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const offset = parseInt(btn.getAttribute("data-date-offset"), 10);
      selectedTimeDate = getDateFromOffset(offset);
      updateDateBadge("time", offset);
      haptic("light");
    });
  });

  document.querySelectorAll(".quick-duration-pills .btn-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById("timeDuration").value = btn.getAttribute("data-min");
      haptic("light");
    });
  });

  const timeStart = document.getElementById("timeStart");
  const timeEnd = document.getElementById("timeEnd");
  function autoCalculateDuration() {
    if (timeStart.value && timeEnd.value) {
      const [h1, m1] = timeStart.value.split(":").map(Number);
      const [h2, m2] = timeEnd.value.split(":").map(Number);
      const startMin = h1 * 60 + m1;
      const endMin = h2 * 60 + m2;
      let diff = endMin - startMin;
      if (diff < 0) diff += 24 * 60;
      if (diff > 0) document.getElementById("timeDuration").value = diff;
    }
  }
  timeStart?.addEventListener("change", autoCalculateDuration);
  timeEnd?.addEventListener("change", autoCalculateDuration);

  document.querySelectorAll("#timeSatisfaction .btn-star").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#timeSatisfaction .btn-star").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedTimeSatisfaction = btn.getAttribute("data-val");
      haptic("light");
    });
  });

  const formTimeTracker = document.getElementById("formTimeTracker");
  formTimeTracker?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("timeTitle").value.trim();
    if (!title) {
      showToast("لطفاً عنوان تسک را وارد کنید", "error");
      return;
    }

    const btnSubmit = document.getElementById("btnSubmitTime");
    btnSubmit.disabled = true;
    btnSubmit.querySelector("span").textContent = "در حال ثبت در نوشن...";

    const personSelect = document.getElementById("timePerson");
    const personId = personSelect.value || null;
    const personName = personSelect.options[personSelect.selectedIndex]?.text || null;
    const durationVal = document.getElementById("timeDuration").value;
    const duration = durationVal ? parseInt(durationVal, 10) : null;
    const desc = document.getElementById("timeDescription").value.trim() || null;

    try {
      const res = await fetch("/api/time-tracker/create", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          name: title,
          person_id: personId,
          person_name: personName,
          date_iso: selectedTimeDate,
          start_time: timeStart.value || null,
          end_time: timeEnd.value || null,
          manual_duration: duration,
          satisfaction: selectedTimeSatisfaction,
          description: desc,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "خطا در ثبت زمان");

      showToast("زمان کاری با موفقیت در نوشن ثبت شد! 🎉", "success");
      formTimeTracker.reset();
      document.getElementById("timeDuration").value = "";
      selectedTimeSatisfaction = "5";
      document.querySelectorAll("#timeSatisfaction .btn-star").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-val") === "5");
      });
      loadRecentLogs();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.querySelector("span").textContent = "ثبت در نوشن";
    }
  });

  // ==========================================
  // 5. LIFE TRACKER (REVAMPED)
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
      modesLabel.textContent = `حالت‌های انتخابی «${typeMeta.name}» (امکان انتخاب صفر، یک یا چند حالت):`;
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

  function updateLifeSubmitButton() {
    const btn = document.getElementById("btnSubmitLife");
    if (!selectedLifeType) {
      btn.disabled = true;
      btn.innerHTML = "<span>لطفاً یک فعالیت را انتخاب کنید</span>";
      return;
    }
    btn.disabled = false;
    let text = `ثبت ${selectedLifeType}`;
    if (selectedLifeModes.length > 0) {
      text += ` (${selectedLifeModes.join("، ")})`;
    }
    btn.innerHTML = `<span>${text}</span> <span class="btn-arrow">←</span>`;
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
      document.getElementById("lifeNotes").value = "";
      loadRecentLogs();
    } catch (err) {
      showToast(err.message, "error");
    } finally {
      btnSubmit.disabled = false;
      btnSubmit.innerHTML = origHTML;
    }
  });

  // Routine Radar (Intervals)
  async function loadLifeRadar() {
    const grid = document.getElementById("lifeRadarGrid");
    grid.innerHTML = '<div class="loading-state">در حال محاسبه فواصل زمانی و وضعیت موعدها...</div>';

    try {
      const res = await fetch("/api/life-tracker/insights", { headers: getHeaders() });
      if (!res.ok) throw new Error();
      const data = await res.json();
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
          .map((d) => `<span class="radar-date-badge">${d}</span>`)
          .join("");

        card.innerHTML = `
          <div class="radar-top">
            <span class="radar-name"><span>${item.emoji}</span> <span>${tName}</span></span>
            <span class="radar-status-pill ${statusClass}">${item.badge} ${statusText}</span>
          </div>
          <div class="radar-details">
            <span>📅 آخرین بار: <b>${item.days_ago} روز پیش</b> (${item.last_date_shamsi})</span>
            <span>⏱️ میانگین: <b>${item.avg_interval ? `هر ${item.avg_interval} روز` : "—"}</b></span>
          </div>
          <div class="radar-dates">
            <span style="font-size:10px; color:var(--hint-color); align-self:center;">دفعات اخیر:</span>
            ${datesHtml}
          </div>
        `;
        grid.appendChild(card);
      });

      document.getElementById("radarGoodCount").textContent = goodCnt;
      document.getElementById("radarNearCount").textContent = nearCnt;
      document.getElementById("radarOverdueCount").textContent = overdueCnt;

      if (grid.children.length === 0) {
        grid.innerHTML = '<div class="loading-state">داده‌ای برای تحلیل فواصل یافت نشد. با ثبت فعالیت‌ها رادار فعال خواهد شد.</div>';
      }
    } catch (e) {
      grid.innerHTML = '<div class="loading-state" style="color:var(--danger-color)">خطا در دریافت گزارش رادار</div>';
    }
  }

  // History & Filter
  function populateHistoryFilter() {
    const sel = document.getElementById("lifeHistoryFilter");
    if (!sel || !lifeOptionsData?.all_types) return;
    sel.innerHTML = '<option value="">تمام فعالیت‌ها</option>';
    Object.keys(lifeOptionsData.all_types).forEach((t) => {
      const opt = document.createElement("option");
      opt.value = t;
      opt.textContent = `${lifeOptionsData.all_types[t].emoji} ${t}`;
      sel.appendChild(opt);
    });
  }

  document.getElementById("lifeHistoryFilter")?.addEventListener("change", () => {
    loadLifeHistory();
  });

  async function loadLifeHistory() {
    const list = document.getElementById("lifeHistoryList");
    list.innerHTML = '<div class="loading-state">در حال دریافت لاگ‌ها...</div>';
    const filter = document.getElementById("lifeHistoryFilter")?.value || "";

    try {
      const url = filter ? `/api/life-tracker/history?event_type=${encodeURIComponent(filter)}` : "/api/life-tracker/history";
      const res = await fetch(url, { headers: getHeaders() });
      if (!res.ok) throw new Error();
      const data = await res.json();
      const entries = data.entries || [];

      list.innerHTML = "";
      if (entries.length === 0) {
        list.innerHTML = '<div class="loading-state">موردی برای نمایش یافت نشد</div>';
        return;
      }

      entries.forEach((item) => {
        const div = document.createElement("div");
        div.className = "timeline-item";
        div.innerHTML = `
          <div>
            <div style="font-weight:700; font-size:13px;">${item.emoji} ${item.type} ${item.mode ? `(${item.mode})` : ""}</div>
            <div style="font-size:11px; color:var(--hint-color); margin-top:2px;">
              📅 ${item.date} ${item.notes ? `| 📝 ${item.notes}` : ""}
            </div>
          </div>
          <button class="btn-item-delete" title="حذف رکورد">🗑️</button>
        `;

        div.querySelector(".btn-item-delete").addEventListener("click", async () => {
          if (!confirm(`آیا از حذف لاگ «${item.type}» مطمئن هستید؟`)) return;
          haptic("warning");
          try {
            await fetch(`/api/life-tracker/delete/${item.id}`, { method: "DELETE", headers: getHeaders() });
            showToast("رکورد حذف شد", "success");
            div.remove();
          } catch (e) {
            showToast("خطا در حذف رکورد", "error");
          }
        });

        list.appendChild(div);
      });
    } catch (e) {
      list.innerHTML = '<div class="loading-state" style="color:var(--danger-color)">خطا در بارگذاری تاریخچه</div>';
    }
  }

  // ==========================================
  // 6. HABITS TRACKER (REVAMPED)
  // ==========================================
  function setupStealthModeUI() {
    const tabHabits = document.getElementById("tab-habits");
    const btnToggle = document.getElementById("btnToggleStealth");

    if (isStealthMode) {
      tabHabits?.classList.add("stealth-active");
      btnToggle?.classList.add("active");
    } else {
      tabHabits?.classList.remove("stealth-active");
      btnToggle?.classList.remove("active");
    }

    btnToggle?.addEventListener("click", () => {
      isStealthMode = !isStealthMode;
      localStorage.setItem("notionyar_stealth", isStealthMode);
      tabHabits?.classList.toggle("stealth-active", isStealthMode);
      btnToggle?.classList.toggle("active", isStealthMode);
      haptic("medium");
      showToast(isStealthMode ? "حالت مخفی فعال شد 🕶️" : "حالت عادی فعال شد 👁️", "info");
      // Re-render heatmap if on analytics tab
      loadHabitsAnalytics();
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
    container.innerHTML = '<div class="loading-state">در حال دریافت وضعیت عادات...</div>';

    try {
      const res = await fetch(`/api/habits/day?date_iso=${dateIso}`, { headers: getHeaders() });
      if (!res.ok) throw new Error("خطا در دریافت اطلاعات عادات");

      habitDayData = await res.json();

      document.getElementById("habitDateTitle").textContent = habitDayData.jalali_title;
      document.getElementById("habitPercent").textContent = `${habitDayData.progress_percent}٪`;
      document.getElementById("habitCountDisplay").textContent = `${habitDayData.completed_count} از ${habitDayData.total_habits}`;
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
    } catch (err) {
      container.innerHTML = `<div class="loading-state" style="color:var(--danger-color)">${err.message}</div>`;
    }
  }

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

        card.className = `habit-card ${cardStatusClass}`;

        const codeTag = `[${h.code || "HBT"}]`;

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
          <button class="btn-habit-level ${h.status ? "active" : ""}">
            ${h.status ? h.status.replace(/^[0-9]-/, "") : "تنظیم کیفیت"}
          </button>
        `;

        // Checkmark Tap (One-tap complete/clear)
        card.querySelector(".habit-check-circle").addEventListener("click", async () => {
          haptic("light");
          const nextVal = isDone ? null : "1-💪 کامل";
          await setHabitStatus(h, nextVal);
        });

        // Level Button Tap (Opens Modal)
        card.querySelector(".btn-habit-level").addEventListener("click", () => {
          openHabitLevelModal(h);
        });

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

      // Reload to ensure precise formula progress calculation
      loadHabitsForDate(currentHabitDateIso);
    } catch (e) {
      showToast("خطا در ثبت وضعیت عادت", "error");
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
      loadHabitsForDate(currentHabitDateIso);
    } catch (e) {
      showToast("خطا در تکمیل خودکار عادات", "error");
    }
  });

  // Modal Level Selector (Cleaned: Freeze & Reset moved to Analytics section)
  function openHabitLevelModal(habitObj) {
    const modal = document.getElementById("habitLevelModal");
    const title = document.getElementById("modalHabitTitle");
    const body = document.getElementById("modalLevelOptions");

    title.textContent = `${habitObj.emoji} ${habitObj.name} - انتخاب سطح کیفیت`;
    body.innerHTML = "";

    const options = [
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
      btn.addEventListener("click", async () => {
        modal.style.display = "none";
        haptic("light");
        await setHabitStatus(habitObj, opt.key);
      });
      body.appendChild(btn);
    });

    modal.style.display = "flex";
  }

  document.getElementById("btnModalClose")?.addEventListener("click", () => {
    document.getElementById("habitLevelModal").style.display = "none";
  });

  // ==========================================
  // 7. HABIT ANALYTICS, STREAKS & DAY ACTIONS
  // ==========================================
  async function loadHabitsAnalytics() {
    try {
      const res = await fetch("/api/habits/analytics?period=7d", { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();

      const streaks = data.streaks || {};
      const matrix = data.matrix || {};

      document.getElementById("overallCurrentStreak").textContent = `${streaks.overall_streak?.current || 0} روز`;
      document.getElementById("overallBestStreak").textContent = `${streaks.overall_streak?.best || 0} روز`;

      // Render Rankings
      const rankList = document.getElementById("habitRankingsList");
      rankList.innerHTML = "";
      (matrix.habit_rankings || []).slice(0, 6).forEach((item) => {
        const div = document.createElement("div");
        div.className = "ranking-item";
        div.innerHTML = `
          <div>
            <span style="font-weight:700;">${item.info?.emoji || "🎯"} ${item.info?.fa || item.key}</span>
            <div class="ranking-bar-box">
              <div class="ranking-bar-fill" style="width:${Math.round(item.pct)}%;"></div>
            </div>
          </div>
          <span style="font-weight:800; color:var(--button-color); font-size:13px;">${Math.round(item.pct)}٪</span>
        `;
        rankList.appendChild(div);
      });

      // Render 7-day consistency Heatmap (Fix undefined in column headers)
      const heatmapContainer = document.getElementById("habitHeatmapContainer");
      if (matrix.daily_timeline && matrix.daily_timeline.length > 0) {
        let tableHtml = '<table class="heatmap-table"><thead><tr><th>عادت</th>';
        matrix.daily_timeline.forEach((day) => {
          const weekdayStr = day.weekday || "";
          const jDateStr = day.jalali_str ? day.jalali_str.split("/").slice(1).join("/") : (day.date ? day.date.slice(5) : "");
          tableHtml += `
            <th>
              <div style="font-size:11px; font-weight:700;">${weekdayStr}</div>
              <div style="font-size:9px; color:var(--hint-color); font-weight:normal;">${jDateStr}</div>
            </th>`;
        });
        tableHtml += "</tr></thead><tbody>";

        (matrix.habit_rankings || []).forEach((item) => {
          const habitLabel = isStealthMode
            ? `[${item.info?.code || item.key.toUpperCase()}]`
            : `${item.info?.emoji || ""} ${item.info?.fa || item.key}`;

          tableHtml += `<tr><td style="text-align:right; font-weight:600;">${habitLabel}</td>`;
          matrix.daily_timeline.forEach((day) => {
            const hStatus = day.habits?.[item.key];
            let cellClass = "none";
            if (hStatus === "1-💪 کامل") cellClass = "done";
            else if (hStatus === "2-🏃‍♂️ نیمه‌کامل" || hStatus === "3-🐢 سبک") cellClass = "partial";
            else if (day.is_frozen) cellClass = "frozen";
            tableHtml += `<td><div class="heatmap-cell ${cellClass}"></div></td>`;
          });
          tableHtml += "</tr>";
        });

        tableHtml += "</tbody></table>";
        heatmapContainer.innerHTML = tableHtml;
      }
    } catch (e) {
      console.error(e);
    }
  }

  // Action: Streak Freeze Day Modal
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
        loadHabitsForDate(currentHabitDateIso);
        loadHabitsAnalytics();
      } catch (e) {
        showToast("خطا در ثبت روز فریز", "error");
      }
    });
  });

  // Action: Reset Habit Day
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
      loadHabitsForDate(currentHabitDateIso);
      loadHabitsAnalytics();
    } catch (e) {
      showToast("خطا در بازنشانی عادات", "error");
    }
  });

  // ==========================================
  // 8. GRATITUDE BUILDER & JOURNAL REFLECTIONS
  // ==========================================
  function initGratitudeItems(dayData) {
    if (dayData?.gratitude_items && dayData.gratitude_items.length > 0) {
      gratitudeItems = dayData.gratitude_items.map((it, idx) => ({
        id: Date.now() + idx,
        tag: it.tag || "سایر",
        text: it.text || "",
      }));
    } else if (dayData?.gratitude) {
      // Parse plain text lines if previously entered
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

  // Gratitude Category Chips
  document.querySelectorAll("#gratTagsChips .btn-tag-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#gratTagsChips .btn-tag-chip").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentGratitudeTag = btn.getAttribute("data-tag") || "سایر";
      haptic("light");
    });
  });

  // Add Gratitude Item
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

  // Save All Gratitude Items
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
    } catch (e) {
      showToast("خطا در ذخیره دفتر شکرگزاری", "error");
    } finally {
      btn.disabled = false;
      btn.querySelector("span").textContent = "💾 ذخیره کل شکرگزاری‌ها در نوشن";
    }
  });

  // Journal Inputs Save Handlers (Book, Quran, Notes)
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
  // 9. RECENT LOGS
  // ==========================================
  async function loadRecentLogs() {
    try {
      const res = await fetch("/api/recent-logs", { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();

      const timeContainer = document.getElementById("recentTimeList");
      if (data.time_tracker?.length > 0) {
        timeContainer.innerHTML = "";
        data.time_tracker.forEach((item) => {
          const div = document.createElement("div");
          div.className = "timeline-item";
          div.innerHTML = `
            <div>
              <div style="font-weight:700; font-size:13px;">${item.name}</div>
              <div style="font-size:11px; color:var(--hint-color); margin-top:2px;">
                📅 ${item.date} | ⏰ ${item.time_range || item.duration + " د"}
              </div>
            </div>
            <button class="btn-item-delete" title="حذف رکورد">🗑️</button>
          `;
          div.querySelector(".btn-item-delete").addEventListener("click", async () => {
            if (!confirm(`آیا از حذف رکورد «${item.name}» مطمئن هستید؟`)) return;
            haptic("warning");
            try {
              await fetch(`/api/time-tracker/delete/${item.id}`, { method: "DELETE", headers: getHeaders() });
              showToast("رکورد زمان حذف شد", "success");
              div.remove();
            } catch (e) {
              showToast("خطا در حذف رکورد", "error");
            }
          });
          timeContainer.appendChild(div);
        });
      } else {
        timeContainer.innerHTML = '<div class="loading-state">هنوز رکوردی ثبت نشده است</div>';
      }

      const lifeContainer = document.getElementById("recentLifeList");
      if (data.life_tracker?.length > 0) {
        lifeContainer.innerHTML = "";
        data.life_tracker.forEach((item) => {
          const div = document.createElement("div");
          div.className = "timeline-item";
          div.innerHTML = `
            <div>
              <div style="font-weight:700; font-size:13px;">${item.emoji} ${item.type} ${item.mode ? `(${item.mode})` : ""}</div>
              <div style="font-size:11px; color:var(--hint-color); margin-top:2px;">
                📅 ${item.date} ${item.notes ? "| 📝 " + item.notes : ""}
              </div>
            </div>
            <button class="btn-item-delete" title="حذف رکورد">🗑️</button>
          `;
          div.querySelector(".btn-item-delete").addEventListener("click", async () => {
            if (!confirm(`آیا از حذف لاگ «${item.type}» مطمئن هستید؟`)) return;
            haptic("warning");
            try {
              await fetch(`/api/life-tracker/delete/${item.id}`, { method: "DELETE", headers: getHeaders() });
              showToast("لاگ حذف شد", "success");
              div.remove();
            } catch (e) {
              showToast("خطا در حذف لاگ", "error");
            }
          });
          lifeContainer.appendChild(div);
        });
      } else {
        lifeContainer.innerHTML = '<div class="loading-state">هنوز رکوردی ثبت نشده است</div>';
      }
    } catch (e) {
      console.error(e);
    }
  }

  // ==========================================
  // START APPLICATION
  // ==========================================
  initApp();
})();
