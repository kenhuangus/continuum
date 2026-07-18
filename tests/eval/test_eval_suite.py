from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "memory_core"))
sys.path.insert(0, str(ROOT / "evals"))

from continuum_eval import aggregate, continuum_beats_naive, load_fixtures, run_fixture

pytestmark = pytest.mark.eval


def test_eval_suite_continuum_ge_naive():
    fixtures = load_fixtures()
    assert len(fixtures) >= 15
    rows = [run_fixture(fx) for fx in fixtures]
    agg = aggregate(rows)
    assert continuum_beats_naive(agg), agg
    assert agg["continuum_pack"]["recall"] >= agg["no_memory"]["recall"]
