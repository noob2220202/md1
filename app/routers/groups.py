import asyncio

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import telegram_client as tg
from ..database import get_db
from ..models import Account, ActivityLog, GroupJoinLog
from ..session_paths import session_path
from ..templating import templates

router = APIRouter(prefix="/groups")

STATUS_LABELS = {
    "joined": ("가입 완료", "trust-clean"),
    "already_member": ("이미 가입됨", "trust-unknown"),
    "invalid_link": ("잘못된 링크", "trust-banned"),
    "flood_wait": ("대기 필요", "trust-limited"),
    "error": ("오류", "trust-banned"),
}


def _redirect(msg: str, msg_type: str = "success") -> RedirectResponse:
    return RedirectResponse(url=f"/groups?msg={msg}&msg_type={msg_type}", status_code=303)


@router.get("")
def groups_page(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(Account).order_by(Account.created_at.desc()).all()
    logs = db.query(GroupJoinLog).order_by(GroupJoinLog.joined_at.desc()).limit(100).all()
    return templates.TemplateResponse(
        "groups.html",
        {
            "request": request,
            "accounts": accounts,
            "logs": logs,
            "status_labels": STATUS_LABELS,
        },
    )


@router.post("/join")
async def join_group(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    link = str(form.get("invite_link", "")).strip()
    ids = [int(v) for v in form.getlist("account_ids")]

    if not link:
        return _redirect("초대 링크를 입력하세요", "error")
    if not ids:
        return _redirect("가입할 계정을 하나 이상 선택하세요", "error")

    ok, fail = 0, 0
    for aid in ids:
        account = db.get(Account, aid)
        if not account:
            continue
        try:
            result = await tg.join_group(session_path(account), link)
        except Exception as e:
            result = {"status": "error", "title": "", "detail": str(e)}

        db.add(
            GroupJoinLog(
                account_id=account.id,
                invite_link=link,
                group_title=result.get("title") or "",
                status=result["status"],
                detail=result.get("detail") or "",
            )
        )
        db.add(
            ActivityLog(
                account_id=account.id,
                action="group_join",
                detail=f"{link} -> {STATUS_LABELS.get(result['status'], (result['status'],))[0]}",
            )
        )
        if result["status"] in ("joined", "already_member"):
            ok += 1
        else:
            fail += 1
        db.commit()
        await asyncio.sleep(3)

    return _redirect(f"그룹 가입 완료: 성공 {ok} / 실패 {fail}")
