import re

from fastapi.templating import Jinja2Templates

from .config import BASE_DIR

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def format_phone(value) -> str:
    raw = str(value or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw
    rest = None
    if digits.startswith("82") and len(digits) >= 10:
        rest = digits[2:].lstrip("0")
    elif digits.startswith("0") and len(digits) in (10, 11) and not raw.startswith("+"):
        rest = digits[1:]
    if rest is not None:
        if rest.startswith("10") and len(rest) == 10:
            return f"+82 {rest[:2]}-{rest[2:6]}-{rest[6:]}"
        if rest.startswith("2") and len(rest) in (8, 9):
            return f"+82 2-{rest[1:-4]}-{rest[-4:]}"
        if len(rest) in (9, 10):
            return f"+82 {rest[:2]}-{rest[2:-4]}-{rest[-4:]}"
        return f"+82 {rest}"
    if digits.startswith("1") and len(digits) == 11:
        return f"+1 {digits[1:4]}-{digits[4:7]}-{digits[7:]}"
    return f"+{digits}" if raw.startswith("+") or len(digits) > 10 else raw


def avatar_tone(account_id) -> str:
    try:
        return f"av{int(account_id) % 8}"
    except Exception:
        return "av0"


def _given_name(account) -> str:
    try:
        name = f"{account.first_name or ''} {account.last_name or ''}".strip()
        return name or (account.username or "")
    except Exception:
        return ""


def account_name(account) -> str:
    name = _given_name(account)
    if name:
        return name
    try:
        return format_phone(account.phone) if account.phone else account.display_name
    except Exception:
        return ""


def account_initial(account) -> str:
    return _given_name(account)[:1].upper() or "#"


templates.env.filters["phone"] = format_phone
templates.env.filters["avatar_tone"] = avatar_tone
templates.env.filters["acct_name"] = account_name
templates.env.filters["acct_initial"] = account_initial
