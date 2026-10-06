"""ConnectorRouter: one connector per configured account, looked up by account id."""

from __future__ import annotations

from pathlib import Path

from riemann.email.base import EmailConnector, Message, MessageSummary
from riemann.email.config import AccountConfig, EmailConfig, load_config
from riemann.email.gmail import GmailConnector
from riemann.email.stubs import ImapConnector

PROVIDERS: dict[str, type] = {"gmail": GmailConnector, "imap": ImapConnector}


class ConnectorRouter:
    def __init__(self, config: EmailConfig, providers: dict[str, type] | None = None) -> None:
        # Construction is lazy: connectors must not touch the network or credential files here.
        registry = providers or PROVIDERS
        self._accounts = {a.id: a for a in config.accounts}
        self._connectors: dict[str, EmailConnector] = {a.id: registry[a.provider](a) for a in config.accounts}

    @classmethod
    def from_file(cls, path: Path | str | None = None) -> ConnectorRouter:
        return cls(load_config(path))

    def accounts(self) -> list[AccountConfig]:
        return list(self._accounts.values())

    def get(self, account_id: str) -> EmailConnector:
        try:
            return self._connectors[account_id]
        except KeyError:
            known = ", ".join(self._connectors) or "none"
            raise KeyError(f"unknown email account {account_id!r} (configured: {known})") from None

    async def list_messages(self, account_id: str, limit: int = 20, query: str | None = None) -> list[MessageSummary]:
        return await self.get(account_id).list_messages(limit=limit, query=query)

    async def get_message(self, account_id: str, message_id: str) -> Message:
        return await self.get(account_id).get_message(message_id)
