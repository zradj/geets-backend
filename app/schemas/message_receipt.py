import uuid
from enum import StrEnum
from datetime import datetime, UTC

from sqlmodel import SQLModel, Field


class ReceiptStatus(StrEnum):
    SENT = 'SENT'
    DELIVERED = 'DELIVERED'
    SEEN = 'SEEN'


class MessageReceipt(SQLModel, table=True):
    __tablename__ = 'message_receipts'  # type: ignore[assignment]

    message_id: uuid.UUID = Field(foreign_key='messages.id', primary_key=True)
    user_id: uuid.UUID = Field(foreign_key='users.id', primary_key=True)

    status: ReceiptStatus = Field(default=ReceiptStatus.SENT)
    delivered_at: datetime | None = None
    seen_at: datetime | None = None
