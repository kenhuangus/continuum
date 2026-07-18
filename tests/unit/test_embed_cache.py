from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.embed_cache import content_hash, get_or_embed
from continuum_memory.schemas import Memory, MemoryType
from continuum_memory.store import MemoryStore

pytestmark = pytest.mark.unit


def _mem(content: str, **kwargs) -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=kwargs.get("id") or str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id="ws_cache",
        type=MemoryType.SEMANTIC,
        content=content,
        entities=kwargs.get("entities", ["Acme"]),
        created_at=now,
        last_accessed_at=now,
    )


def test_get_or_embed_cache_hit(tmp_path: Path):
    store = MemoryStore(db_path=tmp_path / "cache.db")
    mem = _mem("Acme VIP discount is 12%")
    store.remember(mem)

    v1 = get_or_embed(store, mem)
    hit = store.get_embed_cache(mem.id)
    assert hit is not None
    assert hit[0] == content_hash(mem)
    assert hit[1] == v1

    v2 = get_or_embed(store, mem)
    assert v2 == v1
