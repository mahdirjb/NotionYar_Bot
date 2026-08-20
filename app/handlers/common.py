from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.config import ALLOWED_USERS
from app.keyboards.inline import get_main_menu_keyboard

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
        await message.answer("⛔ Access Denied: You are not authorized to use this bot.")
        return

    first_name = message.from_user.first_name if message.from_user else "there"
    await message.answer(
        f"Hello {first_name}!\nWelcome to **NotionYar Bot**.\nChoose an option below:",
        reply_markup=get_main_menu_keyboard(),
        parse_mode="Markdown"
    )

@router.message(Command("cancel"))
async def cancel_command_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Action cancelled.", reply_markup=get_main_menu_keyboard())

@router.callback_query(F.data == "cancel_action")
async def cancel_callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Action cancelled.", reply_markup=get_main_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "btn_help")
async def help_callback_handler(callback: CallbackQuery) -> None:
    help_text = (
        "ℹ️ **NotionYar Bot Help**\n\n"
        "• Click *Add Time Entry* to log your work session directly to Notion.\n"
        "• Use /cancel at any time to abort the current form."
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(help_text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    await callback.answer()