"""Regression test for the stress_noise_budget stale-leak fix (Loop 3, §1).

Root cause (docs/research/LOOP3_NOTES.md §1): the turn "Earlier we had floated
an 8% discount for Globex but that is obsolete." was extracted as a fresh,
high-priority DECISION/EPISODIC fact still containing the literal stale value
"8%". Under the fixture's tight 60-token budget, that content could win a
packer type-quota slot ahead of (or alongside) the legitimate 15% decision,
leaking the stale value into packed context.

This test replays the actual stress_noise_budget.json ingest+pack path and
asserts the packed text never contains the stale "8%" value, while critical
facts remain recallable as much as the tight budget allows.
"""

from __future__ import annotations

import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.extractor import extract_heuristic, has_obsolescence_cue
from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.service import MemoryService
from continuum_memory.supersession import apply_supersession

pytestmark = pytest.mark.unit

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "evals" / "fixtures" / "stress_noise_budget.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _seed(svc: MemoryService, fx: dict) -> None:
    ws = fx["workspace_id"]
    org = fx.get("org_id", "org_demo")
    now = datetime.now(timezone.utc)
    for raw in fx.get("seed_memories") or []:
        mem = Memory(
            id=raw.get("id") or str(uuid.uuid4()),
            org_id=org,
            workspace_id=ws,
            type=MemoryType(raw["type"]),
            content=raw["content"],
            entities=list(raw.get("entities") or []),
            confidence=float(raw.get("confidence", 1.0)),
            utility=float(raw.get("utility", 1.0)),
            status=MemoryStatus(raw.get("status", "active")),
            created_at=now,
            last_accessed_at=now,
            source=raw.get("source") or {"seed": True},
        )
        svc.remember(mem)


def _ingest_session_a(svc: MemoryService, fx: dict) -> None:
    ws = fx["workspace_id"]
    org = fx.get("org_id", "org_demo")
    session = fx["session_a"]
    for turn in session["turns"]:
        svc.ingest_turn(ws, session["session_id"], turn["user"], turn.get("assistant"), org_id=org)


def test_fixture_has_obsolescence_turn():
    """Sanity: the fixture still contains the obsolescence-cue turn we target."""
    fx = _load_fixture()
    turns = [t["user"] for t in fx["session_a"]["turns"]]
    assert any(has_obsolescence_cue(t) for t in turns)


def test_obsolescence_turn_never_writes_stale_numeric_active_fact():
    """Extractor must not write the obsolete "8%" value as a fresh active fact."""
    mems = extract_heuristic(
        "Earlier we had floated an 8% discount for Globex but that is obsolete.",
        "Understood, 8% is outdated.",
        org_id="org_demo",
        workspace_id="ws_stale_unit",
        session_id="s-a",
    )
    assert mems, "expected an obsolescence marker memory to be extracted"
    for m in mems:
        assert "8%" not in m.content
        assert "8 %" not in m.content
    # Marker carries the stale value in slots only (for supersession), never content.
    assert any(m.slots.get("obsolete_value") == 8.0 for m in mems)


def test_stress_noise_budget_stale_leakage_is_zero():
    """Full replay of the stress_noise_budget fixture ingest+pack path."""
    fx = _load_fixture()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        _seed(svc, fx)
        _ingest_session_a(svc, fx)

        ws = fx["workspace_id"]
        query = fx["session_b"]["query"]
        budget = int(fx["budget_tokens"])
        packed = svc.pack(ws, query, budget_tokens=budget, algorithm="type_quota")

        assert packed.token_estimate <= budget
        text = " ".join(m.content for m in packed.memories)

        stale_facts = fx.get("stale_facts") or []
        stale_hits = [s for s in stale_facts if s.lower() in text.lower()]
        assert stale_hits == [], f"stale facts leaked into packed context: {stale_hits}"

        # The 15% decision must remain ACTIVE (never wrongly superseded by the
        # obsolescence marker for the unrelated stale "8%" value).
        active = svc.list_memories(ws, MemoryStatus.ACTIVE)
        assert any("15%" in m.content for m in active)

        # Recall "as much as budget allows": at least one critical fact should
        # survive the tight 60-token budget.
        critical = fx["critical_facts"]
        hits = [c for c in critical if c.lower() in text.lower()]
        assert len(hits) >= 1, f"expected at least one critical fact packed, got none from {critical}"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_apply_supersession_retires_stale_value_not_marker_itself():
    """Obsolescence marker must retire matching-value actives, never win itself."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        now = datetime.now(timezone.utc)
        stale_decision = Memory(
            id=str(uuid.uuid4()),
            org_id="org_demo",
            workspace_id="ws_marker",
            type=MemoryType.DECISION,
            content="Approved 8% discount for Globex.",
            entities=["Globex"],
            created_at=now,
            last_accessed_at=now,
            slots={"discount_pct": 8.0, "entity": "Globex"},
        )
        svc.remember(stale_decision)

        marker = Memory(
            id=str(uuid.uuid4()),
            org_id="org_demo",
            workspace_id="ws_marker",
            type=MemoryType.EPISODIC,
            content="A previous discount pct value for Globex is now obsolete and no longer applies.",
            entities=["Globex"],
            created_at=now,
            last_accessed_at=now,
            slots={"entity": "Globex", "obsolete_slot": "discount_pct", "obsolete_value": 8.0},
        )
        stored_marker = svc.store.remember(marker)
        apply_supersession(svc.store, [stored_marker])

        active_ids = {m.id for m in svc.list_memories("ws_marker", MemoryStatus.ACTIVE)}
        assert stale_decision.id not in active_ids

        # Marker itself never becomes packable content for that slot either —
        # it is an EPISODIC bookkeeping record, hard-excluded from packing.
        from continuum_memory.packer import filter_packable

        remaining_active = svc.list_memories("ws_marker", MemoryStatus.ACTIVE)
        packable = filter_packable(remaining_active)
        assert stored_marker.id not in {m.id for m in packable}
    finally:
        Path(db_path).unlink(missing_ok=True)
