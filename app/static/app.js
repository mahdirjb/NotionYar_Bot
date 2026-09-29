// app/static/app.js
// NotionYar Telegram Mini App v2.0 - Rich UI & Analytics

(function () {
  const tg = window.Telegram?.WebApp;

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
  let lifeOptionsData = null;
  let currentHabitDateIso = null;
  let habitDayData = null;

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
  // 3. TIME TRACKER
  // ==========================================
  let selectedTimeDate = getDateFromOffset(0);

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
  // 4. LIFE TRACKER (REVAMPED)
  // ==========================================
  let selectedLifeDate = getDateFromOffset(0);

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
    selectedLifeMode = null;

    document.querySelectorAll(".life-tile").forEach((t) => t.classList.remove("active"));
    tileEl.classList.add("active");

    const modesBox = document.getElementById("lifeModesContainer");
    const modesChips = document.getElementById("lifeModesChips");
    const modesLabel = document.getElementById("lifeModesLabel");

    if (typeMeta.modes && typeMeta.modes.length > 0) {
      modesBox.style.display = "block";
      modesLabel.textContent = `حالت‌های «${typeMeta.name}»:`;
      modesChips.innerHTML = "";

      typeMeta.modes.forEach((m, idx) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "mode-chip" + (idx === 0 ? " active" : "");
        chip.innerHTML = `<span>${m.emoji}</span> <span>${m.name}</span>`;
        if (idx === 0) selectedLifeMode = m.name;

        chip.addEventListener("click", () => {
          modesChips.querySelectorAll(".mode-chip").forEach((c) => c.classList.remove("active"));
          chip.classList.add("active");
          selectedLifeMode = m.name;
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
    if (selectedLifeMode) text += ` (${selectedLifeMode})`;
    btn.innerHTML = `<span>${text}</span> <span class="btn-arrow">←</span>`;
  }

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
          mode: selectedLifeMode,
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
      selectFilterOption(opt, sel);
    });
  }

  function selectFilterOption(opt, sel) {
    sel.appendChild(opt);
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
  // 5. HABITS TRACKER (REVAMPED)
  // ==========================================
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

      // Fill Journal
      document.getElementById("habitGratitude").value = habitDayData.gratitude || "";
      document.getElementById("habitNotes").value = habitDayData.notes || "";
      document.getElementById("habitBook").value = habitDayData.book_detail || "";
      document.getElementById("habitQuran").value = habitDayData.quran_detail || "";

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

        card.innerHTML = `
          <div class="habit-check-circle">${isDone ? "✓" : ""}</div>
          <div class="habit-info">
            <div class="habit-name-row">
              <span>${h.emoji}</span>
              <span class="habit-title">${h.name}</span>
            </div>
            <div class="habit-desc">${h.description || ""}</div>
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
    if (!habitDayData?.page_id) return;

    try {
      await fetch("/api/habits/update-status", {
        method: "POST",
        headers: getHeaders(),
        body: JSON.stringify({
          page_id: habitDayData.page_id,
          habit_prop: habitObj.prop,
          select_val: selectVal,
        }),
      });

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

  // Modal Level Selector
  function openHabitLevelModal(habitObj) {
    const modal = document.getElementById("habitLevelModal");
    const title = document.getElementById("modalHabitTitle");
    const body = document.getElementById("modalLevelOptions");

    title.textContent = `${habitObj.emoji} ${habitObj.name} - انتخاب سطح`;
    body.innerHTML = "";

    const options = [
      { key: "1-💪 کامل", label: "💪 کامل", desc: habitObj.levels?.v1 || "انجام با بالاترین کیفیت" },
      { key: "2-🏃‍♂️ نیمه‌کامل", label: "🏃‍♂️ نیمه‌کامل", desc: habitObj.levels?.v2 || "کیفیت استاندارد" },
      { key: "3-🐢 سبک", label: "🐢 سبک", desc: habitObj.levels?.v3 || "حداقل اجرای ممکن" },
      { key: "فریز", label: "❄️ روز فریز (Streak Freeze)", desc: "محافظت از زنجیره در روزهای خاص" },
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

  // Habit Analytics & Streaks
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

      // Render 7-day consistency Heatmap
      const heatmapContainer = document.getElementById("habitHeatmapContainer");
      if (matrix.daily_timeline && matrix.daily_timeline.length > 0) {
        let tableHtml = '<table class="heatmap-table"><thead><tr><th>عادت</th>';
        matrix.daily_timeline.forEach((day) => {
          tableHtml += `<th>${day.day_label || day.date?.slice(5)}</th>`;
        });
        tableHtml += "</tr></thead><tbody>";

        (matrix.habit_rankings || []).forEach((item) => {
          tableHtml += `<tr><td style="text-align:right; font-weight:600;">${item.info?.emoji || ""} ${item.info?.fa || item.key}</td>`;
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

  // Journal Reflections
  document.querySelectorAll(".journal-form .btn-action").forEach((btn) => {
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
  // 6. RECENT LOGS
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

  // Start
  initApp();
})();
