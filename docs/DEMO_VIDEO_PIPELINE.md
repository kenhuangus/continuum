# Continuum demo video pipeline

Build a ≤3 minute Track 1 (MemoryAgent) demo video from the live Continuum UI:

1. **Playwright** captures eight happy-path screenshots  
2. **Qwen Cloud TTS** (`qwen3-tts-flash`) narrates each beat (free-quota eligible, sync/non-streaming)  
3. **ffmpeg** assembles frames + audio into `demo_video/continuum_demo.mp4`

Alibaba Cloud **deploy** is out of scope for this pipeline — narration mentions Qwen Cloud APIs only.

## One-command run

From the repo root (with `.venv` and deps installed):

```powershell
.venv\Scripts\python.exe scripts\demo_video\run_pipeline.py
```

Useful flags:

| Flag | Meaning |
|------|---------|
| `--skip-capture` | Reuse existing `demo_video/frames/` |
| `--skip-tts` | Skip speech; timed silent slides |
| `--silent` | Force silent slideshow |
| `--base-url URL` | Continuum UI/API (default `http://127.0.0.1:8000`) |
| `--no-ken-burns` | Static stills instead of mild zoom |

If nothing is listening on the base URL, the capture step starts `uvicorn continuum_api.main:app` with `CONTINUUM_AUTH_DISABLED=1` (same PYTHONPATH pattern as `tests/conftest.py`), waits for `/v1/health`, and tears the process down when done.

## Prerequisites

- Python 3.11+ project venv: `pip install -e ".[dev]"`
- Playwright Chromium: `playwright install chromium`
- Optional: system `ffmpeg` on PATH — otherwise the assembler uses `imageio-ffmpeg` (auto-`pip install` if missing)
- Optional: `DASHSCOPE_API_KEY` or `QWEN_API_KEY` in gitignored `.env` for Qwen TTS
- Optional: `pyttsx3` for a smoother Windows SAPI fallback (PowerShell `System.Speech` is used if pyttsx3 is absent)

## Qwen Cloud international TTS

| Item | Value |
|------|--------|
| Model | `qwen3-tts-flash` (sync / non-streaming; free-quota eligible) |
| Endpoint | `POST https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation` |
| SDK base URL | `https://dashscope-intl.aliyuncs.com/api/v1` |
| Auth | `Authorization: Bearer $DASHSCOPE_API_KEY` |

Example body:

```json
{
  "model": "qwen3-tts-flash",
  "input": {
    "text": "Continuum remembers across sessions.",
    "voice": "Cherry",
    "language_type": "English"
  }
}
```

Non-streaming responses include `output.audio.url` (WAV, URL typically expires in ~24h). The pipeline downloads each URL to `demo_video/audio/beat_01.wav` … `beat_08.wav`.

Docs:

- [Qwen TTS developer guide](https://docs.qwencloud.com/developer-guides/speech/tts)
- [Alibaba Model Studio Qwen-TTS API](https://www.alibabacloud.com/help/en/model-studio/qwen-tts-api)

This pipeline uses raw **httpx** against the intl endpoint — no DashScope SDK required, and **no paid Wan video models**.

## Fallback behavior

| Stage | Failure | Fallback |
|-------|---------|----------|
| Qwen TTS | Missing key, HTTP/quota/model error | Windows SAPI (`pyttsx3` or PowerShell `System.Speech`) |
| SAPI | Not available / synthesize error | Silent slideshow (~8–12s per slide from word count) |
| ffmpeg | Not on PATH | `imageio_ffmpeg.get_ffmpeg_exe()` (install `imageio-ffmpeg` if needed) |

`demo_video/STATUS.txt` records `tts_mode=qwen|sapi|silent` plus a short note. API keys are never printed in full (masked to first/last 4 chars when presence is logged).

## Outputs (gitignored binaries)

```
demo_video/
  .gitkeep
  frames/01_hero.png … 08_forget_or_tabs.png
  audio/beat_01.wav … beat_08.wav
  continuum_demo.mp4
  STATUS.txt
```

Large media under `demo_video/` is gitignored; commit only `.gitkeep` and the scripts/docs.

## Story beats (Track 1)

Aligned with `docs/HACKATHON_SUBMIT.md` (~2:45–3:00):

1. Problem — agents forget across sessions  
2–4. Session A — VIP, discount, email preference + memory inspector  
5. New session (clean chat)  
6. Session B — recall discount / VIP  
7. Packer panel under budget  
8. Forgetting / supersession + Qwen Cloud / open Memory OS CTA  

Script source: `scripts/demo_video/narration.py` (`BEATS`).

## Layout

| File | Role |
|------|------|
| `scripts/demo_video/run_pipeline.py` | Entrypoint / orchestration |
| `narration.py` | Beat copy |
| `capture_frames.py` | Playwright screenshots |
| `tts_qwen.py` | DashScope intl TTS |
| `tts_fallback.py` | Windows SAPI |
| `assemble_video.py` | ffmpeg Ken Burns / concat |
