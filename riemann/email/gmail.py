"""Read-only Gmail connector (installed-app OAuth, gmail.readonly scope only).

The token is an authorized-user JSON file at resolve_ref(account.credential_ref), created by
`python -m riemann.email.authorize <account_id>`. The Google client is sync, so every API call
runs in asyncio.to_thread. The service is built lazily on first use.
"""

from __future__ import annotations

import asyncio
import base64
import html
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from riemann.email.base import Message, MessageSummary
from riemann.email.config import AccountConfig
from riemann.email.credentials import resolve_ref

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_METADATA_HEADERS = ["From", "Subject", "Date"]


class GmailAuthError(RuntimeError):
    """The account has no usable token; the user needs to run the authorize command."""


def authorize_hint(account_id: str) -> str:
    return f"run: uv run python -m riemann.email.authorize {account_id}"


def write_token(path: Path, token_json: str) -> None:
    """Write the token file with mode 0600, creating the parent dir with mode 0700."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token_json)
    os.chmod(path, 0o600)  # O_CREAT's mode is ignored when the file already exists


# --- pure parsing helpers ---------------------------------------------------------------


def parse_headers(payload: dict[str, Any]) -> dict[str, str]:
    """Header name (lowercased) -> value; the first occurrence wins."""
    out: dict[str, str] = {}
    for h in payload.get("headers") or []:
        out.setdefault(h.get("name", "").lower(), h.get("value", ""))
    return out


def parse_date(internal_date: str | int | None) -> datetime:
    """Gmail internalDate is ms since epoch; missing falls back to the epoch."""
    return datetime.fromtimestamp(int(internal_date or 0) / 1000, tz=timezone.utc)


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _find_part(payload: dict[str, Any], mime: str) -> str | None:
    """Depth-first search for the first non-empty part of the given mime type."""
    if payload.get("mimeType") == mime and (data := (payload.get("body") or {}).get("data")):
        return _decode(data)
    for part in payload.get("parts") or []:
        if (found := _find_part(part, mime)) is not None:
            return found
    return None


def _strip_tags(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def extract_body(payload: dict[str, Any]) -> str:
    """First text/plain part, else tag-stripped text/html, else ''."""
    if (plain := _find_part(payload, "text/plain")) is not None:
        return plain
    if (markup := _find_part(payload, "text/html")) is not None:
        return _strip_tags(markup)
    return ""


def summary_fields(raw: dict[str, Any]) -> dict[str, Any]:
    headers = parse_headers(raw.get("payload") or {})
    return {
        "id": raw["id"],
        "sender": headers.get("from", ""),
        "subject": headers.get("subject", ""),
        "date": parse_date(raw.get("internalDate")),
        "snippet": html.unescape(raw.get("snippet", "")),
    }


# --- connector --------------------------------------------------------------------------


class GmailConnector:
    provider = "gmail"

    def __init__(self, account: AccountConfig, service: Any | None = None) -> None:
        # `service` is a test seam; when None it is built lazily from the token file.
        self.account_id = account.id
        self.label = account.label
        self._credential_ref = account.credential_ref
        self._service = service

    def _load_credentials(self) -> Any:
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        path = resolve_ref(self._credential_ref)
        hint = authorize_hint(self.account_id)
        if not path.is_file():
            raise GmailAuthError(f"no Gmail token for account {self.account_id!r} at {path}; {hint}")
        creds = Credentials.from_authorized_user_file(str(path), SCOPES)
        if not creds.valid:
            if not (creds.expired and creds.refresh_token):
                raise GmailAuthError(f"Gmail token for account {self.account_id!r} is unusable; {hint}")
            try:
                creds.refresh(Request())
            except RefreshError as e:
                raise GmailAuthError(f"Gmail token for account {self.account_id!r} could not be refreshed ({e}); {hint}") from e
            write_token(path, creds.to_json())
        return creds

    def _get_service(self) -> Any:
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build("gmail", "v1", credentials=self._load_credentials(), cache_discovery=False)
        return self._service

    def _list_sync(self, limit: int, query: str | None) -> list[MessageSummary]:
        messages = self._get_service().users().messages()
        listing = messages.list(userId="me", maxResults=limit, q=query).execute()
        out = []
        for ref in listing.get("messages", []):
            raw = messages.get(userId="me", id=ref["id"], format="metadata", metadataHeaders=_METADATA_HEADERS).execute()
            out.append(MessageSummary(account_id=self.account_id, **summary_fields(raw)))
        return out

    def _get_sync(self, message_id: str) -> Message:
        raw = self._get_service().users().messages().get(userId="me", id=message_id, format="full").execute()
        return Message(account_id=self.account_id, body=extract_body(raw.get("payload") or {}), **summary_fields(raw))

    async def list_messages(self, limit: int = 20, query: str | None = None) -> list[MessageSummary]:
        if limit <= 0:
            return []
        return await asyncio.to_thread(self._list_sync, limit, query)

    async def get_message(self, message_id: str) -> Message:
        return await asyncio.to_thread(self._get_sync, message_id)
