from typing import Annotated

from fastapi import Depends, HTTPException, Query, status
from fastapi.routing import APIRouter

from db.session import get_session
from schemas import User
from sqlmodel import Session, select

router = APIRouter(prefix='/users')

@router.get('/search')
async def search_user_by_username(
    username: Annotated[str, Query()],
    session: Session = Depends(get_session),
):
    user = session.exec(
        select(User).where(User.username == username)
    ).first()

    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'User not found')
    
    return user.model_dump(exclude={'password_hash'})
