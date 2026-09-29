from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from app.config import WEBAPP_URL
from app.services.auth_service import has_permission, PERM_ADD_TIME, PERM_VIEW_REPORTS, PERM_ADMIN

BTN_MINIAPP = "📱 مینی‌اپ نوشن‌یار (ثبت سریع)"
BTN_ADD_TIME = "⏱ ثبت زمان جدید"
BTN_REPORTS = "📊 گزارش و کارکردها"
BTN_HABITS = "🎯 عادات روزانه"
BTN_LIFE_TRACKER = "🌱 لاگ روزمرگی"
BTN_ADMIN = "⚙️ پنل مدیریت"
BTN_HELP = "ℹ️ راهنما"

def get_main_reply_keyboard(user_id: int | None = None) -> ReplyKeyboardMarkup:
    """
    Dynamically generates the reply keyboard based on user permissions.
    """
    keyboard = []

    # Row 0: Telegram Mini App Button (Top Priority if WEBAPP_URL configured)
    if WEBAPP_URL:
        keyboard.append([
            KeyboardButton(text=BTN_MINIAPP, web_app=WebAppInfo(url=WEBAPP_URL))
        ])

    # Row 1: Add time button (only if user has add_time permission)
    if has_permission(user_id, PERM_ADD_TIME):
        keyboard.append([KeyboardButton(text=BTN_ADD_TIME)])

    # Row 2: Reports button (if permitted) + Help button
    row_2 = []
    if has_permission(user_id, PERM_VIEW_REPORTS):
        row_2.append(KeyboardButton(text=BTN_REPORTS))
    row_2.append(KeyboardButton(text=BTN_HELP))
    keyboard.append(row_2)

    # Row 3 & 4: Habits, Life Tracker & Admin (Exclusive for Admins)
    if has_permission(user_id, PERM_ADMIN):
        keyboard.append([
            KeyboardButton(text=BTN_HABITS),
            KeyboardButton(text=BTN_LIFE_TRACKER)
        ])
        keyboard.append([
            KeyboardButton(text=BTN_ADMIN)
        ])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)