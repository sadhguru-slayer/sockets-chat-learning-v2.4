from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.database import SessionLocal

from sqlalchemy import select
from dotenv import load_dotenv
from app.ws.manager import manager
from app.redis.subscriber import start_redis_listener

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

from app.services.conversation_cache import ConversationCache 
@app.on_event("startup")
async def startup():
    await init_db()
    
    # Use distributed lock to prevent multiple workers from syncing cache concurrently
    lock = await r.set("startup_sync_lock", "1", nx=True, ex=60)
    if lock:
        async with SessionLocal() as db:
            await ConversationCache.sync_all(db)
            
    asyncio.create_task(start_redis_listener())

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
