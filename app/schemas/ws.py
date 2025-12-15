import uuid

from sqlmodel import SQLModel, Field
from datetime import datetime, UTC

class WSRequest(SQLModel, table=False):
    type: str
    payload: dict


class WSMessageCreate(SQLModel, table=False):
    conversation_id: uuid.UUID
    body: str = Field(max_length=10000)


class WSMessageEdit(SQLModel, table=False):
    id: uuid.UUID
    new_body: str = Field(max_length=10000)


class WSMessageDelete(SQLModel, table=False):
    id: uuid.UUID


async def handle_ping(ws, payload):
    await ws.send_json({
        "type": "pong",
        "payload": {
            "ts": payload.get("ts"),
            "server_ts": datetime.now(tz=UTC).isoformat(),
        },
    })
class WSMessageDelivered(SQLModel, table=False):
    message_id: uuid.UUID

class WSMessageSeen(SQLModel, table=False):
    conversation_id: uuid.UUID
    last_seen_message_id: uuid.UUID
