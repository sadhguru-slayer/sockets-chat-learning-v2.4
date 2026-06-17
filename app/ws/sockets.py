# app/ws/sockets.py

from datetime import timezone,datetime
import json
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from app.services.presence_cache import PresenceCache
# Helpers
from app.services.chat import get_other_user
# Services
from app.services.chat import MessageService
from app.services.conversation_cache import ConversationCache
from app.models.conversations import Conversation, ConversationType

from app.ws.manager import manager
from app.ws.events import WSMessageEvent


from app.redis_client import r

from app.dependencies.auth import get_current_user_ws
from app.database import SessionLocal


router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(...)
):
    
    async with SessionLocal() as db:
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
    conversation_ids = await ConversationCache.get_user_conversations(
        user.id
    )

    for conversation_id in conversation_ids:
        await manager.join_conversation(
            conversation_id,
            user.id,
            ws)

    try:

        while True:

            data = await ws.receive_json()

            event = data.get("event")
            
            if event in [
                WSMessageEvent.MESSAGE_CREATED.value,
                WSMessageEvent.MESSAGE_EDITED.value,
                WSMessageEvent.MESSAGE_DELETED_FOR_EVERYONE.value,
                WSMessageEvent.MESSAGE_DELETED_FOR_ME.value
            ]:
                async with SessionLocal() as db:
                    service = MessageService(db)
                    if event == WSMessageEvent.MESSAGE_CREATED.value:
                        await service.MessageCreate(user,data)
                    elif event == WSMessageEvent.MESSAGE_EDITED.value:
                        await service.MessageEdited(user,data)
                    elif event == WSMessageEvent.MESSAGE_DELETED_FOR_EVERYONE.value:
                        await service.MessageDeletedForEveryOne(user,data)
                    elif event == WSMessageEvent.MESSAGE_DELETED_FOR_ME.value:
                        await service.MessageDeletedForMe(user,data)
            
            elif event == "typing":

                conversation_id = data.get(
                    "conversation_id"
                )

                if not conversation_id:
                    continue

                if not await ConversationCache.is_member(
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
                if not conversation_id:
                    continue

                # 1. register locally (Phase 3 addition)
                await manager.join_conversation(
                    conversation_id,
                    user.id,
                    ws
                )
                
                async with SessionLocal() as db:
                    conversation = await db.get(Conversation, conversation_id)
                    if conversation and conversation.type == ConversationType.PERSONAL:
                        other_user_id = await get_other_user(
                            conversation_id,
                            user.id,
                            db
                        )

                        if other_user_id:
                            conn = manager._find_connection(user.id, ws)
                            if conn:
                                conn.watched_users.add(other_user_id)
                                
                            await PresenceCache.watch(
                                watcher_id=user.id,
                                target_id=other_user_id
                            )
                        online = await PresenceCache.online(other_user_id)

                        await ws.send_json({
                            "event": "presence",
                            "user_id": other_user_id,
                            "online": bool(online)
                        })
            elif event == "conversation.left":

                conversation_id = data["conversation_id"]
                if not conversation_id:
                    continue

                # await manager.leave_conversation(
                #     conversation_id,
                #     user.id,
                #     ws
                # )

                async with SessionLocal() as db:
                    conversation = await db.get(Conversation, conversation_id)
                    if conversation and conversation.type == ConversationType.PERSONAL:
                        other_user_id = await get_other_user(
                            conversation_id,
                            user.id,
                            db
                        )
                    
                        if other_user_id:
                            conn = manager._find_connection(user.id, ws)
                            if conn:
                                conn.watched_users.discard(other_user_id)
                                
                            await PresenceCache.unwatch(
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