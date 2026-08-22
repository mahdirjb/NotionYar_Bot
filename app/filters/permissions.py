from aiogram.filters import Filter
from aiogram.types import Message, CallbackQuery
from app.services.auth_service import has_permission

class HasPermission(Filter):
    """
    Custom aiogram filter that validates whether the user has the required permission.
    """
    def __init__(self, permission: str):
        self.permission = permission

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_id = event.from_user.id if event.from_user else None
        return has_permission(user_id, self.permission)