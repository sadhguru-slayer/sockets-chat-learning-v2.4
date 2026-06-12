# app/ws/manager.py

from collections import defaultdict
from fastapi import WebSocket
from typing import Dict
from dataclasses import dataclass
from app.ws.events import WSMessageEvent
from app.redis_client import r

@dataclass
class Connection:
    ws: WebSocket
    username: str




class ConnectionManager:
    def __init__(self):
        # room_id (int) -> user_id -> list[Connection]
        self.rooms: dict[int, dict[int, list[Connection]]] = defaultdict(dict)

    # ----------------------------
    # CONNECT
    # ----------------------------
    async def connect(self, room_id: int, user_id: int, username: str, ws: WebSocket):
        await ws.accept()

        room = self.rooms[room_id]

        if user_id not in room:
            room[user_id] = []

        room[user_id].append(Connection(ws=ws, username=username))

        # ✅ Redis: mark user online
        await r.sadd(f"conversation:{room_id}:online", user_id)

        await self.send_online_users(room_id)
        return True

    # ----------------------------
    # DISCONNECT
    # ----------------------------
    async def disconnect(self, room_id: int, user_id: int, ws: WebSocket):
        room = self.rooms.get(room_id)
        if not room:
            return

        connections = room.get(user_id, [])
        room[user_id] = [c for c in connections if c.ws != ws]

        if not room[user_id]:
            room.pop(user_id, None)

        if not room:
            self.rooms.pop(room_id, None)

        # ❗ if no more connections for user -> mark offline in Redis
        still_online = await r.sismember(f"conversation:{room_id}:online", user_id)

        if still_online:
            # check if user has ANY active connection left
            if user_id not in room:
                await r.srem(f"conversation:{room_id}:online", user_id)

        await self.send_online_users(room_id)

    # ----------------------------
    # SEND ONE USER
    # ----------------------------
    async def send_personal(self, ws: WebSocket, payload: dict):
        await ws.send_json(payload)

    # ----------------------------
    # BROADCAST
    # ----------------------------
    async def broadcast(self, room_id: int, payload: dict):
        room = self.rooms.get(room_id)
        if not room:
            return

        dead = []

        for user_id, conn_list in room.items():
            for conn in conn_list:
                try:
                    await conn.ws.send_json(payload)
                except Exception:
                    dead.append((user_id, conn))

        for user_id, conn in dead:
            try:
                room[user_id].remove(conn)
                if not room[user_id]:
                    room.pop(user_id, None)
            except Exception:
                pass

    # ----------------------------
    # ONLINE USERS (Redis SOURCE OF TRUTH)
    # ----------------------------
    async def send_online_users(self, room_id: int):
        room = self.rooms.get(room_id, {})

        # ✅ Redis is authoritative
        online_ids = await r.smembers(f"conversation:{room_id}:online")
        online_ids = {int(uid) for uid in online_ids}

        users = [
            {
                "id": uid,
                "username": conn_list[0].username
            }
            for uid, conn_list in room.items()
            if uid in online_ids
        ]

        payload = {
            "event": WSMessageEvent.ONLINE_USERS,
            "users": users
        }
        print(payload)

        await self.broadcast(room_id, payload)

manager = ConnectionManager()