# app/handlers/life_tracker.py

from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.life_tracker_state import LifeTrackerCard, LifeTrackerReportState
from app.keyboards.inline import (
    build_life_tracker_hub_keyboard,
    build_life_tracker_card_keyboard,
    get_life_tracker_type_keyboard,
    get_life_tracker_mode_keyboard,
    get_life_tracker_date_keyboard,
    get_life_tracker_notes_keyboard,
    get_lt_back_cancel_keyboard,
    build_life_tracker_report_keyboard,
    get_lt_report_date_range_keyboard,
    get_lt_report_type_filter_keyboard,
    get_lt_report_mode_filter_keyboard,
    get_lt_entries_selector_keyboard,
    get_lt_entry_detail_keyboard,
    get_lt_delete_confirm_keyboard,
    get_lt_edit_fields_keyboard,
    get_lt_edit_type_keyboard,
    get_lt_edit_mode_keyboard,
    TYPE_EMOJIS,
    MODE_EMOJIS
)
from app.services.notion_service import (
    TYPE_MODE_MAPPING,
    add_life_tracker_entry,
    query_life_tracker_entries,
    get_life_tracker_entry,
    archive_notion_page,
    update_notion_page_properties
)
from app.services.date_helper import (
    get_jalali_date_info,
    parse_user_date_input,
    get_preset_date_range,
    parse_custom_date_range
)
from app.services.auth_service import has_permission, PERM_ADMIN

router = Router()

PAGE_SIZE = 5


# ==========================================
# 🧹 CHAT HYGIENE HELPERS
# ==========================================

async def cleanup_prompt_messages(bot: Bot, chat_id: int, state: FSMContext, user_msg: Message | None = None):
    """Deletes temporary prompt and error messages to keep the chat clean."""
    data = await state.get_data()
    prompt_id = data.get("last_prompt_id")
    if prompt_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=prompt_id)
        except Exception:
            pass

    for em_id in data.get("error_msg_ids", []):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=em_id)
        except Exception:
            pass
    await state.update_data(error_msg_ids=[])

    if user_msg:
        try:
            await user_msg.delete()
        except Exception:
            pass


async def register_error_message(state: FSMContext, error_msg: Message, user_msg: Message | None = None):
    """Saves error message IDs for subsequent cleanup."""
    data = await state.get_data()
    err_list = data.get("error_msg_ids", [])
    err_list.append(error_msg.message_id)
    if user_msg:
        err_list.append(user_msg.message_id)
    await state.update_data(error_msg_ids=err_list)


# ==========================================
# 🌿 LIFE TRACKER HUB & LANDING
# ==========================================

def render_hub_text() -> str:
    return (
        "🌱 <b>بخش مدیریت روزمرگی‌ها (Life Tracker)</b>\n\n"
        "این بخش اختصاصی برای ثبت، مشاهده و تحلیل فعالیت‌های تکرارشونده، عادات، "
        "مراقبت‌های فردی، خریدها و اتفاقات روزانه متصل به نوشن است.\n\n"
        "👇 <i>یکی از بخش‌های زیر را انتخاب کنید:</i>"
    )


@router.message(F.text.contains("روزمرگی"))
@router.message(Command("life"))
async def open_life_tracker_hub(message: Message, state: FSMContext):
    user_id = message.from_user.id if message.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await message.answer("⛔ شما به بخش لاگ روزمرگی دسترسی ندارید.")
        return

    await state.clear()
    await message.answer(
        render_hub_text(),
        reply_markup=build_life_tracker_hub_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "lt_back_to_hub")
async def back_to_hub_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await callback.answer("⛔ عدم دسترسی.", show_alert=True)
        return

    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_hub_text(),
            reply_markup=build_life_tracker_hub_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "lt_close_hub")
async def close_hub_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("🌱 بخش روزمرگی بسته شد.")
    await callback.answer()


@router.callback_query(F.data == "lt_noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()


# ==========================================
# 📝 CREATE ENTRY FLOW (Interactive Card)
# ==========================================

def render_card_text(data: dict) -> str:
    name = data.get("name") or "وارد نشده ❌"
    t_val = data.get("type")
    t_emoji = TYPE_EMOJIS.get(t_val, "🏷") if t_val else "🏷"
    type_display = f"{t_emoji} {t_val}" if t_val else "انتخاب نشده ❌"

    modes = data.get("modes") or []
    if modes:
        mode_str = " | ".join([f"{MODE_EMOJIS.get(m, '✨')} {m}" for m in modes])
    else:
        mode_str = "بدون انتخاب (عادی)"

    d_label = data.get("date_label", "امروز")
    notes = data.get("notes") or "—"

    return (
        "📋 <b>فرم پیش‌نویس ثبت روزمرگی (Life Tracker)</b>\n\n"
        f"🏷 <b>نوع فعالیت:</b> {type_display}\n"
        f"📌 <b>عنوان رکورد:</b> {name}\n"
        f"🎭 <b>حالت (Mode):</b> {mode_str}\n"
        f"📅 <b>تاریخ:</b> {d_label}\n"
        f"📝 <b>یادداشت:</b> {notes}\n\n"
        "👇 <i>با دکمه‌های زیر فیلدها را تنظیم و در نهایت ثبت کنید:</i>"
    )


async def update_main_card(bot: Bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    card_msg_id = data.get("card_message_id")
    if card_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=card_msg_id,
                text=render_card_text(data),
                reply_markup=build_life_tracker_card_keyboard(data),
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.callback_query(F.data == "lt_new_log")
async def start_new_log_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await callback.answer("⛔ عدم دسترسی.", show_alert=True)
        return

    await state.clear()
    g_today, j_today = get_jalali_date_info(offset_days=0)
    initial_data = {
        "name": None,
        "type": None,
        "modes": [],
        "date_iso": g_today,
        "date_label": f"امروز ({j_today})",
        "notes": "",
        "error_msg_ids": []
    }

    if isinstance(callback.message, Message):
        card_msg = await callback.message.edit_text(
            render_card_text(initial_data),
            reply_markup=build_life_tracker_card_keyboard(initial_data),
            parse_mode="HTML"
        )
        initial_data["card_message_id"] = card_msg.message_id
        await state.update_data(**initial_data)
        await state.set_state(LifeTrackerCard.viewing_card)
    await callback.answer()


@router.callback_query(F.data == "lt_back_to_card")
async def back_to_card_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if isinstance(callback.message, Message):
        await cleanup_prompt_messages(bot, callback.message.chat.id, state)
        data = await state.get_data()
        await state.set_state(LifeTrackerCard.viewing_card)
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_life_tracker_card_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer()


# 1. Pick Type
@router.callback_query(F.data == "lt_pick_type")
async def pick_type_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🏷 <b>نوع فعالیت مورد نظر را انتخاب کنید:</b>",
            reply_markup=get_life_tracker_type_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_set_type:"))
async def set_type_handler(callback: CallbackQuery, state: FSMContext):
    selected_type = (callback.data or "").split(":", 1)[1]
    data = await state.get_data()
    
    # Auto-fill Name if previously empty or matched prior type
    current_name = data.get("name")
    if not current_name or current_name == data.get("type"):
        new_name = selected_type
    else:
        new_name = current_name

    # Reset modes if newly selected type doesn't support them
    valid_modes_for_type = TYPE_MODE_MAPPING.get(selected_type, [])
    current_modes = data.get("modes", [])
    updated_modes = [m for m in current_modes if m in valid_modes_for_type]

    await state.update_data(type=selected_type, name=new_name, modes=updated_modes)
    updated_data = await state.get_data()

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(updated_data),
            reply_markup=build_life_tracker_card_keyboard(updated_data),
            parse_mode="HTML"
        )
    await callback.answer(f"نوع: {selected_type}")


# 2. Pick Mode (Multi-Select Toggle)
@router.callback_query(F.data == "lt_pick_mode")
async def pick_mode_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    t_val = data.get("type")
    if not t_val:
        await callback.answer("⚠️ لطفاً ابتدا نوع فعالیت را انتخاب کنید!", show_alert=True)
        return

    available_modes = TYPE_MODE_MAPPING.get(t_val, [])
    if not available_modes:
        await callback.answer(f"ℹ️ برای «{t_val}» حالتی تعریف نشده است.", show_alert=True)
        return

    selected_modes = data.get("modes", [])
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"🎭 <b>انتخاب حالت‌ها برای «{t_val}»:</b>\n"
            "<i>(می‌توانید چند گزینه را انتخاب یا تیک آن‌ها را بردارید)</i>",
            reply_markup=get_life_tracker_mode_keyboard(t_val, selected_modes),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_tog_mode:"))
async def toggle_mode_handler(callback: CallbackQuery, state: FSMContext):
    mode_name = (callback.data or "").split(":", 1)[1]
    data = await state.get_data()
    t_val = data.get("type", "")
    selected_modes = list(data.get("modes", []))

    if mode_name in selected_modes:
        selected_modes.remove(mode_name)
    else:
        selected_modes.append(mode_name)

    await state.update_data(modes=selected_modes)

    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=get_life_tracker_mode_keyboard(t_val, selected_modes)
        )
    await callback.answer()


@router.callback_query(F.data == "lt_clear_modes")
async def clear_modes_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    t_val = data.get("type", "")
    await state.update_data(modes=[])
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=get_life_tracker_mode_keyboard(t_val, [])
        )
    await callback.answer("حالت‌ها پاک شدند.")


# 3. Edit Name
@router.callback_query(F.data == "lt_edit_name")
async def edit_name_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LifeTrackerCard.typing_name)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "✏️ لطفاً <b>عنوان رکورد</b> را ارسال کنید (حداکثر ۱۰۰ کاراکتر):",
            reply_markup=get_lt_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(LifeTrackerCard.typing_name)
async def process_name_input(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    if not text:
        err = await message.answer("❌ عنوان نمی‌تواند خالی باشد. متنی وارد کنید:")
        await register_error_message(state, err, user_msg=message)
        return
    if len(text) > 100:
        err = await message.answer("❌ عنوان طولانی است (حداکثر ۱۰۰ کاراکتر):")
        await register_error_message(state, err, user_msg=message)
        return

    await state.update_data(name=text)
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(LifeTrackerCard.viewing_card)
    await update_main_card(bot, message.chat.id, state)


# 4. Date Picker
@router.callback_query(F.data == "lt_pick_date")
async def pick_date_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📅 <b>تاریخ ثبت را انتخاب کنید:</b>",
            reply_markup=get_life_tracker_date_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_set_date_preset:"))
async def set_date_preset_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    offset = int(parts[1])
    label_text = parts[2]
    
    g_iso, j_str = get_jalali_date_info(offset_days=offset)
    await state.update_data(date_iso=g_iso, date_label=f"{label_text} ({j_str})")
    updated_data = await state.get_data()

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(updated_data),
            reply_markup=build_life_tracker_card_keyboard(updated_data),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data == "lt_enter_custom_date")
async def enter_custom_date_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LifeTrackerCard.typing_custom_date)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📅 تاریخ مورد نظر را به صورت <b>شمسی</b> (مثلاً <code>1405/05/25</code>) ارسال کنید:",
            reply_markup=get_lt_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(LifeTrackerCard.typing_custom_date)
async def process_custom_date_input(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    parsed = parse_user_date_input(text)
    if not parsed:
        err = await message.answer(
            "❌ تاریخ نامعتبر است. لطفاً به فرمت <code>1405/05/25</code> وارد کنید:",
            parse_mode="HTML"
        )
        await register_error_message(state, err, user_msg=message)
        return

    g_iso, j_str = parsed
    await state.update_data(date_iso=g_iso, date_label=j_str)
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(LifeTrackerCard.viewing_card)
    await update_main_card(bot, message.chat.id, state)


# 5. Notes
@router.callback_query(F.data == "lt_edit_notes")
async def edit_notes_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LifeTrackerCard.typing_notes)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📝 لطفاً <b>یادداشت یا توضیحات</b> را ارسال کنید (حداکثر ۲۰۰۰ کاراکتر):",
            reply_markup=get_life_tracker_notes_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(LifeTrackerCard.typing_notes)
async def process_notes_input(message: Message, state: FSMContext, bot: Bot):
    notes = (message.text or "").strip()
    if len(notes) > 2000:
        err = await message.answer("❌ متن یادداشت بیش از حد طولانی است:")
        await register_error_message(state, err, user_msg=message)
        return

    await state.update_data(notes=notes)
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(LifeTrackerCard.viewing_card)
    await update_main_card(bot, message.chat.id, state)


@router.callback_query(F.data == "lt_clear_notes")
async def clear_notes_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.update_data(notes="")
    if isinstance(callback.message, Message):
        await cleanup_prompt_messages(bot, callback.message.chat.id, state)
        data = await state.get_data()
        await state.set_state(LifeTrackerCard.viewing_card)
        await update_main_card(bot, callback.message.chat.id, state)
    await callback.answer("یادداشت پاک شد.")


# 6. Submit & Cancel
@router.callback_query(F.data == "lt_cancel_card")
async def cancel_card_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_hub_text(),
            reply_markup=build_life_tracker_hub_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer("فرم لغو شد.")


@router.callback_query(F.data == "lt_submit_card")
async def submit_card_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    t_val = data.get("type")
    name = data.get("name")

    if not t_val:
        await callback.answer("⚠️ لطفاً نوع فعالیت را انتخاب کنید!", show_alert=True)
        return
    if not name:
        await callback.answer("⚠️ لطفاً عنوان رکورد را مشخص کنید!", show_alert=True)
        return

    date_iso = data.get("date_iso") or get_jalali_date_info(0)[0]
    modes = data.get("modes", [])
    notes = data.get("notes", "")

    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("⏳ در حال ثبت اطلاعات در دیتابیس روزمرگی نوشن...")

        try:
            res = add_life_tracker_entry(
                name=name,
                type_val=t_val,
                date_iso=date_iso,
                mode_list=modes,
                notes=notes
            )
            page_url = res.get("url", "") if isinstance(res, dict) else ""
            t_emoji = TYPE_EMOJIS.get(t_val, "🏷")
            mode_display = " | ".join([f"{MODE_EMOJIS.get(m, '✨')} {m}" for m in modes]) if modes else "بدون حالت"

            success_text = (
                "✅ <b>رکورد روزمرگی با موفقیت در نوشن ثبت شد!</b>\n\n"
                f"🏷 <b>نوع:</b> {t_emoji} {t_val}\n"
                f"📌 <b>عنوان:</b> {name}\n"
                f"🎭 <b>حالت:</b> {mode_display}\n"
                f"📅 <b>تاریخ:</b> {data.get('date_label')}\n"
            )
            if notes:
                success_text += f"📝 <b>یادداشت:</b> {notes}\n"
            if page_url:
                success_text += f'\n<a href="{page_url}">🔗 مشاهده در نوشن</a>'

            await callback.message.edit_text(
                success_text,
                reply_markup=build_life_tracker_hub_keyboard(),
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e:
            await callback.message.edit_text(
                f"❌ خطا در ثبت نوشن:\n<code>{e}</code>",
                reply_markup=build_life_tracker_hub_keyboard(),
                parse_mode="HTML"
            )
    await callback.answer()


# ==========================================
# 📊 REPORTS, PAGINATION & FILTERING
# ==========================================

def render_report_text(entries: list, data: dict, current_page: int = 1) -> tuple[str, int]:
    date_label = data.get("date_label", "امروز")
    t_filter = data.get("type_val", "all")
    t_display = f"{TYPE_EMOJIS.get(t_filter, '')} {t_filter}" if t_filter != "all" else "همه انواع"

    m_filter = data.get("mode_val", "all")
    m_display = f"{MODE_EMOJIS.get(m_filter, '')} {m_filter}" if m_filter != "all" else "همه حالت‌ها"

    total_count = len(entries)
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    safe_page = min(max(1, current_page), total_pages)

    if not entries:
        text = (
            f"📊 <b>گزارش روزمرگی — {date_label}</b>\n"
            f"🏷 <b>نوع فعالیت:</b> {t_display} | 🎭 <b>حالت:</b> {m_display}\n\n"
            "🔍 <i>در این بازه هیچ رکوردی ثبت نشده است.</i>"
        )
        return text, 1

    start_idx = (safe_page - 1) * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_entries = entries[start_idx:end_idx]

    items_text = []
    for idx, e in enumerate(page_entries, start_idx + 1):
        name = e.get("name", "بدون عنوان")
        url = e.get("url", "")
        url_link = f' <a href="{url}">🔗</a>' if url else ""
        t_val = e.get("type", "")
        t_em = TYPE_EMOJIS.get(t_val, "🏷")

        lines = [f"<b>{idx}. {t_em} {name}</b>{url_link}"]
        
        # Format date
        raw_d = e.get("date_iso")
        if raw_d:
            parsed_d = parse_user_date_input(raw_d)
            d_str = parsed_d[1] if parsed_d else raw_d
            lines.append(f"   📅 <b>تاریخ:</b> {d_str}")

        modes = e.get("modes", [])
        if modes:
            m_str = " | ".join([f"{MODE_EMOJIS.get(m, '✨')} {m}" for m in modes])
            lines.append(f"   🎭 <b>حالت:</b> {m_str}")

        notes = e.get("notes")
        if notes:
            lines.append(f"   📝 <b>یادداشت:</b> <i>{notes}</i>")

        items_text.append("\n".join(lines))

    items_block = "\n\n".join(items_text)

    text = (
        f"📊 <b>گزارش روزمرگی — {date_label}</b>\n"
        f"🏷 <b>نوع:</b> {t_display} | 🎭 <b>حالت:</b> {m_display}\n"
        f"📌 <b>مجموع لاگ‌ها:</b> <code>{total_count} مورد</code> (صفحه {safe_page} از {total_pages})\n\n"
        "─────────────────\n"
        f"{items_block}\n"
        "─────────────────"
    )
    return text, total_pages


async def fetch_and_render_report(message_or_query: Message | CallbackQuery, state: FSMContext, page: int = 1):
    data = await state.get_data()
    start_iso = data.get("start_iso")
    end_iso = data.get("end_iso")
    type_val = data.get("type_val")
    mode_val = data.get("mode_val")

    try:
        entries = query_life_tracker_entries(
            start_date_iso=start_iso,
            end_date_iso=end_iso,
            type_val=type_val,
            mode_val=mode_val
        )
        text, total_pages = render_report_text(entries, data, current_page=page)
    except Exception as e:
        text = f"❌ خطا در دریافت لاگ‌های روزمرگی از نوشن:\n<code>{e}</code>"
        entries = []
        total_pages = 1

    await state.update_data(current_page=page, total_pages=total_pages)
    markup = build_life_tracker_report_keyboard(
        data,
        current_page=page,
        total_pages=total_pages,
        has_entries=bool(entries)
    )

    if isinstance(message_or_query, Message):
        await message_or_query.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    elif isinstance(message_or_query, CallbackQuery) and isinstance(message_or_query.message, Message):
        await message_or_query.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


@router.callback_query(F.data == "lt_reports")
async def open_reports_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await callback.answer("⛔ عدم دسترسی.", show_alert=True)
        return

    await state.clear()
    s_iso, e_iso, d_label = get_preset_date_range("today")
    initial_data = {
        "start_iso": s_iso,
        "end_iso": e_iso,
        "date_preset": "today",
        "date_label": d_label,
        "type_val": "all",
        "mode_val": "all",
        "current_page": 1
    }
    await state.update_data(**initial_data)
    await state.set_state(LifeTrackerReportState.viewing_report)
    await fetch_and_render_report(callback, state, page=1)
    await callback.answer()


@router.callback_query(F.data.startswith("lt_page:"))
async def change_page_handler(callback: CallbackQuery, state: FSMContext):
    target_page = int((callback.data or "").split(":", 1)[1])
    await fetch_and_render_report(callback, state, page=target_page)
    await callback.answer()


@router.callback_query(F.data == "lt_rep_refresh")
async def refresh_report_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    curr_page = data.get("current_page", 1)
    await fetch_and_render_report(callback, state, page=curr_page)
    await callback.answer("🔄 گزارش بروزرسانی شد.")


@router.callback_query(F.data == "lt_back_to_report")
async def back_to_report_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    curr_page = data.get("current_page", 1)
    await fetch_and_render_report(callback, state, page=curr_page)
    await callback.answer()


@router.callback_query(F.data == "lt_rep_close")
async def close_report_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("📊 گزارش روزمرگی بسته شد.")
    await callback.answer()


# --- Report Filter Handlers ---

@router.callback_query(F.data == "lt_rep_pick_date")
async def rep_pick_date_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📅 <b>بازه زمانی گزارش روزمرگی را انتخاب کنید:</b>",
            reply_markup=get_lt_report_date_range_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_rep_set_date:"))
async def rep_set_date_preset(callback: CallbackQuery, state: FSMContext):
    preset = (callback.data or "").split(":", 1)[1]
    s_iso, e_iso, d_label = get_preset_date_range(preset)
    await state.update_data(start_iso=s_iso, end_iso=e_iso, date_preset=preset, date_label=d_label)
    await fetch_and_render_report(callback, state, page=1)
    await callback.answer()


@router.callback_query(F.data == "lt_rep_custom_date")
async def rep_custom_date_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(LifeTrackerReportState.typing_custom_date_range)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📅 لطفاً بازه تاریخ دلخواه شمسی را ارسال کنید:\n\n"
            "▫️ <b>نمونه بازه:</b> <code>1405/05/01 تا 1405/05/15</code>\n"
            "▫️ <b>نمونه یک روز:</b> <code>1405/05/01</code>",
            reply_markup=get_lt_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(LifeTrackerReportState.typing_custom_date_range)
async def rep_process_custom_date(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    parsed = parse_custom_date_range(text)
    data = await state.get_data()
    prompt_id = data.get("last_prompt_id")

    if not parsed:
        err = await message.answer(
            "❌ فرمت بازه تاریخ نامعتبر است.\n"
            "لطفاً مانند <code>1405/05/01 تا 1405/05/15</code> وارد کنید:",
            parse_mode="HTML"
        )
        await register_error_message(state, err, user_msg=message)
        return

    s_iso, e_iso, d_label = parsed
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.update_data(start_iso=s_iso, end_iso=e_iso, date_preset="custom", date_label=d_label)
    await state.set_state(LifeTrackerReportState.viewing_report)
    await fetch_and_render_report(message, state, page=1)


@router.callback_query(F.data == "lt_rep_pick_type")
async def rep_pick_type_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🏷 <b>نوع فعالیت مورد نظر برای فیلتر را انتخاب کنید:</b>",
            reply_markup=get_lt_report_type_filter_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_rep_set_type:"))
async def rep_set_type_handler(callback: CallbackQuery, state: FSMContext):
    t_val = (callback.data or "").split(":", 1)[1]
    await state.update_data(type_val=t_val, mode_val="all")
    await fetch_and_render_report(callback, state, page=1)
    await callback.answer(f"فیلتر نوع: {t_val}")


@router.callback_query(F.data == "lt_rep_pick_mode")
async def rep_pick_mode_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    t_val = data.get("type_val", "all")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"🎭 <b>حالت مورد نظر برای «{t_val}» را انتخاب کنید:</b>",
            reply_markup=get_lt_report_mode_filter_keyboard(t_val),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_rep_set_mode:"))
async def rep_set_mode_handler(callback: CallbackQuery, state: FSMContext):
    m_val = (callback.data or "").split(":", 1)[1]
    await state.update_data(mode_val=m_val)
    await fetch_and_render_report(callback, state, page=1)
    await callback.answer(f"فیلتر حالت: {m_val}")


# ==========================================
# 🔍 RECORD INSPECT, EDIT & DELETE
# ==========================================

def render_entry_detail_text(entry: dict) -> str:
    name = entry.get("name", "بدون عنوان")
    t_val = entry.get("type", "نامشخص")
    t_em = TYPE_EMOJIS.get(t_val, "🏷")

    raw_d = entry.get("date_iso")
    if raw_d:
        parsed_d = parse_user_date_input(raw_d)
        d_str = parsed_d[1] if parsed_d else raw_d
    else:
        d_str = "تعیین نشده"

    modes = entry.get("modes", [])
    m_str = " | ".join([f"{MODE_EMOJIS.get(m, '✨')} {m}" for m in modes]) if modes else "بدون حالت (عادی)"
    notes = entry.get("notes") or "ندارد"

    return (
        "📄 <b>جزئیات کامل لاگ روزمرگی:</b>\n\n"
        f"🏷 <b>نوع:</b> {t_em} {t_val}\n"
        f"📌 <b>عنوان:</b> {name}\n"
        f"🎭 <b>حالت (Mode):</b> {m_str}\n"
        f"📅 <b>تاریخ ثبت:</b> {d_str}\n"
        f"📝 <b>یادداشت:</b> {notes}"
    )


@router.callback_query(F.data == "lt_rep_manage")
async def rep_manage_entries_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    entries = query_life_tracker_entries(
        start_date_iso=data.get("start_iso"),
        end_date_iso=data.get("end_iso"),
        type_val=data.get("type_val"),
        mode_val=data.get("mode_val")
    )
    if not entries:
        await callback.answer("⚠️ رکوردی برای نمایش وجود ندارد.", show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📋 <b>یکی از رکوردهای زیر را برای مشاهده جزئیات، ویرایش یا حذف انتخاب کنید:</b>",
            reply_markup=get_lt_entries_selector_keyboard(entries, page=1, page_size=PAGE_SIZE),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_sel_page:"))
async def selector_page_handler(callback: CallbackQuery, state: FSMContext):
    target_page = int((callback.data or "").split(":", 1)[1])
    data = await state.get_data()
    entries = query_life_tracker_entries(
        start_date_iso=data.get("start_iso"),
        end_date_iso=data.get("end_iso"),
        type_val=data.get("type_val"),
        mode_val=data.get("mode_val")
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=get_lt_entries_selector_keyboard(entries, page=target_page, page_size=PAGE_SIZE)
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_det:"))
async def entry_detail_handler(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    if isinstance(callback.message, Message):
        await state.update_data(detail_message_id=callback.message.message_id)

    entry = get_life_tracker_entry(page_id)
    if not entry:
        await callback.answer("⚠️ رکورد یافت نشد.", show_alert=True)
        return

    text = render_entry_detail_text(entry)
    markup = get_lt_entry_detail_keyboard(page_id, entry.get("url", ""))

    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    await callback.answer()


# 1. Delete Record
@router.callback_query(F.data.startswith("lt_confirm_del:"))
async def confirm_delete_handler(callback: CallbackQuery):
    page_id = (callback.data or "").split(":", 1)[1]
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "⚠️ <b>آیا از حذف این لاگ روزمرگی از نوشن اطمینان دارید؟</b>\n\n"
            "<i>این عملیات رکورد را در نوشن آرشیو می‌کند.</i>",
            reply_markup=get_lt_delete_confirm_keyboard(page_id),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_do_del:"))
async def do_delete_handler(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    success = archive_notion_page(page_id)
    if success:
        await callback.answer("✅ رکورد با موفقیت از نوشن حذف شد!", show_alert=True)
    else:
        await callback.answer("❌ خطا در حذف رکورد از نوشن.", show_alert=True)

    await fetch_and_render_report(callback, state, page=1)


# 2. Live In-Place Editor
async def show_edit_menu(event: Message | CallbackQuery, page_id: str, bot: Bot, state: FSMContext, alert_text: str | None = None):
    entry = get_life_tracker_entry(page_id)
    if not entry:
        if isinstance(event, CallbackQuery):
            await event.answer("⚠️ رکورد یافت نشد.", show_alert=True)
        return

    detail_summary = render_entry_detail_text(entry)
    text = (
        f"{detail_summary}\n\n"
        "👇 <b>برای ویرایش هر بخش، دکمه مربوطه را انتخاب کنید:</b>"
    )
    markup = get_lt_edit_fields_keyboard(page_id, entry.get("type", ""))

    data = await state.get_data()
    detail_msg_id = data.get("detail_message_id")

    if isinstance(event, CallbackQuery) and isinstance(event.message, Message):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
        if alert_text:
            await event.answer(alert_text)
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


@router.callback_query(F.data.startswith("lt_edit:"))
async def open_edit_menu_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    await show_edit_menu(callback, page_id, bot, state)


# A. Edit Name
@router.callback_query(F.data.startswith("lt_ed_name:"))
async def edit_entry_name_prompt(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    await state.set_state(LifeTrackerReportState.editing_name)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "✏️ لطفاً <b>عنوان جدید</b> را ارسال کنید:",
            reply_markup=get_lt_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(LifeTrackerReportState.editing_name)
async def process_edit_entry_name(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    data = await state.get_data()
    page_id = data.get("editing_page_id")

    if not text:
        err = await message.answer("❌ عنوان نمی‌تواند خالی باشد:")
        await register_error_message(state, err, user_msg=message)
        return

    update_notion_page_properties(page_id, {"Name": {"title": [{"text": {"content": text}}]}})
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(LifeTrackerReportState.viewing_report)
    await show_edit_menu(message, page_id, bot, state, alert_text="✅ عنوان به‌روزرسانی شد.")


# B. Edit Notes
@router.callback_query(F.data.startswith("lt_ed_notes:"))
async def edit_entry_notes_prompt(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    await state.set_state(LifeTrackerReportState.editing_notes)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📝 لطفاً <b>متن یادداشت جدید</b> را ارسال کنید (برای خالی کردن بنویسید <code>خالی</code>):",
            reply_markup=get_lt_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(LifeTrackerReportState.editing_notes)
async def process_edit_entry_notes(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    data = await state.get_data()
    page_id = data.get("editing_page_id")

    content = "" if text == "خالی" else text
    rich_text = [{"text": {"content": content}}] if content else []
    update_notion_page_properties(page_id, {"Notes": {"rich_text": rich_text}})

    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(LifeTrackerReportState.viewing_report)
    await show_edit_menu(message, page_id, bot, state, alert_text="✅ یادداشت به‌روزرسانی شد.")


# C. Edit Date
@router.callback_query(F.data.startswith("lt_ed_date:"))
async def edit_entry_date_prompt(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    await state.set_state(LifeTrackerReportState.editing_custom_date)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📅 تاریخ جدید را به صورت شمسی (مثلاً <code>1405/05/25</code>) ارسال کنید:",
            reply_markup=get_lt_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(LifeTrackerReportState.editing_custom_date)
async def process_edit_entry_date(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    parsed = parse_user_date_input(text)
    data = await state.get_data()
    page_id = data.get("editing_page_id")

    if not parsed:
        err = await message.answer("❌ تاریخ نامعتبر است:")
        await register_error_message(state, err, user_msg=message)
        return

    g_iso, _ = parsed
    update_notion_page_properties(page_id, {"Date_": {"date": {"start": g_iso}}})
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(LifeTrackerReportState.viewing_report)
    await show_edit_menu(message, page_id, bot, state, alert_text="✅ تاریخ به‌روزرسانی شد.")


# D. Edit Type
@router.callback_query(F.data.startswith("lt_ed_type:"))
async def edit_entry_type_menu(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🏷 <b>نوع جدید فعالیت را انتخاب کنید:</b>",
            reply_markup=get_lt_edit_type_keyboard(page_id),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("lt_set_ed_type:"))
async def set_edit_entry_type(callback: CallbackQuery, state: FSMContext, bot: Bot):
    parts = (callback.data or "").split(":", 2)
    page_id, new_type = parts[1], parts[2]
    
    props = {"Type": {"select": {"name": new_type}}}
    # Clear modes if new type does not support modes
    if new_type not in TYPE_MODE_MAPPING:
        props["Mode"] = {"multi_select": []}

    update_notion_page_properties(page_id, props)
    await show_edit_menu(callback, page_id, bot, state, alert_text=f"✅ نوع به '{new_type}' تغییر کرد.")


# E. Edit Modes
@router.callback_query(F.data.startswith("lt_ed_mode:"))
async def edit_entry_mode_menu(callback: CallbackQuery, state: FSMContext):
    page_id = (callback.data or "").split(":", 1)[1]
    await state.update_data(editing_page_id=page_id)
    entry