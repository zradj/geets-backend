import json
import logging
import uuid

from sqlmodel import Session, select, desc

from schemas import ConversationParticipant, Message

logger = logging.getLogger(__name__)

class PermissionError(Exception):
    pass

def is_participant(session: Session, user_id: uuid.UUID, conversation_id: uuid.UUID):
    participant = session.exec(
        select(ConversationParticipant)
        .where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.user_id == user_id,
        )
    ).first()

    return bool(participant)

def create_message(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    if not is_participant(session, user_id, payload['conversation_id']):
        raise PermissionError('Not a participant')

    message = Message(
        conversation_id=payload['conversation_id'],
        sender_id=user_id,
        body=payload['body'],
    )
    session.add(message)
    session.commit()
    session.refresh(message)

    message_json = message.model_dump_json()
    return json.loads(message_json)


def edit_message(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    message = session.get(Message, payload['id'])
    if not message or message.deleted:
        raise ValueError('Message not found')

    if not is_participant(session, user_id, message.conversation_id):
        raise PermissionError('Not a participant')
    
    if message.sender_id != user_id:
        raise PermissionError('Only sender can edit the message')
    
    message.body = payload['new_body']
    message.edited = True
    session.add(message)
    session.commit()
    session.refresh(message)

    message_json = message.model_dump_json()
    return json.loads(message_json)


def delete_message(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    message = session.get(Message, payload['id'])
    if not message or message.deleted:
        raise ValueError('Message not found')

    if not is_participant(session, user_id, message.conversation_id):
        raise PermissionError('Not a participant')
    
    if message.sender_id != user_id:
        raise PermissionError('Only sender can delete the message')
    
    message.deleted = True
    session.add(message)
    session.commit()
    session.refresh(message)

    message_json = message.model_dump_json()
    return json.loads(message_json)

def get_messages(session: Session, conversation_id: uuid.UUID) -> list[Message]:
    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.deleted == False)
        .order_by(desc(Message.created_at))
    ).all()
    return list(messages)
