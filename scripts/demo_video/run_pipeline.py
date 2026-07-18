"""Orchestrate Continuum demo-video pipeline: capture → TTS → ffmpeg assemble."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/demo_video/run_pipeline.py` without package install.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from assemble_video import assemble_video  # noqa: E402
from capture_frames import DEFAULT_BASE_URL, capture_frames  # noqa: E402
from narration import BEATS, estimated_duration_seconds, word_count  # noqa: E402
from tts_fallback import synthesize_beats as sapi_synthesize_beats  # noqa: E402
from tts_qwen import QwenTTSError, synthesize_beats as qwen_synthesize_beats  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "demo_video"


def write_status(mode: str, notes: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "STATUS.txt").write_text(
        f"tts_mode={mode}\nnotes={notes}\n",
        encoding="utf-8",
    )


def run_tts(*, silent: bool, skip_tts: bool) -> str:
    """Return tts mode: qwen | sapi | silent."""
    audio_dir = OUT_DIR / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if silent or skip_tts:
        write_status("silent", "TTS skipped (--silent or --skip-tts); slideshow timing from word count.")
        return "silent"

    try:
        qwen_synthesize_beats(BEATS, audio_dir)
        write_status("qwen", "Qwen Cloud intl TTS (qwen3-tts-flash) succeeded.")
        return "qwen"
    except QwenTTSError as exc:
        print(f"Qwen TTS failed: {exc}")
        print("Falling back to Windows SAPI...")
        try:
            sapi_synthesize_beats(BEATS, audio_dir)
            write_status("sapi", f"Qwen failed ({exc}); used Windows SAPI fallback.")
            return "sapi"
        except Exception as sapi_exc:
            print(f"SAPI fallback failed: {sapi_exc}")
            write_status(
                "silent",
                f"Qwen failed ({exc}); SAPI failed ({sapi_exc}); silent slideshow.",
            )
            return "silent"
    except Exception as exc:
        print(f"Qwen TTS unexpected error: {exc}")
        try:
            sapi_synthesize_beats(BEATS, audio_dir)
            write_status("sapi", f"Qwen error ({exc}); used Windows SAPI fallback.")
            return "sapi"
        except Exception as sapi_exc:
            write_status(
                "silent",
                f"Qwen error ({exc}); SAPI failed ({sapi_exc}); silent slideshow.",
            )
            return "silent"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Continuum hackathon demo video.")
    parser.add_argument("--skip-capture", action="store_true", help="Reuse existing demo_video/frames/")
    parser.add_argument("--skip-tts", action="store_true", help="Skip TTS; assemble silent/timed slides")
    parser.add_argument("--silent", action="store_true", help="Force silent slideshow (no TTS)")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Continuum UI/API base URL (default {DEFAULT_BASE_URL})",
    )
    parser.add_argument("--no-ken-burns", action="store_true", help="Use static stills instead of mild zoom")
    args = parser.parse_args(argv)

    print(f"Repo: {REPO_ROOT}")
    print(f"Out:  {OUT_DIR}")
    print(f"Beats: {len(BEATS)}  words={word_count()}  ~{estimated_duration_seconds():.0f}s narration")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not args.skip_capture:
        print("Capturing Playwright frames...")
        paths = capture_frames(OUT_DIR, base_url=args.base_url)
        print(f"  Wrote {len(paths)} frames")
    else:
        missing = [b["frame"] for b in BEATS if not (OUT_DIR / "frames" / b["frame"]).is_file()]
        if missing:
            print(f"ERROR: --skip-capture but missing frames: {missing}")
            return 1
        print("Skipping capture (reusing frames)")

    mode = run_tts(silent=args.silent, skip_tts=args.skip_tts)
    print(f"TTS mode: {mode}")

    print("Assembling video...")
    out = assemble_video(
        BEATS,
        OUT_DIR,
        silent=(mode == "silent"),
        ken_burns=not args.no_ken_burns,
    )
    print(f"Done: {out}")
    print(f"Status: {OUT_DIR / 'STATUS.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
