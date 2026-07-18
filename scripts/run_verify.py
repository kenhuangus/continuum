#!/usr/bin/env python3
"""Run Continuum verify commands and write full output to verify_results.txt."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "verify_results.txt"


def run_step(name: str, cmd: list[str], env: dict[str, str]) -> int:
    lines: list[str] = [f"=== {name} ===", f"CMD: {' '.join(cmd)}", ""]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        lines.append("--- stdout ---")
        lines.append(proc.stdout.rstrip())
    if proc.stderr:
        lines.append("--- stderr ---")
        lines.append(proc.stderr.rstrip())
    lines.append(f"EXIT_CODE: {proc.returncode}")
    lines.append("")
    OUT.write_text(OUT.read_text(encoding="utf-8") + "\n".join(lines) + "\n\n", encoding="utf-8")
    return proc.returncode


def main() -> int:
    OUT.write_text("", encoding="utf-8")
    env = os.environ.copy()
    env["CONTINUUM_AUTH_DISABLED"] = "1"
    env["CONTINUUM_FORCE_LOCAL_EMBED"] = "1"
    env.pop("DASHSCOPE_API_KEY", None)
    env.pop("QWEN_API_KEY", None)

    py = sys.executable
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        py = str(venv_py)

    steps = [
        ("1: unit", [py, "-m", "pytest", "-m", "unit", "-q", "--tb=short"]),
        ("2: api", [py, "-m", "pytest", "-m", "api", "-q", "--tb=short"]),
        ("3: smoke", [py, str(ROOT / "evals" / "run_smoke.py")]),
        ("4: suite", [py, str(ROOT / "evals" / "run_suite.py")]),
    ]

    worst = 0
    for name, cmd in steps:
        code = run_step(name, cmd, env)
        worst = max(worst, code)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
