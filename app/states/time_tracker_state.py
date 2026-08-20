from aiogram.fsm.state import State, StatesGroup

class TimeTrackerCard(StatesGroup):
    viewing_card = State()
    typing_name = State()
    typing_description = State()
    typing_custom_date = State()
    typing_custom_time = State()
    typing_custom_duration = State()