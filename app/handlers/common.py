from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from aiogram.fsm.context import FSMContext
from app.config import ALLOWED_USERS

router = Router()


def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏱ ثبت زمان جدید")],
            [KeyboardButton(text="ℹ️ راهنما")],
        ],
        resize_keyboard=True,
    )

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
        f"سلام {first_name}، به ربات **نوشن‌یار** خوش اومدی! 🌿\n\n"
        "برای ثبت فعالیت کاری، از منوی پایین گزینه **⏱ ثبت زمان جدید** رو انتخاب کن."
    )
    await message.answer(welcome_text, reply_markup=get_main_reply_keyboard(), parse_mode="Markdown")

@router.message(F.text == "ℹ️ راهنما")
@router.message(Command("help"))
async def help_handler(message: Message) -> None:
    text = (
        "💡 **راهنمای استفاده از نوشن‌یار:**\n\n"
        "۱. روی **⏱ ثبت زمان جدید** بزنید.\n"
        "۲. فرم پیش‌نویس باز می‌شود؛ فیلدهای عنوان، ساعت، انجام‌دهنده و... را با دکمه‌ها تکمیل کنید.\n"
        "۳. دکمه **✅ ثبت در نوشن** را بزنید تا مستقیماً در دیتابیس ثبت شود."
    )
    await message.answer(text, parse_mode="Markdown")