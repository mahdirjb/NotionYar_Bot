# app/services/notion_service.py

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, cast
from notion_client import Client
from app.config import (
    NOTION_TOKEN,
    NOTION_DBID_TIME_TRACKER,
    NOTION_DBID_LIFE_TRACKER,
    NOTION_DBID_HABITS,
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
    Automatically links to the default Intervals page if configured.
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

    if type_val and type_val != "all":
        and_filters.append({
            "property": "Type",
            "select": {"equals": type_val}
        })

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
    
# ==========================================
# 🎯 HABIT TRACKER CONSTANTS & FUNCTIONS (V2.0)
# ==========================================

# 12 Habits Mapping with Persian names, emojis, and 2-3 letter Stealth Codes
HABIT_ITEMS: Dict[str, Dict[str, str]] = {
    "bt": {"prop": "Brush Teeth", "fa": "مسواک", "emoji": "🪥", "code": "BST", "cat": "جسمی"},
    "fr": {"prop": "Face Routine", "fa": "روتین پوستی", "emoji": "🧖", "code": "SKN", "cat": "جسمی"},
    "mb": {"prop": "Make the Bed", "fa": "مرتب‌کردن تخت", "emoji": "🛏️", "code": "BDM", "cat": "نظم"},
    "ex": {"prop": "Exercise", "fa": "ورزش", "emoji": "🏃", "code": "WKO", "cat": "جسمی"},
    "md": {"prop": "Meditation", "fa": "مدیتیشن", "emoji": "🧘", "code": "MDT", "cat": "ذهنی"},
    "gr": {"prop": "Gratitude", "fa": "شکرگزاری", "emoji": "🌸", "code": "THG", "cat": "ذهنی"},
    "rq": {"prop": "Read Holy Quran", "fa": "تلاوت قرآن", "emoji": "📖", "code": "QRN", "cat": "معنوی"},
    "sl": {"prop": "Salam", "fa": "سلام", "emoji": "🕊️", "code": "SLM", "cat": "معنوی"},
    "es": {"prop": "Esteghfar", "fa": "استغفار", "emoji": "📿", "code": "EST", "cat": "معنوی"},
    "ps": {"prop": "Pray After Salah", "fa": "تعقیبات نماز", "emoji": "🤲", "code": "PAS", "cat": "معنوی"},
    "bp": {"prop": "Bedtime Prayer", "fa": "دعای قبل خواب", "emoji": "🌙", "code": "BDP", "cat": "معنوی"},
    "sg": {"prop": "Spritual Gift", "fa": "هدیه معنوی", "emoji": "🎁", "code": "SPG", "cat": "معنوی"}
}

HABIT_LEVELS: Dict[str, str] = {
    "1": "1-💪 کامل",
    "2": "2-🏃‍♂️ نیمه‌کامل",
    "3": "3-🐢 سبک",
    "4": "4-❌ با دلیل",
    "5": "5-⛔ بدون دلیل"
}

LEVEL_BADGES: Dict[str, str] = {
    "1-💪 کامل": "💪 کامل",
    "2-🏃‍♂️ نیمه‌کامل": "🏃‍♂️ نیمه‌کامل",
    "3-🐢 سبک": "🐢 سبک",
    "4-❌ با دلیل": "❌ با دلیل",
    "5-⛔ بدون دلیل": "⛔ بدون دلیل"
}

def get_persian_cheerleader(progress_float: float) -> str:
    """Generates warm, colloquial Persian motivational feedback based on progress percentage."""
    pct = max(0.0, min(1.0, progress_float))
    if pct >= 1.0:
        return "👑 سلطان نظم و اراده! امروز رو ترکوندی، دمت گرم."
    elif pct >= 0.80:
        return "🔥 فوق‌العاده بود! بخش اعظم روزت با اقتدار برنده شد."
    elif pct >= 0.50:
        return "🏃‍♂️ دمت گرم، بیشتر از نصف مسیر رو رفتی. روز قابل قبولی بود."
    elif pct >= 0.25:
        return "🐢 پایبندی حداقلی هم پیروزیه! استمرار از کمال‌گرایی مهم‌تره."
    elif pct > 0.0:
        return "🌱 هنوز وقت هست؛ یه حرکت کوچیک بزن که زنجیره قطع نشه."
    else:
        return "☕ روز هنوز شروع نشده؛ برو جلو که امروز مال خودته!"

_cached_habits_ds_id: Optional[str] = None

def get_habits_data_source_id() -> str:
    """Retrieves and caches the data_source_id of the Habit Tracker database."""
    global _cached_habits_ds_id
    if _cached_habits_ds_id:
        return _cached_habits_ds_id

    if not NOTION_DBID_HABITS:
        raise ValueError("NOTION_DBID_HABITS is not defined in environment variables.")

    db_info = cast(
        Dict[str, Any],
        notion.databases.retrieve(database_id=NOTION_DBID_HABITS),
    )
    data_sources = db_info.get("data_sources", [])
    if data_sources:
        _cached_habits_ds_id = data_sources[0]["id"]
        return _cached_habits_ds_id

    return NOTION_DBID_HABITS


def get_or_create_habit_day(date_iso: str, day_title: str = "New Habit") -> Dict[str, Any]:
    """
    Finds existing habit page for the given date, or creates a new row if none exists.
    """
    if not NOTION_DBID_HABITS:
        raise ValueError("NOTION_DBID_HABITS is not defined in environment variables.")

    ds_id = get_habits_data_source_id()
    filter_payload = {"property": "Date_", "date": {"equals": date_iso}}

    if hasattr(notion, "data_sources") and hasattr(notion.data_sources, "query"):
        query_res = notion.data_sources.query(
            data_source_id=ds_id,
            filter=filter_payload,
            page_size=1
        )
    else:
        query_res = notion.databases.query( # type: ignore
            database_id=NOTION_DBID_HABITS,
            filter=filter_payload,
            page_size=1
        )

    results = query_res.get("results", []) if isinstance(query_res, dict) else []

    if results:
        page = results[0]
    else:
        create_props: Dict[str, Any] = {
            "Day": {"title": [{"text": {"content": day_title}}]},
            "Date_": {"date": {"start": date_iso}}
        }
        page = notion.pages.create(
            parent={"database_id": NOTION_DBID_HABITS},
            properties=create_props
        )

    return parse_habit_page(page)


def parse_habit_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Parses a Notion habit page into a clean Python dictionary."""
    props = page.get("properties", {})

    title_list = props.get("Day", {}).get("title", [])
    day_name = title_list[0].get("plain_text", "New Habit") if title_list else "New Habit"

    date_prop = props.get("Date_", {}).get("date") or {}
    raw_date = date_prop.get("start", "")

    # Progress formula
    prog_prop = props.get("Progress", {}).get("formula", {})
    progress_val = prog_prop.get("number", 0.0) if prog_prop.get("type") == "number" else 0.0

    # Notes
    notes_list = props.get("Notes", {}).get("rich_text", [])
    notes = notes_list[0].get("plain_text", "") if notes_list else ""

    # Gratitude Log (Rich Text)
    grat_list = props.get("Gratitude Log", {}).get("rich_text", [])
    gratitude_log = grat_list[0].get("plain_text", "") if grat_list else ""

    # 12 Habits values
    habits_status = {}
    for h_key, h_info in HABIT_ITEMS.items():
        prop_name = h_info["prop"]
        sel_val = (props.get(prop_name, {}).get("select") or {}).get("name")
        habits_status[h_key] = sel_val

    return {
        "id": page.get("id"),
        "day_name": day_name,
        "date_iso": raw_date,
        "progress": progress_val,
        "cheerleader": get_persian_cheerleader(progress_val),
        "notes": notes,
        "gratitude_log": gratitude_log,
        "habits": habits_status,
        "url": page.get("url", "")
    }


def update_habit_entry(page_id: str, habit_prop_name: str, select_val: Optional[str]) -> bool:
    """Updates a single habit property (or clears it if select_val is None)."""
    try:
        val_payload = {"name": select_val} if select_val else None
        notion.pages.update(
            page_id=page_id,
            properties={habit_prop_name: {"select": val_payload}}
        )
        return True
    except Exception as e:
        print(f"Error updating habit {habit_prop_name}: {e}")
        return False


def bulk_update_all_habits(page_id: str, select_val: Optional[str]) -> bool:
    """Updates all 12 habits at once (e.g. mark all complete or reset)."""
    try:
        val_payload = {"name": select_val} if select_val else None
        update_props = {
            h_info["prop"]: {"select": val_payload}
            for h_info in HABIT_ITEMS.values()
        }
        notion.pages.update(page_id=page_id, properties=update_props)
        return True
    except Exception as e:
        print(f"Error bulk updating habits: {e}")
        return False


def batch_update_habit_dict(page_id: str, habit_dict: Dict[str, Optional[str]]) -> bool:
    """Updates multiple specific habits in a single API call (used by Quick-Run Wizard)."""
    try:
        update_props = {}
        for h_key, sel_val in habit_dict.items():
            if h_key in HABIT_ITEMS:
                prop_name = HABIT_ITEMS[h_key]["prop"]
                val_payload = {"name": sel_val} if sel_val else None
                update_props[prop_name] = {"select": val_payload}

        if update_props:
            notion.pages.update(page_id=page_id, properties=update_props)
        return True
    except Exception as e:
        print(f"Error batch updating habits: {e}")
        return False


def update_habit_notes(page_id: str, notes: str) -> bool:
    """Updates the rich_text Notes property for a habit day."""
    try:
        payload = [{"text": {"content": notes}}] if notes else []
        notion.pages.update(
            page_id=page_id,
            properties={"Notes": {"rich_text": payload}}
        )
        return True
    except Exception as e:
        print(f"Error updating habit notes: {e}")
        return False


def update_habit_gratitude(page_id: str, gratitude_text: str) -> bool:
    """Updates the rich_text Gratitude Log property for a habit day."""
    try:
        payload = [{"text": {"content": gratitude_text}}] if gratitude_text else []
        notion.pages.update(
            page_id=page_id,
            properties={"Gratitude Log": {"rich_text": payload}}
        )
        return True
    except Exception as e:
        print(f"Error updating habit gratitude log: {e}")
        return False


def reset_habit_day(page_id: str) -> bool:
    """Safely resets all 12 habits, notes, and gratitude log for a day."""
    try:
        reset_props: Dict[str, Any] = {
            h_info["prop"]: {"select": None}
            for h_info in HABIT_ITEMS.values()
        }
        reset_props["Notes"] = {"rich_text": []}
        reset_props["Gratitude Log"] = {"rich_text": []}

        notion.pages.update(page_id=page_id, properties=reset_props)
        return True
    except Exception as e:
        print(f"Error resetting habit day: {e}")
        return False