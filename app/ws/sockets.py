# app/ws/sockets.py

from datetime import timezone,datetime
import json
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from app.services.presence import watch_user,unwatch_user,is_online
from app.services.chat import get_other_user

from app.ws.manager import manager
from app.ws.events import WSMessageEvent

from app.models.messages import Message,MessageDeleteState
from app.models.users import ConversationParticipants,ParticipantRole
from app.models.conversations import ConversationType

from app.services.message_store import MessageStore

from app.redis_client import r

from app.dependencies.auth import get_current_user_ws
from app.dependencies.db import db_session


router = APIRouter()

async def redis_user_listner(user_id: int, ws: WebSocket):
    pubsub = r.pubsub()
    await pubsub.subscribe(f"user:{user_id}")
    print("👂 Listening Redis for user:", user_id)

    try:
        async for message in pubsub.listen():   # ✅ IMPORTANT FIX

            if message["type"] != "message":
                continue

            data = message["data"]

            if isinstance(data, bytes):
                data = data.decode("utf-8")

            payload = json.loads(data)

            # print("🔥 Redis → WS:", payload)

            await manager.send_to_user(user_id, payload)

    except asyncio.CancelledError:
        await pubsub.close()


async def is_member(
    db: db_session,
    conversation_id: int,
    user_id: int
):
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation_id,
        ConversationParticipants.user_id == user_id
    )

    result = await db.execute(stmt)

    return result.scalar_one_or_none() is not None


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    db: db_session,
    token: str = Query(...)
):
    user = await get_current_user_ws(
        db,
        token
    )

    if not user:
        await ws.close(code=1008)
        return

    await manager.connect(
        user.id,
        user.username,
        ws
    )

    redis_task = asyncio.create_task(redis_user_listner(user.id,ws))

    try:

        while True:

            data = await ws.receive_json()

            event = data.get("event")
            if event == WSMessageEvent.MESSAGE_CREATED.value:

                conversation_id = data.get(
                    "conversation_id"
                )

                if not conversation_id:
                    continue

                if not await is_member(
                    db,
                    conversation_id,
                    user.id
                ):
                    continue

                content = data.get(
                    "message",
                    ""
                ).strip()

                if not content:
                    continue

                db_message = Message(
                    conversation_id=conversation_id,
                    sender_id=user.id,
                    message=content
                )

                db.add(db_message)

                await db.commit()
                await db.refresh(db_message)

                event_payload = {
                    "type": "chat",
                    "event": WSMessageEvent.MESSAGE_CREATED.value,
                    "message_id": db_message.id,
                    "conversation_id": conversation_id,
                    "sender_id": user.id,
                    "username": user.username,
                    "message": content,
                    "timestamp": (
                        db_message.timestamp
                        .astimezone(timezone.utc)
                        .isoformat()
                    )
                }

                await r.publish(
                    f"conversation:{conversation_id}",
                    json.dumps(event_payload)
                )
            
            elif event == WSMessageEvent.MESSAGE_EDITED.value:
                conversation_id = data.get(
                    "conversation_id"
                )

                if not conversation_id:
                    continue

                if not await is_member(
                    db,
                    conversation_id,
                    user.id
                ):
                    continue

                content = data.get(
                    "message",
                    ""
                ).strip()
                message_id = data.get(
                    "message_id",
                    None
                )
                if not content or not message_id:
                    continue
                stmt = select(Message).where(Message.id == message_id)
                result = await db.execute(stmt)
                message = result.scalar_one_or_none()

                if not message:
                    continue
                if message.sender_id != user.id:
                    continue
                if message.is_deleted_global:
                    continue

                message.message = content
                message.edited_at = datetime.now(timezone.utc)

                await db.commit()
                await db.refresh(message)

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

            elif event == WSMessageEvent.MESSAGE_DELETED_FOR_EVERYONE.value:

                conversation_id = data.get("conversation_id")
                message_id = data.get("message_id")

                if not conversation_id or not message_id:
                    continue

                if not await is_member(
                    db,
                    conversation_id,
                    user.id
                ):
                    continue

                stmt = select(Message).where(
                    Message.id == message_id,
                    Message.conversation_id == conversation_id
                )

                result = await db.execute(stmt)
                message = result.scalar_one_or_none()

                par_stmt_role = select(ConversationParticipants.role).where(
                    ConversationParticipants.user_id == user.id,
                    ConversationParticipants.conversation_id == conversation_id
                )

                par_role_result = await db.execute(par_stmt_role)
                participant_role = par_role_result.scalar_one_or_none()

                if not message:
                    continue

                print(participant_role == ParticipantRole.OWNER)
                print(participant_role)

                # Only sender can delete for everyone
                if (
                    message.sender_id != user.id
                    and participant_role not in [ParticipantRole.ADMIN, ParticipantRole.OWNER]
                ):
                    print(message.sender_id != user.id)
                    print(participant_role not in [ParticipantRole.ADMIN, ParticipantRole.OWNER])
                    continue

                message.is_deleted_global = True

                await db.commit()
                await db.refresh(message)

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
            
            elif event == WSMessageEvent.MESSAGE_DELETED_FOR_ME.value:

                conversation_id = data.get("conversation_id")
                message_id = data.get("message_id")

                if not conversation_id or not message_id:
                    continue

                if not await is_member(
                    db,
                    conversation_id,
                    user.id
                ):
                    continue

                stmt = select(Message).where(
                    Message.id == message_id,
                    Message.conversation_id == conversation_id
                )

                result = await db.execute(stmt)
                message = result.scalar_one_or_none()

                if not message:
                    continue

                stmt = select(MessageDeleteState).where(
                    MessageDeleteState.message_id == message_id,
                    MessageDeleteState.user_id == user.id
                )
            
                existing = (
                    await db.execute(stmt)
                ).scalar_one_or_none()
            
                if existing:
                    continue
                delete_state = MessageDeleteState(
                    message_id=message_id,
                    user_id=user.id
                )

                db.add(delete_state)

                await db.commit()
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
            elif event == "typing":

                conversation_id = data.get(
                    "conversation_id"
                )

                if not conversation_id:
                    continue

                if not await is_member(
                    db,
                    conversation_id,
                    user.id
                ):
                    continue

                typing_payload = {
                    "event": "typing",
                    "conversation_id": conversation_id,
                    "sender_id": user.id,
                    "username": user.username
                }

                await r.publish(
                    f"conversation:{conversation_id}",
                    json.dumps(typing_payload)
                )
            
            elif event == "conversation.joined":

                conversation_id = data["conversation_id"]

                other_user_id = await get_other_user(
                    conversation_id,
                    user.id,
                    db
                )

                if not other_user_id:
                    continue
                
                await watch_user(
                    watcher_id=user.id,
                    target_id=other_user_id
                )

                online = await is_online(other_user_id)

                await ws.send_json({
                    "event": "presence",
                    "user_id": other_user_id,
                    "online": bool(online)
                })
            elif event == "conversation.left":

                conversation_id = data["conversation_id"]
            
                other_user_id = await get_other_user(
                    conversation_id,
                    user.id,
                    db
                )
            
                if not other_user_id:
                    continue
                
                await unwatch_user(
                    watcher_id=user.id,
                    target_id=other_user_id
                )
            
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(
            user.id,
            ws
        )
        redis_task.cancel()