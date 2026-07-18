from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.embeddings import cosine_similarity, local_embed
from continuum_memory.extractor import extract_heuristic, is_pure_interrogative
from continuum_memory.packer import pack_context
from continuum_memory.retrieve import retrieve_candidates
from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.service import MemoryService
from continuum_memory.store import MemoryStore
from continuum_memory.supersession import apply_supersession, extract_slots

pytestmark = pytest.mark.unit


def _mem(content: str, **kwargs) -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id=kwargs.get("workspace_id", "ws1"),
        type=kwargs.get("type", MemoryType.SEMANTIC),
        content=content,
        entities=kwargs.get("entities", ["Acme"]),
        slots=kwargs.get("slots", {}),
        created_at=now,
        last_accessed_at=now,
    )


def test_local_embed_deterministic():
    a = local_embed("Acme VIP discount")
    b = local_embed("Acme VIP discount")
    assert a == b
    assert cosine_similarity(a, a) > 0.99


def test_hybrid_retrieve_returns_candidates_not_full_table():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        for i in range(30):
            store.remember(_mem(f"Noise fact number {i} about weather and lunch"))
        store.remember(
            _mem(
                "Approved 12% discount for Acme.",
                type=MemoryType.DECISION,
                entities=["Acme"],
                slots={"discount_pct": 12.0, "entity": "Acme"},
            )
        )
        cands = retrieve_candidates(store, "ws1", "Acme discount", top_k=10)
        assert len(cands) <= 20
        assert any("12%" in m.content or "discount" in m.content.lower() for m in cands)
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_pack_uses_retrieve_not_full_scan():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        svc.remember(
            _mem("Approved 12% discount for Acme.", type=MemoryType.DECISION, entities=["Acme"])
        )
        pack = svc.pack("ws1", "Acme discount", budget_tokens=200)
        assert pack.candidate_count >= 1
        assert pack.token_estimate <= 200
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_slot_supersession_and_multi_supersedes():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        old = _mem(
            "Approved 10% discount for Acme.",
            type=MemoryType.DECISION,
            slots={"discount_pct": 10.0, "entity": "Acme"},
        )
        mid = _mem(
            "Approved 11% discount for Acme.",
            type=MemoryType.DECISION,
            slots={"discount_pct": 11.0, "entity": "Acme"},
        )
        new = _mem(
            "Approved 12% discount for Acme.",
            type=MemoryType.DECISION,
            slots={"discount_pct": 12.0, "entity": "Acme"},
        )
        store.remember(old)
        store.remember(mid)
        apply_supersession(store, [mid])
        store.remember(new)
        apply_supersession(store, [new])

        active = store.list_by_workspace("ws1", MemoryStatus.ACTIVE)
        assert len(active) == 1
        assert "12%" in active[0].content
        assert old.id in active[0].supersedes or mid.id in active[0].supersedes
        # multi-supersedes list append
        fetched = store.get(active[0].id)
        assert isinstance(fetched.supersedes, list)
        assert len(fetched.supersedes) >= 1
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_extract_slots_discount_vip():
    slots = extract_slots("Approved 12% discount for Globex. Globex is VIP.")
    assert slots.get("discount_pct") == 12.0
    assert slots.get("vip") is True


def test_complementary_sla_slots_do_not_conflict():
    """Uptime % and response hours are different slots — must both stay active."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        uptime = _mem(
            "Skyline SLA uptime is 99.95%.",
            entities=["Skyline"],
            slots={"sla_pct": 99.95, "entity": "Skyline"},
        )
        response = _mem(
            "Skyline SLA response is 1 hours.",
            entities=["Skyline"],
            slots={"sla_hours": 1.0, "entity": "Skyline"},
        )
        store.remember(uptime)
        store.remember(response)
        apply_supersession(store, [response])
        active = store.list_by_workspace("ws1", MemoryStatus.ACTIVE)
        assert {m.id for m in active} == {uptime.id, response.id}
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_reject_pure_interrogatives():
    assert is_pure_interrogative("What discount does Acme get?")
    mems = extract_heuristic(
        "What discount does Acme get?",
        None,
        org_id="o",
        workspace_id="w",
        session_id="s",
    )
    assert mems == []


def test_domain_agnostic_vip_discount():
    mems = extract_heuristic(
        "Please note that Globex Corp is a VIP customer for us.",
        None,
        org_id="o",
        workspace_id="w",
        session_id="s",
    )
    assert any("VIP" in m.content for m in mems)
    mems2 = extract_heuristic(
        "We approved a 15% discount for Globex through end of 2027.",
        None,
        org_id="o",
        workspace_id="w",
        session_id="s",
    )
    assert any("15%" in m.content for m in mems2)


def test_knapsack_and_mmr_packers():
    memories = [
        _mem("Decision " + "a" * 80, type=MemoryType.DECISION),
        _mem("Preference " + "b" * 80, type=MemoryType.PREFERENCE),
        _mem("Semantic " + "c" * 80, type=MemoryType.SEMANTIC),
    ]
    for algo in ("knapsack_dp", "mmr"):
        pack = pack_context(memories, "decision preference", 120, algorithm=algo)
        assert pack.token_estimate <= 120
        assert pack.algorithm in ("knapsack_dp", "mmr")


def test_forget_requires_workspace_match():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        m = _mem("secret", workspace_id="ws-a")
        svc.remember(m)
        bad = svc.forget(m.id, workspace_id="ws-other")
        assert bad["forgotten"] is False
        good = svc.forget(m.id, workspace_id="ws-a")
        assert good["forgotten"] is True
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_legacy_supersedes_string_parses():
    m = Memory(
        id="x",
        org_id="o",
        workspace_id="w",
        type=MemoryType.SEMANTIC,
        content="c",
        created_at=datetime.now(timezone.utc),
        last_accessed_at=datetime.now(timezone.utc),
        supersedes="old-id-1",  # type: ignore[arg-type]
    )
    assert m.supersedes == ["old-id-1"]
