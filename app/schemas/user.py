import uuid

from db.types import EncryptedString 
from sqlmodel import SQLModel, Field, Column

class User(SQLModel, table=True):
    __tablename__ = 'users'
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str
    password_hash: str = Field(sa_column=Column(EncryptedString(), nullable=False))
    display_name: str | None = None
