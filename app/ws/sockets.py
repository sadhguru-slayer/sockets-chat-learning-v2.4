from datetime import datetime
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ws.manager import manager
from app.ws.events import WSMessageEvent

from app.models.messages import Message
from app.models.users import ConversationParticipants

from app.services.message_store import MessageStore

from app.redis_client import r

from app.dependencies.auth import get_current_user_ws
from app.dependencies.db import db_session


router = APIRouter()


@router.websocket('/ws/{conversation_id}')
async def conversation_socket(
    ws:WebSocket,
    conversation_id:int,
    db:db_session,
    token:str = Query(...)
):
    user = await get_current_user_ws(db,token)
    if not user:
        await ws.close(code=1008)
        return
    user_id = user.id
    username = user.username

    stmt  = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation_id,
        ConversationParticipants.user_id == user_id
    )

    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        await ws.close(code=1008)
        return
    
    connected = await manager.connect(conversation_id,user_id,username,ws)
    if not connected:
        return
    
    history = await MessageStore.get_history(str(conversation_id))

    for msg in history:
        await ws.send_json(json.loads(msg))
    try:
        while True:
            data = await ws.receive_json()
            event = data.get("event")

            if event == WSMessageEvent.MESSAGE_CREATED.value:
                content = data.get("message","").strip()
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
                    "type":"chat",
                    "event": WSMessageEvent.MESSAGE_CREATED.value,
                    "message_id": db_message.id,
                    "conversation_id": conversation_id,
                    "sender_id": user.id,
                    "username": user.username,
                    "message": content,
                    "timestamp": db_message.timestamp.isoformat()
                }

                await MessageStore.save_message(
                    str(conversation_id),
                    event_payload
                )

                await r.publish(
                    f"conversation:{conversation_id}",
                    json.dumps(event_payload)
                )
            elif event == "typing":
                typing_payload = {
                    "event":"typing",
                    "conversation_id":conversation_id,
                    "sender_id":user.id,
                    "username":user.username
                }
                await r.publish(
                    f"conversation:{conversation_id}",
                    json.dumps(typing_payload)
                )
    except WebSocketDisconnect:
        await manager.disconnect(
            str(conversation_id),
            user.id,
            ws
        )