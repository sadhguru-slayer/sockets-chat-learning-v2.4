# app/ws/manager.py

from collections import defaultdict
from dataclasses import dataclass
from fastapi import WebSocket
from app.redis_client import r
import json


@dataclass
class Connection:
    ws: WebSocket
    username: str


class ConnectionManager:
    def __init__(self):
        self.users: dict[int, list[Connection]] = defaultdict(list)

    # ----------------------------
    # CONNECT
    # ----------------------------
    async def connect(self, user_id: int, username: str, ws: WebSocket):
        await ws.accept()

        first = user_id not in self.users

        self.users[user_id].append(Connection(ws=ws, username=username))

        if first:
            await r.sadd("online_users", user_id)
            await r.publish(
                "presence",
                json.dumps({
                    "event": "presence",
                    "user_id": user_id,
                    "online": True
                })
            )

    # ----------------------------
    # DISCONNECT
    # ----------------------------
    async def disconnect(self, user_id: int, ws: WebSocket):
        connections = self.users.get(user_id, [])

        self.users[user_id] = [
            c for c in connections if c.ws != ws
        ]

        if not self.users[user_id]:
            self.users.pop(user_id, None)
            await r.srem("online_users", user_id)
            await r.publish(
                "presence",
                json.dumps({
                    "event": "presence",
                    "user_id": user_id,
                    "online": False
                })
            )

    # ----------------------------
    # SEND TO USER (LOCAL ONLY)
    # ----------------------------
    async def send_to_user(self, user_id: int, payload: dict):
        connections = self.users.get(user_id)
        if not connections:
            return
        print("📨 send_to_user CALLED:", user_id)

        dead = []

        for conn in connections:
            try:
                await conn.ws.send_json(payload)
            except Exception:
                dead.append(conn)

        for conn in dead:
            try:
                self.users[user_id].remove(conn)
            except Exception:
                pass

        if user_id in self.users and not self.users[user_id]:
            self.users.pop(user_id, None)


manager = ConnectionManager()