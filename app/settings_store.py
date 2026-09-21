from .database import SessionLocal
from .models import AppSetting

DEFAULTS = {
    "auto_wipe_on_add": "true",
}


def get_setting(key: str) -> str:
    db = SessionLocal()
    try:
        row = db.get(AppSetting, key)
        return row.value if row else DEFAULTS.get(key, "")
    finally:
        db.close()


def set_setting(key: str, value: str) -> None:
    db = SessionLocal()
    try:
        row = db.get(AppSetting, key)
        if row:
            row.value = value
        else:
            db.add(AppSetting(key=key, value=value))
        db.commit()
    finally:
        db.close()


def get_bool_setting(key: str) -> bool:
    return get_setting(key).lower() in ("1", "true", "yes", "on")
