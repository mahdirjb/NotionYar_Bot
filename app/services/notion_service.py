from datetime import datetime, timezone, timedelta
from notion_client import Client
from app.config import NOTION_TOKEN, NOTION_DBID_TIME_TRACKER

notion = Client(auth=NOTION_TOKEN)

def add_time_tracker_entry(name: str, duration: int, satisfaction: str, description: str = "") -> dict:
    """
    Creates a new row in the Time Tracker database in Notion.
    """
    tz = timezone(timedelta(hours=3, minutes=30))
    now = datetime.now(tz).isoformat()
    
    properties = {
        "Name": {
            "title": [
                {"text": {"content": name}}
            ]پ
        },
        "MDuration": {
            "number": duration
        },
        "Date": {
            "date": {
                "start": now
            }
        },
        "Satisfaction": {
            "select": {
                "name": satisfaction
            }
        }
    }
    
    if description:
        properties["Description"] = {
            "rich_text": [
                {"text": {"content": description}}
            ]
        }
        
    response = notion.pages.create(
        parent={"database_id": NOTION_DBID_TIME_TRACKER},
        properties=properties
    )
    return response