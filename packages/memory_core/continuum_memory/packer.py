from __future__ import annotations

import math
from continuum_memory.schemas import Memory, MemoryType, PackedContext


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def memory_tokens(memory: Memory) -> int:
    return estimate_tokens(memory.content) + estimate_tokens(" ".join(memory.entities)) + 8


def _score(memory: Memory, query: str) -> float:
    q = query.lower()
    score = memory.utility * memory.confidence
    haystack = f"{memory.content} {' '.join(memory.entities)}".lower()
    if q:
        for term in q.split():
            if term in haystack:
                score += 2.0
    type_boost = {
        MemoryType.DECISION: 4.0,
        MemoryType.PREFERENCE: 3.5,
        MemoryType.SEMANTIC: 2.5,
        MemoryType.PROCEDURAL: 2.0,
        MemoryType.EPISODIC: 1.0,
        MemoryType.ARTIFACT_REF: 0.5,
    }
    score += type_boost.get(memory.type, 1.0)
    return score


def pack_greedy(
    memories: list[Memory],
    query: str,
    budget_tokens: int,
) -> PackedContext:
    ranked = sorted(memories, key=lambda m: _score(m, query), reverse=True)
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
        explanations.append(
            f"Included [{mem.id[:8]}] ({mem.type.value}): score={_score(mem, query):.1f}, "
            f"tokens={cost}"
        )

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
            key=lambda m: _score(m, query),
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
        key=lambda m: _score(m, query),
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
) -> PackedContext:
    """0/1 knapsack DP on token costs with score as value. Caps items for runtime."""
    items = sorted(memories, key=lambda m: _score(m, query), reverse=True)[:40]
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
    values = [_score(m, query) for m in items]
    # DP: dp[t] = best (value, bitmask-as-set via prev pointers)
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
            rel = _score(mem, query)
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
    algo = (algorithm or "type_quota").lower()
    if algo == "greedy":
        result = pack_greedy(memories, query, budget_tokens)
    elif algo in ("knapsack", "knapsack_dp"):
        result = pack_knapsack_dp(memories, query, budget_tokens)
    elif algo == "mmr":
        result = pack_mmr(memories, query, budget_tokens)
    else:
        result = pack_type_quota(memories, query, budget_tokens)

    assert result.token_estimate <= budget_tokens, "Packer exceeded budget"
    return result
