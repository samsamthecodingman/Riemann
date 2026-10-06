"""Gmail connector: credential refs, pure parsing helpers, connector with a fake service. No network."""
import base64
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import pytest

from riemann.email.base import EmailConnector, Message, MessageSummary
from riemann.email.config import AccountConfig
from riemann.email.credentials import resolve_ref
from riemann.email.gmail import (
    GmailAuthError,
    GmailConnector,
    extract_body,
    parse_date,
    parse_headers,
    write_token,
)


def b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")  # Gmail omits padding


def test_resolve_ref_file_expands_user():
    assert resolve_ref("file:~/x/t.json") == Path.home() / "x" / "t.json"
    assert resolve_ref("file:/abs/t.json") == Path("/abs/t.json")


@pytest.mark.parametrize("ref", ["env:FOO", "plain", "file:"])
def test_resolve_ref_rejects_others(ref):
    with pytest.raises(ValueError, match="credential_ref"):
        resolve_ref(ref)


def test_parse_headers_case_insensitive_first_wins_and_missing():
    h = parse_headers({"headers": [{"name": "From", "value": "a@x"}, {"name": "from", "value": "b@x"}, {"name": "SUBJECT", "value": "Hi"}]})
    assert h == {"from": "a@x", "subject": "Hi"}
    assert parse_headers({}) == {}


def test_parse_date_is_utc_aware():
    d = parse_date("1767225600000")
    assert d == datetime(2026, 1, 1, tzinfo=timezone.utc) and d.tzinfo is not None
    assert parse_date(None) == datetime(1970, 1, 1, tzinfo=timezone.utc)


def test_extract_body_nested_multipart_prefers_plain():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "multipart/alternative", "parts": [
                {"mimeType": "text/html", "body": {"data": b64("<p>html</p>")}},
                {"mimeType": "text/plain", "body": {"data": b64("plain é text")}},
            ]},
            {"mimeType": "application/pdf", "body": {"attachmentId": "abc"}},
        ],
    }
    assert extract_body(payload) == "plain é text"


def test_extract_body_html_only_stripped():
    payload = {"mimeType": "text/html", "body": {"data": b64("<style>p{}</style><div>Hello&nbsp;<b>there</b> &amp; you</div><p>Bye</p>")}}
    assert extract_body(payload) == "Hello there & you\nBye"


def test_extract_body_empty_when_nothing():
    assert extract_body({"mimeType": "multipart/mixed", "parts": [{"mimeType": "image/png", "body": {}}]}) == ""
    assert extract_body({}) == ""


def raw_message(i: str, *, headers=True, body=None) -> dict:
    payload = {"mimeType": "text/plain", "headers": [], "body": {"data": b64(body or "")}}
    if headers:
        payload["headers"] = [
            {"name": "From", "value": f"s{i}@example.com"},
            {"name": "Subject", "value": f"Subject {i}"},
            {"name": "Date", "value": "ignored"},
        ]
    return {"id": i, "internalDate": "1767225600000", "snippet": "Tom &amp; Jerry &#39;hi&#39;", "payload": payload}


class FakeRequest:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


class _Msgs:
    def __init__(self, store, calls):
        self.store, self.calls = store, calls

    def list(self, **kw):
        self.calls.append(("list", kw))
        return FakeRequest({"messages": [{"id": i} for i in list(self.store)[: kw["maxResults"]]]})

    def get(self, **kw):
        self.calls.append(("get", kw))
        return FakeRequest(self.store[kw["id"]])


def fake_service(store):
    calls: list[tuple] = []
    msgs = _Msgs(store, calls)

    class Users:
        def messages(self):
            return msgs

    class Svc:
        def users(self):
            return Users()

    svc = Svc()
    svc.calls = calls
    return svc


ACCT = AccountConfig(id="g1", provider="gmail", label="me@gmail.com", credential_ref="file:/nonexistent/g1.json")


async def test_list_and_get_with_fake_service_are_tagged():
    svc = fake_service({"m1": raw_message("m1", body="body one"), "m2": raw_message("m2", headers=False)})
    c = GmailConnector(ACCT, service=svc)
    assert isinstance(c, EmailConnector)
    msgs = await c.list_messages(limit=5, query="is:unread")
    assert [m.id for m in msgs] == ["m1", "m2"]
    assert all(isinstance(m, MessageSummary) and m.account_id == "g1" for m in msgs)
    assert msgs[0].sender == "sm1@example.com" and msgs[0].subject == "Subject m1"
    assert msgs[0].snippet == "Tom & Jerry 'hi'"
    assert msgs[0].date == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert (msgs[1].sender, msgs[1].subject) == ("", "")  # missing headers tolerated
    kind, kw = svc.calls[0]
    assert kind == "list" and kw == {"userId": "me", "maxResults": 5, "q": "is:unread"}
    assert svc.calls[1][1]["format"] == "metadata" and svc.calls[1][1]["metadataHeaders"] == ["From", "Subject", "Date"]

    full = await c.get_message("m1")
    assert isinstance(full, Message) and full.account_id == "g1" and full.body == "body one"
    assert svc.calls[-1][1]["format"] == "full"


async def test_list_limit_zero_makes_no_call():
    svc = fake_service({})
    assert await GmailConnector(ACCT, service=svc).list_messages(limit=0) == []
    assert svc.calls == []


async def test_missing_token_gives_helpful_error(tmp_path):
    acct = ACCT.model_copy(update={"credential_ref": f"file:{tmp_path}/nope.json"})
    with pytest.raises(GmailAuthError, match=r"riemann\.email\.authorize g1"):
        await GmailConnector(acct).list_messages()


def test_write_token_permissions(tmp_path):
    p = tmp_path / "creds" / "t.json"
    write_token(p, "{}")
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(p.parent).st_mode) == 0o700
    write_token(p, '{"a":1}')
    assert p.read_text() == '{"a":1}'
