from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from app.services.auth_service import is_user_registered, get_user_role
from app.keyboards.reply import get_main_reply_keyboard

router = Router()

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id if message.from_user else None

    if not is_user_registered(user_id):
        await message.answer("⛔ شما اجازه دسترسی به این ربات را ندارید.")
        return

    first_name = message.from_user.first_name if message.from_user else "عزیز"
    role = get_user_role(user_id) or "کاربر"
    role_badges = {
        "admin": "👑 مدیر کل",
        "manager": "💼 مدیر تیم",
        "member": "👤 عضو تیم",
        "guest": "🌿 مهمان"
    }
    badge = role_badges.get(role, "👤 کاربر")

    welcome_text = (
        f"سلام <b>{first_name}</b>، به ربات <b>نوشن‌یار</b> خوش اومدی! 🌿\n"
        f"🏷 <b>سطح دسترسی شما:</b> <code>{badge}</code>\n\n"
        "برای شروع از گزینه‌های منوی پایین استفاده کن."
    )
    await message.answer(
        welcome_text,
        reply_markup=get_main_reply_keyboard(user_id),
        parse_mode="HTML"
    )

@router.message(F.text == "ℹ️ راهنما")
@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_user_registered(user_id):
        await message.answer("⛔ شما اجازه دسترسی به این ربات را ندارید.")
        return

    text = (
        "💡 <b>راهنمای استفاده از نوشن‌یار:</b>\n\n"
        "۱. <b>⏱ ثبت زمان جدید:</b> برای ثبت لاگ کاری و تسک‌ها در دیتابیس نوشن.\n"
        "۲. <b>📊 گزارش و کارکردها:</b> مشاهده آمار ساعات کاری، فیلتر بازه زمانی/شخص، ویرایش و حذف رکوردها.\n"
        "۳. در صورت بروز هرگونه خطا یا نیاز به پشتیبانی با ادمین در ارتباط باشید."
    )
    await message.answer(text, parse_mode="HTML")