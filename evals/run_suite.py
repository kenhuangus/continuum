#!/usr/bin/env python3
"""Run Continuum offline eval suite across all fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "memory_core"))
sys.path.insert(0, str(ROOT / "packages" / "agent"))
sys.path.insert(0, str(ROOT / "evals"))

from continuum_eval.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
