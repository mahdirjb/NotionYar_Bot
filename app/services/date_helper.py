import re
from datetime import datetime, date, timedelta, timezone
import jdatetime

def normalize_digits(text: str) -> str:
    """Converts Persian/Arabic digits to English digits."""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    for i in range(10):
        text = text.replace(persian_digits[i], str(i)).replace(arabic_digits[i], str(i))
    return text

def get_jalali_date_info(offset_days: int = 0) -> tuple[str, str]:
    """
    Returns (gregorian_iso_date, jalali_display_str) with optional day offset.
    """
    tz = timezone(timedelta(hours=3, minutes=30))
    g_target = datetime.now(tz).date() - timedelta(days=offset_days)
    j_target = jdatetime.date.fromgregorian(date=g_target)
    
    g_iso = g_target.isoformat()
    j_str = j_target.strftime("%Y/%m/%d")
    return g_iso, j_str

def parse_user_date_input(input_text: str) -> tuple[str, str] | None:
    """
    Parses user date input (supports both Shamsi 1405/05/25 and Gregorian 2026-08-21).
    Returns (gregorian_iso, jalali_display) or None if invalid.
    """
    cleaned = normalize_digits(input_text.strip())
    match = re.search(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", cleaned)
    if not match:
        return None

    y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))

    # Case 1: Shamsi year (e.g. 13xx or 14xx)
    if 1300 <= y <= 1500:
        try:
            j_date = jdatetime.date(y, m, d)
            g_date = j_date.togregorian()
            return g_date.isoformat(), j_date.strftime("%Y/%m/%d")
        except Exception:
            return None

    # Case 2: Gregorian year (e.g. 20xx)
    elif 1900 <= y <= 2100:
        try:
            g_date = date(y, m, d)
            j_date = jdatetime.date.fromgregorian(date=g_date)
            return g_date.isoformat(), j_date.strftime("%Y/%m/%d")
        except Exception:
            return None

    return None