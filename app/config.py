import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")

# Fallback to handle both case conventions in Railway
NOTION_DBID_TIME_TRACKER = (
    os.getenv("NOTION_DBID_TIME_TRACKER") or 
    os.getenv("NOTION_DBID_Time_Tracker") or 
    os.getenv("NOTION_DATABASE_ID")
)

raw_users = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [int(uid.strip()) for uid in raw_users.split(",") if uid.strip().isdigit()]