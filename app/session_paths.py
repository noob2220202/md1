from .config import SESSIONS_DIR
from .models import Account


def session_path(account: Account) -> str:
    return str((SESSIONS_DIR / account.session_filename).with_suffix(""))
