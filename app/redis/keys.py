# app/redis/keys.py
class RedisKeys:

    # -------------------------
    # User channels (pub/sub)
    # -------------------------
    @staticmethod
    def user_channel(user_id: int) -> str:
        return f"user:{user_id}"

    @staticmethod
    def user_connections(user_id: int) -> str:
        return f"user:{user_id}:connections"

    # -------------------------
    # Presence system
    # -------------------------
    @staticmethod
    def presence_watchers(user_id: int) -> str:
        return f"presence_watchers:{user_id}"

    @staticmethod
    def online_users() -> str:
        return "online_users"

    # -------------------------
    # Conversations
    # -------------------------
    @staticmethod
    def conversation_members(conversation_id: int) -> str:
        return f"conversation:{conversation_id}:members"

    @staticmethod
    def user_conversations(user_id: int) -> str:
        return f"user:{user_id}:conversations"