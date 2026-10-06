"""Shared connector interface and the models it returns. Every object carries account_id."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class MessageSummary(BaseModel):
    id: str
    account_id: str
    sender: str
    subject: str
    date: datetime
    snippet: str


class Message(MessageSummary):
    body: str


@runtime_checkable
class EmailConnector(Protocol):
    account_id: str
    label: str

    async def list_messages(self, limit: int = 20, query: str | None = None) -> list[MessageSummary]: ...

    async def get_message(self, message_id: str) -> Message: ...
