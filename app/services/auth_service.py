import json
import os
from typing import Optional, Set, Dict
from app.config import ADMIN_USERS, MANAGER_USERS, MEMBER_USERS, GUEST_USERS

USER_DB_FILE = "users_db.json"

# Permission Constants
PERM_ADD_TIME = "add_time"
PERM_VIEW_REPORTS = "view_reports"
PERM_VIEW_ALL_USERS = "view_all_users"
PERM_EDIT_RECORDS = "edit_records"
PERM_DELETE_RECORDS = "delete_records"
PERM_ADMIN = "admin"

# Role -> Permissions Mapping
ROLE_PERMISSIONS: Dict[str, Set[str]] = {
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

# Runtime memory user roles cache
_user_roles: Dict[int, str] = {}


def _load_users() -> None:
    """Loads users from users_db.json and merges with environment seed users."""
    global _user_roles
    _user_roles.clear()

    # 1. Load from environment seeds
    for uid in GUEST_USERS:
        _user_roles[uid] = "guest"
    for uid in MEMBER_USERS:
        _user_roles[uid] = "member"
    for uid in MANAGER_USERS:
        _user_roles[uid] = "manager"
    for uid in ADMIN_USERS:
        _user_roles[uid] = "admin"

    # 2. Merge with persistent JSON file if exists
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, "r", encoding="utf-8") as f:
                saved_users = json.load(f)
                for uid_str, role in saved_users.items():
                    if uid_str.isdigit() and role in ROLE_PERMISSIONS:
                        _user_roles[int(uid_str)] = role
        except Exception as e:
            print(f"Error reading {USER_DB_FILE}: {e}")


def _save_users() -> None:
    """Saves current runtime users to users_db.json."""
    try:
        data_to_save = {str(uid): role for uid, role in _user_roles.items()}
        with open(USER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving to {USER_DB_FILE}: {e}")


# Initialize users on startup
_load_users()


def get_all_users() -> Dict[int, str]:
    """Returns a dictionary of all registered user_ids and their roles."""
    return dict(_user_roles)


def get_user_role(user_id: Optional[int]) -> Optional[str]:
    """Returns the role name of a user, or None if unauthorized."""
    if not user_id:
        return None
    return _user_roles.get(user_id)


def set_user_role(user_id: int, role: str) -> bool:
    """Adds or updates a user role dynamically and persists to disk."""
    if role not in ROLE_PERMISSIONS:
        return False
    _user_roles[user_id] = role
    _save_users()
    return True


def remove_user(user_id: int) -> bool:
    """Removes a user and their access completely."""
    if user_id in _user_roles:
        del _user_roles[user_id]
        _save_users()
        return True
    return False


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