# app/config.py

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")


def _clean_database_id(raw_id: str | None) -> str | None:
    """
    Cleans Notion Database or Page ID by removing URL prefixes and query params (like ?v=...).
    """
    if not raw_id:
        return None
    cleaned = raw_id.strip()
    if "?" in cleaned:
        cleaned = cleaned.split("?")[0]
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]
    return cleaned


NOTION_DBID_TIME_TRACKER = _clean_database_id(
    os.getenv("NOTION_DBID_TIME_TRACKER") or 
    os.getenv("NOTION_DBID_Time_Tracker") or 
    os.getenv("NOTION_DATABASE_ID")
)

NOTION_DBID_LIFE_TRACKER = _clean_database_id(os.getenv("NOTION_DBID_LIFE_TRACKER"))
NOTION_DBID_HABITS = _clean_database_id(os.getenv("NOTION_DBID_HABITS"))

# Default Page ID for Life Tracker 'Intervals' relation field
NOTION_LIFE_TRACKER_INTERVALS_PAGE_ID = _clean_database_id(
    os.getenv("NOTION_LIFE_TRACKER_INTERVALS_PAGE_ID") or "1e3a75a2561480ba972bcecbf620304f"
)


def _parse_user_ids(env_var_name: str) -> list[int]:
    raw = os.getenv(env_var_name, "")
    return [int(uid.strip()) for uid in raw.split(",") if uid.strip().isdigit()]


# Role-based User ID Lists
ADMIN_USERS = _parse_user_ids("ADMIN_USERS")
MANAGER_USERS = _parse_user_ids("MANAGER_USERS")
MEMBER_USERS = _parse_user_ids("MEMBER_USERS")
GUEST_USERS = _parse_user_ids("GUEST_USERS")

# Fallback: Anyone in legacy ALLOWED_USERS defaults to a standard MEMBER (Safe default)
LEGACY_ALLOWED = _parse_user_ids("ALLOWED_USERS")
if LEGACY_ALLOWED:
    for uid in LEGACY_ALLOWED:
        if uid not in ADMIN_USERS and uid not in MANAGER_USERS and uid not in MEMBER_USERS and uid not in GUEST_USERS:
            MEMBER_USERS.append(uid)