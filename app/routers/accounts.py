import asyncio
import datetime as dt
import shutil
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import settings_store
from .. import telegram_client as tg
from ..config import SESSIONS_DIR, TRASH_DIR
from ..database import get_db
from ..models import Account, ActivityLog, Category, SpamCheck
from ..session_paths import session_path as _session_path

router = APIRouter(prefix="/accounts")


def _redirect(msg: str, msg_type: str = "success", path: str = "/") -> RedirectResponse:
    return RedirectResponse(url=f"{path}?msg={msg}&msg_type={msg_type}", status_code=303)


async def _wipe_and_log(account: Account, db: Session, action: str = "wipe") -> str:
    result = await tg.wipe_account(_session_path(account))
    summary = (
        f"그룹 {result['left_groups']}개, 채널 {result['left_channels']}개, "
        f"대화 {result['deleted_chats']}개, 연락처 {result['deleted_contacts']}명 삭제"
    )
    if result["errors"]:
        summary += f" (오류 {len(result['errors'])}건)"
    db.add(ActivityLog(account_id=account.id, action=action, detail=summary))
    return summary


@router.post("/upload")
async def upload_accounts(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    added, failed = 0, []
    for f in files:
        if not f.filename or not f.filename.endswith(".session"):
            failed.append(f"{f.filename or '(이름없음)'}: .session 파일이 아닙니다")
            continue

        unique_name = f"{uuid.uuid4().hex}.session"
        dest = SESSIONS_DIR / unique_name
        with dest.open("wb") as out:
            shutil.copyfileobj(f.file, out)

        account = Account(session_filename=unique_name, status="active")
        db.add(account)
        db.flush()

        try:
            profile = await tg.fetch_profile(_session_path(account), account.id)
            for key, value in profile.items():
                setattr(account, key, value)
            db.add(ActivityLog(account_id=account.id, action="added", detail="세션 파일 업로드로 계정 추가됨"))
            added += 1

            if settings_store.get_bool_setting("auto_wipe_on_add"):
                try:
                    await _wipe_and_log(account, db, action="auto_wipe")
                except Exception as e:
                    db.add(ActivityLog(account_id=account.id, action="auto_wipe_failed", detail=str(e)))
        except Exception as e:
            account.status = "error"
            account.last_error = str(e)
            failed.append(f"{f.filename}: {e}")
        db.commit()

    msg = f"{added}개 계정이 추가되었습니다"
    if settings_store.get_bool_setting("auto_wipe_on_add") and added:
        msg += " (그룹/채널/대화/연락처 자동 초기화 완료)"
    if failed:
        msg += f" (실패 {len(failed)}건: {'; '.join(failed)[:120]})"
    return _redirect(msg, "success" if not failed else "warning")


@router.post("/delete")
async def delete_accounts(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("account_ids")]
    count = 0
    for aid in ids:
        account = db.get(Account, aid)
        if not account:
            continue
        src = SESSIONS_DIR / account.session_filename
        if src.exists():
            shutil.move(str(src), str(TRASH_DIR / account.session_filename))
        db.delete(account)
        count += 1
    db.commit()
    return _redirect(f"{count}개 계정이 삭제되었습니다 (세션 파일은 휴지통 폴더로 이동됨)")


@router.post("/{account_id}/edit")
async def edit_account(
    account_id: int,
    first_name: str = Form(""),
    last_name: str = Form(""),
    about: str = Form(""),
    db: Session = Depends(get_db),
):
    account = db.get(Account, account_id)
    if not account:
        return _redirect("계정을 찾을 수 없습니다", "error")
    try:
        await tg.update_profile(_session_path(account), first_name, last_name, about)
        account.first_name, account.last_name, account.about = first_name, last_name, about
        db.add(ActivityLog(account_id=account.id, action="profile_edit", detail="닉네임/소개 변경"))
        db.commit()
        return _redirect("프로필이 변경되었습니다", path=f"/accounts/{account_id}")
    except Exception as e:
        return _redirect(f"변경 실패: {e}", "error", path=f"/accounts/{account_id}")


@router.post("/{account_id}/photo")
async def edit_photo(account_id: int, photo: UploadFile = File(...), db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        return _redirect("계정을 찾을 수 없습니다", "error")
    tmp_path = SESSIONS_DIR / f"tmp_{uuid.uuid4().hex}"
    with tmp_path.open("wb") as out:
        shutil.copyfileobj(photo.file, out)
    try:
        avatar_path = await tg.update_photo(_session_path(account), str(tmp_path), account.id)
        account.avatar_path = avatar_path
        db.add(ActivityLog(account_id=account.id, action="photo_edit", detail="프로필 사진 변경"))
        db.commit()
        return _redirect("프로필 사진이 변경되었습니다", path=f"/accounts/{account_id}")
    except Exception as e:
        return _redirect(f"사진 변경 실패: {e}", "error", path=f"/accounts/{account_id}")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/bulk-edit")
async def bulk_edit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("account_ids")]
    first_name = str(form.get("first_name", "")).strip()
    last_name = str(form.get("last_name", "")).strip()
    about = str(form.get("about", "")).strip()
    has_first = first_name != ""
    has_last = last_name != ""
    has_about = about != ""

    ok, fail = 0, 0
    for aid in ids:
        account = db.get(Account, aid)
        if not account:
            continue
        try:
            fn = first_name if has_first else account.first_name
            ln = last_name if has_last else account.last_name
            ab = about if has_about else account.about
            await tg.update_profile(_session_path(account), fn or "", ln or "", ab or "")
            account.first_name, account.last_name, account.about = fn, ln, ab
            db.add(ActivityLog(account_id=account.id, action="bulk_profile_edit", detail="일괄 프로필 변경"))
            ok += 1
        except Exception as e:
            account.last_error = str(e)
            fail += 1
        db.commit()
    return _redirect(f"일괄 변경 완료: 성공 {ok} / 실패 {fail}")


@router.post("/bulk-photo")
async def bulk_photo(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("account_ids")]
    photo = form.get("photo")
    if photo is None or not getattr(photo, "filename", ""):
        return _redirect("사진 파일을 선택하세요", "error")

    tmp_path = SESSIONS_DIR / f"tmp_{uuid.uuid4().hex}"
    with tmp_path.open("wb") as out:
        shutil.copyfileobj(photo.file, out)

    ok, fail = 0, 0
    try:
        for aid in ids:
            account = db.get(Account, aid)
            if not account:
                continue
            try:
                avatar_path = await tg.update_photo(_session_path(account), str(tmp_path), account.id)
                account.avatar_path = avatar_path
                db.add(ActivityLog(account_id=account.id, action="bulk_photo_edit", detail="일괄 사진 변경"))
                ok += 1
            except Exception as e:
                account.last_error = str(e)
                fail += 1
            db.commit()
    finally:
        tmp_path.unlink(missing_ok=True)
    return _redirect(f"사진 일괄 변경 완료: 성공 {ok} / 실패 {fail}")


@router.post("/{account_id}/spam-check")
async def spam_check_single(account_id: int, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        return _redirect("계정을 찾을 수 없습니다", "error")
    try:
        result = await tg.run_spam_check(_session_path(account))
        account.trust_status = result["result"]
        account.last_checked_at = dt.datetime.utcnow()
        db.add(SpamCheck(account_id=account.id, result=result["result"], raw_response=result["raw_response"]))
        db.add(ActivityLog(account_id=account.id, action="spam_check", detail=f"결과: {result['result']}"))
        db.commit()
        return _redirect("스팸 체크가 완료되었습니다", path=f"/accounts/{account_id}")
    except Exception as e:
        return _redirect(f"스팸 체크 실패: {e}", "error", path=f"/accounts/{account_id}")


@router.post("/spam-check/bulk")
async def spam_check_bulk(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("account_ids")]
    ok, fail = 0, 0
    for aid in ids:
        account = db.get(Account, aid)
        if not account:
            continue
        try:
            result = await tg.run_spam_check(_session_path(account))
            account.trust_status = result["result"]
            account.last_checked_at = dt.datetime.utcnow()
            db.add(SpamCheck(account_id=account.id, result=result["result"], raw_response=result["raw_response"]))
            db.add(ActivityLog(account_id=account.id, action="spam_check", detail=f"결과: {result['result']}"))
            ok += 1
        except Exception as e:
            account.last_error = str(e)
            fail += 1
        db.commit()
        await asyncio.sleep(2)
    return _redirect(f"스팸 체크 완료: 성공 {ok} / 실패 {fail}")


@router.post("/{account_id}/wipe")
async def wipe_single(account_id: int, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        return _redirect("계정을 찾을 수 없습니다", "error")
    try:
        summary = await _wipe_and_log(account, db, action="manual_wipe")
        db.commit()
        return _redirect(f"초기화 완료: {summary}", path=f"/accounts/{account_id}")
    except Exception as e:
        return _redirect(f"초기화 실패: {e}", "error", path=f"/accounts/{account_id}")


@router.post("/wipe/bulk")
async def wipe_bulk(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    ids = [int(v) for v in form.getlist("account_ids")]
    ok, fail = 0, 0
    for aid in ids:
        account = db.get(Account, aid)
        if not account:
            continue
        try:
            await _wipe_and_log(account, db, action="manual_wipe")
            ok += 1
        except Exception as e:
            account.last_error = str(e)
            fail += 1
        db.commit()
        await asyncio.sleep(1)
    return _redirect(f"일괄 초기화 완료: 성공 {ok} / 실패 {fail}")


@router.post("/{account_id}/categories")
async def set_categories(account_id: int, request: Request, db: Session = Depends(get_db)):
    account = db.get(Account, account_id)
    if not account:
        return _redirect("계정을 찾을 수 없습니다", "error")
    form = await request.form()
    ids = [int(v) for v in form.getlist("category_ids")]
    account.categories = db.query(Category).filter(Category.id.in_(ids)).all() if ids else []
    db.commit()
    return _redirect("카테고리가 변경되었습니다", path=f"/accounts/{account_id}")
