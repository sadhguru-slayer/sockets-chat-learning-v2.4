from jose import jwt, JWTError
from datetime import datetime, timedelta

SECRET_KEY = "super-secret-key-change-this"
ALGORITHM = "HS256"

ACCESS_EXP_MIN = 15
REFRESH_EXP_DAYS = 7


def create_access_token(user):
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role.value,
        "type": "access",
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_EXP_MIN)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user):
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "exp": datetime.utcnow() + timedelta(days=REFRESH_EXP_DAYS)
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def verify_access_token(token: str):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    return payload


def verify_refresh_token(token: str):
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        return None
    return payload