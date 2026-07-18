from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.store import MemoryStore

pytestmark = pytest.mark.unit


def _sample(workspace: str = "ws_test") -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id=workspace,
        type=MemoryType.SEMANTIC,
        content="Acme is VIP",
        entities=["Acme"],
        created_at=now,
        last_accessed_at=now,
    )


def test_remember_get_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        mem = _sample()
        store.remember(mem)
        fetched = store.get(mem.id)
        assert fetched is not None
        assert fetched.content == mem.content
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_list_and_search():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        m1 = _sample()
        m2 = _sample()
        m2.content = "Prefers email contact"
        m2.entities = ["Acme"]
        store.remember(m1)
        store.remember(m2)

        listed = store.list_by_workspace("ws_test", MemoryStatus.ACTIVE)
        assert len(listed) == 2

        results = store.search("ws_test", query="email")
        assert len(results) == 1
        assert "email" in results[0].content.lower()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_forget_and_audit():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        mem = _sample()
        store.remember(mem)
        event = store.forget(mem.id, reason="test")
        assert event is not None

        forgotten = store.get(mem.id)
        assert forgotten.status == MemoryStatus.FORGOTTEN

        audit = store.get_audit_log("ws_test")
        assert len(audit) == 1
        assert audit[0].reason == "test"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_remember_skips_identical_normalized_duplicate():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        first = _sample()
        first.content = "Prefers email contact"
        store.remember(first)

        dup = _sample()
        dup.content = "  Prefers   EMAIL   contact  "
        returned = store.remember(dup)

        assert returned.id == first.id
        active = store.list_by_workspace("ws_test", MemoryStatus.ACTIVE)
        assert len(active) == 1
        assert store.get(dup.id) is None
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_remember_skips_high_jaccard_near_duplicate():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        first = _sample()
        # 20 tokens so one-word change yields Jaccard 19/21 ≈ 0.905 > 0.9
        first.content = (
            "User prefers email contact for all Acme support requests during "
            "business hours on weekdays only always please use this method"
        )
        store.remember(first)

        near = _sample()
        near.content = (
            "User prefers email contact for all Acme support requests during "
            "business hours on weekdays only always please use that method"
        )
        returned = store.remember(near)

        assert returned.id == first.id
        active = store.list_by_workspace("ws_test", MemoryStatus.ACTIVE)
        assert len(active) == 1
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_remember_allows_distinct_content():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        store = MemoryStore(db_path)
        a = _sample()
        a.content = "Acme is VIP"
        b = _sample()
        b.content = "Prefers email contact"
        store.remember(a)
        store.remember(b)
        active = store.list_by_workspace("ws_test", MemoryStatus.ACTIVE)
        assert len(active) == 2
    finally:
        Path(db_path).unlink(missing_ok=True)
