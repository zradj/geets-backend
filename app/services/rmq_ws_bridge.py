import json
import logging
import uuid

import aio_pika
from sqlmodel import Session, select

from db.session import get_session
from schemas import ConversationParticipant
from ws.connection import manager

logger = logging.getLogger(__name__)


def _extract_conversation_id(payload: dict) -> uuid.UUID | None:
    cid = payload.get("conversation_id")
    if cid is None and isinstance(payload.get("message"), dict):
        cid = payload["message"].get("conversation_id")
    if cid is None:
        return None
    try:
        return cid if isinstance(cid, uuid.UUID) else uuid.UUID(str(cid))
    except Exception:
        return None


def _extract_actor_id(payload: dict) -> uuid.UUID | None:
    raw = payload.get("sender_id") or payload.get("user_id")
    if not raw:
        return None
    try:
        return raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
    except Exception:
        return None


async def rmq_ws_bridge(inc_message: aio_pika.IncomingMessage) -> None:
    try:
        data = json.loads(inc_message.body.decode())
        event_type = data.get("type")
        payload = data.get("payload")

        if not isinstance(event_type, str) or not isinstance(payload, dict):
            logger.warning("Bad RMQ message format: %r", data)
            return

        conversation_id = _extract_conversation_id(payload)
        if conversation_id is None:
            logger.warning("No conversation_id in payload for event=%s payload=%r", event_type, payload)
            return

        actor_id = _extract_actor_id(payload)

        session_gen = get_session()
        session: Session = next(session_gen)
        try:
            participant_ids: list[uuid.UUID] = session.exec(
                select(ConversationParticipant.user_id)
                .where(ConversationParticipant.conversation_id == conversation_id)
            ).all()
        finally:
            session.close()

        out = {"type": event_type, "payload": payload}

        for uid in participant_ids:
            # чтобы sender не получал дубль (он уже получил echo в ws endpoint)
            if actor_id is not None and uid == actor_id:
                continue
            await manager.send_to_user(out, uid)

    except Exception:
        logger.exception("Failed to bridge RMQ to WS")
