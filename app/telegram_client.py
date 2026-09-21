import asyncio

from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest

from .config import AVATARS_DIR, settings


class TelegramConfigError(RuntimeError):
    pass


def _require_api() -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise TelegramConfigError(
            "TELEGRAM_API_ID / TELEGRAM_API_HASH가 설정되지 않았습니다. .env 파일을 확인하세요."
        )


def make_client(session_path: str) -> TelegramClient:
    _require_api()
    return TelegramClient(session_path, settings.telegram_api_id, settings.telegram_api_hash)


async def fetch_profile(session_path: str, account_id: int) -> dict:
    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다 (로그인이 만료되었거나 잘못된 세션 파일입니다).")
        me = await client.get_me()

        avatar_rel = ""
        avatar_target = AVATARS_DIR / f"{account_id}.jpg"
        try:
            downloaded = await client.download_profile_photo(me, file=str(avatar_target))
            if downloaded:
                avatar_rel = f"/avatars/{account_id}.jpg"
        except Exception:
            avatar_rel = ""

        about = ""
        try:
            from telethon.tl.functions.users import GetFullUserRequest

            full_user = await client(GetFullUserRequest(me))
            about = full_user.full_user.about or ""
        except Exception:
            about = ""

        return {
            "phone": me.phone or "",
            "username": me.username or "",
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "about": about,
            "telegram_user_id": str(me.id),
            "avatar_path": avatar_rel,
        }
    finally:
        await client.disconnect()


async def update_profile(session_path: str, first_name: str, last_name: str, about: str) -> None:
    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다.")
        await client(UpdateProfileRequest(first_name=first_name, last_name=last_name, about=about))
    finally:
        await client.disconnect()


async def update_photo(session_path: str, photo_path: str, account_id: int) -> str:
    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다.")
        file = await client.upload_file(photo_path)
        await client(UploadProfilePhotoRequest(file=file))
        me = await client.get_me()
        avatar_target = AVATARS_DIR / f"{account_id}.jpg"
        await client.download_profile_photo(me, file=str(avatar_target))
        return f"/avatars/{account_id}.jpg"
    finally:
        await client.disconnect()


SPAM_BOT_USERNAME = "SpamBot"

CLEAN_MARKERS = ["good news", "no limits", "free as a bird"]
LIMITED_MARKERS = ["some limitations", "read-only mode", "violat", "temporary"]
BANNED_MARKERS = ["permanently restricted", "frozen", "deleted for violation", "banned"]


def classify_spambot_reply(text: str) -> str:
    lowered = (text or "").lower()
    if any(marker in lowered for marker in BANNED_MARKERS):
        return "banned"
    if any(marker in lowered for marker in LIMITED_MARKERS):
        return "limited"
    if any(marker in lowered for marker in CLEAN_MARKERS):
        return "clean"
    return "unknown"


async def run_spam_check(session_path: str) -> dict:
    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다.")
        await client.send_message(SPAM_BOT_USERNAME, "/start")
        await asyncio.sleep(4)
        messages = await client.get_messages(SPAM_BOT_USERNAME, limit=1)
        text = messages[0].message if messages else ""
        result = classify_spambot_reply(text)
        return {"result": result, "raw_response": text}
    finally:
        await client.disconnect()
