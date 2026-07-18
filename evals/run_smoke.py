#!/usr/bin/env python3
"""Offline smoke eval: Session A memories recalled in Session B under budget."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "memory_core"))
sys.path.insert(0, str(ROOT / "packages" / "agent"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

from continuum_memory import MemoryService  # noqa: E402


def main() -> int:
    fixture_path = Path(__file__).parent / "fixtures" / "acme_session_a_b.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    svc = MemoryService(db_path=db_path)
    ws = fixture["workspace_id"]
    org = fixture["org_id"]

    print("=== Continuum Smoke Eval ===")
    print(f"Workspace: {ws}")

    for turn in fixture["session_a"]["turns"]:
        written = svc.ingest_turn(
            ws,
            fixture["session_a"]["session_id"],
            turn["user"],
            turn.get("assistant"),
            org_id=org,
        )
        print(f"  Session A ingest: {len(written)} memories from turn")

    query = fixture["session_b"]["query"]
    budget = 400
    pack = svc.pack(ws, query, budget_tokens=budget, algorithm="type_quota")

    # Only score packed memory content — do not include the query (avoids false PASS).
    combined = " ".join(m.content.lower() for m in pack.memories)

    signals = fixture["expected_signals"]
    missing = [s for s in signals if s.lower() not in combined]

    if not pack.memories:
        print("\nFAIL — no memories packed")
        return 1

    print(f"\nSession B query: {query}")
    print(f"Pack algorithm: {pack.algorithm}, tokens: {pack.token_estimate}/{budget}")
    print(f"Packed {len(pack.memories)} memories:")
    for m in pack.memories:
        print(f"  - [{m.id[:8]}] {m.type.value}: {m.content}")

    if missing:
        print(f"\nFAIL — missing signals: {missing}")
        return 1

    if pack.token_estimate > budget:
        print(f"\nFAIL — budget exceeded: {pack.token_estimate} > {budget}")
        return 1

    print("\nPASS — all expected signals present within budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
