from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import select
from dotenv import load_dotenv
from app.ws.manager import manager
from app.dependencies.db import db_session

import json

from sarvamai import (
    SarvamAI,
    ChatCompletionRequestMessage_User,
    ChatCompletionRequestMessage_Assistant
)
from .ws.sockets import router as ws_router
from .redis_client import r
from .database import init_db
import asyncio

chat_history = []

load_dotenv()

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

@app.on_event("startup")
async def startup():
    await init_db()
    asyncio.create_task(redis_listener())

# -------------------
# HTML Pages
# -------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )
@app.get("/chat", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="chat.html"
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html"
    )


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html"
    )


@app.get("/aichat", response_class=HTMLResponse)
async def ai_chat_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="aichat.html",
    )

from app.api.auth import router as auth_router
from app.api.chats import router as chats_router
from app.api.presence import router as presence_router

app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(ws_router)
app.include_router(presence_router)

# --------------------------
# ----- REDIS LISTENER -----
# --------------------------

from app.models.users import ConversationParticipants
from app.models.conversations import Conversation

async def get_conversation_members_and_type(conversation_id, db):
    conversation = await db.get(Conversation, conversation_id)

    if conversation is None:
        return [], None  # or raise an exception

    stmt = select(ConversationParticipants.user_id).where(
        ConversationParticipants.conversation_id == conversation_id
    )

    result = await db.execute(stmt)
    user_ids = result.scalars().all()
    return user_ids, conversation.type

from app.database import SessionLocal

async def redis_listener():
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

        # =========================
        # 1. PRESENCE STREAM
        # =========================
        print("Channel",channel)
        if channel.startswith("presence"):
        
            target_user_id = payload["user_id"]

            watchers = await r.smembers(
                f"presence_watchers:{target_user_id}"
            )

            event_payload = {
                "event": payload["event"],
                "user_id": target_user_id,
                "online":payload["online"]
            }

            for watcher in watchers:
            
                watcher_id = int(watcher)

                await r.publish(
                    f"user:{watcher_id}",
                    json.dumps(event_payload)
                )

            continue

        # =========================
        # 2. CONVERSATION STREAM
        # =========================
        if channel.startswith("conversation:"):
            conversation_id = channel.split(":")[1]

            async with SessionLocal() as db:
                users, conversation_type = await get_conversation_members_and_type(
                    conversation_id,
                    db
                )

            for uid in users:
                await r.publish(
                    f"user:{uid}",
                    json.dumps(payload)
                )
                



