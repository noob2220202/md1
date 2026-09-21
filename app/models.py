import datetime as dt

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base

account_categories = Table(
    "account_categories",
    Base.metadata,
    Column("account_id", Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    session_filename = Column(String, unique=True, nullable=False)

    phone = Column(String, default="")
    username = Column(String, default="")
    first_name = Column(String, default="")
    last_name = Column(String, default="")
    about = Column(Text, default="")
    avatar_path = Column(String, default="")
    telegram_user_id = Column(String, default="")

    status = Column(String, default="active")  # active, error
    trust_status = Column(String, default="unknown")  # clean, limited, banned, unknown
    last_error = Column(Text, default="")

    auto_reply_enabled = Column(Boolean, default=False)
    auto_reply_pool = Column(Text, default="")

    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)

    categories = relationship("Category", secondary=account_categories, back_populates="accounts")
    spam_checks = relationship(
        "SpamCheck", back_populates="account", cascade="all, delete-orphan", order_by="desc(SpamCheck.checked_at)"
    )
    logs = relationship(
        "ActivityLog", back_populates="account", cascade="all, delete-orphan", order_by="desc(ActivityLog.created_at)"
    )
    group_joins = relationship(
        "GroupJoinLog",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="desc(GroupJoinLog.joined_at)",
    )
    warmup_participations = relationship(
        "WarmupParticipant",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="desc(WarmupParticipant.id)",
    )

    @property
    def display_name(self) -> str:
        name = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return name or self.username or self.phone or f"계정 #{self.id}"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    color = Column(String, default="#6d6dfb")
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    accounts = relationship("Account", secondary=account_categories, back_populates="categories")


class SpamCheck(Base):
    __tablename__ = "spam_checks"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"))
    result = Column(String, default="unknown")  # clean, limited, banned, unknown
    raw_response = Column(Text, default="")
    checked_at = Column(DateTime, default=dt.datetime.utcnow)

    account = relationship("Account", back_populates="spam_checks")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"))
    action = Column(String)
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    account = relationship("Account", back_populates="logs")


class GroupJoinLog(Base):
    __tablename__ = "group_join_logs"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"))
    invite_link = Column(String, default="")
    group_title = Column(String, default="")
    status = Column(String, default="error")  # joined, already_member, invalid_link, flood_wait, error
    detail = Column(Text, default="")
    joined_at = Column(DateTime, default=dt.datetime.utcnow)

    account = relationship("Account", back_populates="group_joins")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String, primary_key=True)
    value = Column(String, default="")


class WarmupCampaign(Base):
    __tablename__ = "warmup_campaigns"

    id = Column(Integer, primary_key=True)
    group_link = Column(String, default="")
    group_chat_id = Column(String, default="")  # resolved after first successful join
    group_messages = Column(Text, default="")  # newline-separated pool
    dm_messages = Column(Text, default="")
    reply_messages = Column(Text, default="")
    interval_min_minutes = Column(Integer, default=30)
    interval_max_minutes = Column(Integer, default=180)

    day = Column(Integer, default=1)  # current global day of the campaign, 1-7
    day_started_at = Column(DateTime, default=dt.datetime.utcnow)
    started_at = Column(DateTime, default=dt.datetime.utcnow)
    status = Column(String, default="running")  # running, completed, cancelled

    dm1_sender_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    dm1_recipient_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    dm1_send_due_at = Column(DateTime, nullable=True)
    dm1_done = Column(Boolean, default=False)

    dm2_sender_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    dm2_recipient_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    dm2_send_due_at = Column(DateTime, nullable=True)
    dm2_done = Column(Boolean, default=False)

    created_at = Column(DateTime, default=dt.datetime.utcnow)

    participants = relationship(
        "WarmupParticipant", back_populates="campaign", cascade="all, delete-orphan", order_by="WarmupParticipant.id"
    )
    events = relationship(
        "WarmupEvent",
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="desc(WarmupEvent.created_at)",
    )


class WarmupParticipant(Base):
    __tablename__ = "warmup_participants"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("warmup_campaigns.id", ondelete="CASCADE"))
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"))

    status = Column(String, default="running")  # running, completed, failed, cancelled
    joined_group = Column(Boolean, default=False)
    join_due_at = Column(DateTime, nullable=True)
    joined_at = Column(DateTime, nullable=True)
    next_message_at = Column(DateTime, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    message_count = Column(Integer, default=0)
    error = Column(Text, default="")

    created_at = Column(DateTime, default=dt.datetime.utcnow)

    campaign = relationship("WarmupCampaign", back_populates="participants")
    account = relationship("Account", back_populates="warmup_participations")


class WarmupEvent(Base):
    __tablename__ = "warmup_events"

    id = Column(Integer, primary_key=True)
    campaign_id = Column(Integer, ForeignKey("warmup_campaigns.id", ondelete="CASCADE"))
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    day = Column(Integer, default=1)
    event_type = Column(String, default="")
    detail = Column(Text, default="")
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    campaign = relationship("WarmupCampaign", back_populates="events")
    account = relationship("Account")


class AutoReplyLog(Base):
    __tablename__ = "auto_reply_logs"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"))
    peer_key = Column(String, default="")
    replied_at = Column(DateTime, default=dt.datetime.utcnow)
