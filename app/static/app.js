// app/static/app.js
// NotionYar Telegram Mini App Frontend Logic

(function () {
  const tg = window.Telegram?.WebApp;

  // Initialize Telegram WebApp
  if (tg) {
    tg.ready();
    tg.expand();
  }

  // State
  let currentUser = null;
  let currentDateIso = new Date().toISOString().split("T")[0];
  let selectedTimeSatisfaction = "5";
  let selectedLifeType = null;
  let selectedLifeMode = null;
  let lifeOptions = null;
  let currentHabitDateIso = null;
  let habitDayData = null;

  // Telegram Headers Helper
  function getHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (tg?.initData) {
      headers["X-Telegram-Init-Data"] = tg.initData;
    }
    return headers;
  }

  // Haptic Feedback Helper
  function haptic(type = "light") {
    try {
      if (tg?.HapticFeedback) {
        if (type === "success" || type === "error" || type === "warning") {
          tg.HapticFeedback.notificationOccurred(type);
        } else {
          tg.HapticFeedback.impactOccurred(type);
        }
      }
    } catch (e) {
      // Ignore
    }
  }

  // Toast Notification Helper
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

  // Calculate Date Offset (0 = Today, 1 = Yesterday, etc.)
  function getDateFromOffset(offset) {
    const d = new Date();
    d.setDate(d.getDate() - offset);
    return d.toISOString().split("T")[0];
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
      currentHabitDateIso = data.today_iso;

      // Update UI Header
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

      // Load Initial Tab Data
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

  // ==========================================
  // 2. TAB SWITCHING
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

  document.getElementById("btnRefresh")?.addEventListener("click", async () => {
    haptic("medium");
    showToast("در حال بروزرسانی اطلاعات...", "info");
    await initApp();
    showToast("داده‌ها بروز شدند", "success");
  });

  // ==========================================
  // 3. TIME TRACKER LOGIC
  // ==========================================
  let selectedTimeDate = getDateFromOffset(0);

  async function loadTimeTrackerMeta() {
    try {
      const res = await fetch("/api/time-tracker/meta", { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();

      const select = document.getElementById("timePerson");
      select.innerHTML = '<option value="">انتخاب انجام‌دهنده (اختیاری)</option>';

      if (data.persons && data.persons.length > 0) {
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

  // Date Pills
  document.querySelectorAll("[data-date-offset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-date-offset]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const offset = parseInt(btn.getAttribute("data-date-offset"), 10);
      selectedTimeDate = getDateFromOffset(offset);
      document.getElementById("timeCustomDate").value = "";
      haptic("light");
    });
  });

  document.getElementById("timeCustomDate")?.addEventListener("change", (e) => {
    if (e.target.value) {
      document.querySelectorAll("[data-date-offset]").forEach((b) => b.classList.remove("active"));
      selectedTimeDate = e.target.value;
      haptic("light");
    }
  });

  // Duration Quick Pills
  document.querySelectorAll(".quick-duration-pills .btn-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mins = btn.getAttribute("data-min");
      document.getElementById("timeDuration").value = mins;
      haptic("light");
    });
  });

  // Auto calculate duration from start and end time
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
      if (diff > 0) {
        document.getElementById("timeDuration").value = diff;
      }
    }
  }
  timeStart?.addEventListener("change", autoCalculateDuration);
  timeEnd?.addEventListener("change", autoCalculateDuration);

  // Satisfaction Stars
  document.querySelectorAll("#timeSatisfaction .btn-star").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#timeSatisfaction .btn-star").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      selectedTimeSatisfaction = btn.getAttribute("data-val");
      haptic("light");
    });
  });

  // Time Tracker Submit
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
      if (!res.ok) {
        throw new Error(data.detail || "خطا در ثبت زمان");
      }

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
  // 4. LIFE TRACKER LOGIC
  // ==========================================
  let selectedLifeDate = getDateFromOffset(0);

  async function loadLifeTrackerOptions() {
    try {
      const res = await fetch("/api/life-tracker/options", { headers: getHeaders() });
      if (!res.ok) return;
      lifeOptions = await res.json();
      renderLifeCategories();
    } catch (e) {
      console.error(e);
    }
  }

  function renderLifeCategories() {
    const grid = document.getElementById("lifeCategoriesGrid");
    if (!grid || !lifeOptions?.types) return;

    grid.innerHTML = "";
    lifeOptions.types.forEach((typeObj) => {
      const card = document.createElement("div");
      card.className = "cat-card";
      card.innerHTML = `
        <span class="cat-emoji">${typeObj.emoji}</span>
        <span class="cat-name">${typeObj.name}</span>
      `;
      card.addEventListener("click", () => {
        selectLifeCategory(typeObj, card);
        haptic("light");
      });
      grid.appendChild(card);
    });
  }

  function selectLifeCategory(typeObj, cardElement) {
    selectedLifeType = typeObj.name;
    selectedLifeMode = null;

    document.querySelectorAll(".cat-card").forEach((c) => c.classList.remove("active"));
    cardElement.classList.add("active");

    const modesContainer = document.getElementById("lifeModesContainer");
    const modesChips = document.getElementById("lifeModesChips");
    const modesLabel = document.getElementById("lifeModesLabel");
    const btnSubmit = document.getElementById("btnSubmitLife");

    if (typeObj.modes && typeObj.modes.length > 0) {
      modesContainer.style.display = "block";
      modesLabel.textContent = `حالت‌های «${typeObj.name}»:`;
      modesChips.innerHTML = "";

      typeObj.modes.forEach((modeObj, idx) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "mode-chip" + (idx === 0 ? " active" : "");
        chip.innerHTML = `<span>${modeObj.emoji}</span> <span>${modeObj.name}</span>`;
        if (idx === 0) selectedLifeMode = modeObj.name;

        chip.addEventListener("click", () => {
          document.querySelectorAll(".mode-chip").forEach((mc) => mc.classList.remove("active"));
          chip.classList.add("active");
          selectedLifeMode = modeObj.name;
          haptic("light");
          updateLifeSubmitButton();
        });
        modesChips.appendChild(chip);
      });
    } else {
      modesContainer.style.display = "none";
    }

    updateLifeSubmitButton();
  }

  function updateLifeSubmitButton() {
    const btnSubmit = document.getElementById("btnSubmitLife");
    if (!selectedLifeType) {
      btnSubmit.disabled = true;
      btnSubmit.innerHTML = "<span>لطفاً یک نوع را انتخاب کنید</span>";
      return;
    }

    btnSubmit.disabled = false;
    let label = `ثبت ${selectedLifeType}`;
    if (selectedLifeMode) {
      label += ` (${selectedLifeMode})`;
    }
    btnSubmit.innerHTML = `<span>${label}</span> <span class="btn-arrow">←</span>`;
  }

  // Date Pills for Life Tracker
  document.querySelectorAll("[data-life-offset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-life-offset]").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const offset = parseInt(btn.getAttribute("data-life-offset"), 10);
      selectedLifeDate = getDateFromOffset(offset);
      document.getElementById("lifeCustomDate").value = "";
      haptic("light");
    });
  });

  document.getElementById("lifeCustomDate")?.addEventListener("change", (e) => {
    if (e.target.value) {
      document.querySelectorAll("[data-life-offset]").forEach((b) => b.classList.remove("active"));
      selectedLifeDate = e.target.value;
      haptic("light");
    }
  });

  // Life Tracker Submit
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
    btnSubmit.innerHTML = "<span>در حال ذخیره در روزمرگی...</span>";

    const notes = document.getElementById("lifeNotes").value.trim() || null;

    try {
      const res = await fetch("/api/life-tracker/create", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          event_type: selectedLifeType,
          mode: selectedLifeMode,
          date_iso: selectedLifeDate,
          notes: notes,
        }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "خطا در ثبت روزمرگی");

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

  // ==========================================
  // 5. HABITS TRACKER LOGIC
  // ==========================================
  async function loadHabitsForDate(dateIso) {
    const listContainer = document.getElementById("habitsListContainer");
    listContainer.innerHTML = '<div class="loading-state">در حال بارگذاری عادات...</div>';

    try {
      const res = await fetch(`/api/habits/day?date_iso=${dateIso}`, { headers: getHeaders() });
      if (!res.ok) throw new Error("خطا در دریافت عادات روز");

      habitDayData = await res.json();

      document.getElementById("habitDateTitle").textContent = habitDayData.jalali_title;
      document.getElementById("habitPercent").textContent = `${habitDayData.progress_percent}٪`;
      document.getElementById("habitCheerleader").textContent = habitDayData.cheerleader;
      document.getElementById("habitProgressFill").style.width = `${habitDayData.progress_percent}%`;

      // Fill Reflection Fields
      document.getElementById("habitGratitude").value = habitDayData.gratitude || "";
      document.getElementById("habitNotes").value = habitDayData.notes || "";
      document.getElementById("habitBook").value = habitDayData.book_detail || "";
      document.getElementById("habitQuran").value = habitDayData.quran_detail || "";

      renderHabitsList(habitDayData.habits);
    } catch (err) {
      listContainer.innerHTML = `<div class="loading-state" style="color:var(--danger-color)">${err.message}</div>`;
    }
  }

  function renderHabitsList(habits) {
    const listContainer = document.getElementById("habitsListContainer");
    listContainer.innerHTML = "";

    const statusOptions = [
      { key: "انجام شد", label: "✅ انجام", class: "done" },
      { key: "ناقص", label: "⚠️ ناقص", class: "partial" },
      { key: "انجام نشد", label: "❌ نشد", class: "skipped" },
      { key: "فریز", label: "❄️ فریز", class: "frozen" },
    ];

    habits.forEach((h) => {
      const row = document.createElement("div");
      row.className = "habit-row";

      const header = document.createElement("div");
      header.className = "habit-header";
      header.innerHTML = `
        <span class="habit-title">${h.name}</span>
        <span class="habit-desc">${h.description}</span>
      `;

      const pillsContainer = document.createElement("div");
      pillsContainer.className = "habit-status-pills";

      statusOptions.forEach((opt) => {
        const pill = document.createElement("button");
        pill.type = "button";
        const isActive = h.status === opt.key;
        pill.className = `btn-status-pill ${opt.class}${isActive ? " active" : ""}`;
        pill.textContent = opt.label;

        pill.addEventListener("click", async () => {
          haptic("light");
          const newVal = isActive ? null : opt.key;

          // Optimistic UI update
          pillsContainer.querySelectorAll(".btn-status-pill").forEach((p) => p.classList.remove("active"));
          if (newVal) pill.classList.add("active");
          h.status = newVal;

          try {
            await fetch("/api/habits/update-status", {
              method: "POST",
              headers: getHeaders(),
              body: JSON.stringify({
                page_id: habitDayData.page_id,
                habit_prop: h.name,
                select_val: newVal,
              }),
            });
            // Recalculate progress visually
            recalculateHabitProgress();
          } catch (e) {
            showToast("خطا در به‌روزرسانی عادت", "error");
          }
        });

        pillsContainer.appendChild(pill);
      });

      row.appendChild(header);
      row.appendChild(pillsContainer);
      listContainer.appendChild(row);
    });
  }

  function recalculateHabitProgress() {
    if (!habitDayData?.habits) return;
    const total = habitDayData.habits.length;
    let done = 0;
    habitDayData.habits.forEach((h) => {
      if (h.status === "انجام شد" || h.status === "فریز") done += 1;
      else if (h.status === "ناقص") done += 0.5;
    });
    const pct = Math.round((done / total) * 100);
    document.getElementById("habitPercent").textContent = `${pct}٪`;
    document.getElementById("habitProgressFill").style.width = `${pct}%`;
  }

  // Habit Date Switchers
  document.getElementById("btnHabitPrevDay")?.addEventListener("click", () => {
    haptic("light");
    document.getElementById("btnHabitToday").classList.remove("active");
    document.getElementById("btnHabitPrevDay").classList.add("active");
    currentHabitDateIso = getDateFromOffset(1);
    loadHabitsForDate(currentHabitDateIso);
  });

  document.getElementById("btnHabitToday")?.addEventListener("click", () => {
    haptic("light");
    document.getElementById("btnHabitPrevDay").classList.remove("active");
    document.getElementById("btnHabitToday").classList.add("active");
    currentHabitDateIso = getDateFromOffset(0);
    loadHabitsForDate(currentHabitDateIso);
  });

  // Habit Reflection Save Buttons
  document.querySelectorAll(".reflection-section .btn-action").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!habitDayData?.page_id) return;
      const field = btn.getAttribute("data-field");
      let text = "";
      if (field === "gratitude") text = document.getElementById("habitGratitude").value;
      if (field === "notes") text = document.getElementById("habitNotes").value;
      if (field === "book") text = document.getElementById("habitBook").value;
      if (field === "quran") text = document.getElementById("habitQuran").value;

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
  // 6. RECENT LOGS LOGIC
  // ==========================================
  async function loadRecentLogs() {
    try {
      const res = await fetch("/api/recent-logs", { headers: getHeaders() });
      if (!res.ok) return;
      const data = await res.json();

      // Recent Time Logs
      const timeContainer = document.getElementById("recentTimeList");
      if (data.time_tracker?.length > 0) {
        timeContainer.innerHTML = "";
        data.time_tracker.forEach((item) => {
          const div = document.createElement("div");
          div.className = "recent-item";
          div.innerHTML = `
            <div>
              <div class="recent-title">${item.name}</div>
              <div class="recent-meta">📅 ${item.date} | ⏰ ${item.time_range || item.duration + " د"}</div>
            </div>
            <span class="recent-tag">${item.person || "—"}</span>
          `;
          timeContainer.appendChild(div);
        });
      } else {
        timeContainer.innerHTML = '<div class="loading-state">هنوز رکوردی ثبت نشده است</div>';
      }

      // Recent Life Logs
      const lifeContainer = document.getElementById("recentLifeList");
      if (data.life_tracker?.length > 0) {
        lifeContainer.innerHTML = "";
        data.life_tracker.forEach((item) => {
          const div = document.createElement("div");
          div.className = "recent-item";
          const modeText = item.mode ? ` (${item.mode})` : "";
          div.innerHTML = `
            <div>
              <div class="recent-title">${item.emoji} ${item.type}${modeText}</div>
              <div class="recent-meta">📅 ${item.date} ${item.notes ? " | " + item.notes : ""}</div>
            </div>
            <span class="recent-tag">${item.type}</span>
          `;
          lifeContainer.appendChild(div);
        });
      } else {
        lifeContainer.innerHTML = '<div class="loading-state">هنوز رکوردی ثبت نشده است</div>';
      }
    } catch (e) {
      console.error(e);
    }
  }

  // Run on start
  initApp();
})();
