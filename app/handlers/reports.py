from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.report_state import ReportState
from app.keyboards.inline import (
    build_report_keyboard,
    get_report_date_range_keyboard,
    get_report_person_keyboard,
    get_back_cancel_keyboard,
    SATISFACTION_EMOJIS
)
from app.services.notion_service import get_workspace_persons, query_time_tracker_entries
from app.services.date_helper import (
    get_preset_date_range,
    format_minutes_to_hours_str,
    parse_custom_date_range,
    parse_notion_time_display
)
from app.config import ALLOWED_USERS

router = Router()

def is_user_allowed(user_id: int | None) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS if user_id else False


def calculate_total_minutes(entries: list) -> int:
    """Calculates total duration across entries in minutes."""
    total = 0
    for e in entries:
        dur = e.get("duration")
        if dur is not None and dur > 0:
            total += int(dur)
        else:
            s_iso = e.get("start_iso")
            e_iso = e.get("end_iso")
            if s_iso and e_iso and "T" in s_iso and "T" in e_iso:
                try:
                    fmt = "%H:%M"
                    t_start = datetime.strptime(s_iso.split("T")[1][:5], fmt)
                    t_end = datetime.strptime(e_iso.split("T")[1][:5], fmt)
                    diff = int((t_end - t_start).total_seconds() / 60)
                    if diff > 0:
                        total += diff
                except Exception:
                    pass
    return total


def render_report_text(entries: list, data: dict) -> str:
    """Renders the comprehensive HTML report summary with clean line-by-line entry formatting."""
    date_label = data.get("date_label", "امروز")
    person_name = data.get("person_name", "همه افراد")

    if not entries:
        return (
            f"📊 <b>گزارش کارکرد — {date_label}</b>\n"
            f"👤 <b>انجام‌دهنده:</b> {person_name}\n\n"
            "🔍 <i>در این بازه زمانی هیچ فعالیتی در نوشن ثبت نشده است.</i>"
        )

    total_mins = calculate_total_minutes(entries)
    total_time_str = format_minutes_to_hours_str(total_mins)
    total_count = len(entries)

    # Satisfaction summary counts
    sat_counts: dict[str, int] = {}
    for e in entries:
        sat = e.get("satisfaction")
        if sat:
            sat_counts[sat] = sat_counts.get(sat, 0) + 1

    sat_parts = []
    for s_name, s_count in sat_counts.items():
        emoji = SATISFACTION_EMOJIS.get(s_name, "⭐")
        sat_parts.append(f"{s_count} {s_name} {emoji}")
    sat_summary = " | ".join(sat_parts) if sat_parts else "ثبت نشده"

    # Build formatted line-by-line items list
    items_text = []
    for idx, e in enumerate(entries, 1):
        name = e.get("name", "بدون عنوان")
        url = e.get("url", "")
        url_link = f' <a href="{url}">🔗</a>' if url else ""

        lines = [f"<b>{idx}. {name}</b>{url_link}"]

        # Time line
        time_info = parse_notion_time_display(e.get("start_iso"), e.get("end_iso"), e.get("duration"))
        if time_info != "—":
            lines.append(f"   ⏱ <b>زمان:</b> {time_info}")

        # Person line (show if available)
        if e.get("person_name"):
            lines.append(f"   👤 <b>انجام‌دهنده:</b> {e['person_name']}")

        # Satisfaction line
        sat = e.get("satisfaction")
        if sat:
            sat_emoji = SATISFACTION_EMOJIS.get(sat, "⭐")
            lines.append(f"   ⭐ <b>میزان رضایت:</b> {sat} {sat_emoji}")

        # Description line
        desc = e.get("description")
        if desc:
            lines.append(f"   📝 <b>توضیحات:</b> <i>{desc}</i>")

        items_text.append("\n".join(lines))

    items_block = "\n\n".join(items_text)

    return (
        f"📊 <b>گزارش کارکرد — {date_label}</b>\n"
        f"👤 <b>انجام‌دهنده:</b> {person_name}\n\n"
        f"⏱ <b>مجموع زمان کار:</b> <code>{total_time_str}</code>\n"
        f"📌 <b>تعداد فعالیت‌ها:</b> <code>{total_count} تسک</code>\n"
        f"⭐ <b>وضعیت رضایت:</b> {sat_summary}\n\n"
        "─────────────────\n"
        f"{items_block}\n"
        "─────────────────"
    )

async def fetch_and_render_report(message_or_query: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    start_iso = data.get("start_iso")
    end_iso = data.get("end_iso")
    person_id = data.get("person_id")

    try:
        entries = query_time_tracker_entries(
            start_date_iso=start_iso,
            end_date_iso=end_iso,
            person_id=person_id
        )
        text = render_report_text(entries, data)
    except Exception as e:
        text = f"❌ خطا در دریافت گزارش از نوشن:\n<code>{e}</code>"

    markup = build_report_keyboard(data)

    if isinstance(message_or_query, Message):
        await message_or_query.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    elif isinstance(message_or_query, CallbackQuery) and isinstance(message_or_query.message, Message):
        await message_or_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


@router.message(F.text.contains("گزارش"))
async def open_report_dashboard(message: Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id if message.from_user else None):
        await message.answer("⛔ شما به این بخش دسترسی ندارید.")
        return

    await state.clear()
    s_iso, e_iso, d_label = get_preset_date_range("today")
    
    initial_data = {
        "start_iso": s_iso,
        "end_iso": e_iso,
        "date_preset": "today",
        "date_label": d_label,
        "person_id": None,
        "person_name": "همه افراد"
    }
    await state.update_data(**initial_data)
    await state.set_state(ReportState.viewing_report)
    await fetch_and_render_report(message, state)


# --- Filters Handlers ---
@router.callback_query(F.data == "rep_pick_date")
async def rep_pick_date_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📅 <b>بازه زمانی گزارش را انتخاب کنید:</b>",
            reply_markup=get_report_date_range_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_set_date:"))
async def rep_set_date_handler(callback: CallbackQuery, state: FSMContext):
    preset = (callback.data or "").split(":")[1]
    s_iso, e_iso, d_label = get_preset_date_range(preset)
    
    await state.update_data(start_iso=s_iso, end_iso=e_iso, date_preset=preset, date_label=d_label)
    await fetch_and_render_report(callback, state)
    await callback.answer()


@router.callback_query(F.data == "rep_pick_person")
async def rep_pick_person_handler(callback: CallbackQuery):
    persons = get_workspace_persons()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "👤 <b>انجام‌دهنده مورد نظر برای فیلتر را انتخاب کنید:</b>",
            reply_markup=get_report_person_keyboard(persons),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_set_person:"))
async def rep_set_person_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":", 1)
    person_id = parts[1]

    if person_id == "all":
        person_name = "همه افراد"
        await state.update_data(person_id=None, person_name=person_name)
    else:
        persons = get_workspace_persons()
        person_name = next((p["name"] for p in persons if p["id"] == person_id), "کاربر")
        await state.update_data(person_id=person_id, person_name=person_name)

    await fetch_and_render_report(callback, state)
    await callback.answer(f"فیلتر شخص: {person_name}")

@router.callback_query(F.data == "rep_refresh")
async def rep_refresh_handler(callback: CallbackQuery, state: FSMContext):
    await fetch_and_render_report(callback, state)
    await callback.answer("🔄 گزارش بروزرسانی شد.")


@router.callback_query(F.data == "rep_back_to_report")
async def rep_back_to_report_handler(callback: CallbackQuery, state: FSMContext):
    await fetch_and_render_report(callback, state)
    await callback.answer()


@router.callback_query(F.data == "rep_close")
async def rep_close_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("📊 گزارش بسته شد.")
    await callback.answer()
    
# --- Custom Date Range Handlers ---
@router.callback_query(F.data == "rep_custom_date")
async def rep_custom_date_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ReportState.typing_custom_date_range)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📅 لطفاً بازه تاریخ دلخواه شمسی را ارسال کنید:\n\n"
            "▫️ <b>نمونه بازه:</b> <code>1405/05/01 تا 1405/05/15</code>\n"
            "▫️ <b>نمونه یک روز:</b> <code>1405/05/01</code>",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(ReportState.typing_custom_date_range)
async def rep_process_custom_date(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    parsed = parse_custom_date_range(text)
    
    data = await state.get_data()
    prompt_id = data.get("last_prompt_id")

    if not parsed:
        err = await message.answer(
            "❌ فرمت بازه تاریخ نامعتبر است.\n"
            "لطفاً مانند <code>1405/05/01 تا 1405/05/15</code> یا <code>1405/05/01</code> وارد کنید:",
            parse_mode="HTML"
        )
        # Store error message id for cleanup
        err_list = data.get("error_msg_ids", [])
        err_list.extend([err.message_id, message.message_id])
        await state.update_data(error_msg_ids=err_list)
        return

    # Cleanup prompts and error messages
    if prompt_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
        except Exception:
            pass

    for em_id in data.get("error_msg_ids", []):
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=em_id)
        except Exception:
            pass

    try:
        await message.delete()
    except Exception:
        pass

    s_iso, e_iso, d_label = parsed
    await state.update_data(
        start_iso=s_iso,
        end_iso=e_iso,
        date_preset="custom",
        date_label=d_label,
        error_msg_ids=[]
    )
    await state.set_state(ReportState.viewing_report)
    await fetch_and_render_report(message, state)