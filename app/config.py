import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DBID_TIME_TRACKER = os.getenv("NOTION_DBID_TIME_TRACKER")

# Parse allowed user IDs into a list of integers
raw_users = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [int(uid.strip()) for uid in raw_users.split(",") if uid.strip().isdigit()]