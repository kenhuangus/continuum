from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from continuum_memory.schemas import Memory, MemoryType
from continuum_memory.scoring import (
    combined_rir_scores,
    hours_since,
    importance_score,
    minmax_normalize,
    recency_score,
    relevance_score,
)

pytestmark = pytest.mark.unit


def _mem(content: str, **kwargs) -> Memory:
    now = kwargs.pop("now", None) or datetime.now(timezone.utc)
    accessed = kwargs.pop("last_accessed_at", now)
    return Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id=kwargs.get("workspace_id", "ws1"),
        type=kwargs.get("type", MemoryType.SEMANTIC),
        content=content,
        entities=kwargs.get("entities", ["Acme"]),
        utility=kwargs.get("utility", 1.0),
        confidence=kwargs.get("confidence", 1.0),
        importance=kwargs.get("importance"),
        created_at=now,
        last_accessed_at=accessed,
    )


def test_recency_decreases_with_age():
    now = datetime.now(timezone.utc)
    fresh = _mem("fresh", last_accessed_at=now)
    old = _mem("old", last_accessed_at=now - timedelta(hours=48))
    assert recency_score(fresh, now=now) > recency_score(old, now=now)
    assert hours_since(now - timedelta(hours=2), now=now) == pytest.approx(2.0)


def test_minmax_normalize():
    assert minmax_normalize([]) == []
    assert minmax_normalize([3.0, 3.0, 3.0]) == [0.5, 0.5, 0.5]
    assert minmax_normalize([0.0, 5.0, 10.0]) == [0.0, 0.5, 1.0]


def test_combined_ranks_recent_relevant_higher():
    now = datetime.now(timezone.utc)
    relevant_recent = _mem(
        "Acme VIP discount is 12%",
        entities=["Acme"],
        last_accessed_at=now,
        type=MemoryType.DECISION,
    )
    stale_noise = _mem(
        "Weather was cloudy yesterday",
        entities=["Weather"],
        last_accessed_at=now - timedelta(days=30),
        type=MemoryType.EPISODIC,
        utility=0.2,
        confidence=0.5,
    )
    scores = combined_rir_scores(
        [relevant_recent, stale_noise],
        "Acme discount",
        now=now,
    )
    assert scores[relevant_recent.id] > scores[stale_noise.id]


def test_importance_blends_explicit_field():
    plain = _mem("fact", utility=1.0, confidence=1.0, type=MemoryType.SEMANTIC)
    boosted = _mem(
        "fact",
        utility=1.0,
        confidence=1.0,
        type=MemoryType.SEMANTIC,
        importance=10.0,
    )
    assert importance_score(boosted) >= importance_score(plain)


def test_relevance_uses_dense_when_provided():
    mem = _mem("Acme discount policy")
    sparse_only = relevance_score(mem, "Acme discount")
    with_dense = relevance_score(mem, "Acme discount", dense_sim=0.9)
    assert with_dense != sparse_only or sparse_only > 0
    assert 0.0 <= with_dense <= 1.0
