from pydantic import BaseModel

class UserResponse(BaseModel):
    id: int
    username: str

class ConversationParticipantResponse(BaseModel):
    id: int
    username: str
    role:str
    status:str

    model_config = {
        "from_attributes": True
    }