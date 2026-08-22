from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BTN_ADD_TIME = "⏱ ثبت زمان جدید"
BTN_REPORTS = "📊 گزارش و کارکردها"
BTN_HELP = "ℹ️ راهنما"

def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text=BTN_ADD_TIME)],
        [KeyboardButton(text=BTN_REPORTS), KeyboardButton(text=BTN_HELP)]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)