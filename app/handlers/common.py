from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from app.config import ALLOWED_USERS
from app.keyboards.reply import get_main_reply_keyboard

router = Router()

def is_user_allowed(user_id: int | None) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS if user_id else False

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_id = message.from_user.id if message.from_user else None
    if not is_user_allowed(user_id):
        await message.answer("⛔ شما اجازه دسترسی به این ربات را ندارید.")
        return

    first_name = message.from_user.first_name if message.from_user else "عزیز"
    welcome_text = (
        f"سلام <b>{first_name}</b>، به ربات <b>نوشن‌یار</b> خوش اومدی! 🌿\n\n"
        "برای ثبت فعالیت کاری، از منوی پایین گزینه <b>⏱ ثبت زمان جدید</b> رو انتخاب کن."
    )
    await message.answer(welcome_text, reply_markup=get_main_reply_keyboard(), parse_mode="HTML")

@router.message(F.text == "ℹ️ راهنما")
@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    text = (
        "💡 <b>راهنمای استفاده از نوشن‌یار:</b>\n\n"
        "۱. روی <b>⏱ ثبت زمان جدید</b> بزنید.\n"
        "۲. فرم پیش‌نویس باز می‌شود؛ فیلدهای عنوان، ساعت، انجام‌دهنده و... را با دکمه‌ها تکمیل کنید.\n"
        "۳. دکمه <b>✅ ثبت در نوشن</b> را بزنید تا مستقیماً در دیتابیس ثبت شود."
    )
    await message.answer(text, parse_mode="HTML")