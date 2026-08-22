import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")

NOTION_DBID_TIME_TRACKER = (
    os.getenv("NOTION_DBID_TIME_TRACKER") or 
    os.getenv("NOTION_DBID_Time_Tracker") or 
    os.getenv("NOTION_DATABASE_ID")
)

def _parse_user_ids(env_var_name: str) -> list[int]:
    raw = os.getenv(env_var_name, "")
    return [int(uid.strip()) for uid in raw.split(",") if uid.strip().isdigit()]

# Role-based User ID Lists
ADMIN_USERS = _parse_user_ids("ADMIN_USERS")
MANAGER_USERS = _parse_user_ids("MANAGER_USERS")
MEMBER_USERS = _parse_user_ids("MEMBER_USERS")
GUEST_USERS = _parse_user_ids("GUEST_USERS")

# Backward compatibility for legacy ALLOWED_USERS
LEGACY_ALLOWED = _parse_user_ids("ALLOWED_USERS")
if LEGACY_ALLOWED:
    for uid in LEGACY_ALLOWED:
        if uid not in ADMIN_USERS and uid not in MANAGER_USERS and uid not in MEMBER_USERS:
            ADMIN_USERS.append(uid)