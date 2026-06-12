from passlib.context import CryptContext
from fastapi import HTTPException,Depends
from app.utils.jwt_auth import ALGORITHM,SECRET_KEY, verify_access_token
from jose import jwt, JWTError, ExpiredSignatureError
from app.models.users import User
from sqlalchemy import select
from fastapi.security import OAuth2PasswordBearer

pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)

def hash_password(password:str)->str:
    return pwd_context.hash(password)

def verify_password(password:str, hashed:str) ->bool:
    return pwd_context.verify(password,hashed)


async def get_current_user(db, token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")

        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(
        select(User).where(User.id == user_id)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user

async def get_current_user_ws(
    db,
    token: str
):

    payload = verify_access_token(token)

    if not payload:
        return None
    
    user_id = payload.get("sub")

    stmt = select(User).where(User.id == user_id)

    result = await db.execute(stmt)

    return result.scalar_one_or_none()