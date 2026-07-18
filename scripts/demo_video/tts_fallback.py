"""Windows SAPI TTS fallback (pyttsx3 preferred, else PowerShell System.Speech)."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def _via_pyttsx3(text: str, out_path: Path) -> bool:
    try:
        import pyttsx3
    except ImportError:
        return False
    engine = pyttsx3.init()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Prefer a WAV path; pyttsx3 save_to_file + runAndWait writes on Windows SAPI.
    engine.save_to_file(text, str(out_path))
    engine.runAndWait()
    engine.stop()
    return out_path.is_file() and out_path.stat().st_size > 0


def _via_powershell(text: str, out_path: Path) -> bool:
    """Synthesize WAV via System.Speech.Synthesis (Windows only)."""
    if sys.platform != "win32":
        return False
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Escape for PowerShell single-quoted string: double any single quotes.
    safe_text = text.replace("'", "''")
    safe_path = str(out_path.resolve()).replace("'", "''")
    ps = f"""
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SetOutputToWaveFile('{safe_path}')
$synth.Speak('{safe_text}')
$synth.Dispose()
"""
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8") as tf:
        tf.write(ps)
        script = tf.name
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            return False
        return out_path.is_file() and out_path.stat().st_size > 0
    except (OSError, subprocess.TimeoutExpired):
        return False
    finally:
        try:
            Path(script).unlink(missing_ok=True)
        except OSError:
            pass


def synthesize_to_file(text: str, out_path: Path) -> Path:
    """Write spoken audio for text. Raises RuntimeError if all backends fail."""
    if _via_pyttsx3(text, out_path):
        return out_path
    if _via_powershell(text, out_path):
        return out_path
    raise RuntimeError(
        "SAPI fallback failed (install pyttsx3 or use Windows PowerShell System.Speech)."
    )


def synthesize_beats(beats: list[dict], audio_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for beat in beats:
        out = audio_dir / beat["audio"]
        print(f"  SAPI {beat['id']} -> {out.name}")
        synthesize_to_file(beat["text"], out)
        paths.append(out)
    return paths
