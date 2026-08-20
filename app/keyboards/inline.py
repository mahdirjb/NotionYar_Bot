from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any, List

def build_card_keyboard(data: Dict[str, Any]) -> InlineKeyboardMarkup:
    """
    Builds the interactive dashboard card keyboard.
    """
    name_label = "✏️ عنوان: " + (data.get("name") or "وارد نشده ❌")
    person_label = "👤 انجام‌دهنده: " + (data.get("person_name") or "انتخاب کنید")
    date_label = "📅 تاریخ: " + (data.get("date_label") or "امروز")
    start_label = "⏰ شروع: " + (data.get("start_time") or "تنظیم نشده")
    end_label = "⏰ پایان: " + (data.get("end_time") or "تنظیم نشده")
    sat_label = "⭐ رضایت: " + (data.get("satisfaction") or "خوب")
    desc_label = "📝 توضیحات: " + ("ثبت شده ✅" if data.get("description") else "اختیاری")

    buttons = [
        [InlineKeyboardButton(text=name_label, callback_data="edit_name")],
        [InlineKeyboardButton(text=person_label, callback_data="pick_person")],
        [InlineKeyboardButton(text=date_label, callback_data="pick_date")],
        [
            InlineKeyboardButton(text=start_label, callback_data="pick_start_time"),
            InlineKeyboardButton(text=end_label, callback_data="pick_end_time")
        ],
        [InlineKeyboardButton(text=sat_label, callback_data="pick_satisfaction")],
        [InlineKeyboardButton(text=desc_label, callback_data="edit_description")],
        [
            InlineKeyboardButton(text="✅ ثبت در نوشن", callback_data="submit_card"),
            InlineKeyboardButton(text="❌ انصراف", callback_data="cancel_card")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_person_keyboard(persons: List[Dict[str, str]]) -> InlineKeyboardMarkup:
    buttons = []
    for p in persons:
        buttons.append([InlineKeyboardButton(text=f"👤 {p['name']}", callback_data=f"set_person:{p['id']}:{p['name']}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_date_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="امروز", callback_data="set_date:0:امروز"),
            InlineKeyboardButton(text="دیروز", callback_data="set_date:1:دیروز"),
            InlineKeyboardButton(text="پریروز", callback_data="set_date:2:پریروز")
        ],
        [InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_time_picker_keyboard(target: str) -> InlineKeyboardMarkup:
    """
    Time presets picker for start or end time.
    """
    hours = ["08:00", "09:00", "10:00", "11:00", "12:00", "13:00",
             "14:00", "15:00", "16:00", "17:00", "18:00", "19:00",
             "20:00", "21:00", "22:00", "23:00"]
    
    rows = []
    current_row = []
    for h in hours:
        current_row.append(InlineKeyboardButton(text=h, callback_data=f"set_time:{target}:{h}"))
        if len(current_row) == 4:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
        
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_satisfaction_keyboard() -> InlineKeyboardMarkup:
    options = ["عالی", "خوب", "متوسط", "بد", "داغون"]
    buttons = [[InlineKeyboardButton(text=f"⭐ {opt}", callback_data=f"set_sat:{opt}")] for opt in options]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)