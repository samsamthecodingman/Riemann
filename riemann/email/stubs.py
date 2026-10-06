"""Placeholder connectors: deterministic fake messages tagged with their account_id.

No network and no credentials. Real auth goes in __init__/a connect step: resolve
account.credential_ref ("env:..." / "file:...") there, never in config.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from riemann.email.base import Message, MessageSummary
from riemann.email.config import AccountConfig

_EPOCH = datetime(2026, 1, 1, tzinfo=timezone.utc)
_STUB_COUNT = 50


class _StubConnector:
    provider = ""

    def __init__(self, account: AccountConfig) -> None:
        # TODO(auth): resolve account.credential_ref here when real providers land.
        self.account_id = account.id
        self.label = account.label

    def _message(self, n: int) -> Message:
        return Message(
            id=f"{self.provider}-{n}",
            account_id=self.account_id,
            sender=f"sender{n}@example.com",
            subject=f"[{self.provider}] placeholder message {n}",
            date=_EPOCH + timedelta(days=n),
            snippet=f"Placeholder snippet {n} for {self.account_id}",
            body=f"Placeholder body {n} for {self.account_id} ({self.provider}).",
        )

    async def list_messages(self, limit: int = 20, query: str | None = None) -> list[MessageSummary]:
        msgs = [self._message(n) for n in range(1, _STUB_COUNT + 1)]
        if query:
            q = query.lower()
            msgs = [m for m in msgs if q in m.subject.lower() or q in m.snippet.lower()]
        return [MessageSummary(**m.model_dump(exclude={"body"})) for m in msgs[: max(limit, 0)]]

    async def get_message(self, message_id: str) -> Message:
        prefix, _, num = message_id.partition("-")
        if prefix != self.provider or not num.isdigit() or not 1 <= int(num) <= _STUB_COUNT:
            raise KeyError(f"no message {message_id!r} in account {self.account_id!r}")
        return self._message(int(num))


class GmailConnector(_StubConnector):
    provider = "gmail"


class ImapConnector(_StubConnector):
    provider = "imap"
