from __future__ import annotations

import math
import os
import re

from continuum_memory.schemas import Memory, MemoryType, PackedContext
from continuum_memory.scoring import combined_rir_scores, score_breakdown

_TYPE_BOOST: dict[MemoryType, float] = {
    MemoryType.DECISION: 1.2,
    MemoryType.PREFERENCE: 1.0,
    MemoryType.SEMANTIC: 0.5,
    MemoryType.PROCEDURAL: 0.3,
    MemoryType.EPISODIC: 0.1,
    MemoryType.ARTIFACT_REF: 0.0,
}

_STALE_LANGUAGE_RE = re.compile(
    r"(?i)\bobsolete\b|\boutdated\b|\bno longer\b|\bsuperseded\b|\bwas floated\b"
)
_STALE_LANGUAGE_PENALTY = 5.0


def _is_obsolescence_marker(memory: Memory) -> bool:
    """True for extractor-emitted retraction markers (see extractor.py).

    These never carry positive packing value — they exist purely so
    `supersession.apply_supersession` can retire stale active facts — and must
    never be surfaced in packed context (noise-budget stale-leak fix).
    """
    slots = memory.slots or {}
    return "obsolete_slot" in slots and "obsolete_value" in slots


def _has_stale_language(memory: Memory) -> bool:
    return bool(_STALE_LANGUAGE_RE.search(memory.content or ""))


def filter_packable(memories: list[Memory]) -> list[Memory]:
    """Drop obsolescence markers before any packing algorithm sees candidates."""
    return [m for m in memories if not _is_obsolescence_marker(m)]


_LEGACY_TYPE_BOOST: dict[MemoryType, float] = {
    MemoryType.DECISION: 4.0,
    MemoryType.PREFERENCE: 3.5,
    MemoryType.SEMANTIC: 2.5,
    MemoryType.PROCEDURAL: 2.0,
    MemoryType.EPISODIC: 1.0,
    MemoryType.ARTIFACT_REF: 0.5,
}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def memory_tokens(memory: Memory) -> int:
    return estimate_tokens(memory.content) + estimate_tokens(" ".join(memory.entities)) + 8


def _rir_disabled() -> bool:
    return os.environ.get("CONTINUUM_DISABLE_RIR", "").lower() in ("1", "true", "yes")


def _legacy_score(memory: Memory, query: str) -> float:
    q = query.lower()
    score = memory.utility * memory.confidence
    haystack = f"{memory.content} {' '.join(memory.entities)}".lower()
    if q:
        for term in q.split():
            if term in haystack:
                score += 2.0
    score += _LEGACY_TYPE_BOOST.get(memory.type, 1.0)
    if _has_stale_language(memory):
        score -= _STALE_LANGUAGE_PENALTY
    return score


def _score(
    memory: Memory,
    query: str,
    rir_scores: dict[str, float] | None = None,
) -> float:
    if rir_scores is not None and not _rir_disabled():
        score = rir_scores.get(memory.id, 0.0) + _TYPE_BOOST.get(memory.type, 0.0)
        if _has_stale_language(memory):
            score -= _STALE_LANGUAGE_PENALTY
        return score
    return _legacy_score(memory, query)


def _rir_map(memories: list[Memory], query: str) -> dict[str, float] | None:
    if _rir_disabled() or not memories:
        return None
    return combined_rir_scores(memories, query)


def _explain_include(mem: Memory, query: str, cost: int, score: float, prefix: str) -> str:
    try:
        bd = score_breakdown(mem, query)
        return (
            f"{prefix} [{mem.id[:8]}] ({mem.type.value}): score={score:.2f}, "
            f"r={bd['recency']:.2f} i={bd['importance']:.2f} rel={bd['relevance']:.2f}, "
            f"tokens={cost}"
        )
    except Exception:
        return f"{prefix} [{mem.id[:8]}] ({mem.type.value}): score={score:.1f}, tokens={cost}"


def pack_greedy(
    memories: list[Memory],
    query: str,
    budget_tokens: int,
    rir_scores: dict[str, float] | None = None,
) -> PackedContext:
    ranked = sorted(memories, key=lambda m: _score(m, query, rir_scores), reverse=True)
    packed: list[Memory] = []
    explanations: list[str] = []
    used = 0

    for mem in ranked:
        cost = memory_tokens(mem)
        if used + cost > budget_tokens:
            explanations.append(
                f"Excluded [{mem.id[:8]}] ({mem.type.value}): would exceed budget "
                f"({used + cost} > {budget_tokens})"
            )
            continue
        packed.append(mem)
        used += cost
        sc = _score(mem, query, rir_scores)
        explanations.append(_explain_include(mem, query, cost, sc, "Included"))

    return PackedContext(
        memories=packed,
        token_estimate=used,
        algorithm="greedy",
        explanations=explanations,
        query=query,
        budget_tokens=budget_tokens,
        candidate_count=len(memories),
    )


def pack_type_quota(
    memories: list[Memory],
    query: str,
    budget_tokens: int,
    rir_scores: dict[str, float] | None = None,
) -> PackedContext:
    quotas = [
        (MemoryType.DECISION, 0.35),
        (MemoryType.PREFERENCE, 0.25),
        (MemoryType.SEMANTIC, 0.25),
        (MemoryType.PROCEDURAL, 0.10),
        (MemoryType.EPISODIC, 0.05),
        (MemoryType.ARTIFACT_REF, 0.05),
    ]

    packed: list[Memory] = []
    explanations: list[str] = []
    used = 0
    remaining = list(memories)
    included_ids: set[str] = set()

    for mem_type, fraction in quotas:
        type_budget = max(1, int(budget_tokens * fraction))
        type_used = 0
        candidates = sorted(
            [m for m in remaining if m.type == mem_type and m.id not in included_ids],
            key=lambda m: _score(m, query, rir_scores),
            reverse=True,
        )
        for mem in candidates:
            cost = memory_tokens(mem)
            if type_used + cost > type_budget or used + cost > budget_tokens:
                explanations.append(
                    f"Excluded [{mem.id[:8]}] ({mem.type.value}): type quota or global budget"
                )
                continue
            packed.append(mem)
            included_ids.add(mem.id)
            type_used += cost
            used += cost
            explanations.append(
                f"Included [{mem.id[:8]}] ({mem.type.value}): type_quota slot, tokens={cost}"
            )

    leftovers = sorted(
        [m for m in remaining if m.id not in included_ids],
        key=lambda m: _score(m, query, rir_scores),
        reverse=True,
    )
    for mem in leftovers:
        cost = memory_tokens(mem)
        if used + cost > budget_tokens:
            continue
        packed.append(mem)
        used += cost
        explanations.append(
            f"Included [{mem.id[:8]}] ({mem.type.value}): leftover budget fill"
        )

    return PackedContext(
        memories=packed,
        token_estimate=used,
        algorithm="type_quota",
        explanations=explanations,
        query=query,
        budget_tokens=budget_tokens,
        candidate_count=len(memories),
    )


def pack_knapsack_dp(
    memories: list[Memory],
    query: str,
    budget_tokens: int,
    rir_scores: dict[str, float] | None = None,
) -> PackedContext:
    """0/1 knapsack DP on token costs with score as value. Caps items for runtime."""
    items = sorted(memories, key=lambda m: _score(m, query, rir_scores), reverse=True)[:40]
    n = len(items)
    if n == 0 or budget_tokens <= 0:
        return PackedContext(
            memories=[],
            token_estimate=0,
            algorithm="knapsack_dp",
            explanations=[],
            query=query,
            budget_tokens=budget_tokens,
            candidate_count=len(memories),
        )

    costs = [memory_tokens(m) for m in items]
    values = [_score(m, query, rir_scores) for m in items]
    dp = [-math.inf] * (budget_tokens + 1)
    dp[0] = 0.0
    choose: list[dict[int, int]] = [{} for _ in range(n)]

    for i, (c, v) in enumerate(zip(costs, values)):
        if c > budget_tokens:
            continue
        for t in range(budget_tokens, c - 1, -1):
            cand = dp[t - c] + v
            if cand > dp[t]:
                dp[t] = cand
                choose[i][t] = t - c

    best_t = max(range(budget_tokens + 1), key=lambda t: dp[t])
    selected: list[Memory] = []
    explanations: list[str] = []
    t = best_t
    for i in range(n - 1, -1, -1):
        if t in choose[i]:
            selected.append(items[i])
            explanations.append(
                f"Included [{items[i].id[:8]}] ({items[i].type.value}): knapsack_dp, "
                f"score={values[i]:.1f}, tokens={costs[i]}"
            )
            t = choose[i][t]

    selected.reverse()
    used = sum(memory_tokens(m) for m in selected)
    return PackedContext(
        memories=selected,
        token_estimate=used,
        algorithm="knapsack_dp",
        explanations=explanations,
        query=query,
        budget_tokens=budget_tokens,
        candidate_count=len(memories),
    )


def _token_overlap(a: Memory, b: Memory) -> float:
    ta = set(a.content.lower().split())
    tb = set(b.content.lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def pack_mmr(
    memories: list[Memory],
    query: str,
    budget_tokens: int,
    lambda_mult: float = 0.7,
    rir_scores: dict[str, float] | None = None,
) -> PackedContext:
    """Maximal Marginal Relevance packing under token budget."""
    remaining = list(memories)
    packed: list[Memory] = []
    explanations: list[str] = []
    used = 0

    while remaining:
        best: Memory | None = None
        best_score = -math.inf
        for mem in remaining:
            cost = memory_tokens(mem)
            if used + cost > budget_tokens:
                continue
            rel = _score(mem, query, rir_scores)
            div = max((_token_overlap(mem, p) for p in packed), default=0.0)
            mmr = lambda_mult * rel - (1 - lambda_mult) * div * 5.0
            if mmr > best_score:
                best_score = mmr
                best = mem
        if best is None:
            break
        cost = memory_tokens(best)
        packed.append(best)
        remaining = [m for m in remaining if m.id != best.id]
        used += cost
        explanations.append(
            f"Included [{best.id[:8]}] ({best.type.value}): mmr={best_score:.2f}, tokens={cost}"
        )

    return PackedContext(
        memories=packed,
        token_estimate=used,
        algorithm="mmr",
        explanations=explanations,
        query=query,
        budget_tokens=budget_tokens,
        candidate_count=len(memories),
    )


def pack_context(
    memories: list[Memory],
    query: str,
    budget_tokens: int,
    algorithm: str = "type_quota",
) -> PackedContext:
    memories = filter_packable(memories)
    rir_scores = _rir_map(memories, query)
    algo = (algorithm or "type_quota").lower()
    if algo == "greedy":
        result = pack_greedy(memories, query, budget_tokens, rir_scores)
    elif algo in ("knapsack", "knapsack_dp"):
        result = pack_knapsack_dp(memories, query, budget_tokens, rir_scores)
    elif algo == "mmr":
        result = pack_mmr(memories, query, budget_tokens, rir_scores=rir_scores)
    else:
        result = pack_type_quota(memories, query, budget_tokens, rir_scores)

    assert result.token_estimate <= budget_tokens, "Packer exceeded budget"
    return result
