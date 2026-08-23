from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, cast
from notion_client import Client
from app.config import (
    NOTION_TOKEN,
    NOTION_DBID_TIME_TRACKER,
    NOTION_DBID_LIFE_TRACKER,
    NOTION_LIFE_TRACKER_INTERVALS_PAGE_ID
)

notion = Client(auth=NOTION_TOKEN)

# ==========================================
# 🌿 LIFE TRACKER CONSTANTS & MAPPINGS
# ==========================================

LIFE_TRACKER_TYPES: List[str] = [
    "مریضی",
    "رانندگی",
    "موپالمو",
    "ریش و سبیل",
    "خورشید",
    "آینه",
    "دوری",
    "آرایشگاه",
    "ناخن دست",
    "ناخن پا",
    "ویتامین دی",
    "خرید",
    "اتفاقات",
    "سایر"
]

TYPE_MODE_MAPPING: Dict[str, List[str]] = {
    "مریضی": ["سرماخوردگی", "سردرد"],
    "رانندگی": ["پارک", "در پارکینگ", "شهر", "اتوبان"],
    "موپالمو": ["ساق", "کل", "شانه کوچک", "شانه بزرگ"],
    "ریش و سبیل": ["ریش", "سبیل", "کوتاه‌کردن", "مرتب‌کردن"],
    "خورشید": ["نوره", "ژیلت"],
    "آینه": ["نوره", "ژیلت"],
    "دوری": ["شب"],
}

TYPE_EMOJIS: Dict[str, str] = {
    "مریضی": "🤒",
    "سایر": "📦",
    "رانندگی": "🚗",
    "اتفاقات": "⚡",
    "خرید": "🛒",
    "ویتامین دی": "💊",
    "آرایشگاه": "💈",
    "موپالمو": "🪒",
    "ریش و سبیل": "🧔",
    "دوری": "🌙",
    "آینه": "🪞",
    "خورشید": "☀️",
    "ناخن پا": "🦶",
    "ناخن دست": "💅"
}

MODE_EMOJIS: Dict[str, str] = {
    "سرماخوردگی": "🤧",
    "سردرد": "🤕",
    "پارک": "🅿️",
    "در پارکینگ": "🏢",
    "شهر": "🏙",
    "اتوبان": "🛣",
    "ساق": "🦵",
    "کل": "✨",
    "شانه کوچک": "🪮",
    "شانه بزرگ": "🪮",
    "نوره": "🌿",
    "ژیلت": "🪒",
    "مرتب کردن": "✂️",
    "کوتاه کردن": "✂️",
    "مرتب‌کردن": "✂️",
    "کوتاه‌کردن": "✂️",
    "سبیل": "🧔‍♂️",
    "ریش": "🧔",
    "شب": "🌌"
}

# ==========================================
# ⏱ TIME TRACKER FUNCTIONS
# ==========================================

def get_workspace_persons() -> List[Dict[str, str]]:
    """Dynamically fetches all persons: workspace members and database assignees."""
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
    """Creates a new row in the Time Tracker database in Notion."""
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

    if satisfaction:
        properties["Satisfaction"] = {
            "select": {"name": satisfaction}
        }

    if person_id:
        properties["Person"] = {
            "people": [{"id": person_id}]
        }

    if description:
        properties["Description"] = {
            "rich_text": [{"text": {"content": description}}]
        }

    return notion.pages.create(
        parent={"database_id": NOTION_DBID_TIME_TRACKER},
        properties=properties
    )


_cached_time_tracker_ds_id: Optional[str] = None

def get_time_tracker_data_source_id() -> str:
    """Retrieves and caches the data_source_id of the Time Tracker database."""
    global _cached_time_tracker_ds_id
    if _cached_time_tracker_ds_id:
        return _cached_time_tracker_ds_id

    if not NOTION_DBID_TIME_TRACKER:
        raise ValueError("NOTION_DBID_TIME_TRACKER is not defined in environment variables.")

    db_info = cast(
        Dict[str, Any],
        notion.databases.retrieve(database_id=NOTION_DBID_TIME_TRACKER),
    )
    data_sources = db_info.get("data_sources", [])
    if data_sources:
        _cached_time_tracker_ds_id = data_sources[0]["id"]
        return _cached_time_tracker_ds_id

    return NOTION_DBID_TIME_TRACKER


def query_time_tracker_entries(
    start_date_iso: str,
    end_date_iso: Optional[str] = None,
    person_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Queries time tracker entries within a date range and optional person filter."""
    ds_id = get_time_tracker_data_source_id()
    and_filters: List[Dict[str, Any]] = []

    if end_date_iso and end_date_iso != start_date_iso:
        and_filters.append({
            "property": "Date",
            "date": {"on_or_after": start_date_iso}
        })
        and_filters.append({
            "property": "Date",
            "date": {"on_or_before": end_date_iso}
        })
    else:
        and_filters.append({
            "property": "Date",
            "date": {"equals": start_date_iso}
        })

    if person_id:
        and_filters.append({
            "property": "Person",
            "people": {"contains": person_id}
        })

    filter_payload = {"and": and_filters} if len(and_filters) > 1 else and_filters[0]

    if hasattr(notion, "data_sources") and hasattr(notion.data_sources, "query"):
        query_res = notion.data_sources.query(
            data_source_id=ds_id,
            filter=filter_payload,
            sorts=[{"property": "Date", "direction": "descending"}]
        )
    else:
        query_res = notion.databases.query( # type: ignore
            database_id=NOTION_DBID_TIME_TRACKER,
            filter=filter_payload,
            sorts=[{"property": "Date", "direction": "descending"}]
        )

    parsed_entries: List[Dict[str, Any]] = []
    results = query_res.get("results", []) if isinstance(query_res, dict) else []

    for page in results:
        props = page.get("properties", {})
        title_list = props.get("Name", {}).get("title", [])
        name = title_list[0].get("plain_text", "بدون عنوان") if title_list else "بدون عنوان"

        date_prop = props.get("Date", {}).get("date") or {}
        raw_start = date_prop.get("start")
        raw_end = date_prop.get("end")

        m_duration = props.get("MDuration", {}).get("number")
        satisfaction = (props.get("Satisfaction", {}).get("select") or {}).get("name")

        people = props.get("Person", {}).get("people", [])
        person_name = people[0].get("name", "نامشخص") if people else None
        page_person_id = people[0].get("id") if people else None

        desc_list = props.get("Description", {}).get("rich_text", [])
        description = desc_list[0].get("plain_text", "") if desc_list else ""

        parsed_entries.append({
            "id": page.get("id"),
            "name": name,
            "start_iso": raw_start,
            "end_iso": raw_end,
            "duration": m_duration,
            "satisfaction": satisfaction,
            "person_name": person_name,
            "person_id": page_person_id,
            "description": description,
            "url": page.get("url", "")
        })

    return parsed_entries


def get_time_tracker_entry(page_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves and parses a single time tracker page by page_id."""
    try:
        page = notion.pages.retrieve(page_id=page_id)
        if not isinstance(page, dict):
            return None

        props = page.get("properties", {})
        title_list = props.get("Name", {}).get("title", [])
        name = title_list[0].get("plain_text", "بدون عنوان") if title_list else "بدون عنوان"

        date_prop = props.get("Date", {}).get("date") or {}
        raw_start = date_prop.get("start")
        raw_end = date_prop.get("end")

        m_duration = props.get("MDuration", {}).get("number")
        satisfaction = (props.get("Satisfaction", {}).get("select") or {}).get("name")

        people = props.get("Person", {}).get("people", [])
        person_name = people[0].get("name", "نامشخص") if people else None
        page_person_id = people[0].get("id") if people else None

        desc_list = props.get("Description", {}).get("rich_text", [])
        description = desc_list[0].get("plain_text", "") if desc_list else ""

        return {
            "id": page.get("id"),
            "name": name,
            "start_iso": raw_start,
            "end_iso": raw_end,
            "duration": m_duration,
            "satisfaction": satisfaction,
            "person_name": person_name,
            "person_id": page_person_id,
            "description": description,
            "url": page.get("url", "")
        }
    except Exception as e:
        print(f"Error retrieving entry {page_id}: {e}")
        return None


# ==========================================
# 🌿 LIFE TRACKER FUNCTIONS
# ==========================================

_cached_life_tracker_ds_id: Optional[str] = None

def get_life_tracker_data_source_id() -> str:
    """Retrieves and caches the data_source_id of the Life Tracker database."""
    global _cached_life_tracker_ds_id
    if _cached_life_tracker_ds_id:
        return _cached_life_tracker_ds_id

    if not NOTION_DBID_LIFE_TRACKER:
        raise ValueError("NOTION_DBID_LIFE_TRACKER is not defined in environment variables.")

    db_info = cast(
        Dict[str, Any],
        notion.databases.retrieve(database_id=NOTION_DBID_LIFE_TRACKER),
    )
    data_sources = db_info.get("data_sources", [])
    if data_sources:
        _cached_life_tracker_ds_id = data_sources[0]["id"]
        return _cached_life_tracker_ds_id

    return NOTION_DBID_LIFE_TRACKER


def add_life_tracker_entry(
    name: str,
    type_val: str,
    date_iso: str,
    mode_list: Optional[List[str]] = None,
    notes: str = ""
) -> Any:
    """
    Creates a new row in the Life Tracker database in Notion.
    Automatically links to the default Intervals page.
    """
    if not NOTION_DBID_LIFE_TRACKER:
        raise ValueError("NOTION_DBID_LIFE_TRACKER is not defined in environment variables.")

    properties: Dict[str, Any] = {
        "Name": {
            "title": [{"text": {"content": name}}]
        },
        "Type": {
            "select": {"name": type_val}
        },
        "Date_": {
            "date": {"start": date_iso}
        }
    }

    # Automatically link to the default Intervals page if configured
    if NOTION_LIFE_TRACKER_INTERVALS_PAGE_ID:
        properties["Intervals"] = {
            "relation": [{"id": NOTION_LIFE_TRACKER_INTERVALS_PAGE_ID}]
        }

    if mode_list:
        properties["Mode"] = {
            "multi_select": [{"name": m} for m in mode_list]
        }

    if notes:
        properties["Notes"] = {
            "rich_text": [{"text": {"content": notes}}]
        }

    return notion.pages.create(
        parent={"database_id": NOTION_DBID_LIFE_TRACKER},
        properties=properties
    )

def query_life_tracker_entries(
    start_date_iso: Optional[str] = None,
    end_date_iso: Optional[str] = None,
    type_val: Optional[str] = None,
    mode_val: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Queries life tracker entries from Notion with date range, Type and Mode filters.
    """
    ds_id = get_life_tracker_data_source_id()
    and_filters: List[Dict[str, Any]] = []

    # 1. Date filter on Date_ property
    if start_date_iso:
        if end_date_iso and end_date_iso != start_date_iso:
            and_filters.append({
                "property": "Date_",
                "date": {"on_or_after": start_date_iso}
            })
            and_filters.append({
                "property": "Date_",
                "date": {"on_or_before": end_date_iso}
            })
        else:
            and_filters.append({
                "property": "Date_",
                "date": {"equals": start_date_iso}
            })

    # 2. Type filter
    if type_val and type_val != "all":
        and_filters.append({
            "property": "Type",
            "select": {"equals": type_val}
        })

    # 3. Mode filter
    if mode_val and mode_val != "all":
        and_filters.append({
            "property": "Mode",
            "multi_select": {"contains": mode_val}
        })

    filter_payload = None
    if len(and_filters) == 1:
        filter_payload = and_filters[0]
    elif len(and_filters) > 1:
        filter_payload = {"and": and_filters}

    # Query Notion
    kwargs: Dict[str, Any] = {
        "data_source_id": ds_id,
        "sorts": [{"property": "Date_", "direction": "descending"}]
    }
    if filter_payload:
        kwargs["filter"] = filter_payload

    if hasattr(notion, "data_sources") and hasattr(notion.data_sources, "query"):
        query_res = notion.data_sources.query(**kwargs)
    else:
        kwargs.pop("data_source_id", None)
        kwargs["database_id"] = NOTION_DBID_LIFE_TRACKER
        if filter_payload:
            kwargs["filter"] = filter_payload
        query_res = notion.databases.query(**kwargs) # type: ignore

    parsed_entries: List[Dict[str, Any]] = []
    results = query_res.get("results", []) if isinstance(query_res, dict) else []

    for page in results:
        props = page.get("properties", {})

        title_list = props.get("Name", {}).get("title", [])
        name = title_list[0].get("plain_text", "بدون عنوان") if title_list else "بدون عنوان"

        t_val = (props.get("Type", {}).get("select") or {}).get("name", "نامشخص")
        
        mode_items = props.get("Mode", {}).get("multi_select", [])
        modes = [m.get("name") for m in mode_items if m.get("name")]

        date_prop = props.get("Date_", {}).get("date") or {}
        raw_date = date_prop.get("start")

        notes_list = props.get("Notes", {}).get("rich_text", [])
        notes = notes_list[0].get("plain_text", "") if notes_list else ""

        parsed_entries.append({
            "id": page.get("id"),
            "name": name,
            "type": t_val,
            "modes": modes,
            "date_iso": raw_date,
            "notes": notes,
            "url": page.get("url", "")
        })

    return parsed_entries


def get_life_tracker_entry(page_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves and parses a single life tracker entry by page_id."""
    try:
        page = notion.pages.retrieve(page_id=page_id)
        if not isinstance(page, dict):
            return None

        props = page.get("properties", {})

        title_list = props.get("Name", {}).get("title", [])
        name = title_list[0].get("plain_text", "بدون عنوان") if title_list else "بدون عنوان"

        t_val = (props.get("Type", {}).get("select") or {}).get("name", "نامشخص")
        
        mode_items = props.get("Mode", {}).get("multi_select", [])
        modes = [m.get("name") for m in mode_items if m.get("name")]

        date_prop = props.get("Date_", {}).get("date") or {}
        raw_date = date_prop.get("start")

        notes_list = props.get("Notes", {}).get("rich_text", [])
        notes = notes_list[0].get("plain_text", "") if notes_list else ""

        return {
            "id": page.get("id"),
            "name": name,
            "type": t_val,
            "modes": modes,
            "date_iso": raw_date,
            "notes": notes,
            "url": page.get("url", "")
        }
    except Exception as e:
        print(f"Error retrieving life tracker entry {page_id}: {e}")
        return None


# ==========================================
# 🛠 GENERAL NOTION HELPERS
# ==========================================

def archive_notion_page(page_id: str) -> bool:
    """Archives (deletes) a page from any Notion database."""
    try:
        notion.pages.update(page_id=page_id, archived=True)
        return True
    except Exception as e:
        print(f"Error archiving Notion page {page_id}: {e}")
        return False


def update_notion_page_properties(page_id: str, properties: Dict[str, Any]) -> bool:
    """Updates specific properties of an existing page in Notion."""
    try:
        notion.pages.update(page_id=page_id, properties=properties)
        return True
    except Exception as e:
        print(f"Error updating Notion page {page_id}: {e}")
        return False