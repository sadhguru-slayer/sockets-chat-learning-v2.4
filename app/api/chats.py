from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.models.conversations import Conversation
from app.models.users import ConversationParticipants,User, ParticipantRole
from app.models.messages import Message, MessageType
from datetime import timezone
from app.dependencies.db import db_session
from app.dependencies.auth import get_current_user, oauth2_scheme
from app.schemas.chat import JoinGroupSchema, CreateGroupSchema,AddMember, RemoveMember
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
            type=MessageType.SYSTEM,
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
                type=MessageType.SYSTEM,
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
            "type": "SYSTEM",
            "event": "join",
            "user": token_user.username,
            "message": f"{token_user.username} joined group"
        }

        db.add(Message(
                        conversation_id=int(conversation.id),
                        sender_id=0,
                        type=MessageType.SYSTEM,
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
        message_text = f"{token_user.username} added {user_exist.username}"
        msg = {
            "type": "system",
            "event": "join",
            "message": message_text
        }

        db.add(Message(
            conversation_id = int(conversation.id),
            sender_id=0,
            type=MessageType.SYSTEM,
            message=f"{token_user.username} added {user_exist.username}"
        ))
        await r.publish(
            f"conversation:{conversation.id}",
            json.dumps(msg)
            )

    await db.commit()

    return {
        "status":"OK",
        "message":message
    }

@router.delete("/groups/remove-member")
async def remove_member(
    db:db_session,
    payload:RemoveMember,
    token:str = Depends(oauth2_scheme)
):
    current_user = await get_current_user(db,token)

    stmt_conv = select(Conversation).where(
        Conversation.id == payload.group_id
    )
    conv_result = await db.execute(stmt_conv)
    conversation = conv_result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.type != ConversationType.GROUP:
        raise HTTPException(status_code=400,detail="The conversation is not group")

    stmt_is_admin = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation.id,
        ConversationParticipants.user_id == current_user.id
    )
    is_admin_result = await db.execute(stmt_is_admin)
    is_admin = is_admin_result.scalar_one_or_none()
    if not is_admin:
        raise HTTPException(status_code=403, detail="You are not part of this group")
    print(is_admin.role, is_admin.user_id,ParticipantRole.OWNER == is_admin.role)
    if is_admin.role not in [
        ParticipantRole.OWNER,
        ParticipantRole.ADMIN
    ]:
        raise HTTPException(status_code=403, detail="Only admins/owners are allowed to remove members")
    
    stmt_participant = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation.id,
        ConversationParticipants.user_id == payload.member_id
    )

    participant_result = await db.execute(stmt_participant)
    participant = participant_result.scalar_one_or_none()
    if not participant:
        raise HTTPException(status_code=404,detail="Member not found")
    stmt_user = select(User.username).where(User.id == payload.member_id)
    user_result = await db.execute(stmt_user)
    removed_user = user_result.scalar_one()

    await db.delete(participant)
    message_text = f"{current_user.username} removed {removed_user}"
    msg = {
        "type": "system",
        "event": "leave",
        "user": current_user.username,
        "message": message_text
    }
    
    db.add(Message(
                conversation_id=int(payload.group_id),
                sender_id=0,
                type=MessageType.SYSTEM,
                message=message_text
    ))
    await r.publish(
    f"conversation:{payload.group_id}",
    json.dumps(msg)
    )
    await db.commit()
    return {
        "message": message_text
    }


@router.get("/groups/get-participant-details")
async def get_participant_details(
    db: db_session,
    conversation_id: int = Query(...),
    participant_id: int = Query(...)
):
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation_id,
        ConversationParticipants.user_id == participant_id
    )

    result = await db.execute(stmt)
    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")

    return {
        "id": participant.user_id,
        "role": participant.role.value,
    }

@router.delete('/conversation/{conversation_id}/delete-conversation')
async def delete_group(
    db: db_session,
    conversation_id: int,
    token: str = Depends(oauth2_scheme)
):
    current_user = await get_current_user(db, token)

    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # check if user is OWNER
    stmt_owner = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation_id,
        ConversationParticipants.user_id == current_user.id
    )

    res = await db.execute(stmt_owner)
    participant = res.scalar_one_or_none()

    if not participant or participant.role != ParticipantRole.OWNER:
        raise HTTPException(
            status_code=403,
            detail="Only owner can delete conversation"
        )

    await db.delete(conversation)
    await db.commit()

    return {"message": "Conversation deleted successfully"}

from sqlalchemy import outerjoin
    
@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    db: db_session,
    token: str = Depends(oauth2_scheme)
):

    token_user = await get_current_user(db, token)
    
    stmt_conv = select(Conversation).where(
        Conversation.id == conversation_id
    )

    conv_result = await db.execute(stmt_conv)
    conversation = conv_result.scalar_one_or_none()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    
    stmt = select(ConversationParticipants).where(
        ConversationParticipants.conversation_id == conversation_id,
        ConversationParticipants.user_id == token_user.id
    )

    result = await db.execute(stmt)

    participant = result.scalar_one_or_none()

    if not participant:
        raise HTTPException(403, "Not in group")

    query = (
    select(Message, User)
    .outerjoin(User, User.id == Message.sender_id)
    .where(Message.conversation_id == conversation_id)
    .order_by(Message.timestamp.asc())
    .limit(100)
)

    results = await db.execute(query)

    return [
            {
                "id": m.id,
                "sender_id": m.sender_id,
                 "username": user.username if user else "System",
                "message":m.message,
                "timestamp": m.timestamp.astimezone(timezone.utc).isoformat() if m.timestamp else None,
                "type": m.type
            }
            for m, user in results.all()
        ]


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
                    type=MessageType.SYSTEM,
                    message=f"{token_user.username} left group"
                ))
        await r.publish(
        f"conversation:{group_id}",
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
