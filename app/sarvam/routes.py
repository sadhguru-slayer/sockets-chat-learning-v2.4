from fastapi import FastAPI, HTTPException, Request,APIRouter
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
from sarvamai import (
    SarvamAI,
    ChatCompletionRequestMessage_User,
    ChatCompletionRequestMessage_Assistant
)
from .ws.sockets import router as ws_router
from .redis_client import redis_listener
from .database import init_db
import asyncio
import os
import re

chat_history = []

load_dotenv()

router = APIRouter()

API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise ValueError("API_KEY not found in environment variables")

client = SarvamAI(
    api_subscription_key=os.getenv("API_KEY"),
)


# -------------------
# API
# -------------------

class ChatRequest(BaseModel):
    message: str

@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        chat_history.append(
            ChatCompletionRequestMessage_User(
                content=request.message
            )
        )

        response = client.chat.completions(
            messages=chat_history,
            model="sarvam-m"
        )

        ai_message = response.choices[0].message.content

        think_match = re.search(
            r"<think>(.*?)</think>",
            ai_message,
            re.DOTALL
        )

        thinking = ""
        answer = ai_message

        if think_match:
            thinking = think_match.group(1).strip()

            answer = re.sub(
                r"<think>.*?</think>",
                "",
                ai_message,
                flags=re.DOTALL
            ).strip()

        chat_history.append(
            ChatCompletionRequestMessage_Assistant(
                content=answer
            )
        )

        return {
            "thinking": thinking,
            "response": answer
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
@router.post("/new-chat")
async def new_chat():
    global chat_history

    chat_history = []

    return {
        "message": "Chat cleared"
    }