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
    person_label = "👤 انجام‌دهنده: " + (data.get("person_name") or "تعیین نشده")
    date_label = "📅 تاریخ: " + (data.get("date_label") or "امروز")
    
    start_label = "⏰ شروع: " + (data.get("start_time") or "—")
    end_label = "⏰ پایان: " + (data.get("end_time") or "—")
    
    manual_dur = data.get("manual_duration")
    if manual_dur is not None:
        dur_label = f"⏱ مدت: {manual_dur} دقیقه"
    else:
        dur_label = "⏱ مدت: تعیین نشده"
    
    sat = data.get("satisfaction")
    if sat:
        sat_emoji = SATISFACTION_EMOJIS.get(sat, "⭐")
        sat_label = f"{sat_emoji} رضایت: {sat}"
    else:
        sat_label = "⭐ رضایت: تعیین نشده"
        
    desc_label = "📝 توضیحات: " + ("ثبت شده ✅" if data.get("description") else "—")

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
    buttons.append([InlineKeyboardButton(text="🗑 پاک کردن انجام‌دهنده", callback_data="clear_person")])
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
    rows.append([InlineKeyboardButton(text="🗑 پاک کردن بازه زمانی", callback_data="clear_times")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def get_satisfaction_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for opt, emoji in SATISFACTION_EMOJIS.items():
        buttons.append([InlineKeyboardButton(text=f"{emoji} {opt}", callback_data=f"set_sat:{opt}")])
    buttons.append([InlineKeyboardButton(text="🗑 بدون انتخاب (حذف رضایت)", callback_data="clear_sat")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="back_to_card")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_duration_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🗑 پاک کردن مدت زمان", callback_data="clear_duration")],
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="back_to_card")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_description_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="🗑 پاک کردن توضیحات", callback_data="clear_description")],
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="back_to_card")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_back_cancel_keyboard() -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text="🔙 انصراف و بازگشت به فرم", callback_data="back_to_card")]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_report_keyboard(data: dict) -> InlineKeyboardMarkup:
    """
    Main interactive controls for the report message.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="📅 تغییر بازه زمانی", callback_data="rep_pick_date"),
            InlineKeyboardButton(text="👤 تغییر شخص", callback_data="rep_pick_person")
        ],
        [
            InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="rep_refresh"),
            InlineKeyboardButton(text="❌ بستن گزارش", callback_data="rep_close")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_report_date_range_keyboard() -> InlineKeyboardMarkup:
    """
    Presets keyboard for report date filters.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="📍 امروز", callback_data="rep_set_date:today"),
            InlineKeyboardButton(text="⏮ دیروز", callback_data="rep_set_date:yesterday")
        ],
        [
            InlineKeyboardButton(text="🗓 ۷ روز اخیر", callback_data="rep_set_date:last_7_days"),
            InlineKeyboardButton(text="🌙 ماه جاری شمسی", callback_data="rep_set_date:this_month")
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="rep_back_to_report")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_report_person_keyboard(persons: list) -> InlineKeyboardMarkup:
    """
    Person selection keyboard for filtering reports.
    """
    keyboard = [
        [InlineKeyboardButton(text="👥 همه افراد (بدون فیلتر)", callback_data="rep_set_person:all:همه افراد")]
    ]
    for p in persons:
        btn_text = f"👤 {p['name']}"
        callback_data = f"rep_set_person:{p['id']}:{p['name']}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="rep_back_to_report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)