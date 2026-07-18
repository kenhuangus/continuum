"""python -m continuum_eval — run the offline baseline suite."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure packages importable when run as script
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "memory_core"))
sys.path.insert(0, str(ROOT / "packages" / "agent"))
sys.path.insert(0, str(ROOT / "evals"))

from continuum_eval import (  # noqa: E402
    aggregate,
    continuum_beats_naive,
    load_fixtures,
    run_fixture,
)


def main() -> int:
    os.environ.setdefault("CONTINUUM_AUTH_DISABLED", "1")
    os.environ["CONTINUUM_FORCE_LOCAL_EMBED"] = "1"
    os.environ.pop("DASHSCOPE_API_KEY", None)
    os.environ.pop("QWEN_API_KEY", None)

    fixtures = load_fixtures()
    if not fixtures:
        print("No fixtures found under evals/fixtures/")
        return 1

    print("=== Continuum Eval Suite ===")
    print(f"Fixtures: {len(fixtures)}")
    rows = []
    for fx in fixtures:
        row = run_fixture(fx)
        rows.append(row)
        c = row["baselines"]["continuum_pack"]
        n = row["baselines"]["naive_topk_keyword"]
        print(
            f"  {row['fixture']}: continuum recall={c['recall']:.2f} "
            f"stale={c['stale_leakage']:.2f} | naive recall={n['recall']:.2f} "
            f"stale={n['stale_leakage']:.2f}"
        )

    agg = aggregate(rows)
    print("\n=== Aggregate ===")
    for name, stats in agg.items():
        print(
            f"  {name}: recall={stats['recall']:.3f} "
            f"stale_leakage={stats['stale_leakage']:.3f} "
            f"avg_tokens={stats['tokens']:.1f}"
        )

    ok = continuum_beats_naive(agg)
    if ok:
        print("\nPASS — continuum_pack >= naive_topk_keyword on recall and stale leakage")
        return 0
    print("\nFAIL — continuum_pack did not meet/exceed naive baseline aggregate")
    print(json.dumps(agg, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
