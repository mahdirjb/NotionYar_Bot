import json
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import REMINDER_SETTINGS_FILE


REMINDER_MODELS = {"full", "compact", "questions"}
REMINDER_QUESTIONS = {"habits", "gratitude", "prayers", "quran", "day_review"}
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")

DEFAULT_REMINDER: Dict[str, Any] = {
    "id": "nightly-checkin",
    "name": "چک‌این شبانه",
    "time": "22:30",
    "enabled": True,
    "model": "full",
    "questions": ["habits", "gratitude"],
}


def _settings_path() -> Path:
    path = Path(REMINDER_SETTINGS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _normalize_reminder(payload: Dict[str, Any], reminder_id: Optional[str] = None) -> Dict[str, Any]:
    name = str(payload.get("name") or "").strip()
    time_value = str(payload.get("time") or "").strip()
    model = str(payload.get("model") or "full").strip()
    questions = [str(item) for item in payload.get("questions", []) if str(item) in REMINDER_QUESTIONS]

    if not name or len(name) > 80:
        raise ValueError("نام یادآور باید بین ۱ تا ۸۰ کاراکتر باشد.")
    if not TIME_PATTERN.match(time_value):
        raise ValueError("زمان یادآور باید با قالب ساعت و دقیقه وارد شود.")
    if model not in REMINDER_MODELS:
        raise ValueError("سبک پیام یادآور معتبر نیست.")
    if not questions:
        raise ValueError("حداقل یک مورد برای پرسش انتخاب کنید.")

    return {
        "id": reminder_id or str(payload.get("id") or uuid.uuid4().hex[:12]),
        "name": name,
        "time": time_value,
        "enabled": bool(payload.get("enabled", True)),
        "model": model,
        "questions": list(dict.fromkeys(questions)),
    }


def list_reminders() -> List[Dict[str, Any]]:
    path = _settings_path()
    if not path.exists():
        reminders = [dict(DEFAULT_REMINDER)]
        _write_reminders(reminders)
        return reminders
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw_items = data.get("reminders", []) if isinstance(data, dict) else []
        reminders = [_normalize_reminder(item, str(item.get("id") or "")) for item in raw_items]
        return sorted(reminders, key=lambda item: (item["time"], item["name"]))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return [dict(DEFAULT_REMINDER)]


def get_reminder(reminder_id: str) -> Optional[Dict[str, Any]]:
    return next((item for item in list_reminders() if item["id"] == reminder_id), None)


def save_reminder(payload: Dict[str, Any], reminder_id: Optional[str] = None) -> Dict[str, Any]:
    reminders = list_reminders()
    normalized = _normalize_reminder(payload, reminder_id)
    replaced = False
    for index, item in enumerate(reminders):
        if item["id"] == normalized["id"]:
            reminders[index] = normalized
            replaced = True
            break
    if not replaced:
        reminders.append(normalized)
    _write_reminders(reminders)
    return normalized


def delete_reminder(reminder_id: str) -> bool:
    reminders = list_reminders()
    updated = [item for item in reminders if item["id"] != reminder_id]
    if len(updated) == len(reminders):
        return False
    _write_reminders(updated)
    return True


def _write_reminders(reminders: List[Dict[str, Any]]) -> None:
    path = _settings_path()
    content = json.dumps({"reminders": reminders}, ensure_ascii=False, indent=2)
    fd, temp_name = tempfile.mkstemp(prefix="reminders-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
