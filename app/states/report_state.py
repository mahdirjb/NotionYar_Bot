from aiogram.fsm.state import State, StatesGroup

class ReportState(StatesGroup):
    viewing_report = State()
    typing_custom_date_range = State()
    editing_name = State()
    editing_description = State()
    editing_duration = State()