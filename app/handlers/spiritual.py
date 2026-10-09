# app/handlers/spiritual.py

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.keyboards.reply import BTN_SPIRITUAL
from app.keyboards.inline import (
    build_spiritual_hub_keyboard,
    get_spiritual_prayer_picker_keyboard,
    get_spiritual_date_picker_keyboard,
    get_spiritual_notes_keyboard,
    get_spiritual_cancel_keyboard,
    get_spiritual_report_keyboard,
    get_spiritual_report_result_keyboard,
    PRAYER_STATUS_BADGES,
)
from app.states.spiritual_state import SpiritualState
from app.services.auth_service import has_permission, PERM_ADMIN
from app.services.date_helper import (
    format_jalali_full_display,
    parse_user_date_input,
    get_preset_date_range,
    parse_custom_date_range,
)
from app.services.notion_service import (
    PRAYER_KEYS,
    PRAYER_META,
    get_or_create_salah_day,
    update_salah_prayer_status,
    bulk_mark_salah_ada,
    bulk_mark_salah_reset,
    update_salah_notes,
    add_quran_reading_entry,
    get_spiritual_report,
)

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


def render_spiritual_hub_text(
    page_data: Dict[str, Any],
    full_jalali: str,
    rel_label: str,
    stealth: bool = False
) -> str:
    """Formats the main landing text for daily prayers and spiritual tracker."""
    prayers = page_data.get("prayers", {})
    completed_count = page_data.get("completed_count", 0)
    ada_count = page_data.get("ada_count", 0)
    qaza_count = page_data.get("qaza_count", 0)
    prog_bar = _build_progress_bar(float(page_data.get("progress", 0.0)))
    notes = str(page_data.get("notes", "")).strip()

    if stealth:
        return (
            "🕶️ <b>[حالت مخفی - ردیاب معنوی]</b>\n"
            f"📅 <code>{full_jalali}</code> | 📊 <b>{int(round(page_data.get('progress', 0.0) * 100))}%</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 <i>جزئیات برای حفظ حریم خصوصی پنهان شده‌اند.</i>\n"
            f"• وضعیت نمازها: {completed_count} از ۵ مورد انجام شده\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👇 برای تغییر وضعیت از دکمه‌های زیر استفاده کنید:"
        )

    lines = [
        "📿 <b>هاب ردیاب معنوی و نمازها</b>",
        f"📅 <b>تاریخ:</b> <code>{full_jalali}</code> ({rel_label})",
        "",
        f"📊 <b>پیشرفت نمازها:</b> {prog_bar}",
        f"🟢 اداء: <b>{ada_count}</b> | 🟡 قضاء: <b>{qaza_count}</b> | ⚪ نخوانده: <b>{5 - completed_count}</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "<b>وضعیت نمازهای یومیه:</b>",
    ]

    for k in PRAYER_KEYS:
        p = prayers.get(k, {})
        emoji = p.get("emoji", "")
        name = p.get("name", "")
        status = p.get("status", "none")
        badge = PRAYER_STATUS_BADGES.get(status, "⚪ نخوانده")
        lines.append(f"{emoji} <b>نماز {name}:</b> {badge}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    if notes:
        lines.append(f"📝 <b>یادداشت معنوی:</b> <i>«{notes}»</i>")
    else:
        lines.append("📝 <b>یادداشت معنوی:</b> <i>(ثبت نشده ▫️)</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 <i>نکته: نمازها هر روز به‌صورت خودکار «اداء» علامت می‌خورند. برای تغییر به قضاء یا نخوانده، روی دکمه مربوطه لمس کنید.</i>")

    return "\n".join(lines)


# ==========================================
# 🌿 OPEN HUB COMMAND & REPLY BUTTON
# ==========================================

@router.message(F.text == BTN_SPIRITUAL)
@router.message(F.text.contains("معنوی"))
@router.message(Command("salah"))
@router.message(Command("spiritual"))
async def open_spiritual_hub(message: Message, state: FSMContext):
    user_id = message.from_user.id if message.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await message.answer("⛔ شما به بخش ردیاب معنوی دسترسی ندارید.")
        return

    await state.clear()
    await state.update_data(offset_days=0, stealth=False)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(0)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=False)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=0, stealth=False)

    await message.answer(hub_text, reply_markup=kb, parse_mode="HTML")


# ==========================================
# ⚡ PRAYER TOGGLES & BULK ACTIONS
# ==========================================

@router.callback_query(F.data.startswith("sp_tog:"))
async def handle_toggle_prayer(callback: CallbackQuery, state: FSMContext):
    """Cycles prayer status: ada -> qaza -> none -> ada."""
    parts = callback.data.split(":")
    prayer_key = parts[1]
    offset_days = int(parts[2])

    data = await state.get_data()
    stealth = data.get("stealth", False)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")
    page_id = page_data.get("id")

    if page_id:
        await asyncio.to_thread(update_salah_prayer_status, page_id, prayer_key, None)
        # Re-fetch
        page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=stealth)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=offset_days, stealth=stealth)

    await callback.message.edit_text(hub_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer(f"وضعیت {PRAYER_META.get(prayer_key, {}).get('name', '')} تغییر کرد.")


@router.callback_query(F.data.startswith("sp_set:"))
async def handle_set_prayer_direct(callback: CallbackQuery, state: FSMContext):
    """Sets explicit prayer status (ada, qaza, or none)."""
    parts = callback.data.split(":")
    prayer_key = parts[1]
    target_status = parts[2]
    offset_days = int(parts[3])

    data = await state.get_data()
    stealth = data.get("stealth", False)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")
    page_id = page_data.get("id")

    if page_id:
        await asyncio.to_thread(update_salah_prayer_status, page_id, prayer_key, target_status)
        page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=stealth)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=offset_days, stealth=stealth)

    await callback.message.edit_text(hub_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("به‌روزرسانی انجام شد ✅")


@router.callback_query(F.data.startswith("sp_bulk_ada:"))
async def handle_bulk_ada(callback: CallbackQuery, state: FSMContext):
    """Marks all 5 prayers as completed on-time (Ada)."""
    offset_days = int(callback.data.split(":")[1])
    data = await state.get_data()
    stealth = data.get("stealth", False)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")
    page_id = page_data.get("id")

    if page_id:
        await asyncio.to_thread(bulk_mark_salah_ada, page_id)
        page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=stealth)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=offset_days, stealth=stealth)

    await callback.message.edit_text(hub_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("همه نمازها با موفقیت «اداء» علامت خوردند! 🟢", show_alert=True)


# ==========================================
# 📅 DATE NAVIGATION & SELECTION
# ==========================================

@router.callback_query(F.data.startswith("sp_nav:"))
async def handle_spiritual_nav(callback: CallbackQuery, state: FSMContext):
    offset_days = int(callback.data.split(":")[1])
    await state.clear()
    await state.update_data(offset_days=offset_days)

    data = await state.get_data()
    stealth = data.get("stealth", False)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=stealth)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=offset_days, stealth=stealth)

    await callback.message.edit_text(hub_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sp_stealth:"))
async def handle_toggle_stealth(callback: CallbackQuery, state: FSMContext):
    offset_days = int(callback.data.split(":")[1])
    data = await state.get_data()
    new_stealth = not data.get("stealth", False)
    await state.update_data(stealth=new_stealth, offset_days=offset_days)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=new_stealth)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=offset_days, stealth=new_stealth)

    await callback.message.edit_text(hub_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("حالت مخفی تغییر کرد." if new_stealth else "حالت عادی فعال شد.")


@router.callback_query(F.data.startswith("sp_date_menu:"))
async def handle_date_menu(callback: CallbackQuery):
    offset_days = int(callback.data.split(":")[1])
    kb = get_spiritual_date_picker_keyboard(offset_days)
    await callback.message.edit_text(
        "📅 <b>انتخاب تاریخ برای ردیاب معنوی:</b>\n\n"
        "یکی از میانبرهای زمانی را انتخاب کرده یا تاریخ شمسی دلخواه را تایپ کنید:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sp_cust_date:"))
async def handle_prompt_custom_date(callback: CallbackQuery, state: FSMContext):
    offset_days = int(callback.data.split(":")[1])
    await state.set_state(SpiritualState.waiting_for_custom_date)
    await state.update_data(offset_days=offset_days)

    kb = get_spiritual_cancel_keyboard(offset_days)
    await callback.message.edit_text(
        "✍️ لطفاً تاریخ شمسی مورد نظر را وارد کنید:\n\n"
        "<i>مثال‌ها:</i>\n"
        "• <code>1405/07/18</code>\n"
        "• <code>1405-07-18</code>\n"
        "• <code>2026-10-10</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(SpiritualState.waiting_for_custom_date)
async def process_custom_date_input(message: Message, state: FSMContext):
    parsed = parse_user_date_input(message.text or "")
    if not parsed:
        await message.answer(
            "❌ فرمت تاریخ نامعتبر است. لطفاً به فرمت <code>1405/07/18</code> تایپ کنید:",
            parse_mode="HTML"
        )
        return

    g_iso, j_display = parsed
    # Calculate offset in days from today
    tz = timezone(timedelta(hours=3, minutes=30))
    today_date = datetime.now(tz).date()
    target_date = datetime.strptime(g_iso, "%Y-%m-%d").date()
    diff_days = (today_date - target_date).days

    await state.clear()
    await state.update_data(offset_days=diff_days, stealth=False)

    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")
    full_jalali = format_jalali_full_display(g_iso)
    rel_label = f"🗓 {j_display}"

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=False)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=diff_days, stealth=False)

    await message.answer(hub_text, reply_markup=kb, parse_mode="HTML")


# ==========================================
# 📝 NOTES MANAGEMENT
# ==========================================

@router.callback_query(F.data.startswith("sp_notes:"))
async def handle_edit_notes_prompt(callback: CallbackQuery, state: FSMContext):
    offset_days = int(callback.data.split(":")[1])
    g_iso, _, _ = _calculate_date_from_offset(offset_days)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso)

    await state.set_state(SpiritualState.waiting_for_notes)
    await state.update_data(offset_days=offset_days, page_id=page_data.get("id"))

    current_note = page_data.get("notes", "")
    kb = get_spiritual_notes_keyboard(offset_days)

    prompt = (
        "📝 <b>ثبت یادداشت معنوی روز:</b>\n\n"
        f"یادداشت فعلی: <i>«{current_note}»</i>\n\n"
        "متن جدید خود را ارسال کنید:"
        if current_note
        else "📝 لطفاً یادداشت، دعا، یا احوالات معنوی امروز خود را ارسال کنید:"
    )

    await callback.message.edit_text(prompt, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("sp_clr_notes:"))
async def handle_clear_notes(callback: CallbackQuery, state: FSMContext):
    offset_days = int(callback.data.split(":")[1])
    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso)
    page_id = page_data.get("id")

    if page_id:
        await asyncio.to_thread(update_salah_notes, page_id, "")
        page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso)

    await state.clear()
    await state.update_data(offset_days=offset_days)

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=False)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=offset_days, stealth=False)

    await callback.message.edit_text(hub_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("یادداشت پاک شد 🗑")


@router.message(SpiritualState.waiting_for_notes)
async def process_notes_input(message: Message, state: FSMContext):
    data = await state.get_data()
    offset_days = data.get("offset_days", 0)
    page_id = data.get("page_id")
    text = (message.text or "").strip()

    if page_id and text:
        await asyncio.to_thread(update_salah_notes, page_id, text)

    await state.clear()
    await state.update_data(offset_days=offset_days)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)
    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso)

    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=False)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=offset_days, stealth=False)

    await message.answer("✅ یادداشت معنوی با موفقیت در نوشن ذخیره شد.", reply_markup=kb, parse_mode="HTML")


# ==========================================
# 📖 QURAN READING TRACKER
# ==========================================

@router.callback_query(F.data.startswith("sp_quran:"))
async def handle_log_quran_prompt(callback: CallbackQuery, state: FSMContext):
    offset_days = int(callback.data.split(":")[1])
    await state.set_state(SpiritualState.waiting_for_quran_pages)
    await state.update_data(offset_days=offset_days)

    kb = get_spiritual_cancel_keyboard(offset_days)
    await callback.message.edit_text(
        "📖 <b>ثبت تلاوت قرآن:</b>\n\n"
        "لطفاً صفحات یا سوره تلاوت‌شده را وارد کنید:\n"
        "<i>مثال‌ها:</i>\n"
        "• <code>۴۲۴</code>\n"
        "• <code>ص ۱ تا ۱۰</code>\n"
        "• <code>سوره یس (ص ۴۴۰)</code>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(SpiritualState.waiting_for_quran_pages)
async def process_quran_pages_input(message: Message, state: FSMContext):
    pages_text = (message.text or "").strip()
    data = await state.get_data()
    offset_days = data.get("offset_days", 0)

    g_iso, full_jalali, rel_label = _calculate_date_from_offset(offset_days)

    # Session title logic
    session_title = f"تلاوت {full_jalali}"

    res = await asyncio.to_thread(
        add_quran_reading_entry,
        date_iso=g_iso,
        pages_text=pages_text,
        session_name=session_title
    )

    await state.clear()
    await state.update_data(offset_days=offset_days)

    page_data = await asyncio.to_thread(get_or_create_salah_day, g_iso)
    hub_text = render_spiritual_hub_text(page_data, full_jalali, rel_label, stealth=False)
    kb = build_spiritual_hub_keyboard(page_data, offset_days=offset_days, stealth=False)

    if res:
        await message.answer(
            f"✅ تلاوت قرآن (<code>{pages_text}</code>) با موفقیت در جدول قرآن ثبت شد! ✨",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ خطا در ثبت تلاوت در نوشن.", reply_markup=kb)


# ==========================================
# 📊 REPORTS & ANALYTICS
# ==========================================

def _format_spiritual_report_text(report_data: Dict[str, Any], range_title: str) -> str:
    """Formats comprehensive report text with charts and prayer stats."""
    total_days = report_data.get("total_days", 0)
    if total_days == 0:
        return (
            f"📊 <b>گزارش معنوی ({range_title})</b>\n\n"
            "⚪ رکوردی در این بازه زمانی یافت نشد."
        )

    total_possible = report_data.get("total_prayers_possible", 0)
    total_ada = report_data.get("total_ada", 0)
    total_qaza = report_data.get("total_qaza", 0)
    total_missed = report_data.get("total_missed", 0)
    rate = report_data.get("overall_ada_rate", 0)
    perfect_days = report_data.get("perfect_days", 0)

    bar = _build_progress_bar(rate / 100.0)

    lines = [
        f"📊 <b>تحلیل و گزارش معنوی ({range_title})</b>",
        f"🗓 <b>تعداد روزهای ثبت‌شده:</b> {total_days} روز",
        "",
        f"🎯 <b>نرخ ادای به‌موقع:</b> {bar}",
        f"🟢 کل اداء: <b>{total_ada}</b> | 🟡 کل قضاء: <b>{total_qaza}</b> | ⚪ نخوانده: <b>{total_missed}</b>",
        f"✨ روزهای با ۵/۵ ادای کامل: <b>{perfect_days} روز</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "<b>تفکیک نمازها:</b>",
    ]

    p_stats = report_data.get("prayer_stats", {})
    for k in PRAYER_KEYS:
        st = p_stats.get(k, {})
        name = st.get("name", "")
        emoji = st.get("emoji", "")
        p_ada = st.get("ada", 0)
        p_qaza = st.get("qaza", 0)
        p_rate = st.get("rate", 0)
        lines.append(f"{emoji} <b>{name}:</b> {p_ada} اداء ({p_rate}٪) | {p_qaza} قضا")

    q_count = report_data.get("quran_sessions_count", 0)
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📖 <b>جلسات تلاوت قرآن:</b> <b>{q_count} جلسه</b> ثبت شده")

    q_sessions = report_data.get("quran_sessions", [])[:5]
    if q_sessions:
        for qs in q_sessions:
            pg = qs.get("pages", "") or "—"
            sh_d = qs.get("shamsi_date") or qs.get("date_iso", "")
            lines.append(f"  • {sh_d}: {pg}")

    return "\n".join(lines)


@router.callback_query(F.data == "sp_report_menu")
async def handle_report_menu(callback: CallbackQuery):
    kb = get_spiritual_report_keyboard()
    await callback.message.edit_text(
        "📊 <b>بازه گزارش‌گیری معنوی را انتخاب کنید:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sp_rep:"))
async def handle_spiritual_report_run(callback: CallbackQuery, state: FSMContext):
    preset = callback.data.split(":")[1]

    if preset == "custom":
        await state.set_state(SpiritualState.waiting_for_custom_report_range)
        kb = get_spiritual_cancel_keyboard(0)
        await callback.message.edit_text(
            "✍️ لطفاً بازه تاریخ شمسی را وارد کنید:\n\n"
            "<i>مثال‌ها:</i>\n"
            "• <code>1405/07/01 تا 1405/07/18</code>\n"
            "• <code>1405/07/01 - 1405/07/18</code>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Presets: 7d, month, 30d
    if preset == "7d":
        start_iso, end_iso, label = get_preset_date_range("last_7_days")
    elif preset == "month":
        start_iso, end_iso, label = get_preset_date_range("this_month")
    else:  # 30d
        tz = timezone(timedelta(hours=3, minutes=30))
        end_d = datetime.now(tz).date()
        start_d = end_d - timedelta(days=29)
        start_iso, end_iso = start_d.isoformat(), end_d.isoformat()
        label = "۳۰ روز اخیر"

    report_data = await asyncio.to_thread(get_spiritual_report, start_iso, end_iso)
    report_text = _format_spiritual_report_text(report_data, label)
    kb = get_spiritual_report_result_keyboard()

    await callback.message.edit_text(report_text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(SpiritualState.waiting_for_custom_report_range)
async def process_custom_report_range_input(message: Message, state: FSMContext):
    parsed = parse_custom_date_range(message.text or "")
    if not parsed:
        await message.answer(
            "❌ بازه وارد شده نامعتبر است. لطفاً به فرمت <code>1405/07/01 تا 1405/07/18</code> وارد کنید:",
            parse_mode="HTML"
        )
        return

    start_iso, end_iso, label = parsed
    await state.clear()

    report_data = await asyncio.to_thread(get_spiritual_report, start_iso, end_iso)
    report_text = _format_spiritual_report_text(report_data, label)
    kb = get_spiritual_report_result_keyboard()

    await message.answer(report_text, reply_markup=kb, parse_mode="HTML")
