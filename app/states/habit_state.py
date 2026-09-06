# app/states/habit_state.py

from aiogram.fsm.state import State, StatesGroup


class HabitState(StatesGroup):
    waiting_for_custom_date = State()
    waiting_for_notes = State()
    waiting_for_gratitude_item = State()
    waiting_for_gratitude_edit = State()
    waiting_for_quran_detail = State()
    quick_run_active = State()