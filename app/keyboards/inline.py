from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="⏱ Add Time Entry", callback_data="btn_add_time")],
        [InlineKeyboardButton(text="ℹ️ Help & Info", callback_data="btn_help")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_satisfaction_keyboard() -> InlineKeyboardMarkup:
    options = ["عالی", "خوب", "متوسط", "بد", "داغون"]
    buttons = [[InlineKeyboardButton(text=opt, callback_data=f"sat_{opt}")] for opt in options]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_skip_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="⏩ Skip", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_action")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)