from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
TRASH_DIR = DATA_DIR / "sessions_trash"
AVATARS_DIR = DATA_DIR / "avatars"


class Settings(BaseSettings):
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"
    secret_key: str = "dev-secret"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()

for _dir in (DATA_DIR, SESSIONS_DIR, TRASH_DIR, AVATARS_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
