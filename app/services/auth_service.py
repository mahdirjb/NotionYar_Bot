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

# Runtime memory structure: {user_id: {"name": "...", "role": "..."}}
_user_data: Dict[int, Dict[str, str]] = {}


def _load_users() -> None:
    """Loads users from persistent JSON and merges with environment seed users."""
    global _user_data
    _user_data.clear()

    # 1. Load from environment seeds (default names)
    for uid in GUEST_USERS:
        _user_data[uid] = {"name": f"کاربر {uid}", "role": "guest"}
    for uid in MEMBER_USERS:
        _user_data[uid] = {"name": f"کاربر {uid}", "role": "member"}
    for uid in MANAGER_USERS:
        _user_data[uid] = {"name": f"کاربر {uid}", "role": "manager"}
    for uid in ADMIN_USERS:
        _user_data[uid] = {"name": f"ادمین {uid}", "role": "admin"}

    # 2. Merge with persistent JSON file if exists
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for uid_str, u_info in saved.items():
                    if uid_str.isdigit():
                        uid = int(uid_str)
                        if isinstance(u_info, dict):
                            _user_data[uid] = {
                                "name": u_info.get("name", f"کاربر {uid}"),
                                "role": u_info.get("role", "member")
                            }
                        elif isinstance(u_info, str) and u_info in ROLE_PERMISSIONS:
                            _user_data[uid] = {"name": f"کاربر {uid}", "role": u_info}
        except Exception as e:
            print(f"Error reading {USER_DB_FILE}: {e}")


def _save_users() -> None:
    """Saves current runtime users to users_db.json."""
    try:
        data_to_save = {str(uid): info for uid, info in _user_data.items()}
        with open(USER_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving to {USER_DB_FILE}: {e}")


# Initialize users on startup
_load_users()


def get_all_users() -> Dict[int, Dict[str, str]]:
    """Returns all registered users with their names and roles."""
    return dict(_user_data)


def get_user_role(user_id: Optional[int]) -> Optional[str]:
    """Returns the role of a user, or None if unauthorized."""
    if not user_id:
        return None
    info = _user_data.get(user_id)
    return info["role"] if info else None


def get_user_name(user_id: Optional[int]) -> str:
    """Returns the custom display name of a user."""
    if not user_id:
        return "ناشناس"
    info = _user_data.get(user_id)
    return info["name"] if info else f"کاربر {user_id}"


def set_user_role(user_id: int, role: str) -> bool:
    """Updates only the role of a user."""
    if role not in ROLE_PERMISSIONS:
        return False
    if user_id in _user_data:
        _user_data[user_id]["role"] = role
    else:
        _user_data[user_id] = {"name": f"کاربر {user_id}", "role": role}
    _save_users()
    return True


def set_user_name(user_id: int, name: str) -> bool:
    """Updates only the display name of a user."""
    if user_id in _user_data:
        _user_data[user_id]["name"] = name
        _save_users()
        return True
    return False


def add_or_update_user(user_id: int, name: str, role: str) -> bool:
    """Adds or updates both name and role for a user."""
    if role not in ROLE_PERMISSIONS:
        return False
    _user_data[user_id] = {"name": name.strip(), "role": role}
    _save_users()
    return True


def remove_user(user_id: int) -> bool:
    """Removes a user completely."""
    if user_id in _user_data:
        del _user_data[user_id]
        _save_users()
        return True
    return False


def has_permission(user_id: Optional[int], permission: str) -> bool:
    """Checks if a user has a specific permission."""
    if not user_id:
        return False
    
    role = get_user_role(user_id)
    if not role:
        return False

    user_perms = ROLE_PERMISSIONS.get(role, set())
    return PERM_ADMIN in user_perms or permission in user_perms


def is_user_registered(user_id: Optional[int]) -> bool:
    """Checks if user has any role in the system."""
    return get_user_role(user_id) is not None