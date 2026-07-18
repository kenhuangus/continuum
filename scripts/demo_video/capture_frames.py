"""Playwright happy-path screenshots for the Continuum demo video."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
VIEWPORT = {"width": 1400, "height": 900}


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

        r = httpx.get(f"{url.rstrip('/')}/v1/health", timeout=2.0)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def ensure_server(base_url: str, timeout_s: float = 45.0) -> subprocess.Popen[Any] | None:
    """Return a Popen if we started uvicorn; None if an existing healthy server is reused."""
    url = base_url.rstrip("/")
    if _health_ok(url):
        return None

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if _port_open(host, port):
        raise RuntimeError(
            f"Port {host}:{port} is occupied but /v1/health is not ok. "
            "Stop the other process or pass --base-url to a healthy Continuum API."
        )

    env = os.environ.copy()
    env.setdefault("CONTINUUM_AUTH_DISABLED", "1")
    env.setdefault("CONTINUUM_DB_PATH", str(REPO_ROOT / "data" / "continuum_demo_video.db"))
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

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                "Failed to start uvicorn for demo capture. "
                "Start manually: uvicorn continuum_api.main:app --host 127.0.0.1 --port 8000"
            )
        if _health_ok(url):
            return proc
        time.sleep(0.4)

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    raise RuntimeError(f"Timed out waiting for {url}/v1/health ({timeout_s:.0f}s).")


def _stop_proc(proc: subprocess.Popen[Any] | None) -> None:
    if proc is None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _wait_chat_reply(page: Any, prev_msg_count: int, timeout_ms: int = 60000) -> None:
    # Embed count in the expression (avoids Playwright arg quirks across versions).
    page.wait_for_function(
        f"""() => {{
          const log = document.getElementById('chatLog');
          return log && log.querySelectorAll('.msg').length > {int(prev_msg_count)};
        }}""",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(600)


def _send_message(page: Any, text: str) -> None:
    prev = page.locator("#chatLog .msg").count()
    page.fill("#messageInput", text)
    page.click("#sendBtn")
    _wait_chat_reply(page, prev)


def _shot(page: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=False)


def capture_frames(out_dir: Path, base_url: str = DEFAULT_BASE_URL) -> list[Path]:
    """Run the happy-path UI flow and write the eight demo frames. Returns frame paths."""
    from playwright.sync_api import sync_playwright

    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    workspace_id = f"demo-video-{int(time.time())}"
    url = base_url.rstrip("/")

    proc = ensure_server(url)
    paths: list[Path] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport=VIEWPORT)
            page = context.new_page()
            page.goto(f"{url}/", wait_until="networkidle", timeout=30000)

            page.wait_for_selector("h1", timeout=10000)
            assert "Continuum" in (page.locator("h1").inner_text() or "")
            p01 = frames_dir / "01_hero.png"
            _shot(page, p01)
            paths.append(p01)

            page.fill("#workspaceId", workspace_id)
            page.evaluate("document.getElementById('sessionId').value = 'session-a'")

            _send_message(page, "Remember: Acme is a VIP customer.")
            p02 = frames_dir / "02_session_a_vip.png"
            _shot(page, p02)
            paths.append(p02)

            _send_message(page, "Remember: Approved 12% discount for Acme through end of 2026.")
            p03 = frames_dir / "03_session_a_discount.png"
            _shot(page, p03)
            paths.append(p03)

            _send_message(page, "Remember: Acme prefers email communication over phone.")
            page.click(".tab[data-status='active']")
            page.wait_for_timeout(500)
            page.wait_for_selector("#memoryList .memory-card", timeout=15000)
            p04 = frames_dir / "04_session_a_email.png"
            _shot(page, p04)
            paths.append(p04)

            page.click("#newSession")
            page.wait_for_timeout(400)
            p05 = frames_dir / "05_new_session.png"
            _shot(page, p05)
            paths.append(p05)

            _send_message(page, "What discount does Acme get and are they VIP?")
            page.wait_for_timeout(800)
            p06 = frames_dir / "06_session_b_recall.png"
            _shot(page, p06)
            paths.append(p06)

            page.wait_for_function(
                """() => {
                  const el = document.getElementById('packMeta');
                  return el && el.innerText && el.innerText.includes('Algorithm:');
                }""",
                timeout=30000,
            )
            p07 = frames_dir / "07_packer_panel.png"
            _shot(page, p07)
            paths.append(p07)

            # Prefer forget pass; fall back to tab cycling if flaky.
            try:
                page.click("#forgetPass")
                page.wait_for_timeout(1200)
                log = page.locator("#chatLog").inner_text()
                if "Forgetting pass:" not in log:
                    raise RuntimeError("forget pass message missing")
            except Exception:
                for status in ("superseded", "forgotten", "active"):
                    page.click(f".tab[data-status='{status}']")
                    page.wait_for_timeout(350)
            p08 = frames_dir / "08_forget_or_tabs.png"
            _shot(page, p08)
            paths.append(p08)

            context.close()
            browser.close()
    finally:
        _stop_proc(proc)

    return paths


if __name__ == "__main__":
    out = REPO_ROOT / "demo_video"
    captured = capture_frames(out)
    print(f"captured {len(captured)} frames -> {out / 'frames'}")
