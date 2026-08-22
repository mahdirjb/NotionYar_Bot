from aiogram.fsm.state import State, StatesGroup

class ReportState(StatesGroup):
    viewing_report = State()