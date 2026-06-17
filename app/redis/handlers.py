# app/redis/handlers.py
import json
from app.redis_client import r
from app.services.conversation_cache import ConversationCache
from app.services.presence_cache import PresenceCache
from app.ws.manager import manager


async def handle_presence(payload: dict):
    target_user_id = payload["user_id"]

    watchers = await PresenceCache.watchers(target_user_id)

    event_payload = {
        "event": payload["event"],
        "user_id": target_user_id,
        "online": payload["online"]
    }

    for watcher in watchers:
        watcher_id = int(watcher)
        await manager.send_to_user(watcher_id, event_payload)


async def handle_conversation(channel: str, payload: dict):

    conversation_id = int(channel.split(":")[1])

    # 🧠 IMPORTANT: no Redis membership fan-out here
    # ONLY local routing
    user_ids = manager.get_local_members(conversation_id)
        
    for uid in user_ids:
        await manager.send_to_user(uid, payload)