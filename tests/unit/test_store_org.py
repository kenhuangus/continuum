"""SQLite store org_id isolation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.store import MemoryStore

pytestmark = pytest.mark.unit


def _mem(org: str, ws: str, content: str) -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=str(uuid.uuid4()),
        org_id=org,
        workspace_id=ws,
        type=MemoryType.SEMANTIC,
        content=content,
        entities=["Acme"],
        created_at=now,
        last_accessed_at=now,
        source={"test": True},
    )


def test_store_org_isolation_list_search_get_forget(tmp_path: Path):
    store = MemoryStore(tmp_path / "org_iso.db")
    ws = "shared-ws"
    a = store.remember(_mem("org_a", ws, "Org A fact about pricing"))
    b = store.remember(_mem("org_b", ws, "Org B fact about pricing"))

    listed_a = store.list_by_workspace(ws, MemoryStatus.ACTIVE, org_id="org_a")
    assert {m.id for m in listed_a} == {a.id}

    listed_b = store.list_by_workspace(ws, MemoryStatus.ACTIVE, org_id="org_b")
    assert {m.id for m in listed_b} == {b.id}

    search_a = store.search(ws, "pricing", org_id="org_a")
    assert {m.id for m in search_a} == {a.id}

    assert store.get(a.id, org_id="org_b") is None
    assert store.get(a.id, org_id="org_a") is not None

    # Cross-org forget must not succeed when org scoped
    event = store.forget(a.id, reason="test", workspace_id=ws, org_id="org_b")
    assert event is None
    assert store.get(a.id, org_id="org_a") is not None

    event_ok = store.forget(a.id, reason="test", workspace_id=ws, org_id="org_a")
    assert event_ok is not None
    assert store.get(a.id) is None or store.get(a.id).status == MemoryStatus.FORGOTTEN
