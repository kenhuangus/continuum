"""QA: verify each chapter video segment duration matches its audio within tolerance."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from assemble_video import (
    audio_duration_seconds,
    resolve_ffmpeg,
    resolve_ffprobe,
)
from narration import BEATS

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOLERANCE_S = 0.15


def _probe_duration(path: Path, ffmpeg: str, ffprobe: str | None) -> float:
    return audio_duration_seconds(path, ffmpeg, ffprobe)


def split_final_into_segments(
    mp4: Path,
    beats: list[dict],
    audio_dir: Path,
    tmp: Path,
    *,
    ffmpeg: str,
    ffprobe: str | None,
) -> list[Path]:
    """Cut final mp4 into per-chapter segments using cumulative audio durations."""
    segments: list[Path] = []
    t = 0.0
    for i, beat in enumerate(beats, start=1):
        ap = audio_dir / beat["audio"]
        if not ap.is_file():
            raise FileNotFoundError(f"Missing audio for QA: {ap}")
        dur = _probe_duration(ap, ffmpeg, ffprobe)
        seg = tmp / f"qa_seg_{i:02d}.mp4"
        # Slight overlap-safe cut: start at t, duration = audio dur
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-ss",
                f"{t:.6f}",
                "-i",
                str(mp4),
                "-t",
                f"{dur:.6f}",
                "-c",
                "copy",
                str(seg),
            ],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not seg.is_file():
            # Re-encode fallback (copy can fail on keyframe boundaries)
            proc2 = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-ss",
                    f"{t:.6f}",
                    "-i",
                    str(mp4),
                    "-t",
                    f"{dur:.6f}",
                    "-c:v",
                    "libx264",
                    "-c:a",
                    "aac",
                    "-pix_fmt",
                    "yuv420p",
                    str(seg),
                ],
                capture_output=True,
                text=True,
            )
            if proc2.returncode != 0 or not seg.is_file():
                err = (proc2.stderr or proc.stderr or "")[-500:]
                raise RuntimeError(f"Failed to cut segment {beat['id']}: {err}")
        segments.append(seg)
        t += dur
    return segments


def check_sync(
    out_dir: Path,
    *,
    beats: list[dict] | None = None,
    tolerance_s: float = DEFAULT_TOLERANCE_S,
    output_name: str = "continuum_demo.mp4",
) -> dict:
    """
    For each chapter: |video_seg_duration - audio_duration| < tolerance_s.

    Prefer checking intermediate per-beat clips if present under out_dir/_qa_clips;
    otherwise split the final mp4 using cumulative audio timelines (valid when
    assemble used per-chapter duration = audio duration).
    """
    beats = beats or BEATS
    ffmpeg = resolve_ffmpeg()
    ffprobe = resolve_ffprobe(ffmpeg)
    audio_dir = out_dir / "audio"
    mp4 = out_dir / output_name
    if not mp4.is_file():
        raise FileNotFoundError(f"Missing demo mp4: {mp4}")

    rows: list[dict] = []
    all_pass = True

    qa_clips = out_dir / "_qa_clips"
    use_clips = qa_clips.is_dir() and all(
        (qa_clips / f"clip_{i:02d}.mp4").is_file() for i in range(1, len(beats) + 1)
    )

    with tempfile.TemporaryDirectory(prefix="continuum_qa_") as tmp_name:
        tmp = Path(tmp_name)
        if use_clips:
            segs = [qa_clips / f"clip_{i:02d}.mp4" for i in range(1, len(beats) + 1)]
        else:
            segs = split_final_into_segments(
                mp4, beats, audio_dir, tmp, ffmpeg=ffmpeg, ffprobe=ffprobe
            )

        for i, beat in enumerate(beats):
            ap = audio_dir / beat["audio"]
            audio_dur = _probe_duration(ap, ffmpeg, ffprobe) if ap.is_file() else -1.0
            vid_dur = _probe_duration(segs[i], ffmpeg, ffprobe)
            delta = abs(vid_dur - audio_dur) if audio_dur > 0 else 999.0
            passed = audio_dur > 0 and delta < tolerance_s
            if not passed:
                all_pass = False
            rows.append(
                {
                    "id": beat["id"],
                    "chapter": beat.get("chapter", beat["id"]),
                    "audio_s": round(audio_dur, 3),
                    "video_s": round(vid_dur, 3),
                    "delta_s": round(delta, 3),
                    "pass": passed,
                }
            )

        total_audio = sum(r["audio_s"] for r in rows if r["audio_s"] > 0)
        total_video = _probe_duration(mp4, ffmpeg, ffprobe)
        total_delta = abs(total_video - total_audio)
        total_pass = total_delta < tolerance_s * max(2.0, len(beats) * 0.25)

        report = {
            "mp4": str(mp4),
            "tolerance_s": tolerance_s,
            "method": "qa_clips" if use_clips else "split_final",
            "chapters": rows,
            "total_audio_s": round(total_audio, 3),
            "total_video_s": round(total_video, 3),
            "total_delta_s": round(total_delta, 3),
            "total_pass": total_pass,
            "all_chapters_pass": all_pass,
            "pass": all_pass and total_pass,
        }

    return report


def write_qa_report(out_dir: Path, report: dict) -> Path:
    lines = [
        "# Continuum demo video — sync QA",
        "",
        f"- File: `{Path(report['mp4']).name}`",
        f"- Tolerance: **{report['tolerance_s']}s** per chapter",
        f"- Method: `{report['method']}`",
        f"- Overall: **{'PASS' if report['pass'] else 'FAIL'}**",
        f"- Total audio: {report['total_audio_s']:.3f}s · total video: {report['total_video_s']:.3f}s "
        f"(Δ {report['total_delta_s']:.3f}s) — {'PASS' if report['total_pass'] else 'FAIL'}",
        "",
        "| # | Chapter | Audio (s) | Video seg (s) | |Δ| (s) | Result |",
        "|---|---------|-----------|---------------|--------|--------|",
    ]
    for i, row in enumerate(report["chapters"], 1):
        lines.append(
            f"| {i} | {row['id']} — {row['chapter']} | {row['audio_s']:.3f} | "
            f"{row['video_s']:.3f} | {row['delta_s']:.3f} | "
            f"{'PASS' if row['pass'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "Sync model: each chapter still/clip duration equals ffprobe duration of that chapter's TTS audio.",
            "Continuous screencast mux is disabled for the final mp4 (visuals would race ahead of narration).",
            "",
        ]
    )
    path = out_dir / "QA_REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "QA_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


if __name__ == "__main__":
    out = REPO_ROOT / "demo_video"
    rep = check_sync(out)
    p = write_qa_report(out, rep)
    print(json.dumps(rep, indent=2))
    print(f"Wrote {p} pass={rep['pass']}")
    raise SystemExit(0 if rep["pass"] else 1)
