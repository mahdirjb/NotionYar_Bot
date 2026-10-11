# app/services/notion_service.py

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, cast
from notion_client import Client
from app.config import (
    NOTION_TOKEN,
    NOTION_DBID_TIME_TRACKER,
    NOTION_DBID_LIFE_TRACKER,
    NOTION_DBID_HABITS,
    NOTION_DBID_SALAH,
    NOTION_DBID_QURAN,
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


def update_life_tracker_entry(
    page_id: str,
    type_val: Optional[str] = None,
    date_iso: Optional[str] = None,
    mode_list: Optional[List[str]] = None,
    notes: Optional[str] = None
) -> bool:
    """Updates an existing row in the Life Tracker database in Notion."""
    properties: Dict[str, Any] = {}
    clean_date = str(date_iso).split("T")[0].split(" ")[0].strip() if date_iso else None

    if type_val is not None:
        properties["Type"] = {"select": {"name": type_val}}
        if clean_date:
            properties["Name"] = {"title": [{"text": {"content": f"{type_val} - {clean_date}"}}]}
        else:
            properties["Name"] = {"title": [{"text": {"content": type_val}}]}
    if clean_date:
        properties["Date_"] = {"date": {"start": clean_date}}
    if mode_list is not None:
        properties["Mode"] = {"multi_select": [{"name": m} for m in mode_list]}
    if notes is not None:
        properties["Notes"] = {"rich_text": [{"text": {"content": notes}}]}

    return update_notion_page_properties(page_id, properties)


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
        clean_date = raw_date.split("T")[0].split(" ")[0].strip() if raw_date else ""

        notes_list = props.get("Notes", {}).get("rich_text", [])
        notes = notes_list[0].get("plain_text", "") if notes_list else ""

        parsed_entries.append({
            "id": page.get("id"),
            "name": name,
            "type": t_val,
            "modes": modes,
            "date_iso": clean_date,
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
# 🎯 HABIT TRACKER CONSTANTS & FUNCTIONS (V2.2)
# ==========================================

HABIT_ITEMS: Dict[str, Dict[str, Any]] = {
    "bt": {"prop": "Brush Teeth", "fa": "مسواک", "emoji": "🪥", "code": "BST", "cat": "جسمی", "binary": False},
    "fr": {"prop": "Face Routine", "fa": "روتین پوستی", "emoji": "🧖", "code": "SKN", "cat": "جسمی", "binary": False},
    "mb": {"prop": "Make the Bed", "fa": "مرتب‌کردن تخت", "emoji": "🛏️", "code": "BDM", "cat": "نظم", "binary": True},
    "ex": {"prop": "Exercise", "fa": "ورزش", "emoji": "🏃", "code": "WKO", "cat": "جسمی", "binary": False},
    "md": {"prop": "Meditation", "fa": "مدیتیشن", "emoji": "🧘", "code": "MDT", "cat": "ذهنی", "binary": False},
    "gr": {"prop": "Gratitude", "fa": "شکرگزاری", "emoji": "🌸", "code": "THG", "cat": "ذهنی", "binary": False},
    "rb": {"prop": "Read Book", "fa": "کتاب‌خوانی", "emoji": "📚", "code": "BOK", "cat": "ذهنی", "binary": False},
    "rq": {"prop": "Read Holy Quran", "fa": "تلاوت قرآن", "emoji": "📖", "code": "QRN", "cat": "معنوی", "binary": False},
    "sl": {"prop": "Salam", "fa": "سلام", "emoji": "🕊️", "code": "SLM", "cat": "معنوی", "binary": True},
    "es": {"prop": "Esteghfar", "fa": "استغفار", "emoji": "📿", "code": "EST", "cat": "معنوی", "binary": False},
    "ps": {"prop": "Pray After Salah", "fa": "تعقیبات نماز", "emoji": "🤲", "code": "PAS", "cat": "معنوی", "binary": False},
    "bp": {"prop": "Bedtime Prayer", "fa": "دعای قبل خواب", "emoji": "🌙", "code": "BDP", "cat": "معنوی", "binary": False},
    "sg": {"prop": "Spritual Gift", "fa": "هدیه معنوی", "emoji": "🎁", "code": "SPG", "cat": "معنوی", "binary": False}
}

# Accurate Habit Tier Descriptions
HABIT_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "bt": {
        "v1": "مسواک زدن کامل + نخ دندان",
        "v2": "فقط مسواک زدن دقیق",
        "v3": "فقط نخ دندان کشیدن"
    },
    "fr": {
        "v1": "شستشوی صورت با شوینده در ۲ نوبت (صبح + شب)",
        "v2": "شستشوی صورت با شوینده در ۱ نوبت (شب)",
        "v3": "فقط آب‌زدن ساده به صورت با آب خالی"
    },
    "mb": {
        "v1": "مرتب کردن تخت و صاف کردن پتو و بالش‌ها",
        "v2": "مرتب کردن تخت",
        "v3": "جمع کردن حداقل پتو"
    },
    "ex": {
        "v1": "۴۵ تا ۶۰ دقیقه تمرین سنگین / باشگاه / فوتبال",
        "v2": "۲۰ تا ۳۰ دقیقه پیاده‌روی سریع / ورزش خانگی",
        "v3": "۵ تا ۱۰ دقیقه کشش یا چند حرکت سبک"
    },
    "md": {
        "v1": "۱۵ تا ۲۰ دقیقه بادی‌اسکن / تمرکز بر نفس",
        "v2": "۵ تا ۱۰ دقیقه تمرکز روی تنفس",
        "v3": "۱ تا ۲ دقیقه (۳ نفس عمیق و آگاهانه)"
    },
    "gr": {
        "v1": "ثبت ۳ تا ۵ مورد با جزئیات در دفترچه",
        "v2": "ثبت ۱ تا ۲ مورد مشخص در دفترچه",
        "v3": "۱ مورد شکرگزاری قلبی و توجه ذهنی"
    },
    "rb": {
        "v1": "۱۵ تا ۲۰ صفحه مطالعه عمیق (یا ۳۰ دقیقه)",
        "v2": "۵ تا ۱۰ صفحه مطالعه (یا ۱۵ دقیقه)",
        "v3": "حداقل ۱ صفحه یا ۱ پاراگراف"
    },
    "rq": {
        "v1": "۱ صفحه قرآن با معنی و تفسیرش",
        "v2": "۱ صفحه قرآن بدون تفسیر",
        "v3": "فقط سوره عادیات یا هر سوره راحت‌تر"
    },
    "sl": {
        "v1": "سلام به اهل بیت (علیهم‌السلام)",
        "v2": "سلام معمولی",
        "v3": "پاسخ دادن به سلام"
    },
    "es": {
        "v1": "۷۰ مرتبه استغفار",
        "v2": "۳۰ مرتبه استغفار",
        "v3": "۱۰ یا ۳ مرتبه استغفار"
    },
    "ps": {
        "v1": "خواندن هر ۵ دعا + دعاهای دیگر (اختیاری)",
        "v2": "خواندن ۳ دعا",
        "v3": "خواندن دعای سلامتی امام زمان (عج)"
    },
    "bp": {
        "v1": "وضو + آیت‌الکرسی + ۳ قل (یا ادعیه)",
        "v2": "آیت‌الکرسی",
        "v3": "۱ صلوات قلبی یا سوره توحید"
    },
    "sg": {
        "v1": "۱۰ صلوات + ۲ قدر یا/و ۱ آیت‌الکرسی + ۲ رکعت نماز نشسته (اختیاری)",
        "v2": "۱۰ صلوات یا/و ۲ سوره قدر",
        "v3": "فقط آیت‌الکرسی"
    }
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
    "2-🏃‍♂️ نیمه‌کامل": "🏃 معمول",
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

def parse_existing_gratitude_log(raw_log: str) -> List[Dict[str, Any]]:
    """Extracts existing gratitude bullet points from Notion's Gratitude Log string."""
    if not raw_log or not raw_log.strip():
        return []

    items: List[Dict[str, Any]] = []
    current_tag: Optional[str] = None

    for line in raw_log.split("\n"):
        clean = line.strip()
        if not clean or clean.startswith("🌸") or clean.startswith("📅") or clean.startswith("━") or clean.startswith("🤍"):
            continue

        if clean.startswith("🏷 [") and clean.endswith("]:"):
            current_tag = clean.replace("🏷 [", "").replace("]:", "").strip()
            continue

        if clean.startswith("🌿"):
            text = clean.replace("🌿", "").replace("خدایا شکرت بابت", "").replace("خدایا شکرت", "").replace("خدایا ممنونم بابت", "").replace("خدایا ممنونم", "").strip()
            if text:
                items.append({"tag": current_tag, "text": text})

    return items


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
        _cached_habits_ds_id = str(data_sources[0]["id"])
        return _cached_habits_ds_id

    _cached_habits_ds_id = str(NOTION_DBID_HABITS)
    return _cached_habits_ds_id


def get_or_create_habit_day(date_iso: str, day_title: str = "New Habit") -> Dict[str, Any]:
    """Finds existing habit page for the given date, or creates a new row if none exists."""
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
        page = cast(Dict[str, Any], results[0])
    else:
        create_props: Dict[str, Any] = {
            "Day": {"title": [{"text": {"content": day_title}}]},
            "Date_": {"date": {"start": date_iso}}
        }
        raw_created = notion.pages.create(
            parent={"database_id": NOTION_DBID_HABITS},
            properties=create_props
        )
        page = cast(Dict[str, Any], raw_created)

    return parse_habit_page(page)


def parse_habit_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Parses a Notion habit page into a clean Python dictionary."""
    props = page.get("properties", {})

    title_list = props.get("Day", {}).get("title", [])
    day_name = title_list[0].get("plain_text", "New Habit") if title_list else "New Habit"

    date_prop = props.get("Date_", {}).get("date") or {}
    raw_date = str(date_prop.get("start") or "")

    prog_prop = props.get("Progress", {}).get("formula", {})
    progress_val = float(prog_prop.get("number", 0.0)) if prog_prop.get("type") == "number" else 0.0

    notes_list = props.get("Notes", {}).get("rich_text", [])
    notes = notes_list[0].get("plain_text", "") if notes_list else ""

    grat_list = props.get("Gratitude Log", {}).get("rich_text", [])
    gratitude_log = grat_list[0].get("plain_text", "") if grat_list else ""

    quran_list = props.get("Quran Detail", {}).get("rich_text", [])
    quran_detail = quran_list[0].get("plain_text", "") if quran_list else ""

    book_list = props.get("Book Detail", {}).get("rich_text", [])
    book_detail = book_list[0].get("plain_text", "") if book_list else ""

    habits_status: Dict[str, Optional[str]] = {}
    for h_key, h_info in HABIT_ITEMS.items():
        prop_name = h_info["prop"]
        sel_val = (props.get(prop_name, {}).get("select") or {}).get("name")
        habits_status[h_key] = sel_val

    return {
        "id": str(page.get("id")),
        "day_name": day_name,
        "date_iso": raw_date,
        "progress": progress_val,
        "cheerleader": get_persian_cheerleader(progress_val),
        "notes": notes,
        "gratitude_log": gratitude_log,
        "quran_detail": quran_detail,
        "book_detail": book_detail,
        "habits": habits_status,
        "url": str(page.get("url", ""))
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
    """Updates all 12 habits at once."""
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
    """Updates multiple specific habits in a single API call."""
    try:
        update_props: Dict[str, Any] = {}
        for k, sel_val in habit_dict.items():
            if k in HABIT_ITEMS:
                prop_name = HABIT_ITEMS[k]["prop"]
            else:
                prop_name = k
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


def update_habit_quran_detail(page_id: str, detail_text: str) -> bool:
    """Updates the rich_text Quran Detail property for a habit day."""
    try:
        payload = [{"text": {"content": detail_text}}] if detail_text else []
        notion.pages.update(
            page_id=page_id,
            properties={"Quran Detail": {"rich_text": payload}}
        )
        return True
    except Exception as e:
        print(f"Error updating habit quran detail: {e}")
        return False


def reset_habit_day(page_id: str) -> bool:
    """Safely resets all 13 habits, notes, gratitude log, book and quran detail for a day."""
    try:
        reset_props: Dict[str, Any] = {
            h_info["prop"]: {"select": None}
            for h_info in HABIT_ITEMS.values()
        }
        reset_props["Notes"] = {"rich_text": []}
        reset_props["Gratitude Log"] = {"rich_text": []}
        reset_props["Quran Detail"] = {"rich_text": []}
        reset_props["Book Detail"] = {"rich_text": []}

        notion.pages.update(page_id=page_id, properties=reset_props)
        return True
    except Exception as e:
        print(f"Error resetting habit day: {e}")
        return False 
    
def query_habit_history(limit_count: int = 60) -> List[Dict[str, Any]]:
    """
    Fetches recent historical habit days sorted descending by Date_ for analytics & streaks.
    """
    if not NOTION_DBID_HABITS:
        raise ValueError("NOTION_DBID_HABITS is not defined in environment variables.")

    ds_id = get_habits_data_source_id()
    filter_payload: Dict[str, Any] = {}

    kwargs: Dict[str, Any] = {
        "page_size": min(100, max(1, limit_count)),
        "sorts": [{"property": "Date_", "direction": "descending"}],
    }

    try:
        if hasattr(notion, "data_sources") and hasattr(notion.data_sources, "query"):
            kwargs["data_source_id"] = ds_id
            query_res = notion.data_sources.query(**kwargs)
        else:
            kwargs.pop("data_source_id", None)
            kwargs["database_id"] = NOTION_DBID_HABITS
            query_res = notion.databases.query(**kwargs)  # type: ignore

        results = query_res.get("results", []) if isinstance(query_res, dict) else []
        return [parse_habit_page(page) for page in results]
    except Exception as e:
        print(f"Error querying habit history from Notion: {e}")
        return []

def update_habit_book_detail(page_id: str, detail_text: str) -> bool:
    """Updates the rich_text Book Detail property for a habit day."""
    try:
        payload = [{"text": {"content": detail_text}}] if detail_text else []
        notion.pages.update(
            page_id=page_id,
            properties={"Book Detail": {"rich_text": payload}}
        )
        return True
    except Exception as e:
        print(f"Error updating habit book detail: {e}")
        return False


# ==========================================
# 📿 SPIRITUAL TRACKER (SALAH & QURAN)
# ==========================================

PRAYER_KEYS: List[str] = ["sobh", "zohr", "asr", "maghreb", "eshsa"]

PRAYER_META: Dict[str, Dict[str, str]] = {
    "sobh": {"name": "صبح", "prop": "Sobh", "ada_name": "صبح", "emoji": "🌅"},
    "zohr": {"name": "ظهر", "prop": "Zohr", "ada_name": "ظهر", "emoji": "☀️"},
    "asr": {"name": "عصر", "prop": "Asr", "ada_name": "عصر", "emoji": "🌤️"},
    "maghreb": {"name": "مغرب", "prop": "Maghreb", "ada_name": "مغرب", "emoji": "🌇"},
    "eshsa": {"name": "عشاء", "prop": "Eshsa", "ada_name": "عشاء", "emoji": "🌌"},
}

_cached_salah_ds_id: Optional[str] = None
_cached_quran_ds_id: Optional[str] = None


def get_salah_data_source_id() -> str:
    """Retrieves and caches the data_source_id of the Salah Entries database."""
    global _cached_salah_ds_id
    if _cached_salah_ds_id:
        return _cached_salah_ds_id

    if not NOTION_DBID_SALAH:
        raise ValueError("NOTION_DBID_SALAH is not defined in environment variables.")

    db_info = cast(Dict[str, Any], notion.databases.retrieve(database_id=NOTION_DBID_SALAH))
    data_sources = db_info.get("data_sources", [])
    if data_sources:
        _cached_salah_ds_id = str(data_sources[0]["id"])
        return _cached_salah_ds_id

    _cached_salah_ds_id = str(NOTION_DBID_SALAH)
    return _cached_salah_ds_id


def get_quran_data_source_id() -> str:
    """Retrieves and caches the data_source_id of the Quran Reading database."""
    global _cached_quran_ds_id
    if _cached_quran_ds_id:
        return _cached_quran_ds_id

    if not NOTION_DBID_QURAN:
        raise ValueError("NOTION_DBID_QURAN is not defined in environment variables.")

    db_info = cast(Dict[str, Any], notion.databases.retrieve(database_id=NOTION_DBID_QURAN))
    data_sources = db_info.get("data_sources", [])
    if data_sources:
        _cached_quran_ds_id = str(data_sources[0]["id"])
        return _cached_quran_ds_id

    _cached_quran_ds_id = str(NOTION_DBID_QURAN)
    return _cached_quran_ds_id


def parse_salah_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Parses a Notion Salah Entries page into a structured python dictionary."""
    props = page.get("properties", {})
    page_id = page.get("id", "")

    name_list = props.get("Name", {}).get("title", [])
    name = name_list[0].get("plain_text", "") if name_list else "New Salah"

    date_val = props.get("Date_", {}).get("date")
    date_iso = date_val.get("start", "") if date_val else ""

    shamsi_formula = props.get("Date", {}).get("formula", {})
    shamsi_date = shamsi_formula.get("string", "") if shamsi_formula else ""

    notes_list = props.get("Notes", {}).get("rich_text", [])
    notes = "".join([t.get("plain_text", "") for t in notes_list])

    prog_formula = props.get("Progress", {}).get("formula", {})
    prog_num = prog_formula.get("number", 0.0) if prog_formula else 0.0

    ada_ms = props.get("Ada?", {}).get("multi_select", [])
    ada_names = [o.get("name") for o in ada_ms if o.get("name")]

    chks = {
        "sobh": bool(props.get("Sobh", {}).get("checkbox", False)),
        "zohr": bool(props.get("Zohr", {}).get("checkbox", False)),
        "asr": bool(props.get("Asr", {}).get("checkbox", False)),
        "maghreb": bool(props.get("Maghreb", {}).get("checkbox", False)),
        "eshsa": bool(props.get("Eshsa", {}).get("checkbox", False)),
    }

    prayers: Dict[str, Dict[str, Any]] = {}
    completed_count = 0
    ada_count = 0
    qaza_count = 0

    for k in PRAYER_KEYS:
        chk = chks[k]
        ada_str = PRAYER_META[k]["ada_name"]
        in_ada = ada_str in ada_names

        if chk and in_ada:
            p_status = "ada"
            completed_count += 1
            ada_count += 1
        elif chk and not in_ada:
            p_status = "qaza"
            completed_count += 1
            qaza_count += 1
        else:
            p_status = "none"

        prayers[k] = {
            "key": k,
            "name": PRAYER_META[k]["name"],
            "emoji": PRAYER_META[k]["emoji"],
            "prop": PRAYER_META[k]["prop"],
            "checked": chk,
            "is_ada": (p_status == "ada"),
            "is_qaza": (p_status == "qaza"),
            "status": p_status,
        }

    return {
        "id": page_id,
        "name": name,
        "date_iso": date_iso,
        "shamsi_date": shamsi_date,
        "notes": notes,
        "progress": float(prog_num or (completed_count / 5.0)),
        "ada_names": ada_names,
        "prayers": prayers,
        "completed_count": completed_count,
        "ada_count": ada_count,
        "qaza_count": qaza_count,
    }


def get_or_create_salah_day(date_iso: str, day_title: str = "New Salah") -> Dict[str, Any]:
    """
    Finds existing salah page for the given date, or creates a new row with all 5 prayers checked
    and set to Ada (on-time) by default.
    """
    if not NOTION_DBID_SALAH:
        raise ValueError("NOTION_DBID_SALAH is not defined in environment variables.")

    ds_id = get_salah_data_source_id()
    filter_payload = {"property": "Date_", "date": {"equals": date_iso}}

    if hasattr(notion, "data_sources") and hasattr(notion.data_sources, "query"):
        query_res = notion.data_sources.query(
            data_source_id=ds_id,
            filter=filter_payload,
            page_size=1
        )
    else:
        query_res = notion.databases.query(
            database_id=NOTION_DBID_SALAH,
            filter=filter_payload,
            page_size=1
        )  # type: ignore

    results = query_res.get("results", []) if isinstance(query_res, dict) else []
    if results:
        page = cast(Dict[str, Any], results[0])
    else:
        # Default Auto-Completion: All 5 prayers checked and added to Ada?
        create_props: Dict[str, Any] = {
            "Name": {"title": [{"text": {"content": day_title}}]},
            "Date_": {"date": {"start": date_iso}},
            "Sobh": {"checkbox": True},
            "Zohr": {"checkbox": True},
            "Asr": {"checkbox": True},
            "Maghreb": {"checkbox": True},
            "Eshsa": {"checkbox": True},
            "Ada?": {"multi_select": [
                {"name": "صبح"},
                {"name": "ظهر"},
                {"name": "عصر"},
                {"name": "مغرب"},
                {"name": "عشاء"},
            ]},
            "Notes": {"rich_text": []}
        }
        raw_created = notion.pages.create(
            parent={"database_id": NOTION_DBID_SALAH},
            properties=create_props
        )
        page = cast(Dict[str, Any], raw_created)

    return parse_salah_page(page)


def update_salah_prayer_status(page_id: str, prayer_key: str, target_status: Optional[str] = None) -> bool:
    """
    Updates the status of a prayer:
    - target_status = 'ada': checkbox=True, added to Ada?
    - target_status = 'qaza': checkbox=True, removed from Ada?
    - target_status = 'none': checkbox=False, removed from Ada?
    - If target_status is None: cycles (ada -> qaza -> none -> ada)
    """
    if prayer_key not in PRAYER_META:
        return False

    try:
        page = notion.pages.retrieve(page_id=page_id)
        parsed = parse_salah_page(page)
        curr = parsed["prayers"].get(prayer_key)
        if not curr:
            return False

        curr_status = curr["status"]
        if not target_status:
            if curr_status == "ada":
                target_status = "qaza"
            elif curr_status == "qaza":
                target_status = "none"
            else:
                target_status = "ada"

        meta = PRAYER_META[prayer_key]
        prop_name = meta["prop"]
        ada_name = meta["ada_name"]
        current_ada_names = list(parsed["ada_names"])

        if target_status == "ada":
            new_chk = True
            if ada_name not in current_ada_names:
                current_ada_names.append(ada_name)
        elif target_status == "qaza":
            new_chk = True
            if ada_name in current_ada_names:
                current_ada_names.remove(ada_name)
        else:
            new_chk = False
            if ada_name in current_ada_names:
                current_ada_names.remove(ada_name)

        notion.pages.update(
            page_id=page_id,
            properties={
                prop_name: {"checkbox": new_chk},
                "Ada?": {"multi_select": [{"name": n} for n in current_ada_names]}
            }
        )
        return True
    except Exception as e:
        print(f"Error updating salah prayer status: {e}")
        return False


def bulk_mark_salah_ada(page_id: str) -> bool:
    """Marks all 5 prayers as completed and Ada (on-time)."""
    try:
        notion.pages.update(
            page_id=page_id,
            properties={
                "Sobh": {"checkbox": True},
                "Zohr": {"checkbox": True},
                "Asr": {"checkbox": True},
                "Maghreb": {"checkbox": True},
                "Eshsa": {"checkbox": True},
                "Ada?": {"multi_select": [
                    {"name": "صبح"},
                    {"name": "ظهر"},
                    {"name": "عصر"},
                    {"name": "مغرب"},
                    {"name": "عشاء"}
                ]}
            }
        )
        return True
    except Exception as e:
        print(f"Error bulk marking salah ada: {e}")
        return False


def bulk_mark_salah_reset(page_id: str) -> bool:
    """Resets all 5 prayers to uncompleted."""
    try:
        notion.pages.update(
            page_id=page_id,
            properties={
                "Sobh": {"checkbox": False},
                "Zohr": {"checkbox": False},
                "Asr": {"checkbox": False},
                "Maghreb": {"checkbox": False},
                "Eshsa": {"checkbox": False},
                "Ada?": {"multi_select": []}
            }
        )
        return True
    except Exception as e:
        print(f"Error resetting salah day: {e}")
        return False


def bulk_mark_salah_range_ada(start_date_iso: str, end_date_iso: str) -> Dict[str, Any]:
    """
    Marks all 5 prayers as completed and Ada across an entire date range.
    Creates missing days with 5/5 Ada and updates existing days.
    """
    if not NOTION_DBID_SALAH:
        raise ValueError("NOTION_DBID_SALAH is not defined in environment variables.")

    start_d = datetime.strptime(start_date_iso, "%Y-%m-%d").date()
    end_d = datetime.strptime(end_date_iso, "%Y-%m-%d").date()
    if start_d > end_d:
        start_d, end_d = end_d, start_d

    # Generate all ISO dates in range
    cur_d = start_d
    dates_list: List[str] = []
    while cur_d <= end_d:
        dates_list.append(cur_d.isoformat())
        cur_d += timedelta(days=1)

    # Fetch existing entries in this range
    existing = query_salah_entries(
        start_date_iso=start_d.isoformat(),
        end_date_iso=end_d.isoformat(),
        limit_count=min(100, max(len(dates_list) + 10, 30))
    )
    existing_by_date = {p.get("date_iso"): p for p in existing if p.get("date_iso")}

    updated_count = 0
    created_count = 0
    already_ada_count = 0

    for d_iso in dates_list:
        if d_iso in existing_by_date:
            p = existing_by_date[d_iso]
            if p.get("ada_count", 0) < 5 or p.get("completed_count", 0) < 5:
                if bulk_mark_salah_ada(p["id"]):
                    updated_count += 1
            else:
                already_ada_count += 1
        else:
            get_or_create_salah_day(d_iso, f"Salah - {d_iso}")
            created_count += 1

    return {
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "total_days": len(dates_list),
        "updated_count": updated_count,
        "created_count": created_count,
        "already_ada_count": already_ada_count
    }



def update_salah_notes(page_id: str, notes_text: str) -> bool:
    """Updates the Notes property in Salah table."""
    try:
        notion.pages.update(
            page_id=page_id,
            properties={
                "Notes": {"rich_text": [{"text": {"content": notes_text}}] if notes_text else []}
            }
        )
        return True
    except Exception as e:
        print(f"Error updating salah notes: {e}")
        return False


def query_salah_entries(
    start_date_iso: Optional[str] = None,
    end_date_iso: Optional[str] = None,
    limit_count: int = 30
) -> List[Dict[str, Any]]:
    """Queries history of Salah days."""
    if not NOTION_DBID_SALAH:
        return []

    ds_id = get_salah_data_source_id()
    and_filters: List[Dict[str, Any]] = []

    if start_date_iso:
        if end_date_iso and end_date_iso != start_date_iso:
            and_filters.append({"property": "Date_", "date": {"on_or_after": start_date_iso}})
            and_filters.append({"property": "Date_", "date": {"on_or_before": end_date_iso}})
        else:
            and_filters.append({"property": "Date_", "date": {"equals": start_date_iso}})

    filter_payload = None
    if len(and_filters) == 1:
        filter_payload = and_filters[0]
    elif len(and_filters) > 1:
        filter_payload = {"and": and_filters}

    kwargs: Dict[str, Any] = {
        "page_size": min(100, max(1, limit_count)),
        "sorts": [{"property": "Date_", "direction": "descending"}]
    }
    if filter_payload:
        kwargs["filter"] = filter_payload

    try:
        if hasattr(notion, "data_sources") and hasattr(notion.data_sources, "query"):
            kwargs["data_source_id"] = ds_id
            res = notion.data_sources.query(**kwargs)
        else:
            kwargs.pop("data_source_id", None)
            kwargs["database_id"] = NOTION_DBID_SALAH
            res = notion.databases.query(**kwargs)  # type: ignore

        results = res.get("results", []) if isinstance(res, dict) else []
        return [parse_salah_page(p) for p in results]
    except Exception as e:
        print(f"Error querying salah entries: {e}")
        return []


def parse_quran_page(page: Dict[str, Any]) -> Dict[str, Any]:
    """Parses a Notion Quran Reading Tracker page."""
    props = page.get("properties", {})
    page_id = page.get("id", "")

    name_list = props.get("Name", {}).get("title", [])
    name = name_list[0].get("plain_text", "") if name_list else "New Session"

    date_val = props.get("Date_", {}).get("date")
    date_iso = date_val.get("start", "") if date_val else ""

    shamsi_formula = props.get("Date", {}).get("formula", {})
    shamsi_date = shamsi_formula.get("string", "") if shamsi_formula else ""

    pages_list = props.get("Page(s)", {}).get("rich_text", [])
    pages = "".join([t.get("plain_text", "") for t in pages_list])

    return {
        "id": page_id,
        "name": name,
        "date_iso": date_iso,
        "shamsi_date": shamsi_date,
        "pages": pages,
    }


def add_quran_reading_entry(
    date_iso: str,
    pages_text: str,
    session_name: str = "New Session"
) -> Optional[Dict[str, Any]]:
    """Logs a Quran reading session into Notion."""
    if not NOTION_DBID_QURAN:
        return None

    try:
        create_props: Dict[str, Any] = {
            "Name": {"title": [{"text": {"content": session_name or "New Session"}}]},
            "Date_": {"date": {"start": date_iso}},
            "Page(s)": {"rich_text": [{"text": {"content": pages_text}}] if pages_text else []}
        }
        res = notion.pages.create(
            parent={"database_id": NOTION_DBID_QURAN},
            properties=create_props
        )
        return cast(Dict[str, Any], res)
    except Exception as e:
        print(f"Error adding quran entry: {e}")
        return None


def query_quran_entries(
    start_date_iso: Optional[str] = None,
    end_date_iso: Optional[str] = None,
    limit_count: int = 20
) -> List[Dict[str, Any]]:
    """Queries recent Quran reading sessions."""
    if not NOTION_DBID_QURAN:
        return []

    ds_id = get_quran_data_source_id()
    and_filters: List[Dict[str, Any]] = []

    if start_date_iso:
        if end_date_iso and end_date_iso != start_date_iso:
            and_filters.append({"property": "Date_", "date": {"on_or_after": start_date_iso}})
            and_filters.append({"property": "Date_", "date": {"on_or_before": end_date_iso}})
        else:
            and_filters.append({"property": "Date_", "date": {"equals": start_date_iso}})

    filter_payload = None
    if len(and_filters) == 1:
        filter_payload = and_filters[0]
    elif len(and_filters) > 1:
        filter_payload = {"and": and_filters}

    kwargs: Dict[str, Any] = {
        "page_size": min(100, max(1, limit_count)),
        "sorts": [{"property": "Date_", "direction": "descending"}]
    }
    if filter_payload:
        kwargs["filter"] = filter_payload

    try:
        if hasattr(notion, "data_sources") and hasattr(notion.data_sources, "query"):
            kwargs["data_source_id"] = ds_id
            res = notion.data_sources.query(**kwargs)
        else:
            kwargs.pop("data_source_id", None)
            kwargs["database_id"] = NOTION_DBID_QURAN
            res = notion.databases.query(**kwargs)  # type: ignore

        results = res.get("results", []) if isinstance(res, dict) else []
        return [parse_quran_page(p) for p in results]
    except Exception as e:
        print(f"Error querying quran entries: {e}")
        return []


def get_spiritual_report(start_date_iso: str, end_date_iso: str) -> Dict[str, Any]:
    """Generates analytics report for Salah and Quran over a date range."""
    salah_list = query_salah_entries(start_date_iso=start_date_iso, end_date_iso=end_date_iso, limit_count=100)
    quran_list = query_quran_entries(start_date_iso=start_date_iso, end_date_iso=end_date_iso, limit_count=100)

    total_days = len(salah_list)
    total_prayers_possible = total_days * 5
    total_ada = sum(d["ada_count"] for d in salah_list)
    total_qaza = sum(d["qaza_count"] for d in salah_list)
    total_missed = max(0, total_prayers_possible - (total_ada + total_qaza))

    prayer_stats: Dict[str, Dict[str, Any]] = {}
    for k in PRAYER_KEYS:
        p_ada = sum(1 for d in salah_list if d["prayers"][k]["is_ada"])
        p_qaza = sum(1 for d in salah_list if d["prayers"][k]["is_qaza"])
        p_missed = sum(1 for d in salah_list if d["prayers"][k]["status"] == "none")
        prayer_stats[k] = {
            "name": PRAYER_META[k]["name"],
            "emoji": PRAYER_META[k]["emoji"],
            "ada": p_ada,
            "qaza": p_qaza,
            "missed": p_missed,
            "rate": round((p_ada / total_days * 100), 1) if total_days > 0 else 0
        }

    perfect_days = sum(1 for d in salah_list if d["ada_count"] == 5)
    overall_ada_rate = (total_ada / total_prayers_possible * 100) if total_prayers_possible > 0 else 0

    return {
        "start_date": start_date_iso,
        "end_date": end_date_iso,
        "total_days": total_days,
        "total_prayers_possible": total_prayers_possible,
        "total_ada": total_ada,
        "total_qaza": total_qaza,
        "total_missed": total_missed,
        "overall_ada_rate": round(overall_ada_rate, 1),
        "perfect_days": perfect_days,
        "prayer_stats": prayer_stats,
        "quran_sessions_count": len(quran_list),
        "quran_sessions": quran_list,
        "recent_salah": salah_list[:7]
    }