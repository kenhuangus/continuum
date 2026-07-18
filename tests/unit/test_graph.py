from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.graph import (
    expand_neighbors,
    expand_ppr,
    link_on_remember,
    personalized_pagerank,
)
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


def _chain_abc(store: MemoryStore) -> tuple[Memory, Memory, Memory]:
    """A —related_to— B —related_to— C, with no direct A↔C edge (2 hops apart)."""
    a = _mem("Node A content.", entities=["NodeA"])
    b = _mem("Node B content.", entities=["NodeB"])
    c = _mem("Node C content.", entities=["NodeC"])
    store.remember(a)
    store.remember(b)
    store.remember(c)
    store.add_edge("ws1", a.id, b.id, "related_to")
    store.add_edge("ws1", b.id, c.id, "related_to")
    return a, b, c


def test_expand_neighbors_is_1hop_only():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        a, b, c = _chain_abc(store)
        neighbors = expand_neighbors(store, "ws1", [a.id], limit=20)
        neighbor_ids = {n.id for n in neighbors}
        assert b.id in neighbor_ids
        assert c.id not in neighbor_ids
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_personalized_pagerank_scores_decay_with_distance():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        a, b, c = _chain_abc(store)
        scores = personalized_pagerank(store, "ws1", [a.id])
        assert scores.get(a.id, 0.0) > 0.0
        # Closer node (1-hop) should outrank the farther node (2-hop).
        assert scores.get(b.id, 0.0) > scores.get(c.id, 0.0)
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_personalized_pagerank_empty_seeds_returns_empty():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        assert personalized_pagerank(store, "ws1", []) == {}
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_expand_ppr_reaches_second_hop_neighbor():
    """HippoRAG-inspired multi-hop: PPR restart from A should surface C even
    though C is 2 hops away and outside expand_neighbors' 1-hop reach."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        a, b, c = _chain_abc(store)
        ppr_expanded = expand_ppr(store, "ws1", [a.id], limit=20)
        ppr_ids = {n.id for n in ppr_expanded}
        assert b.id in ppr_ids
        assert c.id in ppr_ids
        assert a.id not in ppr_ids  # seeds excluded from expansion results
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_expand_ppr_excludes_non_active_memories():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        a, b, _c = _chain_abc(store)
        store.forget(b.id, reason="test")
        ppr_expanded = expand_ppr(store, "ws1", [a.id], limit=20)
        assert all(n.id != b.id for n in ppr_expanded)
    finally:
        Path(db_path).unlink(missing_ok=True)
