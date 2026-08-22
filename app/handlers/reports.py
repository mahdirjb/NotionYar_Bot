from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.report_state import ReportState
from app.keyboards.inline import (
    build_report_keyboard,
    get_report_date_range_keyboard,
    get_report_person_keyboard,
    get_entries_selector_keyboard,
    get_entry_detail_keyboard,
    get_delete_confirm_keyboard,
    get_back_cancel_keyboard,
    get_edit_fields_keyboard,
    get_edit_satisfaction_keyboard,
    get_edit_person_keyboard,
    SATISFACTION_EMOJIS
)
from app.services.notion_service import (
    get_workspace_persons,
    query_time_tracker_entries,
    get_time_tracker_entry,
    archive_notion_page,
    update_notion_page_properties
)
from app.services.date_helper import (
    get_preset_date_range,
    format_minutes_to_hours_str,
    parse_notion_time_display,
    parse_custom_date_range
)
from app.services.auth_service import (
    has_permission,
    PERM_VIEW_REPORTS,
    PERM_VIEW_ALL_USERS,
    PERM_EDIT_RECORDS,
    PERM_DELETE_RECORDS
)

router = Router()


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

    items_text = []
    for idx, e in enumerate(entries, 1):
        name = e.get("name", "بدون عنوان")
        url = e.get("url", "")
        url_link = f' <a href="{url}">🔗</a>' if url else ""

        lines = [f"<b>{idx}. {name}</b>{url_link}"]

        time_info = parse_notion_time_display(e.get("start_iso"), e.get("end_iso"), e.get("duration"))
        if time_info != "—":
            lines.append(f"   ⏱ <b>زمان:</b> {time_info}")

        if e.get("person_name"):
            lines.append(f"   👤 <b>انجام‌دهنده:</b> {e['person_name']}")

        sat = e.get("satisfaction")
        if sat:
            sat_emoji = SATISFACTION_EMOJIS.get(sat, "⭐")
            lines.append(f"   ⭐ <b>میزان رضایت:</b> {sat} {sat_emoji}")

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


def render_entry_detail_text(entry: dict) -> str:
    """Formats a single record detail text."""
    time_info = parse_notion_time_display(entry.get("start_iso"), entry.get("end_iso"), entry.get("duration"))
    person = entry.get("person_name") or "تعیین نشده"
    sat = entry.get("satisfaction")
    sat_text = f"{SATISFACTION_EMOJIS.get(sat, '⭐')} {sat}" if sat else "تعیین نشده"
    desc = entry.get("description") or "ندارد"

    return (
        "📄 <b>جزئیات کامل رکورد:</b>\n\n"
        f"📌 <b>عنوان:</b> {entry.get('name')}\n"
        f"⏱ <b>زمان / بازه:</b> {time_info}\n"
        f"👤 <b>انجام‌دهنده:</b> {person}\n"
        f"⭐ <b>میزان رضایت:</b> {sat_text}\n"
        f"📝 <b>توضیحات:</b> {desc}"
    )


async def fetch_and_render_report(message_or_query: Message | CallbackQuery, state: FSMContext):
    data = await state.get_data()
    start_iso = data.get("start_iso")
    end_iso = data.get("end_iso")
    person_id = data.get("person_id")
    user_id = message_or_query.from_user.id if message_or_query.from_user else None

    try:
        entries = query_time_tracker_entries(
            start_date_iso=start_iso,
            end_date_iso=end_iso,
            person_id=person_id
        )
        text = render_report_text(entries, data)
    except Exception as e:
        text = f"❌ خطا در دریافت گزارش از نوشن:\n<code>{e}</code>"
        entries = []

    markup = build_report_keyboard(data, has_entries=bool(entries), user_id=user_id)

    if isinstance(message_or_query, Message):
        await message_or_query.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    elif isinstance(message_or_query, CallbackQuery) and isinstance(message_or_query.message, Message):
        await message_or_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


async def show_edit_menu(
    event: Message | CallbackQuery,
    page_id: str,
    bot: Bot,
    state: FSMContext,
    alert_text: str | None = None
):
    """Renders the updated record summary directly inside the edit submenu."""
    entry = get_time_tracker_entry(page_id)
    if not entry:
        if isinstance(event, CallbackQuery):
            await event.answer("⚠️ این رکورد یافت نشد.", show_alert=True)
        return

    detail_summary = render_entry_detail_text(entry)
    text = (
        f"{detail_summary}\n\n"
        "👇 <b>برای ویرایش هر بخش، دکمه مربوطه را انتخاب کنید:</b>"
    )
    markup = get_edit_fields_keyboard(page_id)

    data = await state.get_data()
    detail_msg_id = data.get("detail_message_id")

    if isinstance(event, CallbackQuery) and isinstance(event.message, Message):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        if alert_text:
            await event.answer(alert_text, show_alert=False)
        else:
            await event.answer()
    elif isinstance(event, Message):
        chat_id = event.chat.id
        if detail_msg_id:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=detail_msg_id,
                    text=text,
                    reply_markup=markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                return
            except Exception:
                pass
        msg = await event.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        await state.update_data(detail_message_id=msg.message_id)


# --- Report Dashboard Entry ---
@router.message(F.text.contains("گزارش"))
async def open_report_dashboard(message: Message, state: FSMContext):
    user_id = message.from_user.id if message.from_user else None
    if not has_permission(user_id, PERM_VIEW_REPORTS):
        await message.answer("⛔ شما به بخش گزارش‌ها دسترسی ندارید.")
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
        err_list = data.get("error_msg_ids", [])
        err_list.extend([err.message_id, message.message_id])
        await state.update_data(error_msg_ids=err_list)
        return

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


@router.callback_query(F.data == "rep_pick_person")
async def rep_pick_person_handler(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_VIEW_ALL_USERS):
        await callback.answer("⛔ شما دسترسی به فیلتر سایر کاربران را ندارید.", show_alert=True)
        return

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


# --- Record Details & Edit Handlers ---
@router.callback_query(F.data == "rep_manage_entries")
async def rep_manage_entries_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not (has_permission(user_id, PERM_EDIT_RECORDS) or has_permission(user_id, PERM_DELETE_RECORDS)):
        await callback.answer("⛔ شما دسترسی به ویرایش یا حذف رکوردها را ندارید.", show_alert=True)
        return

    data = await state.get_data()
    entries = query_time_tracker_entries(
        start_date_iso=data.get("start_iso"),
        end_date_iso=data.get("end_iso"),
        person_id=data.get("person_id")
    )
    if not entries:
        await callback.answer("⚠️ رکوردی برای نمایش یا ویرایش وجود ندارد.", show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📋 <b>یکی از رکوردهای زیر را برای مشاهده جزئیات، ویرایش یا حذف انتخاب کنید:</b>",
            reply_markup=get_entries_selector_keyboard(entries),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_det:"))
async def rep_entry_detail_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    if isinstance(callback.message, Message):
        await state.update_data(detail_message_id=callback.message.message_id)

    entry = get_time_tracker_entry(page_id)
    if not entry:
        await callback.answer("⚠️ این رکورد یافت نشد.", show_alert=True)
        return

    user_id = callback.from_user.id if callback.from_user else None
    text = render_entry_detail_text(entry)
    markup = get_entry_detail_keyboard(page_id, entry.get("url", ""), user_id=user_id)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.startswith("rep_confirm_del:"))
async def rep_confirm_delete_handler(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_DELETE_RECORDS):
        await callback.answer("⛔ شما دسترسی به حذف رکوردها را ندارید.", show_alert=True)
        return

    page_id = (callback.data or "").split(":", 1)[1]
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "⚠️ <b>آیا از حذف این رکورد از دیتابیس نوشن اطمینان دارید؟</b>\n\n"
            "<i>این عملیات رکورد را در نوشن آرشیو می‌کند.</i>",
            reply_markup=get_delete_confirm_keyboard(page_id),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_do_del:"))
async def rep_do_delete_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_DELETE_RECORDS):
        await callback.answer("⛔ شما دسترسی به حذف رکوردها را ندارید.", show_alert=True)
        return

    page_id = (callback.data or "").split(":", 1)[1]
    success = archive_notion_page(page_id)

    if success:
        await callback.answer("✅ رکورد با موفقیت از نوشن حذف شد!", show_alert=True)
    else:
        await callback.answer("❌ خطا در حذف رکورد از نوشن.", show_alert=True)

    await fetch_and_render_report(callback, state)


# --- Edit Submenu Handlers ---
@router.callback_query(F.data.startswith("rep_edit:"))
async def rep_edit_menu_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_EDIT_RECORDS):
        await callback.answer("⛔ شما دسترسی به ویرایش رکوردها را ندارید.", show_alert=True)
        return

    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    await show_edit_menu(callback, page_id, bot, state)


# 1. Edit Name
@router.callback_query(F.data.startswith("rep_ed_name:"))
async def rep_edit_name_prompt(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    await state.set_state(ReportState.editing_name)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "✏️ لطفاً <b>عنوان جدید فعالیت</b> را ارسال کنید:",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(ReportState.editing_name)
async def rep_process_edit_name(message: Message, state: FSMContext, bot: Bot):
    new_name = (message.text or "").strip()
    data = await state.get_data()
    page_id = data.get("editing_page_id")

    if not new_name:
        err = await message.answer("❌ عنوان نمی‌تواند خالی باشد. متنی وارد کنید:")
        await state.update_data(error_msg_ids=[err.message_id, message.message_id])
        return

    update_notion_page_properties(page_id, {"Name": {"title": [{"text": {"content": new_name}}]}})

    prompt_id = data.get("last_prompt_id")
    if prompt_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass

    await state.set_state(ReportState.viewing_report)
    await show_edit_menu(message, page_id, bot, state)


# 2. Edit Description
@router.callback_query(F.data.startswith("rep_ed_desc:"))
async def rep_edit_desc_prompt(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    await state.set_state(ReportState.editing_description)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📝 لطفاً <b>متن جدید توضیحات</b> را ارسال کنید (برای خالی کردن بنویسید <code>خالی</code>):",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(ReportState.editing_description)
async def rep_process_edit_desc(message: Message, state: FSMContext, bot: Bot):
    new_desc = (message.text or "").strip()
    data = await state.get_data()
    page_id = data.get("editing_page_id")

    content = "" if new_desc == "خالی" else new_desc
    rich_text = [{"text": {"content": content}}] if content else []
    update_notion_page_properties(page_id, {"Description": {"rich_text": rich_text}})

    prompt_id = data.get("last_prompt_id")
    if prompt_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass

    await state.set_state(ReportState.viewing_report)
    await show_edit_menu(message, page_id, bot, state)


# 3. Edit Duration
@router.callback_query(F.data.startswith("rep_ed_dur:"))
async def rep_edit_dur_prompt(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    await state.set_state(ReportState.editing_duration)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "⏱ لطفاً <b>مدت زمان جدید را به دقیقه</b> وارد کنید (مثلاً <code>45</code>):",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(ReportState.editing_duration)
async def rep_process_edit_dur(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    data = await state.get_data()
    page_id = data.get("editing_page_id")

    if not text.isdigit() or not (0 <= int(text) <= 1440):
        err = await message.answer("❌ لطفاً عددی بین ۰ تا ۱۴۴۰ دقیقه وارد کنید:")
        await state.update_data(error_msg_ids=[err.message_id, message.message_id])
        return

    dur_val = int(text)
    update_notion_page_properties(page_id, {"MDuration": {"number": dur_val}})

    prompt_id = data.get("last_prompt_id")
    if prompt_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass

    await state.set_state(ReportState.viewing_report)
    await show_edit_menu(message, page_id, bot, state)


# 4. Edit Satisfaction
@router.callback_query(F.data.startswith("rep_ed_sat:"))
async def rep_edit_sat_menu(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "⭐ <b>میزان رضایت جدید را انتخاب کنید:</b>",
            reply_markup=get_edit_satisfaction_keyboard(page_id),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_set_ed_sat:"))
async def rep_set_edit_sat_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    sat_val = (callback.data or "").split(":", 1)[1]
    data = await state.get_data()
    page_id = data.get("editing_page_id")

    update_notion_page_properties(page_id, {"Satisfaction": {"select": {"name": sat_val}}})
    await show_edit_menu(callback, page_id, bot, state, alert_text=f"✅ رضایت به '{sat_val}' تغییر یافت.")


# 5. Edit Person
@router.callback_query(F.data.startswith("rep_ed_per:"))
async def rep_edit_person_menu(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    persons = get_workspace_persons()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "👤 <b>انجام‌دهنده جدید را انتخاب کنید:</b>",
            reply_markup=get_edit_person_keyboard(page_id, persons),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("rep_set_ed_per:"))
async def rep_set_edit_person_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    new_person_id = (callback.data or "").split(":", 1)[1]
    data = await state.get_data()
    page_id = data.get("editing_page_id")

    update_notion_page_properties(page_id, {"Person": {"people": [{"id": new_person_id}]}})
    await show_edit_menu(callback, page_id, bot, state, alert_text="✅ انجام‌دهنده تغییر کرد.")