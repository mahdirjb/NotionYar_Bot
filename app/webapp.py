# app/webapp.py

import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Depends, HTTPException, Header, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.config import BOT_TOKEN, ADMIN_USERS
from app.services.auth_service import (
    is_user_registered,
    get_user_role,
    has_permission,
    PERM_ADD_TIME,
    PERM_VIEW_REPORTS,
    PERM_ADMIN
)
from app.services.notion_service import (
    get_workspace_persons,
    add_time_tracker_entry,
    query_time_tracker_entries,
    LIFE_TRACKER_TYPES,
    TYPE_MODE_MAPPING,
    TYPE_EMOJIS,
    MODE_EMOJIS,
    add_life_tracker_entry,
    query_life_tracker_entries,
    get_or_create_habit_day,
    parse_habit_page,
    update_habit_entry,
    bulk_update_all_habits,
    update_habit_notes,
    update_habit_gratitude,
    update_habit_quran_detail,
    update_habit_book_detail,
    archive_notion_page,
    HABIT_ITEMS,
    HABIT_DESCRIPTIONS,
    HABIT_LEVELS,
    get_persian_cheerleader
)
from app.services.date_helper import format_jalali_full_display, get_jalali_date_info
from app.services.insights_service import calculate_habit_insights
from app.services.habit_analytics_service import calculate_habit_streaks, calculate_consistency_matrix

from aiogram.utils.web_app import safe_parse_webapp_init_data, check_webapp_signature

app = FastAPI(title="NotionYar Telegram Mini App API", version="2.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 🔐 AUTHENTICATION & DEPENDENCY
# ==========================================

async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
) -> Dict[str, Any]:
    """
    Validates Telegram WebApp initData or falls back to dev mode if testing in browser.
    """
    if x_telegram_init_data and BOT_TOKEN:
        try:
            init_data = safe_parse_webapp_init_data(token=BOT_TOKEN, init_data=x_telegram_init_data)
            if init_data and init_data.user:
                user_id = init_data.user.id
                if not is_user_registered(user_id):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="شما اجازه دسترسی به این ربات را ندارید."
                    )
                role = get_user_role(user_id) or "member"
                return {
                    "id": user_id,
                    "first_name": init_data.user.first_name or "",
                    "last_name": init_data.user.last_name or "",
                    "username": init_data.user.username or "",
                    "role": role,
                    "can_add_time": has_permission(user_id, PERM_ADD_TIME),
                    "can_view_reports": has_permission(user_id, PERM_VIEW_REPORTS),
                    "is_admin": has_permission(user_id, PERM_ADMIN)
                }
        except HTTPException:
            raise
        except Exception:
            pass

    # Development Fallback
    allow_dev_bypass = os.getenv("ALLOW_DEV_BYPASS", "true").lower() == "true"
    if allow_dev_bypass:
        mock_id = ADMIN_USERS[0] if ADMIN_USERS else 999999999
        return {
            "id": mock_id,
            "first_name": "کاربر توسعه‌دهنده (تست)",
            "last_name": "",
            "username": "dev_user",
            "role": "admin",
            "can_add_time": True,
            "can_view_reports": True,
            "is_admin": True,
            "_is_dev_mock": True
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="اعتبارسنجی تلگرام ناموفق بود."
    )


# ==========================================
# 📦 REQUEST MODELS
# ==========================================

class TimeTrackerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    date_iso: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    manual_duration: Optional[int] = None
    satisfaction: Optional[str] = None
    description: Optional[str] = None


class LifeTrackerCreateRequest(BaseModel):
    event_type: str
    mode: Optional[str] = None
    date_iso: Optional[str] = None
    notes: Optional[str] = None


class HabitStatusUpdateRequest(BaseModel):
    page_id: str
    habit_key: Optional[str] = None
    habit_prop: Optional[str] = None
    select_val: Optional[str] = None  # "1-💪 کامل", "2-🏃‍♂️ نیمه‌کامل", "3-🐢 سبک", "فریز", None


class HabitBulkCompleteRequest(BaseModel):
    page_id: str
    select_val: str = "1-💪 کامل"


class HabitTextUpdateRequest(BaseModel):
    page_id: str
    field: str  # "notes", "gratitude", "quran", "book"
    text: str


# ==========================================
# 🚀 COMMON & PROFILE ENDPOINTS
# ==========================================

@app.get("/api/me")
async def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    tz = timezone(timedelta(hours=3, minutes=30))
    today_iso = datetime.now(tz).strftime("%Y-%m-%d")
    jalali_today = format_jalali_full_display(today_iso)

    return {
        "user": user,
        "today_iso": today_iso,
        "today_jalali": jalali_today
    }


# ==========================================
# ⏱ TIME TRACKER ENDPOINTS
# ==========================================

@app.get("/api/time-tracker/meta")
async def get_time_tracker_meta(user: Dict[str, Any] = Depends(get_current_user)):
    persons = await asyncio.to_thread(get_workspace_persons)
    satisfaction_options = [
        {"value": "1", "label": "۱ - ضعیف", "emoji": "😞"},
        {"value": "2", "label": "۲ - قابل قبول", "emoji": "😐"},
        {"value": "3", "label": "۳ - خوب", "emoji": "🙂"},
        {"value": "4", "label": "۴ - خیلی خوب", "emoji": "😃"},
        {"value": "5", "label": "۵ - عالی", "emoji": "🤩"},
    ]
    return {
        "persons": persons,
        "satisfaction_options": satisfaction_options
    }


@app.post("/api/time-tracker/create")
async def create_time_tracker_entry(
    payload: TimeTrackerCreateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    if not user.get("can_add_time"):
        raise HTTPException(status_code=403, detail="شما مجوز ثبت زمان را ندارید.")

    tz = timezone(timedelta(hours=3, minutes=30))
    date_str = payload.date_iso or datetime.now(tz).strftime("%Y-%m-%d")

    res = await asyncio.to_thread(
        add_time_tracker_entry,
        task_name=payload.name.strip(),
        person_id=payload.person_id,
        date_str=date_str,
        start_time=payload.start_time,
        end_time=payload.end_time,
        manual_duration=payload.manual_duration,
        satisfaction=payload.satisfaction,
        description=payload.description
    )

    if not res:
        raise HTTPException(status_code=500, detail="خطا در ثبت رکورد در نوشن.")

    return {"success": True, "page_id": res.get("id")}


@app.delete("/api/time-tracker/delete/{page_id}")
async def delete_time_tracker_entry(
    page_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    success = await asyncio.to_thread(archive_notion_page, page_id)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در حذف رکورد زمان.")
    return {"success": True}


# ==========================================
# 🌱 LIFE TRACKER ENDPOINTS (REVAMPED)
# ==========================================

@app.get("/api/life-tracker/options")
async def get_life_tracker_options(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns grouped categories and their modes for an intuitive UI."""
    groups = [
        {
            "title": "نظافت و آراستگی",
            "emoji": "💈",
            "types": ["آرایشگاه", "ریش و سبیل", "موپالمو", "خورشید", "آینه", "ناخن دست", "ناخن پا"]
        },
        {
            "title": "سلامتی و درمان",
            "emoji": "💊",
            "types": ["ویتامین دی", "مریضی"]
        },
        {
            "title": "نقلیه و رفت‌وآمد",
            "emoji": "🚗",
            "types": ["رانندگی", "دوری"]
        },
        {
            "title": "خرید و رویدادها",
            "emoji": "🛒",
            "types": ["خرید", "اتفاقات", "سایر"]
        }
    ]

    all_types_meta = {}
    for t in LIFE_TRACKER_TYPES:
        all_types_meta[t] = {
            "name": t,
            "emoji": TYPE_EMOJIS.get(t, "🌱"),
            "modes": [
                {"name": m, "emoji": MODE_EMOJIS.get(m, "🔹")}
                for m in TYPE_MODE_MAPPING.get(t, [])
            ]
        }

    return {
        "groups": groups,
        "all_types": all_types_meta
    }


@app.post("/api/life-tracker/create")
async def create_life_tracker_entry(
    payload: LifeTrackerCreateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    tz = timezone(timedelta(hours=3, minutes=30))
    date_str = payload.date_iso or datetime.now(tz).strftime("%Y-%m-%d")

    res = await asyncio.to_thread(
        add_life_tracker_entry,
        event_type=payload.event_type,
        mode=payload.mode,
        date_str=date_str,
        notes=payload.notes
    )

    if not res:
        raise HTTPException(status_code=500, detail="خطا در ذخیره رکورد در روزمرگی نوشن.")

    return {"success": True, "page_id": res.get("id")}


@app.get("/api/life-tracker/insights")
async def get_life_tracker_insights(user: Dict[str, Any] = Depends(get_current_user)):
    """Calculates routines, intervals, averages and overdue alerts."""
    try:
        insights = await asyncio.to_thread(calculate_habit_insights)
        return {"insights": insights}
    except Exception as e:
        return {"insights": {}, "error": str(e)}


@app.get("/api/life-tracker/history")
async def get_life_tracker_history(
    event_type: Optional[str] = Query(None),
    limit: int = Query(30),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Returns past life tracker logs with optional type filter."""
    try:
        entries = await asyncio.to_thread(query_life_tracker_entries, page_size=limit)
        if event_type:
            entries = [e for e in entries if e.get("type") == event_type]

        results = []
        for item in entries:
            t_name = item.get("type", "")
            results.append({
                "id": item.get("id"),
                "type": t_name,
                "emoji": TYPE_EMOJIS.get(t_name, "🌱"),
                "mode": item.get("mode", ""),
                "date": item.get("date", "—"),
                "date_iso": item.get("date_iso", ""),
                "notes": item.get("notes", "")
            })

        return {"entries": results}
    except Exception as e:
        return {"entries": [], "error": str(e)}


@app.delete("/api/life-tracker/delete/{page_id}")
async def delete_life_tracker_entry(
    page_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    success = await asyncio.to_thread(archive_notion_page, page_id)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در حذف رکورد روزمرگی.")
    return {"success": True}


# ==========================================
# 🎯 HABITS TRACKER ENDPOINTS (REVAMPED)
# ==========================================

@app.get("/api/habits/day")
async def get_habits_day(
    date_iso: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Returns habit checklist with categories, progress, and reflections."""
    tz = timezone(timedelta(hours=3, minutes=30))
    if not date_iso:
        date_iso = datetime.now(tz).strftime("%Y-%m-%d")

    jalali_title = format_jalali_full_display(date_iso)

    try:
        page = await asyncio.to_thread(get_or_create_habit_day, date_iso, jalali_title)
        parsed = parse_habit_page(page)
    except Exception as e:
        parsed = {"id": "", "progress": 0.0, "habits": {}, "cheerleader": "روز خوبی بساز! 🌟"}

    # Group habits by category
    categories = {
        "ذهنی": {"title": "ذهن و تمرکز", "emoji": "🧘", "habits": []},
        "جسمی": {"title": "جسم و سلامتی", "emoji": "🏃", "habits": []},
        "نظم": {"title": "نظم و محیط", "emoji": "🛏️", "habits": []},
        "معنوی": {"title": "معنوی و آرامش", "emoji": "🕊️", "habits": []}
    }

    total_habits = len(HABIT_ITEMS)
    completed_count = 0

    for h_key, h_info in HABIT_ITEMS.items():
        val = parsed.get("habits", {}).get(h_key)
        is_done = val in ("1-💪 کامل", "2-🏃‍♂️ نیمه‌کامل", "3-🐢 سبک")
        if is_done:
            completed_count += 1

        cat = h_info.get("cat", "سایر")
        if cat not in categories:
            categories[cat] = {"title": cat, "emoji": "🎯", "habits": []}

        categories[cat]["habits"].append({
            "key": h_key,
            "prop": h_info["prop"],
            "name": h_info["fa"],
            "emoji": h_info["emoji"],
            "is_binary": h_info.get("binary", False),
            "description": HABIT_DESCRIPTIONS.get(h_key, {}).get("v1", ""),
            "levels": HABIT_DESCRIPTIONS.get(h_key, {}),
            "status": val,
            "is_done": is_done
        })

    progress_pct = int(round(parsed.get("progress", 0.0) * 100))

    return {
        "page_id": parsed.get("id"),
        "date_iso": date_iso,
        "jalali_title": jalali_title,
        "progress_float": parsed.get("progress", 0.0),
        "progress_percent": progress_pct,
        "completed_count": completed_count,
        "total_habits": total_habits,
        "cheerleader": parsed.get("cheerleader", "روز خوبی بساز! 🌟"),
        "categories": categories,
        "notes": parsed.get("notes", ""),
        "gratitude": parsed.get("gratitude_log", ""),
        "quran_detail": parsed.get("quran_detail", ""),
        "book_detail": parsed.get("book_detail", "")
    }


@app.post("/api/habits/update-status")
async def update_habit_status(
    payload: HabitStatusUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Updates a single habit using either key (bt) or prop (Brush Teeth)."""
    prop_name = payload.habit_prop
    if not prop_name and payload.habit_key in HABIT_ITEMS:
        prop_name = HABIT_ITEMS[payload.habit_key]["prop"]

    if not prop_name:
        raise HTTPException(status_code=400, detail="مشخصه عادت نامعتبر است.")

    success = await asyncio.to_thread(
        update_habit_entry,
        payload.page_id,
        prop_name,
        payload.select_val
    )
    if not success:
        raise HTTPException(status_code=500, detail="خطا در به‌روزرسانی عادت در نوشن.")
    return {"success": True}


@app.post("/api/habits/bulk-complete")
async def bulk_complete_habits(
    payload: HabitBulkCompleteRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Marks all habits as completed for the day in one click!"""
    success = await asyncio.to_thread(
        bulk_update_all_habits,
        payload.page_id,
        payload.select_val
    )
    if not success:
        raise HTTPException(status_code=500, detail="خطا در تکمیل خودکار عادات.")
    return {"success": True}


@app.get("/api/habits/analytics")
async def get_habits_analytics(
    period: str = Query("7d"),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Returns streaks, 7-day consistency heatmap, and habit rankings."""
    try:
        streaks = await asyncio.to_thread(calculate_habit_streaks, None, 100)
    except Exception as e:
        streaks = {}

    try:
        matrix = await asyncio.to_thread(calculate_consistency_matrix, period, None)
    except Exception as e:
        matrix = {}

    return {
        "streaks": streaks,
        "matrix": matrix
    }


@app.post("/api/habits/update-text")
async def update_habit_text(
    payload: HabitTextUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    if payload.field == "notes":
        success = await asyncio.to_thread(update_habit_notes, payload.page_id, payload.text)
    elif payload.field == "gratitude":
        success = await asyncio.to_thread(update_habit_gratitude, payload.page_id, payload.text)
    elif payload.field == "quran":
        success = await asyncio.to_thread(update_habit_quran_detail, payload.page_id, payload.text)
    elif payload.field == "book":
        success = await asyncio.to_thread(update_habit_book_detail, payload.page_id, payload.text)
    else:
        raise HTTPException(status_code=400, detail="فیلد نامعتبر است.")

    if not success:
        raise HTTPException(status_code=500, detail="خطا در ذخیره متن در نوشن.")
    return {"success": True}


# ==========================================
# 📜 RECENT ACTIVITY LOGS
# ==========================================

@app.get("/api/recent-logs")
async def get_recent_logs(user: Dict[str, Any] = Depends(get_current_user)):
    try:
        time_entries = await asyncio.to_thread(query_time_tracker_entries, page_size=5)
    except Exception:
        time_entries = []

    try:
        life_entries = await asyncio.to_thread(query_life_tracker_entries, page_size=5)
    except Exception:
        life_entries = []

    recent_time = []
    for item in time_entries:
        recent_time.append({
            "id": item.get("id"),
            "name": item.get("name", "بدون عنوان"),
            "date": item.get("date", "—"),
            "time_range": f"{item.get('start_time') or ''} - {item.get('end_time') or ''}".strip(" -"),
            "duration": item.get("duration", "—"),
            "person": item.get("person", "—"),
            "satisfaction": item.get("satisfaction", "—")
        })

    recent_life = []
    for item in life_entries:
        recent_life.append({
            "id": item.get("id"),
            "type": item.get("type", "—"),
            "emoji": TYPE_EMOJIS.get(item.get("type", ""), "🌱"),
            "mode": item.get("mode", "—"),
            "date": item.get("date", "—"),
            "notes": item.get("notes", "")
        })

    return {
        "time_tracker": recent_time,
        "life_tracker": recent_life
    }


# ==========================================
# 🌐 STATIC FILES & FRONTEND
# ==========================================

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"status": "running", "message": "NotionYar Mini App API is ready"})
