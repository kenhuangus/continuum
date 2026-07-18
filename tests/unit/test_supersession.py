from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.service import MemoryService

pytestmark = pytest.mark.unit


def _decision(content: str, workspace: str = "ws1") -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id=workspace,
        type=MemoryType.DECISION,
        content=content,
        entities=["Acme"],
        created_at=now,
        last_accessed_at=now,
    )


def test_conflicting_decision_supersedes_old():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        old = _decision("Approved 10% discount for Acme.")
        new = _decision("Approved 12% discount for Acme through 2026.")

        svc.remember(old)
        svc.remember(new)

        active = svc.list_memories("ws1", MemoryStatus.ACTIVE)
        superseded = svc.list_memories("ws1", MemoryStatus.SUPERSEDED)

        assert len(active) == 1
        assert active[0].content.startswith("Approved 12%")
        assert len(superseded) == 1
        assert superseded[0].superseded_by == active[0].id
    finally:
        Path(db_path).unlink(missing_ok=True)
