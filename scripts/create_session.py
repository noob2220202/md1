"""
새 텔레그램 계정의 세션 파일을 생성하는 스크립트.

사용법:
    python scripts/create_session.py 01012345678

전화번호, 인증코드(그리고 필요하다면 2단계 인증 비밀번호)를 입력하면
data/sessions 폴더에 .session 파일이 생성됩니다.
생성된 파일은 웹 대시보드의 "계정 추가"에서 업로드해 등록하세요.
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telethon import TelegramClient  # noqa: E402

from app.config import SESSIONS_DIR, settings  # noqa: E402


async def main() -> None:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        print("먼저 .env 파일에 TELEGRAM_API_ID / TELEGRAM_API_HASH를 설정하세요.")
        return

    if len(sys.argv) < 2:
        print("사용법: python scripts/create_session.py <전화번호(+국가코드 포함)>")
        return

    phone = sys.argv[1]
    session_name = uuid.uuid4().hex
    session_path = str(SESSIONS_DIR / session_name)

    client = TelegramClient(session_path, settings.telegram_api_id, settings.telegram_api_hash)
    await client.start(phone=phone)
    me = await client.get_me()
    await client.disconnect()

    print(f"완료! {me.first_name or me.username or phone} 계정의 세션 파일이 생성되었습니다:")
    print(f"  {session_path}.session")
    print("웹 대시보드의 '계정 추가' 버튼에서 이 파일을 업로드하세요.")


if __name__ == "__main__":
    asyncio.run(main())
