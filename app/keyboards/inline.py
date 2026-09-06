# app/keyboards/inline.py

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any, List, Optional
from app.services.auth_service import (
    has_permission,
    PERM_VIEW_ALL_USERS,
    PERM_EDIT_RECORDS,
    PERM_DELETE_RECORDS
)
from app.services.notion_service import (
    LIFE_TRACKER_TYPES,
    TYPE_MODE_MAPPING,
    TYPE_EMOJIS,
    MODE_EMOJIS,
    HABIT_ITEMS,
    HABIT_LEVELS
)

# ==========================================
# ⏱ TIME TRACKER KEYBOARDS
# ==========================================

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

def build_report_keyboard(data: dict, has_entries: bool = True, user_id: int | None = None) -> InlineKeyboardMarkup:
    row_1 = [InlineKeyboardButton(text="📅 تغییر بازه زمانی", callback_data="rep_pick_date")]
    if has_permission(user_id, PERM_VIEW_ALL_USERS):
        row_1.append(InlineKeyboardButton(text="👤 تغییر شخص", callback_data="rep_pick_person"))
    keyboard = [row_1]

    can_manage = has_permission(user_id, PERM_EDIT_RECORDS) or has_permission(user_id, PERM_DELETE_RECORDS)
    if has_entries and can_manage:
        keyboard.append([
            InlineKeyboardButton(text="🔍 مدیریت و ویرایش رکوردها", callback_data="rep_manage_entries")
        ])
        
    keyboard.append([
        InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="rep_refresh"),
        InlineKeyboardButton(text="❌ بستن گزارش", callback_data="rep_close")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_report_date_range_keyboard() -> InlineKeyboardMarkup:
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
            InlineKeyboardButton(text="✍️ بازه دلخواه شمسی (تایپ دستی)", callback_data="rep_custom_date")
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="rep_back_to_report")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_report_person_keyboard(persons: list) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="👥 همه افراد (بدون فیلتر)", callback_data="rep_set_person:all")]
    ]
    for p in persons:
        btn_text = f"👤 {p['name']}"
        callback_data = f"rep_set_person:{p['id']}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="rep_back_to_report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_entries_selector_keyboard(entries: list) -> InlineKeyboardMarkup:
    keyboard = []
    for idx, e in enumerate(entries, 1):
        name = e.get("name", "بدون عنوان")
        display_name = (name[:25] + "...") if len(name) > 25 else name
        btn_text = f"{idx}. {display_name}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"rep_det:{e['id']}")])

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="rep_back_to_report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_entry_detail_keyboard(page_id: str, page_url: str, user_id: int | None = None) -> InlineKeyboardMarkup:
    action_row = []
    if has_permission(user_id, PERM_EDIT_RECORDS):
        action_row.append(InlineKeyboardButton(text="✏️ ویرایش این رکورد", callback_data=f"rep_edit:{page_id}"))
    if has_permission(user_id, PERM_DELETE_RECORDS):
        action_row.append(InlineKeyboardButton(text="🗑 حذف این رکورد", callback_data=f"rep_confirm_del:{page_id}"))
        
    keyboard = []
    if action_row:
        keyboard.append(action_row)
        
    if page_url:
        keyboard.append([InlineKeyboardButton(text="🔗 مشاهده در نوشن", url=page_url)])
        
    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به لیست رکوردها", callback_data="rep_manage_entries")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_delete_confirm_keyboard(page_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="⚠️ بله، حذف شود", callback_data=f"rep_do_del:{page_id}"),
            InlineKeyboardButton(text="❌ انصراف", callback_data=f"rep_det:{page_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_edit_fields_keyboard(page_id: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="📌 ویرایش عنوان", callback_data=f"rep_ed_name:{page_id}"),
            InlineKeyboardButton(text="👤 تغییر شخص", callback_data=f"rep_ed_per:{page_id}")
        ],
        [
            InlineKeyboardButton(text="⭐ تغییر رضایت", callback_data=f"rep_ed_sat:{page_id}"),
            InlineKeyboardButton(text="⏱ ویرایش مدت زمان", callback_data=f"rep_ed_dur:{page_id}")
        ],
        [
            InlineKeyboardButton(text="📝 ویرایش توضیحات", callback_data=f"rep_ed_desc:{page_id}")
        ],
        [
            InlineKeyboardButton(text="📄 مشاهده کارت رکورد", callback_data=f"rep_det:{page_id}"),
            InlineKeyboardButton(text="📋 لیست رکوردها", callback_data="rep_manage_entries")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_edit_satisfaction_keyboard(page_id: str) -> InlineKeyboardMarkup:
    options = ["عالی", "خوب", "متوسط", "بد", "داغون"]
    keyboard = []
    for opt in options:
        emoji = SATISFACTION_EMOJIS.get(opt, "⭐")
        keyboard.append([InlineKeyboardButton(text=f"{emoji} {opt}", callback_data=f"rep_set_ed_sat:{opt}")])
    keyboard.append([InlineKeyboardButton(text="🔙 انصراف", callback_data=f"rep_edit:{page_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_edit_person_keyboard(page_id: str, persons: list) -> InlineKeyboardMarkup:
    keyboard = []
    for p in persons:
        keyboard.append([InlineKeyboardButton(text=f"👤 {p['name']}", callback_data=f"rep_set_ed_per:{p['id']}")])
    keyboard.append([InlineKeyboardButton(text="🔙 انصراف", callback_data=f"rep_edit:{page_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==========================================
# 👑 ADMIN PANEL KEYBOARDS
# ==========================================

ROLE_BADGES = {
    "admin": "👑 مدیر کل",
    "manager": "💼 مدیر تیم",
    "member": "👤 عضو تیم",
    "guest": "🌿 مهمان"
}

def build_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="👥 مدیریت و لیست کاربران", callback_data="adm_list_users"),
            InlineKeyboardButton(text="➕ افزودن کاربر جدید", callback_data="adm_add_user")
        ],
        [
            InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="adm_refresh"),
            InlineKeyboardButton(text="❌ بستن پنل", callback_data="adm_close")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_users_list_keyboard(users: dict) -> InlineKeyboardMarkup:
    keyboard = []
    for uid, info in users.items():
        role = info.get("role", "member")
        name = info.get("name", f"کاربر {uid}")
        badge = ROLE_BADGES.get(role, "👤")
        btn_text = f"{badge} {name}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_manage_user:{uid}")])

    keyboard.append([
        InlineKeyboardButton(text="➕ افزودن کاربر جدید", callback_data="adm_add_user"),
        InlineKeyboardButton(text="🔙 بازگشت به پنل", callback_data="adm_back_to_dashboard")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_user_manage_keyboard(target_user_id: int, current_role: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="✏️ ویرایش نام کاربر", callback_data=f"adm_edit_name:{target_user_id}")]
    ]
    roles = [
        ("admin", "👑 تبدیل به مدیر کل"),
        ("manager", "💼 تبدیل به مدیر تیم"),
        ("member", "👤 تبدیل به عضو عادی"),
        ("guest", "🌿 تبدیل به مهمان")
    ]
    for r_key, r_label in roles:
        if r_key != current_role:
            keyboard.append([InlineKeyboardButton(text=r_label, callback_data=f"adm_set_role:{target_user_id}:{r_key}")])

    keyboard.append([InlineKeyboardButton(text="🗑 مسدودسازی و حذف دسترسی", callback_data=f"adm_confirm_del:{target_user_id}")])
    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به لیست کاربران", callback_data="adm_list_users")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_role_picker_keyboard(target_user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="👑 مدیر کل (Admin)", callback_data=f"adm_assign_role:{target_user_id}:admin"),
            InlineKeyboardButton(text="💼 مدیر تیم (Manager)", callback_data=f"adm_assign_role:{target_user_id}:manager")
        ],
        [
            InlineKeyboardButton(text="👤 عضو عادی (Member)", callback_data=f"adm_assign_role:{target_user_id}:member"),
            InlineKeyboardButton(text="🌿 مهمان (Guest)", callback_data=f"adm_assign_role:{target_user_id}:guest")
        ],
        [
            InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="adm_back_to_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_delete_confirm_keyboard(target_user_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(text="⚠️ بله، حذف دسترسی", callback_data=f"adm_do_del:{target_user_id}"),
            InlineKeyboardButton(text="❌ انصراف", callback_data=f"adm_manage_user:{target_user_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ==========================================
# 🌿 LIFE TRACKER KEYBOARDS
# ==========================================

def build_life_tracker_hub_keyboard() -> InlineKeyboardMarkup:
    """Main landing hub keyboard for Life Tracker with Insights button."""
    keyboard = [
        [
            InlineKeyboardButton(text="📝 ثبت لاگ جدید", callback_data="lt_new_log"),
            InlineKeyboardButton(text="📊 تاریخچه و گزارش‌ها", callback_data="lt_reports")
        ],
        [
            InlineKeyboardButton(text="📈 تحلیل فواصل و روتین‌ها", callback_data="lt_ins_hub")
        ],
        [
            InlineKeyboardButton(text="❌ بستن منو", callback_data="lt_close_hub")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def build_life_tracker_card_keyboard(data: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Interactive card for creating a new Life Tracker entry."""
    name_label = "✏️ عنوان: " + (data.get("name") or "وارد نشده ❌")
    
    t_val = data.get("type")
    t_emoji = TYPE_EMOJIS.get(t_val, "🏷") if t_val else "🏷"
    type_label = f"{t_emoji} نوع فعالیت: " + (t_val or "انتخاب نشده ❌")

    modes = data.get("modes") or []
    if modes:
        mode_str = " | ".join([f"{MODE_EMOJIS.get(m, '✨')} {m}" for m in modes])
        mode_label = f"🎭 حالت: {mode_str}"
    else:
        mode_label = "🎭 حالت: بدون انتخاب (عادی)"

    date_label = "📅 تاریخ: " + (data.get("date_label") or "امروز")
    notes_label = "📝 یادداشت: " + ("ثبت شده ✅" if data.get("notes") else "—")

    buttons = [
        [InlineKeyboardButton(text=type_label, callback_data="lt_pick_type")],
        [InlineKeyboardButton(text=name_label, callback_data="lt_edit_name")],
    ]

    # Only show Mode button if selected Type supports modes or if modes already exist
    available_modes = TYPE_MODE_MAPPING.get(t_val or "", [])
    if available_modes or modes:
        buttons.append([InlineKeyboardButton(text=mode_label, callback_data="lt_pick_mode")])

    buttons.extend([
        [InlineKeyboardButton(text=date_label, callback_data="lt_pick_date")],
        [InlineKeyboardButton(text=notes_label, callback_data="lt_edit_notes")],
        [
            InlineKeyboardButton(text="✅ ثبت در روزمرگی", callback_data="lt_submit_card"),
            InlineKeyboardButton(text="❌ انصراف", callback_data="lt_cancel_card")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_life_tracker_type_keyboard() -> InlineKeyboardMarkup:
    """Type picker keyboard for Life Tracker with custom emojis."""
    keyboard = []
    row = []
    for t in LIFE_TRACKER_TYPES:
        emoji = TYPE_EMOJIS.get(t, "🏷")
        row.append(InlineKeyboardButton(text=f"{emoji} {t}", callback_data=f"lt_set_type:{t}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="lt_back_to_card")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_life_tracker_mode_keyboard(type_val: str, selected_modes: List[str]) -> InlineKeyboardMarkup:
    """
    Dynamic Multi-Select Mode picker keyboard with toggle checkboxes (✅ / ⬜).
    """
    available_modes = TYPE_MODE_MAPPING.get(type_val, [])
    keyboard = []
    row = []

    for m in available_modes:
        is_selected = m in selected_modes
        check_icon = "✅" if is_selected else "⬜"
        m_emoji = MODE_EMOJIS.get(m, "✨")
        btn_text = f"{check_icon} {m_emoji} {m}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"lt_tog_mode:{m}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(text="🗑 پاک کردن همه حالت‌ها", callback_data="lt_clear_modes"),
        InlineKeyboardButton(text="✔️ تایید و بازگشت", callback_data="lt_back_to_card")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_life_tracker_date_keyboard() -> InlineKeyboardMarkup:
    """Preset date picker for Life Tracker."""
    keyboard = [
        [
            InlineKeyboardButton(text="امروز", callback_data="lt_set_date_preset:0:امروز"),
            InlineKeyboardButton(text="دیروز", callback_data="lt_set_date_preset:1:دیروز"),
            InlineKeyboardButton(text="پریروز", callback_data="lt_set_date_preset:2:پریروز")
        ],
        [InlineKeyboardButton(text="✍️ ورود تاریخ دلخواه شمسی", callback_data="lt_enter_custom_date")],
        [InlineKeyboardButton(text="🔙 بازگشت به فرم", callback_data="lt_back_to_card")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_life_tracker_notes_keyboard() -> InlineKeyboardMarkup:
    """Action buttons when typing notes."""
    keyboard = [
        [InlineKeyboardButton(text="🗑 پاک کردن یادداشت", callback_data="lt_clear_notes")],
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت", callback_data="lt_back_to_card")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lt_back_cancel_keyboard() -> InlineKeyboardMarkup:
    """Generic cancel and back to Life Tracker card."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف و بازگشت به فرم", callback_data="lt_back_to_card")]
    ])


# --- Life Tracker Reports & Pagination Keyboards ---

def build_life_tracker_report_keyboard(
    data: Dict[str, Any],
    current_page: int = 1,
    total_pages: int = 1,
    has_entries: bool = True
) -> InlineKeyboardMarkup:
    """
    Main interactive controls for Life Tracker reports with pagination.
    """
    selected_type = data.get("type_val")
    filter_row = [
        InlineKeyboardButton(text="📅 تاریخ", callback_data="lt_rep_pick_date"),
        InlineKeyboardButton(text="🏷 نوع فعالیت", callback_data="lt_rep_pick_type")
    ]
    if selected_type and selected_type in TYPE_MODE_MAPPING:
        filter_row.append(InlineKeyboardButton(text="🎭 حالت", callback_data="lt_rep_pick_mode"))
    
    keyboard = [filter_row]

    if has_entries:
        keyboard.append([
            InlineKeyboardButton(text="🔍 مدیریت، ویرایش و حذف رکوردها", callback_data="lt_rep_manage")
        ])

    # Pagination Row
    if total_pages > 1:
        pag_row = []
        if current_page > 1:
            pag_row.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"lt_page:{current_page - 1}"))
        else:
            pag_row.append(InlineKeyboardButton(text="▪️", callback_data="lt_noop"))

        pag_row.append(InlineKeyboardButton(text=f"صفحه {current_page} از {total_pages}", callback_data="lt_noop"))

        if current_page < total_pages:
            pag_row.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"lt_page:{current_page + 1}"))
        else:
            pag_row.append(InlineKeyboardButton(text="▪️", callback_data="lt_noop"))

        keyboard.append(pag_row)

    keyboard.append([
        InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="lt_rep_refresh"),
        InlineKeyboardButton(text="🌱 هاب روزمرگی", callback_data="lt_back_to_hub"),
        InlineKeyboardButton(text="❌ بستن", callback_data="lt_rep_close")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lt_report_date_range_keyboard() -> InlineKeyboardMarkup:
    """Date presets for Life Tracker reports including All Time."""
    keyboard = [
        [
            InlineKeyboardButton(text="🌐 تمام زمان‌ها (نمایش همه سطرها)", callback_data="lt_rep_set_date:all_time")
        ],
        [
            InlineKeyboardButton(text="📍 امروز", callback_data="lt_rep_set_date:today"),
            InlineKeyboardButton(text="⏮ دیروز", callback_data="lt_rep_set_date:yesterday")
        ],
        [
            InlineKeyboardButton(text="🗓 ۷ روز اخیر", callback_data="lt_rep_set_date:last_7_days"),
            InlineKeyboardButton(text="🌙 ماه جاری شمسی", callback_data="lt_rep_set_date:this_month")
        ],
        [
            InlineKeyboardButton(text="✍️ بازه دلخواه شمسی (تایپ دستی)", callback_data="lt_rep_custom_date")
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="lt_back_to_report")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_lt_report_type_filter_keyboard() -> InlineKeyboardMarkup:
    """Type filter keyboard for Life Tracker reports."""
    keyboard = [
        [InlineKeyboardButton(text="👥 همه انواع (بدون فیلتر)", callback_data="lt_rep_set_type:all")]
    ]
    row = []
    for t in LIFE_TRACKER_TYPES:
        emoji = TYPE_EMOJIS.get(t, "🏷")
        row.append(InlineKeyboardButton(text=f"{emoji} {t}", callback_data=f"lt_rep_set_type:{t}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="lt_back_to_report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lt_report_mode_filter_keyboard(type_val: str) -> InlineKeyboardMarkup:
    """Mode filter keyboard for Life Tracker reports."""
    keyboard = [
        [InlineKeyboardButton(text="👥 همه حالت‌ها (بدون فیلتر)", callback_data="lt_rep_set_mode:all")]
    ]
    available_modes = TYPE_MODE_MAPPING.get(type_val, [])
    row = []
    for m in available_modes:
        emoji = MODE_EMOJIS.get(m, "✨")
        row.append(InlineKeyboardButton(text=f"{emoji} {m}", callback_data=f"lt_rep_set_mode:{m}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="lt_back_to_report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lt_entries_selector_keyboard(entries: list, page: int = 1, page_size: int = 5) -> InlineKeyboardMarkup:
    """Builds a paginated list of Life Tracker entries to inspect."""
    total_entries = len(entries)
    total_pages = max(1, (total_entries + page_size - 1) // page_size)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_entries = entries[start_idx:end_idx]

    keyboard = []
    for idx, e in enumerate(page_entries, start_idx + 1):
        name = e.get("name", "بدون عنوان")
        t_val = e.get("type", "")
        t_emoji = TYPE_EMOJIS.get(t_val, "🏷")
        display_name = (name[:22] + "...") if len(name) > 22 else name
        btn_text = f"{idx}. {t_emoji} {display_name}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"lt_det:{e['id']}")])

    # Pagination controls in selector
    if total_pages > 1:
        pag_row = []
        if page > 1:
            pag_row.append(InlineKeyboardButton(text="◀️ قبلی", callback_data=f"lt_sel_page:{page - 1}"))
        else:
            pag_row.append(InlineKeyboardButton(text="▪️", callback_data="lt_noop"))

        pag_row.append(InlineKeyboardButton(text=f"صفحه {page} از {total_pages}", callback_data="lt_noop"))

        if page < total_pages:
            pag_row.append(InlineKeyboardButton(text="بعدی ▶️", callback_data=f"lt_sel_page:{page + 1}"))
        else:
            pag_row.append(InlineKeyboardButton(text="▪️", callback_data="lt_noop"))

        keyboard.append(pag_row)

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="lt_back_to_report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lt_entry_detail_keyboard(page_id: str, page_url: str) -> InlineKeyboardMarkup:
    """Action buttons for viewing a single Life Tracker record."""
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ ویرایش این رکورد", callback_data=f"lt_edit:{page_id}"),
            InlineKeyboardButton(text="🗑 حذف این رکورد", callback_data=f"lt_confirm_del:{page_id}")
        ]
    ]
    if page_url:
        keyboard.append([InlineKeyboardButton(text="🔗 مشاهده در نوشن", url=page_url)])
    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به لیست رکوردها", callback_data="lt_rep_manage")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lt_delete_confirm_keyboard(page_id: str) -> InlineKeyboardMarkup:
    """Confirmation before archiving a Life Tracker entry."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚠️ بله، حذف شود", callback_data=f"lt_do_del:{page_id}"),
            InlineKeyboardButton(text="❌ انصراف", callback_data=f"lt_det:{page_id}")
        ]
    ])


def get_lt_edit_fields_keyboard(page_id: str, type_val: str) -> InlineKeyboardMarkup:
    """Submenu for picking which field of Life Tracker entry to edit."""
    keyboard = [
        [
            InlineKeyboardButton(text="📌 ویرایش عنوان", callback_data=f"lt_ed_name:{page_id}"),
            InlineKeyboardButton(text="🏷 تغییر نوع فعالیت", callback_data=f"lt_ed_type:{page_id}")
        ]
    ]

    available_modes = TYPE_MODE_MAPPING.get(type_val, [])
    if available_modes:
        keyboard.append([
            InlineKeyboardButton(text="🎭 تغییر حالت‌ها (Mode)", callback_data=f"lt_ed_mode:{page_id}")
        ])

    keyboard.extend([
        [
            InlineKeyboardButton(text="📅 تغییر تاریخ", callback_data=f"lt_ed_date:{page_id}"),
            InlineKeyboardButton(text="📝 ویرایش یادداشت", callback_data=f"lt_ed_notes:{page_id}")
        ],
        [
            InlineKeyboardButton(text="📄 مشاهده کارت رکورد", callback_data=f"lt_det:{page_id}"),
            InlineKeyboardButton(text="📋 لیست رکوردها", callback_data="lt_rep_manage")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lt_edit_type_keyboard(page_id: str) -> InlineKeyboardMarkup:
    """Type picker when editing an existing entry."""
    keyboard = []
    row = []
    for t in LIFE_TRACKER_TYPES:
        emoji = TYPE_EMOJIS.get(t, "🏷")
        row.append(InlineKeyboardButton(text=f"{emoji} {t}", callback_data=f"lt_set_ed_type:{page_id}:{t}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="🔙 انصراف", callback_data=f"lt_edit:{page_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_lt_edit_mode_keyboard(page_id: str, type_val: str, selected_modes: List[str]) -> InlineKeyboardMarkup:
    """Mode picker with toggles when editing an existing entry."""
    available_modes = TYPE_MODE_MAPPING.get(type_val, [])
    keyboard = []
    row = []

    for m in available_modes:
        is_selected = m in selected_modes
        check_icon = "✅" if is_selected else "⬜"
        m_emoji = MODE_EMOJIS.get(m, "✨")
        btn_text = f"{check_icon} {m_emoji} {m}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"lt_tog_ed_mode:{page_id}:{m}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(text="🗑 پاک کردن همه حالت‌ها", callback_data=f"lt_clear_ed_modes:{page_id}"),
        InlineKeyboardButton(text="💾 ذخیره تغییرات", callback_data=f"lt_save_ed_modes:{page_id}")
    ])
    keyboard.append([InlineKeyboardButton(text="🔙 انصراف", callback_data=f"lt_edit:{page_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==========================================
# 📈 INSIGHTS & HABIT INTERVAL KEYBOARDS
# ==========================================

def build_insights_dashboard_keyboard(insights_data: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Dashboard keyboard showing active habit drill-down buttons."""
    keyboard = []
    row = []

    for t_name, info in insights_data.items():
        if info.get("has_data"):
            badge = info.get("badge", "▫️")
            emoji = info.get("emoji", "🏷")
            btn_text = f"{badge} {emoji} {t_name}"
            row.append(InlineKeyboardButton(text=btn_text, callback_data=f"lt_ins_h:{t_name}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []

    if row:
        keyboard.append(row)

    keyboard.extend([
        [
            InlineKeyboardButton(text="⚙️ تنظیم آیتم‌های فعال", callback_data="lt_ins_set"),
            InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="lt_ins_refresh")
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به هاب روزمرگی", callback_data="lt_back_to_hub")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_insights_habit_detail_keyboard() -> InlineKeyboardMarkup:
    """Action keyboard when viewing deep dive of a specific habit."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔙 بازگشت به داشبورد تحلیل", callback_data="lt_ins_hub"),
            InlineKeyboardButton(text="🌱 هاب روزمرگی", callback_data="lt_back_to_hub")
        ]
    ])


def get_insights_settings_keyboard(enabled_types: List[str]) -> InlineKeyboardMarkup:
    """Settings keyboard to toggle on/off habit calculations for each type."""
    keyboard = []
    row = []

    for t in LIFE_TRACKER_TYPES:
        is_on = t in enabled_types
        icon = "✅" if is_on else "⬜"
        emoji = TYPE_EMOJIS.get(t, "🏷")
        btn_text = f"{icon} {emoji} {t}"
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"lt_ins_tog:{t}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton(text="✔️ ذخیره و بازگشت به داشبورد", callback_data="lt_ins_hub")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# ==========================================
# 🎯 HABIT TRACKER KEYBOARDS (V2.2)
# ==========================================

HABIT_STATUS_ICONS = {
    "1-💪 کامل": "💪",
    "2-🏃‍♂️ نیمه‌کامل": "🏃",
    "3-🐢 سبک": "🐢",
    "4-❌ با دلیل": "❌",
    "5-⛔ بدون دلیل": "⛔",
}


def build_habit_hub_keyboard(
    offset_days: int,
    stealth_mode: bool = False,
) -> InlineKeyboardMarkup:
    """Clean, decluttered Hub landing keyboard with 3 primary logging entry modes."""
    keyboard = [
        # Primary Action 1: Standard Fill
        [
            InlineKeyboardButton(
                text="⚡ ثبت همه به عنوان معمول (استاندارد)",
                callback_data=f"hb_ask_fill:{offset_days}",
            )
        ],
        # Primary Action 2 & 3
        [
            InlineKeyboardButton(
                text="⚡ ثبت سریع زنجیره‌ای",
                callback_data=f"hb_qr_start:{offset_days}",
            ),
            InlineKeyboardButton(
                text="📋 نمای تفصیلی ۱۲ عادت",
                callback_data=f"hb_view_det:{offset_days}",
            ),
        ],
        # Journals Row
        [
            InlineKeyboardButton(
                text="🌸 دفترچه شکرگزاری",
                callback_data=f"hb_grat:{offset_days}",
            ),
            InlineKeyboardButton(
                text="📝 یادداشت روز",
                callback_data=f"hb_notes:{offset_days}",
            ),
        ],
        # Navigation Row
        [
            InlineKeyboardButton(
                text="◀️ دیروز", callback_data=f"hb_nav:{offset_days + 1}"
            ),
            InlineKeyboardButton(text="🔄 امروز", callback_data="hb_nav:0"),
            InlineKeyboardButton(
                text="فردا ▶️", callback_data=f"hb_nav:{offset_days - 1}"
            ),
        ],
        # Utility Row
        [
            InlineKeyboardButton(
                text="🕶️ مخفی: روشن" if stealth_mode else "🕶️ مخفی: خاموش",
                callback_data=f"hb_tog_stl:{offset_days}",
            ),
            InlineKeyboardButton(
                text="📅 تقویم", callback_data=f"hb_cdate:{offset_days}"
            ),
            InlineKeyboardButton(
                text="🗑️ ریست روز",
                callback_data=f"hb_ask_reset:{offset_days}",
            ),
        ],
        # Refresh & Close
        [
            InlineKeyboardButton(
                text="🔄 بروزرسانی", callback_data=f"hb_ref:{offset_days}"
            ),
            InlineKeyboardButton(text="❌ بستن", callback_data="hb_close"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def build_habit_detailed_keyboard(
    habits_data: Dict[str, Optional[str]],
    offset_days: int,
    stealth_mode: bool = False,
) -> InlineKeyboardMarkup:
    """Detailed 12-habit grid keyboard."""
    keyboard = []
    row = []
    cols = 3 if stealth_mode else 2

    for h_key, h_info in HABIT_ITEMS.items():
        val = habits_data.get(h_key)
        icon = HABIT_STATUS_ICONS.get(val or "", "▫️")

        if stealth_mode:
            btn_text = f"[{h_info['code']}]: {icon}"
        else:
            btn_text = f"{icon} {h_info['emoji']} {h_info['fa']}"

        row.append(
            InlineKeyboardButton(
                text=btn_text, callback_data=f"hb_pk:{h_key}:{offset_days}"
            )
        )

        if len(row) == cols:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    # Quran detail quick action button
    if not stealth_mode:
        keyboard.append([
            InlineKeyboardButton(
                text="📖 ثبت صفحه / سوره قرآن",
                callback_data=f"hb_qrn_det:{offset_days}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="🔙 بازگشت به هاب عادات",
            callback_data=f"hb_view_hub:{offset_days}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_habit_level_picker_keyboard(
    habit_key: str, offset_days: int
) -> InlineKeyboardMarkup:
    """Submenu for choosing habit completion level (supports binary and 5-level habits)."""
    h_info = HABIT_ITEMS.get(habit_key, {})
    is_binary = h_info.get("binary", False)

    if is_binary:
        # Clean 3-button keyboard for binary habits
        keyboard = [
            [
                InlineKeyboardButton(
                    text="✅ انجام شد",
                    callback_data=f"hb_set:{habit_key}:1:{offset_days}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ با دلیل",
                    callback_data=f"hb_set:{habit_key}:4:{offset_days}",
                ),
                InlineKeyboardButton(
                    text="⛔ بدون دلیل",
                    callback_data=f"hb_set:{habit_key}:5:{offset_days}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 پاک‌کردن",
                    callback_data=f"hb_set:{habit_key}:0:{offset_days}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به نمای عادات",
                    callback_data=f"hb_view_det:{offset_days}",
                )
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    # Standard 5-level picker
    keyboard = [
        [
            InlineKeyboardButton(
                text="💪 ۱. کامل (بونوس)",
                callback_data=f"hb_set:{habit_key}:1:{offset_days}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🏃 ۲. معمول (استاندارد)",
                callback_data=f"hb_set:{habit_key}:2:{offset_days}",
            ),
            InlineKeyboardButton(
                text="🐢 ۳. سبک (حداقلی)",
                callback_data=f"hb_set:{habit_key}:3:{offset_days}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ ۴. با دلیل",
                callback_data=f"hb_set:{habit_key}:4:{offset_days}",
            ),
            InlineKeyboardButton(
                text="⛔ ۵. بدون دلیل",
                callback_data=f"hb_set:{habit_key}:5:{offset_days}",
            ),
        ],
    ]

    # Quick button to log Quran detail if habit is Quran
    if habit_key == "rq":
        keyboard.append([
            InlineKeyboardButton(
                text="📖 ثبت شماره صفحه / سوره",
                callback_data=f"hb_qrn_det:{offset_days}",
            )
        ])

    keyboard.extend([
        [
            InlineKeyboardButton(
                text="🗑 پاک‌کردن (ثبت‌نشده)",
                callback_data=f"hb_set:{habit_key}:0:{offset_days}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 بازگشت به نمای عادات",
                callback_data=f"hb_view_det:{offset_days}",
            )
        ],
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_quick_run_keyboard(
    habit_key: str, offset_days: int
) -> InlineKeyboardMarkup:
    """Fast-action keyboard for the Quick-Run Wizard flow (supports binary habits)."""
    h_info = HABIT_ITEMS.get(habit_key, {})
    is_binary = h_info.get("binary", False)

    if is_binary:
        keyboard = [
            [
                InlineKeyboardButton(
                    text="✅ انجام شد",
                    callback_data=f"hb_qr_val:{habit_key}:1:{offset_days}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ با دلیل",
                    callback_data=f"hb_qr_val:{habit_key}:4:{offset_days}",
                ),
                InlineKeyboardButton(
                    text="⛔ بدون دلیل",
                    callback_data=f"hb_qr_val:{habit_key}:5:{offset_days}",
                ),
                InlineKeyboardButton(
                    text="⏭ رد شدن",
                    callback_data=f"hb_qr_skip:{habit_key}:{offset_days}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 انصراف و خروج از ثبت سریع",
                    callback_data=f"hb_back:{offset_days}",
                )
            ],
        ]
        return InlineKeyboardMarkup(inline_keyboard=keyboard)

    keyboard = [
        [
            InlineKeyboardButton(
                text="💪 ۱. کامل",
                callback_data=f"hb_qr_val:{habit_key}:1:{offset_days}",
            ),
            InlineKeyboardButton(
                text="🏃 ۲. معمول",
                callback_data=f"hb_qr_val:{habit_key}:2:{offset_days}",
            ),
            InlineKeyboardButton(
                text="🐢 ۳. سبک",
                callback_data=f"hb_qr_val:{habit_key}:3:{offset_days}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ ۴. با دلیل",
                callback_data=f"hb_qr_val:{habit_key}:4:{offset_days}",
            ),
            InlineKeyboardButton(
                text="⛔ ۵. بدون دلیل",
                callback_data=f"hb_qr_val:{habit_key}:5:{offset_days}",
            ),
            InlineKeyboardButton(
                text="⏭ رد شدن",
                callback_data=f"hb_qr_skip:{habit_key}:{offset_days}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔙 انصراف و خروج از ثبت سریع",
                callback_data=f"hb_back:{offset_days}",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_gratitude_accumulator_keyboard(
    offset_days: int,
    has_items: bool = False,
    is_saved_preview: bool = False,
) -> InlineKeyboardMarkup:
    """Interactive builder keyboard for Gratitude Journal."""
    if is_saved_preview:
        # Smooth navigation view after saving
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ افزودن مورد جدید به لیست",
                        callback_data=f"hb_gr_add_more:{offset_days}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✏️ ویرایش یک مورد",
                        callback_data=f"hb_gr_ask_edit:{offset_days}",
                    ),
                    InlineKeyboardButton(
                        text="🗑️ حذف یک مورد",
                        callback_data=f"hb_gr_ask_del:{offset_days}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🗑 پاک‌کردن کل شکرگزاری",
                        callback_data=f"hb_gr_clr_all:{offset_days}",
                    ),
                    InlineKeyboardButton(
                        text="🔙 بازگشت به هاب عادات",
                        callback_data=f"hb_back:{offset_days}",
                    ),
                ],
            ]
        )

    keyboard = [
        [
            InlineKeyboardButton(
                text="👤 سلامتی و جسم",
                callback_data=f"hb_gr_tag:جسم:{offset_days}",
            ),
            InlineKeyboardButton(
                text="🤝 روابط و دوستان",
                callback_data=f"hb_gr_tag:روابط:{offset_days}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="💼 کار و رشد",
                callback_data=f"hb_gr_tag:کار:{offset_days}",
            ),
            InlineKeyboardButton(
                text="🌍 نعمات روزمره",
                callback_data=f"hb_gr_tag:نعمات:{offset_days}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🧘 ذهن و آرامش",
                callback_data=f"hb_gr_tag:آرامش:{offset_days}",
            ),
            InlineKeyboardButton(
                text="✨ اتفاقات خرد",
                callback_data=f"hb_gr_tag:اتفاقات:{offset_days}",
            ),
        ],
    ]

    if has_items:
        keyboard.append([
            InlineKeyboardButton(
                text="💾 ذخیره نهایی در نوشن",
                callback_data=f"hb_gr_save:{offset_days}",
            )
        ])
        keyboard.append([
            InlineKeyboardButton(
                text="✏️ ویرایش یک مورد",
                callback_data=f"hb_gr_ask_edit:{offset_days}",
            ),
            InlineKeyboardButton(
                text="🗑️ حذف یک مورد",
                callback_data=f"hb_gr_ask_del:{offset_days}",
            ),
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="🗑 پاک‌کردن کل",
            callback_data=f"hb_gr_clr_all:{offset_days}",
        ),
        InlineKeyboardButton(
            text="🔙 بازگشت به هاب عادات", callback_data=f"hb_back:{offset_days}"
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_gratitude_item_picker_keyboard(
    items: List[Dict[str, Any]], action: str, offset_days: int
) -> InlineKeyboardMarkup:
    """Picker keyboard to choose which gratitude item to edit or delete."""
    keyboard = []
    for idx, item in enumerate(items):
        tag_str = f"[{item.get('tag')}] " if item.get("tag") else ""
        text_preview = item["text"][:20] + "..." if len(item["text"]) > 20 else item["text"]
        btn_text = f"{idx + 1}. 🌿 {tag_str}{text_preview}"
        keyboard.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"hb_gr_do_{action}:{idx}:{offset_days}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="🔙 انصراف و بازگشت",
            callback_data=f"hb_grat:{offset_days}",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_quran_detail_keyboard(offset_days: int) -> InlineKeyboardMarkup:
    """Action buttons when typing Quran details."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 پاک کردن صفحه/سوره",
                    callback_data=f"hb_clr_quran:{offset_days}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 بازگشت به نمای عادات",
                    callback_data=f"hb_view_det:{offset_days}",
                )
            ],
        ]
    )


def get_habit_reset_confirm_keyboard(
    offset_days: int,
) -> InlineKeyboardMarkup:
    """Security confirmation keyboard before resetting habit day."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚠️ بله، کل روز ریست شود",
                    callback_data=f"hb_do_reset:{offset_days}",
                ),
                InlineKeyboardButton(
                    text="❌ انصراف", callback_data=f"hb_back:{offset_days}"
                ),
            ]
        ]
    )


def get_habit_bulk_fill_confirm_keyboard(
    offset_days: int,
) -> InlineKeyboardMarkup:
    """Confirmation before marking all habits as Version 2 (Standard/Normal)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ بله، همه «معمول (استاندارد)» شوند",
                    callback_data=f"hb_do_fill:{offset_days}",
                ),
                InlineKeyboardButton(
                    text="❌ انصراف", callback_data=f"hb_back:{offset_days}"
                ),
            ]
        ]
    )


def get_habit_notes_keyboard(offset_days: int) -> InlineKeyboardMarkup:
    """Action keyboard for editing daily notes."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 پاک کردن یادداشت",
                    callback_data=f"hb_clr_notes:{offset_days}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 انصراف و بازگشت",
                    callback_data=f"hb_back:{offset_days}",
                )
            ],
        ]
    )


def get_habit_custom_date_cancel_keyboard(
    offset_days: int,
) -> InlineKeyboardMarkup:
    """Cancel keyboard for custom date prompt."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 انصراف و بازگشت",
                    callback_data=f"hb_back:{offset_days}",
                )
            ]
        ]
    )