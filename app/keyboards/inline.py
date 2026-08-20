from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any, List

SATISFACTION_EMOJIS = {
    "عالی": "🤩",
    "خوب": "😊",
    "متوسط": "😐",
    "بد": "🙁",
    "داغون": "😫"
}

def build_card_keyboard(data: Dict[str, Any]) -> InlineKeyboardMarkup:
    name_label = "✏️ عنوان: " + (data.get("name") or "وارد نشده ❌")
    person_label = "👤 انجام‌دهنده: " + (data.get("person_name") or "انتخاب کنید")
    date_label = "📅 تاریخ: " + (data.get("date_label") or "امروز")
    
    start_label = "⏰ شروع: " + (data.get("start_time") or "—")
    end_label = "⏰ پایان: " + (data.get("end_time") or "—")
    
    dur = data.get("duration", 0)
    dur_label = f"⏱ مدت: {dur} دقیقه (دستی/محاسبه)"
    
    sat = data.get("satisfaction", "خوب")
    sat_emoji = SATISFACTION_EMOJIS.get(sat, "⭐")
    sat_label = f"{sat_emoji} رضایت: {sat}"
    
    desc_label = "📝 توضیحات: " + ("ثبت شده ✅" if data.get("description") else "اختیاری")

    buttons = [
        [InlineKeyboardButton(text=name_label, callback_data="edit_name")],
        [InlineKeyboardButton(text=person_label, callback_data="pick_person")],
        [InlineKeyboardButton(text=date_label, callback_data="pick_date")],
        [
            InlineKeyboardButton(text=start_label, callback_data="pick_start_time"),
            InlineKeyboardButton(text=end_label, callback_data="pick_end_time")
        ],
        [InlineKeyboardButton(text=dur_label, callback_data="edit_duration")],
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
            InlineKeyboardButton(text="امروز", callback_data="set_date_preset:0:امروز"),
            InlineKeyboardButton(text="دیروز", callback_data="set_date_preset:1:دیروز"),
            InlineKeyboardButton(text="پریروز", callback_data="set_date_preset:2:پریروز")
        ],
        [InlineKeyboardButton(text="✍️ ورود تاریخ دلخواه", callback_data="enter_custom_date")],
        [InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_time_picker_keyboard(target: str) -> InlineKeyboardMarkup:
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
        
    rows.append([InlineKeyboardButton(text="✍️ تایپ ساعت دلخواه (مثلاً 22:27)", callback_data=f"enter_custom_time:{target}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_satisfaction_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for opt, emoji in SATISFACTION_EMOJIS.items():
        buttons.append([InlineKeyboardButton(text=f"{emoji} {opt}", callback_data=f"set_sat:{opt}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_cancel_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="🔙 انصراف و بازگشت به فرم", callback_data="back_to_card")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)