"""Orchestrate Continuum demo-video pipeline: capture → TTS → 1.8x speed → ffmpeg assemble."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from assemble_video import assemble_video  # noqa: E402
from audio_speed import speed_beats_in_dir  # noqa: E402
from capture_frames import DEFAULT_BASE_URL, capture_frames  # noqa: E402
from narration import BEATS, NARRATION_SPEED, estimated_duration_seconds, word_count  # noqa: E402
from tts_edge import EdgeTTSError, synthesize_beats as edge_synthesize_beats  # noqa: E402
from tts_fallback import synthesize_beats as sapi_synthesize_beats  # noqa: E402
from tts_qwen import QwenTTSError, synthesize_beats as qwen_synthesize_beats  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "demo_video"

# Voice quality ranking (human neural first; SAPI last resort):
# 1. Qwen TTS (if DASHSCOPE_API_KEY / QWEN_API_KEY)
# 2. edge-tts neural (Jenny)
# 3. Windows SAPI (robotic — avoid as primary)
# 4. silent slideshow
TTS_RANKING = ("qwen", "edge", "sapi", "silent")


def write_status(mode: str, notes: str, *, speed: float = NARRATION_SPEED) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "STATUS.txt").write_text(
        f"tts_mode={mode}\nnarration_speed={speed}\nnotes={notes}\n",
        encoding="utf-8",
    )


def write_chapters_readme(mode: str, speed: float) -> None:
    lines = [
        "# Continuum demo video",
        "",
        f"- Output: `continuum_demo.mp4`",
        f"- TTS mode: `{mode}`",
        f"- Narration speed: **{speed}x** (ffmpeg `atempo` applied after TTS)",
        f"- Beats: {len(BEATS)} · words: {word_count()} · ~{estimated_duration_seconds(speed=speed):.0f}s wall-clock",
        "",
        "## Chapters",
        "",
    ]
    t = 0.0
    for i, b in enumerate(BEATS, 1):
        # Approximate chapter start from word share after speed
        w = len(b["text"].split())
        dur = (w / 145.0 * 60.0) / max(speed, 0.1)
        mm, ss = divmod(int(t), 60)
        lines.append(f"{i}. **{mm:02d}:{ss:02d}** — {b['chapter']} (`{b['id']}`)")
        t += dur
    lines.extend(
        [
            "",
            "## Re-run",
            "",
            "```powershell",
            r".venv\Scripts\python.exe scripts\demo_video\run_pipeline.py",
            "```",
            "",
            "Flags: `--skip-capture`, `--skip-tts`, `--silent`, `--stills-only`, `--no-ken-burns`,",
            f"`--speed {speed}`, `--base-url URL`.",
            "",
        ]
    )
    (OUT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Also write CHAPTERS.md for upload metadata
    (OUT_DIR / "CHAPTERS.md").write_text(
        "\n".join(lines[lines.index("## Chapters") :]) + "\n",
        encoding="utf-8",
    )


def run_tts(*, silent: bool, skip_tts: bool, speed: float) -> str:
    """Return tts mode: qwen | edge | sapi | silent. Always applies `speed` via atempo when audio exists."""
    audio_dir = OUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if silent:
        write_status("silent", "TTS skipped (--silent); slideshow timing from word count.", speed=speed)
        return "silent"

    if skip_tts:
        missing = [b["audio"] for b in BEATS if not (audio_dir / b["audio"]).is_file()]
        if not missing:
            write_status(
                "reuse",
                f"Reused existing audio/ (--skip-tts); narration_speed={speed} assumed already applied.",
                speed=speed,
            )
            return "reuse"
        write_status("silent", f"--skip-tts but missing audio: {missing}", speed=speed)
        return "silent"

    mode = "silent"
    notes = ""

    try:
        qwen_synthesize_beats(BEATS, audio_dir)
        mode = "qwen"
        notes = "Qwen Cloud intl TTS (qwen3-tts-flash) succeeded."
    except QwenTTSError as exc:
        print(f"Qwen TTS unavailable: {exc}")
        print("Trying edge-tts (neural)...")
        try:
            edge_synthesize_beats(BEATS, audio_dir)
            mode = "edge"
            notes = f"Qwen failed ({exc}); used edge-tts neural voice."
        except EdgeTTSError as edge_exc:
            print(f"edge-tts failed: {edge_exc}")
            print("Falling back to Windows SAPI (robotic — last resort)...")
            try:
                sapi_synthesize_beats(BEATS, audio_dir)
                mode = "sapi"
                notes = f"Qwen failed ({exc}); edge failed ({edge_exc}); used SAPI."
            except Exception as sapi_exc:
                print(f"SAPI failed: {sapi_exc}")
                write_status(
                    "silent",
                    f"All TTS failed; silent. qwen={exc}; edge={edge_exc}; sapi={sapi_exc}",
                    speed=speed,
                )
                return "silent"
    except Exception as exc:
        print(f"Qwen TTS unexpected error: {exc}")
        try:
            edge_synthesize_beats(BEATS, audio_dir)
            mode = "edge"
            notes = f"Qwen error ({exc}); used edge-tts."
        except Exception as edge_exc:
            try:
                sapi_synthesize_beats(BEATS, audio_dir)
                mode = "sapi"
                notes = f"Qwen/edge failed; SAPI. qwen={exc}; edge={edge_exc}"
            except Exception as sapi_exc:
                write_status(
                    "silent",
                    f"All TTS failed. qwen={exc}; edge={edge_exc}; sapi={sapi_exc}",
                    speed=speed,
                )
                return "silent"

    if mode != "silent" and abs(speed - 1.0) > 1e-6:
        print(f"Applying narration speed x{speed} (ffmpeg atempo)...")
        speed_beats_in_dir(audio_dir, BEATS, speed=speed)
        notes = f"{notes} narration_speed={speed}x via ffmpeg atempo."

    write_status(mode, notes, speed=speed)
    return mode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Continuum product demo video.")
    parser.add_argument("--skip-capture", action="store_true", help="Reuse existing demo_video/frames/")
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="Reuse existing demo_video/audio/ (or silent if missing); do not call TTS APIs",
    )
    parser.add_argument("--silent", action="store_true", help="Force silent slideshow (no TTS)")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Continuum UI/API base URL (default {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--no-ken-burns", action="store_true", help="Static stills instead of mild zoom")
    parser.add_argument(
        "--stills-only",
        action="store_true",
        help="Do not prefer Playwright screencast; assemble from stills",
    )
    parser.add_argument(
        "--no-video-record",
        action="store_true",
        help="Skip Playwright screencast recording during capture",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=NARRATION_SPEED,
        help=f"Narration speed multiplier (default {NARRATION_SPEED} = 1.8x via ffmpeg atempo)",
    )
    args = parser.parse_args(argv)

    print(f"Repo: {REPO_ROOT}")
    print(f"Out:  {OUT_DIR}")
    print(
        f"Beats: {len(BEATS)}  words={word_count()}  "
        f"~{estimated_duration_seconds(speed=args.speed):.0f}s wall @x{args.speed}"
    )
    print(f"TTS ranking: {' -> '.join(TTS_RANKING)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_capture:
        print("Capturing Playwright tour (frames + screencast)...")
        try:
            paths = capture_frames(
                OUT_DIR,
                base_url=args.base_url,
                record_video=not args.no_video_record,
            )
            print(f"  Wrote {len(paths)} frames")
        except Exception as exc:
            print(f"ERROR: capture failed: {exc}")
            write_status("capture_failed", str(exc), speed=args.speed)
            return 1
    else:
        missing = [b["frame"] for b in BEATS if not (OUT_DIR / "frames" / b["frame"]).is_file()]
        if missing:
            print(f"ERROR: --skip-capture but missing frames: {missing}")
            return 1
        print("Skipping capture (reusing frames)")

    mode = run_tts(silent=args.silent, skip_tts=args.skip_tts, speed=args.speed)
    print(f"TTS mode: {mode}  speed=x{args.speed}")

    print("Assembling video...")
    try:
        out = assemble_video(
            BEATS,
            OUT_DIR,
            silent=(mode == "silent"),
            ken_burns=not args.no_ken_burns,
            prefer_screencast=not args.stills_only,
        )
    except Exception as exc:
        print(f"ERROR: assemble failed: {exc}")
        # One more try with stills only
        if not args.stills_only:
            print("Retrying assemble with stills only...")
            try:
                out = assemble_video(
                    BEATS,
                    OUT_DIR,
                    silent=(mode == "silent"),
                    ken_burns=not args.no_ken_burns,
                    prefer_screencast=False,
                )
            except Exception as exc2:
                print(f"ERROR: stills assemble also failed: {exc2}")
                return 1
        else:
            return 1

    write_chapters_readme(mode, args.speed)
    # Persist speed in markers sidecar
    markers = OUT_DIR / "CHAPTER_MARKERS.json"
    if markers.is_file():
        try:
            data = json.loads(markers.read_text(encoding="utf-8"))
            data["narration_speed"] = args.speed
            data["tts_mode"] = mode
            markers.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass

    print(f"Done: {out}")
    print(f"Status: {OUT_DIR / 'STATUS.txt'}")
    print(f"Chapters: {OUT_DIR / 'CHAPTERS.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
