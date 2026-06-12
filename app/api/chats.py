from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.conversations import Conversation
from app.models.users import ConversationParticipants,User, ParticipantRole
from app.models.messages import Message

from app.dependencies.db import db_session
from app.dependencies.auth import get_current_user, oauth2_scheme
from app.schemas.chat import JoinGroupSchema, CreateGroupSchema,AddMember
from app.schemas.user import ConversationParticipantResponse
from app.ws.manager import manager
from app.models.conversations import ConversationType
from app.redis_client import r
import json


router = APIRouter(prefix="/chat", tags=["chat"])

@router.post('/groups')
async def create_group(
    payload:CreateGroupSchema,
    db:db_session,
    token:str = Depends(oauth2_scheme)
):
    token_user = await get_current_user(db,token)
    if not token_user:
        raise HTTPException(status_code=401,detail="Invalid token")
    conversation = Conversation(
        type = ConversationType.GROUP,
        title = payload.title
    )
    db.add(conversation)
    await db.flush()

    creator = ConversationParticipants(
        conversation_id = conversation.id,
        user_id = token_user.id,
        role=ParticipantRole.OWNER
    )
    db.add(creator)

    db.add(
        Message(
            conversation_id=int(conversation.id),
            sender_id=token_user.id,
            type="system",
            message=f"{token_user.username} joined group"
        )
    )

    for user_id in payload.participants:
        if user_id == token_user.id:
            continue

        user_exist = await db.get(User,user_id)

        if not user_exist:
            continue

        db.add(
            ConversationParticipants(
                conversation_id = conversation.id,
                user_id=user_id,
                role=ParticipantRole.MEMBER
            )
        )

        if conversation.type == ConversationType.GROUP:
            db.add(Message(
                conversation_id = int(conversation.id),
                sender_id=0,
                type="system",
                message=f"{user_exist.username} joined group"

            ))
    
    await db.commit()
    return {
        "message":"Group created",
        "conversation_id":conversation.id
    }

@router.post('/groups/join')
async def join_group(
    payload:JoinGroupSchema,
    db:db_session,
    token:str=Depends(oauth2_scheme)
):
    token_user = await get_current_user(db,token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    conversation = await db.get(Conversation,payload.conversation_id)
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Group not found")
    is_user_joined = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation.id,
        ConversationParticipants.user_id == token_user.id,
    )

    result = await db.execute(is_user_joined)
    already = result.scalar_one_or_none()
    # print("Is joined:",already)
    if already is not None:
        return {"message":"User already joined"}
    
    db.add(ConversationParticipants(
        conversation_id=conversation.id,
        user_id = token_user.id,
        role=ParticipantRole.MEMBER
    ))
    if conversation.type == ConversationType.GROUP:
        msg = {
            "type": "system",
            "event": "join",
            "user": token_user.username,
            "message": f"{token_user.username} joined group"
        }

        db.add(Message(
                        conversation_id=int(conversation.id),
                        sender_id=0,
                        type="system",
                        message=f"{token_user.username} joined group"
                    ))
        await r.publish(
            f"group:{conversation.id}",
            json.dumps(msg)
        )
    await db.commit()
    return {"message":"Joined group"}

@router.post("/groups/add-members")
async def add_members(
    db:db_session,
    payload:AddMember,
    token:str = Depends(oauth2_scheme),
):
    token_user = await get_current_user(db, token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    stmt_conv = select(Conversation).where(
        Conversation.id == payload.group_id
    )
    conv_result = await db.execute(stmt_conv)
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404,detail="Group not found")
    
    is_group = conversation.type == ConversationType.GROUP
    if not is_group:
        raise HTTPException(status_code=401,detail="It's not a group, so can't add members")
    
    members = payload.participants
    if not members:
        raise HTTPException(status_code=500,detail="Participants cannnot be empty")
    
    stmt = select(ConversationParticipants).where(
    ConversationParticipants.conversation_id == payload.group_id,
    ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(stmt)
    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(403, "Not a member of this group")

    if participant.role not in (
        ParticipantRole.OWNER,
        ParticipantRole.ADMIN
    ):
        raise HTTPException(
            403,
            "Only admins and owners can add members"
        )
    message = []

    stmt_existing_members = select(
    ConversationParticipants.user_id
    ).where(
        ConversationParticipants.conversation_id == conversation.id
    )

    result = await db.execute(stmt_existing_members)

    existing_members_id = set(result.scalars().all())
    for user_id in members:
        if user_id == token_user.id:
            message.append(f"You cannot add yourself, ignoring adding {token_user.username}")
            continue

        user_exist = await db.get(User,user_id)

        if not user_exist:
            message.append(f"User with id {user_id} does not exist")
            continue

        if user_id in existing_members_id:
            message.append(f"User id: {user_id} is already a member")
            continue

        db.add(
            ConversationParticipants(
                conversation_id = conversation.id,
                user_id=user_id,
                role=ParticipantRole.MEMBER
            )
        )

        existing_members_id.add(user_id)

        db.add(Message(
            conversation_id = int(conversation.id),
            sender_id=0,
            type="system",
            message=f"{user_exist.username} joined group"
        ))

    await db.commit()

    return {
        "status":"OK",
        "message":message
    }


@router.get("/groups/{group_id}")
async def get_group(
    group_id: int,
    db: db_session,
    token: str = Depends(oauth2_scheme)
):
    token_user = await get_current_user(db, token)

    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == group_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(stmt)
    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(403, "Not a member")

    return {
        "group_id": group_id,
        "role": participant.role.value
    }


@router.delete("/groups/{group_id}/leave")
async def leave_group(
    group_id: int,
    db: db_session,
    token: str = Depends(oauth2_scheme)
):

    token_user = await get_current_user(db, token)
    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    stmt_conv = select(Conversation).where(
        Conversation.id == group_id
    )

    conv_result = await db.execute(stmt_conv)
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    is_group = conversation.type == ConversationType.GROUP
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == group_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(stmt)

    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(404, "Not in group")

    await db.delete(participant)

    msg = {
        "type": "system",
        "event": "leave",
        "user": token_user.username,
        "message": f"{token_user.username} left group"
    }
    if is_group:
        db.add(Message(
                    conversation_id=int(group_id),
                    sender_id=token_user.id,
                    type="system",
                    message=f"{token_user.username} left group"
                ))
        await r.publish(
        f"group:{group_id}",
        json.dumps(msg)
        )
    await db.commit()

    return {
        "message": "Left group"
    }

@router.get('/groups/{group_id}/fetch-members',response_model = list[ConversationParticipantResponse])
async def fetch_group_members(
    db:db_session,
    group_id:int,
    token:str = Depends(oauth2_scheme)
):
    user = await get_current_user(db,token)
    conv_stmt = select(Conversation).where(
        Conversation.id == group_id
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Group not found")
    participants_stmt = (
        select(ConversationParticipants)
        .options(selectinload(ConversationParticipants.user))
        .where(
            ConversationParticipants.conversation_id == group_id
        ) 
    )
    participants_result = await db.execute(participants_stmt)
    participants = participants_result.scalars().all()
    

    return [
            ConversationParticipantResponse(
            id=p.user.id,
            username=p.user.username,
            role=p.role.value,  # MEMBER / ADMIN / OWNER
            status="offline"
        )
        for p in participants
    ]


@router.get("/groups")
async def get_user_groups(
    db: db_session,
    token: str = Depends(oauth2_scheme)
):

    token_user = await get_current_user(db, token)

    if not token_user:
        raise HTTPException(status_code=401, detail="Invalid token")

    stmt = (
        select(Conversation,
               ConversationParticipants.role
        )
        .join(ConversationParticipants)
        .where(
            ConversationParticipants.user_id == token_user.id,
            Conversation.type == ConversationType.GROUP
        )
    )

    result = await db.execute(stmt)

    groups = result.all()
    return [
        {
            "id": g.id,
            "title": g.title,
            "type": g.type.value,
            "role": role.value
        }
        for g, role in groups
    ]
