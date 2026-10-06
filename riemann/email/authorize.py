"""One-time OAuth consent for a Gmail account: python -m riemann.email.authorize <account_id> [--config PATH]"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from riemann.email.config import load_config
from riemann.email.credentials import resolve_ref
from riemann.email.gmail import SCOPES, write_token

CLIENT_SECRET_ENV = "RIEMANN_GOOGLE_CLIENT_SECRET"
DEFAULT_CLIENT_SECRET = "~/.config/riemann/creds/google_client_secret.json"


def client_secret_path() -> Path:
    return Path(os.environ.get(CLIENT_SECRET_ENV) or DEFAULT_CLIENT_SECRET).expanduser()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m riemann.email.authorize", description=__doc__)
    ap.add_argument("account_id")
    ap.add_argument("--config", help="path to email accounts JSON (default: RIEMANN_EMAIL_CONFIG or config/email_accounts.json)")
    args = ap.parse_args(argv)

    accounts = {a.id: a for a in load_config(args.config).accounts}
    account = accounts.get(args.account_id)
    if account is None:
        return _fail(f"unknown account {args.account_id!r} (configured: {', '.join(accounts) or 'none'})")
    if account.provider != "gmail":
        return _fail(f"account {account.id!r} uses provider {account.provider!r}; only gmail needs this")
    try:
        token_path = resolve_ref(account.credential_ref)
    except ValueError as e:
        return _fail(str(e))

    secret = client_secret_path()
    if not secret.is_file():
        return _fail(
            f"OAuth client secret not found at {secret}. Create a Desktop-app OAuth client in Google Cloud "
            f"(see README, 'Email accounts'), download its JSON there, or set {CLIENT_SECRET_ENV}."
        )

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
    creds = flow.run_local_server(
        port=0,
        login_hint=account.label if "@" in account.label else None,
        access_type="offline",
        prompt="consent",
    )
    from googleapiclient.discovery import build

    # Catch picking the wrong Google account on the consent screen before saving its token.
    email = build("gmail", "v1", credentials=creds, cache_discovery=False).users().getProfile(userId="me").execute()["emailAddress"]
    if "@" in account.label and email.lower() != account.label.lower():
        return _fail(f"signed in as {email}, but account {account.id!r} is {account.label}; token not saved, try again")
    write_token(token_path, creds.to_json())
    print(f"Authorized account {account.id!r} ({email}); token saved to {token_path}")
    return 0


def _fail(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
