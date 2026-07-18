"""Speed audio to target rate via ffmpeg atempo (chains for rates outside 0.5–2.0)."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def resolve_ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except ImportError:
        subprocess.run(
            [__import__("sys").executable, "-m", "pip", "install", "imageio-ffmpeg", "-q"],
            check=False,
        )
        import imageio_ffmpeg  # type: ignore

    return imageio_ffmpeg.get_ffmpeg_exe()


def atempo_filter(speed: float) -> str:
    """Build ffmpeg atempo chain. Each atempo must be in [0.5, 2.0]."""
    if speed <= 0:
        raise ValueError("speed must be positive")
    parts: list[str] = []
    remaining = float(speed)
    # Factor into 0.5–2.0 pieces
    while remaining > 2.0 + 1e-9:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.6g}")
    return ",".join(parts)


def speed_audio_file(src: Path, dst: Path, speed: float = 1.8) -> Path:
    """Rewrite audio at `speed` using ffmpeg atempo. dst may equal src (atomic replace)."""
    if abs(speed - 1.0) < 1e-6:
        if src.resolve() != dst.resolve():
            dst.write_bytes(src.read_bytes())
        return dst

    ffmpeg = resolve_ffmpeg()
    dst.parent.mkdir(parents=True, exist_ok=True)
    af = atempo_filter(speed)

    with tempfile.NamedTemporaryFile(suffix=dst.suffix or ".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(src),
                "-filter:a",
                af,
                "-vn",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not tmp_path.is_file() or tmp_path.stat().st_size == 0:
            err = (proc.stderr or proc.stdout or "")[-600:]
            raise RuntimeError(f"ffmpeg atempo failed ({proc.returncode}): {err}")
        tmp_path.replace(dst)
    finally:
        if tmp_path.exists() and tmp_path.resolve() != dst.resolve():
            tmp_path.unlink(missing_ok=True)

    return dst


def speed_beats_in_dir(audio_dir: Path, beats: list[dict], speed: float = 1.8) -> None:
    """Apply speed in-place to each beat audio file that exists."""
    for beat in beats:
        path = audio_dir / beat["audio"]
        if path.is_file() and path.stat().st_size > 0:
            print(f"  atempo x{speed} {path.name}")
            speed_audio_file(path, path, speed=speed)
