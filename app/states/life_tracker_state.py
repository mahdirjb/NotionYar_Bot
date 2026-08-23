from aiogram.fsm.state import State, StatesGroup

class LifeTrackerCard(StatesGroup):
    viewing_card = State()
    typing_name = State()
    typing_notes = State()
    typing_custom_date = State()
    picking_modes = State()

class LifeTrackerReportState(StatesGroup):
    viewing_report = State()
    typing_custom_date_range = State()
    editing_name = State()
    editing_notes = State()
    editing_custom_date = State()