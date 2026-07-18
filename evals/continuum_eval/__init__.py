"""Continuum offline eval suite — baselines vs hybrid pack."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from continuum_memory.packer import estimate_tokens, pack_context
from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.service import MemoryService

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@dataclass
class BaselineResult:
    name: str
    recall: float
    stale_leakage: float
    tokens: int
    critical_hits: list[str] = field(default_factory=list)
    stale_hits: list[str] = field(default_factory=list)


def load_fixtures(dir_path: Path | None = None) -> list[dict[str, Any]]:
    root = dir_path or FIXTURES_DIR
    fixtures = []
    for path in sorted(root.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["_path"] = str(path)
        fixtures.append(data)
    return fixtures


def _normalize_fixture(fx: dict[str, Any]) -> dict[str, Any]:
    """Support legacy smoke fixture + richer suite fixtures."""
    out = dict(fx)
    if "critical_facts" not in out and "expected_signals" in out:
        out["critical_facts"] = list(out["expected_signals"])
    out.setdefault("stale_facts", [])
    out.setdefault("budget_tokens", 400)
    out.setdefault("org_id", "org_demo")
    return out


def _fact_present(fact: str, text: str) -> bool:
    f = fact.lower().strip()
    t = text.lower()
    if f in t:
        return True
    # Allow percent forms: "12%" vs "12 %"
    f2 = re.sub(r"\s+", "", f)
    t2 = re.sub(r"\s+", "", t)
    return f2 in t2


def _ingest_session_a(svc: MemoryService, fx: dict[str, Any]) -> None:
    ws = fx["workspace_id"]
    org = fx.get("org_id", "org_demo")
    session = fx["session_a"]
    for turn in session["turns"]:
        svc.ingest_turn(
            ws,
            session["session_id"],
            turn["user"],
            turn.get("assistant"),
            org_id=org,
        )


def baseline_no_memory(fx: dict[str, Any]) -> BaselineResult:
    critical = fx["critical_facts"]
    return BaselineResult(
        name="no_memory",
        recall=0.0,
        stale_leakage=0.0,
        tokens=0,
        critical_hits=[],
        stale_hits=[],
    )


def baseline_full_history_dump(svc: MemoryService, fx: dict[str, Any]) -> BaselineResult:
    ws = fx["workspace_id"]
    active = svc.list_memories(ws, MemoryStatus.ACTIVE)
    text = " ".join(m.content for m in active)
    tokens = estimate_tokens(text)
    critical = fx["critical_facts"]
    stale = fx.get("stale_facts") or []
    hits = [c for c in critical if _fact_present(c, text)]
    stale_hits = [s for s in stale if _fact_present(s, text)]
    return BaselineResult(
        name="full_history_dump",
        recall=len(hits) / max(1, len(critical)),
        stale_leakage=len(stale_hits) / max(1, len(stale)) if stale else 0.0,
        tokens=tokens,
        critical_hits=hits,
        stale_hits=stale_hits,
    )


def baseline_naive_topk_keyword(svc: MemoryService, fx: dict[str, Any]) -> BaselineResult:
    ws = fx["workspace_id"]
    query = fx["session_b"]["query"]
    budget = int(fx["budget_tokens"])
    active = svc.list_memories(ws, MemoryStatus.ACTIVE)
    # Naive: keyword score then greedy pack
    packed = pack_context(active, query, budget, algorithm="greedy")
    text = " ".join(m.content for m in packed.memories)
    critical = fx["critical_facts"]
    stale = fx.get("stale_facts") or []
    hits = [c for c in critical if _fact_present(c, text)]
    stale_hits = [s for s in stale if _fact_present(s, text)]
    return BaselineResult(
        name="naive_topk_keyword",
        recall=len(hits) / max(1, len(critical)),
        stale_leakage=len(stale_hits) / max(1, len(stale)) if stale else 0.0,
        tokens=packed.token_estimate,
        critical_hits=hits,
        stale_hits=stale_hits,
    )


def baseline_continuum_pack(svc: MemoryService, fx: dict[str, Any]) -> BaselineResult:
    ws = fx["workspace_id"]
    query = fx["session_b"]["query"]
    budget = int(fx["budget_tokens"])
    packed = svc.pack(ws, query, budget_tokens=budget, algorithm="type_quota")
    text = " ".join(m.content for m in packed.memories)
    critical = fx["critical_facts"]
    stale = fx.get("stale_facts") or []
    hits = [c for c in critical if _fact_present(c, text)]
    stale_hits = [s for s in stale if _fact_present(s, text)]
    return BaselineResult(
        name="continuum_pack",
        recall=len(hits) / max(1, len(critical)),
        stale_leakage=len(stale_hits) / max(1, len(stale)) if stale else 0.0,
        tokens=packed.token_estimate,
        critical_hits=hits,
        stale_hits=stale_hits,
    )


def run_fixture(fx: dict[str, Any]) -> dict[str, Any]:
    fx = _normalize_fixture(fx)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    svc = MemoryService(db_path=db_path)
    _ingest_session_a(svc, fx)

    results = [
        baseline_no_memory(fx),
        baseline_full_history_dump(svc, fx),
        baseline_naive_topk_keyword(svc, fx),
        baseline_continuum_pack(svc, fx),
    ]
    by_name = {r.name: r for r in results}
    return {
        "fixture": Path(fx.get("_path", fx["workspace_id"])).name,
        "workspace_id": fx["workspace_id"],
        "baselines": {
            name: {
                "recall": r.recall,
                "stale_leakage": r.stale_leakage,
                "tokens": r.tokens,
                "critical_hits": r.critical_hits,
                "stale_hits": r.stale_hits,
            }
            for name, r in by_name.items()
        },
    }


def aggregate(suite_results: list[dict[str, Any]]) -> dict[str, Any]:
    names = ["no_memory", "full_history_dump", "naive_topk_keyword", "continuum_pack"]
    agg: dict[str, dict[str, float]] = {
        n: {"recall": 0.0, "stale_leakage": 0.0, "tokens": 0.0} for n in names
    }
    n = max(1, len(suite_results))
    for row in suite_results:
        for name in names:
            b = row["baselines"][name]
            agg[name]["recall"] += b["recall"]
            agg[name]["stale_leakage"] += b["stale_leakage"]
            agg[name]["tokens"] += b["tokens"]
    for name in names:
        agg[name]["recall"] /= n
        agg[name]["stale_leakage"] /= n
        agg[name]["tokens"] /= n
    return agg


def continuum_beats_naive(agg: dict[str, Any]) -> bool:
    c = agg["continuum_pack"]
    naive = agg["naive_topk_keyword"]
    recall_ok = c["recall"] >= naive["recall"] - 1e-9
    # Prefer lower or equal stale leakage when stale facts exist in suite
    stale_ok = c["stale_leakage"] <= naive["stale_leakage"] + 1e-9
    return recall_ok and stale_ok
