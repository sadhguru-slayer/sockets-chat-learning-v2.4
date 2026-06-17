from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from app.dependencies.db import db_session
from app.models.users import User
from app.schemas.schemas import RegisterRequest, TokenResponse
from app.dependencies.auth import hash_password, verify_password, oauth2_scheme
from app.utils.jwt_auth import create_access_token, create_refresh_token, verify_refresh_token,verify_access_token
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
async def register(data: RegisterRequest, db: db_session):

    result = await db.execute(
        select(User).where(User.username == data.username)
    )

    if result.scalar():
        raise HTTPException(400, "User already exists")

    email_result = await db.execute(
        select(User).where(User.email == data.email)
    )

    if email_result.scalar():
        raise HTTPException(400, "Email already exists")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password)
    )

    db.add(user)
    await db.commit()

    return {"message": "registered"}
    

@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    db: db_session
):
    payload = verify_refresh_token(refresh_token)

    if not payload:
        raise HTTPException(
            401,
            "Invalid refresh token"
        )

    user_id = int(payload["sub"])

    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar()

    if not user:
        raise HTTPException(
            404,
            "User not found"
        )

    new_access = create_access_token(user)

    return {
        "access_token": new_access
    }
    

from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated

@router.post("/login", response_model=TokenResponse)
async def login(data: Annotated[OAuth2PasswordRequestForm,Depends()],db:db_session):
    result = await db.execute(
        select(User).where(User.username == data.username)
    )
    user = result.scalar()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Invalid credentials")
    access = create_access_token(user)
    refresh = create_refresh_token(user)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh
    )

from app.services.user_cache_service import UserCacheService

# @router.get("/me")
# async def get_me(
#     db: db_session,
#     token: str = Depends(oauth2_scheme)
# ):
#     # Get user ID from token
#     payload = verify_access_token(token)
#     user_id = payload.get("sub")

#     # Try cache first
#     cached_user = await UserCacheService.get(user_id)

#     if cached_user:
#         print("Cached User:",cached_user)
#         return {
#             "id": int(cached_user["id"]),
#             "username": cached_user["username"]
#         }

#     # Cache miss -> fetch from DB
#     user = await get_current_user(db, token)

#     # Save to cache
#     await UserCacheService.save(user)

#     return {
#         "id": user.id,
#         "username": user.username
#     }

async def get_payload_user(
    token: str = Depends(oauth2_scheme)
):
    payload = verify_access_token(token)

    if not payload:
        raise HTTPException(
            401,
            "Invalid token"
        )

    return payload

@router.get("/me")
async def get_me(
    current_user=Depends(get_payload_user)
):
    return {
        "id": int(current_user["sub"]),
        "username": current_user["username"],
        "role": current_user["role"]
    }



@router.get("/users")
async def get_users(db: db_session):
    result = await db.execute(
        select(User)
    )

    users = result.scalars().all()

    return users