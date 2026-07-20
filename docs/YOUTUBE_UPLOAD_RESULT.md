# YouTube Upload Result — Continuum demo

**Date:** 2026-07-20 00:33 (local)  
**Status:** **URL READY — Devpost submit BLOCKED (no MCP browser tab)**

## Constraint compliance

- Did **not** spawn Chrome / Chromium / Playwright.
- Used **cursor-ide-browser MCP only**.

## Browser attempt (submit session)

| Step | Result |
|------|--------|
| `browser_tabs` list | **Empty** at start |
| `browser_navigate` | Failed: *No browser tab available* |
| `browser_tabs` new (+ active/side) | Tab metadata returned briefly, then **vanished** (`list` empty; navigate with viewId → *Browser view not found*) |
| Devpost Submit | **No** — automation blocked |

## YouTube URL

**https://youtu.be/OftGzFIvAAs**

## Devpost submit result

| Item | Value |
|------|--------|
| Submitted? | **No** |
| Confirmation URL | *none* — draft still expected at manage URL below |
| Manage draft | https://devpost.com/submit-to/29966-global-ai-hackathon-series-with-qwen-cloud/manage/submissions/1106234-continuum/ |

## Next step

Open the Continuum Devpost draft in **this chat’s Browser panel** (so `browser_tabs` list shows a live Devpost tab), stay logged in, then re-run submit automation:

1. Paste video: `https://youtu.be/OftGzFIvAAs`
2. Try-it: `https://continuum-8hwx.onrender.com/`
3. Built With includes **Qwen Cloud**; repo `https://github.com/kenhuangus/continuum`
4. Complete Additional info → check terms → **Submit project**
5. Confirm status is **Submitted** (not DRAFT)
