from aiogram.fsm.state import State, StatesGroup

class TimeTrackerCard(StatesGroup):
    viewing_card = State()
    typing_name = State()
    typing_description = State()