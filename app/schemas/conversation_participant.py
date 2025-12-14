from enum import StrEnum

import uuid
from datetime import datetime, UTC

from sqlmodel import SQLModel, Field

class ParticipantRole(StrEnum):
    MEMBER = 'MEMBER'
    ADMIN = 'ADMIN'

class ConversationParticipant(SQLModel, table=True):
    __tablename__ = 'conversation_participants'

    conversation_id: uuid.UUID = Field(foreign_key='conversations.id', primary_key=True)
    user_id: uuid.UUID = Field(foreign_key='users.id', primary_key=True)
    role: ParticipantRole = Field(default=ParticipantRole.MEMBER)
    joined_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
