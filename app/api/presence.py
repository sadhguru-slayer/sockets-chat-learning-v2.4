from fastapi import APIRouter
from app.services.presence_cache import PresenceCache

router = APIRouter()


@router.get("/presence/{user_id}")
async def get_presence(user_id: int):
    return {
        "user_id": user_id,
        "online": user_id
    }