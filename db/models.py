import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class DealStatus(str, enum.Enum):
    collecting = "collecting"
    goal_reached = "goal_reached"
    expired = "expired"
    cancelled = "cancelled"
    sent_to_manager = "sent_to_manager"
    confirmed = "confirmed"


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    house_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    profile_vector: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tone_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    delivery_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checkout_pending: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    manager_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    order_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    deals: Mapped[list["Deal"]] = relationship(back_populates="group")
    messages: Mapped[list["GroupMessage"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, default=0)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    group: Mapped[Group] = relationship(back_populates="messages")


class TelegramUser(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("telegram_user_id", name="uq_user_telegram_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_pending: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"), index=True)
    mcp_product_id: Mapped[str] = mapped_column(String(64), index=True)
    product_slug: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_name: Mapped[str] = mapped_column(String(512))
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    unit_price_retail: Mapped[float] = mapped_column(Numeric(10, 2))
    unit_price_wholesale: Mapped[float] = mapped_column(Numeric(10, 2))
    wholesale_pack_size: Mapped[float] = mapped_column(Numeric(10, 3))
    savings_per_unit: Mapped[float] = mapped_column(Numeric(10, 2))
    weighted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[DealStatus] = mapped_column(
        Enum(DealStatus, name="deal_status"),
        default=DealStatus.collecting,
        server_default=DealStatus.collecting.name,
        index=True,
    )
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    group: Mapped[Group] = relationship(back_populates="deals")
    participants: Mapped[list["Participant"]] = relationship(
        back_populates="deal", cascade="all, delete-orphan"
    )


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("deal_id", "telegram_user_id", name="uq_participant_deal_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(10, 3), default=1)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    deal: Mapped[Deal] = relationship(back_populates="participants")
