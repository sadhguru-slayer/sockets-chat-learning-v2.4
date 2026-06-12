from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, DateTime, Boolean, Enum
from datetime import datetime
from .base import Base
import enum


class ConversationType(enum.Enum):
    PERSONAL = "PERSONAL"
    GROUP = "GROUP"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)

    type: Mapped[ConversationType] = mapped_column(Enum(ConversationType))

    title: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    participants = relationship(
        "ConversationParticipants",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan"
    )