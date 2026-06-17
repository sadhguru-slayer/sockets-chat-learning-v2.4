from app.redis_client import r
from app.redis.keys import RedisKeys


class PresenceCache:

    @staticmethod
    async def watch(watcher_id: int, target_id: int):
        await r.sadd(
            RedisKeys.presence_watchers(target_id),
            watcher_id
        )

    @staticmethod
    async def unwatch(watcher_id: int, target_id: int):
        await r.srem(
            RedisKeys.presence_watchers(target_id),
            watcher_id
        )
        print("unwatch:",watcher_id,target_id)

    @staticmethod
    async def online(user_id: int):
        return await r.sismember(
            RedisKeys.online_users(),
            user_id
        )

    @staticmethod
    async def watchers(target_id: int):
        return await r.smembers(
            RedisKeys.presence_watchers(target_id)
        )