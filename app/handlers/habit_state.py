# app/states/habit_state.py

from aiogram.fsm.state import State, StatesGroup


class HabitState(StatesGroup):
    waiting_for_custom_date = State()
    waiting_for_notes = State()