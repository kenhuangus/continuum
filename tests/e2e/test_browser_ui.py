"""Playwright e2e regression — sequential happy-path ported from evals/browser_ui_test.py."""
from __future__ import annotations

import time
from typing import Any

import pytest

pytestmark = pytest.mark.e2e

# Avoid importing playwright at collection time so `pytest -m unit` works without it.
playwright = pytest.importorskip("playwright.sync_api", reason="playwright not installed")
expect = playwright.expect
Page = Any


@pytest.fixture(scope="module")
def unique_ws() -> str:
    return f"ui-test-{int(time.time())}"


@pytest.fixture(scope="module")
def ui(browser, e2e_server: str, unique_ws: str):
    """One shared page for the ordered UI flow (matches original sequential suite)."""
    context = browser.new_context(viewport={"width": 1400, "height": 900})
    page = context.new_page()
    console_errors: list[str] = []
    page_errors: list[str] = []
    page.on(
        "console",
        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
    )
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    page.goto(e2e_server + "/", wait_until="networkidle", timeout=30000)
    state = {
        "page": page,
        "console_errors": console_errors,
        "page_errors": page_errors,
        "unique_ws": unique_ws,
        "base": e2e_server,
    }
    yield state
    context.close()


class TestBrowserUIRegression:
    """Ordered UI flow sharing module-scoped page state (definition order = run order)."""

    def test_load_ui(self, ui: dict):
        page = ui["page"]
        expect(page.locator("h1")).to_have_text("Continuum")

    def test_memory_inspector_present(self, ui: dict):
        page = ui["page"]
        page.wait_for_selector("#memoryList", timeout=5000)

    def test_session_field_readonly(self, ui: dict):
        page = ui["page"]
        page.fill("#workspaceId", ui["unique_ws"])
        page.evaluate("document.getElementById('sessionId').value = 'session-a'")
        assert page.locator("#sessionId").get_attribute("readonly") is not None

    def test_session_a_remember(self, ui: dict):
        page = ui["page"]
        msgs_a = [
            "Remember: Acme is a VIP customer.",
            "Remember: Approved 12% discount for Acme through end of 2026.",
            "Remember: Acme prefers email communication over phone.",
        ]
        for msg in msgs_a:
            page.fill("#messageInput", msg)
            page.click("#sendBtn")
            page.wait_for_function(
                """() => {
                  const log = document.getElementById('chatLog');
                  return log && log.querySelectorAll('.msg').length >= 1;
                }""",
                timeout=60000,
            )
            page.wait_for_timeout(800)

    def test_active_memories_after_session_a(self, ui: dict):
        page = ui["page"]
        page.click(".tab[data-status='active']")
        page.wait_for_timeout(500)
        count = page.locator("#memoryList .memory-card").count()
        assert count >= 1, f"expected active memories, count={count}"

    def test_new_session_changes_id(self, ui: dict):
        page = ui["page"]
        page.click("#newSession")
        page.wait_for_timeout(300)
        sid = page.input_value("#sessionId")
        assert sid != "session-a", f"session={sid}"

    def test_session_b_recall_and_pack(self, ui: dict):
        page = ui["page"]
        page.fill("#messageInput", "What discount does Acme get and are they VIP?")
        page.click("#sendBtn")
        page.wait_for_timeout(2500)
        pack_meta = page.locator("#packMeta").inner_text()
        assert "Algorithm:" in pack_meta, f"pack_meta={pack_meta!r}"

    def test_budget_slider_updates_label(self, ui: dict):
        page = ui["page"]
        page.locator("#budget").evaluate(
            "el => { el.value = '300'; el.dispatchEvent(new Event('input')); }"
        )
        bv = page.locator("#budgetVal").inner_text()
        assert bv == "300", f"budgetVal={bv}"

    def test_low_budget_pack(self, ui: dict):
        page = ui["page"]
        page.fill("#messageInput", "Summarize Acme commercial terms.")
        page.click("#sendBtn")
        page.wait_for_timeout(2000)
        meta = page.locator("#packMeta").inner_text()
        assert "300" in meta or "Tokens:" in meta, meta

    def test_tabs_superseded_forgotten_active(self, ui: dict):
        page = ui["page"]
        for status in ("superseded", "forgotten", "active"):
            page.click(f".tab[data-status='{status}']")
            page.wait_for_timeout(400)
            active_tab = page.locator(".tab.active").get_attribute("data-status")
            assert active_tab == status, f"active={active_tab}"

    def test_forget_pass_message(self, ui: dict):
        page = ui["page"]
        page.click("#forgetPass")
        page.wait_for_timeout(1000)
        log = page.locator("#chatLog").inner_text()
        assert "Forgetting pass:" in log, log[-150:]

    def test_empty_message_noop(self, ui: dict):
        page = ui["page"]
        before = page.locator("#chatLog .msg.user").count()
        page.fill("#messageInput", "   ")
        page.click("#sendBtn")
        page.wait_for_timeout(300)
        after = page.locator("#chatLog .msg.user").count()
        assert after == before, f"before={before} after={after}"

    def test_enter_key_sends(self, ui: dict):
        page = ui["page"]
        page.fill("#messageInput", "Remember: contact Jordan at Acme.")
        page.press("#messageInput", "Enter")
        page.wait_for_timeout(2000)
        log = page.locator("#chatLog").inner_text()
        assert "Jordan" in log or "contact" in log.lower() or "Remember" in log

    def test_workspace_isolation_empty(self, ui: dict):
        page = ui["page"]
        page.fill("#workspaceId", "empty-workspace-xyz")
        page.click(".tab[data-status='active']")
        page.wait_for_timeout(500)
        page.click("#newSession")
        page.wait_for_timeout(500)
        count = page.locator("#memoryList .memory-card").count()
        assert count == 0, f"count={count}"

    def test_xss_innerhtml_memory_cards(self, ui: dict):
        page = ui["page"]
        page.fill("#workspaceId", ui["unique_ws"])
        page.click("#newSession")
        page.wait_for_timeout(300)
        payload = "<img src=x onerror=alert(1)> Remember: XSS probe tag"
        page.fill("#messageInput", payload)
        page.click("#sendBtn")
        page.wait_for_timeout(2000)
        imgs = page.locator("#memoryList img").count()
        assert imgs == 0, f"img_tags_in_memory_list={imgs} (0 expected if escaped)"

    def test_rapid_double_send_no_crash(self, ui: dict):
        page = ui["page"]
        page.fill("#workspaceId", ui["unique_ws"])
        page.fill("#messageInput", "Remember: rapid fire one")
        page.click("#sendBtn")
        page.fill("#messageInput", "Remember: rapid fire two")
        page.click("#sendBtn")
        page.wait_for_timeout(3000)
        assert len(ui["page_errors"]) == 0, f"page_errors={ui['page_errors']}"

    def test_api_error_handled_gracefully(self, ui: dict):
        page = ui["page"]
        before_len = len(page.locator("#chatLog").inner_text())
        page.evaluate(
            """() => {
              window.__oldFetch = window.fetch;
              window.fetch = async (...args) => {
                window.fetch = window.__oldFetch;
                return new Response(JSON.stringify({detail: 'boom'}), {status: 500});
              };
            }"""
        )
        page.fill("#messageInput", "trigger-api-failure-now")
        page.click("#sendBtn")
        page.wait_for_timeout(1200)
        log = page.locator("#chatLog").inner_text()
        new_part = log[before_len:]
        shows_undefined = "undefined" in new_part.lower()
        shows_error = "Error:" in new_part and ("500" in new_part or "boom" in new_part)
        assert shows_error and not shows_undefined, f"new_part={new_part[-200:]!r}"

    def test_citations_visible_in_ui(self, ui: dict):
        page = ui["page"]
        page.fill("#workspaceId", ui["unique_ws"])
        page.click("#newSession")
        page.wait_for_timeout(200)
        page.fill("#messageInput", "What is Acme discount?")
        page.click("#sendBtn")
        page.wait_for_timeout(2500)
        html = page.locator("#chatLog").inner_html()
        text = page.locator("#chatLog").inner_text()
        assert 'class="cite"' in html or "Citations:" in text

    def test_no_severe_console_errors(self, ui: dict):
        real_errs = [e for e in ui["console_errors"] if "fonts.googleapis" not in e]
        assert len(real_errs) == 0, f"errors={real_errs[:5]}"
