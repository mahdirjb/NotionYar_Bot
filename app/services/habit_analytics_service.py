# app/services/habit_analytics_service.py

from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
import jdatetime
from app.services.notion_service import (
    HABIT_ITEMS,
    query_habit_history,
)

VALID_STREAK_LEVELS = {"1-💪 کامل", "2-🏃‍♂️ نیمه‌کامل", "3-🐢 سبک"}
FREEZE_MARKERS = ["[❄️", "STREAK_FREEZE", "روز فریز"]


def _get_tehran_today() -> date:
    """Returns today's date in Tehran timezone (UTC+3:30)."""
    tz = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(tz).date()


def is_day_frozen(page: Optional[Dict[str, Any]]) -> bool:
    """Checks if a habit day is marked as Streak Frozen."""
    if not page:
        return False
    notes = str(page.get("notes") or "")
    return any(marker in notes for marker in FREEZE_MARKERS)


def calculate_habit_streaks(
    history_pages: Optional[List[Dict[str, Any]]] = None,
    max_days: int = 100
) -> Dict[str, Any]:
    """
    Analyzes historical habit records and calculates:
    - Current Streak & Best Streak for each of the 12 habits (with Freeze Protection).
    - Current Streak & Best Streak for overall successful days.
    """
    if history_pages is None:
        history_pages = query_habit_history(limit_count=max_days)

    today = _get_tehran_today()

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

    # 1. Calculate Habit-by-Habit Streaks with Freeze Bridge
    habit_streaks: Dict[str, Dict[str, int]] = {}

    for h_key in HABIT_ITEMS.keys():
        current_streak = 0
        check_date = today

        today_record = records_by_date.get(today)
        today_val = today_record.get("habits", {}).get(h_key) if today_record else None
        today_frozen = is_day_frozen(today_record)

        if today_val in VALID_STREAK_LEVELS or today_frozen:
            current_streak = 1 if today_val in VALID_STREAK_LEVELS else 0
            check_date = today - timedelta(days=1)
        else:
            yesterday = today - timedelta(days=1)
            yest_record = records_by_date.get(yesterday)
            yest_val = yest_record.get("habits", {}).get(h_key) if yest_record else None
            yest_frozen = is_day_frozen(yest_record)

            if yest_val in VALID_STREAK_LEVELS or yest_frozen:
                current_streak = 1 if yest_val in VALID_STREAK_LEVELS else 0
                check_date = yesterday - timedelta(days=1)
            else:
                current_streak = 0
                check_date = None

        if check_date:
            while True:
                rec = records_by_date.get(check_date)
                if not rec:
                    break
                
                # If frozen, bridge across this day without breaking streak
                if is_day_frozen(rec):
                    check_date -= timedelta(days=1)
                    continue

                val = rec.get("habits", {}).get(h_key)
                if val in VALID_STREAK_LEVELS:
                    current_streak += 1
                    check_date -= timedelta(days=1)
                else:
                    break

        # Best Streak Across History with Freeze Protection
        sorted_dates = sorted(records_by_date.keys())
        best_streak = 0
        temp_streak = 0
        last_date: Optional[date] = None

        for d in sorted_dates:
            rec = records_by_date[d]
            val = rec.get("habits", {}).get(h_key)
            is_done = val in VALID_STREAK_LEVELS
            frozen = is_day_frozen(rec)

            if is_done:
                if last_date is not None and (d - last_date).days == 1:
                    temp_streak += 1
                else:
                    temp_streak = 1
                best_streak = max(best_streak, temp_streak)
                last_date = d
            elif frozen:
                # Freeze bridges the gap to the next day
                if last_date is not None and (d - last_date).days == 1:
                    last_date = d
            else:
                temp_streak = 0
                last_date = None

        best_streak = max(best_streak, current_streak)

        habit_streaks[h_key] = {
            "current": current_streak,
            "best": best_streak,
        }

    # 2. Overall Day Streaks with Freeze Protection
    overall_current = 0
    today_rec = records_by_date.get(today)
    today_prog = float(today_rec.get("progress", 0.0)) if today_rec else 0.0
    today_frz = is_day_frozen(today_rec)

    if today_prog >= 0.50 or today_frz:
        overall_current = 1 if today_prog >= 0.50 else 0
        check_date = today - timedelta(days=1)
    else:
        yesterday = today - timedelta(days=1)
        yest_rec = records_by_date.get(yesterday)
        yest_prog = float(yest_rec.get("progress", 0.0)) if yest_rec else 0.0
        yest_frz = is_day_frozen(yest_rec)

        if yest_prog >= 0.50 or yest_frz:
            overall_current = 1 if yest_prog >= 0.50 else 0
            check_date = yesterday - timedelta(days=1)
        else:
            overall_current = 0
            check_date = None

    if check_date:
        while True:
            rec = records_by_date.get(check_date)
            if not rec:
                break
            if is_day_frozen(rec):
                check_date -= timedelta(days=1)
                continue

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
        frz = is_day_frozen(rec)

        if prog >= 0.50:
            if last_d is not None and (d - last_d).days == 1:
                temp_overall += 1
            else:
                temp_overall = 1
            overall_best = max(overall_best, temp_overall)
            last_d = d
        elif frz:
            if last_d is not None and (d - last_d).days == 1:
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


def calculate_consistency_matrix(
    period_key: str = "7d",
    history_pages: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Calculates detailed quality breakdown, habit ranking, and timeline for a given period.
    """
    if history_pages is None:
        history_pages = query_habit_history(limit_count=100)

    today = _get_tehran_today()
    j_today = jdatetime.date.fromgregorian(date=today)

    if period_key == "month":
        j_start = jdatetime.date(j_today.year, j_today.month, 1)
        start_date = j_start.togregorian()
        period_label = f"ماه جاری ({j_today.strftime('%B %Y')})"
        days_in_period = (today - start_date).days + 1
    elif period_key == "30d":
        start_date = today - timedelta(days=29)
        period_label = "۳۰ روز اخیر"
        days_in_period = 30
    else:
        period_key = "7d"
        start_date = today - timedelta(days=6)
        period_label = "۷ روز اخیر"
        days_in_period = 7

    records_by_date: Dict[date, Dict[str, Any]] = {}
    for page in history_pages:
        raw_date = page.get("date_iso")
        if not raw_date:
            continue
        try:
            d_obj = date.fromisoformat(raw_date)
            if start_date <= d_obj <= today:
                records_by_date[d_obj] = page
        except Exception:
            continue

    total_possible_checks = days_in_period * len(HABIT_ITEMS)
    quality_counts = {
        "v1": 0,
        "v2": 0,
        "v3": 0,
        "v4": 0,
        "v5": 0,
        "none": 0,
    }

    per_habit_counts: Dict[str, Dict[str, int]] = {
        h: {"completed": 0, "v1": 0, "v2": 0, "v3": 0, "v4": 0, "v5": 0, "none": 0}
        for h in HABIT_ITEMS.keys()
    }

    daily_timeline: List[Dict[str, Any]] = []

    cur_date = start_date
    while cur_date <= today:
        page = records_by_date.get(cur_date)
        j_cur = jdatetime.date.fromgregorian(date=cur_date)
        day_prog = float(page.get("progress", 0.0)) if page else 0.0
        frz = is_day_frozen(page)

        daily_timeline.append({
            "date_iso": cur_date.isoformat(),
            "jalali_str": j_cur.strftime("%m/%d"),
            "weekday": j_cur.strftime("%a"),
            "progress": day_prog,
            "has_data": page is not None,
            "is_frozen": frz,
        })

        if page:
            habits_data = page.get("habits", {})
            for h_key in HABIT_ITEMS.keys():
                val = habits_data.get(h_key)
                if val == "1-💪 کامل":
                    quality_counts["v1"] += 1
                    per_habit_counts[h_key]["v1"] += 1
                    per_habit_counts[h_key]["completed"] += 1
                elif val == "2-🏃‍♂️ نیمه‌کامل":
                    quality_counts["v2"] += 1
                    per_habit_counts[h_key]["v2"] += 1
                    per_habit_counts[h_key]["completed"] += 1
                elif val == "3-🐢 سبک":
                    quality_counts["v3"] += 1
                    per_habit_counts[h_key]["v3"] += 1
                    per_habit_counts[h_key]["completed"] += 1
                elif val == "4-❌ با دلیل":
                    quality_counts["v4"] += 1
                    per_habit_counts[h_key]["v4"] += 1
                elif val == "5-⛔ بدون دلیل":
                    quality_counts["v5"] += 1
                    per_habit_counts[h_key]["v5"] += 1
                else:
                    quality_counts["none"] += 1
                    per_habit_counts[h_key]["none"] += 1
        else:
            for h_key in HABIT_ITEMS.keys():
                quality_counts["none"] += 1
                per_habit_counts[h_key]["none"] += 1

        cur_date += timedelta(days=1)

    total_completed = (
        quality_counts["v1"] + quality_counts["v2"] + quality_counts["v3"]
    )
    overall_consistency_pct = (
        (total_completed / total_possible_checks) * 100
        if total_possible_checks > 0
        else 0.0
    )

    habit_rankings: List[Dict[str, Any]] = []
    for h_key, h_info in HABIT_ITEMS.items():
        comp = per_habit_counts[h_key]["completed"]
        pct = (comp / days_in_period) * 100 if days_in_period > 0 else 0.0
        habit_rankings.append({
            "key": h_key,
            "info": h_info,
            "completed_days": comp,
            "pct": pct,
            "breakdown": per_habit_counts[h_key],
        })

    habit_rankings.sort(key=lambda x: x["pct"], reverse=True)

    top_habit = habit_rankings[0] if habit_rankings else None
    bottom_habit = habit_rankings[-1] if habit_rankings else None

    return {
        "period_key": period_key,
        "period_label": period_label,
        "days_in_period": days_in_period,
        "logged_days_count": len(records_by_date),
        "overall_consistency_pct": overall_consistency_pct,
        "total_completed": total_completed,
        "total_possible": total_possible_checks,
        "quality_counts": quality_counts,
        "habit_rankings": habit_rankings,
        "top_habit": top_habit,
        "bottom_habit": bottom_habit,
        "daily_timeline": daily_timeline,
    }