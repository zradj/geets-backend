import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    sender_id: uuid.UUID
    body: str
    created_at: datetime
    edited: bool
    deleted: bool
