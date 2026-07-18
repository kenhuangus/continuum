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
from qa_sync import check_sync, write_qa_report  # noqa: E402
from tts_edge import EdgeTTSError, synthesize_beats as edge_synthesize_beats  # noqa: E402
from tts_fallback import synthesize_beats as sapi_synthesize_beats  # noqa: E402
from tts_qwen import QwenTTSError, synthesize_beats as qwen_synthesize_beats  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "demo_video"

# Voice quality ranking (product demo prefers neural Jenny; SAPI last resort):
# 1. edge-tts neural (en-US-JennyNeural) — default for Continuum product tour
# 2. Qwen TTS (if DASHSCOPE_API_KEY / QWEN_API_KEY)
# 3. Windows SAPI (robotic — avoid as primary)
# 4. silent slideshow
TTS_RANKING = ("edge", "qwen", "sapi", "silent")


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
            "Flags: `--skip-capture`, `--skip-tts`, `--silent`, `--screencast-mux` (sync-unsafe),",
            f"`--no-ken-burns`, `--speed {speed}`, `--base-url URL`.",
            "",
            "Assemble uses **per-chapter stills timed to TTS audio** (sync-correct).",
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
    """Return tts mode: edge | qwen | sapi | silent. Always applies `speed` via atempo when audio exists."""
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

    # Prefer edge-tts Jenny neural for product demos (human voice, no competition branding).
    try:
        print("Synthesizing with edge-tts (en-US-JennyNeural)...")
        edge_synthesize_beats(BEATS, audio_dir)
        mode = "edge"
        notes = "edge-tts neural voice (en-US-JennyNeural)."
    except EdgeTTSError as edge_exc:
        print(f"edge-tts failed: {edge_exc}")
        print("Trying Qwen TTS...")
        try:
            qwen_synthesize_beats(BEATS, audio_dir)
            mode = "qwen"
            notes = f"edge failed ({edge_exc}); used Qwen Cloud TTS."
        except QwenTTSError as qwen_exc:
            print(f"Qwen TTS unavailable: {qwen_exc}")
            print("Falling back to Windows SAPI (robotic — last resort)...")
            try:
                sapi_synthesize_beats(BEATS, audio_dir)
                mode = "sapi"
                notes = f"edge failed ({edge_exc}); qwen failed ({qwen_exc}); used SAPI."
            except Exception as sapi_exc:
                print(f"SAPI failed: {sapi_exc}")
                write_status(
                    "silent",
                    f"All TTS failed; silent. edge={edge_exc}; qwen={qwen_exc}; sapi={sapi_exc}",
                    speed=speed,
                )
                return "silent"
        except Exception as qwen_exc:
            print(f"Qwen TTS unexpected error: {qwen_exc}")
            try:
                sapi_synthesize_beats(BEATS, audio_dir)
                mode = "sapi"
                notes = f"edge/qwen failed; SAPI. edge={edge_exc}; qwen={qwen_exc}"
            except Exception as sapi_exc:
                write_status(
                    "silent",
                    f"All TTS failed. edge={edge_exc}; qwen={qwen_exc}; sapi={sapi_exc}",
                    speed=speed,
                )
                return "silent"
    except Exception as edge_exc:
        print(f"edge-tts unexpected error: {edge_exc}")
        try:
            qwen_synthesize_beats(BEATS, audio_dir)
            mode = "qwen"
            notes = f"edge error ({edge_exc}); used Qwen TTS."
        except Exception as qwen_exc:
            try:
                sapi_synthesize_beats(BEATS, audio_dir)
                mode = "sapi"
                notes = f"edge/qwen failed; SAPI. edge={edge_exc}; qwen={qwen_exc}"
            except Exception as sapi_exc:
                write_status(
                    "silent",
                    f"All TTS failed. edge={edge_exc}; qwen={qwen_exc}; sapi={sapi_exc}",
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
        help="(Default behavior) Assemble from per-chapter stills timed to audio",
    )
    parser.add_argument(
        "--screencast-mux",
        action="store_true",
        help="UNSAFE: mux continuous screencast + narration (desyncs chapters; debug only)",
    )
    parser.add_argument(
        "--no-video-record",
        action="store_true",
        help="Skip Playwright screencast recording during capture",
    )
    parser.add_argument(
        "--skip-qa",
        action="store_true",
        help="Skip post-assemble sync QA (|video_seg - audio| < 0.15s)",
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

    prefer_sc = bool(args.screencast_mux) and not args.stills_only
    if prefer_sc:
        print("WARNING: --screencast-mux enabled (chapter A/V will desync)")

    print("Assembling video (per-chapter stills = audio duration)...")
    try:
        out = assemble_video(
            BEATS,
            OUT_DIR,
            silent=(mode == "silent"),
            ken_burns=not args.no_ken_burns,
            prefer_screencast=prefer_sc,
        )
    except Exception as exc:
        print(f"ERROR: assemble failed: {exc}")
        if prefer_sc:
            print("Retrying assemble with sync-correct stills...")
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
            data["assemble_mode"] = "screencast_mux" if prefer_sc else "per_chapter_stills"
            markers.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, OSError):
            pass

    print(f"Done: {out}")
    print(f"Status: {OUT_DIR / 'STATUS.txt'}")
    print(f"Chapters: {OUT_DIR / 'CHAPTERS.md'}")

    if not args.skip_qa and mode != "silent":
        print("Running sync QA (|video_seg - audio| < 0.15s)...")
        try:
            report = check_sync(OUT_DIR, beats=BEATS, tolerance_s=0.15)
            qa_path = write_qa_report(OUT_DIR, report)
            print(f"QA: {qa_path} pass={report['pass']}")
            if not report["pass"]:
                fails = [c["id"] for c in report["chapters"] if not c["pass"]]
                print(f"ERROR: sync QA failed for chapters: {fails}")
                return 2
        except Exception as qa_exc:
            print(f"ERROR: sync QA failed to run: {qa_exc}")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
