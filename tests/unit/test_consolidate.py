from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.service import MemoryService
from continuum_memory.store import MemoryStore

pytestmark = pytest.mark.unit


def _episodic(content: str, entity: str = "Acme") -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id="ws1",
        type=MemoryType.EPISODIC,
        content=content,
        entities=[entity],
        created_at=now,
        last_accessed_at=now,
    )


def test_consolidate_distills_episodics_and_tags_sources():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        a = _episodic("Acme meeting discussed pricing.")
        b = _episodic("Acme follow-up confirmed VIP status.")
        svc.remember(a)
        svc.remember(b)

        written = svc.consolidate("ws1", max_groups=20)
        assert len(written) == 1
        distilled = written[0]
        assert distilled.type == MemoryType.SEMANTIC
        assert distilled.content.startswith("Distilled:")
        assert "distilled" in distilled.policy_tags
        assert distilled.source.get("kind") == "consolidation"

        store = MemoryStore(db_path)
        src_a = store.get(a.id)
        src_b = store.get(b.id)
        assert src_a is not None and "consolidated" in src_a.policy_tags
        assert src_b is not None and "consolidated" in src_b.policy_tags
        assert src_a.status == MemoryStatus.ACTIVE
        assert src_b.status == MemoryStatus.ACTIVE
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_consolidate_llm_path_tags_reflection():
    class FakeClient:
        def chat_json(self, system: str, user: str):
            return {"summary": "Acme pricing and VIP confirmed."}

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path, client=FakeClient())
        svc.remember(_episodic("Acme meeting discussed pricing."))
        svc.remember(_episodic("Acme follow-up confirmed VIP status."))
        written = svc.consolidate("ws1")
        assert len(written) == 1
        assert "reflection" in written[0].policy_tags
        assert written[0].source.get("path") == "llm"
        assert "Acme pricing" in written[0].content or written[0].content.startswith(
            "Distilled:"
        )
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_consolidate_skips_singleton_groups():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        svc.remember(_episodic("Only one Acme note."))
        written = svc.consolidate("ws1")
        assert written == []
    finally:
        Path(db_path).unlink(missing_ok=True)
