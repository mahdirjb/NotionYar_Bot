# app/handlers/habits.py

import asyncio
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, Optional, List
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.keyboards.reply import BTN_HABITS
from app.keyboards.inline import (
    build_habit_hub_keyboard,
    build_habit_detailed_keyboard,
    build_habit_streaks_keyboard,
    build_habit_matrix_keyboard,
    get_habit_level_picker_keyboard,
    get_quick_run_keyboard,
    get_gratitude_accumulator_keyboard,
    get_gratitude_item_picker_keyboard,
    get_quran_detail_keyboard,
    get_habit_reset_confirm_keyboard,
    get_habit_bulk_fill_confirm_keyboard,
    get_habit_notes_keyboard,
    get_habit_custom_date_cancel_keyboard,
    HABIT_STATUS_ICONS,
)
from app.states.habit_state import HabitState
from app.filters.permissions import HasPermission
from app.services.auth_service import PERM_ADMIN
from app.services.date_helper import (
    format_jalali_full_display,
    parse_user_date_input,
)
from app.services.notion_service import (
    HABIT_ITEMS,
    HABIT_DESCRIPTIONS,
    HABIT_LEVELS,
    LEVEL_BADGES,
    get_or_create_habit_day,
    parse_existing_gratitude_log,
    update_habit_entry,
    bulk_update_all_habits,
    batch_update_habit_dict,
    update_habit_notes,
    update_habit_gratitude,
    update_habit_quran_detail,
    reset_habit_day,
)
from app.services.habit_analytics_service import calculate_habit_streaks

router = Router()


def _calculate_date_from_offset(offset_days: int) -> tuple[str, str, str]:
    """Returns (gregorian_iso, full_jalali_title, relative_label)."""
    tz = timezone(timedelta(hours=3, minutes=30))
    g_target = datetime.now(tz).date() - timedelta(days=offset_days)
    g_iso = g_target.isoformat()
    full_jalali = format_jalali_full_display(g_iso)

    if offset_days == 0:
        rel_label = "📍 امروز"
    elif offset_days == 1:
        rel_label = "⏮ دیروز"
    elif offset_days == -1:
        rel_label = "⏭ فردا"
    elif offset_days > 1:
        rel_label = f"🗓 {offset_days} روز قبل"
    else:
        rel_label = f"🗓 {abs(offset_days)} روز بعد"

    return g_iso, full_jalali, rel_label


def _build_progress_bar(percent_float: float) -> str:
    """Generates visual progress bar."""
    pct = max(0.0, min(1.0, percent_float))
    pct_int = int(round(pct * 100))
    filled_count = int(round(pct * 10))

    if filled_count == 10:
        bar = "🟩" * 10
    elif filled_count == 0:
        bar = "⬜" * 10
    else:
        bar = ("🟩" * max(0, filled_count - 1)) + "🟨" + ("⬜" * (10 - filled_count))

    return f"[{bar}] <b>{pct_int}%</b>"


def _format_hub_text(
    page_data: Dict[str, Any],
    full_jalali: str,
    rel_label: str,
    stealth: bool = False,
    streaks_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Formats clean Hub landing message with streak integration."""
    pct_int = int(round(max(0.0, min(1.0, float(page_data.get("progress", 0.0)))) * 100))

    if stealth:
        return (
            "🕶️ <b>[STEALTH MODE - HABIT HUB]</b>\n"
            f"📅 <code>{full_jalali}</code> | 📊 <b>{pct_int}%</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 <i>جزئیات برای حفظ حریم خصوصی پنهان هستند.</i>\n"
            "یک گزینه را برای ثبت یا مدیریت انتخاب کنید:"
        )

    prog_bar = _build_progress_bar(float(page_data.get("progress", 0.0)))
    cheerleader = str(page_data.get("cheerleader", "")).strip()
    notes = str(page_data.get("notes", "")).strip()
    gratitude = str(page_data.get("gratitude_log", "")).strip()
    quran_detail = str(page_data.get("quran_detail", "")).strip()

    habits = page_data.get("habits", {})
    completed_count = sum(
        1
        for v in habits.values()
        if v in ["1-💪 کامل", "2-🏃‍♂️ نیمه‌کامل", "3-🐢 سبک"]
    )

    lines = [
        "🎯 <b>هاب مدیریت عادات روزانه</b>",
        f"📅 <b>تاریخ:</b> <code>{full_jalali}</code> ({rel_label})",
        "",
        f"📊 <b>پیشرفت:</b> {prog_bar} ({completed_count} از ۱۲ عادت)",
        f"📣 <b>وضعیت:</b> <i>{cheerleader}</i>",
    ]

    if streaks_data:
        ov = streaks_data.get("overall", {})
        c_ov = ov.get("current", 0)
        b_ov = ov.get("best", 0)
        lines.append(f"🔥 <b>زنجیره پیوستگی:</b> <b>{c_ov} روز متوالی</b> (رکورد: {b_ov} روز)")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    if quran_detail:
        lines.append(f"📖 <b>قرآن:</b> <code>{quran_detail}</code> ✨")

    if gratitude:
        lines.append("🌸 <b>شکرگزاری روز:</b> <i>ثبت شده ✅</i>")
    else:
        lines.append("🌸 <b>شکرگزاری روز:</b> <i>(ثبت نشده ▫️)</i>")

    if notes:
        lines.append(
            f"📝 <b>یادداشت روز:</b> <i>«{notes[:35]}...»</i>"
            if len(notes) > 35
            else f"📝 <b>یادداشت روز:</b> <i>«{notes}»</i>"
        )
    else:
        lines.append("📝 <b>یادداشت روز:</b> <i>(ثبت نشده ▫️)</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚡ برای ثبت سریع یا مشاهده جزئیات، گزینه‌های زیر را لمس کنید:")

    return "\n".join(lines)


def _format_detailed_text(
    page_data: Dict[str, Any],
    full_jalali: str,
    rel_label: str,
    stealth: bool = False,
    streaks_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Formats the 12-habit detailed overview text with individual streak badges."""
    pct_int = int(round(max(0.0, min(1.0, float(page_data.get("progress", 0.0)))) * 100))
    habits: Dict[str, Optional[str]] = page_data.get("habits", {})
    quran_detail = str(page_data.get("quran_detail", "")).strip()
    h_streaks = streaks_data.get("habit_streaks", {}) if streaks_data else {}

    if stealth:
        lines = [
            "🕶️ <b>[STEALTH MODE - DETAILED VIEW]</b>",
            f"📅 <code>{full_jalali}</code> | 📊 <b>{pct_int}%</b>",
            "━━━━━━━━━━━━━━━━━━━━━━",
        ]
        grid_items: List[str] = []
        for h_key, h_info in HABIT_ITEMS.items():
            val = habits.get(h_key)
            icon = HABIT_STATUS_ICONS.get(val or "", "▫️")
            grid_items.append(f"[{h_info['code']}]: {icon}")

        for i in range(0, len(grid_items), 3):
            lines.append("   ".join(grid_items[i : i + 3]))

        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    prog_bar = _build_progress_bar(float(page_data.get("progress", 0.0)))
    lines = [
        "📋 <b>نمای تفصیلی ۱۲ عادت روزانه</b>",
        f"📅 <b>تاریخ:</b> <code>{full_jalali}</code> ({rel_label})",
        f"📊 <b>پیشرفت:</b> {prog_bar}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    categories = {
        "💪 جسم و سلامت": ["bt", "fr", "ex"],
        "🏡 نظم و محیط": ["mb"],
        "🧘 ذهن و آرامش": ["md", "gr"],
        "✨ معنویت و درون": ["rq", "sl", "es", "ps", "bp", "sg"],
    }

    for cat_title, keys in categories.items():
        lines.append(f"<b>{cat_title}:</b>")
        for k in keys:
            h_info = HABIT_ITEMS[k]
            val = habits.get(k)
            badge = LEVEL_BADGES.get(val or "", "▫️ ثبت‌نشده")
            streak_num = h_streaks.get(k, {}).get("current", 0)
            streak_badge = f" 🔥 <code>{streak_num}d</code>" if streak_num > 0 else ""
            extra = f" (<code>{quran_detail}</code>)" if k == "rq" and quran_detail else ""
            lines.append(f"  {h_info['emoji']} {h_info['fa']}: <b>{badge}</b>{streak_badge}{extra}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("👆 روی هر عادت بزنید تا وضعیت و سطوح آن را تنظیم کنید:")
    return "\n".join(lines)


def _format_streaks_dashboard_text(
    streaks_data: Dict[str, Any], full_jalali: str
) -> str:
    """Formats full leaderboard dashboard of Habit Streaks and historical records."""
    ov = streaks_data.get("overall", {})
    h_streaks = streaks_data.get("habit_streaks", {})
    total_days = streaks_data.get("total_days_analyzed", 0)

    lines = [
        "🔥 <b>داشبورد تداوم و رکوردهای تاریخی</b>",
        f"📅 <code>{full_jalali}</code>",
        f"📈 <i>تحلیل بر پایه {total_days} روز ثبت‌شده در نوشن</i>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🏆 <b>تداوم روزانه کل (پیشرفت بالای ۵۰٪):</b>",
        f"  ⚡ زنجیره فعال فعلی: <b>{ov.get('current', 0)} روز متوالی</b>",
        f"  👑 بیشترین رکورد تاریخی: <b>{ov.get('best', 0)} روز</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>وضعیت زنجیره ۱۲ عادت هدف:</b>\n",
    ]

    # Sort habits by current streak descending
    sorted_habits = sorted(
        HABIT_ITEMS.items(),
        key=lambda item: (h_streaks.get(item[0], {}).get("current", 0), h_streaks.get(item[0], {}).get("best", 0)),
        reverse=True,
    )

    for h_key, h_info in sorted_habits:
        s_info = h_streaks.get(h_key, {"current": 0, "best": 0})
        cur = s_info["current"]
        best = s_info["best"]

        flame = "🔥" if cur >= 7 else ("✨" if cur > 0 else "▫️")
        lines.append(
            f"{flame} <b>{h_info['emoji']} {h_info['fa']}</b>:\n"
            f"   └ 🏃 فعلی: <b>{cur} روز</b> | 👑 بهترین: <b>{best} روز</b>"
        )

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>استمرار حتی در سطح ۳ (سبک)، زنجیره شما را زنده نگه می‌دارد!</i>")
    return "\n".join(lines)


# ==========================================
# 🚀 MAIN ENTRY & REFRESH
# ==========================================


@router.message(F.text == BTN_HABITS, HasPermission(PERM_ADMIN))
@router.message(F.text == "/habits", HasPermission(PERM_ADMIN))
async def cmd_habits_dashboard(message: Message, state: FSMContext, bot: Bot) -> None:
    """Main landing handler: Opens clean Habit Hub."""
    await state.clear()
    wait_msg = await message.answer("🔄 در حال بارگذاری هاب عادات و محاسبه تداوم...")

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(0)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(page_data, full_jalali, rel_label, stealth=False, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=0, stealth_mode=False)

    await wait_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("hb_ref:"), HasPermission(PERM_ADMIN))
async def cb_refresh_habits(call: CallbackQuery, state: FSMContext) -> None:
    """Refreshes the hub card from Notion."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    parts = call.data.split(":")
    offset_days = int(parts[1]) if len(parts) > 1 else 0

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(page_data, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await call.answer("🔄 کارنامه و تداوم به‌روزرسانی شدند.")
    except Exception:
        await call.answer("اطلاعات از قبل به‌روز است.")


# ==========================================
# 🔥 STREAKS & CONSISTENCY LEADERBOARD
# ==========================================


@router.callback_query(F.data.startswith("hb_streaks:"), HasPermission(PERM_ADMIN))
async def cb_view_streaks(call: CallbackQuery, state: FSMContext) -> None:
    """Opens dedicated Streaks & Records Dashboard."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    parts = call.data.split(":")
    offset_days = int(parts[1]) if len(parts) > 1 else 0

    _, full_jalali, _ = _calculate_date_from_offset(offset_days)
    streaks_data = calculate_habit_streaks()

    text = _format_streaks_dashboard_text(streaks_data, full_jalali)
    kb = build_habit_streaks_keyboard(offset_days=offset_days)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


# ==========================================
# 📋 VIEW SWITCHING (Hub vs Detailed)
# ==========================================


@router.callback_query(F.data.startswith("hb_view_det:"), HasPermission(PERM_ADMIN))
async def cb_view_detailed(call: CallbackQuery, state: FSMContext) -> None:
    """Switches to the 12-habit detailed grid view."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_detailed_text(page_data, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_detailed_keyboard(
        page_data.get("habits", {}), offset_days=offset_days, stealth_mode=stealth
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_view_hub:"), HasPermission(PERM_ADMIN))
async def cb_view_hub(call: CallbackQuery, state: FSMContext) -> None:
    """Switches back to the clean Hub view."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(page_data, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_back:"), HasPermission(PERM_ADMIN))
async def cb_back_to_hub(call: CallbackQuery, state: FSMContext) -> None:
    """Standard back handler to Hub view."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    await state.clear()
    await state.update_data(stealth=stealth)

    parts = call.data.split(":")
    offset_days = int(parts[1]) if len(parts) > 1 else 0

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(page_data, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


# ==========================================
# 🕶️ STEALTH & NAVIGATION
# ==========================================


@router.callback_query(F.data.startswith("hb_tog_stl:"), HasPermission(PERM_ADMIN))
async def cb_toggle_stealth(call: CallbackQuery, state: FSMContext) -> None:
    """Toggles Stealth (Privacy) mode on/off."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = not data.get("stealth", False)
    await state.update_data(stealth=stealth)

    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(page_data, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    mode_text = "روشن شد 🕶️" if stealth else "خاموش شد ☀️"
    await call.answer(f"حالت حریم خصوصی {mode_text}")


@router.callback_query(F.data.startswith("hb_nav:"), HasPermission(PERM_ADMIN))
async def cb_navigate_days(call: CallbackQuery, state: FSMContext) -> None:
    """Navigates to another day."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(page_data, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


# ==========================================
# ⚡ QUICK-RUN WIZARD (Supports Binary Habits)
# ==========================================


@router.callback_query(F.data.startswith("hb_qr_start:"), HasPermission(PERM_ADMIN))
async def cb_start_quick_run(call: CallbackQuery, state: FSMContext) -> None:
    """Starts the Quick-Run Wizard."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, _ = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    keys = list(HABIT_ITEMS.keys())
    await state.update_data(
        offset_days=offset_days,
        page_id=page_data["id"],
        qr_keys=keys,
        qr_idx=0,
        qr_collected={},
        stealth=stealth,
    )
    await state.set_state(HabitState.quick_run_active)

    first_key = keys[0]
    h_info = HABIT_ITEMS[first_key]
    h_desc = HABIT_DESCRIPTIONS.get(first_key, {})
    is_binary = h_info.get("binary", False)

    if stealth:
        text = (
            f"⚡ <b>[STEALTH QUICK-RUN] ({1}/{len(keys)})</b>\n"
            f"🎯 <b>[{h_info['code']}]</b>\n"
            f"Select level:"
        )
    else:
        if is_binary:
            desc_text = f"✅ انجام شد: <i>{h_desc.get('v1', 'انجام کامل')}</i>"
        else:
            desc_text = (
                f"💪 ۱. کامل: <i>{h_desc.get('v1', '')}</i>\n"
                f"🏃 ۲. معمول: <i>{h_desc.get('v2', '')}</i>\n"
                f"🐢 ۳. سبک: <i>{h_desc.get('v3', '')}</i>"
            )

        text = (
            f"⚡ <b>ثبت سریع زنجیره‌ای (گام ۱ از ۱۲)</b>\n"
            f"📅 <code>{full_jalali}</code>\n\n"
            f"🎯 عادت: <b>{h_info['emoji']} {h_info['fa']}</b>\n\n"
            f"📋 <b>راهنما:</b>\n{desc_text}\n\n"
            f"وضعیت را لمس کنید:"
        )

    kb = get_quick_run_keyboard(first_key, offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(
    F.data.startswith("hb_qr_val:") | F.data.startswith("hb_qr_skip:"),
    HasPermission(PERM_ADMIN),
)
async def cb_quick_run_step(call: CallbackQuery, state: FSMContext) -> None:
    """Processes each step in the Quick-Run Wizard."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    keys: List[str] = data.get("qr_keys", list(HABIT_ITEMS.keys()))
    idx: int = data.get("qr_idx", 0)
    collected: Dict[str, Optional[str]] = data.get("qr_collected", {})
    offset_days: int = data.get("offset_days", 0)
    page_id: str = data.get("page_id", "")
    stealth: bool = data.get("stealth", False)

    current_key = keys[idx]

    if call.data.startswith("hb_qr_val:"):
        _, _, lvl_str, _ = call.data.split(":")
        select_val = HABIT_LEVELS.get(lvl_str)
        collected[current_key] = select_val

    next_idx = idx + 1
    if next_idx < len(keys):
        await state.update_data(qr_idx=next_idx, qr_collected=collected)
        next_key = keys[next_idx]
        h_info = HABIT_ITEMS[next_key]
        h_desc = HABIT_DESCRIPTIONS.get(next_key, {})
        is_binary = h_info.get("binary", False)
        _, full_jalali, _ = _calculate_date_from_offset(offset_days)

        if stealth:
            text = (
                f"⚡ <b>[STEALTH QUICK-RUN] ({next_idx + 1}/{len(keys)})</b>\n"
                f"🎯 <b>[{h_info['code']}]</b>\n"
                f"Select level:"
            )
        else:
            if is_binary:
                desc_text = f"✅ انجام شد: <i>{h_desc.get('v1', 'انجام کامل')}</i>"
            else:
                desc_text = (
                    f"💪 ۱. کامل: <i>{h_desc.get('v1', '')}</i>\n"
                    f"🏃 ۲. معمول: <i>{h_desc.get('v2', '')}</i>\n"
                    f"🐢 ۳. سبک: <i>{h_desc.get('v3', '')}</i>"
                )

            text = (
                f"⚡ <b>ثبت سریع زنجیره‌ای (گام {next_idx + 1} از {len(keys)})</b>\n"
                f"📅 <code>{full_jalali}</code>\n\n"
                f"🎯 عادت: <b>{h_info['emoji']} {h_info['fa']}</b>\n\n"
                f"📋 <b>راهنما:</b>\n{desc_text}\n\n"
                f"وضعیت را لمس کنید:"
            )

        kb = get_quick_run_keyboard(next_key, offset_days)
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await call.answer()
    else:
        await call.message.edit_text("⏳ در حال ذخیره یکپارچه تمام عادات در نوشن...")
        if page_id and collected:
            batch_update_habit_dict(page_id, collected)

        await state.clear()
        await state.update_data(stealth=stealth)

        g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
        updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
        streaks_data = calculate_habit_streaks()

        text = _format_hub_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
        kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await call.answer("⚡ تمام ۱۲ عادت با موفقیت ثبت شدند! 🎉")


# ==========================================
# 🎯 SINGLE HABIT PICKER & LEVEL SELECT
# ==========================================


@router.callback_query(F.data.startswith("hb_pk:"), HasPermission(PERM_ADMIN))
async def cb_pick_habit_level(call: CallbackQuery, state: FSMContext) -> None:
    """Opens level picker for a single habit."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)

    _, h_key, offset_str = call.data.split(":")
    offset_days = int(offset_str)

    h_info = HABIT_ITEMS.get(h_key, {"fa": "عادت", "emoji": "🎯", "code": "HBT", "binary": False})
    h_desc = HABIT_DESCRIPTIONS.get(h_key, {})
    is_binary = h_info.get("binary", False)
    _, full_jalali, _ = _calculate_date_from_offset(offset_days)

    if stealth:
        text = (
            f"🎯 <b>[{h_info['code']}]</b>\n"
            f"📅 <code>{full_jalali}</code>\n\n"
            f"Select completion level:"
        )
    else:
        if is_binary:
            desc_text = f"✅ <b>انجام شد:</b> <i>{h_desc.get('v1', 'انجام کامل')}</i>"
        else:
            desc_text = (
                f"💪 <b>۱. کامل (بونوس):</b> <i>{h_desc.get('v1', '')}</i>\n"
                f"🏃 <b>۲. معمول (استاندارد):</b> <i>{h_desc.get('v2', '')}</i>\n"
                f"🐢 <b>۳. سبک (حداقلی):</b> <i>{h_desc.get('v3', '')}</i>"
            )

        text = (
            f"🎯 <b>تنظیم وضعیت: {h_info['emoji']} {h_info['fa']}</b>\n"
            f"📅 <code>{full_jalali}</code>\n\n"
            f"📋 <b>راهنمای سطوح این عادت:</b>\n{desc_text}\n\n"
            f"یکی از گزینه‌های زیر را انتخاب کنید:"
        )

    kb = get_habit_level_picker_keyboard(h_key, offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_set:"), HasPermission(PERM_ADMIN))
async def cb_set_habit_level(call: CallbackQuery, state: FSMContext) -> None:
    """Sets habit level in Notion and returns to Detailed view."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)

    _, h_key, lvl_str, offset_str = call.data.split(":")
    offset_days = int(offset_str)

    h_info = HABIT_ITEMS.get(h_key)
    if not h_info:
        await call.answer("❌ عادت نامعتبر است.", show_alert=True)
        return

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    select_val = HABIT_LEVELS.get(lvl_str) if lvl_str != "0" else None
    update_habit_entry(page_data["id"], h_info["prop"], select_val)

    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_detailed_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_detailed_keyboard(
        updated_page.get("habits", {}),
        offset_days=offset_days,
        stealth_mode=stealth,
    )

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    status_name = select_val or "پاک شد 🗑"
    await call.answer(f"✅ {h_info['fa']}: {status_name}")


# ==========================================
# 📖 QURAN DETAIL PROMPT & HANDLER
# ==========================================


@router.callback_query(F.data.startswith("hb_qrn_det:"), HasPermission(PERM_ADMIN))
async def cb_prompt_quran_detail(call: CallbackQuery, state: FSMContext) -> None:
    """Prompts the user to enter Quran page number or Surah name."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    offset_days = int(call.data.split(":")[1])
    g_iso, full_jalali, _ = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    await state.update_data(
        offset_days=offset_days,
        page_id=page_data["id"],
        dash_msg_id=call.message.message_id,
    )
    await state.set_state(HabitState.waiting_for_quran_detail)

    current_quran = str(page_data.get("quran_detail") or "ثبت نشده")
    text = (
        f"📖 <b>ثبت جزئیات تلاوت قرآن</b>\n"
        f"📅 تاریخ: <code>{full_jalali}</code>\n\n"
        f"📌 <b>ثبت شده فعلی:</b> <code>{current_quran}</code>\n\n"
        f"✍️ شماره صفحه یا نام سوره‌ای که خواندید را بنویسید:\n"
        f"<i>مثال: صفحه ۴۵ یا سوره واقعه و عادیات</i>"
    )
    kb = get_quran_detail_keyboard(offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_clr_quran:"), HasPermission(PERM_ADMIN))
async def cb_clear_quran_detail(call: CallbackQuery, state: FSMContext) -> None:
    """Clears Quran details."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    offset_days = int(call.data.split(":")[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    update_habit_quran_detail(page_data["id"], "")

    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_detailed_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_detailed_keyboard(
        updated_page.get("habits", {}),
        offset_days=offset_days,
        stealth_mode=stealth,
    )

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("🗑 جزئیات قرآن پاک شد.")


@router.message(HabitState.waiting_for_quran_detail, HasPermission(PERM_ADMIN))
async def msg_receive_quran_detail(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    """Receives Quran detail text and cleanly updates the card."""
    if not message.text:
        return

    data = await state.get_data()
    offset_days = data.get("offset_days", 0)
    page_id = str(data.get("page_id", ""))
    dash_msg_id = data.get("dash_msg_id")
    stealth = data.get("stealth", False)

    try:
        await message.delete()
    except Exception:
        pass

    q_text = message.text.strip()
    if page_id:
        update_habit_quran_detail(page_id, q_text)

    await state.clear()
    await state.update_data(stealth=stealth)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_detailed_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_detailed_keyboard(
        updated_page.get("habits", {}),
        offset_days=offset_days,
        stealth_mode=stealth,
    )

    if dash_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=dash_msg_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# ==========================================
# 🌸 GRATITUDE JOURNAL BUILDER & ITEM MANAGER
# ==========================================


def _compile_gratitude_journal(
    items: List[Dict[str, Any]], full_jalali: str
) -> str:
    """Compiles gratitude entries into the full, soulful template."""
    lines = [
        "🌸 دفتر شکرگزاری روزانه",
        f"📅 {full_jalali}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    has_tags = any(item.get("tag") for item in items)
    if has_tags:
        tagged_groups: Dict[str, List[str]] = {}
        for item in items:
            tag = str(item.get("tag") or "سایر نعمات")
            tagged_groups.setdefault(tag, []).append(str(item["text"]))

        for tag, texts in tagged_groups.items():
            lines.append(f"🏷 [{tag}]:")
            for t in texts:
                lines.append(f"🌿 خدایا شکرت بابت {t}")
            lines.append("")
    else:
        for item in items:
            lines.append(f"🌿 خدایا شکرت بابت {item['text']}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤍 «الحمدلله ربّ العالمین علی کلّ حال»")
    return "\n".join(lines)


def _render_gratitude_screen_text(
    items: List[Dict[str, Any]], full_jalali: str, current_tag: Optional[str] = None, is_saved: bool = False
) -> str:
    """Renders the aesthetic Gratitude card text."""
    header = (
        f"🌸 <b>دفترچه شکرگزاری روزانه</b>\n"
        f"📅 <code>{full_jalali}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
    )

    if not items:
        body = "<i>(هنوز موردی برای امروز ثبت نشده است)</i>\n"
    else:
        lines_buf: List[str] = []
        for i, item in enumerate(items):
            tag_label = f"[{item.get('tag')}] " if item.get("tag") else ""
            lines_buf.append(f"<b>{i + 1}.</b> 🌿 {tag_label}{item['text']}")
        body = "\n".join(lines_buf) + "\n"

    footer = "━━━━━━━━━━━━━━━━━━━━━━\n🤍 <i>«الحمدلله ربّ العالمین علی کلّ حال»</i>\n\n"

    if is_saved:
        instruction = "✅ <b>دفترچه با موفقیت در نوشن ذخیره شد!</b>\nمی‌توانید مورد جدید اضافه کرده یا به هاب بازگردید:"
    elif current_tag:
        instruction = f"🏷 حوزه انتخاب‌شده: <b>{current_tag}</b>\n✍️ حالا متن شکرگزاری بابت این حوزه را بفرستید:"
    else:
        instruction = "✍️ <b>نحوه ثبت:</b> متن شکرگزاری را تایپ کنید یا یکی از حوزه‌های زیر را انتخاب نمایید:"

    return header + body + footer + instruction


@router.callback_query(
    F.data.startswith("hb_grat:") | F.data.startswith("hb_gr_add_more:"),
    HasPermission(PERM_ADMIN),
)
async def cb_open_gratitude_hub(call: CallbackQuery, state: FSMContext) -> None:
    """Opens the Gratitude Journal Builder with existing logs auto-loaded."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, _ = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    data = await state.get_data()
    existing_items = data.get("grat_items")
    if existing_items is None:
        current_log = str(page_data.get("gratitude_log", "")).strip()
        existing_items = parse_existing_gratitude_log(current_log)

    await state.update_data(
        offset_days=offset_days,
        page_id=page_data["id"],
        grat_items=existing_items,
        active_tag=None,
        dash_msg_id=call.message.message_id,
    )
    await state.set_state(HabitState.waiting_for_gratitude_item)

    text = _render_gratitude_screen_text(existing_items, full_jalali)
    kb = get_gratitude_accumulator_keyboard(
        offset_days, has_items=bool(existing_items), is_saved_preview=False
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(
    F.data.startswith("hb_gr_tag:"), HasPermission(PERM_ADMIN)
)
async def cb_pick_gratitude_tag(call: CallbackQuery, state: FSMContext) -> None:
    """Sets active tag for the next gratitude sentence."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    _, tag_name, offset_str = call.data.split(":")
    offset_days = int(offset_str)
    await state.update_data(active_tag=tag_name)

    data = await state.get_data()
    items: List[Dict[str, Any]] = data.get("grat_items", [])
    _, full_jalali, _ = _calculate_date_from_offset(offset_days)

    text = _render_gratitude_screen_text(items, full_jalali, current_tag=tag_name)
    kb = get_gratitude_accumulator_keyboard(offset_days, has_items=bool(items))
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer(f"حوزه {tag_name} انتخاب شد.")


@router.message(HabitState.waiting_for_gratitude_item, HasPermission(PERM_ADMIN))
async def msg_receive_gratitude_item(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    """Receives gratitude text line and appends to journal list."""
    if not message.text:
        return

    data = await state.get_data()
    items: List[Dict[str, Any]] = data.get("grat_items", [])
    active_tag = data.get("active_tag")
    offset_days = data.get("offset_days", 0)
    dash_msg_id = data.get("dash_msg_id")

    try:
        await message.delete()
    except Exception:
        pass

    raw_text = message.text.strip()
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    for line in lines:
        cleaned = (
            line.replace("خدایا شکرت بابت", "")
            .replace("خدایا شکرت", "")
            .replace("خدایا ممنونم بابت", "")
            .replace("خدایا ممنونم", "")
            .strip()
        )
        items.append({"tag": active_tag, "text": cleaned or line})

    await state.update_data(grat_items=items, active_tag=None)

    _, full_jalali, _ = _calculate_date_from_offset(offset_days)
    text = _render_gratitude_screen_text(items, full_jalali)
    kb = get_gratitude_accumulator_keyboard(offset_days, has_items=True)

    if dash_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=dash_msg_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(
    F.data.startswith("hb_gr_save:"), HasPermission(PERM_ADMIN)
)
async def cb_save_gratitude_journal(
    call: CallbackQuery, state: FSMContext
) -> None:
    """Compiles and saves gratitude journal to Notion, showing clean confirmation preview."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    items: List[Dict[str, Any]] = data.get("grat_items", [])
    offset_days = int(call.data.split(":")[1])
    page_id = str(data.get("page_id", ""))

    _, full_jalali, _ = _calculate_date_from_offset(offset_days)

    if items and page_id:
        compiled_text = _compile_gratitude_journal(items, full_jalali)
        update_habit_gratitude(page_id, compiled_text)

    text = _render_gratitude_screen_text(items, full_jalali, is_saved=True)
    kb = get_gratitude_accumulator_keyboard(
        offset_days, has_items=bool(items), is_saved_preview=True
    )

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer(f"🌸 دفترچه با {len(items)} مورد ذخیره شد! ✨")


# --- Gratitude Itemized Edit & Delete ---


@router.callback_query(
    F.data.startswith("hb_gr_ask_del:"), HasPermission(PERM_ADMIN)
)
async def cb_ask_delete_gratitude_item(
    call: CallbackQuery, state: FSMContext
) -> None:
    """Shows picker to choose which item to delete."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    items: List[Dict[str, Any]] = data.get("grat_items", [])
    offset_days = int(call.data.split(":")[1])

    if not items:
        await call.answer("هیچ موردی برای حذف وجود ندارد.")
        return

    text = "🗑 <b>کدام مورد را می‌خواهید حذف کنید؟</b>\nروی مورد مربوطه بزنید:"
    kb = get_gratitude_item_picker_keyboard(items, action="del", offset_days=offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(
    F.data.startswith("hb_gr_do_del:"), HasPermission(PERM_ADMIN)
)
async def cb_do_delete_gratitude_item(
    call: CallbackQuery, state: FSMContext
) -> None:
    """Deletes the specific gratitude item and auto-saves."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    _, idx_str, offset_str = call.data.split(":")
    del_idx = int(idx_str)
    offset_days = int(offset_str)

    data = await state.get_data()
    items: List[Dict[str, Any]] = data.get("grat_items", [])
    page_id = str(data.get("page_id", ""))

    if 0 <= del_idx < len(items):
        removed = items.pop(del_idx)
        await state.update_data(grat_items=items)

        # Auto-update Notion
        _, full_jalali, _ = _calculate_date_from_offset(offset_days)
        compiled_text = _compile_gratitude_journal(items, full_jalali) if items else ""
        if page_id:
            update_habit_gratitude(page_id, compiled_text)

        await call.answer(f"مورد {del_idx + 1} حذف شد.")

    _, full_jalali, _ = _calculate_date_from_offset(offset_days)
    text = _render_gratitude_screen_text(items, full_jalali, is_saved=True)
    kb = get_gratitude_accumulator_keyboard(
        offset_days, has_items=bool(items), is_saved_preview=True
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(
    F.data.startswith("hb_gr_ask_edit:"), HasPermission(PERM_ADMIN)
)
async def cb_ask_edit_gratitude_item(
    call: CallbackQuery, state: FSMContext
) -> None:
    """Shows picker to choose which item to edit."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    items: List[Dict[str, Any]] = data.get("grat_items", [])
    offset_days = int(call.data.split(":")[1])

    if not items:
        await call.answer("هیچ موردی برای ویرایش وجود ندارد.")
        return

    text = "✏️ <b>کدام مورد را می‌خواهید ویرایش کنید؟</b>\nروی مورد مربوطه بزنید:"
    kb = get_gratitude_item_picker_keyboard(items, action="ed", offset_days=offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(
    F.data.startswith("hb_gr_do_ed:"), HasPermission(PERM_ADMIN)
)
async def cb_prompt_edit_gratitude_item(
    call: CallbackQuery, state: FSMContext
) -> None:
    """Prompts the user to type new text for the selected item."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    _, idx_str, offset_str = call.data.split(":")
    ed_idx = int(idx_str)
    offset_days = int(offset_str)

    data = await state.get_data()
    items: List[Dict[str, Any]] = data.get("grat_items", [])

    if not (0 <= ed_idx < len(items)):
        await call.answer("مورد یافت نشد.")
        return

    await state.update_data(
        edit_idx=ed_idx,
        dash_msg_id=call.message.message_id,
        offset_days=offset_days,
    )
    await state.set_state(HabitState.waiting_for_gratitude_edit)

    target_item = items[ed_idx]
    tag_info = f"[{target_item.get('tag')}] " if target_item.get("tag") else ""

    text = (
        f"✏️ <b>ویرایش مورد شماره {ed_idx + 1}</b>\n\n"
        f"📌 <b>متن فعلی:</b>\n<i>«{tag_info}{target_item['text']}»</i>\n\n"
        f"✍️ متن جدید و اصلاح‌شده را بفرستید:"
    )
    kb = get_habit_custom_date_cancel_keyboard(offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.message(HabitState.waiting_for_gratitude_edit, HasPermission(PERM_ADMIN))
async def msg_receive_gratitude_edit(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    """Applies the edited text to the specific gratitude item and updates Notion."""
    if not message.text:
        return

    data = await state.get_data()
    items: List[Dict[str, Any]] = data.get("grat_items", [])
    ed_idx = data.get("edit_idx", -1)
    offset_days = data.get("offset_days", 0)
    page_id = str(data.get("page_id", ""))
    dash_msg_id = data.get("dash_msg_id")

    try:
        await message.delete()
    except Exception:
        pass

    if 0 <= ed_idx < len(items):
        new_text = (
            message.text.replace("خدایا شکرت بابت", "")
            .replace("خدایا شکرت", "")
            .replace("خدایا ممنونم بابت", "")
            .replace("خدایا ممنونم", "")
            .strip()
        )
        items[ed_idx]["text"] = new_text
        await state.update_data(grat_items=items)

        # Auto-update Notion
        _, full_jalali, _ = _calculate_date_from_offset(offset_days)
        compiled_text = _compile_gratitude_journal(items, full_jalali)
        if page_id:
            update_habit_gratitude(page_id, compiled_text)

    await state.set_state(HabitState.waiting_for_gratitude_item)

    _, full_jalali, _ = _calculate_date_from_offset(offset_days)
    text = _render_gratitude_screen_text(items, full_jalali, is_saved=True)
    kb = get_gratitude_accumulator_keyboard(
        offset_days, has_items=bool(items), is_saved_preview=True
    )

    if dash_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=dash_msg_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(
    F.data.startswith("hb_gr_clr_all:"), HasPermission(PERM_ADMIN)
)
async def cb_clear_all_gratitude(
    call: CallbackQuery, state: FSMContext
) -> None:
    """Clears the gratitude log from Notion."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    offset_days = int(call.data.split(":")[1])
    page_id = str(data.get("page_id", ""))
    stealth = data.get("stealth", False)

    if page_id:
        update_habit_gratitude(page_id, "")

    await state.clear()
    await state.update_data(stealth=stealth)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("🗑 شکرگزاری روز پاک شد.")


# ==========================================
# 🗑️ RESET & BULK FILL (Standard Version 2)
# ==========================================


@router.callback_query(
    F.data.startswith("hb_ask_fill:"), HasPermission(PERM_ADMIN)
)
async def cb_ask_bulk_fill(call: CallbackQuery) -> None:
    """Asks confirmation before bulk complete as Version 2 (Standard)."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    offset_days = int(call.data.split(":")[1])
    _, full_jalali, _ = _calculate_date_from_offset(offset_days)

    text = (
        f"⚡ <b>ثبت سریع همه عادات به عنوان معمول</b>\n\n"
        f"آیا مطمئنید تمام ۱۲ عادت برای <code>{full_jalali}</code> روی <b>۲. معمول (استاندارد روزمره)</b> تنظیم شوند؟"
    )
    kb = get_habit_bulk_fill_confirm_keyboard(offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(
    F.data.startswith("hb_do_fill:"), HasPermission(PERM_ADMIN)
)
async def cb_do_bulk_fill(call: CallbackQuery, state: FSMContext) -> None:
    """Executes bulk fill to Version 2 ('2-🏃‍♂️ نیمه‌کامل') in Notion."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    offset_days = int(call.data.split(":")[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    bulk_update_all_habits(page_data["id"], "2-🏃‍♂️ نیمه‌کامل")

    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("⚡ تمام ۱۲ عادت روی سطح معمول (استاندارد) ثبت شدند! 🏃")


@router.callback_query(
    F.data.startswith("hb_ask_reset:"), HasPermission(PERM_ADMIN)
)
async def cb_ask_reset(call: CallbackQuery) -> None:
    """Asks confirmation before resetting all day entries."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    offset_days = int(call.data.split(":")[1])
    _, full_jalali, _ = _calculate_date_from_offset(offset_days)

    text = (
        f"⚠️ <b>ریست کردن کامل عادات روز</b>\n\n"
        f"آیا مطمئنید که می‌خواهید تمام ۱۲ عادت، یادداشت، شکرگزاری و جزئیات قرآن تاریخ <code>{full_jalali}</code> پاک و ریست شوند؟"
    )
    kb = get_habit_reset_confirm_keyboard(offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(
    F.data.startswith("hb_do_reset:"), HasPermission(PERM_ADMIN)
)
async def cb_do_reset(call: CallbackQuery, state: FSMContext) -> None:
    """Executes full day reset in Notion."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    offset_days = int(call.data.split(":")[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    reset_habit_day(page_data["id"])

    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("🗑 کارنامه روز کاملاً پاک و بازنشانی شد.")


# ==========================================
# 📝 NOTES & CUSTOM DATE
# ==========================================


@router.callback_query(
    F.data.startswith("hb_notes:"), HasPermission(PERM_ADMIN)
)
async def cb_prompt_notes(call: CallbackQuery, state: FSMContext) -> None:
    """Prompts for daily notes."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    offset_days = int(call.data.split(":")[1])
    g_iso, full_jalali, _ = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    await state.update_data(
        offset_days=offset_days,
        page_id=page_data["id"],
        dash_msg_id=call.message.message_id,
    )
    await state.set_state(HabitState.waiting_for_notes)

    current_note = str(page_data.get("notes") or "ثبت نشده")
    text = (
        f"📝 <b>یادداشت روزانه</b>\n"
        f"📅 تاریخ: <code>{full_jalali}</code>\n\n"
        f"📌 <b>یادداشت فعلی:</b>\n<i>«{current_note}»</i>\n\n"
        f"✍️ متن یادداشت جدید خود را تایپ و ارسال کنید:"
    )
    kb = get_habit_notes_keyboard(offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(
    F.data.startswith("hb_clr_notes:"), HasPermission(PERM_ADMIN)
)
async def cb_clear_notes(call: CallbackQuery, state: FSMContext) -> None:
    """Clears daily notes."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    data = await state.get_data()
    stealth = data.get("stealth", False)
    offset_days = int(call.data.split(":")[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    update_habit_notes(page_data["id"], "")

    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("🗑 یادداشت روز پاک شد.")


@router.message(HabitState.waiting_for_notes, HasPermission(PERM_ADMIN))
async def msg_receive_notes(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    """Receives notes text with zero clutter chat hygiene."""
    if not message.text:
        return

    data = await state.get_data()
    offset_days = data.get("offset_days", 0)
    page_id = str(data.get("page_id", ""))
    dash_msg_id = data.get("dash_msg_id")
    stealth = data.get("stealth", False)

    try:
        await message.delete()
    except Exception:
        pass

    note_text = message.text.strip()
    if page_id:
        update_habit_notes(page_id, note_text)

    await state.clear()
    await state.update_data(stealth=stealth)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(updated_page, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    if dash_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=dash_msg_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(
    F.data.startswith("hb_cdate:"), HasPermission(PERM_ADMIN)
)
async def cb_prompt_custom_date(call: CallbackQuery, state: FSMContext) -> None:
    """Prompts for custom Jalali date."""
    if not call.data or not isinstance(call.message, Message):
        await call.answer()
        return

    offset_days = int(call.data.split(":")[1])
    await state.update_data(
        offset_days=offset_days, dash_msg_id=call.message.message_id
    )
    await state.set_state(HabitState.waiting_for_custom_date)

    text = (
        "📅 <b>انتخاب تاریخ دلخواه</b>\n\n"
        "لطفاً تاریخ مورد نظر را با فرمت شمسی تایپ و ارسال کنید:\n"
        "مثال: <code>1405/06/15</code> یا <code>1404/12/01</code>"
    )
    kb = get_habit_custom_date_cancel_keyboard(offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.message(HabitState.waiting_for_custom_date, HasPermission(PERM_ADMIN))
async def msg_receive_custom_date(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    """Processes user entered custom Jalali date."""
    if not message.text:
        return

    data = await state.get_data()
    dash_msg_id = data.get("dash_msg_id")
    stealth = data.get("stealth", False)

    try:
        await message.delete()
    except Exception:
        pass

    parsed = parse_user_date_input(message.text)
    if not parsed:
        err_msg = await message.answer(
            "❌ فرمت تاریخ نامعتبر است! لطفاً به صورت <code>1405/06/15</code> وارد کنید."
        )
        await asyncio.sleep(3)
        try:
            await err_msg.delete()
        except Exception:
            pass
        return

    g_target_iso, _ = parsed
    tz = timezone(timedelta(hours=3, minutes=30))
    g_today = datetime.now(tz).date()
    g_target_date = date.fromisoformat(g_target_iso)
    offset_days = (g_today - g_target_date).days

    await state.clear()
    await state.update_data(stealth=stealth)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    streaks_data = calculate_habit_streaks()

    text = _format_hub_text(page_data, full_jalali, rel_label, stealth=stealth, streaks_data=streaks_data)
    kb = build_habit_hub_keyboard(offset_days=offset_days, stealth_mode=stealth)

    if dash_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=dash_msg_id,
                text=text,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "hb_close", HasPermission(PERM_ADMIN))
async def cb_close_habits(call: CallbackQuery, state: FSMContext) -> None:
    """Closes the habit tracker dashboard."""
    if not isinstance(call.message, Message):
        await call.answer()
        return

    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass
    
def _format_matrix_dashboard_text(
    matrix_data: Dict[str, Any], full_jalali: str
) -> str:
    """Formats the comprehensive Consistency Matrix & Analytics text."""
    p_label = matrix_data["period_label"]
    overall_pct = matrix_data["overall_consistency_pct"]
    prog_bar = _build_progress_bar(overall_pct / 100.0)
    q = matrix_data["quality_counts"]
    total_checks = matrix_data["total_possible"] or 1

    lines = [
        "📊 <b>ماتریس و داشبورد تحلیل پایبندی</b>",
        f"📅 <code>{full_jalali}</code>",
        f"⏱ <b>بازه تحلیلی:</b> <code>{p_label}</code> ({matrix_data['days_in_period']} روز)",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 <b>پایبندی کلی دوره:</b> {prog_bar}",
        f"📝 روزهای ثبت‌شده: <b>{matrix_data['logged_days_count']} از {matrix_data['days_in_period']} روز</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🎨 <b>تفکیک کیفیت اجرای عادات:</b>",
        f"  💪 کامل (بونوس): <b>{q['v1']} بار</b> ({int(q['v1']/total_checks*100)}%)",
        f"  🏃 معمول (استاندارد): <b>{q['v2']} بار</b> ({int(q['v2']/total_checks*100)}%)",
        f"  🐢 سبک (حداقلی): <b>{q['v3']} بار</b> ({int(q['v3']/total_checks*100)}%)",
        f"  ❌ با دلیل: <b>{q['v4']} بار</b> | ⛔ بدون دلیل: <b>{q['v5']} بار</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Anchor & Growth Habits
    top_h = matrix_data.get("top_habit")
    bot_h = matrix_data.get("bottom_habit")
    if top_h and bot_h:
        lines.append(
            f"🏆 <b>قوی‌ترین عادت:</b> {top_h['info']['emoji']} {top_h['info']['fa']} (<b>{int(top_h['pct'])}%</b>)"
        )
        lines.append(
            f"🌱 <b>نیازمند توجه:</b> {bot_h['info']['emoji']} {bot_h['info']['fa']} (<b>{int(bot_h['pct'])}%</b>)"
        )
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    # Habit-by-Habit Ranking with mini bars
    lines.append("📋 <b>رتبه‌بندی پایبندی ۱۲ عادت:</b>")
    for r in matrix_data["habit_rankings"]:
        h_info = r["info"]
        pct_int = int(round(r["pct"]))
        mini_filled = int(round(pct_int / 10))
        mini_bar = ("🟩" * mini_filled) + ("⬜" * (10 - mini_filled))
        lines.append(
            f"{h_info['emoji']} {h_info['fa']}:\n"
            f"   └ [{mini_bar}] <b>{pct_int}%</b> ({r['completed_days']}/{matrix_data['days_in_period']} روز)"
        )

    # Daily Sparkline
    lines.append("\n🗓 <b>توالی روزهای بازه:</b>")
    timeline_emojis = []
    for d in matrix_data["daily_timeline"]:
        p = d["progress"]
        if not d["has_data"] or p == 0.0:
            timeline_emojis.append("⬜")
        elif p >= 0.80:
            timeline_emojis.append("🟩")
        elif p >= 0.50:
            timeline_emojis.append("🟨")
        else:
            timeline_emojis.append("🟧")

    lines.append(" ".join(timeline_emojis))
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("👆 بازه زمانی مورد نظر خود را از دکمه‌های زیر انتخاب کنید:")

    return "\n".join(lines)

