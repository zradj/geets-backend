import uuid
from datetime import datetime, UTC

from sqlalchemy import Column
from db.types import EncryptedString
from sqlmodel import SQLModel, Field

class Message(SQLModel, table=True):
    __tablename__ = 'messages'

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: uuid.UUID = Field(foreign_key='conversations.id')
    sender_id: uuid.UUID = Field(foreign_key='users.id')
    body: str = Field(sa_column=Column(EncryptedString(), nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    edited: bool = False
    deleted: bool = False
