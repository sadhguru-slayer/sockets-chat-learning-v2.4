from pydantic import BaseModel, Field
from typing import List


class CreateGroupSchema(BaseModel):
    title: str
    participants: List[int] = Field(default_factory=list)



class JoinGroupSchema(BaseModel):
    conversation_id: int

class DMRequest(BaseModel):
    user_ids: List[int]

class AddMember(BaseModel):
    group_id: int
    participants: List[int] = Field(default_factory=list)

class RemoveMember(BaseModel):
    group_id:int
    member_id:int