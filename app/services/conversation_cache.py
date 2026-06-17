# app/services/conversation_cache.py
from sqlalchemy import select
from app.models.users import ConversationParticipants
from app.redis_client import r
from app.redis.keys import RedisKeys


class ConversationCache:

    # -------------------------
    # Conversation -> Users
    # -------------------------
    @classmethod
    async def add_member(cls, conversation_id: int, user_id: int):
        await r.sadd(
            RedisKeys.conversation_members(conversation_id),
            user_id
        )

        # User -> Conversations (dual index)
        await r.sadd(
            RedisKeys.user_conversations(user_id),
            conversation_id
        )

    @classmethod
    async def remove_member(cls, conversation_id: int, user_id: int):
        await r.srem(
            RedisKeys.conversation_members(conversation_id),
            user_id
        )

        # Remove reverse mapping
        await r.srem(
            RedisKeys.user_conversations(user_id),
            conversation_id
        )

    @classmethod
    async def get_members(cls, conversation_id: int):
        members = await r.smembers(
            RedisKeys.conversation_members(conversation_id)
        )
        return [int(m) for m in members]

    # -------------------------
    # User -> Conversations
    # -------------------------
    @classmethod
    async def get_user_conversations(cls, user_id: int):
        conversation_ids = await r.smembers(
            RedisKeys.user_conversations(user_id)
        )
        return [int(cid) for cid in conversation_ids]

    @classmethod
    async def is_member(cls, conversation_id: int, user_id: int):
        return await r.sismember(
            RedisKeys.conversation_members(conversation_id),
            user_id
        )

    # -------------------------
    # Sync single conversation
    # -------------------------
    @classmethod
    async def sync_conversation(cls, conversation_id: int, db):
        stmt = select(
            ConversationParticipants.user_id
        ).where(
            ConversationParticipants.conversation_id == conversation_id
        )

        result = await db.execute(stmt)
        user_ids = result.scalars().all()

        conv_key = RedisKeys.conversation_members(conversation_id)

        async with r.pipeline() as pipe:
            pipe.delete(conv_key)
            if user_ids:
                pipe.sadd(conv_key, *user_ids)
                for user_id in user_ids:
                    pipe.sadd(
                        RedisKeys.user_conversations(user_id),
                        conversation_id
                    )
            await pipe.execute()

    # -------------------------
    # Sync all conversations
    # -------------------------
    @classmethod
    async def sync_all(cls, db):
        stmt = select(
            ConversationParticipants.conversation_id,
            ConversationParticipants.user_id
        )
        result = await db.execute(stmt)
        rows = result.all()

        from collections import defaultdict
        conv_map = defaultdict(list)
        user_map = defaultdict(list)

        for row in rows:
            conv_map[row.conversation_id].append(row.user_id)
            user_map[row.user_id].append(row.conversation_id)

        async with r.pipeline() as pipe:
            for conv_id, users in conv_map.items():
                conv_key = RedisKeys.conversation_members(conv_id)
                pipe.delete(conv_key)
                pipe.sadd(conv_key, *users)

            for user_id, convs in user_map.items():
                user_key = RedisKeys.user_conversations(user_id)
                pipe.delete(user_key)
                pipe.sadd(user_key, *convs)

            if rows:
                await pipe.execute()