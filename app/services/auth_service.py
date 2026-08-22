from typing import Optional, Set
from app.config import ADMIN_USERS, MANAGER_USERS, MEMBER_USERS, GUEST_USERS

# Permission Constants
PERM_ADD_TIME = "add_time"
PERM_VIEW_REPORTS = "view_reports"
PERM_VIEW_ALL_USERS = "view_all_users"
PERM_EDIT_RECORDS = "edit_records"
PERM_DELETE_RECORDS = "delete_records"
PERM_ADMIN = "admin"

# Role -> Permissions Mapping
ROLE_PERMISSIONS: dict[str, Set[str]] = {
    "admin": {
        PERM_ADMIN,
        PERM_ADD_TIME,
        PERM_VIEW_REPORTS,
        PERM_VIEW_ALL_USERS,
        PERM_EDIT_RECORDS,
        PERM_DELETE_RECORDS,
    },
    "manager": {
        PERM_ADD_TIME,
        PERM_VIEW_REPORTS,
        PERM_VIEW_ALL_USERS,
        PERM_EDIT_RECORDS,
        PERM_DELETE_RECORDS,
    },
    "member": {
        PERM_ADD_TIME,
        PERM_VIEW_REPORTS,
    },
    "guest": {
        PERM_ADD_TIME,
    }
}


def get_user_role(user_id: Optional[int]) -> Optional[str]:
    """Returns the role name of a user, or None if unauthorized."""
    if not user_id:
        return None
    if user_id in ADMIN_USERS:
        return "admin"
    if user_id in MANAGER_USERS:
        return "manager"
    if user_id in MEMBER_USERS:
        return "member"
    if user_id in GUEST_USERS:
        return "guest"
    return None


def has_permission(user_id: Optional[int], permission: str) -> bool:
    """
    Checks if a user has a specific permission.
    Admins always have all permissions.
    """
    if not user_id:
        return False
    
    role = get_user_role(user_id)
    if not role:
        return False

    user_perms = ROLE_PERMISSIONS.get(role, set())
    return PERM_ADMIN in user_perms or permission in user_perms


def is_user_registered(user_id: Optional[int]) -> bool:
    """Checks if the user has any role in the system."""
    return get_user_role(user_id) is not None