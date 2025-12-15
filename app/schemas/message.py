import uuid
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from db.types import EncryptedString
from schemas.message_out import MessageOut
from schemas.message_receipt import ReceiptStatus

class Message(SQLModel, table=True):
    __tablename__ = 'messages'

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key="conversations.id", index=True)
    sender_id: uuid.UUID = Field(foreign_key="users.id", index=True)

    body: str = Field(sa_column=Column(EncryptedString, nullable=False))

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    edited: bool = Field(default=False)
    deleted: bool = Field(default=False)

def dump_model(m: Message) -> dict:
    return MessageOut.model_validate(m).model_dump(mode="json")