from datetime import datetime, timezone, timedelta, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.time_tracker_state import TimeTrackerCard
from app.keyboards.inline import (
    build_card_keyboard,
    get_person_keyboard,
    get_date_keyboard,
    get_time_picker_keyboard,
    get_satisfaction_keyboard
)
from app.services.notion_service import get_workspace_persons, add_time_tracker_entry
from app.config import ALLOWED_USERS

router = Router()

def is_user_allowed(user_id: int | None) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS if user_id else False

def render_card_text(data: dict) -> str:
    tz = timezone(timedelta(hours=3, minutes=30))
    now = datetime.now(tz)
    
    name = data.get("name", "وارد نشده ❌")
    person = data.get("person_name", "انتخاب نشده")
    d_label = data.get("date_label", f"امروز ({now.strftime('%Y-%m-%d')})")
    start = data.get("start_time", "--:--")
    end = data.get("end_time", "--:--")
    duration = data.get("duration", "محاسبه نشده")
    sat = data.get("satisfaction", "خوب")
    desc = data.get("description", "—")

    return (
        "📋 **فرم پیش‌نویس ثبت زمان کاری**\n\n"
        f"📌 **عنوان کار:** {name}\n"
        f"👤 **انجام‌دهنده:** {person}\n"
        f"📅 **تاریخ:** {d_label}\n"
        f"⏰ **بازه زمانی:** از `{start}` تا `{end}`\n"
        f"⏱ **مدت زمان محاسبه‌شده:** {duration} دقیقه\n"
        f"⭐ **میزان رضایت:** {sat}\n"
        f"📝 **توضیحات:** {desc}\n\n"
        "👇 *با دکمه‌های زیر فیلدها را تنظیم کنید و در نهایت دکمه ثبت را بزنید:*"
    )

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

@router.message(F.text == "⏱ ثبت زمان جدید (تایم‌ترکر)")
async def start_card_from_menu(message: Message, state: FSMContext):
    if not is_user_allowed(message.from_user.id if message.from_user else None):
        await message.answer("⛔ شما به این بخش دسترسی ندارید.")
        return

    await state.clear()
    tz = timezone(timedelta(hours=3, minutes=30))
    now = datetime.now(tz)
    
    # Default initial data
    initial_data = {
        "name": None,
        "person_id": None,
        "person_name": None,
        "date_offset": 0,
        "date_label": "امروز",
        "start_time": (now - timedelta(hours=1)).strftime("%H:00"),
        "end_time": now.strftime("%H:00"),
        "duration": 60,
        "satisfaction": "خوب",
        "description": ""
    }
    
    await state.update_data(**initial_data)
    await state.set_state(TimeTrackerCard.viewing_card)
    await message.answer(
        render_card_text(initial_data),
        reply_markup=build_card_keyboard(initial_data),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "back_to_card")
async def back_to_card_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(TimeTrackerCard.viewing_card)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data == "edit_name")
async def ask_task_name(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TimeTrackerCard.typing_name)
    if isinstance(callback.message, Message):
        await callback.message.answer("✏️ لطفاً **عنوان فعالیت / کار** را تایپ و ارسال کنید:")
    await callback.answer()

@router.message(TimeTrackerCard.typing_name)
async def set_task_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    await state.update_data(name=name)
    data = await state.get_data()
    await state.set_state(TimeTrackerCard.viewing_card)
    await message.answer(
        render_card_text(data),
        reply_markup=build_card_keyboard(data),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "pick_person")
async def pick_person_handler(callback: CallbackQuery):
    persons = get_workspace_persons()
    if not persons:
        await callback.answer("⚠️ کاربری در نوشن پیدا نشد!", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "👤 **انجام‌دهنده این فعالیت چه کسی است؟**",
            reply_markup=get_person_keyboard(persons),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("set_person:"))
async def set_person_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    person_id = parts[1]
    person_name = parts[2]
    await state.update_data(person_id=person_id, person_name=person_name)
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="Markdown"
        )
    await callback.answer(f"انجام‌دهنده: {person_name}")

@router.callback_query(F.data == "pick_date")
async def pick_date_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📅 **تاریخ ثبت این فعالیت را انتخاب کنید:**",
            reply_markup=get_date_keyboard(),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("set_date:"))
async def set_date_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    offset = int(parts[1])
    label = parts[2]
    await state.update_data(date_offset=offset, date_label=label)
    data = await state.get_data()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data.in_(["pick_start_time", "pick_end_time"]))
async def pick_time_handler(callback: CallbackQuery):
    target = "start" if callback.data == "pick_start_time" else "end"
    title = "ساعت شروع" if target == "start" else "ساعت پایان"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"⏰ **انتخاب {title}:**",
            reply_markup=get_time_picker_keyboard(target),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data.startswith("set_time:"))
async def set_time_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    target = parts[1]
    time_val = parts[2]
    
    if target == "start":
        await state.update_data(start_time=time_val)
    else:
        await state.update_data(end_time=time_val)
        
    data = await state.get_data()
    duration = calculate_duration(data.get("start_time"), data.get("end_time"))
    await state.update_data(duration=duration)
    data["duration"] = duration
    
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            render_card_text(data),
            reply_markup=build_card_keyboard(data),
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data == "pick_satisfaction")
async def pick_satisfaction_handler(callback: CallbackQuery):
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "⭐ **میزان رضایت خود را از این تایم کاری انتخاب کنید:**",
            reply_markup=get_satisfaction_keyboard(),
            parse_mode="Markdown"
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
            parse_mode="Markdown"
        )
    await callback.answer()

@router.callback_query(F.data == "edit_description")
async def ask_description_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TimeTrackerCard.typing_description)
    if isinstance(callback.message, Message):
        await callback.message.answer("📝 لطفاً **توضیحات یا یادداشت‌های تکمیلی** را بفرستید:")
    await callback.answer()

@router.message(TimeTrackerCard.typing_description)
async def set_description_handler(message: Message, state: FSMContext):
    desc = (message.text or "").strip()
    await state.update_data(description=desc)
    data = await state.get_data()
    await state.set_state(TimeTrackerCard.viewing_card)
    await message.answer(
        render_card_text(data),
        reply_markup=build_card_keyboard(data),
        parse_mode="Markdown"
    )

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
        
    await state.clear()
    if isinstance(callback.message, Message):
        status_msg = await callback.message.answer("⏳ در حال ثبت اطلاعات در نوشن...")
        
        try:
            tz = timezone(timedelta(hours=3, minutes=30))
            target_date = date.today() - timedelta(days=data.get("date_offset", 0))
            
            start_str = data.get("start_time", "09:00")
            end_str = data.get("end_time", "10:00")
            
            start_dt = datetime.strptime(f"{target_date} {start_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            end_dt = datetime.strptime(f"{target_date} {end_str}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
            
            res = add_time_tracker_entry(
                name=name,
                start_iso=start_dt.isoformat(),
                end_iso=end_dt.isoformat(),
                duration=data.get("duration", 60),
                satisfaction=data.get("satisfaction", "خوب"),
                person_id=data.get("person_id"),
                description=data.get("description", "")
            )
            
            page_url = res.get("url", "#")
            success_text = (
                "✅ **زمان کاری با موفقیت در نوشن ثبت شد!**\n\n"
                f"📌 **عنوان:** {name}\n"
                f"👤 **انجام‌دهنده:** {data.get('person_name', 'تعیین نشده')}\n"
                f"📅 **تاریخ:** {data.get('date_label')}\n"
                f"⏰ **ساعت:** `{start_str}` تا `{end_str}` ({data.get('duration')} دقیقه)\n"
                f"⭐ **رضایت:** {data.get('satisfaction')}\n\n"
                f"[🔗 مشاهده در نوشن]({page_url})"
            )
            await status_msg.edit_text(
                success_text,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            await status_msg.edit_text(f"❌ خطا در ثبت نوشن: {e}")
            
    await callback.answer()