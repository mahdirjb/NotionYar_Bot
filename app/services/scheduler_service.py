# app/services/scheduler_service.py

import logging
from datetime import datetime, timedelta, timezone
from typing import List
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import ADMIN_USERS
from app.services.date_helper import format_jalali_full_display
from app.services.notion_service import (
    HABIT_ITEMS,
    get_or_create_habit_day,
)
from app.services.habit_analytics_service import is_day_frozen
from app.keyboards.inline import build_nightly_checkin_keyboard

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def _get_tehran_date_info() -> tuple[str, str]:
    """Returns (gregorian_iso, full_jalali_display) for today in Tehran timezone."""
    tz = timezone(timedelta(hours=3, minutes=30))
    today = datetime.now(tz).date()
    g_iso = today.isoformat()
    j_full = format_jalali_full_display(g_iso)
    return g_iso, j_full


def _build_progress_bar(percent_float: float) -> str:
    """Generates visual progress bar."""
    pct = max(0.0, min(1.0, percent_float))
    pct_int = int(round(pct * 100))
    filled_count = int(round(pct * 10))

    if filled_count == 10:
        bar = "🟩" * 10
    elif filled_count == 0:
        bar = "⬜" * 10
    else:
        bar = ("🟩" * max(0, filled_count - 1)) + "🟨" + ("⬜" * (10 - filled_count))

    return f"[{bar}] <b>{pct_int}%</b>"


def _get_target_admin_ids() -> List[int]:
    """Parses ADMIN_USERS into a clean list of integer user IDs."""
    admin_ids: List[int] = []
    if isinstance(ADMIN_USERS, list):
        raw_list = ADMIN_USERS
    elif isinstance(ADMIN_USERS, str):
        raw_list = ADMIN_USERS.replace(";", ",").split(",")
    else:
        raw_list = [ADMIN_USERS]

    for item in raw_list:
        clean = str(item).strip()
        if clean.isdigit():
            admin_ids.append(int(clean))
    return admin_ids


async def send_nightly_habit_checkin(bot: Bot, target_user_id: int | None = None) -> bool:
    """
    Executes nightly check-in scan and dispatches reminders.
    If target_user_id is provided, sends directly to that user (for test command).
    """
    try:
        g_iso, full_jalali = _get_tehran_date_info()
        page_data = get_or_create_habit_day(g_iso, day_title=full_jalali)

        habits = page_data.get("habits", {})
        prog_float = float(page_data.get("progress", 0.0))
        prog_bar = _build_progress_bar(prog_float)
        prog_pct = int(round(prog_float * 100))
        frozen = is_day_frozen(page_data)
        gratitude_done = bool(str(page_data.get("gratitude_log", "")).strip())

        # Find uncompleted habits
        uncompleted: List[str] = []
        for h_key, h_info in HABIT_ITEMS.items():
            val = habits.get(h_key)
            if val not in ["1-💪 کامل", "2-🏃‍♂️ نیمه‌کامل", "3-🐢 سبک"]:
                uncompleted.append(f"{h_info['emoji']} {h_info['fa']}")

        if frozen:
            text = (
                "🌙 <b>چک‌این شبانه عادات روزانه</b>\n"
                f"📅 <code>{full_jalali}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🧊 <b>امروز برای شما فریز (استراحت) ثبت شده است.</b>\n"
                "🛡️ <i>زنجیره و تداوم شما در امان است. شبتون پر از آرامش و ریکاوری! ✨</i>"
            )
            kb = build_nightly_checkin_keyboard(is_completed=True)
        elif prog_pct >= 100 or len(uncompleted) == 0:
            text = (
                "👑 <b>ماشاءالله! کارنامه بی‌نقص امروز</b>\n"
                f"📅 <code>{full_jalali}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>پیشرفت:</b> {prog_bar}\n\n"
                "🎉 <i>تمام ۱۳ عادت امروزت با موفقیت ثبت شده! دمت گرم بابت این پایبندی، شبت آروم و پر ستاره ✨</i>"
            )
            kb = build_nightly_checkin_keyboard(is_completed=True)
        else:
            pending_list_str = "\n".join([f"  ▫️ {item}" for item in uncompleted])
            grat_status = "✅ ثبت شده" if gratitude_done else "▫️ ثبت‌نشده"

            text = (
                "⏰ <b>وقت چک‌این و بستن پرونده امروز!</b>\n"
                f"📅 <code>{full_jalali}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 <b>پیشرفت تا این لحظه:</b> {prog_bar}\n"
                f"🌸 <b>شکرگزاری:</b> {grat_status}\n\n"
                f"📋 <b>عادات باقی‌مانده ({len(uncompleted)} مورد):</b>\n"
                f"{pending_list_str}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 <i>حتی ثبت سریع با سطح ۳ (سبک) یا فریز کردن، زنجیره شما را زنده نگه می‌دارد!</i>"
            )
            kb = build_nightly_checkin_keyboard(is_completed=False)

        # Dispatch
        recipients = [target_user_id] if target_user_id else _get_target_admin_ids()
        for uid in recipients:
            try:
                await bot.send_message(chat_id=uid, text=text, reply_markup=kb, parse_mode="HTML")
                logger.info(f"Nightly check-in sent to user {uid}")
            except Exception as e:
                logger.error(f"Failed to send nightly check-in to {uid}: {e}")

        return True
    except Exception as e:
        logger.error(f"Error executing nightly check-in: {e}", exc_info=True)
        return False


def start_scheduler(bot: Bot) -> None:
    """Configures and starts the background job scheduler."""
    tehran_tz = timezone(timedelta(hours=3, minutes=30))
    trigger = CronTrigger(hour=22, minute=30, timezone=tehran_tz)

    scheduler.add_job(
        send_nightly_habit_checkin,
        trigger=trigger,
        args=[bot],
        id="nightly_habit_checkin",
        replace_existing=True,
    )
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started successfully (Nightly Check-in set for 22:30 Tehran Time).")


def shutdown_scheduler() -> None:
    """Safely shuts down the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler shut down safely.")