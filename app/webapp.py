# app/webapp.py

import os
import json
import hmac
import hashlib
import asyncio
from urllib.parse import parse_qsl, unquote
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Depends, HTTPException, Header, status
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
    update_habit_notes,
    update_habit_gratitude,
    update_habit_quran_detail,
    update_habit_book_detail,
    HABIT_ITEMS,
    HABIT_DESCRIPTIONS,
    get_persian_cheerleader
)
from app.services.date_helper import format_jalali_full_display, get_jalali_date_info

app = FastAPI(title="NotionYar Telegram Mini App API", version="1.0.0")

# Enable CORS for local testing or custom web app domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 🔐 TELEGRAM AUTHENTICATION & VALIDATION
# ==========================================

def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Validates data received from Telegram WebApp according to official Telegram docs:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not bot_token:
        return None

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed:
            return None

        received_hash = parsed.pop("hash")

        # Sort the pairs in alphabetical order: key=value\nkey2=value2...
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        # Secret key is HMAC-SHA256 of bot_token with "WebAppData"
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

        # Calculated hash
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        # Extract user object
        user_raw = parsed.get("user")
        if user_raw:
            user_data = json.loads(user_raw)
            return user_data

        return None
    except Exception as e:
        return None


async def get_current_user(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data")
) -> Dict[str, Any]:
    """
    Dependency to authenticate and authorize requests from the Telegram Mini App.
    In local development or debug mode, if header is absent, falls back to first admin.
    """
    # 1. Real Telegram Init Data check
    if x_telegram_init_data and BOT_TOKEN:
        user_info = validate_telegram_init_data(x_telegram_init_data, BOT_TOKEN)
        if user_info and "id" in user_info:
            user_id = int(user_info["id"])
            if not is_user_registered(user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="شما اجازه دسترسی به این ربات را ندارید."
                )
            role = get_user_role(user_id) or "member"
            return {
                "id": user_id,
                "first_name": user_info.get("first_name", ""),
                "last_name": user_info.get("last_name", ""),
                "username": user_info.get("username", ""),
                "role": role,
                "can_add_time": has_permission(user_id, PERM_ADD_TIME),
                "can_view_reports": has_permission(user_id, PERM_VIEW_REPORTS),
                "is_admin": has_permission(user_id, PERM_ADMIN)
            }

    # 2. Local development fallback (Allows viewing Mini App in regular desktop browser during development)
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
# 📦 PYDANTIC REQUEST MODELS
# ==========================================

class TimeTrackerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="عنوان کار یا تسک")
    person_id: Optional[str] = Field(None, description="شناسه شخص در نوشن")
    person_name: Optional[str] = Field(None, description="نام شخص")
    date_iso: Optional[str] = Field(None, description="تاریخ میلادی YYYY-MM-DD")
    start_time: Optional[str] = Field(None, description="ساعت شروع HH:MM")
    end_time: Optional[str] = Field(None, description="ساعت پایان HH:MM")
    manual_duration: Optional[int] = Field(None, description="مدت زمان به دقیقه")
    satisfaction: Optional[str] = Field(None, description="میزان رضایت ۱ تا ۵")
    description: Optional[str] = Field(None, description="توضیحات تسک")


class LifeTrackerCreateRequest(BaseModel):
    event_type: str = Field(..., description="نوع لاگ روزمرگی")
    mode: Optional[str] = Field(None, description="حالت یا زیرمجموعه")
    date_iso: Optional[str] = Field(None, description="تاریخ میلادی YYYY-MM-DD")
    notes: Optional[str] = Field(None, description="یادداشت")


class HabitStatusUpdateRequest(BaseModel):
    page_id: str
    habit_prop: str
    select_val: Optional[str] = None  # "انجام شد", "ناقص", "انجام نشد", "فریز", None


class HabitTextUpdateRequest(BaseModel):
    page_id: str
    field: str  # "notes", "gratitude", "quran", "book"
    text: str


# ==========================================
# 🚀 API ENDPOINTS
# ==========================================

@app.get("/api/me")
async def get_me(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns current authenticated user profile and permissions."""
    tz = timezone(timedelta(hours=3, minutes=30))
    today_iso = datetime.now(tz).strftime("%Y-%m-%d")
    jalali_today = format_jalali_full_display(today_iso)

    return {
        "user": user,
        "today_iso": today_iso,
        "today_jalali": jalali_today
    }


# ------------------------------------------
# ⏱ TIME TRACKER ENDPOINTS
# ------------------------------------------

@app.get("/api/time-tracker/meta")
async def get_time_tracker_meta(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns workspace persons and satisfaction choices for Time Tracker."""
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
    """Creates a new record in Notion Time Tracker database."""
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


# ------------------------------------------
# 🌱 LIFE TRACKER ENDPOINTS
# ------------------------------------------

@app.get("/api/life-tracker/options")
async def get_life_tracker_options(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns categories, modes and emojis for Life Tracker."""
    types_with_meta = []
    for t in LIFE_TRACKER_TYPES:
        types_with_meta.append({
            "name": t,
            "emoji": TYPE_EMOJIS.get(t, "🌱"),
            "modes": [
                {"name": m, "emoji": MODE_EMOJIS.get(m, "🔹")}
                for m in TYPE_MODE_MAPPING.get(t, [])
            ]
        })

    return {
        "types": types_with_meta
    }


@app.post("/api/life-tracker/create")
async def create_life_tracker_entry(
    payload: LifeTrackerCreateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Creates a new entry in Life Tracker database."""
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


# ------------------------------------------
# 🎯 HABITS TRACKER ENDPOINTS
# ------------------------------------------

@app.get("/api/habits/day")
async def get_habits_day(
    date_iso: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Returns habit checklist, progress, and reflections for the given date."""
    tz = timezone(timedelta(hours=3, minutes=30))
    if not date_iso:
        date_iso = datetime.now(tz).strftime("%Y-%m-%d")

    jalali_title = format_jalali_full_display(date_iso)

    # Fetch or create habit day page in Notion
    page = await asyncio.to_thread(get_or_create_habit_day, date_iso, jalali_title)
    parsed = parse_habit_page(page)

    # Format habits with their definitions
    habits_list = []
    for h_name in HABIT_ITEMS:
        current_status = parsed.get("habits", {}).get(h_name)
        habits_list.append({
            "name": h_name,
            "description": HABIT_DESCRIPTIONS.get(h_name, ""),
            "status": current_status
        })

    cheerleader = get_persian_cheerleader(parsed.get("progress_float", 0.0))

    return {
        "page_id": parsed.get("page_id"),
        "date_iso": date_iso,
        "jalali_title": jalali_title,
        "progress_float": parsed.get("progress_float", 0.0),
        "progress_percent": int(round(parsed.get("progress_float", 0.0) * 100)),
        "cheerleader": cheerleader,
        "habits": habits_list,
        "notes": parsed.get("notes", ""),
        "gratitude": parsed.get("gratitude", ""),
        "quran_detail": parsed.get("quran_detail", ""),
        "book_detail": parsed.get("book_detail", "")
    }


@app.post("/api/habits/update-status")
async def update_habit_status(
    payload: HabitStatusUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Updates the status of a specific habit for a day."""
    success = await asyncio.to_thread(
        update_habit_entry,
        payload.page_id,
        payload.habit_prop,
        payload.select_val
    )
    if not success:
        raise HTTPException(status_code=500, detail="خطا در به‌روزرسانی عادت در نوشن.")
    return {"success": True}


@app.post("/api/habits/update-text")
async def update_habit_text(
    payload: HabitTextUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Updates reflection text fields (notes, gratitude, quran, book)."""
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
        raise HTTPException(status_code=500, detail="خطا در ذخیره یادداشت در نوشن.")
    return {"success": True}


# ------------------------------------------
# 📜 RECENT ACTIVITY LOGS
# ------------------------------------------

@app.get("/api/recent-logs")
async def get_recent_logs(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns recent Time Tracker and Life Tracker entries for quick overview."""
    time_entries = await asyncio.to_thread(query_time_tracker_entries, page_size=5)
    life_entries = await asyncio.to_thread(query_life_tracker_entries, page_size=5)

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
# 🌐 STATIC FILES & FRONTEND APP
# ==========================================

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index():
    """Serves the Telegram Mini App single-page frontend."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"status": "running", "message": "NotionYar Mini App API is ready"})
