from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
from app.ws.manager import manager

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

app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(ws_router)


async def redis_listener():
    pubsub = r.pubsub()

    await pubsub.psubscribe("conversation:*")

    async for message in pubsub.listen():

        if message["type"] != "pmessage":
            continue

        raw = message["data"]

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        payload = json.loads(raw)

        channel = message["channel"]

        if isinstance(channel, bytes):
            channel = channel.decode()

        conversation_id = channel.split(":")[1]

        await manager.broadcast(
            conversation_id,
            payload
        )