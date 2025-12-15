import asyncio
import json
import logging
import time
import uuid
from typing import Annotated
from sqlmodel import Session

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocketState

import services.messaging as messaging_service
from db.session import get_session
from schemas.ws import (
    WSRequest,
    WSMessageCreate,
    WSMessageEdit,
    WSMessageDelete,
    WSMessageDelivered,
    WSMessageSeen,
    handle_ping,
)
from utils.auth import get_token_user_id_ws
from .connection import manager

logger = logging.getLogger(__name__)
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
        if time.time() - last_seen['t'] > PING_IDLE_TIMEOUT_S:
            await safe_close(websocket, 1001, 'Heartbeat timeout')
            return


async def safe_close(ws: WebSocket, code: int, reason: str = ''):
    try:
        if ws.client_state == WebSocketState.CONNECTED:
            await ws.close(code=code, reason=reason)
    except Exception:
        pass


async def ws_send_error(websocket: WebSocket, code: str, message: str, details: dict | None = None):
    try:
        await websocket.send_json(
            {
                'type': 'error',
                'payload': {
                    'code': code,
                    'message': message,
                    'details': details or {},
                },
            }
        )
    except Exception:
        pass


def build_routing_key(template: str, payload: dict, result: dict) -> str | None:
    ctx = {}
    if isinstance(payload, dict):
        ctx.update(payload)
    if isinstance(result, dict):
        ctx.update(result)

    cid = ctx.get('conversation_id')
    if cid is None:
        return None

    ctx['conversation_id'] = str(cid)
    return template.format(**ctx)


def call_handler_in_own_session(handler, user_id: uuid.UUID, payload: dict) -> dict:
    gen = get_session()
    session = next(gen)
    try:
        return handler(session, user_id, payload)
    finally:
        gen.close()


@router.websocket('')
async def ws_messages_endpoint(
    websocket: WebSocket,
    user_id: Annotated[uuid.UUID, Depends(get_token_user_id_ws)],
    session: Session = Depends(get_session),
):
    await manager.connect(user_id, websocket)

    last_seen = {'t': time.time()}
    watchdog_task = asyncio.create_task(heartbeat_watchdog(websocket, last_seen))

    try:
        while True:
            try:
                data_text = await websocket.receive_text()
            except WebSocketDisconnect:
                break

            last_seen['t'] = time.time()

            try:
                raw = json.loads(data_text)
                ws_request = WSRequest.model_validate(raw)
            except (json.JSONDecodeError, ValidationError) as e:
                await ws_send_error(websocket, 'bad_request', 'Invalid JSON/schema', {'err': str(e)})
                continue

            if ws_request.type == 'ping':
                await handle_ping(websocket, ws_request.payload or {})
                continue

            if ws_request.type not in EVENT_HANDLERS:
                await ws_send_error(websocket, 'bad_request', f'Unknown type: {ws_request.type}')
                continue

            payload_schema, handler, routing_key_template = EVENT_HANDLERS[ws_request.type]

            try:
                payload = payload_schema.model_validate(ws_request.payload).model_dump()
            except ValidationError as e:
                await ws_send_error(websocket, 'bad_request', 'Invalid payload', {'err': str(e)})
                continue

            try:
                result = await run_in_threadpool(handler, session, user_id, payload)
            except messaging_service.PermissionError as e:
                await ws_send_error(websocket, 'forbidden', str(e))
                continue
            except messaging_service.BadRequestError as e:
                await ws_send_error(websocket, 'bad_request', str(e))
                continue
            except messaging_service.NotFoundError as e:
                await ws_send_error(websocket, 'not_found', str(e))
                continue
            except ValueError as e:
                await ws_send_error(websocket, 'not_found', str(e))
                continue
            except Exception:
                logger.exception('handler crash')
                await ws_send_error(websocket, 'server_error', 'Internal error in handler')
                continue

            event = {'type': ws_request.type, 'payload': result}

            try:
                await websocket.send_json(event)
            except Exception:
                break

            try:
                rk = build_routing_key(routing_key_template, payload, result)
                if rk is None:
                    await ws_send_error(websocket, 'bad_event', 'No conversation_id for routing')
                    continue

                await websocket.app.state.message_publisher.publish(
                    routing_key=rk,
                    payload=event,
                )
            except Exception:
                logger.exception('publish crash')
                await ws_send_error(websocket, 'broker_error', 'Failed to publish event')
                continue

    except Exception:
        logger.exception('ws endpoint crashed')
        await safe_close(websocket, 1011, 'Server error')
    finally:
        watchdog_task.cancel()
        manager.disconnect(user_id)
        await safe_close(websocket, 1000, 'bye')
