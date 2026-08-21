import re
from datetime import datetime, timezone, timedelta, date
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.time_tracker_state import TimeTrackerCard
from app.keyboards.inline import (
    build_card_keyboard,
    get_person_keyboard,
    get_date_keyboard,
    get_time_picker_keyboard,
    get_satisfaction_keyboard,
    get_description_keyboard,
    get_back_cancel_keyboard,
    SATISFACTION_EMOJIS
)
from app.services.notion_service import get_workspace_persons, add_time_tracker_entry
from app.config import ALLOWED_USERS

router = Router()

def is_user_allowed(user_id: int | None) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS if user_id else False

def render_card_text(data: dict) -> str:
    name = data.get("name") or "وارد نشده ❌"
    person = data.get("person_name") or "تعیین نشده"
    d_label = data.get("date_label", "امروز")
    start = data.get("start_time") or "—"
    end = data.get("end_time") or "—"
    duration = data.get("duration", 0)
    
    sat = data.get("satisfaction")
    if sat:
        sat_emoji = SATISFACTION_EMOJIS.get(sat, "⭐")
        sat_text = f"{sat_emoji} {sat}"
    else:
        sat_text = "تعیین نشده (اختیاری)"
        
    desc = data.get("description") or "—"

    return (
        "📋 <b>فرم پیش‌نویس ثبت زمان کاری</b>\n\n"
        f"📌 <b>عنوان کار:</b> {name}\n"
        f"👤 <b>انجام‌دهنده:</b> {person}\n"
        f"📅 <b>تاریخ:</b> {d_label}\n"
        f"⏰ <b>بازه زمانی:</b> از <code>{start}</code> تا <code>{end}</code>\n"
        f"⏱ <b>مدت زمان:</b> {duration} دقیقه\n"
        f"⭐ <b>میزان رضایت:</b> {sat_text}\n"
        f"📝 <b>توضیحات:</b> {desc}\n\n"
        "👇 <i>با دکمه‌های زیر فیلدها را تنظیم کنید و در نهایت دکمه ثبت را بزنید:</i>"
    )

def is_time_order_valid(start_time: str | None, end_time: str | None) -> bool:
    """Checks if start_time is strictly before end_time."""
    if not start_time or not end_time:
        return True
    fmt = "%H:%M"
    try:
        t1 = datetime.strptime(start_time, fmt)
        t2 = datetime.strptime(end_time, fmt)
        return t2 > t1
    except Exception:
        return False

def calculate_duration(start_time: str | None, end_time: str | None) -> int:
    if not start_time or not end_time:
        return 0
    try:
        fmt = "%H:%M"
        t1 = datetime.strptime(start_time, fmt)
        t2 = datetime.strptime(end_time, fmt)
        diff = (t2 - t1).total_seconds() / 60
        return int(diff) if diff > 0 else 0
    except Exception:
        return 0

async def cleanup_prompt_messages(bot: Bot, chat_id: int, state: FSMContext, user_msg: Message | None = None):
    data = await state.get_data()
    prompt_id = data.get("last_prompt_id")
    if prompt_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=prompt_id)
        except Exception:
            pass
    if user_msg:
        try:
            await user_msg.delete()
        except Exception:
            pass

async def update_main_card(bot: Bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    card_msg_id = data.get("card_message_id")
    if card_msg_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=card_msg_id,
                text=render_card_text(data),
                reply_markup=build_card_keyboard(data),
                parse_mode="HTML"
            )
        except Exception:
            pass

@router.message(F.text.contains("ثبت زمان"))
async def start_card_from_menu(message: Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id if message.from_user else None):
        await message.answer("⛔ شما به این بخش دسترسی ندارید.")
        return

    await state.clear()
    tz = timezone(timedelta(hours=3, minutes=30))
    now = datetime.now(tz)
    today_iso = now.date().isoformat()
    
    initial_data = {
        "name": None,
        "person_id": None,
        "person_name": None,
        "date_iso": today_iso,
        "date_label": f"امروز ({today_iso})",
        "start_time": None,
        "end_time": None,
        "duration": 0,
        "satisfaction": None,
        "description": ""
    }
    
    card_msg = await message.answer(
        render_card_text(initial_data),
        reply_markup=build_card_keyboard(initial_data),
        parse_mode="HTML"
    )
    initial_data["card_message_id"] = card_msg.message_id
    await state.update_data(**initial_data)
    await state.set_state(TimeTrackerCard.viewing_card)

@router.callback_query(F.data == "back_to_card")
async def back_to_card_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if isinstance(callback.message, Message):
        await cleanup_prompt_messages(bot, callback.message.chat.id, state)
        data = await state.get_data()
        await state.set_state(TimeTrackerCard.viewing_card)
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer()

# --- Title Handler with Length Validation ---
@router.callback_query(F.data == "edit_name")
async def ask_task_name(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TimeTrackerCard.typing_name)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "✏️ لطفاً <b>عنوان فعالیت / کار</b> را ارسال کنید (حداکثر ۲۰۰۰ کاراکتر):",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()

@router.message(TimeTrackerCard.typing_name)
async def set_task_name(message: Message, state: FSMContext, bot: Bot):
    name = (message.text or "").strip()
    if not name:
        await message.answer("❌ عنوان نمی‌تواند خالی باشد. لطفاً متنی وارد کنید:")
        return
    if len(name) > 2000:
        await message.answer("❌ عنوان بسیار طولانی است (باید کمتر از ۲۰۰۰ کاراکتر باشد):")
        return

    await state.update_data(name=name)
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(TimeTrackerCard.viewing_card)
    await update_main_card(bot, message.chat.id, state)

# --- Person Handlers ---
@router.callback_query(F.data == "pick_person")
async def pick_person_handler(callback: CallbackQuery):
    persons = get_workspace_persons()
    if not persons:
        await callback.answer("⚠️ کاربری در ورک‌اسپیس نوشن یافت نشد!", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "👤 <b>انجام‌دهنده این فعالیت را انتخاب کنید:</b>",
            reply_markup=get_person_keyboard(persons),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("set_person:"))
async def set_person_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    person_id, person_name = parts[1], parts[2]
    await state.update_data(person_id=person_id, person_name=person_name)
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer(f"انجام‌دهنده: {person_name}")

@router.callback_query(F.data == "clear_person")
async def clear_person_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(person_id=None, person_name=None)
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer("انجام‌دهنده پاک شد.")

# --- Date Handlers ---
@router.callback_query(F.data == "pick_date")
async def pick_date_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📅 <b>تاریخ ثبت این فعالیت را انتخاب کنید:</b>",
            reply_markup=get_date_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("set_date_preset:"))
async def set_date_preset_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    offset = int(parts[1])
    label_text = parts[2]
    
    tz = timezone(timedelta(hours=3, minutes=30))
    target_date = datetime.now(tz).date() - timedelta(days=offset)
    iso_date = target_date.isoformat()
    
    await state.update_data(date_iso=iso_date, date_label=f"{label_text} ({iso_date})")
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "enter_custom_date")
async def enter_custom_date_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TimeTrackerCard.typing_custom_date)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📅 تاریخ مورد نظر را به فرمت <b>YYYY-MM-DD</b> (مثلاً <code>2026-08-15</code>) ارسال کنید:",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()

@router.message(TimeTrackerCard.typing_custom_date)
async def process_custom_date(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if not match:
        await message.answer("❌ فرمت نامعتبر است. لطفاً به صورت <code>2026-08-15</code> وارد کنید:", parse_mode="HTML")
        return

    y, m, d = match.groups()
    iso_date = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    await state.update_data(date_iso=iso_date, date_label=iso_date)
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(TimeTrackerCard.viewing_card)
    await update_main_card(bot, message.chat.id, state)

# --- Time Handlers with Order Validation ---
@router.callback_query(F.data.in_(["pick_start_time", "pick_end_time"]))
async def pick_time_handler(callback: CallbackQuery):
    target = "start" if callback.data == "pick_start_time" else "end"
    title = "ساعت شروع" if target == "start" else "ساعت پایان"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"⏰ <b>انتخاب {title}:</b>",
            reply_markup=get_time_picker_keyboard(target),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("set_time:"))
async def set_time_preset_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    target, time_val = parts[1], parts[2]
    data = await state.get_data()
    
    # Validation: Start must be before End
    if target == "start":
        if data.get("end_time") and not is_time_order_valid(time_val, data.get("end_time")):
            await callback.answer("⚠️ ساعت شروع باید قبل از ساعت پایان باشد!", show_alert=True)
            return
        await state.update_data(start_time=time_val)
    else:
        if data.get("start_time") and not is_time_order_valid(data.get("start_time"), time_val):
            await callback.answer("⚠️ ساعت پایان باید بعد از ساعت شروع باشد!", show_alert=True)
            return
        await state.update_data(end_time=time_val)
        
    updated_data = await state.get_data()
    dur = calculate_duration(updated_data.get("start_time"), updated_data.get("end_time"))
    if dur > 0:
        await state.update_data(duration=dur)
        updated_data["duration"] = dur
    
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(updated_data),
            reply_markup=build_card_keyboard(updated_data),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("enter_custom_time:"))
async def enter_custom_time_prompt(callback: CallbackQuery, state: FSMContext):
    target = (callback.data or "").split(":")[1]
    await state.update_data(custom_time_target=target)
    await state.set_state(TimeTrackerCard.typing_custom_time)
    
    target_name = "شروع" if target == "start" else "پایان"
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            f"⏰ ساعت <b>{target_name}</b> را به صورت <code>HH:MM</code> (مثلاً <code>22:27</code>) ارسال کنید:",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()

@router.message(TimeTrackerCard.typing_custom_time)
async def process_custom_time(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    match = re.search(r"^(\d{1,2})[:.](\d{1,2})$", text)
    if not match:
        await message.answer("❌ فرمت نامعتبر است. لطفاً مثل <code>22:27</code> یا <code>08:15</code> وارد کنید:", parse_mode="HTML")
        return

    h, m = int(match.group(1)), int(match.group(2))
    if not (0 <= h <= 23 and 0 <= m <= 59):
        await message.answer("❌ ساعت یا دقیقه خارج از محدوده است.", parse_mode="HTML")
        return

    formatted_time = f"{h:02d}:{m:02d}"
    data = await state.get_data()
    target = data.get("custom_time_target", "start")
    
    # Validation: Time Order
    if target == "start":
        if data.get("end_time") and not is_time_order_valid(formatted_time, data.get("end_time")):
            await message.answer("⚠️ ساعت شروع واردشده باید قبل از ساعت پایان باشد. لطفاً دوباره وارد کنید:")
            return
        await state.update_data(start_time=formatted_time)
    else:
        if data.get("start_time") and not is_time_order_valid(data.get("start_time"), formatted_time):
            await message.answer("⚠️ ساعت پایان واردشده باید بعد از ساعت شروع باشد. لطفاً دوباره وارد کنید:")
            return
        await state.update_data(end_time=formatted_time)

    updated_data = await state.get_data()
    dur = calculate_duration(updated_data.get("start_time"), updated_data.get("end_time"))
    if dur > 0:
        await state.update_data(duration=dur)

    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(TimeTrackerCard.viewing_card)
    await update_main_card(bot, message.chat.id, state)

@router.callback_query(F.data == "clear_times")
async def clear_times_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(start_time=None, end_time=None)
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer("ساعت‌های شروع و پایان پاک شدند.")

# --- Manual Duration with Range Validation (1 to 1440 mins) ---
@router.callback_query(F.data == "edit_duration")
async def edit_duration_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TimeTrackerCard.typing_custom_duration)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "⏱ لطفاً <b>مدت زمان کار را به دقیقه</b> وارد کنید (بین ۱ تا ۱۴۴۰ دقیقه / ۲۴ ساعت):",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()

@router.message(TimeTrackerCard.typing_custom_duration)
async def process_custom_duration(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❌ لطفاً فقط عدد وارد کنید (مثلاً <code>45</code>):", parse_mode="HTML")
        return

    dur_val = int(text)
    if not (1 <= dur_val <= 1440):
        await message.answer("❌ مدت زمان باید بین <b>۱ تا ۱۴۴۰ دقیقه</b> (حداکثر ۲۴ ساعت) باشد:", parse_mode="HTML")
        return

    await state.update_data(duration=dur_val)
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(TimeTrackerCard.viewing_card)
    await update_main_card(bot, message.chat.id, state)

# --- Satisfaction Handlers ---
@router.callback_query(F.data == "pick_satisfaction")
async def pick_satisfaction_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "⭐ <b>میزان رضایت خود را انتخاب کنید:</b>",
            reply_markup=get_satisfaction_keyboard(),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("set_sat:"))
async def set_sat_handler(callback: CallbackQuery, state: FSMContext):
    sat = (callback.data or "").split(":")[1]
    await state.update_data(satisfaction=sat)
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer()

@router.callback_query(F.data == "clear_sat")
async def clear_satisfaction_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(satisfaction=None)
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="HTML"
        )
    await callback.answer("میزان رضایت پاک شد.")

# --- Description Handlers with Length Validation ---
@router.callback_query(F.data == "edit_description")
async def ask_description_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TimeTrackerCard.typing_description)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "📝 لطفاً <b>توضیحات یا یادداشت‌های تکمیلی</b> را بفرستید (حداکثر ۲۰۰۰ کاراکتر):",
            reply_markup=get_description_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()

@router.message(TimeTrackerCard.typing_description)
async def set_description_handler(message: Message, state: FSMContext, bot: Bot):
    desc = (message.text or "").strip()
    if len(desc) > 2000:
        await message.answer("❌ متن توضیحات بیش از حد طولانی است (باید کمتر از ۲۰۰۰ کاراکتر باشد):")
        return

    await state.update_data(description=desc)
    await cleanup_prompt_messages(bot, message.chat.id, state, user_msg=message)
    await state.set_state(TimeTrackerCard.viewing_card)
    await update_main_card(bot, message.chat.id, state)

@router.callback_query(F.data == "clear_description")
async def clear_description_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.update_data(description="")
    if isinstance(callback.message, Message):
        await cleanup_prompt_messages(bot, callback.message.chat.id, state)
        data = await state.get_data()
        await state.set_state(TimeTrackerCard.viewing_card)
        await update_main_card(bot, callback.message.chat.id, state)
    await callback.answer("توضیحات پاک شد.")

# --- Card Submission & Final Validation ---
@router.callback_query(F.data == "cancel_card")
async def cancel_card_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("❌ فرم ثبت زمان لغو شد.")
    await callback.answer()

@router.callback_query(F.data == "submit_card")
async def submit_card_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    name = data.get("name")
    
    if not name:
        await callback.answer("⚠️ لطفاً ابتدا عنوان فعالیت را وارد کنید!", show_alert=True)
        return
        
    start_str = data.get("start_time")
    end_str = data.get("end_time")
    if start_str and end_str and not is_time_order_valid(start_str, end_str):
        await callback.answer("⚠️ ساعت شروع باید قبل از ساعت پایان باشد!", show_alert=True)
        return

    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("⏳ در حال ثبت اطلاعات در نوشن...")
        
        try:
            tz = timezone(timedelta(hours=3, minutes=30))
            date_iso = data.get("date_iso") or date.today().isoformat()
            
            if start_str and end_str:
                start_dt = datetime.strptime(f"{date_iso} {start_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
                end_dt = datetime.strptime(f"{date_iso} {end_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
                start_payload = start_dt.isoformat()
                end_payload = end_dt.isoformat()
            elif start_str:
                start_dt = datetime.strptime(f"{date_iso} {start_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
                start_payload = start_dt.isoformat()
                end_payload = None
            else:
                start_payload = date_iso
                end_payload = None
            
            sat = data.get("satisfaction")
            res = add_time_tracker_entry(
                name=name,
                start_date_str=start_payload,
                end_date_str=end_payload,
                duration=data.get("duration", 0),
                satisfaction=sat,
                person_id=data.get("person_id"),
                description=data.get("description", "")
            )
            
            page_url = res.get("url", "#") if isinstance(res, dict) else "#"
            sat_text = f"{SATISFACTION_EMOJIS.get(sat, '⭐')} {sat}" if sat else "تعیین نشده"
            
            success_text = (
                "✅ <b>زمان کاری با موفقیت در نوشن ثبت شد!</b>\n\n"
                f"📌 <b>عنوان:</b> {name}\n"
                f"👤 <b>انجام‌دهنده:</b> {data.get('person_name', 'تعیین نشده')}\n"
                f"📅 <b>تاریخ:</b> {data.get('date_label')}\n"
                f"⏱ <b>مدت زمان:</b> {data.get('duration', 0)} دقیقه\n"
                f"⭐ <b>میزان رضایت:</b> {sat_text}\n\n"
                f'<a href="{page_url}">🔗 مشاهده در نوشن</a>'
            )
            await callback.message.edit_text(
                success_text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
        except Exception as e:
            await callback.message.edit_text(f"❌ خطا در ثبت نوشن:\n<code>{e}</code>", parse_mode="HTML")
            
    await callback.answer()