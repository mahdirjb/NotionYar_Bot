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

from app.services.auth_service import (
    has_permission,
    PERM_VIEW_ALL_USERS,
    PERM_EDIT_RECORDS,
    PERM_DELETE_RECORDS
)

def build_report_keyboard(data: dict, has_entries: bool = True, user_id: int | None = None) -> InlineKeyboardMarkup:
    """
    Main interactive controls for the report message with granular permissions.
    """
    row_1 = [InlineKeyboardButton(text="📅 تغییر بازه زمانی", callback_data="rep_pick_date")]
    
    # Only show person filter if user has view_all_users permission
    if has_permission(user_id, PERM_VIEW_ALL_USERS):
        row_1.append(InlineKeyboardButton(text="👤 تغییر شخص", callback_data="rep_pick_person"))
        
    keyboard = [row_1]

    # Only show manage/edit/delete button if user has permission and entries exist
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
    """
    Presets keyboard for report date filters including custom range.
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
            InlineKeyboardButton(text="✍️ بازه دلخواه شمسی (تایپ دستی)", callback_data="rep_custom_date")
        ],
        [
            InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="rep_back_to_report")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_report_person_keyboard(persons: list) -> InlineKeyboardMarkup:
    """
    Person selection keyboard for filtering reports.
    Keeps callback_data under Telegram's 64-byte limit.
    """
    keyboard = [
        [InlineKeyboardButton(text="👥 همه افراد (بدون فیلتر)", callback_data="rep_set_person:all")]
    ]
    for p in persons:
        btn_text = f"👤 {p['name']}"
        # Only pass person ID to keep under 64 bytes limit
        callback_data = f"rep_set_person:{p['id']}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=callback_data)])

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="rep_back_to_report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_entries_selector_keyboard(entries: list) -> InlineKeyboardMarkup:
    """
    Builds a list of buttons for each record in the report to inspect or delete.
    Keeps callback_data under 64 bytes by only using page_id.
    """
    keyboard = []
    for idx, e in enumerate(entries, 1):
        name = e.get("name", "بدون عنوان")
        # Shorten name for button if too long
        display_name = (name[:25] + "...") if len(name) > 25 else name
        btn_text = f"{idx}. {display_name}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"rep_det:{e['id']}")])

    keyboard.append([InlineKeyboardButton(text="🔙 بازگشت به گزارش", callback_data="rep_back_to_report")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_entry_detail_keyboard(page_id: str, page_url: str, user_id: int | None = None) -> InlineKeyboardMarkup:
    """
    Action buttons for a single entry detail view with granular permissions.
    """
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
    """
    Two-step confirmation buttons for deleting a record.
    """
    keyboard = [
        [
            InlineKeyboardButton(text="⚠️ بله، حذف شود", callback_data=f"rep_do_del:{page_id}"),
            InlineKeyboardButton(text="❌ انصراف", callback_data=f"rep_det:{page_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_edit_fields_keyboard(page_id: str) -> InlineKeyboardMarkup:
    """
    Submenu to pick which field of the record to edit.
    """
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
    """
    Satisfaction picker for editing.
    """
    options = ["عالی", "خوب", "متوسط", "بد", "داغون"]
    keyboard = []
    for opt in options:
        emoji = SATISFACTION_EMOJIS.get(opt, "⭐")
        keyboard.append([InlineKeyboardButton(text=f"{emoji} {opt}", callback_data=f"rep_set_ed_sat:{opt}")])
    keyboard.append([InlineKeyboardButton(text="🔙 انصراف", callback_data=f"rep_edit:{page_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_edit_person_keyboard(page_id: str, persons: list) -> InlineKeyboardMarkup:
    """
    Person picker for editing.
    """
    keyboard = []
    for p in persons:
        keyboard.append([InlineKeyboardButton(text=f"👤 {p['name']}", callback_data=f"rep_set_ed_per:{p['id']}")])
    keyboard.append([InlineKeyboardButton(text="🔙 انصراف", callback_data=f"rep_edit:{page_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Admin Panel Keyboards ---

ROLE_BADGES = {
    "admin": "👑 مدیر کل",
    "manager": "💼 مدیر تیم",
    "member": "👤 عضو تیم",
    "guest": "🌿 مهمان"
}

def build_admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Main dashboard keyboard for Admin Panel."""
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
    """Keyboard listing all registered users for role editing or removal."""
    keyboard = []
    for uid, role in users.items():
        badge = ROLE_BADGES.get(role, "👤")
        btn_text = f"{badge} | ID: {uid}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_manage_user:{uid}")])

    keyboard.append([
        InlineKeyboardButton(text="➕ افزودن کاربر جدید", callback_data="adm_add_user"),
        InlineKeyboardButton(text="🔙 بازگشت به پنل", callback_data="adm_back_to_dashboard")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_user_manage_keyboard(target_user_id: int, current_role: str) -> InlineKeyboardMarkup:
    """Action keyboard for a specific user: Switch role or delete access."""
    keyboard = []
    
    # Available role switch buttons
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
    """Keyboard to choose role for newly added user."""
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
    """Confirmation keyboard before removing a user."""
    keyboard = [
        [
            InlineKeyboardButton(text="⚠️ بله، حذف دسترسی", callback_data=f"adm_do_del:{target_user_id}"),
            InlineKeyboardButton(text="❌ انصراف", callback_data=f"adm_manage_user:{target_user_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)