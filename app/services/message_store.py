# app/services/message_store.py

import json
from app.redis_client import r


class MessageStore:

    @staticmethod
    async def save_message(room_id: str, message: dict):
        key = f"room:{room_id}:history"

        await r.rpush(key, json.dumps(message))
        await r.ltrim(key, -50, -1)

    @staticmethod
    async def get_history(room_id: str):
        key = f"room:{room_id}:history"
        return await r.lrange(key, -50, -1)