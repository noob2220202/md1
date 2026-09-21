# TeleOps — 텔레그램 다중 계정 관리

개인용 텔레그램 다중 계정 관리 대시보드. Docker/가상환경 없이 Python만으로 실행됩니다.
데이터는 전부 로컬 SQLite(`data/app.db`)와 로컬 세션 파일(`data/sessions/`)에 저장됩니다.

## 기능

- 계정 목록 (아바타 / 닉네임 / 아이디 / 전화번호 / 신뢰도 / 카테고리)
- 닉네임·소개(bio)·프로필 사진 일괄 변경 또는 계정별 개별 변경
- 공식 @SpamBot을 통한 스팸/제한 여부 체크 (신뢰도 지표로 사용)
- 카테고리 분류 (기본 "스팸" 카테고리 + 자유롭게 커스텀 카테고리 생성)
- 그룹/채널 초대 링크 입력 후 원하는 계정들을 골라 일괄 가입 (공개 링크·비공개 초대 링크 모두 지원)
- 계정별 스팸 체크 이력, 그룹 가입 이력, 활동 로그

## 설치 (가상환경 없이)

```bash
pip install -r requirements.txt
# 시스템에 따라 pip 대신 pip3, 또는 pip install --user -r requirements.txt 사용
```

Python 3.10 이상을 권장합니다.

## 설정

1. https://my.telegram.org 에서 API ID / API Hash 발급
2. `.env.example` 을 `.env` 로 복사 후 값 입력

```bash
cp .env.example .env
```

```
TELEGRAM_API_ID=123456
TELEGRAM_API_HASH=your_api_hash_here
```

## 계정 세션 파일 준비

이미 Telethon으로 만든 `.session` 파일이 있다면 그대로 쓰면 됩니다. 없다면 아래 스크립트로 새로 로그인해서 생성하세요.

```bash
python scripts/create_session.py +821012345678
```

전화번호 / 인증코드 / (필요시) 2단계 인증 비밀번호를 입력하면 `data/sessions/`에 `.session` 파일이 생성됩니다.

## 실행

```bash
uvicorn app.main:app --reload --port 8000
```

브라우저에서 http://localhost:8000 접속 후, 대시보드의 "계정 추가" 버튼으로 `.session` 파일을 업로드하면
프로필 정보(이름/아이디/전화번호/사진)를 자동으로 가져옵니다.

## 주의사항

- `data/` 폴더에는 로그인 세션 파일과 DB가 들어 있습니다. **절대 git에 커밋하거나 외부에 노출하지 마세요** (`.gitignore`에 이미 포함됨). 유출 시 해당 텔레그램 계정이 그대로 탈취될 수 있습니다.
- 스팸 체크/일괄 변경을 짧은 시간에 너무 많은 계정에 실행하면 텔레그램의 플러드(rate limit) 정책에 걸릴 수 있습니다. 특히 스팸 체크는 계정 간 2초 간격을 두고 순차 실행됩니다.
- 계정 삭제 시 세션 파일은 바로 지우지 않고 `data/sessions_trash/`로 이동합니다. 완전히 지우려면 해당 폴더를 직접 비우세요.
- 스팸 체크 결과 판정은 @SpamBot 응답 문구를 키워드로 분석하는 방식이라 100% 정확하지 않을 수 있습니다. 원문 응답은 계정 상세 페이지에서 항상 확인할 수 있습니다.
