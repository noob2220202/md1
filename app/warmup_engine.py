import asyncio
import datetime as dt
import random

from . import telegram_client as tg
from .database import SessionLocal
from .models import Account, ActivityLog, AutoReplyLog, WarmupCampaign, WarmupEvent
from .session_paths import session_path

MESSAGING_START_DAY = 2
TOTAL_DAYS = 7
TICK_SECONDS = 90
AUTO_REPLY_EVERY_N_TICKS = 4


def _log(db, campaign_id, account_id, day, event_type, detail=""):
    db.add(
        WarmupEvent(
            campaign_id=campaign_id,
            account_id=account_id,
            day=day,
            event_type=event_type,
            detail=detail,
        )
    )


def _random_minutes(lo: int, hi: int) -> int:
    lo, hi = max(1, lo), max(lo, hi)
    return random.randint(lo, hi)


async def _process_join(db, campaign: WarmupCampaign, participant) -> None:
    account = participant.account
    try:
        result = await tg.join_group(session_path(account), campaign.group_link)
        if result["status"] in ("joined", "already_member"):
            participant.joined_group = True
            participant.joined_at = dt.datetime.utcnow()
            if not campaign.group_chat_id and result.get("chat_id"):
                campaign.group_chat_id = str(result["chat_id"])
            _log(db, campaign.id, account.id, 1, "joined_group", result.get("title") or "")
            participant.next_message_at = dt.datetime.utcnow() + dt.timedelta(
                minutes=_random_minutes(campaign.interval_min_minutes, campaign.interval_max_minutes)
            )
        else:
            participant.status = "failed"
            participant.error = result.get("detail") or result["status"]
            _log(db, campaign.id, account.id, 1, "join_failed", participant.error)
    except Exception as e:
        participant.status = "failed"
        participant.error = str(e)
        _log(db, campaign.id, account.id, 1, "join_failed", str(e))


async def _send_group_message(db, campaign: WarmupCampaign, participant) -> None:
    account = participant.account
    pool = [line.strip() for line in (campaign.group_messages or "").splitlines() if line.strip()]
    if not pool or not campaign.group_chat_id:
        participant.next_message_at = dt.datetime.utcnow() + dt.timedelta(minutes=30)
        return
    text = random.choice(pool)
    try:
        await tg.send_group_message(session_path(account), campaign.group_chat_id, text)
        participant.last_message_at = dt.datetime.utcnow()
        participant.message_count = (participant.message_count or 0) + 1
        participant.next_message_at = dt.datetime.utcnow() + dt.timedelta(
            minutes=_random_minutes(campaign.interval_min_minutes, campaign.interval_max_minutes)
        )
        _log(db, campaign.id, account.id, campaign.day, "group_message", text[:80])
    except Exception as e:
        participant.error = str(e)
        _log(db, campaign.id, account.id, campaign.day, "message_failed", str(e))
        participant.next_message_at = dt.datetime.utcnow() + dt.timedelta(minutes=30)


async def _run_dm_pair(db, campaign: WarmupCampaign, sender: Account, recipient: Account) -> None:
    dm_pool = [line.strip() for line in (campaign.dm_messages or "").splitlines() if line.strip()] or ["안녕하세요!"]
    reply_pool = [line.strip() for line in (campaign.reply_messages or "").splitlines() if line.strip()] or [
        "네 안녕하세요 :)"
    ]
    dm_text = random.choice(dm_pool)
    try:
        await tg.add_contact_and_message(session_path(sender), recipient.phone, recipient.first_name, dm_text)
        _log(db, campaign.id, sender.id, campaign.day, "dm_sent", f"-> {recipient.display_name}: {dm_text[:60]}")
    except Exception as e:
        _log(db, campaign.id, sender.id, campaign.day, "dm_failed", str(e))
        return

    await asyncio.sleep(random.randint(10, 90))

    reply_text = random.choice(reply_pool)
    try:
        await tg.add_contact_and_message(session_path(recipient), sender.phone, sender.first_name, reply_text)
        _log(db, campaign.id, recipient.id, campaign.day, "dm_reply", f"-> {sender.display_name}: {reply_text[:60]}")
    except Exception as e:
        _log(db, campaign.id, recipient.id, campaign.day, "dm_reply_failed", str(e))


def _schedule_dm(db, campaign: WarmupCampaign, slot: int) -> None:
    candidates = [p for p in campaign.participants if p.joined_group and p.status == "running"]
    if len(candidates) < 2:
        _log(db, campaign.id, None, campaign.day, "dm_skipped", "참가자가 2명 미만이라 디엠 단계를 건너뜁니다")
        if slot == 1:
            campaign.dm1_done = True
        else:
            campaign.dm2_done = True
        return

    sender, recipient = random.sample(candidates, 2)
    due_at = dt.datetime.utcnow() + dt.timedelta(minutes=random.randint(5, 20 * 60))
    if slot == 1:
        campaign.dm1_sender_id = sender.account_id
        campaign.dm1_recipient_id = recipient.account_id
        campaign.dm1_send_due_at = due_at
    else:
        campaign.dm2_sender_id = sender.account_id
        campaign.dm2_recipient_id = recipient.account_id
        campaign.dm2_send_due_at = due_at
    _log(
        db,
        campaign.id,
        None,
        campaign.day,
        "dm_scheduled",
        f"{sender.account.display_name} -> {recipient.account.display_name}",
    )


async def _advance_days(db, campaign: WarmupCampaign) -> None:
    now = dt.datetime.utcnow()
    while campaign.day < TOTAL_DAYS and now >= campaign.day_started_at + dt.timedelta(hours=24):
        campaign.day += 1
        campaign.day_started_at += dt.timedelta(hours=24)
        _log(db, campaign.id, None, campaign.day, "day_advanced", f"{campaign.day}일차 시작")

        if campaign.day == 4:
            _schedule_dm(db, campaign, slot=1)
        elif campaign.day == 5:
            _schedule_dm(db, campaign, slot=2)

    if campaign.day == TOTAL_DAYS and now >= campaign.day_started_at + dt.timedelta(hours=24) and campaign.status == "running":
        campaign.status = "completed"
        for participant in campaign.participants:
            if participant.status == "running":
                participant.status = "completed"
                account = participant.account
                account.auto_reply_enabled = True
                account.auto_reply_pool = campaign.reply_messages
                _log(db, campaign.id, account.id, campaign.day, "completed", "웜업 완료, 자동 답장 활성화")


async def _process_campaign(db, campaign: WarmupCampaign) -> None:
    await _advance_days(db, campaign)
    db.commit()

    if campaign.status != "running":
        return

    now = dt.datetime.utcnow()

    if campaign.day == 1:
        for participant in campaign.participants:
            if participant.status != "running" or participant.joined_group:
                continue
            if participant.join_due_at and now >= participant.join_due_at:
                await _process_join(db, campaign, participant)
                db.commit()

    if campaign.day >= MESSAGING_START_DAY:
        for participant in campaign.participants:
            if participant.status != "running" or not participant.joined_group:
                continue
            if participant.next_message_at and now >= participant.next_message_at:
                await _send_group_message(db, campaign, participant)
                db.commit()

    if campaign.day >= 4 and campaign.dm1_send_due_at and not campaign.dm1_done and now >= campaign.dm1_send_due_at:
        sender = db.get(Account, campaign.dm1_sender_id)
        recipient = db.get(Account, campaign.dm1_recipient_id)
        campaign.dm1_done = True
        db.commit()
        if sender and recipient:
            await _run_dm_pair(db, campaign, sender, recipient)
            db.commit()

    if campaign.day >= 5 and campaign.dm2_send_due_at and not campaign.dm2_done and now >= campaign.dm2_send_due_at:
        sender = db.get(Account, campaign.dm2_sender_id)
        recipient = db.get(Account, campaign.dm2_recipient_id)
        campaign.dm2_done = True
        db.commit()
        if sender and recipient:
            await _run_dm_pair(db, campaign, sender, recipient)
            db.commit()


async def run_tick() -> None:
    db = SessionLocal()
    try:
        campaigns = db.query(WarmupCampaign).filter(WarmupCampaign.status == "running").all()
        for campaign in campaigns:
            try:
                await _process_campaign(db, campaign)
            except Exception as e:
                _log(db, campaign.id, None, campaign.day, "tick_error", str(e))
                db.commit()
    finally:
        db.close()


async def run_auto_reply_tick() -> None:
    db = SessionLocal()
    try:
        cutoff = dt.datetime.utcnow() - dt.timedelta(hours=6)
        accounts = db.query(Account).filter(Account.auto_reply_enabled == True, Account.status == "active").all()  # noqa: E712
        for account in accounts:
            recent = (
                db.query(AutoReplyLog)
                .filter(AutoReplyLog.account_id == account.id, AutoReplyLog.replied_at >= cutoff)
                .all()
            )
            skip_ids = {r.peer_key for r in recent}
            try:
                replies = await tg.check_and_auto_reply(session_path(account), account.auto_reply_pool, skip_ids)
                for r in replies:
                    db.add(AutoReplyLog(account_id=account.id, peer_key=r["peer_id"], replied_at=dt.datetime.utcnow()))
                    db.add(
                        ActivityLog(
                            account_id=account.id,
                            action="auto_reply",
                            detail=f"{r['peer_name']}에게 자동 답장: {r['text'][:60]}",
                        )
                    )
                db.commit()
            except Exception as e:
                db.add(ActivityLog(account_id=account.id, action="auto_reply_failed", detail=str(e)))
                db.commit()
            await asyncio.sleep(2)
    finally:
        db.close()


async def warmup_background_loop() -> None:
    tick_count = 0
    while True:
        try:
            await run_tick()
            tick_count += 1
            if tick_count % AUTO_REPLY_EVERY_N_TICKS == 0:
                await run_auto_reply_tick()
        except Exception:
            pass
        await asyncio.sleep(TICK_SECONDS)
