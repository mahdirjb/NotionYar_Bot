# app/services/insights_service.py

import json
import os
from datetime import datetime, date, timedelta, timezone
from typing import Dict, List, Any, Optional
import jdatetime
from app.services.notion_service import (
    LIFE_TRACKER_TYPES,
    TYPE_EMOJIS,
    MODE_EMOJIS,
    query_life_tracker_entries
)
from app.services.date_helper import parse_user_date_input

INSIGHTS_SETTINGS_FILE = "insights_settings.json"

# Default enabled types for routine/interval tracking
DEFAULT_ENABLED_TYPES = [
    "آرایشگاه",
    "ناخن دست",
    "ناخن پا",
    "موپالمو",
    "خورشید",
    "آینه",
    "ریش و سبیل",
    "ویتامین دی",
    "رانندگی",
    "مریضی"
]


def _load_enabled_types() -> List[str]:
    """Loads configured active habit types from storage."""
    if os.path.exists(INSIGHTS_SETTINGS_FILE):
        try:
            with open(INSIGHTS_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("enabled_types", DEFAULT_ENABLED_TYPES)
        except Exception:
            return list(DEFAULT_ENABLED_TYPES)
    return list(DEFAULT_ENABLED_TYPES)


def _save_enabled_types(enabled: List[str]) -> None:
    """Saves configured active habit types to storage."""
    try:
        with open(INSIGHTS_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"enabled_types": enabled}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving insights settings: {e}")


def get_enabled_insight_types() -> List[str]:
    """Returns currently enabled habit types."""
    return _load_enabled_types()


def toggle_insight_type(type_name: str) -> bool:
    """Toggles active state of a habit type and returns new status."""
    enabled = _load_enabled_types()
    if type_name in enabled:
        enabled.remove(type_name)
        is_on = False
    else:
        enabled.append(type_name)
        is_on = True
    _save_enabled_types(enabled)
    return is_on


def calculate_habit_insights() -> Dict[str, Any]:
    """
    Fetches all life tracker entries and calculates intervals, averages and status indicators.
    """
    entries = query_life_tracker_entries(start_date_iso=None)
    enabled_types = _load_enabled_types()

    # Group entries by type
    grouped: Dict[str, List[Dict[str, Any]]] = {t: [] for t in LIFE_TRACKER_TYPES}
    for e in entries:
        t_val = e.get("type")
        if t_val in grouped and e.get("date_iso"):
            grouped[t_val].append(e)

    tz = timezone(timedelta(hours=3, minutes=30))
    today_g = datetime.now(tz).date()

    insights_data: Dict[str, Any] = {}

    for t_name in LIFE_TRACKER_TYPES:
        if t_name not in enabled_types:
            continue

        type_entries = grouped.get(t_name, [])
        if not type_entries:
            insights_data[t_name] = {
                "has_data": False,
                "total_count": 0,
                "emoji": TYPE_EMOJIS.get(t_name, "🏷")
            }
            continue

        # Sort dates descending
        dates: List[date] = []
        for item in type_entries:
            iso_str = item.get("date_iso")
            if iso_str:
                try:
                    d_obj = datetime.strptime(iso_str.split("T")[0], "%Y-%m-%d").date()
                    dates.append(d_obj)
                except Exception:
                    pass

        dates.sort(reverse=True)
        if not dates:
            insights_data[t_name] = {
                "has_data": False,
                "total_count": 0,
                "emoji": TYPE_EMOJIS.get(t_name, "🏷")
            }
            continue

        last_date = dates[0]
        days_ago = (today_g - last_date).days
        j_last = jdatetime.date.fromgregorian(date=last_date).strftime("%Y/%m/%d")

        # Calculate intervals between consecutive records
        intervals: List[int] = []
        for i in range(len(dates) - 1):
            gap = (dates[i] - dates[i + 1]).days
            if gap >= 0:
                intervals.append(gap)

        avg_interval = int(round(sum(intervals) / len(intervals))) if intervals else None
        min_interval = min(intervals) if intervals else None
        max_interval = max(intervals) if intervals else None

        # Determine status badge
        if avg_interval is None:
            badge = "⚪"
            status_text = "نیازمند ثبت‌های بیشتر"
        elif days_ago <= int(avg_interval * 0.85):
            badge = "🟢"
            status_text = "به‌موقع و عادی"
        elif days_ago <= int(avg_interval * 1.15):
            badge = "🟡"
            status_text = "نزدیک به موعد"
        else:
            badge = "🔴"
            status_text = "زمانشه / گذشته از موعد"

        insights_data[t_name] = {
            "has_data": True,
            "total_count": len(dates),
            "emoji": TYPE_EMOJIS.get(t_name, "🏷"),
            "last_date_shamsi": j_last,
            "days_ago": days_ago,
            "avg_interval": avg_interval,
            "min_interval": min_interval,
            "max_interval": max_interval,
            "recent_intervals": intervals[:4],
            "badge": badge,
            "status_text": status_text,
            "recent_dates": [jdatetime.date.fromgregorian(date=d).strftime("%m/%d") for d in dates[:5]]
        }

    return insights_data