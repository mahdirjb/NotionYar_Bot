from aiogram.fsm.state import State, StatesGroup

class TimeTrackerForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_duration = State()
    waiting_for_satisfaction = State()
    waiting_for_description = State()