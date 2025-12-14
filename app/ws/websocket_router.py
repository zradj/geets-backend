import json
import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    Depends,
    status,
)
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, select

from .connection import manager
from db.session import get_session
from schemas import Message, ConversationParticipant
from utils.auth import get_token_user_id

router = APIRouter(prefix='/ws')


class WSMessage(BaseModel):
    conversation_id: uuid.UUID
    body: str = Field(max_length=10000)


@router.websocket('/messages')
async def ws_messages_endpoint(
    websocket: WebSocket,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id)],
    session: Session = Depends(get_session)
):
    if user_id is None:
        raise WebSocketException(status.WS_1008_POLICY_VIOLATION, reason='Invalid token')

    await manager.connect(user_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            ws_message = WSMessage.model_validate(data)

            participant = session.exec(
                select(ConversationParticipant)
                .where(
                    ConversationParticipant.conversation_id == ws_message.conversation_id,
                    ConversationParticipant.user_id == user_id,
                )
            ).first()

            if not participant:
                raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

            message = Message(
                conversation_id=ws_message.conversation_id,
                sender_id=user_id,
                body=ws_message.body,
            )
            session.add(message)
            session.commit()

            message_dict = message.model_dump()

            await websocket.app.state.publisher.publish(
                routing_key=f'create.{ws_message.conversation_id}',
                payload=message_dict,
            )
    except ValidationError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)
    finally:
        manager.disconnect(user_id)
