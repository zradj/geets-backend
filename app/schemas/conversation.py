import uuid

from sqlmodel import SQLModel, Field

class Conversation(SQLModel, table=True):
    __tablename__ = 'conversations'

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str | None
    is_group: bool = False
    deleted: bool = False
