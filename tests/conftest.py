"""Global test isolation: never let tests touch Sam's real cache/data dirs."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RIEMANN_DATA_DIR", str(tmp_path))
    yield


# The ASGI test client's Host is "test"; the app only answers local names.
import os as _os

_os.environ.setdefault("RIEMANN_ALLOWED_HOSTS", "test")
