import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field

from db.session import get_session
from schemas import Conversation, ConversationParticipant, Message, User
from schemas.conversation_participant import ParticipantRole
from sqlmodel import Session, select, desc
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
        .where(ConversationParticipant.user_id == user_id, Conversation.deleted == False)
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
    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.deleted == False)
        .order_by(desc(Message.created_at))
    ).all()
    return list(messages)


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
    
    if conversation.is_group and conversation_participant.role != ParticipantRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Only admin can delete a group')
    
    conversation.deleted = True
    session.add(conversation)
    session.commit()

    return

@router.get('/{conversation_id}/participants')
async def get_group_participants(
    conversation_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> list[ParticipantInformation]:
    conversation = session.get(Conversation, conversation_id)
    requesting_participant = session.get(ConversationParticipant, (conversation_id, user_id))
    if not conversation or conversation.deleted or not requesting_participant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Could not find conversation')

    participants = session.exec(
        select(User.id, User.username, User.display_name, ConversationParticipant.role)
        .join(ConversationParticipant)
        .where(ConversationParticipant.conversation_id == conversation_id)
    ).all()

    return participants


@router.put('/{conversation_id}/participants/{participant_id}', status_code=status.HTTP_204_NO_CONTENT)
async def add_group_participant(
    conversation_id: uuid.UUID,
    participant_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> None:
    conversation = session.get(Conversation, conversation_id)
    adder = session.get(ConversationParticipant, (conversation_id, user_id))
    to_add = session.get(User, participant_id)
    if not conversation or conversation.deleted or not adder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Could not find conversation')
    
    if not conversation.is_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Can only add participants to a group')
    
    if not to_add:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Adding a non-existing user')
    
    added_participant = ConversationParticipant(
        conversation_id=conversation_id,
        user_id=participant_id
    )
    session.add(added_participant)
    session.commit()

    return None


@router.delete('/{conversation_id}/participants/{participant_id}', status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_participant(
    conversation_id: uuid.UUID,
    participant_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> None:
    conversation = session.get(Conversation, conversation_id)
    remover = session.get(ConversationParticipant, (conversation_id, user_id))
    to_remove = session.get(ConversationParticipant, (conversation_id, participant_id))
    if not conversation or conversation.deleted or not to_remove or not remover:
        return
    
    if not conversation.is_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Cannot leave from a regular conversation; delete it instead')
    
    if participant_id != user_id and remover.role != ParticipantRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Only admin can remove other members from a group')
    
    session.delete(to_remove)
    session.commit()
    return
