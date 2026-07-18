from __future__ import annotations

from continuum_memory.embeddings import cosine_similarity, embed_text
from continuum_memory.schemas import Memory, MemoryStatus


def _sparse_score(memory: Memory, query: str, entities: list[str] | None) -> float:
    q_lower = (query or "").lower().strip()
    haystack = f"{memory.content} {' '.join(memory.entities)}".lower()
    score = 0.0
    if q_lower:
        if q_lower in haystack:
            score += 5.0
        for term in q_lower.split():
            if term and term in haystack:
                score += 1.5
    entity_set = {e.lower() for e in (entities or [])}
    if entity_set:
        mem_entities = {e.lower() for e in memory.entities}
        overlap = entity_set.intersection(mem_entities)
        score += 3.0 * len(overlap)
        for e in entities or []:
            if e.lower() in memory.content.lower():
                score += 1.0
    # Slot / entity boost from query tokens matching slot values
    for key, val in (memory.slots or {}).items():
        if str(val).lower() in q_lower or key.lower() in q_lower:
            score += 2.0
    return score


def sparse_retrieve(
    memories: list[Memory],
    query: str,
    top_k: int = 50,
    entities: list[str] | None = None,
) -> list[Memory]:
    ranked = sorted(
        memories,
        key=lambda m: _sparse_score(m, query, entities),
        reverse=True,
    )
    # Keep only positive-scoring when query present; otherwise return top_k by utility
    if (query or "").strip() or entities:
        filtered = [m for m in ranked if _sparse_score(m, query, entities) > 0]
        if filtered:
            return filtered[:top_k]
    return ranked[:top_k]


def dense_retrieve(
    memories: list[Memory],
    query: str,
    top_k: int = 50,
) -> list[Memory]:
    if not memories:
        return []
    q_vec = embed_text(query or " ")
    scored: list[tuple[float, Memory]] = []
    for mem in memories:
        text = f"{mem.content} {' '.join(mem.entities)}"
        m_vec = embed_text(text)
        scored.append((cosine_similarity(q_vec, m_vec), mem))
    scored.sort(key=lambda x: x[0], reverse=True)
    # Drop near-zero similarity when we have a real query
    if (query or "").strip():
        positive = [m for s, m in scored if s > 0.05]
        if positive:
            return positive[:top_k]
    return [m for _, m in scored[:top_k]]


def retrieve_candidates(
    store,
    workspace_id: str,
    query: str,
    top_k: int = 50,
    entities: list[str] | None = None,
    *,
    as_of=None,
) -> list[Memory]:
    """Hybrid sparse + dense retrieve; returns deduped candidate union only."""
    if hasattr(store, "list_by_workspace"):
        try:
            active = store.list_by_workspace(
                workspace_id, MemoryStatus.ACTIVE, as_of=as_of
            )
        except TypeError:
            active = store.list_by_workspace(workspace_id, MemoryStatus.ACTIVE)
    else:
        active = []

    if not active:
        return []

    # Small workspaces: skip ranking loss — pack all active memories as candidates.
    if len(active) <= top_k:
        return active

    sparse = sparse_retrieve(active, query, top_k=top_k, entities=entities)
    dense = dense_retrieve(active, query, top_k=top_k)

    seen: set[str] = set()
    merged: list[Memory] = []
    for mem in sparse + dense:
        if mem.id in seen:
            continue
        seen.add(mem.id)
        merged.append(mem)
        if len(merged) >= top_k * 2:
            break

    # Ensure entity-filtered sparse hits aren't dropped when query is weak
    if entities:
        for mem in sparse_retrieve(active, "", top_k=top_k, entities=entities):
            if mem.id not in seen:
                seen.add(mem.id)
                merged.append(mem)

    return merged
