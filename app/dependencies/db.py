from app.database import get_db
from fastapi import Depends
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession

db_session = Annotated[AsyncSession,Depends(get_db)]