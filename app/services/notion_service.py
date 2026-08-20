from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from notion_client import Client
from app.config import NOTION_TOKEN, NOTION_DBID_TIME_TRACKER

notion = Client(auth=NOTION_TOKEN)

def get_workspace_persons() -> List[Dict[str, str]]:
    """
    Fetches real workspace users (excluding bots) from Notion API.
    """
    try:
        response = notion.users.list()
        if not isinstance(response, dict):
            return []

        users = response.get("results", [])
        persons = []
        for user in users:
            if user.get("type") == "person":
                persons.append({
                    "id": user["id"],
                    "name": user.get("name", "Unknown")
                })
        return persons
    except Exception as e:
        print(f"Error fetching Notion users: {e}")
        return []

def add_time_tracker_entry(
    name: str,
    start_date_str: str,
    end_date_str: Optional[str],
    duration: int,
    satisfaction: str,
    person_id: Optional[str] = None,
    description: str = ""
) -> Any:
    """
    Creates a new row in the Time Tracker database in Notion.
    """
    if not NOTION_DBID_TIME_TRACKER:
        raise ValueError("NOTION_DBID_TIME_TRACKER is not defined in environment variables.")

    date_payload: Dict[str, Any] = {"start": start_date_str}
    if end_date_str:
        date_payload["end"] = end_date_str

    properties: Dict[str, Any] = {
        "Name": {
            "title": [{"text": {"content": name}}]
        },
        "MDuration": {
            "number": duration
        },
        "Date": {
            "date": date_payload
        },
        "Satisfaction": {
            "select": {"name": satisfaction}
        }
    }

    if person_id:
        properties["Person"] = {
            "people": [{"id": person_id}]
        }

    if description:
        properties["Description"] = {
            "rich_text": [{"text": {"content": description}}]
        }

    response = notion.pages.create(
        parent={"database_id": NOTION_DBID_TIME_TRACKER},
        properties=properties
    )
    return response