from app.models.users import ConversationParticipants
from sqlalchemy import select
async def get_other_user(
    conversation_id: int,
    current_user_id: int,
    db
):
    stmt = select(
        ConversationParticipants.user_id
    ).where(
        ConversationParticipants.conversation_id == conversation_id,
        ConversationParticipants.user_id != current_user_id
    )

    result = await db.execute(stmt)

    return result.scalar_one_or_none()