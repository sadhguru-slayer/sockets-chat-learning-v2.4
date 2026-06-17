# app/redis/subscriber.py
import json
from app.redis_client import r
from app.redis.handlers import (
    handle_presence,
    handle_conversation
)

async def start_redis_listener():
    pubsub = r.pubsub()

    await pubsub.psubscribe("conversation:*", "presence*")

    async for message in pubsub.listen():

        if message["type"] != "pmessage":
            continue

        channel = message["channel"]
        if isinstance(channel, bytes):
            channel = channel.decode()

        raw = message["data"]
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        payload = json.loads(raw)

        # ONLY DISPATCHING NOW
        if channel.startswith("presence"):
            await handle_presence(payload)
            continue

        if channel.startswith("conversation:"):
            await handle_conversation(channel, payload)
            continue