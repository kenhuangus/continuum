"""edge-tts neural voice (human-like). Prefer over Windows SAPI."""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

# Slightly faster voice; pipeline still applies ffmpeg atempo to hit NARRATION_SPEED.
DEFAULT_VOICE = "en-US-JennyNeural"
# edge-tts rate relative to 1.0; +20% here + pipeline 1.8 atempo would be too fast —
# we keep edge near-natural and apply 1.8x in audio_speed / run_pipeline.
DEFAULT_RATE = "+0%"


class EdgeTTSError(RuntimeError):
    pass


def _ensure_edge_tts() -> None:
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "edge-tts", "-q"],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if proc.returncode != 0:
            raise EdgeTTSError(f"Failed to install edge-tts: {(proc.stderr or '')[-300:]}")
        try:
            import edge_tts  # noqa: F401
        except ImportError as exc:
            raise EdgeTTSError("edge-tts import failed after install") from exc


async def _synthesize_one(text: str, out_path: Path, voice: str, rate: str) -> None:
    import edge_tts

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # edge-tts writes mp3 by default; request wav via communicate + save
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    # Save as mp3 then we may convert — prefer .mp3 temp if wav unsupported
    tmp = out_path.with_suffix(".mp3")
    await communicate.save(str(tmp))
    if not tmp.is_file() or tmp.stat().st_size == 0:
        raise EdgeTTSError(f"edge-tts produced empty file for {out_path.name}")

    # Convert mp3 → wav for assemble_video consistency
    from audio_speed import resolve_ffmpeg

    ffmpeg = resolve_ffmpeg()
    proc = subprocess.run(
        [ffmpeg, "-y", "-i", str(tmp), str(out_path)],
        capture_output=True,
        text=True,
    )
    tmp.unlink(missing_ok=True)
    if proc.returncode != 0 or not out_path.is_file() or out_path.stat().st_size == 0:
        raise EdgeTTSError(f"ffmpeg mp3→wav failed: {(proc.stderr or '')[-400:]}")


def synthesize_to_file(
    text: str,
    out_path: Path,
    *,
    voice: str = DEFAULT_VOICE,
    rate: str = DEFAULT_RATE,
) -> Path:
    _ensure_edge_tts()
    try:
        asyncio.run(_synthesize_one(text, out_path, voice, rate))
    except EdgeTTSError:
        raise
    except Exception as exc:
        raise EdgeTTSError(f"edge-tts failed: {exc}") from exc
    return out_path


def synthesize_beats(
    beats: list[dict],
    audio_dir: Path,
    *,
    voice: str = DEFAULT_VOICE,
) -> list[Path]:
    _ensure_edge_tts()
    paths: list[Path] = []
    for beat in beats:
        out = audio_dir / beat["audio"]
        print(f"  edge-tts {beat['id']} -> {out.name} ({voice})")
        synthesize_to_file(beat["text"], out, voice=voice)
        paths.append(out)
    return paths
