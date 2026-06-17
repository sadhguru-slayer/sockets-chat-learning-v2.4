#app/ws/manager.py
from collections import defaultdict
from dataclasses import dataclass, field
from fastapi import WebSocket
from app.redis_client import r
from app.redis.keys import RedisKeys

import json
import uuid
import logging

logger = logging.getLogger("connection_manager")
logger.setLevel(logging.DEBUG)

@dataclass
class Connection:
    ws: WebSocket
    username: str
    connection_id: str
    joined_conversations: set[int] = field(default_factory=set)
    watched_users: set[int] = field(default_factory=set)

class ConnectionManager:
    def __init__(self):
        self.users: dict[int, list[Connection]] = defaultdict(list)
        self.local_conversations: dict[
            int,
            set[int]
        ] = defaultdict(set)

    # ----------------------------
    # CONNECT
    # ----------------------------
    async def connect(
        self,
        user_id: int,
        username: str,
        ws: WebSocket
    ) -> str:

        await ws.accept()

        connection_id = str(uuid.uuid4())

        conn = Connection(
            ws=ws,
            username=username,
            connection_id=connection_id
        )

        self.users[user_id].append(conn)

        redis_key = RedisKeys.user_connections(user_id)
        # redis_key = f"user:{user_id}:connections"

        await r.sadd(
            redis_key,
            connection_id
        )

        count = await r.scard(redis_key)

        # first connection globally
        if count == 1:

            await r.sadd(
                "online_users",
                user_id
            )

            await r.publish(
                "presence",
                json.dumps({
                    "event": "presence",
                    "user_id": user_id,
                    "online": True
                })
            )

        return connection_id
    # ----------------------------
    # ----- CONVERSATIONS --------
    # ----------------------------
    def _find_connection(
        self,
        user_id: int,
        ws: WebSocket
    ) -> Connection | None:
        for conn in self.users.get(user_id, []):
            if conn.ws == ws:
                return conn

        return None
    # ------- JOIN CONV ----------
    async def join_conversation(
        self,
        conversation_id: int,
        user_id: int,
        ws: WebSocket
    ):
        conn = self._find_connection(
            user_id,
            ws
        )
        if not conn:
            return

        conn.joined_conversations.add(
            conversation_id
        )

        self.local_conversations[
            conversation_id
        ].add(user_id)

    # ------ LEAVE CONV ---------
    async def leave_conversation(
        self,
        conversation_id: int,
        user_id: int,
        ws: WebSocket
    ):
        conn = self._find_connection(
            user_id,
            ws
        )

        if not conn:
            return

        conn.joined_conversations.discard(
            conversation_id
        )

        self.local_conversations[
            conversation_id
        ].discard(user_id)

        if not self.local_conversations[
            conversation_id
        ]:
            self.local_conversations.pop(
                conversation_id,
                None
            )
    def get_local_members(
        self,
        conversation_id: int
    ) -> set[int]:

        return self.local_conversations.get(
            conversation_id,
            set()
        )

    # ----------------------------
    # DISCONNECT
    # ----------------------------
    async def disconnect(
        self,
        user_id: int,
        ws: WebSocket
    ):
        connections = self.users.get(user_id, [])

        disconnected = None
        remaining = []

        # 1. split active vs disconnected connection
        for conn in connections:
            if conn.ws == ws:
                disconnected = conn
            else:
                remaining.append(conn)

        self.users[user_id] = remaining

        if not self.users[user_id]:
            self.users.pop(user_id, None)

        # If we cannot find the connection, just exit safely
        if not disconnected:
            return

        # 2. cleanup conversation state
        for conv_id in list(disconnected.joined_conversations):
            self.local_conversations[conv_id].discard(user_id)

            if not self.local_conversations[conv_id]:
                self.local_conversations.pop(conv_id, None)

        disconnected.joined_conversations.clear()

        # 3. Redis cleanup
        redis_key = RedisKeys.user_connections(user_id)

        try:
            # remove this connection id
            await r.srem(redis_key, disconnected.connection_id)

            # check remaining connections
            remaining_count = await r.scard(redis_key)

            # 4. mark offline if no connections remain
            if remaining_count == 0:
                await r.delete(redis_key)

                # IMPORTANT FIX: remove from global online set
                await r.srem("online_users", user_id)

                await r.publish(
                    "presence",
                    json.dumps({
                        "event": "presence",
                        "user_id": user_id,
                        "online": False
                    })
                )

        except Exception as e:
            logger.exception(
                f"Error during disconnect cleanup for user {user_id}: {e}"
            )
            
        # 5. Cleanup presence watchers
        from app.services.presence_cache import PresenceCache
        for target_id in list(disconnected.watched_users):
            try:
                await PresenceCache.unwatch(watcher_id=user_id, target_id=target_id)
            except Exception as e:
                logger.error(f"Failed to unwatch {target_id} for {user_id}: {e}")
        disconnected.watched_users.clear()
    
    # ----------------------------
    # SEND TO USER (LOCAL ONLY)
    # ----------------------------
    async def send_to_user(
        self,
        user_id: int,
        payload: dict
    ):
        connections = self.users.get(user_id)

        if not connections:
            return

        dead = []

        for conn in connections:
            try:
                await conn.ws.send_json(payload)
            except Exception:
                dead.append(conn)

        for conn in dead:
            try:
                self.users[user_id].remove(conn)

                await r.srem(
                    f"user:{user_id}:connections",
                    conn.connection_id
                )

            except Exception:
                pass

        if (
            user_id in self.users
            and not self.users[user_id]
        ):
            self.users.pop(user_id, None)


manager = ConnectionManager()