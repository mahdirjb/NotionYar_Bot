# app/handlers/habits.py

from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.keyboards.reply import BTN_HABITS
from app.keyboards.inline import (
    build_habit_day_keyboard,
    get_habit_level_picker_keyboard,
    get_habit_bulk_fill_confirm_keyboard,
    get_habit_notes_keyboard,
    get_habit_custom_date_cancel_keyboard,
)
from app.states.habit_state import HabitState
from app.filters.permissions import HasPermission, PERM_ADMIN
from app.services.date_helper import (
    get_jalali_date_info,
    format_jalali_full_display,
    parse_user_date_input,
)
from app.services.notion_service import (
    HABIT_ITEMS,
    HABIT_LEVELS,
    LEVEL_BADGES,
    get_or_create_habit_day,
    update_habit_entry,
    bulk_update_all_habits,
    update_habit_notes,
)

router = Router()


def _calculate_date_from_offset(offset_days: int) -> tuple[str, str, str]:
    """
    Returns (gregorian_iso, full_jalali_title, relative_label).
    offset_days: 0 = Today, 1 = Yesterday, 2 = 2 days ago, -1 = Tomorrow, etc.
    """
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
    """Generates a visual 10-block progress bar (e.g. [🟩🟩🟩🟩🟨⬜⬜⬜⬜⬜] 45%)."""
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


def _format_habit_dashboard_text(
    page_data: Dict[str, Any], full_jalali: str, rel_label: str
) -> str:
    """Formats the comprehensive Habit Dashboard message in clean Persian HTML."""
    prog_bar = _build_progress_bar(page_data.get("progress", 0.0))
    cheerleader = page_data.get("cheerleader", "").strip()
    notes = page_data.get("notes", "").strip()

    lines = [
        "🎯 <b>کارنامه عادات روزانه</b>",
        f"📅 <b>تاریخ:</b> <code>{full_jalali}</code> ({rel_label})",
        "",
        f"📊 <b>پیشرفت:</b> {prog_bar}",
    ]

    if cheerleader:
        lines.append(f"📣 <b>وضعیت:</b> <i>{cheerleader}</i>")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")

    habits = page_data.get("habits", {})
    for h_key, h_info in HABIT_ITEMS.items():
        val = habits.get(h_key)
        badge = LEVEL_BADGES.get(val, "▫️ ثبت‌نشده") if val else "▫️ ثبت‌نشده"
        lines.append(f"{h_info['emoji']} {h_info['fa']}: <b>{badge}</b>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    if notes:
        lines.append(f"\n📝 <b>یادداشت روز:</b>\n<i>«{notes}»</i>")
    else:
        lines.append("\n📝 <b>یادداشت روز:</b> <i>(ثبت نشده)</i>")

    return "\n".join(lines)


# ==========================================
# 🚀 MAIN ENTRY & REFRESH HANDLERS
# ==========================================


@router.message(F.text == BTN_HABITS, HasPermission(PERM_ADMIN))
@router.message(F.text == "/habits", HasPermission(PERM_ADMIN))
async def cmd_habits_dashboard(
    message: Message, state: FSMContext, bot: Bot
) -> None:
    """Main landing handler for Habit Tracker."""
    await state.clear()
    wait_msg = await message.answer("🔄 در حال بارگذاری کارنامه عادات...")

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(0)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    text = _format_habit_dashboard_text(page_data, full_jalali, rel_label)
    kb = build_habit_day_keyboard(page_data.get("habits", {}), offset_days=0)

    await wait_msg.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("hb_ref:"), HasPermission(PERM_ADMIN))
async def cb_refresh_habits(call: CallbackQuery) -> None:
    """Refreshes the current habit day card directly from Notion."""
    parts = call.data.split(":")
    offset_days = int(parts[1]) if len(parts) > 1 else 0

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    text = _format_habit_dashboard_text(page_data, full_jalali, rel_label)
    kb = build_habit_day_keyboard(page_data.get("habits", {}), offset_days=offset_days)

    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await call.answer("🔄 کارنامه به‌روزرسانی شد.")
    except Exception:
        await call.answer("اطلاعات از قبل به‌روز است.")


# ==========================================
# 🗓 NAVIGATION & PICKERS
# ==========================================


@router.callback_query(F.data.startswith("hb_nav:"), HasPermission(PERM_ADMIN))
async def cb_navigate_days(call: CallbackQuery, state: FSMContext) -> None:
    """Navigates to another day (Yesterday, Today, Tomorrow, etc.)."""
    await state.clear()
    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    text = _format_habit_dashboard_text(page_data, full_jalali, rel_label)
    kb = build_habit_day_keyboard(page_data.get("habits", {}), offset_days=offset_days)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_back:"), HasPermission(PERM_ADMIN))
async def cb_back_to_dashboard(call: CallbackQuery, state: FSMContext) -> None:
    """Returns back to the main habit dashboard for the given offset."""
    await state.clear()
    parts = call.data.split(":")
    offset_days = int(parts[1]) if len(parts) > 1 else 0

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    text = _format_habit_dashboard_text(page_data, full_jalali, rel_label)
    kb = build_habit_day_keyboard(page_data.get("habits", {}), offset_days=offset_days)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_pk:"), HasPermission(PERM_ADMIN))
async def cb_pick_habit_level(call: CallbackQuery) -> None:
    """Opens the 5-level selector sub-menu for a specific habit."""
    _, h_key, offset_str = call.data.split(":")
    offset_days = int(offset_str)

    h_info = HABIT_ITEMS.get(h_key, {"fa": "عادت", "emoji": "🎯"})
    _, full_jalali, _ = _calculate_date_from_offset(offset_days)

    text = (
        f"🎯 <b>تنظیم وضعیت: {h_info['emoji']} {h_info['fa']}</b>\n"
        f"📅 <code>{full_jalali}</code>\n\n"
        f"یکی از سطوح کیفیت زیر را انتخاب کنید:"
    )
    kb = get_habit_level_picker_keyboard(h_key, offset_days)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_set:"), HasPermission(PERM_ADMIN))
async def cb_set_habit_level(call: CallbackQuery) -> None:
    """Sets the chosen level for a habit in Notion and returns to the dashboard."""
    _, h_key, lvl_str, offset_str = call.data.split(":")
    offset_days = int(offset_str)

    h_info = HABIT_ITEMS.get(h_key)
    if not h_info:
        await call.answer("❌ عادت نامعتبر است.", show_alert=True)
        return

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)
    page_id = page_data["id"]

    # lvl_str: '0' means clear, '1'..'5' maps to HABIT_LEVELS
    select_val = HABIT_LEVELS.get(lvl_str) if lvl_str != "0" else None
    update_habit_entry(page_id, h_info["prop"], select_val)

    # Fetch updated state with formulas
    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)

    text = _format_habit_dashboard_text(updated_page, full_jalali, rel_label)
    kb = build_habit_day_keyboard(updated_page.get("habits", {}), offset_days=offset_days)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

    status_name = select_val or "پاک شد 🗑"
    await call.answer(f"✅ {h_info['fa']}: {status_name}")


# ==========================================
# ⚡ BULK ACTIONS & NOTES
# ==========================================


@router.callback_query(F.data.startswith("hb_ask_fill:"), HasPermission(PERM_ADMIN))
async def cb_ask_bulk_fill(call: CallbackQuery) -> None:
    """Asks confirmation before marking all 12 habits as Complete."""
    parts = call.data.split(":")
    offset_days = int(parts[1])
    _, full_jalali, _ = _calculate_date_from_offset(offset_days)

    text = (
        f"⚡ <b>تکمیل سریع همه عادات</b>\n\n"
        f"آیا مطمئنید که می‌خواهید تمام ۱۲ عادت برای تاریخ <code>{full_jalali}</code> روی <b>💪 کامل (۱۰۰٪)</b> تنظیم شوند؟"
    )
    kb = get_habit_bulk_fill_confirm_keyboard(offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_do_fill:"), HasPermission(PERM_ADMIN))
async def cb_do_bulk_fill(call: CallbackQuery) -> None:
    """Executes bulk update for all habits to '1-💪 کامل'."""
    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    bulk_update_all_habits(page_data["id"], "1-💪 کامل")

    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    text = _format_habit_dashboard_text(updated_page, full_jalali, rel_label)
    kb = build_habit_day_keyboard(updated_page.get("habits", {}), offset_days=offset_days)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("⚡ تمام ۱۲ عادت با موفقیت کامل شدند! 🎉")


@router.callback_query(F.data.startswith("hb_notes:"), HasPermission(PERM_ADMIN))
async def cb_prompt_notes(call: CallbackQuery, state: FSMContext) -> None:
    """Prompts the user to enter notes for the current day."""
    parts = call.data.split(":")
    offset_days = int(parts[1])
    g_iso, full_jalali, _ = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    await state.update_data(
        offset_days=offset_days,
        page_id=page_data["id"],
        dash_msg_id=call.message.message_id,
    )
    await state.set_state(HabitState.waiting_for_notes)

    current_note = page_data.get("notes") or "ثبت نشده"
    text = (
        f"📝 <b>یادداشت روزانه</b>\n"
        f"📅 تاریخ: <code>{full_jalali}</code>\n\n"
        f"📌 <b>یادداشت فعلی:</b>\n<i>«{current_note}»</i>\n\n"
        f"✍️ متن یادداشت جدید خود را تایپ و ارسال کنید:"
    )
    kb = get_habit_notes_keyboard(offset_days)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("hb_clr_notes:"), HasPermission(PERM_ADMIN))
async def cb_clear_notes(call: CallbackQuery, state: FSMContext) -> None:
    """Clears the notes for the given habit day."""
    await state.clear()
    parts = call.data.split(":")
    offset_days = int(parts[1])

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    update_habit_notes(page_data["id"], "")

    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)
    text = _format_habit_dashboard_text(updated_page, full_jalali, rel_label)
    kb = build_habit_day_keyboard(updated_page.get("habits", {}), offset_days=offset_days)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer("🗑 یادداشت روز پاک شد.")


@router.message(HabitState.waiting_for_notes, HasPermission(PERM_ADMIN))
async def msg_receive_notes(message: Message, state: FSMContext, bot: Bot) -> None:
    """Receives new notes text and cleanly updates the habit card."""
    data = await state.get_data()
    offset_days = data.get("offset_days", 0)
    page_id = data.get("page_id")
    dash_msg_id = data.get("dash_msg_id")

    # Clean up user message immediately (Zero-Clutter Chat Hygiene)
    try:
        await message.delete()
    except Exception:
        pass

    note_text = message.text.strip()
    if page_id:
        update_habit_notes(page_id, note_text)

    await state.clear()

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    updated_page = get_or_create_habit_day(g_iso, day_title=full_jalali)

    text = _format_habit_dashboard_text(updated_page, full_jalali, rel_label)
    kb = build_habit_day_keyboard(updated_page.get("habits", {}), offset_days=offset_days)

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
# 📅 CUSTOM DATE NAVIGATOR
# ==========================================


@router.callback_query(F.data.startswith("hb_cdate:"), HasPermission(PERM_ADMIN))
async def cb_prompt_custom_date(call: CallbackQuery, state: FSMContext) -> None:
    """Prompts the user to enter a custom Jalali date."""
    parts = call.data.split(":")
    offset_days = int(parts[1])

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
    data = await state.get_data()
    dash_msg_id = data.get("dash_msg_id")
    old_offset = data.get("offset_days", 0)

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

    g_target_iso, j_str = parsed

    # Calculate offset relative to today
    tz = timezone(timedelta(hours=3, minutes=30))
    g_today = datetime.now(tz).date()
    g_target_date = date.fromisoformat(g_target_iso)
    offset_days = (g_today - g_target_date).days

    await state.clear()

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

    text = _format_habit_dashboard_text(page_data, full_jalali, rel_label)
    kb = build_habit_day_keyboard(page_data.get("habits", {}), offset_days=offset_days)

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
    await state.clear()
    try:
        await call.message.delete()
    except Exception:
        pass