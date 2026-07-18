"""Generative Agents–style RIR scoring (Park et al. 2023)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from continuum_memory.schemas import Memory, MemoryType

_TYPE_PRIOR: dict[MemoryType, float] = {
    MemoryType.DECISION: 1.0,
    MemoryType.PREFERENCE: 0.9,
    MemoryType.SEMANTIC: 0.7,
    MemoryType.PROCEDURAL: 0.6,
    MemoryType.EPISODIC: 0.4,
    MemoryType.ARTIFACT_REF: 0.3,
}


def hours_since(dt: datetime, now: datetime | None = None) -> float:
    """Hours between dt and now (timezone-aware UTC; naive dt treated as UTC)."""
    if now is None:
        now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = now - dt
    return max(0.0, delta.total_seconds() / 3600.0)


def recency_score(
    memory: Memory,
    now: datetime | None = None,
    decay: float = 0.995,
) -> float:
    """Exponential decay on hours since last_accessed_at."""
    accessed = memory.last_accessed_at
    return float(decay ** hours_since(accessed, now))


def _normalize_importance(value: float) -> float:
    """Clamp/normalize an explicit importance to ~[0, 1]."""
    if value > 1.0:
        # Common 1–10 scale
        if value <= 10.0:
            return min(1.0, value / 10.0)
        return 1.0
    return max(0.0, min(1.0, value))


def importance_score(memory: Memory) -> float:
    """0.4*utility + 0.4*confidence + 0.2*type_prior, optionally blended with importance."""
    u = float(memory.utility)
    c = float(memory.confidence)
    prior = _TYPE_PRIOR.get(memory.type, 0.5)
    base = 0.4 * u + 0.4 * c + 0.2 * prior

    imp = getattr(memory, "importance", None)
    if imp is not None:
        return 0.5 * _normalize_importance(float(imp)) + 0.5 * base
    return base


def _sparse_overlap(memory: Memory, query: str) -> float:
    q = (query or "").lower().strip()
    if not q:
        return 0.0
    terms = [t for t in q.split() if t]
    if not terms:
        return 0.0
    haystack = f"{memory.content} {' '.join(memory.entities)}".lower()
    hits = sum(1 for t in terms if t in haystack)
    return min(1.0, hits / max(1, len(terms)))


def relevance_score(
    memory: Memory,
    query: str,
    dense_sim: float | None = None,
) -> float:
    sparse = _sparse_overlap(memory, query)
    if dense_sim is not None:
        d = max(0.0, min(1.0, float(dense_sim)))
        return 0.6 * d + 0.4 * sparse
    return sparse


def minmax_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def combined_rir_scores(
    memories: list[Memory],
    query: str,
    now: datetime | None = None,
    dense_sims: dict[str, float] | None = None,
) -> dict[str, float]:
    """Min-max normalize R/I/Rel over the set; score = r_norm + i_norm + rel_norm."""
    if not memories:
        return {}
    sims = dense_sims or {}
    raw_r = [recency_score(m, now=now) for m in memories]
    raw_i = [importance_score(m) for m in memories]
    raw_rel = [
        relevance_score(m, query, dense_sim=sims.get(m.id)) for m in memories
    ]
    n_r = minmax_normalize(raw_r)
    n_i = minmax_normalize(raw_i)
    n_rel = minmax_normalize(raw_rel)
    return {
        m.id: n_r[i] + n_i[i] + n_rel[i]
        for i, m in enumerate(memories)
    }


def score_breakdown(
    memory: Memory,
    query: str,
    now: datetime | None = None,
    dense_sim: float | None = None,
    peers: list[Memory] | None = None,
) -> dict[str, Any]:
    """Return recency, importance, relevance, combined for explanations."""
    r = recency_score(memory, now=now)
    i = importance_score(memory)
    rel = relevance_score(memory, query, dense_sim=dense_sim)
    if peers:
        sims = {memory.id: dense_sim} if dense_sim is not None else None
        scores = combined_rir_scores(peers, query, now=now, dense_sims=sims)
        combined = scores.get(memory.id, r + i + rel)
    else:
        combined = r + i + rel
    return {
        "recency": r,
        "importance": i,
        "relevance": rel,
        "combined": combined,
    }
