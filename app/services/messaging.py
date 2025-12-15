import json
import logging
import uuid

from sqlmodel import Session, select, desc
from schemas import ConversationParticipant, Message, MessageReceipt, ReceiptStatus, Conversation, dump_model
from datetime import datetime, UTC

logger = logging.getLogger(__name__)

class NotFoundError(Exception):
    pass

class BadRequestError(Exception):
    pass

class PermissionError(Exception):
    pass

class PermissionError(Exception):
    pass

def require_conversation(session: Session, conversation_id: uuid.UUID) -> Conversation:
    conv = session.get(Conversation, conversation_id)
    if not conv:
        raise NotFoundError('Conversation not found')
    return conv

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

    participants: list[uuid.UUID] = session.exec(
        select(ConversationParticipant.user_id)
        .where(ConversationParticipant.conversation_id == payload['conversation_id'])
    ).all()

    now = datetime.now(tz=UTC)

    for participant_user_id in participants:
        if participant_user_id == user_id:
            continue
        session.add(
            MessageReceipt(
                message_id=message.id,
                user_id=participant_user_id,
                status=ReceiptStatus.DELIVERED,
                delivered_at=now,
            )
        )
    session.commit()

    out = dump_model(message)
    out['status'] = 'DELIVERED'
    out['delivered_at'] = now.isoformat()
    return out


def edit_message(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    message = session.get(Message, payload['id'])
    if not message or message.deleted:
        raise NotFoundError('Message not found')

    if not is_participant(session, user_id, message.conversation_id):
        raise PermissionError('Not a participant')
    
    if message.sender_id != user_id:
        raise PermissionError('Only sender can edit the message')

    new_body = payload.get('new_body')
    if not new_body or not isinstance(new_body, str) or not new_body.strip():
        raise BadRequestError('new_body is required')

    message.body = payload['new_body']
    message.edited = True
    session.add(message)
    session.commit()
    session.refresh(message)
    return dump_model(message)


def delete_message(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    message_id = payload.get('message_id') or payload.get('id')
    if not message_id or not isinstance(message_id, uuid.UUID):
        raise BadRequestError('message_id is required and must be UUID')

    message = session.get(Message, message_id)
    if not message or message.deleted:
        raise NotFoundError('Message not found')

    if not is_participant(session, user_id, message.conversation_id):
        raise PermissionError('Not a participant')
    
    if message.sender_id != user_id:
        raise PermissionError('Only sender can delete the message')
    
    message.deleted = True
    session.add(message)
    session.commit()
    session.refresh(message)
    return dump_model(message)

def get_messages(session: Session, conversation_id: uuid.UUID) -> list[Message]:
    messages = session.exec(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.deleted == False)
        .order_by(desc(Message.created_at))
    ).all()
    return list(messages)


def mark_delivered(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    message_id: uuid.UUID = payload['message_id']

    message = session.get(Message, message_id)
    if not message or message.deleted:
        raise ValueError('Message not found')

    if not is_participant(session, user_id, message.conversation_id):
        raise PermissionError('Not a participant')

    if message.sender_id == user_id:
        raise PermissionError('Sender cannot deliver own message')

    receipt = session.get(MessageReceipt, (message_id, user_id))
    if not receipt:
        receipt = MessageReceipt(message_id=message_id, user_id=user_id, status=ReceiptStatus.SENT)
        session.add(receipt)

    if receipt.status in (ReceiptStatus.DELIVERED, ReceiptStatus.SEEN):
        return {
            'message_id': str(message_id),
            'conversation_id': str(message.conversation_id),
            'user_id': str(user_id),
            'status': receipt.status,
            'delivered_at': receipt.delivered_at.isoformat() if receipt.delivered_at else None,
            'seen_at': receipt.seen_at.isoformat() if receipt.seen_at else None,
        }

    receipt.status = ReceiptStatus.DELIVERED
    receipt.delivered_at = datetime.now(tz=UTC)
    session.add(receipt)
    session.commit()

    return {
        'message_id': str(message_id),
        'conversation_id': str(message.conversation_id),
        'user_id': str(user_id),
        'status': 'DELIVERED',
        'delivered_at': receipt.delivered_at.isoformat(),
    }

    
def mark_seen(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    conversation_id = payload.get('conversation_id')
    last_seen_message_id = payload.get('last_seen_message_id')

    if not conversation_id or not isinstance(conversation_id, uuid.UUID):
        raise BadRequestError('conversation_id is required and must be UUID')
    if not last_seen_message_id or not isinstance(last_seen_message_id, uuid.UUID):
        raise BadRequestError('last_seen_message_id is required and must be UUID')

    require_conversation(session, conversation_id)

    if not is_participant(session, user_id, conversation_id):
        raise PermissionError('Not a participant')

    last_msg = session.get(Message, last_seen_message_id)
    if not last_msg or last_msg.conversation_id != conversation_id:
        raise ValueError('Invalid last_seen_message_id')

    cutoff = last_msg.created_at
    now = datetime.now(tz=UTC)

    if last_msg.sender_id == user_id:
        prev_other = session.exec(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.deleted == False,
                Message.created_at <= cutoff,
                Message.sender_id != user_id,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        ).first()

        if not prev_other:
            return {
                'conversation_id': str(conversation_id),
                'user_id': str(user_id),
                'status': 'SEEN',
                'last_seen_message_id': str(last_seen_message_id),
                'seen_at': now.isoformat(),
                'updated_count': 0,
            }

        cutoff = prev_other.created_at

    message_ids = session.exec(
        select(Message.id)
        .where(
            Message.conversation_id == conversation_id,
            Message.deleted == False,
            Message.created_at <= cutoff,
            Message.sender_id != user_id,
        )
    ).all()

    updated = 0
    for mid in message_ids:
        receipt = session.get(MessageReceipt, (mid, user_id))
        if not receipt:
            receipt = MessageReceipt(message_id=mid, user_id=user_id, status=ReceiptStatus.SENT)
            session.add(receipt)

        if receipt.status != ReceiptStatus.SEEN:
            receipt.status = ReceiptStatus.SEEN
            receipt.seen_at = now
            if receipt.delivered_at is None:
                receipt.delivered_at = now
            updated += 1

        session.add(receipt)

    session.commit()

    return {
        'conversation_id': str(conversation_id),
        'user_id': str(user_id),
        'status': 'SEEN',
        'last_seen_message_id': str(last_seen_message_id),
        'seen_at': now.isoformat(),
        'updated_count': updated,
    }
