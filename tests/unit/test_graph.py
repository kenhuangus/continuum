from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.graph import expand_neighbors, link_on_remember
from continuum_memory.schemas import Memory, MemoryType
from continuum_memory.service import MemoryService
from continuum_memory.store import MemoryStore

pytestmark = pytest.mark.unit


def _mem(content: str, entities: list[str] | None = None, **kwargs) -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id=kwargs.get("workspace_id", "ws1"),
        type=kwargs.get("type", MemoryType.SEMANTIC),
        content=content,
        entities=entities or ["Acme"],
        created_at=now,
        last_accessed_at=now,
        supersedes=kwargs.get("supersedes", []),
    )


def test_link_on_remember_creates_related_edges():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        a = _mem("Acme is VIP.", entities=["Acme"])
        b = _mem("Acme discount is 12%.", entities=["Acme"])
        store.remember(a)
        store.remember(b)
        created = link_on_remember(store, b, max_links=5)
        assert len(created) >= 1
        edges = store.edges_for("ws1", b.id)
        assert any(e["relation"] == "related_to" for e in edges)
        assert any(
            {e["src_id"], e["dst_id"]} == {a.id, b.id} for e in edges
        )
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_expand_neighbors_returns_linked_memory():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        a = _mem("Acme preference: email.", entities=["Acme"])
        b = _mem("Acme SLA is 99.9%.", entities=["Acme"])
        store.remember(a)
        store.remember(b)
        link_on_remember(store, b)
        neighbors = expand_neighbors(store, "ws1", [b.id], limit=20)
        assert any(n.id == a.id for n in neighbors)
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_service_remember_creates_edges():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        a = svc.remember(_mem("Acme note one.", entities=["Acme"]))
        b = svc.remember(_mem("Acme note two.", entities=["Acme"]))
        edges = svc.store.edges_for("ws1", b.id)
        assert len(edges) >= 1
        assert a.id in {e["src_id"] for e in edges} | {e["dst_id"] for e in edges}
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_supersedes_edge_created():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        old = _mem("Old fact.", entities=["Acme"])
        store.remember(old)
        new = _mem("New fact.", entities=["Acme"], supersedes=[old.id])
        store.remember(new)
        link_on_remember(store, new)
        edges = store.edges_for("ws1", new.id)
        assert any(
            e["relation"] == "supersedes" and e["dst_id"] == old.id for e in edges
        )
    finally:
        Path(db_path).unlink(missing_ok=True)
