"""Playwright UI tour: screenshots + optional screencast for Continuum demo video.

Hardened for: server bootstrap, auth-disabled demo mode, flaky selectors after UI redesign,
empty frames, timeouts, and navigation across Chat / Memory Graph / Packer Lab / Policies.
"""
from __future__ import annotations

import json
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
VIEWPORT = {"width": 1440, "height": 900}
# Selector timeouts after UI redesign — generous but bounded
NAV_TIMEOUT_MS = 15000
CHAT_TIMEOUT_MS = 90000


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

        r = httpx.get(f"{url.rstrip('/')}/v1/health", timeout=3.0)
        return r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return False


def _api_features_ok(url: str) -> bool:
    """Require stats/graph routes so capture does not reuse a stale uvicorn process."""
    try:
        import httpx

        base = url.rstrip("/")
        # 422 = route exists but missing required query; 404 = old binary without route
        s = httpx.get(f"{base}/v1/memories/stats", timeout=3.0)
        g = httpx.get(f"{base}/v1/memories/graph", timeout=3.0)
        if s.status_code == 404 or g.status_code == 404:
            return False
        return True
    except Exception:
        return False


def ensure_server(base_url: str, timeout_s: float = 50.0) -> subprocess.Popen[Any] | None:
    """Return a Popen if we started uvicorn; None if an existing healthy server is reused."""
    url = base_url.rstrip("/")
    if _health_ok(url) and _api_features_ok(url):
        print(f"  Reusing healthy server at {url}")
        return None
    if _health_ok(url) and not _api_features_ok(url):
        raise RuntimeError(
            f"Server at {url} is up but missing /v1/memories/stats or /graph (stale process). "
            "Stop it and re-run so capture boots a fresh uvicorn with CONTINUUM_AUTH_DISABLED=1."
        )

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if _port_open(host, port):
        raise RuntimeError(
            f"Port {host}:{port} is occupied but /v1/health is not ok. "
            "Stop the other process or pass --base-url to a healthy Continuum API. "
            "If auth is required, set CONTINUUM_AUTH_DISABLED=1 for local demo capture."
        )

    env = os.environ.copy()
    env["CONTINUUM_AUTH_DISABLED"] = "1"
    env.setdefault("CONTINUUM_DB_PATH", str(REPO_ROOT / "data" / "continuum_demo_video.db"))
    # Fresh DB per capture avoids stale supersession noise
    db = Path(env["CONTINUUM_DB_PATH"])
    if db.is_file():
        try:
            db.unlink()
        except OSError:
            pass
    db.parent.mkdir(parents=True, exist_ok=True)

    env["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPO_ROOT),
            str(REPO_ROOT / "packages" / "memory_core"),
            str(REPO_ROOT / "packages" / "agent"),
            str(REPO_ROOT / "apps" / "api"),
            env.get("PYTHONPATH", ""),
        ]
    )

    print(f"  Starting uvicorn on {host}:{port} (CONTINUUM_AUTH_DISABLED=1)...")
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
        stderr=subprocess.PIPE,
    )

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if proc.poll() is not None:
            err = ""
            try:
                err = (proc.stderr.read() or b"").decode("utf-8", errors="replace")[-800:]
            except Exception:
                pass
            raise RuntimeError(
                "Failed to start uvicorn for demo capture.\n"
                f"{err}\n"
                "Start manually: CONTINUUM_AUTH_DISABLED=1 uvicorn continuum_api.main:app "
                "--host 127.0.0.1 --port 8000"
            )
        if _health_ok(url):
            return proc
        time.sleep(0.35)

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


def _wait_chat_reply(page: Any, prev_msg_count: int, timeout_ms: int = CHAT_TIMEOUT_MS) -> None:
    page.wait_for_function(
        f"""() => {{
          const log = document.getElementById('chatLog');
          if (!log) return false;
          const msgs = log.querySelectorAll('.msg');
          if (msgs.length <= {int(prev_msg_count)}) return false;
          // Prefer an assistant/system reply after the user message
          return true;
        }}""",
        timeout=timeout_ms,
    )
    page.wait_for_timeout(500)


def _send_message(page: Any, text: str) -> None:
    prev = page.locator("#chatLog .msg").count()
    page.fill("#messageInput", text)
    page.click("#sendBtn")
    _wait_chat_reply(page, prev)
    # Wait until send button re-enabled (sending=false)
    try:
        page.wait_for_function(
            "() => !document.getElementById('sendBtn')?.disabled",
            timeout=CHAT_TIMEOUT_MS,
        )
    except Exception:
        pass


def _shot(page: Any, path: Path, *, min_bytes: int = 8_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=False)
    if not path.is_file() or path.stat().st_size < min_bytes:
        # Retry once
        page.wait_for_timeout(400)
        page.screenshot(path=str(path), full_page=False)
    if not path.is_file() or path.stat().st_size < min_bytes:
        raise RuntimeError(f"Empty or tiny screenshot: {path} ({path.stat().st_size if path.is_file() else 0} bytes)")


def _goto_view(page: Any, view: str) -> None:
    """Click nav button for Chat / Memory Graph / Packer Lab / Policies."""
    sel = f"#nav-{view}" if view in ("chat", "memory", "packer", "admin") else f".nav-btn[data-view='{view}']"
    page.click(sel, timeout=NAV_TIMEOUT_MS)
    page.wait_for_function(
        f"() => document.querySelector('.view.active')?.dataset?.viewPanel === '{view}'",
        timeout=NAV_TIMEOUT_MS,
    )
    page.wait_for_timeout(350)


def _assert_no_banned_chrome(page: Any) -> None:
    text = (page.locator("body").inner_text() or "").lower()
    banned = ("hackathon", "devpost", "alibaba", "qwen cloud", "track one", "track 1")
    hits = [b for b in banned if b in text]
    if hits:
        print(f"  WARNING: banned chrome words visible on page: {hits}")


def capture_frames(
    out_dir: Path,
    base_url: str = DEFAULT_BASE_URL,
    *,
    record_video: bool = True,
) -> list[Path]:
    """Drive the full product tour; write frames + optional screencast + chapter markers."""
    from playwright.sync_api import sync_playwright

    frames_dir = out_dir / "frames"
    video_dir = out_dir / "screencast"
    frames_dir.mkdir(parents=True, exist_ok=True)
    if record_video:
        video_dir.mkdir(parents=True, exist_ok=True)

    workspace_id = f"demo-video-{int(time.time())}"
    url = base_url.rstrip("/")
    chapter_markers: list[dict[str, Any]] = []
    t0 = time.time()

    def mark(beat_id: str, label: str) -> None:
        chapter_markers.append(
            {"id": beat_id, "label": label, "t_sec": round(time.time() - t0, 3)}
        )

    proc = ensure_server(url)
    paths: list[Path] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx_kwargs: dict[str, Any] = {"viewport": VIEWPORT}
            if record_video:
                ctx_kwargs["record_video_dir"] = str(video_dir)
                ctx_kwargs["record_video_size"] = VIEWPORT
            context = browser.new_context(**ctx_kwargs)
            page = context.new_page()
            page.set_default_timeout(NAV_TIMEOUT_MS)

            # Retry navigation once (cold start)
            last_err: Exception | None = None
            for attempt in range(2):
                try:
                    page.goto(f"{url}/", wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_selector("h1", timeout=NAV_TIMEOUT_MS)
                    break
                except Exception as exc:
                    last_err = exc
                    page.wait_for_timeout(1000)
            else:
                raise RuntimeError(f"Failed to load Continuum UI at {url}/: {last_err}")

            title = page.locator("h1").inner_text() or ""
            if "Continuum" not in title:
                raise RuntimeError(f"Expected Continuum brand in h1, got: {title!r}")
            _assert_no_banned_chrome(page)

            # Fresh workspace before hero so the inspector is empty (avoid dirty shared server state)
            _goto_view(page, "chat")
            page.fill("#workspaceId", workspace_id)
            page.fill("#orgId", "org_demo")
            page.evaluate("document.getElementById('sessionId').value = 'session-a'")
            page.evaluate(
                """() => {
                  const w = document.getElementById('workspaceId');
                  w && w.dispatchEvent(new Event('change'));
                  const o = document.getElementById('orgId');
                  o && o.dispatchEvent(new Event('change'));
                }"""
            )
            page.wait_for_timeout(600)

            mark("01_intro", "Hero / Chat")
            p01 = frames_dir / "01_hero.png"
            _shot(page, p01)
            paths.append(p01)

            mark("02_session_a_vip", "VIP memory")
            _send_message(page, "Remember: Acme is a VIP customer.")
            p02 = frames_dir / "02_session_a_vip.png"
            _shot(page, p02)
            paths.append(p02)

            mark("03_session_a_discount", "Discount memory")
            _send_message(page, "Remember: Approved 12% discount for Acme through end of 2026.")
            p03 = frames_dir / "03_session_a_discount.png"
            _shot(page, p03)
            paths.append(p03)

            mark("04_session_a_pref", "Preference + Active tab")
            _send_message(page, "Remember: Acme prefers email communication over phone.")
            page.click("#statusTabs .tab[data-status='active']")
            page.wait_for_timeout(400)
            try:
                page.wait_for_selector("#memoryList .memory-card", timeout=20000)
            except Exception:
                page.wait_for_timeout(1000)
            p04 = frames_dir / "04_session_a_pref.png"
            _shot(page, p04)
            paths.append(p04)

            mark("05_new_session", "New Session")
            page.click("#newSession")
            page.wait_for_timeout(500)
            p05 = frames_dir / "05_new_session.png"
            _shot(page, p05)
            paths.append(p05)

            mark("06_recall_citations", "Session B recall")
            _send_message(page, "What discount does Acme get and are they VIP?")
            page.wait_for_timeout(700)
            p06 = frames_dir / "06_recall_citations.png"
            _shot(page, p06)
            paths.append(p06)

            mark("07_packer_chat", "Packer panel")
            try:
                page.wait_for_function(
                    """() => {
                      const el = document.getElementById('packMeta');
                      return el && el.innerText && el.innerText.includes('Algorithm:');
                    }""",
                    timeout=30000,
                )
            except Exception:
                print("  WARNING: packMeta did not show Algorithm — continuing")
            try:
                page.locator("#budget").evaluate(
                    "el => { el.value = 600; el.dispatchEvent(new Event('input')); }"
                )
            except Exception:
                pass
            page.wait_for_timeout(300)
            p07 = frames_dir / "07_packer_chat.png"
            _shot(page, p07)
            paths.append(p07)

            mark("08_memory_graph", "Memory Graph view")
            _goto_view(page, "memory")
            page.wait_for_timeout(800)
            try:
                page.click("#refreshStats")
                page.wait_for_timeout(600)
            except Exception:
                pass
            p08 = frames_dir / "08_memory_graph.png"
            _shot(page, p08)
            paths.append(p08)

            mark("09_packer_lab", "Packer Lab")
            _goto_view(page, "packer")
            page.fill("#packQuery", "What discount does Acme get?")
            page.click("#runPack")
            page.wait_for_timeout(1200)
            try:
                page.wait_for_function(
                    """() => {
                      const el = document.getElementById('labPackMeta');
                      return el && (el.innerText.includes('Algorithm:') || el.innerText.includes('Error'));
                    }""",
                    timeout=30000,
                )
            except Exception:
                print("  WARNING: Packer Lab preview slow — continuing")
            p09 = frames_dir / "09_packer_lab.png"
            _shot(page, p09)
            paths.append(p09)

            mark("10_policies_forget", "Policies / forgetting")
            _goto_view(page, "admin")
            try:
                page.click("#adminForget")
                page.wait_for_timeout(1000)
            except Exception as exc:
                print(f"  WARNING: admin forget click: {exc}")
            try:
                page.click("#loadPolicyMemories")
                page.wait_for_timeout(500)
            except Exception:
                pass
            p10 = frames_dir / "10_policies_forget.png"
            _shot(page, p10)
            paths.append(p10)

            mark("11_close", "Back to Chat close")
            _goto_view(page, "chat")
            # Cycle status tabs to show lifecycle
            for status in ("superseded", "forgotten", "active"):
                try:
                    page.click(f"#statusTabs .tab[data-status='{status}']")
                    page.wait_for_timeout(350)
                except Exception:
                    pass
            p11 = frames_dir / "11_close.png"
            _shot(page, p11)
            paths.append(p11)

            page_video = page.video if record_video else None
            context.close()
            browser.close()

            screencast_path = None
            if page_video is not None:
                try:
                    raw = Path(page_video.path())
                    dest = out_dir / "screencast" / "tour.webm"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if raw.is_file():
                        raw.replace(dest)
                        screencast_path = dest
                        print(f"  Screencast: {dest}")
                except Exception as exc:
                    print(f"  WARNING: could not save screencast: {exc}")

            markers_path = out_dir / "CHAPTER_MARKERS.json"
            markers_path.write_text(
                json.dumps(
                    {
                        "base_url": url,
                        "workspace_id": workspace_id,
                        "screencast": str(screencast_path) if screencast_path else None,
                        "chapters": chapter_markers,
                        "frames": [str(p.name) for p in paths],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"  Chapter markers: {markers_path}")
    finally:
        _stop_proc(proc)

    if len(paths) < 11:
        raise RuntimeError(f"Expected 11 frames, got {len(paths)}")
    return paths


if __name__ == "__main__":
    out = REPO_ROOT / "demo_video"
    captured = capture_frames(out)
    print(f"captured {len(captured)} frames -> {out / 'frames'}")
