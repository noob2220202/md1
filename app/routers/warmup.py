import datetime as dt
import random

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Account, WarmupCampaign, WarmupEvent, WarmupParticipant
from ..templating import templates

router = APIRouter(prefix="/warmup")

TOTAL_DAYS = 7

PARTICIPANT_STATUS_LABELS = {
    "running": ("진행중", "trust-limited"),
    "completed": ("완료", "trust-clean"),
    "failed": ("실패", "trust-banned"),
    "cancelled": ("취소됨", "trust-unknown"),
}

CAMPAIGN_STATUS_LABELS = {
    "running": ("진행중", "trust-limited"),
    "completed": ("완료", "trust-clean"),
    "cancelled": ("취소됨", "trust-unknown"),
}


def _redirect(msg: str, msg_type: str = "success") -> RedirectResponse:
    return RedirectResponse(url=f"/warmup?msg={msg}&msg_type={msg_type}", status_code=303)


def _busy_account_ids(db: Session) -> set:
    campaigns = db.query(WarmupCampaign).filter(WarmupCampaign.status == "running").all()
    return {p.account_id for c in campaigns for p in c.participants if p.status == "running"}


@router.get("")
def warmup_page(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(Account).order_by(Account.created_at.desc()).all()
    campaigns = db.query(WarmupCampaign).order_by(WarmupCampaign.created_at.desc()).all()
    busy_account_ids = _busy_account_ids(db)

    campaigns_view = []
    for c in campaigns:
        next_day_at = c.day_started_at + dt.timedelta(hours=24) if c.status == "running" else None
        events = (
            db.query(WarmupEvent)
            .filter(WarmupEvent.campaign_id == c.id)
            .order_by(WarmupEvent.created_at.desc())
            .limit(20)
            .all()
        )
        campaigns_view.append(
            {
                "campaign": c,
                "status_label": CAMPAIGN_STATUS_LABELS.get(c.status, (c.status, "trust-unknown")),
                "next_day_at": next_day_at,
                "participants": c.participants,
                "events": events,
            }
        )

    return templates.TemplateResponse(
        "warmup.html",
        {
            "request": request,
            "accounts": accounts,
            "campaigns_view": campaigns_view,
            "busy_account_ids": busy_account_ids,
            "total_days": TOTAL_DAYS,
            "participant_status_labels": PARTICIPANT_STATUS_LABELS,
        },
    )


@router.post("/create")
async def create_campaign(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    group_link = str(form.get("group_link", "")).strip()
    group_messages = str(form.get("group_messages", "")).strip()
    dm_messages = str(form.get("dm_messages", "")).strip()
    reply_messages = str(form.get("reply_messages", "")).strip()
    ids = [int(v) for v in form.getlist("account_ids")]

    try:
        interval_min = int(form.get("interval_min") or 30)
        interval_max = int(form.get("interval_max") or 180)
    except ValueError:
        return _redirect("메시지 간격은 숫자로 입력하세요", "error")

    if not group_link:
        return _redirect("그룹 링크를 입력하세요", "error")
    if not group_messages:
        return _redirect("그룹 대화 메시지를 최소 1개 입력하세요 (줄바꿈으로 구분)", "error")
    if interval_min <= 0 or interval_max < interval_min:
        return _redirect("메시지 간격 설정이 올바르지 않습니다", "error")
    if len(ids) < 2:
        return _redirect("최소 2개 이상의 계정을 선택하세요 (서로 대화하려면 2개 이상 필요합니다)", "error")

    busy_ids = _busy_account_ids(db)
    usable_ids = [i for i in ids if i not in busy_ids]
    skipped = len(ids) - len(usable_ids)
    if len(usable_ids) < 2:
        return _redirect("선택한 계정 대부분이 이미 다른 데우기에 참여 중입니다", "error")

    now = dt.datetime.utcnow()
    campaign = WarmupCampaign(
        group_link=group_link,
        group_messages=group_messages,
        dm_messages=dm_messages or group_messages,
        reply_messages=reply_messages or group_messages,
        interval_min_minutes=interval_min,
        interval_max_minutes=interval_max,
        day=1,
        day_started_at=now,
        started_at=now,
        status="running",
    )
    db.add(campaign)
    db.flush()

    for aid in usable_ids:
        join_due_at = now + dt.timedelta(minutes=random.randint(1, 20 * 60))
        db.add(
            WarmupParticipant(
                campaign_id=campaign.id,
                account_id=aid,
                status="running",
                join_due_at=join_due_at,
            )
        )

    db.add(
        WarmupEvent(
            campaign_id=campaign.id,
            account_id=None,
            day=1,
            event_type="campaign_started",
            detail=f"{len(usable_ids)}개 계정으로 데우기 시작",
        )
    )
    db.commit()

    msg = f"데우기 시작: {len(usable_ids)}개 계정 (서버가 계속 실행 중이어야 예정된 작업이 실행됩니다)"
    if skipped:
        msg += f" / {skipped}개 계정은 이미 다른 데우기 진행 중이라 제외됨"
    return _redirect(msg)


@router.post("/{campaign_id}/cancel")
def cancel_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.get(WarmupCampaign, campaign_id)
    if not campaign:
        return _redirect("캠페인을 찾을 수 없습니다", "error")
    campaign.status = "cancelled"
    for p in campaign.participants:
        if p.status == "running":
            p.status = "cancelled"
    db.add(WarmupEvent(campaign_id=campaign.id, account_id=None, day=campaign.day, event_type="cancelled", detail=""))
    db.commit()
    return _redirect("데우기가 취소되었습니다")
