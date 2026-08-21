from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, cast
from notion_client import Client
from app.config import NOTION_TOKEN, NOTION_DBID_TIME_TRACKER

notion = Client(auth=NOTION_TOKEN)

def get_workspace_persons() -> List[Dict[str, str]]:
    """
    Dynamically fetches all persons: workspace members and database assignees.
    """
    found_people: Dict[str, str] = {}

    try:
        user_res = notion.users.list()
        if isinstance(user_res, dict):
            for u in user_res.get("results", []):
                if u.get("type") == "person":
                    found_people[u["id"]] = u.get("name", "Unknown")
    except Exception as e:
        print(f"Error fetching workspace members: {e}")

    try:
        if not NOTION_DBID_TIME_TRACKER:
            raise ValueError("NOTION_DBID_TIME_TRACKER is not defined in environment variables.")

        db_info = cast(
            Dict[str, Any],
            notion.databases.retrieve(database_id=NOTION_DBID_TIME_TRACKER),
        )
        data_sources = db_info.get("data_sources", [])
        if data_sources:
            ds_id = data_sources[0]["id"]
            query_res = notion.data_sources.query(data_source_id=ds_id, page_size=20)
            if isinstance(query_res, dict):
                for page in query_res.get("results", []):
                    props = page.get("properties", {})
                    for _, prop_val in props.items():
                        if prop_val.get("type") == "people":
                            for p in prop_val.get("people", []):
                                pid = p.get("id")
                                pname = p.get("name") or "Unknown"
                                if pid:
                                    found_people[pid] = pname
    except Exception as e:
        print(f"Error inspecting database people: {e}")

    known_seeds = {
        "e01a514e-a27b-4090-aadc-1f64cb85a0d7": "Mahdi Rajabzadeh",
        "3bcd872b-594c-8169-b346-00022faeece8": "Melika Bishbahar"
    }
    for sid, sname in known_seeds.items():
        found_people.setdefault(sid, sname)

    return [{"id": pid, "name": pname} for pid, pname in found_people.items()]


def add_time_tracker_entry(
    name: str,
    start_date_str: str,
    end_date_str: Optional[str] = None,
    duration: int = 0,
    satisfaction: Optional[str] = None,
    person_id: Optional[str] = None,
    description: str = ""
) -> Any:
    """
    Creates a new row in the Time Tracker database in Notion.
    Only provided optional fields are inserted.
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
        }
    }

    # Add optional satisfaction only if selected
    if satisfaction:
        properties["Satisfaction"] = {
            "select": {"name": satisfaction}
        }

    # Add optional person only if selected
    if person_id:
        properties["Person"] = {
            "people": [{"id": person_id}]
        }

    # Add optional description only if entered
    if description:
        properties["Description"] = {
            "rich_text": [{"text": {"content": description}}]
        }

    response = notion.pages.create(
        parent={"database_id": NOTION_DBID_TIME_TRACKER},
        properties=properties
    )
    return response