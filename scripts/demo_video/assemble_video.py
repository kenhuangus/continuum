"""Assemble demo_video/continuum_demo.mp4 from frames + per-beat audio via ffmpeg."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


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


def resolve_ffprobe(ffmpeg_exe: str) -> str | None:
    # imageio-ffmpeg may only ship ffmpeg; try sibling / PATH.
    probe = shutil.which("ffprobe")
    if probe:
        return probe
    sibling = Path(ffmpeg_exe).with_name("ffprobe.exe" if Path(ffmpeg_exe).suffix == ".exe" else "ffprobe")
    if sibling.is_file():
        return str(sibling)
    return None


def audio_duration_seconds(audio_path: Path, ffmpeg_exe: str, ffprobe_exe: str | None) -> float:
    if ffprobe_exe:
        proc = subprocess.run(
            [
                ffprobe_exe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout:
            try:
                data = json.loads(proc.stdout)
                dur = float(data.get("format", {}).get("duration", 0) or 0)
                if dur > 0:
                    return dur
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    # Fallback: ffmpeg -i stderr parse
    proc = subprocess.run(
        [ffmpeg_exe, "-i", str(audio_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    import re

    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", proc.stderr or "")
    if m:
        h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return h * 3600 + mi * 60 + s
    # Last resort: word-count estimate from sibling narration not available — use 10s
    return 10.0


def estimate_duration_from_text(text: str) -> float:
    """Silent-slide duration: ~0.4s/word, floored at 8s (brief: 8–12s or word estimate)."""
    words = max(1, len(text.split()))
    return max(8.0, words * 0.4)


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-800:]
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {err}")


def assemble_video(
    beats: list[dict],
    out_dir: Path,
    *,
    silent: bool = False,
    ken_burns: bool = True,
    output_name: str = "continuum_demo.mp4",
) -> Path:
    """Build mp4: one clip per beat (image + audio or timed still), then concat."""
    ffmpeg = resolve_ffmpeg()
    ffprobe = resolve_ffprobe(ffmpeg)
    frames_dir = out_dir / "frames"
    audio_dir = out_dir / "audio"
    output = out_dir / output_name
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="continuum_demo_") as tmp:
        tmp_path = Path(tmp)
        clip_paths: list[Path] = []

        for i, beat in enumerate(beats, start=1):
            frame = frames_dir / beat["frame"]
            if not frame.is_file():
                raise FileNotFoundError(f"Missing frame: {frame}")

            clip = tmp_path / f"clip_{i:02d}.mp4"
            audio = audio_dir / beat["audio"]

            if silent or not audio.is_file():
                dur = estimate_duration_from_text(beat["text"])
                # Static still for silent / missing audio
                _run(
                    [
                        ffmpeg,
                        "-y",
                        "-loop",
                        "1",
                        "-i",
                        str(frame),
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-t",
                        f"{dur:.3f}",
                        "-c:v",
                        "libx264",
                        "-tune",
                        "stillimage",
                        "-pix_fmt",
                        "yuv420p",
                        "-c:a",
                        "aac",
                        "-shortest",
                        str(clip),
                    ]
                )
            else:
                dur = audio_duration_seconds(audio, ffmpeg, ffprobe)
                if ken_burns:
                    # Mild zoom: d = frames at 25fps for this beat's audio length.
                    frames = max(25, int(dur * 25))
                    vf = (
                        "scale=2800:-1,"
                        f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':"
                        f"y='ih/2-(ih/zoom/2)':d={frames}:s=1400x900:fps=25,"
                        "format=yuv420p"
                    )
                    _run(
                        [
                            ffmpeg,
                            "-y",
                            "-loop",
                            "1",
                            "-i",
                            str(frame),
                            "-i",
                            str(audio),
                            "-vf",
                            vf,
                            "-c:v",
                            "libx264",
                            "-c:a",
                            "aac",
                            "-t",
                            f"{dur:.3f}",
                            "-shortest",
                            "-pix_fmt",
                            "yuv420p",
                            str(clip),
                        ]
                    )
                else:
                    _run(
                        [
                            ffmpeg,
                            "-y",
                            "-loop",
                            "1",
                            "-i",
                            str(frame),
                            "-i",
                            str(audio),
                            "-c:v",
                            "libx264",
                            "-tune",
                            "stillimage",
                            "-c:a",
                            "aac",
                            "-pix_fmt",
                            "yuv420p",
                            "-shortest",
                            str(clip),
                        ]
                    )
            clip_paths.append(clip)

        list_file = tmp_path / "concat.txt"
        list_file.write_text(
            "\n".join(f"file '{c.resolve().as_posix()}'" for c in clip_paths) + "\n",
            encoding="utf-8",
        )
        _run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_file),
                "-c",
                "copy",
                str(output),
            ]
        )

    return output
