# app/services/presence.py

from app.redis_client import r

async def watch_user(watcher_id: int, target_id: int):
    await r.sadd(
        f"presence_watchers:{target_id}",
        watcher_id
    )

async def unwatch_user(watcher_id: int, target_id: int):
    await r.srem(
        f"presence_watchers:{target_id}",
        watcher_id
    )

async def is_online(user_id: int):
    return await r.sismember(
        "online_users",
        user_id
    )