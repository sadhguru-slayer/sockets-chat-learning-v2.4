from sqlalchemy import Text, ForeignKey, DateTime, Enum, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from .base import Base
import enum


class MessageType(enum.Enum):
    CHAT = "CHAT"
    SYSTEM = "SYSTEM"

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True
    )

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True
    )

    type: Mapped[MessageType] = mapped_column(
        Enum(MessageType),
        default=MessageType.CHAT
    )

    message: Mapped[str] = mapped_column(Text)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted_global: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    conversation = relationship(
        "Conversation",
        back_populates="messages"
    )

    sender = relationship(
        "User",
        back_populates="messages"
    )

    __table_args__ = (
        Index(
            "ix_messages_conversation_time",
            "conversation_id",
            "timestamp"
        ),
    )

class MessageDeleteState(Base):
    __tablename__ = "message_delete_state"
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True
    )
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )

    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc),)