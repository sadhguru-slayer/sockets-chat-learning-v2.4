from app.models.users import ConversationParticipants
from sqlalchemy import select
# app/ws/sockets.py

from datetime import timezone,datetime
import json

from sqlalchemy import select
from app.services.conversation_cache import ConversationCache

from app.ws.manager import manager
from app.ws.events import WSMessageEvent

from app.models.messages import Message,MessageDeleteState
from app.models.users import ConversationParticipants,ParticipantRole


from app.redis_client import r

from app.dependencies.db import db_session


# ------------------- HELPERS -------------
async def get_other_user(
    conversation_id: int,
    current_user_id: int,
    db
):
    stmt = select(
        ConversationParticipants.user_id
    ).where(
        ConversationParticipants.conversation_id == conversation_id,
        ConversationParticipants.user_id != current_user_id
    )

    result = await db.execute(stmt)

    return result.scalar_one_or_none()


# ------------- SERVICES -----------------
class MessageService:
    def __init__(self, db):
        self.db = db
    async def MessageCreate(self,user, data):
        conversation_id = data.get("conversation_id")

        if not conversation_id:
            return

        if not await ConversationCache.is_member(
            conversation_id,
            user.id
        ):
            return

        content = data.get("message", "").strip()

        if not content:
            return

        db_message = Message(
            conversation_id=conversation_id,
            sender_id=user.id,
            message=content
        )

        self.db.add(db_message)
        await self.db.commit()
        await self.db.refresh(db_message)

        event_payload = {
            "type": "chat",
            "event": WSMessageEvent.MESSAGE_CREATED.value,
            "message_id": db_message.id,
            "conversation_id": conversation_id,
            "sender_id": user.id,
            "username": user.username,
            "message": content,
            "timestamp": db_message.timestamp.astimezone(
                timezone.utc
            ).isoformat()
        }

        await r.publish(
            f"conversation:{conversation_id}",
            json.dumps(event_payload)
        )

    async def MessageEdited(self,user,data):
        conversation_id = data.get(
            "conversation_id"
        )
        if not conversation_id:
            return
        if not await ConversationCache.is_member(
            conversation_id,
            user.id
        ):
            return
        content = data.get(
            "message",
            ""
        ).strip()
        message_id = data.get(
            "message_id",
            None
        )
        if not content or not message_id:
            return
        stmt = select(Message).where(Message.id == message_id)
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        if not message:
            return
        if message.sender_id != user.id:
            return
        if message.is_deleted_global:
            return
        message.message = content
        message.edited_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(message)
        event_payload = {
            "type": "chat",
            "event": WSMessageEvent.MESSAGE_EDITED.value,
            "message_id": message.id,
            "conversation_id": conversation_id,
            "sender_id": user.id,
            "username": user.username,
            "message": content,
            "timestamp": (
                message.timestamp
                .astimezone(timezone.utc)
                .isoformat()
            ),
            "edited_at": (
                message.edited_at
                .astimezone(timezone.utc)
                .isoformat()
            )
        }
        await r.publish(
            f"conversation:{conversation_id}",
            json.dumps(event_payload)
        )   

    async def MessageDeletedForEveryOne(self,user,data):
        conversation_id = data.get("conversation_id")
        message_id = data.get("message_id")
        if not conversation_id or not message_id:
            return
        if not await ConversationCache.is_member(
            conversation_id,
            user.id
        ):
            return
        stmt = select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id
        )
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        par_stmt_role = select(ConversationParticipants.role).where(
            ConversationParticipants.user_id == user.id,
            ConversationParticipants.conversation_id == conversation_id
        )
        par_role_result = await self.db.execute(par_stmt_role)
        participant_role = par_role_result.scalar_one_or_none()
        if not message:
            return
        # print(participant_role == ParticipantRole.OWNER)
        # print(participant_role)
        # Only sender can delete for everyone
        if (
            message.sender_id != user.id
            and participant_role not in [ParticipantRole.ADMIN, ParticipantRole.OWNER]
        ):
            # print(message.sender_id != user.id)
            # print(participant_role not in [ParticipantRole.ADMIN, ParticipantRole.OWNER])
            return
        message.is_deleted_global = True
        await self.db.commit()
        await self.db.refresh(message)
        event_payload = {
            "type": "chat",
            "event": WSMessageEvent.MESSAGE_DELETED_FOR_EVERYONE.value,
            "message_id": message.id,
            "conversation_id": conversation_id,
            "sender_id": message.sender_id,
            "message": "Deleted for everyone",
            "timestamp": (
                message.timestamp
                .astimezone(timezone.utc)
                .isoformat()
            )
        }
        await r.publish(
            f"conversation:{conversation_id}",
            json.dumps(event_payload)
        )

    async def MessageDeletedForMe(self,user,data):
        conversation_id = data.get("conversation_id")
        message_id = data.get("message_id")
        if not conversation_id or not message_id:
            return
        if not await ConversationCache.is_member(
            conversation_id,
            user.id
        ):
            return
        stmt = select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id
        )
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()
        if not message:
            return
        stmt = select(MessageDeleteState).where(
            MessageDeleteState.message_id == message_id,
            MessageDeleteState.user_id == user.id
        )

        existing = (
            await self.db.execute(stmt)
        ).scalar_one_or_none()

        if existing:
            return
        delete_state = MessageDeleteState(
            message_id=message_id,
            user_id=user.id
        )
        self.db.add(delete_state)
        await self.db.commit()
        event_payload = {
            "type": "chat",
            "event": WSMessageEvent.MESSAGE_DELETED_FOR_ME.value,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "user_id": user.id
        }
        await r.publish(
            f"user:{user.id}",
            json.dumps(event_payload)
        )


