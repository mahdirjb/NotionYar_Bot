# import_history.py

import time
import jdatetime
from dotenv import load_dotenv

load_dotenv()

import app.config as config
import app.services.notion_service as notion_service

# شناسه دیتابیس مستقیماً در متغیرهای ماژول ست می‌شود:
DATABASE_ID = "1c6a75a25614804a9df0e122bb736f42"
config.NOTION_DBID_LIFE_TRACKER = DATABASE_ID
notion_service.NOTION_DBID_LIFE_TRACKER = DATABASE_ID

from app.services.notion_service import add_life_tracker_entry

# Helper for Jalali to Gregorian ISO conversion
def to_iso(y: int, m: int, d: int) -> str:
    return jdatetime.date(y, m, d).togregorian().isoformat()

# Full structured history dataset (1404 for Esfand, 1405 for Farvardin-Mordad)
RAW_DATA = [
    # --- دوری ---
    {"type": "دوری", "name": "دوری", "date": (1404, 12, 28), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 1), "modes": [], "notes": "ساعت ۷:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 3), "modes": [], "notes": "ساعت ۸:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 7), "modes": [], "notes": "ساعت ۶:۰۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 13), "modes": [], "notes": "ساعت ۷:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 17), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 19), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 22), "modes": [], "notes": "ساعت ۴:۰۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 25), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 27), "modes": [], "notes": "ساعت ۲:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 29), "modes": [], "notes": "ساعت ۵:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 1, 30), "modes": [], "notes": "ساعت ۱۰:۰۰ شب"},
    {"type": "دوری", "name": "دوری", "date": (1405, 2, 3), "modes": [], "notes": "ساعت ۲:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 2, 5), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 2, 10), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 2, 13), "modes": [], "notes": "ساعت ۵:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 2, 20), "modes": [], "notes": "ساعت ۲:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 2, 23), "modes": [], "notes": "ساعت ۷:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 2, 28), "modes": [], "notes": "ساعت ۵:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 2, 30), "modes": [], "notes": "ساعت ۶:۰۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 2), "modes": [], "notes": "ساعت ۵:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 4), "modes": [], "notes": "ساعت ۶:۳۰ شب"},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 7), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 10), "modes": [], "notes": "ساعت ۱۱:۰۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 15), "modes": [], "notes": "ساعت ۵:۰۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 16), "modes": ["شب"], "notes": "ساعت ۱۷:۳۰"},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 18), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 21), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 3, 25), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 5), "modes": [], "notes": "ساعت ۵:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 6), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 9), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 13), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 15), "modes": [], "notes": "ساعت ۵:۰۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 17), "modes": [], "notes": "ساعت ۱۱:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 20), "modes": [], "notes": "ساعت ۲:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 23), "modes": [], "notes": "ساعت ۵:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 25), "modes": [], "notes": "ساعت ۷:۰۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 27), "modes": [], "notes": "ساعت ۱۱:۰۰ شب"},
    {"type": "دوری", "name": "دوری", "date": (1405, 4, 30), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 2), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 5), "modes": [], "notes": ""},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 18), "modes": [], "notes": "ساعت ۵:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 22), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 23), "modes": [], "notes": "ساعت ۴:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 25), "modes": [], "notes": "ساعت ۳:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 27), "modes": [], "notes": "ساعت ۳:۰۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 29), "modes": [], "notes": "ساعت ۷:۳۰ صبح"},
    {"type": "دوری", "name": "دوری", "date": (1405, 5, 31), "modes": [], "notes": "ساعت ۸:۰۰ صبح"},

    # --- ناخن دست ---
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1404, 12, 28), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 1, 7), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 1, 19), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 1, 30), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 2, 7), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 2, 16), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 2, 28), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 3, 6), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 3, 18), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 3, 27), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 4, 16), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 4, 27), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 5, 7), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 5, 17), "modes": [], "notes": ""},
    {"type": "ناخن دست", "name": "ناخن دست", "date": (1405, 5, 29), "modes": [], "notes": ""},

    # --- ناخن پا ---
    {"type": "ناخن پا", "name": "ناخن پا", "date": (1405, 1, 10), "modes": [], "notes": ""},
    {"type": "ناخن پا", "name": "ناخن پا", "date": (1405, 1, 30), "modes": [], "notes": ""},
    {"type": "ناخن پا", "name": "ناخن پا", "date": (1405, 2, 28), "modes": [], "notes": ""},
    {"type": "ناخن پا", "name": "ناخن پا", "date": (1405, 3, 27), "modes": [], "notes": ""},
    {"type": "ناخن پا", "name": "ناخن پا", "date": (1405, 4, 27), "modes": [], "notes": ""},
    {"type": "ناخن پا", "name": "ناخن پا", "date": (1405, 5, 17), "modes": [], "notes": ""},

    # --- آینه ---
    {"type": "آینه", "name": "آینه", "date": (1404, 12, 28), "modes": [], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 1, 3), "modes": [], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 1, 9), "modes": [], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 1, 22), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 1, 31), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 2, 8), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 2, 17), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 2, 28), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 3, 9), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 3, 17), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 3, 27), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 4, 6), "modes": ["نوره"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 4, 20), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 4, 29), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 5, 8), "modes": ["نوره"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 5, 18), "modes": ["ژیلت"], "notes": ""},
    {"type": "آینه", "name": "آینه", "date": (1405, 5, 29), "modes": ["ژیلت"], "notes": ""},

    # --- ریش و سبیل (کمرس / مرس) ---
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1404, 12, 28), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 1, 7), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 1, 22), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 2, 8), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 2, 22), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 3, 4), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 3, 9), "modes": ["مرتب‌کردن", "ریش", "سبیل"], "notes": "مرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 3, 13), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 3, 21), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 3, 27), "modes": ["مرتب‌کردن", "ریش", "سبیل"], "notes": "مرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 4, 2), "modes": ["مرتب‌کردن", "ریش", "سبیل"], "notes": "مرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 4, 6), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 4, 22), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 4, 29), "modes": ["مرتب‌کردن", "ریش", "سبیل"], "notes": "مرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 5, 2), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 5, 7), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 5, 18), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},
    {"type": "ریش و سبیل", "name": "ریش و سبیل", "date": (1405, 5, 29), "modes": ["کوتاه‌کردن", "مرتب‌کردن", "ریش", "سبیل"], "notes": "کمرس"},

    # --- موپالمو ---
    {"type": "موپالمو", "name": "موپالمو", "date": (1405, 1, 23), "modes": ["نوره"], "notes": ""},

    # --- خورشید ---
    {"type": "خورشید", "name": "خورشید", "date": (1405, 1, 23), "modes": ["نوره"], "notes": ""},
    {"type": "خورشید", "name": "خورشید", "date": (1405, 4, 6), "modes": ["نوره"], "notes": ""},
    {"type": "خورشید", "name": "خورشید", "date": (1405, 5, 8), "modes": ["نوره"], "notes": ""},

    # --- آرایشگاه (مو) ---
    {"type": "آرایشگاه", "name": "آرایشگاه", "date": (1404, 12, 27), "modes": [], "notes": ""},
    {"type": "آرایشگاه", "name": "آرایشگاه", "date": (1405, 2, 11), "modes": [], "notes": ""},
    {"type": "آرایشگاه", "name": "آرایشگاه", "date": (1405, 3, 13), "modes": [], "notes": ""},
    {"type": "آرایشگاه", "name": "آرایشگاه", "date": (1405, 4, 22), "modes": [], "notes": ""},

    # --- رویدادهای خاص ---
    {"type": "اتفاقات", "name": "کارت پایان خدمت رسید دستم", "date": (1405, 1, 30), "modes": [], "notes": "کارت پایان خدمت رسید دستم"},
    {"type": "خرید", "name": "خرید باتری جدید برای موبایل ۲.۴۰۰.۰۰۰", "date": (1405, 3, 13), "modes": [], "notes": "۲,۴۰۰,۰۰۰ خرید باتری جدید برای موبایل تومان"},
    {"type": "مریضی", "name": "رفتم دکتر و سرم زدم", "date": (1405, 3, 28), "modes": [], "notes": "رفتم دکتر و سرم زدم"},
    {"type": "خرید", "name": "خریدای دیجی کالا رسید دستم", "date": (1405, 4, 20), "modes": [], "notes": "خریدای دیجی کالا رسید دستم"}
]

def main():
    total = len(RAW_DATA)
    print(f"🚀 شروع فرآیند انتقال {total} رکورد به دیتابیس نوشن...")

    success_count = 0
    fail_count = 0

    for idx, item in enumerate(RAW_DATA, start=1):
        y, m, d = item["date"]
        iso_date = to_iso(y, m, d)
        j_str = f"{y}/{m:02d}/{d:02d}"

        try:
            add_life_tracker_entry(
                name=item["name"],
                type_val=item["type"],
                date_iso=iso_date,
                mode_list=item["modes"],
                notes=item["notes"]
            )
            print(f"[{idx}/{total}] ✅ {j_str} | {item['type']} -> {item['name']}")
            success_count += 1
        except Exception as e:
            print(f"[{idx}/{total}] ❌ خطا در ثبت {j_str} ({item['name']}): {e}")
            fail_count += 1

        # Small delay to respect Notion rate limits comfortably
        time.sleep(0.35)

    print("\n" + "=" * 40)
    print(f"🎉 عملیات پایان یافت!")
    print(f"✅ موفق: {success_count} رکورد")
    if fail_count > 0:
        print(f"❌ ناموفق: {fail_count} رکورد")
    print("=" * 40)

if __name__ == "__main__":
    main()