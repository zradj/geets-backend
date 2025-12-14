import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field

from db.session import get_session
from schemas import Conversation, ConversationParticipant, Message, User
from schemas.conversation_participant import ParticipantRole
from services.messaging import get_messages
from sqlmodel import Session, select
from utils.auth import get_token_user_id_http

router = APIRouter(prefix='/groups')

class CreateGroupRequest(BaseModel):
    title: str = Field(max_length=100)
    participant_ids: list[uuid.UUID] = Field(max_length=100)


class ParticipantInformation(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    role: ParticipantRole

@router.get('')
async def get_groups(
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> list[Conversation]:
    groups = session.exec(
        select(ConversationParticipant.conversation_id.label('id'), Conversation.title, Conversation.is_group)
        .where(ConversationParticipant.user_id == user_id, Conversation.is_group == True, Conversation.deleted == False)
        .join(Conversation, Conversation.id == ConversationParticipant.conversation_id)
    ).all()

    return list(groups)

@router.post('/create')
async def create_group(
    data: CreateGroupRequest,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> Conversation:
    added_participants = session.exec(select(User.id).where(User.id.in_(data.participant_ids))).all()
    if len(added_participants) != len(data.participant_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Adding non-existing user(s)')

    group = Conversation(title=data.title, is_group=True)
    participants = []

    creating_participant = ConversationParticipant(
        conversation_id=group.id,
        user_id=user_id,
        role=ParticipantRole.ADMIN,
    )
    participants.append(creating_participant)

    for new_participant_id in data.participant_ids:
        conversation_participant = ConversationParticipant(
            conversation_id=group.id,
            user_id=new_participant_id,
        )
        participants.append(conversation_participant)

    session.add(group)
    session.add_all(participants)
    session.commit()
    session.refresh(group)

    return group

@router.delete('/{group_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> None:
    conversation = session.get(Conversation, group_id)
    conversation_participant = session.get(ConversationParticipant, (group_id, user_id))
    if not conversation or conversation.deleted or not conversation_participant:
        return
    
    if not conversation.is_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Requested to delete a non-group')

    if conversation_participant.role != ParticipantRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Only admin can delete a group')
    
    conversation.deleted = True
    session.add(conversation)
    session.commit()

    return

@router.get('/{group_id}/messages')
async def get_group_messages(
    group_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> list[Message]:
    group_participant = session.get(ConversationParticipant, (group_id, user_id))
    if not group_participant:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail='You have no access to the group')
    return get_messages(session, group_id)


@router.get('/{group_id}/participants')
async def get_group_participants(
    group_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> list[ParticipantInformation]:
    group = session.get(Conversation, group_id)
    requesting_participant = session.get(ConversationParticipant, (group_id, user_id))
    if not group or group.deleted or not requesting_participant:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Could not find group')

    participants = session.exec(
        select(User.id, User.username, User.display_name, ConversationParticipant.role)
        .join(ConversationParticipant)
        .where(ConversationParticipant.conversation_id == group_id)
    ).all()

    return participants


@router.put('/{group_id}/participants/{participant_id}', status_code=status.HTTP_204_NO_CONTENT)
async def add_group_participant(
    group_id: uuid.UUID,
    participant_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> None:
    group = session.get(Conversation, group_id)
    adder = session.get(ConversationParticipant, (group_id, user_id))
    to_add = session.get(User, participant_id)
    if not group or group.deleted or not adder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, 'Could not find group')
    
    if not group.is_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Can only add participants to a group')
    
    if not to_add:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Adding a non-existing user')
    
    added_participant = ConversationParticipant(
        conversation_id=group_id,
        user_id=participant_id
    )
    session.add(added_participant)
    session.commit()

    return None


@router.delete('/{group_id}/participants/{participant_id}', status_code=status.HTTP_204_NO_CONTENT)
async def remove_group_participant(
    group_id: uuid.UUID,
    participant_id: uuid.UUID,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_http)],
    session: Session = Depends(get_session),
) -> None:
    group = session.get(Conversation, group_id)
    remover = session.get(ConversationParticipant, (group_id, user_id))
    to_remove = session.get(ConversationParticipant, (group_id, participant_id))
    if not group or group.deleted or not to_remove or not remover:
        return
    
    if not group.is_group:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, 'Cannot leave from a regular conversation; delete it instead')
    
    if participant_id != user_id and remover.role != ParticipantRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Only admin can remove other members from a group')
    
    session.delete(to_remove)
    session.commit()
    return

