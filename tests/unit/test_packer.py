from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from continuum_memory.packer import memory_tokens, pack_context
from continuum_memory.schemas import Memory, MemoryType

pytestmark = pytest.mark.unit


def _mem(content: str, mem_type: MemoryType = MemoryType.SEMANTIC, **kwargs) -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id="ws1",
        type=mem_type,
        content=content,
        entities=kwargs.get("entities", []),
        confidence=kwargs.get("confidence", 0.9),
        utility=kwargs.get("utility", 1.0),
        created_at=now,
        last_accessed_at=now,
    )


def test_greedy_packer_never_exceeds_budget():
    memories = [
        _mem("x" * 200, MemoryType.DECISION),
        _mem("y" * 200, MemoryType.PREFERENCE),
        _mem("z" * 200, MemoryType.SEMANTIC),
        _mem("w" * 200, MemoryType.EPISODIC),
    ]
    budget = 100
    pack = pack_context(memories, "query", budget, algorithm="greedy")
    assert pack.token_estimate <= budget


def test_type_quota_packer_never_exceeds_budget():
    memories = [
        _mem("Decision " + "a" * 80, MemoryType.DECISION),
        _mem("Preference " + "b" * 80, MemoryType.PREFERENCE),
        _mem("Semantic " + "c" * 80, MemoryType.SEMANTIC),
        _mem("Episodic " + "d" * 80, MemoryType.EPISODIC),
    ]
    for budget in (50, 100, 200, 500):
        pack = pack_context(memories, "decision preference", budget, algorithm="type_quota")
        assert pack.token_estimate <= budget, f"budget={budget} got {pack.token_estimate}"


def test_memory_tokens_positive():
    m = _mem("hello world")
    assert memory_tokens(m) >= 1
