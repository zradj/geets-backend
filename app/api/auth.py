from datetime import datetime, timedelta
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from db.session import get_session
from schemas.user import User
from utils.auth import get_password_hash, create_access_token, verify_password

router = APIRouter(prefix='/auth')

class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=64)


class SuccessfulAuthResponse(BaseModel):
    token: str
    token_type: str = 'bearer'


class FailedAuthResponse(BaseModel):
    status_code: int = status.HTTP_401_UNAUTHORIZED
    detail: str = 'Incorrect username or password'
    headers: dict[str, str] = {'WWW-Authenticate': 'Bearer'}


@router.post('/register')
async def register(data: LoginRequest, session: Session = Depends(get_session)) -> SuccessfulAuthResponse:
    existing = session.exec(select(User).where(User.username == data.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail='Username already registered')
    hashed_pwd = get_password_hash(data.password)
    user = User(username=data.username, password=hashed_pwd)
    session.add(user)
    session.commit()
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
