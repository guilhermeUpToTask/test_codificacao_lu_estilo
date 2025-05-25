from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime


class ClientBase(SQLModel):
    name: str
    email: str
    cpf: str


class Client(ClientBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ClientCreate(ClientBase):
    pass


class ClientRead(ClientBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ClientUpdate(SQLModel):
    name: Optional[str] = None
    email: Optional[str] = None
    cpf: Optional[str] = None
