import asyncio
import random
import re

from telethon import TelegramClient
from telethon.errors import (
    ChannelsTooMuchError,
    FloodWaitError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    UserAlreadyParticipantError,
    UserBannedInChannelError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.contacts import DeleteContactsRequest, GetContactsRequest, ImportContactsRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest
from telethon.tl.types import Channel, Chat, InputPhoneContact, User

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


def _parse_invite_link(link: str) -> tuple[str, str]:
    value = link.strip()
    value = re.sub(r"^https?://", "", value)
    value = re.sub(r"^(t\.me|telegram\.me|telegram\.dog)/", "", value)
    value = value.lstrip("@")

    if value.startswith("joinchat/"):
        return "private", value.split("joinchat/", 1)[1].split("?")[0]
    if value.startswith("+"):
        return "private", value[1:].split("?")[0]

    username = value.split("/")[0].split("?")[0]
    return "public", username


async def join_group(session_path: str, link: str) -> dict:
    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다.")

        kind, value = _parse_invite_link(link)
        if not value:
            return {"status": "invalid_link", "title": "", "detail": "링크를 확인해주세요"}

        try:
            if kind == "private":
                updates = await client(ImportChatInviteRequest(value))
                chat = updates.chats[0] if updates.chats else None
            else:
                entity = await client.get_entity(value)
                await client(JoinChannelRequest(entity))
                chat = entity
            title = getattr(chat, "title", value) or value
            chat_id = getattr(chat, "id", None)
            return {"status": "joined", "title": title, "detail": "", "chat_id": chat_id}
        except UserAlreadyParticipantError:
            chat_id = None
            try:
                existing = await client.get_entity(value)
                chat_id = getattr(existing, "id", None)
            except Exception:
                pass
            return {"status": "already_member", "title": "", "detail": "", "chat_id": chat_id}
        except FloodWaitError as e:
            return {"status": "flood_wait", "title": "", "detail": f"{e.seconds}초 후 다시 시도하세요"}
        except (InviteHashExpiredError, InviteHashInvalidError):
            return {"status": "invalid_link", "title": "", "detail": "초대 링크가 만료되었거나 유효하지 않습니다"}
        except UsernameNotOccupiedError:
            return {"status": "invalid_link", "title": "", "detail": "존재하지 않는 그룹/채널입니다"}
        except ChannelsTooMuchError:
            return {"status": "error", "title": "", "detail": "가입 가능한 채널/그룹 수를 초과했습니다"}
        except UserBannedInChannelError:
            return {"status": "error", "title": "", "detail": "이 채널에서 차단된 계정입니다"}
        except Exception as e:
            return {"status": "error", "title": "", "detail": str(e)}
    finally:
        await client.disconnect()


async def wipe_account(session_path: str) -> dict:
    """모든 그룹/채널 탈퇴, 모든 개인 대화 삭제, 저장된 연락처 전체 삭제. 되돌릴 수 없습니다."""
    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다.")

        left_groups = 0
        left_channels = 0
        deleted_chats = 0
        errors: list[str] = []

        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, User) and entity.is_self:
                continue  # Saved Messages는 보존
            label = getattr(entity, "title", None) or getattr(entity, "first_name", None) or str(dialog.id)
            try:
                await client.delete_dialog(entity)
                if isinstance(entity, Channel):
                    if entity.megagroup:
                        left_groups += 1
                    else:
                        left_channels += 1
                elif isinstance(entity, Chat):
                    left_groups += 1
                else:
                    deleted_chats += 1
                await asyncio.sleep(0.5)
            except FloodWaitError as e:
                errors.append(f"{label}: {e.seconds}초 대기 필요")
                await asyncio.sleep(min(e.seconds, 30))
            except Exception as e:
                errors.append(f"{label}: {e}")

        deleted_contacts = 0
        try:
            result = await client(GetContactsRequest(hash=0))
            contact_ids = [u.id for u in getattr(result, "users", [])]
            if contact_ids:
                await client(DeleteContactsRequest(id=contact_ids))
                deleted_contacts = len(contact_ids)
        except Exception as e:
            errors.append(f"연락처 삭제 실패: {e}")

        return {
            "left_groups": left_groups,
            "left_channels": left_channels,
            "deleted_chats": deleted_chats,
            "deleted_contacts": deleted_contacts,
            "errors": errors,
        }
    finally:
        await client.disconnect()


async def send_group_message(session_path: str, chat_id: str, text: str) -> None:
    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다.")
        entity = await client.get_entity(int(chat_id))
        await client.send_message(entity, text)
    finally:
        await client.disconnect()


async def add_contact_and_message(session_path: str, target_phone: str, target_name: str, text: str) -> None:
    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다.")
        if not target_phone:
            raise RuntimeError("대상 계정에 전화번호 정보가 없습니다.")
        result = await client(
            ImportContactsRequest(
                contacts=[
                    InputPhoneContact(
                        client_id=0, phone=target_phone, first_name=target_name or "Friend", last_name=""
                    )
                ]
            )
        )
        if not result.users:
            raise RuntimeError("대상 계정을 연락처에서 찾을 수 없습니다 (전화번호를 확인하세요).")
        entity = result.users[0]
        await client.send_message(entity, text)
    finally:
        await client.disconnect()


async def check_and_auto_reply(session_path: str, reply_pool_text: str, skip_peer_ids: set) -> list:
    pool = [line.strip() for line in (reply_pool_text or "").splitlines() if line.strip()]
    if not pool:
        pool = ["네 안녕하세요 :)"]

    client = make_client(session_path)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise TelegramConfigError("세션이 인증되지 않았습니다.")

        replied = []
        async for dialog in client.iter_dialogs(limit=40):
            if not dialog.is_user or dialog.unread_count <= 0:
                continue
            entity = dialog.entity
            if getattr(entity, "bot", False) or getattr(entity, "is_self", False):
                continue
            peer_key = str(entity.id)
            if peer_key in skip_peer_ids:
                try:
                    await client.send_read_acknowledge(entity)
                except Exception:
                    pass
                continue
            text = random.choice(pool)
            try:
                await client.send_message(entity, text)
                await client.send_read_acknowledge(entity)
            except Exception:
                continue
            peer_name = getattr(entity, "first_name", "") or getattr(entity, "username", "") or peer_key
            replied.append({"peer_id": peer_key, "peer_name": peer_name, "text": text})
            await asyncio.sleep(1)
        return replied
    finally:
        await client.disconnect()
