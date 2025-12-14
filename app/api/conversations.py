import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field

from db.session import get_session
from schemas import Conversation, ConversationParticipant
from sqlmodel import Session, select
from utils.auth import get_token_user_id_http

router = APIRouter(prefix='/conversations')

class CreateConversationRequest(BaseModel):
    title: str = Field(max_length=100)

@router.post('/create')
async def create_conversation(
    data: CreateConversationRequest,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> Conversation:
    conversation = Conversation(title=data.title)
    conversation_participant = ConversationParticipant(
        conversation_id=conversation.id,
        user_id=user_id
    )
    session.add(conversation)
    session.add(conversation_participant)
    session.commit()
    session.refresh(conversation)

    return conversation

@router.get('')
async def get_conversations(
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> list[Conversation]:
    conversations = session.exec(
        select(ConversationParticipant.conversation_id.label('id'), Conversation.title, Conversation.is_group)
        .where(ConversationParticipant.user_id == user_id)
        .join(Conversation, Conversation.id == ConversationParticipant.conversation_id)
    ).fetchall()

    return list(conversations)
