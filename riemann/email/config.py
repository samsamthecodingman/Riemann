"""Email account config: a JSON file listing accounts.

Default path is config/email_accounts.json (gitignored); RIEMANN_EMAIL_CONFIG,
when set, overrides it. An account holds a credential_ref (where the credentials
live, e.g. "env:RIEMANN_GMAIL_PERSONAL"), never the secret itself.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "email_accounts.json"


class AccountConfig(BaseModel):
    id: str  # stable slug
    provider: Literal["gmail", "imap"]
    label: str  # human-readable
    credential_ref: str  # "env:NAME" or "file:PATH"; resolved by the connector, not here

    @field_validator("id")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not v or not all(c.islower() or c.isdigit() or c in "-_" for c in v):
            raise ValueError(f"account id {v!r} must be a non-empty slug of lowercase letters, digits, '-' or '_'")
        return v


class EmailConfig(BaseModel):
    accounts: list[AccountConfig]

    @model_validator(mode="after")
    def _unique_ids(self) -> EmailConfig:
        seen: set[str] = set()
        for a in self.accounts:
            if a.id in seen:
                raise ValueError(f"duplicate account id {a.id!r}")
            seen.add(a.id)
        return self


def config_path() -> Path:
    override = os.environ.get("RIEMANN_EMAIL_CONFIG")
    return Path(override).expanduser() if override else DEFAULT_CONFIG_PATH


def load_config(path: Path | str | None = None) -> EmailConfig:
    p = Path(path).expanduser() if path else config_path()
    return EmailConfig.model_validate_json(p.read_text(encoding="utf-8"))
