import os
import secrets
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from passlib.context import CryptContext

from db.session import get_session
from schemas.user import User

SECRET_KEY = os.getenv('JWT_SECRET') or secrets.token_urlsafe(32)
ALGORITHM = 'HS256'
TOKEN_EXPIRE_MINS = 60

router = APIRouter(prefix='/auth')
pwd_ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=100)


class SuccessfulAuthResponse(BaseModel):
    token: str
    token_type: str = 'bearer'


class FailedAuthResponse(BaseModel):
    status_code: int = status.HTTP_401_UNAUTHORIZED
    detail: str = 'Incorrect username or password'
    headers: dict[str, str] = {'WWW-Authenticate': 'Bearer'}


def get_password_hash(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=TOKEN_EXPIRE_MINS)
    to_encode.update({'exp': expire})
    return jwt.encode(to_encode, SECRET_KEY, ALGORITHM)


@router.post('/register')
async def register(data: LoginRequest, session: Session = Depends(get_session)) -> SuccessfulAuthResponse:
    existing = session.exec(select(User).where(User.username == data.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail='Username already registered')
    hashed_pwd = get_password_hash(data.password)
    user = User(username=data.username, password=hashed_pwd)
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token({'sub': str(user.id), 'username': user.username})
    return SuccessfulAuthResponse(token=token)


@router.post(
    '/login',
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            'model': FailedAuthResponse,
            'description': 'Incorrect Username or Password',
        },
    },
)
async def login(data: LoginRequest, session: Session = Depends(get_session)) -> SuccessfulAuthResponse:
    user = session.exec(select(User).where(User.username == data.username)).first()
    if not user or not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Incorrect username or password',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    token = create_access_token({'sub': str(user.id), 'username': user.username})
    return SuccessfulAuthResponse(token=token)
