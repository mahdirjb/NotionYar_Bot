from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.admin_state import AdminState
from app.keyboards.inline import (
    build_admin_dashboard_keyboard,
    get_admin_users_list_keyboard,
    get_admin_user_manage_keyboard,
    get_admin_role_picker_keyboard,
    get_admin_delete_confirm_keyboard,
    get_back_cancel_keyboard,
    ROLE_BADGES
)
from app.services.auth_service import (
    has_permission,
    PERM_ADMIN,
    get_all_users,
    get_user_role,
    set_user_role,
    remove_user
)

router = Router()


def render_admin_dashboard_text(users: dict) -> str:
    """Formats the Admin dashboard status overview."""
    admin_cnt = sum(1 for r in users.values() if r == "admin")
    manager_cnt = sum(1 for r in users.values() if r == "manager")
    member_cnt = sum(1 for r in users.values() if r == "member")
    guest_cnt = sum(1 for r in users.values() if r == "guest")
    total_cnt = len(users)

    return (
        "👑 <b>پنل مدیریت دسترسی‌های نوشن‌یار</b>\n\n"
        "📊 <b>وضعیت کاربران ثبت‌شده در سیستم:</b>\n"
        f"├ 👑 <b>مدیران کل:</b> <code>{admin_cnt} نفر</code>\n"
        f"├ 💼 <b>مدیران تیم:</b> <code>{manager_cnt} نفر</code>\n"
        f"├ 👤 <b>اعضای عادی:</b> <code>{member_cnt} نفر</code>\n"
        f"└ 🌿 <b>مهمانان:</b> <code>{guest_cnt} نفر</code>\n\n"
        f"👥 <b>مجموع کل کاربران:</b> <code>{total_cnt} نفر</code>\n\n"
        "👇 <i>از دکمه‌های زیر برای مشاهده لیست، افزودن یا تغییر نقش‌ها استفاده کنید:</i>"
    )


async def show_admin_dashboard(event: Message | CallbackQuery, state: FSMContext):
    """Renders and updates the main admin dashboard card."""
    users = get_all_users()
    text = render_admin_dashboard_text(users)
    markup = build_admin_dashboard_keyboard()

    if isinstance(event, Message):
        msg = await event.answer(text, reply_markup=markup, parse_mode="HTML")
        await state.update_data(admin_card_id=msg.message_id)
    elif isinstance(event, CallbackQuery) and isinstance(event.message, Message):
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await event.answer()


# --- Admin Entry Handlers ---
@router.message(F.text.contains("پنل مدیریت"))
@router.message(Command("admin"))
async def open_admin_panel_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id if message.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await message.answer("⛔ شما به پنل مدیریت دسترسی ندارید.")
        return

    await state.clear()
    await state.set_state(AdminState.viewing_panel)
    await show_admin_dashboard(message, state)


@router.callback_query(F.data == "adm_back_to_dashboard")
@router.callback_query(F.data == "adm_refresh")
async def adm_back_to_dashboard_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await callback.answer("⛔ عدم دسترسی.", show_alert=True)
        return
    await show_admin_dashboard(callback, state)


@router.callback_query(F.data == "adm_close")
async def adm_close_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("🔒 پنل مدیریت بسته شد.")
    await callback.answer()


# --- Users List & Management ---
@router.callback_query(F.data == "adm_list_users")
async def adm_list_users_handler(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await callback.answer("⛔ عدم دسترسی.", show_alert=True)
        return

    users = get_all_users()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "👥 <b>لیست تمام کاربران ثبت‌شده:</b>\n\n"
            "<i>روی هر کاربر کلیک کنید تا نقش او را تغییر دهید یا دسترسی‌اش را حذف کنید:</i>",
            reply_markup=get_admin_users_list_keyboard(users),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_manage_user:"))
async def adm_manage_user_handler(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await callback.answer("⛔ عدم دسترسی.", show_alert=True)
        return

    target_uid = int((callback.data or "").split(":", 1)[1])
    role = get_user_role(target_uid) or "نامشخص"
    badge = ROLE_BADGES.get(role, "👤")

    detail_text = (
        "👤 <b>مدیریت کاربر:</b>\n\n"
        f"🆔 <b>آیدی تلگرام:</b> <code>{target_uid}</code>\n"
        f"🏷 <b>نقش فعلی:</b> {badge} (<code>{role}</code>)\n\n"
        "👇 <i>برای تغییر نقش یا مسدودسازی، یکی از گزینه‌های زیر را انتخاب کنید:</i>"
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            detail_text,
            reply_markup=get_admin_user_manage_keyboard(target_uid, role),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_set_role:"))
async def adm_set_role_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await callback.answer("⛔ عدم دسترسی.", show_alert=True)
        return

    parts = (callback.data or "").split(":")
    target_uid = int(parts[1])
    new_role = parts[2]

    # Prevent self-demoting from admin
    if target_uid == user_id and new_role != "admin":
        await callback.answer("⚠️ شما نمی‌توانید نقش خودتان را تنزل دهید!", show_alert=True)
        return

    set_user_role(target_uid, new_role)
    new_badge = ROLE_BADGES.get(new_role, "")
    await callback.answer(f"✅ نقش کاربر به '{new_badge}' تغییر یافت.", show_alert=True)

    # Re-render user manage card
    if isinstance(callback.message, Message):
        detail_text = (
            "👤 <b>مدیریت کاربر:</b>\n\n"
            f"🆔 <b>آیدی تلگرام:</b> <code>{target_uid}</code>\n"
            f"🏷 <b>نقش جدید:</b> {new_badge} (<code>{new_role}</code>)\n\n"
            "👇 <i>تغییرات با موفقیت ذخیره شد. می‌توانید فیلد دیگری را تغییر دهید:</i>"
        )
        await callback.message.edit_text(
            detail_text,
            reply_markup=get_admin_user_manage_keyboard(target_uid, new_role),
            parse_mode="HTML"
        )


@router.callback_query(F.data.startswith("adm_confirm_del:"))
async def adm_confirm_delete_handler(callback: CallbackQuery):
    target_uid = int((callback.data or "").split(":", 1)[1])
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"⚠️ <b>آیا از حذف و مسدودسازی کاربر <code>{target_uid}</code> اطمینان دارید؟</b>\n\n"
            "<i>این کاربر دیگر به هیچ بخشی از ربات دسترسی نخواهد داشت.</i>",
            reply_markup=get_admin_delete_confirm_keyboard(target_uid),
            parse_mode="HTML"
        )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_do_del:"))
async def adm_do_delete_handler(callback: CallbackQuery):
    user_id = callback.from_user.id if callback.from_user else None
    target_uid = int((callback.data or "").split(":", 1)[1])

    if target_uid == user_id:
        await callback.answer("⚠️ شما نمی‌توانید خودتان را حذف کنید!", show_alert=True)
        return

    remove_user(target_uid)
    await callback.answer("✅ دسترسی کاربر با موفقیت حذف شد.", show_alert=True)

    users = get_all_users()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "👥 <b>لیست به‌روزرسانی‌شده کاربران:</b>",
            reply_markup=get_admin_users_list_keyboard(users),
            parse_mode="HTML"
        )


# --- Add New User Flow ---
@router.callback_query(F.data == "adm_add_user")
async def adm_add_user_prompt(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not has_permission(user_id, PERM_ADMIN):
        await callback.answer("⛔ عدم دسترسی.", show_alert=True)
        return

    await state.set_state(AdminState.typing_new_user_id)
    if isinstance(callback.message, Message):
        prompt = await callback.message.answer(
            "➕ لطفاً <b>آیدی عددی تلگرام (Telegram User ID)</b> کاربر جدید را وارد کنید:\n\n"
            "💡 <i>(کاربر می‌تواند با ربات‌هایی مثل @userinfobot آیدی عددی خود را پیدا کند).</i>",
            reply_markup=get_back_cancel_keyboard(),
            parse_mode="HTML"
        )
        await state.update_data(last_prompt_id=prompt.message_id)
    await callback.answer()


@router.message(AdminState.typing_new_user_id)
async def adm_process_new_user_id(message: Message, state: FSMContext, bot: Bot):
    text = (message.text or "").strip()
    data = await state.get_data()
    prompt_id = data.get("last_prompt_id")

    if not text.isdigit() or len(text) < 5:
        err = await message.answer("❌ آیدی تلگرام باید یک عدد معتبر باشد (مثلاً <code>123456789</code>):", parse_mode="HTML")
        err_list = data.get("error_msg_ids", [])
        err_list.extend([err.message_id, message.message_id])
        await state.update_data(error_msg_ids=err_list)
        return

    target_uid = int(text)

    # Chat Hygiene
    if prompt_id:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
        except Exception:
            pass
    for em_id in data.get("error_msg_ids", []):
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=em_id)
        except Exception:
            pass
    try:
        await message.delete()
    except Exception:
        pass

    await state.set_state(AdminState.viewing_panel)
    await message.answer(
        f"🎯 آیدی <code>{target_uid}</code> دریافت شد.\n\n"
        "🏷 <b>لطفاً نقش مورد نظر برای این کاربر را انتخاب کنید:</b>",
        reply_markup=get_admin_role_picker_keyboard(target_uid),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_assign_role:"))
async def adm_assign_role_handler(callback: CallbackQuery, state: FSMContext):
    parts = (callback.data or "").split(":")
    target_uid = int(parts[1])
    role = parts[2]

    set_user_role(target_uid, role)
    badge = ROLE_BADGES.get(role, "")

    await callback.answer(f"✅ کاربر {target_uid} با نقش '{badge}' ثبت شد!", show_alert=True)
    await show_admin_dashboard(callback, state)