# app/services/scheduler_service.py

import logging
import asyncio
import html
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import ADMIN_USERS
from app.services.date_helper import format_jalali_full_display
from app.services.notion_service import (
    HABIT_ITEMS,
    get_or_create_habit_day,
    get_or_create_salah_day,
    query_quran_entries,
)

from app.services.habit_analytics_service import is_day_frozen
from app.keyboards.inline import build_nightly_checkin_keyboard
from app.services.reminder_settings_service import DEFAULT_REMINDER, get_reminder, list_reminders

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()
_scheduler_bot: Optional[Bot] = None


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


async def send_nightly_habit_checkin(
    bot: Bot,
    target_user_id: int | None = None,
    reminder_id: str | None = None,
) -> bool:
    """
    Executes nightly check-in scan and dispatches reminders.
    If target_user_id is provided, sends directly to that user (for test command).
    """
    try:
        reminder = get_reminder(reminder_id) if reminder_id else dict(DEFAULT_REMINDER)
        if reminder_id and not reminder:
            logger.warning("Reminder %s no longer exists; skipping.", reminder_id)
            return False
        reminder = reminder or dict(DEFAULT_REMINDER)
        questions = set(reminder.get("questions") or ["habits", "gratitude"])
        message_model = str(reminder.get("model") or "full")
        g_iso, full_jalali = _get_tehran_date_info()
        page_data = await asyncio.to_thread(get_or_create_habit_day, g_iso, full_jalali)

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

        prayer_data = None
        if "prayers" in questions:
            prayer_data = await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")
        prayer_pending = [
            f"{item.get('emoji', '🕌')} {item.get('name', key)}"
            for key, item in (prayer_data or {}).get("prayers", {}).items()
            if item.get("status") == "none"
        ]
        quran_done = False
        if "quran" in questions:
            quran_done = bool(await asyncio.to_thread(query_quran_entries, g_iso, g_iso, 1))

        title = html.escape(str(reminder.get("name") or "یادآوری روزانه"))
        lines = [f"⏰ <b>{title}</b>", f"📅 <code>{full_jalali}</code>", "━━━━━━━━━━━━━━━━━━━━━━"]

        if message_model == "questions":
            if "habits" in questions:
                lines.append(f"❓ عادت‌های امروز را کامل ثبت کردی؟ ({prog_pct}٪ ثبت شده)")
            if "gratitude" in questions:
                lines.append("❓ شکرگزاری امروز را نوشتی؟" if not gratitude_done else "✅ شکرگزاری امروز ثبت شده است.")
            if "prayers" in questions:
                lines.append("❓ وضعیت نمازهای امروز را کامل کردی؟" if prayer_pending else "✅ وضعیت همه نمازها مشخص است.")
            if "quran" in questions:
                lines.append("❓ تلاوت قرآن امروز را ثبت کردی؟" if not quran_done else "✅ تلاوت قرآن امروز ثبت شده است.")
            if "day_review" in questions:
                lines.append("❓ مهم‌ترین اتفاق یا نکته امروز چه بود؟")
        elif message_model == "compact":
            if "habits" in questions:
                lines.append(f"🎯 عادت‌ها: {prog_pct}٪ | {len(uncompleted)} مورد باقی‌مانده")
            if "gratitude" in questions:
                lines.append(f"🌸 شکرگزاری: {'ثبت شده' if gratitude_done else 'ثبت نشده'}")
            if "prayers" in questions:
                lines.append(f"🕌 نمازها: {len(prayer_pending)} مورد بدون وضعیت")
            if "quran" in questions:
                lines.append(f"📖 تلاوت: {'ثبت شده' if quran_done else 'ثبت نشده'}")
            if "day_review" in questions:
                lines.append("📝 مرور روز را فراموش نکن.")
        else:
            if "habits" in questions:
                if frozen:
                    lines.append("🧊 امروز فریز ثبت شده و زنجیره عادت‌ها محفوظ است.")
                else:
                    lines.append(f"📊 <b>پیشرفت عادت‌ها:</b> {prog_bar}")
                    if uncompleted:
                        lines.append(f"📋 <b>عادت‌های باقی‌مانده ({len(uncompleted)}):</b>")
                        lines.extend(f"  ▫️ {item}" for item in uncompleted)
                    else:
                        lines.append("✅ همه عادت‌های امروز تکمیل شده‌اند.")
            if "gratitude" in questions:
                lines.append(f"🌸 <b>شکرگزاری:</b> {'✅ ثبت شده' if gratitude_done else '▫️ ثبت‌نشده'}")
            if "prayers" in questions:
                if prayer_pending:
                    lines.append("🕌 <b>نمازهای بدون وضعیت:</b> " + "، ".join(prayer_pending))
                else:
                    lines.append("🕌 وضعیت همه نمازهای امروز مشخص است.")
            if "quran" in questions:
                lines.append(f"📖 <b>تلاوت قرآن:</b> {'✅ ثبت شده' if quran_done else '▫️ ثبت‌نشده'}")
            if "day_review" in questions:
                lines.append("📝 چند دقیقه برای مرور اتفاق‌های مهم امروز وقت بگذار.")

        text = "\n".join(lines)
        habits_complete = frozen or prog_pct >= 100 or len(uncompleted) == 0
        kb = build_nightly_checkin_keyboard(is_completed=habits_complete)

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


async def auto_initialize_daily_spiritual() -> None:
    """Creates blank daily Salah and habit rows shortly after midnight."""
    try:
        g_iso, full_jalali = _get_tehran_date_info()
        await asyncio.to_thread(get_or_create_salah_day, g_iso, f"Salah - {g_iso}")
        await asyncio.to_thread(get_or_create_habit_day, g_iso, full_jalali)
        logger.info(f"Daily spiritual & habit records auto-initialized for {g_iso}")
    except Exception as e:
        logger.error(f"Error auto-initializing daily spiritual records: {e}", exc_info=True)


def start_scheduler(bot: Bot) -> None:
    """Configures and starts the background job scheduler."""
    global _scheduler_bot
    _scheduler_bot = bot
    tehran_tz = timezone(timedelta(hours=3, minutes=30))
    trigger_daily_init = CronTrigger(hour=0, minute=5, timezone=tehran_tz)

    scheduler.add_job(
        auto_initialize_daily_spiritual,
        trigger=trigger_daily_init,
        id="daily_spiritual_init",
        replace_existing=True,
    )
    refresh_reminder_jobs(bot)
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler started with configurable reminders and Daily Init at 00:05.")


def refresh_reminder_jobs(bot: Optional[Bot] = None) -> int:
    """Rebuilds configurable reminder jobs after an in-app settings change."""
    global _scheduler_bot
    if bot is not None:
        _scheduler_bot = bot
    if _scheduler_bot is None:
        return 0

    for job in scheduler.get_jobs():
        if job.id.startswith("configured_reminder_") or job.id == "nightly_habit_checkin":
            scheduler.remove_job(job.id)

    tehran_tz = timezone(timedelta(hours=3, minutes=30))
    scheduled = 0
    for reminder in list_reminders():
        if not reminder.get("enabled"):
            continue
        hour, minute = (int(part) for part in str(reminder["time"]).split(":"))
        scheduler.add_job(
            send_nightly_habit_checkin,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tehran_tz),
            args=[_scheduler_bot, None, reminder["id"]],
            id=f"configured_reminder_{reminder['id']}",
            replace_existing=True,
        )
        scheduled += 1
    logger.info("Configured %s reminder job(s).", scheduled)
    return scheduled



def shutdown_scheduler() -> None:
    """Safely shuts down the scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler shut down safely.")
