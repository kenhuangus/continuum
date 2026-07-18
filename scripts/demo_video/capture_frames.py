"""Playwright UI tour: dense multi-view screencast + frames for Continuum demo video.

Hardened for: server bootstrap, auth-disabled demo mode, flaky selectors after UI redesign,
empty frames, timeouts, and field-level navigation across Chat / Memory Graph / Packer Lab / Policies.
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
# Expected frame count must match narration.BEATS
EXPECTED_FRAMES = 18


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
        s = httpx.get(f"{base}/v1/memories/stats", timeout=3.0, params={"workspace_id": "_probe"})
        g = httpx.get(f"{base}/v1/memories/graph", timeout=3.0, params={"workspace_id": "_probe"})
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
        if _health_ok(url) and _api_features_ok(url):
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
        page.wait_for_timeout(400)
        page.screenshot(path=str(path), full_page=False)
    if not path.is_file() or path.stat().st_size < min_bytes:
        raise RuntimeError(
            f"Empty or tiny screenshot: {path} ({path.stat().st_size if path.is_file() else 0} bytes)"
        )


def _goto_view(page: Any, view: str) -> None:
    """Click nav button for Chat / Memory Graph / Packer Lab / Policies."""
    sel = f"#nav-{view}" if view in ("chat", "memory", "packer", "admin") else f".nav-btn[data-view='{view}']"
    page.click(sel, timeout=NAV_TIMEOUT_MS)
    page.wait_for_function(
        f"() => document.querySelector('.view.active')?.dataset?.viewPanel === '{view}'",
        timeout=NAV_TIMEOUT_MS,
    )
    page.wait_for_timeout(400)


def _focus_field(page: Any, selector: str) -> None:
    try:
        page.locator(selector).click(timeout=3000)
        page.wait_for_timeout(200)
    except Exception:
        pass


def _ensure_demo_highlight_style(page: Any) -> None:
    page.evaluate(
        """() => {
          if (document.getElementById('demo-highlight-style')) return;
          const s = document.createElement('style');
          s.id = 'demo-highlight-style';
          s.textContent = `
            [data-demo-highlight="1"], .demo-highlight {
              outline: 3px solid #0d9488 !important;
              outline-offset: 3px !important;
              box-shadow: 0 0 0 4px rgba(13, 148, 136, 0.25) !important;
              animation: demoPulse 1.1s ease-in-out infinite !important;
              border-radius: 4px;
            }
            @keyframes demoPulse {
              0%, 100% { outline-color: #0d9488; }
              50% { outline-color: #14b8a6; }
            }
          `;
          document.head.appendChild(s);
        }"""
    )


def _clear_highlights(page: Any) -> None:
    try:
        page.evaluate(
            """() => {
              document.querySelectorAll('[data-demo-highlight], .demo-highlight').forEach(el => {
                el.removeAttribute('data-demo-highlight');
                el.classList.remove('demo-highlight');
              });
            }"""
        )
    except Exception:
        pass


def _highlight(page: Any, *selectors: str) -> None:
    """CSS outline/pulse on fields/sections being narrated for this chapter."""
    _ensure_demo_highlight_style(page)
    _clear_highlights(page)
    for sel in selectors:
        try:
            page.locator(sel).first.evaluate(
                """el => {
                  el.setAttribute('data-demo-highlight', '1');
                  el.classList.add('demo-highlight');
                }"""
            )
        except Exception:
            pass
    page.wait_for_timeout(280)


def _set_range(page: Any, selector: str, value: int) -> None:
    page.locator(selector).evaluate(
        f"el => {{ el.value = {int(value)}; el.dispatchEvent(new Event('input')); "
        f"el.dispatchEvent(new Event('change')); }}"
    )
    page.wait_for_timeout(250)


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

            last_err: Exception | None = None
            for _attempt in range(2):
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

            # Fresh workspace before hero
            _goto_view(page, "chat")
            page.fill("#workspaceId", workspace_id)
            page.fill("#orgId", "org_demo")
            page.fill("#apiKey", "")
            page.evaluate("document.getElementById('sessionId').value = 'session-a'")
            page.evaluate(
                """() => {
                  const w = document.getElementById('workspaceId');
                  w && w.dispatchEvent(new Event('change'));
                  const o = document.getElementById('orgId');
                  o && o.dispatchEvent(new Event('change'));
                }"""
            )
            page.wait_for_timeout(700)

            # 01 intro / hero
            mark("01_intro", "Hero / Chat")
            _highlight(page, "h1", "#nav-chat")
            p01 = frames_dir / "01_hero.png"
            _shot(page, p01)
            paths.append(p01)
            page.wait_for_timeout(900)

            # 02 field-level: workspace / session / org / api key
            mark("02_chat_fields", "Workspace & session fields")
            _highlight(page, "#workspaceId", "#sessionId", "#orgId", "#apiKey")
            _focus_field(page, "#workspaceId")
            page.wait_for_timeout(400)
            _focus_field(page, "#sessionId")
            page.wait_for_timeout(350)
            _focus_field(page, "#orgId")
            page.wait_for_timeout(350)
            _focus_field(page, "#apiKey")
            page.wait_for_timeout(400)
            p02 = frames_dir / "02_chat_fields.png"
            _shot(page, p02)
            paths.append(p02)

            # 03 budget + packer algo + buttons
            mark("03_budget_algo", "Budget & packer controls")
            _set_range(page, "#budget", 900)
            page.select_option("#packerAlgo", "type_quota")
            page.wait_for_timeout(300)
            _highlight(page, "#budget", "#packerAlgo", "#newSession", "#forgetPass")
            _focus_field(page, "#budget")
            page.wait_for_timeout(400)
            _focus_field(page, "#packerAlgo")
            page.wait_for_timeout(400)
            page.hover("#newSession")
            page.wait_for_timeout(300)
            page.hover("#forgetPass")
            page.wait_for_timeout(400)
            p03 = frames_dir / "03_budget_algo.png"
            _shot(page, p03)
            paths.append(p03)

            # 04 VIP
            mark("04_session_a_vip", "VIP memory")
            _highlight(page, "#messageInput", "#sendBtn", "#memoryList")
            _send_message(page, "Remember: Acme is a VIP customer.")
            page.wait_for_timeout(600)
            _highlight(page, "#chatLog", "#memoryList")
            p04 = frames_dir / "04_session_a_vip.png"
            _shot(page, p04)
            paths.append(p04)

            # 05 discount
            mark("05_session_a_discount", "Discount memory")
            _highlight(page, "#messageInput", "#memoryList")
            _send_message(page, "Remember: Approved 12% discount for Acme through end of 2026.")
            page.wait_for_timeout(600)
            _highlight(page, "#chatLog", "#memoryList")
            p05 = frames_dir / "05_session_a_discount.png"
            _shot(page, p05)
            paths.append(p05)

            # 06 preference + Active tab
            mark("06_session_a_pref", "Preference + Active tab")
            _send_message(page, "Remember: Acme prefers email communication over phone.")
            page.click("#statusTabs .tab[data-status='active']")
            page.wait_for_timeout(500)
            try:
                page.wait_for_selector("#memoryList .memory-card", timeout=20000)
            except Exception:
                page.wait_for_timeout(1000)
            try:
                page.locator("#memoryList .memory-card").first.click(timeout=5000)
                page.wait_for_timeout(400)
            except Exception:
                pass
            _highlight(page, "#statusTabs", "#memoryList")
            p06 = frames_dir / "06_session_a_pref.png"
            _shot(page, p06)
            paths.append(p06)

            # 07 new session
            mark("07_new_session", "New Session")
            page.click("#newSession")
            page.wait_for_timeout(700)
            _highlight(page, "#newSession", "#sessionId", "#chatLog")
            _focus_field(page, "#sessionId")
            page.wait_for_timeout(400)
            p07 = frames_dir / "07_new_session.png"
            _shot(page, p07)
            paths.append(p07)

            # 08 recall + citations
            mark("08_recall_citations", "Session B recall")
            _highlight(page, "#messageInput", "#chatLog")
            _send_message(page, "What discount does Acme get and are they VIP?")
            page.wait_for_timeout(900)
            try:
                page.wait_for_selector("#chatLog .cite", timeout=15000)
            except Exception:
                print("  WARNING: citations not visible — continuing")
            _highlight(page, "#chatLog", "#memoryList")
            p08 = frames_dir / "08_recall_citations.png"
            _shot(page, p08)
            paths.append(p08)

            # 09 packer panel + tighter budget
            mark("09_packer_chat", "Packer panel")
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
            _set_range(page, "#budget", 600)
            page.wait_for_timeout(500)
            _highlight(page, "#budget", "#packMeta", "#packList")
            p09 = frames_dir / "09_packer_chat.png"
            _shot(page, p09)
            paths.append(p09)

            # 10 inspector lifecycle tabs
            mark("10_inspector_tabs", "Inspector lifecycle")
            for status in ("superseded", "forgotten", "active"):
                try:
                    page.click(f"#statusTabs .tab[data-status='{status}']")
                    page.wait_for_timeout(550)
                except Exception:
                    pass
            _highlight(page, "#statusTabs", "#memoryList")
            p10 = frames_dir / "10_inspector_tabs.png"
            _shot(page, p10)
            paths.append(p10)

            # 11 Memory Graph
            mark("11_memory_graph", "Memory Graph view")
            _goto_view(page, "memory")
            page.wait_for_timeout(900)
            try:
                page.click("#refreshStats")
                page.wait_for_timeout(800)
            except Exception:
                pass
            _highlight(page, "#nav-memory", "#refreshStats", "#graphSvg")
            p11 = frames_dir / "11_memory_graph.png"
            _shot(page, p11)
            paths.append(p11)

            # 12 graph filters + select memory
            mark("12_graph_filters", "Graph filters & detail")
            for status in ("active", "superseded", "forgotten", "active"):
                try:
                    page.click(f"#graphStatusTabs .tab[data-status='{status}']")
                    page.wait_for_timeout(500)
                except Exception:
                    pass
            try:
                page.locator("#graphMemoryList .memory-card").first.click(timeout=8000)
                page.wait_for_timeout(700)
            except Exception:
                try:
                    # Click first graph node circle if list empty
                    page.locator("#graphSvg circle").first.click(timeout=5000)
                    page.wait_for_timeout(600)
                except Exception:
                    print("  WARNING: no graph memory to select")
            _highlight(page, "#graphStatusTabs", "#graphMemoryList")
            p12 = frames_dir / "12_graph_filters.png"
            _shot(page, p12)
            paths.append(p12)

            # 13 Packer Lab fields
            mark("13_packer_lab_fields", "Packer Lab controls")
            _goto_view(page, "packer")
            page.wait_for_timeout(500)
            page.fill("#packQuery", "What discount does Acme get?")
            _set_range(page, "#labBudget", 800)
            page.select_option("#labAlgo", "type_quota")
            _highlight(page, "#packQuery", "#labBudget", "#labAlgo", "#asOf", "#runPack")
            _focus_field(page, "#packQuery")
            page.wait_for_timeout(350)
            _focus_field(page, "#labBudget")
            page.wait_for_timeout(350)
            _focus_field(page, "#labAlgo")
            page.wait_for_timeout(350)
            _focus_field(page, "#asOf")
            page.wait_for_timeout(400)
            p13 = frames_dir / "13_packer_lab_fields.png"
            _shot(page, p13)
            paths.append(p13)

            # 14 tight budget pack
            mark("14_packer_run_tight", "Tight budget pack")
            _set_range(page, "#labBudget", 400)
            page.click("#runPack")
            page.wait_for_timeout(1400)
            try:
                page.wait_for_function(
                    """() => {
                      const el = document.getElementById('labPackMeta');
                      return el && (el.innerText.includes('Algorithm:') || el.innerText.includes('Error'));
                    }""",
                    timeout=30000,
                )
            except Exception:
                print("  WARNING: Packer Lab tight preview slow — continuing")
            try:
                page.locator("#labPackList .memory-card, #labPackList .pack-item").first.click(timeout=5000)
                page.wait_for_timeout(400)
                page.click("#runExplain")
                page.wait_for_timeout(800)
            except Exception:
                pass
            _highlight(page, "#labBudget", "#labPackMeta", "#labPackList")
            p14 = frames_dir / "14_packer_run_tight.png"
            _shot(page, p14)
            paths.append(p14)

            # 15 wider budget + mmr
            mark("15_packer_run_wide", "Wider budget pack")
            _set_range(page, "#labBudget", 1600)
            page.select_option("#labAlgo", "mmr")
            page.click("#runPack")
            page.wait_for_timeout(1400)
            try:
                page.wait_for_function(
                    """() => {
                      const el = document.getElementById('labPackMeta');
                      return el && (el.innerText.includes('Algorithm:') || el.innerText.includes('Error'));
                    }""",
                    timeout=30000,
                )
            except Exception:
                print("  WARNING: Packer Lab wide preview slow — continuing")
            _highlight(page, "#labBudget", "#labAlgo", "#labPackMeta", "#labPackList")
            p15 = frames_dir / "15_packer_run_wide.png"
            _shot(page, p15)
            paths.append(p15)

            # 16 Policies RBAC / policy tags
            mark("16_policies_rbac", "Policies org & RBAC")
            _goto_view(page, "admin")
            page.wait_for_timeout(500)
            _highlight(page, "#orgId", "#apiKey", "#pingHealth", "#loadPolicyMemories")
            _focus_field(page, "#orgId")
            page.wait_for_timeout(350)
            _focus_field(page, "#apiKey")
            page.wait_for_timeout(350)
            try:
                page.click("#pingHealth")
                page.wait_for_timeout(700)
            except Exception:
                pass
            try:
                page.click("#loadPolicyMemories")
                page.wait_for_timeout(900)
            except Exception:
                pass
            p16 = frames_dir / "16_policies_rbac.png"
            _shot(page, p16)
            paths.append(p16)

            # 17 forget + consolidate
            mark("17_policies_forget", "Forget & consolidate")
            _highlight(page, "#adminForget", "#adminConsolidate")
            try:
                page.click("#adminForget")
                page.wait_for_timeout(1200)
            except Exception as exc:
                print(f"  WARNING: admin forget click: {exc}")
            try:
                page.click("#adminConsolidate")
                page.wait_for_timeout(1200)
            except Exception as exc:
                print(f"  WARNING: admin consolidate click: {exc}")
            p17 = frames_dir / "17_policies_forget.png"
            _shot(page, p17)
            paths.append(p17)

            # 18 close back on chat
            mark("18_close", "Back to Chat close")
            _goto_view(page, "chat")
            page.click("#statusTabs .tab[data-status='active']")
            page.wait_for_timeout(600)
            _highlight(page, "h1", "#nav-chat", "#memoryList")
            p18 = frames_dir / "18_close.png"
            _shot(page, p18)
            paths.append(p18)
            _clear_highlights(page)

            # Dwell so screencast covers closing narration
            page.wait_for_timeout(1500)

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

    if len(paths) < EXPECTED_FRAMES:
        raise RuntimeError(f"Expected {EXPECTED_FRAMES} frames, got {len(paths)}")
    return paths


if __name__ == "__main__":
    out = REPO_ROOT / "demo_video"
    captured = capture_frames(out)
    print(f"captured {len(captured)} frames -> {out / 'frames'}")
