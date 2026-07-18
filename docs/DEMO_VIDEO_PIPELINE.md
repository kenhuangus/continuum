# Continuum demo video pipeline

Build a **product tour** video from the live Continuum UI (Chat → Memory Graph → Packer Lab → Policies):

1. **Playwright** drives real navigation (clicks, typing, new session, packer, forget) and records a **screencast** plus chapter stills  
2. **TTS** narrates each chapter (neural voice preferred)  
3. Audio is sped to **1.8×** via ffmpeg `atempo`  
4. **ffmpeg** muxes screencast (or stills fallback) + narration → `demo_video/continuum_demo.mp4`

Narration and on-screen demo chrome focus on **Continuum the product** — no competition / vendor-track wording.

## One-command run

```powershell
.venv\Scripts\python.exe scripts\demo_video\run_pipeline.py
```

Useful flags:

| Flag | Meaning |
|------|---------|
| `--skip-capture` | Reuse existing `demo_video/frames/` (+ screencast if present) |
| `--skip-tts` | Skip speech; timed silent slides |
| `--silent` | Force silent slideshow |
| `--base-url URL` | Continuum UI/API (default `http://127.0.0.1:8000`) |
| `--speed 1.8` | **Narration speed** (default **1.8**). Applied with ffmpeg `atempo` after TTS |
| `--stills-only` | Assemble from Ken Burns stills (ignore screencast) |
| `--no-video-record` | Capture screenshots only (no Playwright video) |
| `--no-ken-burns` | Static stills instead of mild zoom (stills path) |

If nothing is listening on the base URL, capture starts `uvicorn continuum_api.main:app` with **`CONTINUUM_AUTH_DISABLED=1`**, waits for `/v1/health`, and tears the process down when done.

## Narration speed (1.8×)

Configured as `NARRATION_SPEED = 1.8` in `scripts/demo_video/narration.py` and as the default for `--speed`.

| Stage | Behavior |
|-------|----------|
| TTS generation | Natural-rate synthesis (Qwen / edge-tts / SAPI) |
| Post-process | `scripts/demo_video/audio_speed.py` applies ffmpeg `atempo=1.8` (chains if outside 0.5–2.0) |
| Docs / STATUS | `narration_speed=1.8` written to `demo_video/STATUS.txt` and chapter README |

Override: `--speed 1.5` (or any positive float).

## Voice quality ranking

| Priority | Engine | Notes |
|----------|--------|-------|
| 1 | **Qwen TTS** (`qwen3-tts-flash`) | If `DASHSCOPE_API_KEY` or `QWEN_API_KEY` in `.env` |
| 2 | **edge-tts** (`en-US-JennyNeural`) | Free neural voice; auto-`pip install edge-tts` |
| 3 | Windows SAPI | Robotic — last resort only |
| 4 | Silent | Timed slides from word count |

## Prerequisites

- Python 3.11+ venv: `pip install -e ".[dev]"`
- Playwright Chromium: `playwright install chromium`
- Optional: system `ffmpeg` — else `imageio-ffmpeg`
- Optional: API key for Qwen TTS; otherwise edge-tts is used

## Hardening (capture / assemble)

- Auth-disabled server bootstrap; clear error if port occupied without healthy `/v1/health`
- Retries for page load and empty screenshots
- Selectors match the multi-view console (`#nav-chat`, `#nav-memory`, `#nav-packer`, `#nav-admin`, `#statusTabs`, …)
- Chat waits until send re-enables; packer / graph timeouts warn instead of hard-failing mid-tour when possible
- Screencast assemble failure → automatic stills fallback
- Frame size checks before Ken Burns encode

## Outputs (gitignored binaries)

```
demo_video/
  .gitkeep
  frames/01_hero.png … 11_close.png
  screencast/tour.webm
  audio/beat_01.wav …
  continuum_demo.mp4
  STATUS.txt          # tts_mode + narration_speed=1.8
  CHAPTER_MARKERS.json
  CHAPTERS.md
  README.md
```

Large media under `demo_video/` is gitignored; commit scripts + `docs/DEMO_VIDEO_PIPELINE.md`.

## Story chapters

Source: `scripts/demo_video/narration.py` (`BEATS`). Covers memory OS intro, Session A→B recall with citations, budget packer, Memory Graph, Packer Lab (as-of / explain), Policies (forget / consolidate / RBAC lite), close.

## Layout

| File | Role |
|------|------|
| `run_pipeline.py` | Entrypoint / TTS ranking / **1.8× speed** / assemble |
| `narration.py` | Beat copy + `NARRATION_SPEED` |
| `capture_frames.py` | Playwright tour + screencast |
| `tts_qwen.py` | DashScope intl TTS |
| `tts_edge.py` | edge-tts neural |
| `tts_fallback.py` | Windows SAPI |
| `audio_speed.py` | ffmpeg atempo |
| `assemble_video.py` | Screencast mux or stills concat |
