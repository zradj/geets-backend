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

async def ws_send_error(
    websocket: WebSocket,
    *,
    request_id: str | None,
    code: str,
    message: str,
    details: dict | None = None,
):
    payload = {
        "type": "error",
        "payload": {
            "request_id": request_id,
            "code": code,           # e.g. "not_participant", "not_found", "validation_error"
            "message": message,     # human readable
            "details": details or {},
        },
    }
    await websocket.send_json(payload)

async def ws_send_ack(websocket: WebSocket, *, request_id: str | None, result: dict | None = None):
    await websocket.send_json({
        "type": "ack",
        "payload": {"request_id": request_id, "result": result or {}},
    })


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
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await ws_send_error(websocket, request_id=None,
                                    code="bad_json", message="Invalid JSON")
                continue

            last_seen["t"] = time.time()

            try:
                ws_request = WSRequest.model_validate(data)
            except ValidationError as e:
                await ws_send_error(
                    websocket,
                    request_id=getattr(data, "request_id", None) if isinstance(data, dict) else None,
                    code="validation_error",
                    message="Invalid request format",
                    details={"errors": e.errors()},
                )
                continue

            request_id = getattr(ws_request, "request_id", None)

            if ws_request.type == "ping":
                await handle_ping(websocket, {})
                continue

            if ws_request.type not in EVENT_HANDLERS:
                await ws_send_error(websocket, request_id=request_id,
                                    code="unknown_type", message=f"Unknown type: {ws_request.type}")
                continue

            payload_schema, handler, routing_key_template = EVENT_HANDLERS[ws_request.type]

            try:
                payload = payload_schema.model_validate(ws_request.payload).model_dump()
            except ValidationError as e:
                await ws_send_error(websocket, request_id=request_id,
                                    code="validation_error", message="Invalid payload",
                                    details={"errors": e.errors()})
                continue

            try:
                result = await run_in_threadpool(handler, session, user_id, payload)
            except messaging_service.PermissionError as e:
                await ws_send_error(websocket, request_id=request_id,
                                    code="permission_denied", message=str(e))
                continue
            except messaging_service.NotFoundError as e:
                await ws_send_error(websocket, request_id=request_id,
                                    code="not_found", message=str(e))
                continue
            except messaging_service.BadRequestError as e:
                await ws_send_error(websocket, request_id=request_id,
                                    code="bad_request", message=str(e))
                continue
            except Exception:
                import logging
                logging.exception("WS handler crashed")
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Internal error")
                return

            event = {"type": ws_request.type, "payload": result}
            await websocket.app.state.message_publisher.publish(
                routing_key=routing_key_template.format(**result),
                payload=event,
            )

            await ws_send_ack(websocket, request_id=request_id, result={"ok": True})


    except ValidationError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        raise WebSocketException(code=status.WS_1003_UNSUPPORTED_DATA)
    finally:
        watchdog_task.cancel()
        manager.disconnect(user_id)
