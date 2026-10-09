# app/states/spiritual_state.py

from aiogram.fsm.state import State, StatesGroup

class SpiritualState(StatesGroup):
    waiting_for_custom_date = State()
    waiting_for_notes = State()
    waiting_for_quran_pages = State()
    waiting_for_quran_title = State()
    waiting_for_custom_report_range = State()
    waiting_for_bulk_range = State()
