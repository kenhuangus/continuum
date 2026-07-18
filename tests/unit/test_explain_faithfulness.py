from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.explain import cite_overlap, explain_memory_structured
from continuum_memory.schemas import Memory, MemoryType
from continuum_memory.service import MemoryService

pytestmark = pytest.mark.unit


def test_cite_overlap_jaccard():
    assert cite_overlap("Acme discount VIP", "Acme gets VIP discount") > 0.3
    assert cite_overlap("zzz", "unrelated content") == 0.0


def test_pack_fills_explanation_details():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        now = datetime.now(timezone.utc)
        mem = Memory(
            id=str(uuid.uuid4()),
            org_id="org_demo",
            workspace_id="ws_ex",
            type=MemoryType.DECISION,
            content="Approved 12% discount for Acme.",
            entities=["Acme"],
            created_at=now,
            last_accessed_at=now,
        )
        svc.remember(mem)
        packed = svc.pack("ws_ex", "What discount does Acme get?", budget_tokens=400)
        assert packed.explanation_details
        included = [d for d in packed.explanation_details if d.get("included")]
        assert included
        assert "cite_overlap" in included[0]
        structured = explain_memory_structured(mem.id, packed, query="Acme discount")
        assert "explanation" in structured
        assert structured["cite_overlap"] >= 0.0
    finally:
        Path(db_path).unlink(missing_ok=True)
