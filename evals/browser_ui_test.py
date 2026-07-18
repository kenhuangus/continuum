"""Deprecated entrypoint — use `pytest -m e2e` instead.

Thin wrapper that invokes the Playwright regression suite under tests/e2e/.
Kept so existing docs/scripts that call this path still work.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    print(
        "DEPRECATED: evals/browser_ui_test.py → prefer `pytest -m e2e` "
        "(see tests/README.md).",
        file=sys.stderr,
    )
    return subprocess.call(
        [sys.executable, "-m", "pytest", "-m", "e2e", "-v"],
        cwd=str(root),
    )


if __name__ == "__main__":
    raise SystemExit(main())
