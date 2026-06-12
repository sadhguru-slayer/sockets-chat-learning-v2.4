# app/ws/events.py
import enum


class WSMessageEvent(str, enum.Enum):
    MESSAGE_CREATED = "message.created"
    MESSAGE_EDITED = "message.edited"
    MESSAGE_DELETED_FOR_ME = "message.deleted_for_me"
    MESSAGE_DELETED_FOR_EVERYONE = "message.deleted_for_everyone"
    ONLINE_USERS = "online_users"
    ERROR = "error"