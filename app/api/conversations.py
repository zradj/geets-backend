import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel

from db.session import get_session
from schemas import Conversation, ConversationParticipant, Message, User
from schemas.conversation_participant import ParticipantRole
from services.messaging import get_messages
from sqlmodel import Session, select
from utils.auth import get_token_user_id_http

router = APIRouter(prefix='/conversations')

class CreateConversationRequest(BaseModel):
    other_id: uuid.UUID


class ParticipantInformation(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    role: ParticipantRole


@router.post('/create')
async def create_conversation(
    data: CreateConversationRequest,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> Conversation:
    other = session.get(User, data.other_id)
    if not other:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Adding a non-existing user')

    conversation = Conversation()

    creating_participant = ConversationParticipant(
        conversation_id=conversation.id,
        user_id=user_id,
    )
    
    other_participant = ConversationParticipant(
        conversation_id=conversation.id,
        user_id=other.id,
    )

    session.add(conversation)
    session.add(creating_participant)
    session.add(other_participant)
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
        .where(ConversationParticipant.user_id == user_id, Conversation.is_group == False, Conversation.deleted == False)
        .join(Conversation, Conversation.id == ConversationParticipant.conversation_id)
    ).all()

    return list(conversations)


@router.get('/{conversation_id}/messages')
async def get_conversation_messages(
    conversation_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> list[Message]:
    conversation_participant = session.get(ConversationParticipant, (conversation_id, user_id))
    if not conversation_participant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail='You have no access to the conversation')
    return get_messages(session, conversation_id)


@router.delete('/{conversation_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> None:
    conversation = session.get(Conversation, conversation_id)
    conversation_participant = session.get(ConversationParticipant, (conversation_id, user_id))
    if not conversation or conversation.deleted or not conversation_participant:
        return
    
    if conversation.is_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Requested to delete a group')
    
    conversation.deleted = True
    session.add(conversation)
    session.commit()

    return
