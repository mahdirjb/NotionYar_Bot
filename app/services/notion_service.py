from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, cast
from notion_client import Client
from app.config import NOTION_TOKEN, NOTION_DBID_TIME_TRACKER

notion = Client(auth=NOTION_TOKEN)

def get_workspace_persons() -> List[Dict[str, str]]:
    """
    Fetches real workspace users (excluding bots) from Notion API.
    """
    try:
        # The Notion client's type stubs incorrectly describe this call as
        # returning an awaitable, although the synchronous Client returns a
        # response dictionary directly.
        response = cast(Any, notion.users.list())
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
    start_iso: str,
    end_iso: Optional[str],
    duration: int,
    satisfaction: str,
    person_id: Optional[str] = None,
    description: str = ""
) -> Dict[str, Any]:
    """
    Creates a new row in the Time Tracker database with start/end time and person.
    """
    date_prop = {"start": start_iso}
    if end_iso:
        date_prop["end"] = end_iso

    properties: Dict[str, Any] = {
        "Name": {
            "title": [{"text": {"content": name}}]
        },
        "MDuration": {
            "number": duration
        },
        "Date": {
            "date": date_prop
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
    return cast(Dict[str, Any], response)