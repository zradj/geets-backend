import uuid
from datetime import datetime, timedelta, UTC
from typing import Annotated

import jwt
from fastapi import Query

from config import TOKEN_SECRET_KEY, TOKEN_ALGORITHM, TOKEN_EXPIRE_MINS, pwd_ctx
from db.session import get_session
from schemas.user import User

def get_password_hash(plain: str) -> str:
    return pwd_ctx.hash(plain)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(tz=UTC) + timedelta(minutes=TOKEN_EXPIRE_MINS)
    to_encode.update({'exp': expire})
    return jwt.encode(to_encode, TOKEN_SECRET_KEY, TOKEN_ALGORITHM)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def verify_token(token: str) -> bool:
    try:
        decoded_data = jwt.decode(token, TOKEN_SECRET_KEY, algorithms=[TOKEN_ALGORITHM])
    except jwt.InvalidTokenError:
        return False

    if datetime.fromtimestamp(decoded_data['exp'], tz=UTC) <= datetime.now(tz=UTC):
        return False
    
    return True

def decode_token(token: str) -> dict:
    return jwt.decode(token, TOKEN_SECRET_KEY, algorithms=[TOKEN_ALGORITHM])

def get_token_user_id(token: Annotated[str, Query()] = None) -> uuid.UUID | None:
    if token is None or not verify_token(token):
        return None

    token_data = decode_token(token)
    return uuid.UUID(token_data['sub'])
