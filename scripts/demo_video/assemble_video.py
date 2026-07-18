"""Assemble demo_video/continuum_demo.mp4 from frames (+ optional screencast) + audio."""
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
    return 10.0


def estimate_duration_from_text(text: str) -> float:
    words = max(1, len(text.split()))
    return max(5.0, words * 0.22)


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-1000:]
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {err}")


def _find_screencast(out_dir: Path) -> Path | None:
    markers = out_dir / "CHAPTER_MARKERS.json"
    if markers.is_file():
        try:
            data = json.loads(markers.read_text(encoding="utf-8"))
            sc = data.get("screencast")
            if sc and Path(sc).is_file() and Path(sc).stat().st_size > 1000:
                return Path(sc)
        except (json.JSONDecodeError, OSError):
            pass
    cand = out_dir / "screencast" / "tour.webm"
    if cand.is_file() and cand.stat().st_size > 1000:
        return cand
    sc_dir = out_dir / "screencast"
    if sc_dir.is_dir():
        webms = sorted(sc_dir.glob("*.webm"), key=lambda p: p.stat().st_mtime, reverse=True)
        for w in webms:
            if w.stat().st_size > 1000:
                return w
    return None


def _video_duration(path: Path, ffmpeg_exe: str, ffprobe_exe: str | None) -> float:
    if ffprobe_exe:
        proc = subprocess.run(
            [
                ffprobe_exe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout:
            try:
                return float(json.loads(proc.stdout).get("format", {}).get("duration") or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    return audio_duration_seconds(path, ffmpeg_exe, ffprobe_exe)


def assemble_from_screencast(
    beats: list[dict],
    out_dir: Path,
    screencast: Path,
    *,
    silent: bool = False,
    output_name: str = "continuum_demo.mp4",
) -> Path:
    """Mux full screencast with concatenated chapter audio (pad/trim video to audio length)."""
    ffmpeg = resolve_ffmpeg()
    ffprobe = resolve_ffprobe(ffmpeg)
    audio_dir = out_dir / "audio"
    output = out_dir / output_name

    with tempfile.TemporaryDirectory(prefix="continuum_sc_") as tmp:
        tmp_path = Path(tmp)
        concat_list = tmp_path / "audio_concat.txt"
        lines: list[str] = []
        for beat in beats:
            ap = audio_dir / beat["audio"]
            if silent or not ap.is_file():
                dur = estimate_duration_from_text(beat["text"])
                sil = tmp_path / f"sil_{beat['id']}.wav"
                _run(
                    [
                        ffmpeg,
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=24000:cl=mono",
                        "-t",
                        f"{dur:.3f}",
                        str(sil),
                    ]
                )
                lines.append(f"file '{sil.resolve().as_posix()}'")
            else:
                lines.append(f"file '{ap.resolve().as_posix()}'")
        concat_list.write_text("\n".join(lines) + "\n", encoding="utf-8")
        full_audio = tmp_path / "full_narration.wav"
        _run(
            [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(full_audio),
            ]
        )

        scaled = tmp_path / "scaled.mp4"
        _run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(screencast),
                "-vf",
                "scale=1440:900:force_original_aspect_ratio=decrease,"
                "pad=1440:900:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p",
                "-an",
                str(scaled),
            ]
        )

        vid_dur = _video_duration(scaled, ffmpeg, ffprobe)
        audio_dur = audio_duration_seconds(full_audio, ffmpeg, ffprobe)
        if vid_dur > 0 and vid_dur < audio_dur - 0.15:
            pad = audio_dur - vid_dur
            padded = tmp_path / "padded.mp4"
            _run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(scaled),
                    "-vf",
                    f"tpad=stop_mode=clone:stop_duration={pad:.3f}",
                    "-an",
                    str(padded),
                ]
            )
            scaled = padded

        _run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(scaled),
                "-i",
                str(full_audio),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(output),
            ]
        )

    return output


def assemble_video(
    beats: list[dict],
    out_dir: Path,
    *,
    silent: bool = False,
    ken_burns: bool = True,
    output_name: str = "continuum_demo.mp4",
    prefer_screencast: bool = True,
) -> Path:
    """Build mp4: prefer screencast+narration; else per-beat stills + audio."""
    if prefer_screencast:
        sc = _find_screencast(out_dir)
        if sc is not None:
            print(f"  Assembling from screencast: {sc}")
            try:
                return assemble_from_screencast(
                    beats, out_dir, sc, silent=silent, output_name=output_name
                )
            except Exception as exc:
                print(f"  Screencast assemble failed ({exc}); falling back to stills")

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
            if frame.stat().st_size < 1000:
                raise RuntimeError(f"Frame too small (capture bug?): {frame}")

            clip = tmp_path / f"clip_{i:02d}.mp4"
            audio = audio_dir / beat["audio"]

            if silent or not audio.is_file():
                dur = estimate_duration_from_text(beat["text"])
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
                    frames_n = max(25, int(dur * 25))
                    vf = (
                        "scale=2880:-1,"
                        f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':"
                        f"y='ih/2-(ih/zoom/2)':d={frames_n}:s=1440x900:fps=25,"
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
