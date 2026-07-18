"""Qwen Cloud international TTS via DashScope multimodal-generation (httpx)."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
INTL_BASE = "https://dashscope-intl.aliyuncs.com/api/v1"
TTS_URL = f"{INTL_BASE}/services/aigc/multimodal-generation/generation"
DEFAULT_MODEL = "qwen3-tts-flash"
DEFAULT_VOICE = "Cherry"


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path(__file__).resolve()).parent
    for _ in range(8):
        if (cur / ".env").exists() or (cur / "pyproject.toml").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return REPO_ROOT


def load_dotenv(repo_root: Path | None = None) -> None:
    root = repo_root or find_repo_root()
    env_path = root / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def get_api_key() -> str | None:
    load_dotenv()
    key = (os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY") or "").strip()
    return key or None


def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


class QwenTTSError(RuntimeError):
    """Raised when Qwen TTS fails (auth, quota, model, network)."""


def synthesize_to_file(
    text: str,
    out_path: Path,
    *,
    voice: str = DEFAULT_VOICE,
    model: str = DEFAULT_MODEL,
    language_type: str = "English",
    timeout_s: float = 60.0,
) -> Path:
    """POST non-streaming TTS; download output.audio.url WAV to out_path."""
    api_key = get_api_key()
    if not api_key:
        raise QwenTTSError("No DASHSCOPE_API_KEY or QWEN_API_KEY in environment / .env")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
            "language_type": language_type,
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(TTS_URL, headers=headers, json=body)
            if resp.status_code >= 400:
                # Never echo Authorization or full key material.
                detail = resp.text[:400].replace(api_key, mask_key(api_key))
                raise QwenTTSError(f"TTS HTTP {resp.status_code}: {detail}")
            data = resp.json()
            # DashScope error envelope
            code = data.get("code") or data.get("status_code")
            if code and str(code) not in ("200", "Success", "None"):
                msg = data.get("message") or data.get("msg") or str(data)[:300]
                raise QwenTTSError(f"TTS API error code={code}: {msg}")

            output = data.get("output") or {}
            audio = output.get("audio") or {}
            audio_url = audio.get("url") if isinstance(audio, dict) else None
            if not audio_url and isinstance(output.get("audio"), str):
                audio_url = output["audio"]
            if not audio_url:
                raise QwenTTSError(f"TTS response missing output.audio.url: {str(data)[:300]}")

            audio_resp = client.get(audio_url, timeout=timeout_s)
            audio_resp.raise_for_status()
            out_path.write_bytes(audio_resp.content)
    except QwenTTSError:
        raise
    except httpx.HTTPError as exc:
        raise QwenTTSError(f"TTS network error: {exc}") from exc

    return out_path


def synthesize_beats(
    beats: list[dict],
    audio_dir: Path,
    *,
    voice: str = DEFAULT_VOICE,
) -> list[Path]:
    """Synthesize each beat; raise QwenTTSError on first failure (caller may fall back)."""
    api_key = get_api_key()
    if api_key:
        print(f"Qwen TTS key present: {mask_key(api_key)} model={DEFAULT_MODEL}")
    paths: list[Path] = []
    for beat in beats:
        out = audio_dir / beat["audio"]
        print(f"  TTS {beat['id']} -> {out.name}")
        synthesize_to_file(beat["text"], out, voice=voice)
        paths.append(out)
    return paths
