import json
import uuid
import asyncio
import time

from typing import Annotated

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    Depends,
    status,
)
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from sqlmodel import Session, select


import services.messaging as messaging_service
from .connection import manager
from db.session import get_session
from schemas.ws import WSRequest, WSMessageCreate, WSMessageEdit, WSMessageDelete, WSMessageDelivered, WSMessageSeen, handle_ping
from utils.auth import get_token_user_id_ws

router = APIRouter(prefix='/ws')

EVENT_HANDLERS = {
    'message.create': (WSMessageCreate, messaging_service.create_message, 'conversation.{conversation_id}.created'),
    'message.edit': (WSMessageEdit, messaging_service.edit_message, 'conversation.{conversation_id}.edited'),
    'message.delete': (WSMessageDelete, messaging_service.delete_message, 'conversation.{conversation_id}.deleted'),
    'message.seen': (WSMessageSeen, messaging_service.mark_seen, 'conversation.{conversation_id}.seen'),
    'message.delivered': (WSMessageDelivered, messaging_service.mark_delivered, 'conversation.{conversation_id}.delivered'),
}

PING_IDLE_TIMEOUT_S = 75
WATCHDOG_TICK_S = 5  

async def heartbeat_watchdog(websocket: WebSocket, last_seen: dict) -> None:
    while True:
        await asyncio.sleep(WATCHDOG_TICK_S)
        if time.time() - last_seen["t"] > PING_IDLE_TIMEOUT_S:
            # 1001 = going away / idle timeout
            await websocket.close(code=1001, reason="Heartbeat timeout")
            return

@router.websocket('')
async def ws_messages_endpoint(
    websocket: WebSocket,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_ws)],
    session: Session = Depends(get_session)
):
    await manager.connect(user_id, websocket)

    last_seen = {"t": time.time()}
    watchdog_task = asyncio.create_task(heartbeat_watchdog(websocket, last_seen))

    try:
        while True:
            data = await websocket.receive_json()
            last_seen["t"] = time.time()

            ws_request = WSRequest.model_validate(data)

            if ws_request.type == "ping":
                payload = (ws_request.payload or {})
                if hasattr(payload, "model_dump"):
                    payload = payload.model_dump()
                await handle_ping(websocket, payload if isinstance(payload, dict) else {})
                continue

            if ws_request.type not in EVENT_HANDLERS:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

            payload_schema, handler, routing_key_template = EVENT_HANDLERS[ws_request.type]
            payload = payload_schema.model_validate(ws_request.payload).model_dump()

            try:
                result = await run_in_threadpool(handler, session, user_id, payload)
            except messaging_service.PermissionError:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            except ValueError:
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return

            event = {
                'type': ws_request.type,
                'payload': result,
            }

            await websocket.app.state.message_publisher.publish(
                routing_key=routing_key_template.format(**result),
                payload=event,
            )

    except ValidationError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)
    finally:
        watchdog_task.cancel()
        manager.disconnect(user_id)
