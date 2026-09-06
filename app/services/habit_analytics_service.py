# app/services/habit_analytics_service.py

from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from app.services.notion_service import (
    HABIT_ITEMS,
    query_habit_history,
)

VALID_STREAK_LEVELS = {"1-💪 کامل", "2-🏃‍♂️ نیمه‌کامل", "3-🐢 سبک"}


def _get_tehran_today() -> date:
    """Returns today's date in Tehran timezone (UTC+3:30)."""
    tz = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(tz).date()


def calculate_habit_streaks(
    history_pages: Optional[List[Dict[str, Any]]] = None,
    max_days: int = 100
) -> Dict[str, Any]:
    """
    Analyzes historical habit records and calculates:
    - Current Streak & Best Streak for each of the 12 habits.
    - Current Streak & Best Streak for overall successful days (progress >= 50%).
    """
    if history_pages is None:
        history_pages = query_habit_history(limit_count=max_days)

    today = _get_tehran_today()

    # Map dates to habit records: {date_obj: page_dict}
    records_by_date: Dict[date, Dict[str, Any]] = {}
    for page in history_pages:
        raw_date = page.get("date_iso")
        if not raw_date:
            continue
        try:
            d_obj = date.fromisoformat(raw_date)
            records_by_date[d_obj] = page
        except Exception:
            continue

    # -------------------------------------------------------------
    # 1. Calculate Habit-by-Habit Streaks (Current & Best)
    # -------------------------------------------------------------
    habit_streaks: Dict[str, Dict[str, int]] = {}

    for h_key in HABIT_ITEMS.keys():
        # --- Current Streak Calculation ---
        current_streak = 0
        check_date = today

        # Check if today is logged and valid
        today_record = records_by_date.get(today)
        today_val = today_record.get("habits", {}).get(h_key) if today_record else None

        if today_val in VALID_STREAK_LEVELS:
            current_streak = 1
            check_date = today - timedelta(days=1)
        else:
            # If today is not done yet, check if yesterday was done (active streak)
            yesterday = today - timedelta(days=1)
            yest_record = records_by_date.get(yesterday)
            yest_val = yest_record.get("habits", {}).get(h_key) if yest_record else None
            if yest_val in VALID_STREAK_LEVELS:
                current_streak = 1
                check_date = yesterday - timedelta(days=1)
            else:
                current_streak = 0
                check_date = None

        if check_date:
            while True:
                rec = records_by_date.get(check_date)
                if not rec:
                    break
                val = rec.get("habits", {}).get(h_key)
                if val in VALID_STREAK_LEVELS:
                    current_streak += 1
                    check_date -= timedelta(days=1)
                else:
                    break

        # --- Best Streak Calculation Across History ---
        sorted_dates = sorted(records_by_date.keys())
        best_streak = 0
        temp_streak = 0
        last_date: Optional[date] = None

        for d in sorted_dates:
            rec = records_by_date[d]
            val = rec.get("habits", {}).get(h_key)
            is_done = val in VALID_STREAK_LEVELS

            if is_done:
                if last_date is not None and (d - last_date).days == 1:
                    temp_streak += 1
                else:
                    temp_streak = 1
                best_streak = max(best_streak, temp_streak)
                last_date = d
            else:
                temp_streak = 0
                last_date = None

        # Best streak cannot be less than current streak
        best_streak = max(best_streak, current_streak)

        habit_streaks[h_key] = {
            "current": current_streak,
            "best": best_streak,
        }

    # -------------------------------------------------------------
    # 2. Overall Day Streaks (Days with Progress >= 50%)
    # -------------------------------------------------------------
    overall_current = 0
    today_rec = records_by_date.get(today)
    today_prog = float(today_rec.get("progress", 0.0)) if today_rec else 0.0

    if today_prog >= 0.50:
        overall_current = 1
        check_date = today - timedelta(days=1)
    else:
        yesterday = today - timedelta(days=1)
        yest_rec = records_by_date.get(yesterday)
        yest_prog = float(yest_rec.get("progress", 0.0)) if yest_rec else 0.0
        if yest_prog >= 0.50:
            overall_current = 1
            check_date = yesterday - timedelta(days=1)
        else:
            overall_current = 0
            check_date = None

    if check_date:
        while True:
            rec = records_by_date.get(check_date)
            if not rec:
                break
            prog = float(rec.get("progress", 0.0))
            if prog >= 0.50:
                overall_current += 1
                check_date -= timedelta(days=1)
            else:
                break

    sorted_dates = sorted(records_by_date.keys())
    overall_best = 0
    temp_overall = 0
    last_d: Optional[date] = None

    for d in sorted_dates:
        rec = records_by_date[d]
        prog = float(rec.get("progress", 0.0))
        if prog >= 0.50:
            if last_d is not None and (d - last_d).days == 1:
                temp_overall += 1
            else:
                temp_overall = 1
            overall_best = max(overall_best, temp_overall)
            last_d = d
        else:
            temp_overall = 0
            last_d = None

    overall_best = max(overall_best, overall_current)

    return {
        "habit_streaks": habit_streaks,
        "overall": {
            "current": overall_current,
            "best": overall_best,
        },
        "total_days_analyzed": len(records_by_date),
    }