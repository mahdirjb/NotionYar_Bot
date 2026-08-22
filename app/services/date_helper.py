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

def get_preset_date_range(preset: str) -> tuple[str, str, str]:
    """
    Returns (start_iso, end_iso, label) for a given preset:
    - 'today'
    - 'yesterday'
    - 'last_7_days'
    - 'this_month' (start of current Jalali month to today)
    """
    tz = timezone(timedelta(hours=3, minutes=30))
    g_today = datetime.now(tz).date()
    j_today = jdatetime.date.fromgregorian(date=g_today)

    if preset == "today":
        g_iso = g_today.isoformat()
        return g_iso, g_iso, f"امروز ({j_today.strftime('%Y/%m/%d')})"

    elif preset == "yesterday":
        g_yest = g_today - timedelta(days=1)
        j_yest = jdatetime.date.fromgregorian(date=g_yest)
        g_iso = g_yest.isoformat()
        return g_iso, g_iso, f"دیروز ({j_yest.strftime('%Y/%m/%d')})"

    elif preset == "last_7_days":
        g_start = g_today - timedelta(days=6)
        j_start = jdatetime.date.fromgregorian(date=g_start)
        return (
            g_start.isoformat(),
            g_today.isoformat(),
            f"۷ روز اخیر ({j_start.strftime('%m/%d')} تا {j_today.strftime('%m/%d')})"
        )

    elif preset == "this_month":
        j_month_start = jdatetime.date(j_today.year, j_today.month, 1)
        g_month_start = j_month_start.togregorian()
        return (
            g_month_start.isoformat(),
            g_today.isoformat(),
            f"ماه جاری ({j_today.strftime('%B %Y')})"
        )

    # Fallback to today
    g_iso = g_today.isoformat()
    return g_iso, g_iso, f"امروز ({j_today.strftime('%Y/%m/%d')})"


def format_minutes_to_hours_str(minutes: int) -> str:
    """Formats minutes into human-readable Persian duration (e.g., '۲ ساعت و ۳۰ دقیقه' or '۴۵ دقیقه')."""
    if minutes <= 0:
        return "۰ دقیقه"
    h = minutes // 60
    m = minutes % 60
    parts = []
    if h > 0:
        parts.append(f"{h} ساعت")
    if m > 0:
        parts.append(f"{m} دقیقه")
    return " و ".join(parts)


def parse_notion_time_display(start_iso: str | None, end_iso: str | None, m_duration: int | None) -> str:
    """
    Constructs a readable time string from Notion start/end ISO strings and MDuration.
    Examples:
    - '14:00 تا 16:30 (۲ ساعت و ۳۰ دقیقه)'
    - '۴۵ دقیقه'
    """
    # Case 1: Start and End have specific times (e.g. contains 'T')
    if start_iso and "T" in start_iso:
        s_time = start_iso.split("T")[1][:5]
        if end_iso and "T" in end_iso:
            e_time = end_iso.split("T")[1][:5]
            # If manual duration exists, show it
            if m_duration is not None and m_duration > 0:
                return f"{s_time} تا {e_time} ({format_minutes_to_hours_str(m_duration)})"
            return f"{s_time} تا {e_time}"
        return f"شروع از {s_time}"

    # Case 2: Only MDuration exists
    if m_duration is not None and m_duration > 0:
        return f"{format_minutes_to_hours_str(m_duration)}"

    return "—"

def parse_custom_date_range(input_text: str) -> tuple[str, str, str] | None:
    """
    Parses user custom date range input supporting formats:
    - '1405/05/01 تا 1405/05/15'
    - '1405/05/01 - 1405/05/15'
    - '1405/05/01' (single day)
    Returns (start_iso, end_iso, label) or None if invalid.
    """
    cleaned = normalize_digits(input_text.strip())
    
    # Split by 'تا', 'to', or '-' (excluding date hyphens)
    parts = re.split(r"\s+(?:تا|to)\s+|\s+-\s+", cleaned, flags=re.IGNORECASE)
    
    if len(parts) == 1:
        # Single date entered
        parsed = parse_user_date_input(parts[0])
        if not parsed:
            return None
        g_iso, j_str = parsed
        return g_iso, g_iso, f"{j_str}"
        
    elif len(parts) == 2:
        # Range entered
        parsed_start = parse_user_date_input(parts[0])
        parsed_end = parse_user_date_input(parts[1])
        if not parsed_start or not parsed_end:
            return None
            
        g_start_iso, j_start_str = parsed_start
        g_end_iso, j_end_str = parsed_end
        
        # Validate start is before or equal to end
        if g_start_iso > g_end_iso:
            return None
            
        return g_start_iso, g_end_iso, f"{j_start_str} تا {j_end_str}"
        
    return None