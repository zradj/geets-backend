import json
import logging
import uuid

from sqlmodel import Session, select, desc

from schemas import ConversationParticipant, Message, MessageReceipt, ReceiptStatus
from datetime import datetime, UTC

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

    participants = session.exec(
        select(ConversationParticipant.user_id)
        .where(ConversationParticipant.conversation_id == message.conversation_id)
    ).all()

    for (participant_user_id,) in participants:
        if participant_user_id == user_id:
            continue
        session.add(MessageReceipt(
            message_id=message.id,
            user_id=participant_user_id,
            status=ReceiptStatus.SENT,
        ))

    session.commit()

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


def mark_delivered(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    message_id: uuid.UUID = payload["message_id"]

    message = session.get(Message, message_id)
    if not message or message.deleted:
        raise ValueError("Message not found")

    if not is_participant(session, user_id, message.conversation_id):
        raise PermissionError("Not a participant")

    if message.sender_id == user_id:
        raise PermissionError("Sender cannot deliver own message")

    receipt = session.get(MessageReceipt, (message_id, user_id))
    if not receipt:
        receipt = MessageReceipt(message_id=message_id, user_id=user_id, status=ReceiptStatus.SENT)
        session.add(receipt)

    if receipt.status in (ReceiptStatus.DELIVERED, ReceiptStatus.SEEN):
        return {
            "message_id": str(message_id),
            "conversation_id": str(message.conversation_id),
            "user_id": str(user_id),
            "status": receipt.status,
            "delivered_at": receipt.delivered_at.isoformat() if receipt.delivered_at else None,
            "seen_at": receipt.seen_at.isoformat() if receipt.seen_at else None,
        }

    receipt.status = ReceiptStatus.DELIVERED
    receipt.delivered_at = datetime.now(tz=UTC)
    session.add(receipt)
    session.commit()

    return {
        "message_id": str(message_id),
        "conversation_id": str(message.conversation_id),
        "user_id": str(user_id),
        "status": "DELIVERED",
        "delivered_at": receipt.delivered_at.isoformat(),
    }

    
def mark_seen(session: Session, user_id: uuid.UUID, payload: dict) -> dict:
    conversation_id: uuid.UUID = payload["conversation_id"]
    last_seen_message_id: uuid.UUID = payload["last_seen_message_id"]

    if not is_participant(session, user_id, conversation_id):
        raise PermissionError("Not a participant")

    last_msg = session.get(Message, last_seen_message_id)
    if not last_msg or last_msg.conversation_id != conversation_id:
        raise ValueError("Invalid last_seen_message_id")

    cutoff = last_msg.created_at
    now = datetime.now(tz=UTC)

    message_ids = session.exec(
        select(Message.id)
        .where(
            Message.conversation_id == conversation_id,
            Message.deleted == False,
            Message.created_at <= cutoff,
        )
    ).all()

    updated = 0
    for (mid,) in message_ids:
        msg = session.get(Message, mid)
        if msg and msg.sender_id == user_id:
            continue

        receipt = session.get(MessageReceipt, (mid, user_id))
        if not receipt:
            continue
        if receipt.status == ReceiptStatus.SEEN:
            continue

        receipt.status = ReceiptStatus.SEEN
        receipt.seen_at = now
        if receipt.delivered_at is None:
            receipt.delivered_at = now

        session.add(receipt)
        updated += 1

    session.commit()

    return {
        "conversation_id": str(conversation_id),
        "user_id": str(user_id),
        "status": "SEEN",
        "last_seen_message_id": str(last_seen_message_id),
        "seen_at": now.isoformat(),
        "updated_count": updated,
    }
