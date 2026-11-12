# app/webapp.py

import os
import asyncio
import logging
import base64
import hashlib
import hmac
import json
import time
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, Depends, HTTPException, Header, status, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.config import (
    BOT_TOKEN,
    ADMIN_USERS,
    NOTION_DBID_LIFE_TRACKER,
    NOTION_DBID_HABITS,
    NOTION_DBID_QURAN,
    WEB_LOGIN_USERNAME,
    WEB_LOGIN_PASSWORD,
    WEB_LOGIN_PASSWORD_HASH,
    WEB_SESSION_SECRET,
    WEB_SESSION_DAYS,
    WEB_COOKIE_SECURE,
    ALLOWED_HOSTS,
)
from app.services.auth_service import (
    is_user_registered,
    get_user_role,
    has_permission,
    get_all_users,
    add_or_update_user,
    remove_user,
    PERM_ADD_TIME,
    PERM_VIEW_REPORTS,
    PERM_ADMIN
)
from app.services.notion_service import (
    LIFE_TRACKER_TYPES,
    TYPE_MODE_MAPPING,
    TYPE_EMOJIS,
    MODE_EMOJIS,
    add_life_tracker_entry,
    update_life_tracker_entry,
    query_life_tracker_entries,
    query_habit_history,
    get_or_create_habit_day,
    update_habit_entry,
    bulk_update_all_habits,
    batch_update_habit_dict,
    update_habit_notes,
    update_habit_gratitude,
    update_habit_quran_detail,
    update_habit_book_detail,
    archive_notion_page,
    reset_habit_day,
    parse_existing_gratitude_log,
    HABIT_ITEMS,
    HABIT_DESCRIPTIONS,
    HABIT_LEVELS,
    get_persian_cheerleader,
    get_or_create_salah_day,
    update_salah_prayer_status,
    bulk_mark_salah_ada,
    bulk_mark_salah_reset,
    bulk_mark_salah_range_ada,
    update_salah_notes,
    add_quran_reading_entry,
    query_quran_entries,
    get_spiritual_report,
)
from app.services.date_helper import format_jalali_full_display, get_preset_date_range
from app.services.insights_service import calculate_habit_insights
from app.services.habit_analytics_service import calculate_habit_streaks, calculate_consistency_matrix

from aiogram.utils.web_app import safe_parse_webapp_init_data

app = FastAPI(title="NotionYar Web & Telegram API", version="3.0.0")
logger = logging.getLogger(__name__)
SESSION_COOKIE_NAME = "notionyar_session"
_login_attempts: Dict[str, List[float]] = {}


# Enable CORS
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=bool(cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
if ALLOWED_HOSTS:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


# ==========================================
# 🔐 AUTHENTICATION & DEPENDENCY
# ==========================================

def _web_login_is_configured() -> bool:
    has_password = bool(WEB_LOGIN_PASSWORD_HASH or WEB_LOGIN_PASSWORD)
    return bool(WEB_LOGIN_USERNAME and has_password and len(WEB_SESSION_SECRET) >= 32)


def _verify_web_password(password: str) -> bool:
    if WEB_LOGIN_PASSWORD_HASH:
        try:
            algorithm, iterations_raw, salt_raw, digest_raw = WEB_LOGIN_PASSWORD_HASH.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            iterations = int(iterations_raw)
            salt = base64.urlsafe_b64decode(salt_raw.encode("ascii"))
            expected = base64.urlsafe_b64decode(digest_raw.encode("ascii"))
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False
    return bool(WEB_LOGIN_PASSWORD) and hmac.compare_digest(password, WEB_LOGIN_PASSWORD)


def _create_web_session(username: str) -> str:
    payload = {
        "sub": username,
        "exp": int(time.time()) + (WEB_SESSION_DAYS * 86400),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(
        WEB_SESSION_SECRET.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def _verify_web_session(token: Optional[str]) -> Optional[str]:
    if not token or not _web_login_is_configured():
        return None
    try:
        encoded, signature = token.rsplit(".", 1)
        expected = hmac.new(
            WEB_SESSION_SECRET.encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        username = str(payload.get("sub", ""))
        return username if hmac.compare_digest(username, WEB_LOGIN_USERNAME) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _web_admin_user(username: str) -> Dict[str, Any]:
    return {
        "id": ADMIN_USERS[0] if ADMIN_USERS else 0,
        "first_name": username,
        "last_name": "",
        "username": username,
        "role": "admin",
        "can_add_time": False,
        "can_view_reports": True,
        "is_admin": True,
        "auth_source": "web",
    }


def _check_login_rate_limit(client_key: str) -> None:
    now = time.time()
    recent = [attempt for attempt in _login_attempts.get(client_key, []) if now - attempt < 600]
    if len(recent) >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تعداد تلاش‌های ورود بیش از حد مجاز است. کمی بعد دوباره تلاش کنید.",
        )
    recent.append(now)
    _login_attempts[client_key] = recent


async def get_current_user(
    request: Request,
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
                if not has_permission(user_id, PERM_ADMIN):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="مینی‌اپ در حال حاضر فقط برای مدیران فعال است."
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

    web_username = _verify_web_session(request.cookies.get(SESSION_COOKIE_NAME))
    if web_username:
        return _web_admin_user(web_username)

    # Development Fallback
    allow_dev_bypass = os.getenv("ALLOW_DEV_BYPASS", "false").lower() == "true"
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
        detail="برای ادامه وارد حساب وب شوید."
    )


# ==========================================
# 📦 REQUEST MODELS
# ==========================================

class LifeTrackerCreateRequest(BaseModel):
    event_type: str
    mode_list: Optional[List[str]] = None
    mode: Optional[str] = None  # fallback for single string
    date_iso: Optional[str] = None
    notes: Optional[str] = None


class LifeTrackerUpdateRequest(BaseModel):
    event_type: Optional[str] = None
    mode_list: Optional[List[str]] = None
    date_iso: Optional[str] = None
    notes: Optional[str] = None


class HabitStatusUpdateRequest(BaseModel):
    page_id: str
    habit_key: Optional[str] = None
    habit_prop: Optional[str] = None
    select_val: Optional[str] = None  # "1-💪 کامل", "2-🏃‍♂️ نیمه‌کامل", "3-🐢 سبک", "4-❌ با دلیل", "5-⛔ بدون دلیل", None


class HabitBulkCompleteRequest(BaseModel):
    page_id: str
    select_val: str = "1-💪 کامل"


class HabitFreezeRequest(BaseModel):
    page_id: str
    reason: str = "استراحت و ریکاوری"


class HabitResetRequest(BaseModel):
    page_id: str


class HabitTextUpdateRequest(BaseModel):
    page_id: str
    field: str  # "notes", "gratitude", "quran", "book"
    text: str
    date_iso: Optional[str] = None


class GratitudeSaveRequest(BaseModel):
    page_id: str
    date_iso: Optional[str] = None
    items: List[Dict[str, str]]  # list of {"tag": "...", "text": "..."}


class HabitBatchUpdateRequest(BaseModel):
    page_id: str
    updates: Dict[str, Optional[str]]


class AdminUserSaveRequest(BaseModel):
    user_id: int
    name: str
    role: str = "member"


class SpiritualPrayerToggleRequest(BaseModel):
    page_id: str
    prayer_key: str
    target_status: Optional[str] = None  # "ada", "qaza", "none", or None to cycle


class SpiritualBulkRequest(BaseModel):
    page_id: str


class SpiritualBulkRangeRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    preset: Optional[str] = None  # "7d", "14d", "month", "30d", or None


class SpiritualNotesRequest(BaseModel):
    page_id: str
    notes: str


class QuranCreateRequest(BaseModel):
    date_iso: Optional[str] = None
    pages: str
    session_name: Optional[str] = None


class WebLoginRequest(BaseModel):
    username: str
    password: str



# ==========================================
# 🚀 COMMON & PROFILE ENDPOINTS
# ==========================================

@app.post("/api/auth/login")
async def web_login(payload: WebLoginRequest, request: Request, response: Response):
    if not _web_login_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ورود وب هنوز روی سرور تنظیم نشده است.",
        )

    client_key = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_key)
    valid_username = hmac.compare_digest(payload.username.strip(), WEB_LOGIN_USERNAME)
    if not valid_username or not _verify_web_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور صحیح نیست.",
        )

    _login_attempts.pop(client_key, None)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=_create_web_session(WEB_LOGIN_USERNAME),
        max_age=WEB_SESSION_DAYS * 86400,
        httponly=True,
        secure=WEB_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return {"success": True}


@app.post("/api/auth/logout")
async def web_logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=WEB_COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    return {"success": True}

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
# 🌱 LIFE TRACKER ENDPOINTS (UPDATED CATEGORIES)
# ==========================================

@app.get("/api/life-tracker/options")
async def get_life_tracker_options(user: Dict[str, Any] = Depends(get_current_user)):
    """
    Returns updated groupings:
    1. نظافت و آراستگی (شامل دوری)
    2. سلامتی
    3. رویدادها (شامل رانندگی)
    """
    groups = [
        {
            "title": "نظافت و آراستگی",
            "emoji": "💈",
            "types": ["آرایشگاه", "ریش و سبیل", "موپالمو", "خورشید", "آینه", "ناخن دست", "ناخن پا", "دوری"]
        },
        {
            "title": "سلامتی",
            "emoji": "💊",
            "types": ["ویتامین دی", "مریضی"]
        },
        {
            "title": "رویدادها",
            "emoji": "⚡",
            "types": ["رانندگی", "خرید", "اتفاقات", "سایر"]
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

    # Support multiple modes or empty modes list
    modes = payload.mode_list if payload.mode_list is not None else ([payload.mode] if payload.mode else [])

    res = await asyncio.to_thread(
        add_life_tracker_entry,
        name=f"{payload.event_type} - {date_str}",
        type_val=payload.event_type,
        date_iso=date_str,
        mode_list=modes,
        notes=payload.notes or ""
    )

    if not res:
        raise HTTPException(status_code=500, detail="خطا در ذخیره رکورد در روزمرگی نوشن.")

    return {"success": True, "page_id": res.get("id")}


@app.get("/api/life-tracker/insights")
async def get_life_tracker_insights(user: Dict[str, Any] = Depends(get_current_user)):
    try:
        insights = await asyncio.to_thread(calculate_habit_insights)
        return {"insights": insights}
    except Exception as e:
        return {"insights": {}, "error": str(e)}


@app.get("/api/life-tracker/history")
async def get_life_tracker_history(
    event_type: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Fetches real history records from Notion with correct parameter passing."""
    try:
        entries = await asyncio.to_thread(
            query_life_tracker_entries,
            start_date_iso=None,
            end_date_iso=None,
            type_val=event_type if event_type else None,
            mode_val=None
        )

        results = []
        for item in entries:
            t_name = item.get("type", "")
            iso_date = item.get("date_iso") or ""
            shamsi_date = format_jalali_full_display(iso_date) if iso_date else "—"
            modes_list = item.get("modes", [])
            modes_str = "، ".join(modes_list) if modes_list else ""

            results.append({
                "id": item.get("id"),
                "type": t_name,
                "emoji": TYPE_EMOJIS.get(t_name, "🌱"),
                "mode": modes_str,
                "modes": modes_list,
                "date": shamsi_date,
                "date_iso": iso_date,
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
    success = await asyncio.to_thread(
        archive_notion_page,
        page_id,
        NOTION_DBID_LIFE_TRACKER,
    )
    if not success:
        raise HTTPException(status_code=500, detail="خطا در حذف رکورد روزمرگی.")
    return {"success": True}


@app.put("/api/life-tracker/update/{page_id}")
@app.post("/api/life-tracker/update/{page_id}")
async def update_life_tracker_entry_endpoint(
    page_id: str,
    payload: LifeTrackerUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    success = await asyncio.to_thread(
        update_life_tracker_entry,
        page_id=page_id,
        type_val=payload.event_type,
        date_iso=payload.date_iso,
        mode_list=payload.mode_list,
        notes=payload.notes
    )
    if not success:
        raise HTTPException(status_code=500, detail="خطا در ویرایش رکورد روزمرگی.")
    return {"success": True}


# ==========================================
# 🎯 HABITS TRACKER ENDPOINTS (FIXED PARSING)
# ==========================================

@app.get("/api/habits/day")
async def get_habits_day(
    date_iso: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Returns habit checklist.
    Note: get_or_create_habit_day already returns a parsed dictionary!
    """
    tz = timezone(timedelta(hours=3, minutes=30))
    if not date_iso:
        date_iso = datetime.now(tz).strftime("%Y-%m-%d")

    jalali_title = format_jalali_full_display(date_iso)

    try:
        # get_or_create_habit_day returns parse_habit_page(page) directly!
        parsed = await asyncio.to_thread(get_or_create_habit_day, date_iso, jalali_title)
    except Exception as e:
        parsed = {"id": "", "progress": 0.0, "habits": {}, "cheerleader": "روز خوبی بساز! 🌟"}

    page_id = parsed.get("id") or ""

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
            "code": h_info.get("code", "HBT"),
            "name": h_info["fa"],
            "emoji": h_info["emoji"],
            "is_binary": h_info.get("binary", False),
            "description": HABIT_DESCRIPTIONS.get(h_key, {}).get("v1", ""),
            "levels": HABIT_DESCRIPTIONS.get(h_key, {}),
            "status": val,
            "is_done": is_done
        })

    progress_pct = int(round(float(parsed.get("progress", 0.0)) * 100))

    # Parse gratitude items into structured list
    raw_grat = parsed.get("gratitude_log", "")
    grat_items = parse_existing_gratitude_log(raw_grat)

    return {
        "page_id": page_id,
        "date_iso": date_iso,
        "jalali_title": jalali_title,
        "progress_float": parsed.get("progress", 0.0),
        "progress_percent": progress_pct,
        "completed_count": completed_count,
        "total_habits": total_habits,
        "cheerleader": parsed.get("cheerleader", "روز خوبی بساز! 🌟"),
        "categories": categories,
        "notes": parsed.get("notes", ""),
        "gratitude": raw_grat,
        "gratitude_items": grat_items,
        "quran_detail": parsed.get("quran_detail", ""),
        "book_detail": parsed.get("book_detail", "")
    }


@app.post("/api/habits/update-status")
async def update_habit_status(
    payload: HabitStatusUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Updates a single habit using either key (bt) or prop (Brush Teeth)."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

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
    """Marks all habits as completed for the day in one click."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    success = await asyncio.to_thread(
        bulk_update_all_habits,
        payload.page_id,
        payload.select_val
    )
    if not success:
        raise HTTPException(status_code=500, detail="خطا در تکمیل خودکار عادات.")
    return {"success": True}


@app.post("/api/habits/freeze-day")
async def freeze_habit_day(
    payload: HabitFreezeRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Sets streak freeze note on the day page to bridge continuous streak."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    freeze_tag = f"[❄️ روز فریز: {payload.reason}]"
    success = await asyncio.to_thread(update_habit_notes, payload.page_id, freeze_tag)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در ثبت فریز روز.")
    return {"success": True}


@app.post("/api/habits/reset-day")
async def reset_entire_habit_day(
    payload: HabitResetRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Resets all habit checkmarks on the day page."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    success = await asyncio.to_thread(reset_habit_day, payload.page_id)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در بازنشانی عادات روز.")
    return {"success": True}


@app.get("/api/habits/analytics")
async def get_habits_analytics(
    period: str = Query("7d"),
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Returns streaks, 7-day consistency heatmap, and habit rankings."""
    try:
        history = await asyncio.to_thread(query_habit_history, None)
    except Exception:
        history = []

    try:
        streaks = await asyncio.to_thread(calculate_habit_streaks, history, 0)
    except Exception:
        streaks = {}

    try:
        matrix = await asyncio.to_thread(calculate_consistency_matrix, period, history)
    except Exception:
        matrix = {}

    return {
        "streaks": streaks,
        "matrix": matrix
    }


@app.post("/api/habits/gratitude/save")
async def save_gratitude_journal(
    payload: GratitudeSaveRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Compiles individual gratitude items with category tags and saves to Notion."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    tz = timezone(timedelta(hours=3, minutes=30))
    date_str = payload.date_iso or datetime.now(tz).strftime("%Y-%m-%d")
    full_jalali = format_jalali_full_display(date_str)

    lines = [
        "🌸 دفتر شکرگزاری روزانه",
        f"📅 {full_jalali}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if payload.items:
        tagged_groups: Dict[str, List[str]] = {}
        for item in payload.items:
            tag = str(item.get("tag") or "سایر نعمات").strip()
            text = str(item.get("text") or "").strip()
            if text:
                tagged_groups.setdefault(tag, []).append(text)

        for tag, texts in tagged_groups.items():
            lines.append(f"🏷 [{tag}]:")
            for t in texts:
                lines.append(f"🌿 خدایا شکرت بابت {t}")
            lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤍 «الحمدلله ربّ العالمین علی کلّ حال»")
    compiled = "\n".join(lines)

    success = await asyncio.to_thread(update_habit_gratitude, payload.page_id, compiled)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در ذخیره دفترچه شکرگزاری.")
    return {"success": True, "compiled": compiled}


@app.post("/api/habits/update-text")
async def update_habit_text(
    payload: HabitTextUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    if payload.field == "notes":
        success = await asyncio.to_thread(update_habit_notes, payload.page_id, payload.text)
    elif payload.field == "gratitude":
        success = await asyncio.to_thread(update_habit_gratitude, payload.page_id, payload.text)
    elif payload.field == "quran":
        success = await asyncio.to_thread(update_habit_quran_detail, payload.page_id, payload.text)
        if success and payload.text.strip():
            try:
                tz = timezone(timedelta(hours=3, minutes=30))
                date_str = payload.date_iso or datetime.now(tz).strftime("%Y-%m-%d")
                title = f"تلاوت {format_jalali_full_display(date_str)}"
                await asyncio.to_thread(
                    add_quran_reading_entry,
                    date_iso=date_str,
                    pages_text=payload.text.strip(),
                    session_name=title
                )
                await asyncio.to_thread(update_habit_entry, payload.page_id, "Read Holy Quran", "1-💪 کامل")
            except Exception as e:
                logger.warning(f"Could not sync habit Quran detail to Quran database: {e}")
    elif payload.field == "book":
        success = await asyncio.to_thread(update_habit_book_detail, payload.page_id, payload.text)
        if success and payload.text.strip():
            try:
                await asyncio.to_thread(update_habit_entry, payload.page_id, "Read Book", "1-💪 کامل")
            except Exception as e:
                logger.warning(f"Could not mark Read Book complete: {e}")
    else:
        raise HTTPException(status_code=400, detail="فیلد نامعتبر است.")

    if not success:
        raise HTTPException(status_code=500, detail="خطا در ذخیره اطلاعات عادت.")
    return {"success": True}


@app.post("/api/habits/batch-update")
async def batch_update_habits(
    payload: HabitBatchUpdateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Updates multiple habits in a single batch (used for Presets)."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    success = await asyncio.to_thread(batch_update_habit_dict, payload.page_id, payload.updates)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در ثبت گروهی عادات.")
    return {"success": True}


# ==========================================
# 👑 ADMIN PANEL ENDPOINTS
# ==========================================

@app.get("/api/admin/users")
async def admin_get_users(user: Dict[str, Any] = Depends(get_current_user)):
    """Returns all registered users with their roles."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز است.")
    all_users = get_all_users()
    user_list = [
        {"user_id": uid, "name": uinfo.get("name", f"کاربر {uid}"), "role": uinfo.get("role", "member")}
        for uid, uinfo in all_users.items()
    ]
    return {"users": user_list}


@app.post("/api/admin/users/save")
async def admin_save_user(
    payload: AdminUserSaveRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Adds or updates a user role and display name."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز است.")
    success = add_or_update_user(payload.user_id, payload.name, payload.role)
    if not success:
        raise HTTPException(status_code=400, detail="نقش کاربری نامعتبر است.")
    return {"success": True}


@app.delete("/api/admin/users/{target_user_id}")
async def admin_delete_user(
    target_user_id: int,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Deletes a user access."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز است.")
    success = remove_user(target_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد.")
    return {"success": True}


@app.get("/api/admin/stats")
async def admin_get_stats(user: Dict[str, Any] = Depends(get_current_user)):
    """Provides system health and activity counters for admins."""
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="دسترسی غیرمجاز است.")
    all_users = get_all_users()
    try:
        today_str = datetime.now(timezone(timedelta(hours=3, minutes=30))).strftime("%Y-%m-%d")
        recent_life = query_life_tracker_entries(start_date_iso=today_str)
        recent_count = len(recent_life)
    except Exception:
        recent_count = 0

    return {
        "total_users": len(all_users),
        "recent_life_count": recent_count,
        "server_status": "🟢 آنلاین و فعال",
        "scheduler_status": "🟢 فعال (ساعت ۲۲:۳۰)"
    }


# ==========================================
# 📜 RECENT ACTIVITY LOGS
# ==========================================

@app.get("/api/recent-logs")
async def get_recent_logs(user: Dict[str, Any] = Depends(get_current_user)):
    try:
        life_entries = await asyncio.to_thread(query_life_tracker_entries)
        life_entries = life_entries[:5] if life_entries else []
    except Exception:
        life_entries = []

    recent_life = []
    for item in life_entries:
        t_name = item.get("type", "")
        modes_list = item.get("modes", [])
        modes_str = "، ".join(modes_list) if modes_list else ""
        recent_life.append({
            "id": item.get("id"),
            "type": t_name,
            "emoji": TYPE_EMOJIS.get(t_name, "🌱"),
            "mode": modes_str,
            "date": item.get("date_iso", "—"),
            "notes": item.get("notes", "")
        })

    return {
        "life_tracker": recent_life
    }


# ==========================================
# 📿 SPIRITUAL TRACKER (SALAH & QURAN) ENDPOINTS
# ==========================================

@app.get("/api/spiritual/day")
async def get_spiritual_day(
    date_iso: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Returns Salah page for the specified date.
    Auto-creates a blank entry when the selected day does not exist.
    """
    tz = timezone(timedelta(hours=3, minutes=30))
    if not date_iso:
        date_iso = datetime.now(tz).strftime("%Y-%m-%d")

    jalali_title = format_jalali_full_display(date_iso)

    try:
        page_data = await asyncio.to_thread(get_or_create_salah_day, date_iso, f"Salah - {date_iso}")
    except Exception as e:
        page_data = {
            "id": "",
            "progress": 0.0,
            "prayers": {},
            "completed_count": 0,
            "ada_count": 0,
            "qaza_count": 0,
            "notes": "",
            "error": str(e)
        }

    return {
        "page_id": page_data.get("id", ""),
        "date_iso": date_iso,
        "jalali_title": jalali_title,
        "progress_float": page_data.get("progress", 0.0),
        "progress_percent": int(round(page_data.get("progress", 0.0) * 100)),
        "completed_count": page_data.get("completed_count", 0),
        "ada_count": page_data.get("ada_count", 0),
        "qaza_count": page_data.get("qaza_count", 0),
        "prayers": page_data.get("prayers", {}),
        "notes": page_data.get("notes", "")
    }


@app.post("/api/spiritual/toggle-prayer")
async def api_toggle_prayer(
    payload: SpiritualPrayerToggleRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Updates or cycles the status of a prayer (ada, qaza, none)."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    success = await asyncio.to_thread(
        update_salah_prayer_status,
        payload.page_id,
        payload.prayer_key,
        payload.target_status
    )
    if not success:
        raise HTTPException(status_code=500, detail="خطا در به‌روزرسانی وضعیت نماز در نوشن.")
    return {"success": True}


@app.post("/api/spiritual/bulk-ada")
async def api_bulk_ada(
    payload: SpiritualBulkRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Marks all 5 daily prayers as Ada (on-time)."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    success = await asyncio.to_thread(bulk_mark_salah_ada, payload.page_id)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در تکمیل خودکار اداء نمازها.")
    return {"success": True}


@app.post("/api/spiritual/bulk-reset")
async def api_bulk_reset(
    payload: SpiritualBulkRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Resets all 5 prayers to uncompleted."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    success = await asyncio.to_thread(bulk_mark_salah_reset, payload.page_id)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در بازنشانی وضعیت نمازها.")
    return {"success": True}


@app.post("/api/spiritual/bulk-range-ada")
async def api_bulk_range_ada(
    payload: SpiritualBulkRangeRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Marks all 5 daily prayers as Ada across a date range."""
    s_iso = payload.start_date
    e_iso = payload.end_date

    if payload.preset:
        s_iso, e_iso, _ = get_preset_date_range(payload.preset)

    if not s_iso or not e_iso:
        today_iso = datetime.now().strftime("%Y-%m-%d")
        s_iso = s_iso or today_iso
        e_iso = e_iso or today_iso

    try:
        result = await asyncio.to_thread(bulk_mark_salah_range_ada, s_iso, e_iso)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Error in api_bulk_range_ada: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/spiritual/update-notes")
async def api_update_spiritual_notes(
    payload: SpiritualNotesRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Updates daily spiritual notes in Notion."""
    if not payload.page_id or payload.page_id == "None":
        raise HTTPException(status_code=400, detail="شناسه صفحه معتبر نیست.")

    success = await asyncio.to_thread(update_salah_notes, payload.page_id, payload.notes)
    if not success:
        raise HTTPException(status_code=500, detail="خطا در ذخیره یادداشت معنوی.")
    return {"success": True}


@app.post("/api/spiritual/quran/create")
async def api_create_quran_session(
    payload: QuranCreateRequest,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Creates a new Quran reading log in Notion."""
    tz = timezone(timedelta(hours=3, minutes=30))
    date_str = payload.date_iso or datetime.now(tz).strftime("%Y-%m-%d")
    title = payload.session_name or f"تلاوت {format_jalali_full_display(date_str)}"

    res = await asyncio.to_thread(
        add_quran_reading_entry,
        date_iso=date_str,
        pages_text=payload.pages,
        session_name=title
    )
    if not res:
        raise HTTPException(status_code=500, detail="خطا در ثبت لاگ تلاوت قرآن.")

    # Two-way sync: Also update Habit Tracker (read holy Quran habit & Quran Detail)
    try:
        habit_day = await asyncio.to_thread(get_or_create_habit_day, date_str, f"Day - {date_str}")
        if habit_day and habit_day.get("page_id"):
            h_pid = habit_day["page_id"]
            await asyncio.to_thread(update_habit_quran_detail, h_pid, payload.pages)
            await asyncio.to_thread(update_habit_entry, h_pid, "Read Holy Quran", "1-💪 کامل")
    except Exception as e:
        logger.warning(f"Could not sync Spiritual Quran session to Habit Tracker: {e}")

    return {"success": True, "page_id": res.get("id")}



@app.get("/api/spiritual/quran/history")
async def api_get_quran_history(user: Dict[str, Any] = Depends(get_current_user)):
    """Retrieves recent Quran reading logs."""
    try:
        entries = await asyncio.to_thread(query_quran_entries)
        return {"entries": entries}
    except Exception as e:
        return {"entries": [], "error": str(e)}


@app.delete("/api/spiritual/quran/delete/{page_id}")
async def api_delete_quran_entry(
    page_id: str,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Deletes/archives a Quran log."""
    success = await asyncio.to_thread(
        archive_notion_page,
        page_id,
        NOTION_DBID_QURAN,
    )
    if not success:
        raise HTTPException(status_code=500, detail="خطا در حذف لاگ قرآن.")
    return {"success": True}


@app.get("/api/spiritual/report")
async def api_get_spiritual_report(
    period: str = Query("7d"),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    user: Dict[str, Any] = Depends(get_current_user)
):
    """Returns analytics report for prayers and Quran."""
    tz = timezone(timedelta(hours=3, minutes=30))
    today_d = datetime.now(tz).date()

    if start_date and end_date:
        s_iso, e_iso = start_date, end_date
    elif period == "7d":
        s_iso, e_iso, _ = get_preset_date_range("last_7_days")
    elif period == "month":
        s_iso, e_iso, _ = get_preset_date_range("this_month")
    else:  # 30d
        s_d = today_d - timedelta(days=29)
        s_iso, e_iso = s_d.isoformat(), today_d.isoformat()

    try:
        report = await asyncio.to_thread(get_spiritual_report, s_iso, e_iso)
        return {"report": report}
    except Exception as e:
        return {"report": {}, "error": str(e)}


@app.get("/api/reports/dashboard")
async def api_get_reports_dashboard(
    period: str = Query("7d"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Builds one report payload for habits, life logs, and spiritual activity."""
    tz = timezone(timedelta(hours=3, minutes=30))
    today_d = datetime.now(tz).date()
    if period == "month":
        start_iso, end_iso, _ = get_preset_date_range("this_month")
        period_label = "ماه جاری"
    elif period == "30d":
        start_iso = (today_d - timedelta(days=29)).isoformat()
        end_iso = today_d.isoformat()
        period_label = "۳۰ روز اخیر"
    else:
        period = "7d"
        start_iso, end_iso, _ = get_preset_date_range("last_7_days")
        period_label = "۷ روز اخیر"

    warnings: List[str] = []
    life_entries: List[Dict[str, Any]] = []
    habit_history: List[Dict[str, Any]] = []
    spiritual_report: Dict[str, Any] = {}

    async def load_life() -> List[Dict[str, Any]]:
        return await asyncio.to_thread(query_life_tracker_entries, start_iso, end_iso)

    async def load_spiritual() -> Dict[str, Any]:
        return await asyncio.to_thread(get_spiritual_report, start_iso, end_iso)

    life_result, spiritual_result = await asyncio.gather(
        load_life(),
        load_spiritual(),
        return_exceptions=True,
    )
    if isinstance(life_result, Exception):
        warnings.append("دیتابیس روزمرگی تنظیم نشده یا در دسترس نیست.")
    else:
        life_entries = life_result
    if isinstance(spiritual_result, Exception):
        warnings.append("گزارش معنوی در دسترس نیست.")
    else:
        spiritual_report = spiritual_result

    if NOTION_DBID_HABITS:
        try:
            habit_history = await asyncio.to_thread(query_habit_history, 100)
        except Exception:
            warnings.append("داده‌های عادت‌ها دریافت نشد.")
    else:
        warnings.append("شناسه دیتابیس عادت‌ها در تنظیمات سرور وارد نشده است.")

    habit_matrix: Dict[str, Any] = {}
    habit_streaks: Dict[str, Any] = {}
    if habit_history:
        habit_matrix = calculate_consistency_matrix(period, habit_history)
        habit_streaks = calculate_habit_streaks(habit_history, 100)

    type_counts = Counter(str(item.get("type") or "نامشخص") for item in life_entries)
    life_breakdown = [
        {
            "name": name,
            "count": count,
            "emoji": TYPE_EMOJIS.get(name, "🏷️"),
            "pct": round((count / len(life_entries)) * 100, 1) if life_entries else 0,
        }
        for name, count in type_counts.most_common()
    ]

    habit_days = {
        str(item.get("date_iso")): item
        for item in habit_matrix.get("daily_timeline", [])
        if item.get("date_iso")
    }
    life_days = Counter(str(item.get("date_iso") or "") for item in life_entries)
    salah_days = {
        str(item.get("date_iso")): item
        for item in spiritual_report.get("daily_salah", [])
        if item.get("date_iso")
    }
    quran_days = Counter(
        str(item.get("date_iso") or "").split("T")[0]
        for item in spiritual_report.get("quran_sessions", [])
    )

    daily_timeline: List[Dict[str, Any]] = []
    cursor = datetime.strptime(start_iso, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_iso, "%Y-%m-%d").date()
    while cursor <= end_date:
        iso = cursor.isoformat()
        habit_day = habit_days.get(iso, {})
        salah_day = salah_days.get(iso, {})
        daily_timeline.append({
            "date_iso": iso,
            "date_label": format_jalali_full_display(iso),
            "habit_pct": round(float(habit_day.get("progress", 0)) * 100),
            "life_count": life_days.get(iso, 0),
            "prayer_ada": int(salah_day.get("ada_count", 0)),
            "prayer_qaza": int(salah_day.get("qaza_count", 0)),
            "quran_count": quran_days.get(iso, 0),
        })
        cursor += timedelta(days=1)

    return {
        "period": {
            "key": period,
            "label": period_label,
            "start_date": start_iso,
            "end_date": end_iso,
        },
        "summary": {
            "habit_consistency_pct": round(float(habit_matrix.get("overall_consistency_pct", 0)), 1),
            "habit_logged_days": int(habit_matrix.get("logged_days_count", 0)),
            "life_records": len(life_entries),
            "life_active_days": len({item.get("date_iso") for item in life_entries if item.get("date_iso")}),
            "prayer_ada_rate": float(spiritual_report.get("overall_ada_rate", 0)),
            "quran_sessions": int(spiritual_report.get("quran_sessions_count", 0)),
        },
        "habits": {
            "matrix": habit_matrix,
            "streaks": habit_streaks,
        },
        "life": {
            "breakdown": life_breakdown,
            "recent": life_entries[:12],
        },
        "spiritual": spiritual_report,
        "daily_timeline": daily_timeline,
        "warnings": warnings,
    }


# ==========================================
# 🌐 STATIC FILES & FRONTEND
# ==========================================


STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/manifest.webmanifest", include_in_schema=False)
async def serve_manifest():
    return FileResponse(
        os.path.join(STATIC_DIR, "manifest.webmanifest"),
        media_type="application/manifest+json",
    )


@app.get("/service-worker.js", include_in_schema=False)
async def serve_service_worker():
    return FileResponse(
        os.path.join(STATIC_DIR, "service-worker.js"),
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/")
async def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return JSONResponse({"status": "running", "message": "NotionYar Mini App API is ready"})
