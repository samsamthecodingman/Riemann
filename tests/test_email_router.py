"""Multi-account email router: config validation, connector registry, routing by account_id."""
import json

import pytest
from pydantic import ValidationError

from riemann.email import ConnectorRouter, EmailConnector, Message, MessageSummary, load_config
from riemann.email.config import EmailConfig
from riemann.email.gmail import GmailConnector
from riemann.email.stubs import ImapConnector, StubGmailConnector

STUB_PROVIDERS = {"gmail": StubGmailConnector, "imap": ImapConnector}

ACCOUNTS = [
    {"id": "g1", "provider": "gmail", "label": "Gmail One", "credential_ref": "env:G1"},
    {"id": "i1", "provider": "imap", "label": "Imap One", "credential_ref": "file:~/c.json"},
    {"id": "g2", "provider": "gmail", "label": "Gmail Two", "credential_ref": "env:G2"},
]


def router(accounts=ACCOUNTS, providers=None) -> ConnectorRouter:
    return ConnectorRouter(EmailConfig.model_validate({"accounts": accounts}), providers)


def test_config_valid_from_file_and_env_override(tmp_path, monkeypatch):
    p = tmp_path / "accts.json"
    p.write_text(json.dumps({"accounts": ACCOUNTS}))
    monkeypatch.setenv("RIEMANN_EMAIL_CONFIG", str(p))
    cfg = load_config()
    assert [a.id for a in cfg.accounts] == ["g1", "i1", "g2"]
    assert cfg.accounts[1].credential_ref == "file:~/c.json"


def test_example_config_is_valid():
    cfg = load_config("config/email_accounts.example.json")
    assert sorted(a.provider for a in cfg.accounts) == ["gmail", "imap"]


def test_config_duplicate_id_rejected():
    with pytest.raises(ValidationError, match="duplicate account id 'g1'"):
        EmailConfig.model_validate({"accounts": [ACCOUNTS[0], {**ACCOUNTS[1], "id": "g1"}]})


def test_config_unknown_provider_rejected():
    with pytest.raises(ValidationError, match="provider"):
        EmailConfig.model_validate({"accounts": [{**ACCOUNTS[0], "provider": "outlook"}]})


def test_router_one_connector_per_account_with_types():
    r = router()
    assert [a.id for a in r.accounts()] == ["g1", "i1", "g2"]
    assert isinstance(r.get("g1"), GmailConnector)
    assert isinstance(r.get("g2"), GmailConnector)
    assert isinstance(r.get("i1"), ImapConnector)
    assert r.get("g1") is not r.get("g2")
    assert all(isinstance(r.get(a.id), EmailConnector) for a in r.accounts())
    assert r.get("i1").label == "Imap One"


def test_router_construction_is_lazy_and_touches_no_files():
    # credential_ref points nowhere; building the router must not resolve or read it.
    r = router([{**ACCOUNTS[0], "credential_ref": "file:/nonexistent/token.json"}])
    assert r.get("g1")._service is None


async def test_routing_returns_tagged_data():
    # Stub providers keep this test off the network.
    r = router(providers=STUB_PROVIDERS)
    for acct in ("g1", "i1", "g2"):
        msgs = await r.list_messages(acct, limit=3)
        assert len(msgs) == 3
        assert all(isinstance(m, MessageSummary) and m.account_id == acct for m in msgs)
        full = await r.get_message(acct, msgs[0].id)
        assert isinstance(full, Message) and full.account_id == acct and full.body
    assert (await r.list_messages("g1", limit=2, query="message 1"))[0].snippet.endswith("g1")


async def test_unknown_account_errors():
    r = router(providers=STUB_PROVIDERS)
    with pytest.raises(KeyError, match="unknown email account 'nope'"):
        r.get("nope")
    with pytest.raises(KeyError):
        await r.list_messages("nope")
    with pytest.raises(KeyError):
        await r.get_message("nope", "gmail-1")
