import json
import uuid
from datetime import datetime, UTC
from typing import Annotated

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    Query,
    Depends,
    status,
)
from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, select

from .connection import ConnectionManager
from db.session import get_session
from schemas import Message, Conversation
from utils.auth import verify_token, decode_token

router = APIRouter()
manager = ConnectionManager()

class WSMessage(BaseModel):
    conversation_id: uuid.UUID
    body: str = Field(max_length=1000)


@router.websocket('/ws')
async def websocket_endpoint(
    websocket: WebSocket,
    token: Annotated[str, Query()] = None,
    session: Session = Depends(get_session)
):
    if token is None or not verify_token(token):
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason='Invalid token')

    token_data = decode_token(token)
    user_id = uuid.UUID(token_data['sub'])

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            ws_message = WSMessage.model_validate_json(data)

            conversation = session.exec(select(Conversation).where(Conversation.id == ws_message.conversation_id)).first()
            if not conversation:
                raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason='Conversation does not exist')

            message = Message(
                conversation_id=ws_message.conversation_id,
                sender_id=user_id,
                body=data['body'],
                created_at=datetime.now(tz=UTC)
            )
            session.add(message)
            session.commit()

            message_dict = message.model_dump()

            await websocket.app.state.publisher.publish(
                routing_key=f'create.{user_id}.{ws_message.conversation_id}',
                payload=message_dict,
            )

            await websocket.send_json(message_dict)
    except ValidationError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)
    finally:
        manager.disconnect(websocket)
