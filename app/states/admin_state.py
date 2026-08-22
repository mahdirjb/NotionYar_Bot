from aiogram.fsm.state import State, StatesGroup

class AdminState(StatesGroup):
    viewing_panel = State()
    typing_new_user_id = State()
    typing_new_user_name = State()
    editing_user_name = State()