"""Assemble demo_video/continuum_demo.mp4 from per-chapter frames + audio (sync-correct).

Correct model (priority #1 — A/V sync):
  For each chapter i: visual lasting exactly duration(audio_i), then concat in order.

Continuous Playwright screencast must NOT be muxed against chapter narration: capture
wall-clock chapter markers are ~1–2s apart while TTS chapters are many seconds each,
so screencast+concat-audio always desyncs. Screencast remains an optional artifact only.
"""
from __future__ import annotations

import json
import re
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
    sibling = Path(ffmpeg_exe).with_name(
        "ffprobe.exe" if Path(ffmpeg_exe).suffix == ".exe" else "ffprobe"
    )
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
    """DEPRECATED for product demos — continuous screencast ≠ chapter audio timeline.

    Kept only for experiments. Prefer assemble_video(..., prefer_screencast=False).
    """
    print(
        "  WARNING: screencast mux ignores per-chapter sync "
        "(capture wall-clock ≠ TTS durations). Prefer stills."
    )
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


def _make_chapter_clip(
    *,
    ffmpeg: str,
    ffprobe: str | None,
    frame: Path,
    audio: Path | None,
    text: str,
    clip: Path,
    silent: bool,
    ken_burns: bool,
) -> float:
    """Build one chapter mp4 lasting exactly audio (or estimated) duration. Returns duration used."""
    if silent or audio is None or not audio.is_file():
        dur = estimate_duration_from_text(text)
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
                f"{dur:.6f}",
                "-vf",
                "scale=1440:900:force_original_aspect_ratio=decrease,"
                "pad=1440:900:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p",
                "-c:v",
                "libx264",
                "-tune",
                "stillimage",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-shortest",
                str(clip),
            ]
        )
        return dur

    dur = audio_duration_seconds(audio, ffmpeg, ffprobe)
    # Lock video length to audio: -t on output + -shortest; pad audio with apad if needed
    if ken_burns:
        frames_n = max(25, int(round(dur * 25)))
        vf = (
            "scale=2880:-1,"
            f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={frames_n}:s=1440x900:fps=25,"
            "format=yuv420p"
        )
    else:
        vf = (
            "scale=1440:900:force_original_aspect_ratio=decrease,"
            "pad=1440:900:(ow-iw)/2:(oh-ih)/2,fps=25,format=yuv420p"
        )

    _run(
        [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-framerate",
            "25",
            "-i",
            str(frame),
            "-i",
            str(audio),
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-t",
            f"{dur:.6f}",
            "-shortest",
            str(clip),
        ]
    )

    # Verify and re-encode with tpad if video short (zoompan edge cases)
    got = _video_duration(clip, ffmpeg, ffprobe)
    if got > 0 and abs(got - dur) >= 0.12:
        fixed = clip.with_suffix(".fix.mp4")
        if got < dur - 0.05:
            pad = dur - got
            _run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(clip),
                    "-i",
                    str(audio),
                    "-filter_complex",
                    f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.6f}[v];"
                    f"[1:a]apad=whole_dur={dur:.6f}[a]",
                    "-map",
                    "[v]",
                    "-map",
                    "[a]",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    "-t",
                    f"{dur:.6f}",
                    str(fixed),
                ]
            )
        else:
            _run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(clip),
                    "-t",
                    f"{dur:.6f}",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    str(fixed),
                ]
            )
        fixed.replace(clip)

    return dur


def assemble_video(
    beats: list[dict],
    out_dir: Path,
    *,
    silent: bool = False,
    ken_burns: bool = True,
    output_name: str = "continuum_demo.mp4",
    prefer_screencast: bool = False,
) -> Path:
    """Build mp4 from per-beat stills timed to audio (sync-correct). Screencast opt-in only."""
    if prefer_screencast:
        sc = _find_screencast(out_dir)
        if sc is not None:
            print(f"  Assembling from screencast (NOT sync-safe): {sc}")
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

    qa_clips = out_dir / "_qa_clips"
    if qa_clips.is_dir():
        shutil.rmtree(qa_clips, ignore_errors=True)
    qa_clips.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="continuum_demo_") as tmp:
        tmp_path = Path(tmp)
        clip_paths: list[Path] = []
        chapter_meta: list[dict] = []

        for i, beat in enumerate(beats, start=1):
            frame = frames_dir / beat["frame"]
            if not frame.is_file():
                raise FileNotFoundError(f"Missing frame: {frame}")
            if frame.stat().st_size < 1000:
                raise RuntimeError(f"Frame too small (capture bug?): {frame}")

            clip = tmp_path / f"clip_{i:02d}.mp4"
            audio = audio_dir / beat["audio"]
            dur = _make_chapter_clip(
                ffmpeg=ffmpeg,
                ffprobe=ffprobe,
                frame=frame,
                audio=audio if audio.is_file() else None,
                text=beat["text"],
                clip=clip,
                silent=silent,
                ken_burns=ken_burns,
            )
            # Persist for QA
            persisted = qa_clips / f"clip_{i:02d}.mp4"
            shutil.copy2(clip, persisted)
            clip_paths.append(clip)
            chapter_meta.append(
                {
                    "id": beat["id"],
                    "index": i,
                    "audio": beat["audio"],
                    "frame": beat["frame"],
                    "duration_s": round(dur, 6),
                    "clip": str(persisted.name),
                }
            )
            print(f"  Chapter {i:02d} {beat['id']}: visual={dur:.3f}s (= audio)")

        # Re-encode concat (not stream copy) so timestamps stay contiguous and A/V aligned
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
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "44100",
                "-ac",
                "2",
                "-movflags",
                "+faststart",
                str(output),
            ]
        )

    (out_dir / "CHAPTER_TIMING.json").write_text(
        json.dumps({"chapters": chapter_meta, "output": output_name}, indent=2),
        encoding="utf-8",
    )
    return output
