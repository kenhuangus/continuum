---
name: active-chrome-browser-automation
description: >-
  Drive the user's already-open, logged-in Google Chrome on Windows via
  pywinauto UIA + chrome.exe URL open + PrintWindow screenshots. Use when
  cursor-ide-browser MCP tabs are empty, CDP is blocked, or the agent must
  reuse an existing Chrome profile for Render, Devpost, dashboards, or
  form submit without launching an anonymous browser.
---

# Active Chrome Browser Automation (Windows UIA)

## When to use

Use this pattern when:

- The user says a site is **already open and logged in** in their real Chrome
- `cursor-ide-browser` returns empty tabs / "No browser tab available"
- Chrome has **no** `--remote-debugging-port` (CDP connect fails)
- Mouse/`SetCursorPos` / ImageGrab fail under the agent session

**Do not** open a brand-new anonymous Playwright/Chromium profile for login-gated sites.

## Method that worked (Render Continuum deploy)

Proven in Continuum Render Blueprint deploy (`continuum-8hwx.onrender.com`):

1. **Navigate:** `subprocess.Popen([chrome.exe, url])` — reuses the Default profile session
2. **Find window:** `EnumWindows` → score HWND by title (`Render`, `Devpost`, etc.)
3. **Inspect:** `pywinauto` `Desktop(backend="uia").window(handle=hwnd).descendants()`
4. **Type:** `Edit.set_edit_text()` / `iface_value.SetValue()` (not pixel typing)
5. **Click:** `element.invoke()` / ComboBox `select("Option")` — **prefer UIA over mouse**
6. **Screenshot:** `ctypes.windll.user32.PrintWindow(hwnd, hdc, 2)` (PW_RENDERFULLCONTENT)

### What failed (do not retry first)

| Approach | Result |
|----------|--------|
| cursor-ide-browser MCP | Empty tabs; created tabs vanish |
| Playwright `connect_over_cdp(9222)` | CDP not enabled on running Chrome |
| Kill Chrome + relaunch with CDP | Disrupts session; restore dialogs; fragile |
| Playwright persistent context on User Data | Profile lock conflicts with running Chrome |
| `pyautogui` / `SetCursorPos` clicks | Often blocked; clicks miss |

## Minimal recipe

```python
import subprocess, time, ctypes
import win32gui, win32ui
from PIL import Image
from pywinauto import Desktop

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

def find_hwnd(prefer: str) -> int:
    best = None
    def eh(hwnd, _):
        nonlocal best
        if not win32gui.IsWindowVisible(hwnd):
            return True
        title = win32gui.GetWindowText(hwnd) or ""
        if "Chrome" not in title:
            return True
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        if r - l < 600:
            return True
        score = 300 if prefer.lower() in title.lower() else 10
        if best is None or score > best[2]:
            best = (hwnd, title, score)
        return True
    win32gui.EnumWindows(eh, None)
    if not best:
        raise SystemExit("NO_CHROME")
    return best[0]

def open_url(url: str, wait: float = 8) -> None:
    subprocess.Popen([CHROME, url], close_fds=True)
    time.sleep(wait)

def invoke_named(hwnd, substr: str) -> bool:
    win = Desktop(backend="uia").window(handle=hwnd)
    for e in win.descendants():
        try:
            name = (e.window_text() or "").strip()
            ctype = e.element_info.control_type
        except Exception:
            continue
        if substr.lower() in name.lower() and ctype in {
            "Button", "Hyperlink", "CheckBox", "ListItem", "ComboBox"
        }:
            e.invoke()
            return True
    return False
```

## File upload (Open dialog)

1. UIA-invoke the page **"Add file"** / **"Choose File"** button
2. Find top-level window titled `Open` via `EnumWindows` / `Desktop.windows()`
3. Set the **File name** Edit to the absolute path (`set_edit_text`)
4. Invoke the dialog **Open** button
5. Always `close()` stray Open dialogs before the next upload

Avoid `send_keys` for Windows paths — backslashes are modifiers in pywinauto.

## Devpost / Render notes

- Prefer **direct manage URLs** after draft exists (e.g. `.../additional-info/edit`)
- ComboBox options must be probed (`expand` + ListItem children); guess strings fail
- Dismiss Chrome **"Restore pages?"** if present before interacting
- Confirm success by UIA dump: **Submitted** and **not** `DRAFT`

## Project scripts (examples)

- `scripts/_render_invoke_deploy.py` — Render Blueprint deploy via UIA
- `scripts/_devpost_complete_submit.py` / `_devpost_fill_additional.py` — Devpost fill

## Dependencies

`pywinauto`, `pywin32`, `Pillow` (and optionally `pyautogui` only as last resort).
