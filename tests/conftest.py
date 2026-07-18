from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "unit: memory_core unit tests (no server)")
    config.addinivalue_line("markers", "api: FastAPI TestClient API regression (no live server)")
    config.addinivalue_line(
        "markers", "e2e: Playwright browser regression (server + Chromium)"
    )
    config.addinivalue_line("markers", "eval: offline eval suite checks")


@pytest.fixture(scope="session")
def base_url() -> str:
    """Session-scoped so it is compatible with pytest-base_url (pytest-playwright)."""
    return os.environ.get("CONTINUUM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture
def unique_workspace_id() -> str:
    return f"ws-test-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def api_client(tmp_path: Path) -> Generator:
    """FastAPI TestClient bound to a temp DB (does not touch prod continuum.db)."""
    db_path = tmp_path / "continuum_test.db"
    os.environ["CONTINUUM_DB_PATH"] = str(db_path)
    os.environ["CONTINUUM_AUTH_DISABLED"] = "1"
    # Clear keys so auth stays off even if shell has CONTINUUM_API_KEYS set
    os.environ.pop("CONTINUUM_API_KEYS", None)

    # Re-import / reload so module-level MemoryService picks up the temp DB.
    import importlib

    import continuum_api.main as main_mod

    importlib.reload(main_mod)

    from fastapi.testclient import TestClient

    with TestClient(main_mod.app) as client:
        yield client


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            sock.connect((host, port))
            return True
        except OSError:
            return False


def _health_ok(url: str) -> bool:
    try:
        import httpx

        r = httpx.get(f"{url}/v1/health", timeout=2.0)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


@pytest.fixture(scope="session")
def e2e_server() -> Generator[str, None, None]:
    """Ensure API is reachable at CONTINUUM_BASE_URL; start uvicorn if needed."""
    url = os.environ.get("CONTINUUM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    host = "127.0.0.1"
    port = 8000
    if "://" in url:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.hostname or host
        port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if _health_ok(url):
        yield url
        return

    if _port_open(host, port):
        pytest.skip(
            f"Port {host}:{port} is occupied but /v1/health is not ok. "
            f"Stop the other process or set CONTINUUM_BASE_URL."
        )

    env = os.environ.copy()
    env.setdefault("CONTINUUM_DB_PATH", str(REPO_ROOT / "data" / "continuum_e2e.db"))
    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO_ROOT),
            str(REPO_ROOT / "packages" / "memory_core"),
            str(REPO_ROOT / "packages" / "agent"),
            str(REPO_ROOT / "apps" / "api"),
            env.get("PYTHONPATH", ""),
        ]
    )

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "continuum_api.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        if proc.poll() is not None:
            pytest.skip(
                "Failed to start uvicorn for e2e tests. "
                "Start manually: uvicorn continuum_api.main:app --host 127.0.0.1 --port 8000"
            )
        if _health_ok(url):
            break
        time.sleep(0.4)
    else:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        pytest.skip(
            f"Timed out waiting for {url}/v1/health. "
            "Start the API manually or install deps (pip install -e '.[dev]')."
        )

    try:
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def browser():
    playwright = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser, e2e_server: str, request: pytest.FixtureRequest) -> Generator:
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    page = context.new_page()
    yield page

    # Screenshot on failure
    failed = getattr(request.node, "rep_call", None)
    if failed is not None and failed.failed:
        out = REPO_ROOT / "test_artifacts"
        out.mkdir(exist_ok=True)
        safe = request.node.name.replace("/", "_").replace("::", "_")
        page.screenshot(path=str(out / f"{safe}.png"), full_page=True)

    context.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
