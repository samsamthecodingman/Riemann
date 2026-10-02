"""Opt-in browser tests. Skipped unless RIEMANN_E2E=1 and Node, the `playwright` npm package and a
Chromium build are all available (see the README, "Browser tests").

Each run starts its own server on an ephemeral port with a scratch
RIEMANN_DATA_DIR and a FakeSummariser, so it never touches Sam's cache or
activity log and never calls a model."""

from __future__ import annotations

import glob
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
RUNNER = Path(__file__).resolve().parent / "runner.js"

DOC = "\n\n".join(
    f"## Section {s}\n\n"
    + "\n\n".join(
        f"Paragraph {p} of section {s}. " + "The tide moved sand along the northern beach while the survey team measured it. " * 6
        for p in range(4)
    )
    for s in range(1, 6)
)


def _playwright_dir() -> str | None:
    """Where the `playwright` npm package lives: $RIEMANN_PLAYWRIGHT, then a
    global install, then the repo's node_modules."""
    env = os.environ.get("RIEMANN_PLAYWRIGHT")
    candidates = [env] if env else []
    npm = shutil.which("npm")
    if npm:
        try:
            root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True, timeout=20).stdout.strip()
            if root:
                candidates.append(os.path.join(root, "playwright"))
        except Exception:
            pass
    candidates.append(str(ROOT / "node_modules" / "playwright"))
    # An `npx playwright` cache install, e.g. ~/.npm/_npx/<hash>/node_modules/playwright.
    candidates.extend(sorted(glob.glob(os.path.expanduser("~/.npm/_npx/*/node_modules/playwright"))))
    for c in candidates:
        if c and os.path.isfile(os.path.join(c, "package.json")):
            return c
    return None


@pytest.fixture(scope="session")
def playwright_dir():
    if os.environ.get("RIEMANN_E2E") != "1":
        pytest.skip("browser tests are opt-in: set RIEMANN_E2E=1")
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    d = _playwright_dir()
    if d is None:
        pytest.skip("the playwright npm package was not found (set RIEMANN_PLAYWRIGHT to its folder)")
    probe = subprocess.run(
        ["node", "-e", f"const {{chromium}}=require({json.dumps(d)});chromium.launch().then(b=>b.close()).then(()=>process.exit(0),e=>{{console.error(e.message);process.exit(3)}})"],
        capture_output=True, text=True, timeout=60,
    )
    if probe.returncode != 0:
        pytest.skip("no Chromium build for Playwright: " + probe.stderr.strip()[:120])
    return d


@pytest.fixture(scope="session")
def server(tmp_path_factory, playwright_dir):
    data = tmp_path_factory.mktemp("e2e-data")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, RIEMANN_DATA_DIR=str(data), PYTHONPATH=str(ROOT))
    os.environ["RIEMANN_E2E_DATA"] = str(data)  # runner.js writes old-version trees and build markers there
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "tests.e2e.fake_app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(base + "/api/recent", timeout=1).read()
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.kill()
        pytest.skip("the test server did not start")
    yield base
    proc.terminate()
    proc.wait(timeout=10)


@pytest.fixture(scope="session")
def tree_id(server):
    req = urllib.request.Request(
        server + "/api/abstract", data=json.dumps({"text": DOC}).encode(), headers={"content-type": "application/json"}
    )
    tid = json.loads(urllib.request.urlopen(req, timeout=20).read())["tree_id"]
    for _ in range(100):
        tree = json.loads(urllib.request.urlopen(f"{server}/api/tree/{tid}", timeout=5).read())
        if tree["status"] != "building":
            break
        time.sleep(0.1)
    assert tree["status"] == "done"
    return tid


@pytest.fixture()
def run_check(server, tree_id, playwright_dir):
    def run(name: str, *args: str) -> dict:
        proc = subprocess.run(
            ["node", str(RUNNER), playwright_dir, server, tree_id, name, *args],
            capture_output=True, text=True, timeout=300,
        )
        out = proc.stdout.strip().splitlines()
        assert out, f"no output from runner ({proc.stderr[:400]})"
        result = json.loads(out[-1])
        assert result.get("ok"), json.dumps(result, indent=1)[:1500]
        return result

    return run
