from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.states.time_tracker_state import TimeTrackerForm
from app.keyboards.inline import get_satisfaction_keyboard, get_skip_keyboard, get_main_menu_keyboard
from app.services.notion_service import add_time_tracker_entry
from app.config import ALLOWED_USERS

router = Router()

def is_user_allowed(user_id: int | None) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS if user_id else False

@router.callback_query(F.data == "btn_add_time")
async def start_time_entry_flow(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id if callback.from_user else None
    if not is_user_allowed(user_id):
        await callback.answer("⛔ Access Denied", show_alert=True)
        return

    await state.set_state(TimeTrackerForm.waiting_for_name)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("📝 Enter the **Task / Activity Name**:")
    await callback.answer()

@router.message(TimeTrackerForm.waiting_for_name)
async def process_task_name(message: Message, state: FSMContext):
    task_name = (message.text or "").strip()
    if not task_name:
        await message.answer("Please send a valid task name.")
        return

    await state.update_data(name=task_name)
    await state.set_state(TimeTrackerForm.waiting_for_duration)
    await message.answer("⏱ Enter duration in **minutes** (e.g. 45 or 90):")

@router.message(TimeTrackerForm.waiting_for_duration)
async def process_duration(message: Message, state: FSMContext):
    duration_text = (message.text or "").strip()
    if not duration_text.isdigit():
        await message.answer("❌ Invalid input. Please enter numbers only (e.g. 60):")
        return

    await state.update_data(duration=int(duration_text))
    await state.set_state(TimeTrackerForm.waiting_for_satisfaction)
    await message.answer("⭐ Select your **Satisfaction level**:", reply_markup=get_satisfaction_keyboard())

@router.callback_query(TimeTrackerForm.waiting_for_satisfaction, F.data.startswith("sat_"))
async def process_satisfaction(callback: CallbackQuery, state: FSMContext):
    satisfaction_value = callback.data.split("sat_")[1] if callback.data else "متوسط"
    await state.update_data(satisfaction=satisfaction_value)
    
    await state.set_state(TimeTrackerForm.waiting_for_description)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📄 Enter an optional **Description / Notes**, or click **Skip**:",
            reply_markup=get_skip_keyboard()
        )
    await callback.answer()

@router.callback_query(TimeTrackerForm.waiting_for_description, F.data == "skip_description")
async def skip_description(callback: CallbackQuery, state: FSMContext):
    if isinstance(callback.message, Message):
        await save_entry_to_notion(callback.message, state, description="")
    await callback.answer()

@router.message(TimeTrackerForm.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    description = (message.text or "").strip()
    await save_entry_to_notion(message, state, description=description)

async def save_entry_to_notion(message_obj: Message, state: FSMContext, description: str):
    data = await state.get_data()
    await state.clear()
    
    waiting_msg = await message_obj.answer("⏳ Saving entry to Notion...")
    
    try:
        result = add_time_tracker_entry(
            name=data["name"],
            duration=data["duration"],
            satisfaction=data["satisfaction"],
            description=description
        )
        
        page_url = result.get("url", "#")
        response_text = (
            "✅ **Entry saved successfully to Notion!**\n\n"
            f"📌 **Task:** {data['name']}\n"
            f"⏱ **Duration:** {data['duration']} mins\n"
            f"⭐ **Satisfaction:** {data['satisfaction']}\n"
            f"📄 **Notes:** {description or 'None'}\n\n"
            f"[🔗 View in Notion]({page_url})"
        )
        await waiting_msg.edit_text(
            response_text,
            reply_markup=get_main_menu_keyboard(),
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except Exception as e:
        await waiting_msg.edit_text(
            f"❌ Error saving to Notion: {e}",
            reply_markup=get_main_menu_keyboard()
        )