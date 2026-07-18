from __future__ import annotations

import os

from continuum_memory.ann_index import ANNIndex
from continuum_memory.bm25 import BM25
from continuum_memory.embed_cache import get_or_embed
from continuum_memory.embeddings import cosine_similarity, embed_text
from continuum_memory.schemas import Memory, MemoryStatus
from continuum_memory.scoring import combined_rir_scores


def _rir_disabled() -> bool:
    return os.environ.get("CONTINUUM_DISABLE_RIR", "").lower() in ("1", "true", "yes")


def _bm25_scores(memories: list[Memory], query: str) -> dict[str, float]:
    """BM25 over `content + entities` for each candidate — primary sparse score."""
    if not memories or not (query or "").strip():
        return {m.id: 0.0 for m in memories}
    docs = [f"{m.content} {' '.join(m.entities)}" for m in memories]
    index = BM25(docs)
    scores = index.scores(query)
    return {m.id: s for m, s in zip(memories, scores)}


def _entity_slot_bonus(memory: Memory, query: str, entities: list[str] | None) -> float:
    """Additive bonuses on top of BM25 for exact entity/slot overlap."""
    q_lower = (query or "").lower().strip()
    score = 0.0
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


def _sparse_score(memory: Memory, query: str, entities: list[str] | None) -> float:
    """Single-memory sparse score (BM25 computed against itself as a 1-doc corpus).

    Kept for callers that need a per-memory score outside the batch path; prefer
    `sparse_retrieve`, which batches BM25 over the full candidate set (BM25's
    IDF term is corpus-relative, so batch scoring is the more meaningful path).
    """
    bm25 = _bm25_scores([memory], query)
    return bm25.get(memory.id, 0.0) + _entity_slot_bonus(memory, query, entities)


def sparse_retrieve(
    memories: list[Memory],
    query: str,
    top_k: int = 50,
    entities: list[str] | None = None,
) -> list[Memory]:
    bm25 = _bm25_scores(memories, query)

    def combined(m: Memory) -> float:
        return bm25.get(m.id, 0.0) + _entity_slot_bonus(m, query, entities)

    ranked = sorted(memories, key=combined, reverse=True)
    # Keep only positive-scoring when query present; otherwise return top_k by utility
    if (query or "").strip() or entities:
        filtered = [m for m in ranked if combined(m) > 0]
        if filtered:
            return filtered[:top_k]
    return ranked[:top_k]


def dense_retrieve(
    memories: list[Memory],
    query: str,
    top_k: int = 50,
    store=None,
) -> list[Memory]:
    ranked, _sims = dense_retrieve_with_sims(memories, query, top_k=top_k, store=store)
    return ranked


def dense_retrieve_with_sims(
    memories: list[Memory],
    query: str,
    top_k: int = 50,
    store=None,
) -> tuple[list[Memory], dict[str, float]]:
    """ANN shortlist (numpy IVF-lite / brute-force fallback) then exact cosine.

    For workspace sizes at or below `ann_index.BRUTE_FORCE_THRESHOLD` this is
    mathematically identical to a full brute-force cosine scan — the ANN path
    only changes behavior (and reduces work) on larger candidate sets.
    """
    if not memories:
        return [], {}
    q_vec = embed_text(query or " ")
    by_id = {m.id: m for m in memories}
    ids = [m.id for m in memories]
    vectors = [get_or_embed(store, m) for m in memories]

    index = ANNIndex(ids, vectors)
    shortlist = index.search(q_vec, top_k=top_k)
    sims: dict[str, float] = {mid: sim for mid, sim in shortlist}
    scored = sorted(
        ((sim, by_id[mid]) for mid, sim in shortlist if mid in by_id),
        key=lambda x: x[0],
        reverse=True,
    )

    if (query or "").strip():
        positive = [m for s, m in scored if s > 0.05]
        if positive:
            return positive[:top_k], sims
    return [m for _, m in scored[:top_k]], sims


def _build_dense_sims(memories: list[Memory], query: str, store=None) -> dict[str, float]:
    if not memories:
        return {}
    q_vec = embed_text(query or " ")
    sims: dict[str, float] = {}
    for mem in memories:
        sims[mem.id] = cosine_similarity(q_vec, get_or_embed(store, mem))
    return sims


def retrieve_candidates(
    store,
    workspace_id: str,
    query: str,
    top_k: int = 50,
    entities: list[str] | None = None,
    *,
    as_of=None,
    org_id: str | None = None,
) -> list[Memory]:
    """Hybrid sparse + dense retrieve; returns deduped candidate union only."""
    # Point-in-time (as_of): include SUPERSEDED rows still effective at that time;
    # exclude FORGOTTEN. Without as_of: ACTIVE only (current truth).
    status_filter = None if as_of is not None else MemoryStatus.ACTIVE
    if hasattr(store, "list_by_workspace"):
        try:
            active = store.list_by_workspace(
                workspace_id, status_filter, as_of=as_of, org_id=org_id
            )
        except TypeError:
            try:
                active = store.list_by_workspace(
                    workspace_id, status_filter, as_of=as_of
                )
            except TypeError:
                active = store.list_by_workspace(workspace_id, status_filter)
            if org_id is not None:
                active = [m for m in active if m.org_id == org_id]
    else:
        active = []

    if as_of is not None:
        active = [m for m in active if m.status != MemoryStatus.FORGOTTEN]

    if not active:
        return []

    # Small workspaces: skip ranking loss — pack all active memories as candidates.
    if len(active) <= top_k:
        return active

    sparse = sparse_retrieve(active, query, top_k=top_k, entities=entities)
    dense, dense_sims = dense_retrieve_with_sims(
        active, query, top_k=top_k, store=store
    )

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

    # Optional 1-hop graph expansion before RIR
    try:
        from continuum_memory.graph import expand_neighbors

        neighbors = expand_neighbors(
            store, workspace_id, [m.id for m in merged], limit=20
        )
        for mem in neighbors:
            if mem.id not in seen:
                seen.add(mem.id)
                merged.append(mem)
    except Exception:
        pass

    # HippoRAG-inspired multi-hop: personalized PageRank restart from the
    # current candidate set, capturing entity-graph-connected memories beyond
    # the 1-hop neighbor expansion above (design notes §2 — PPR over
    # entity/supersedes edges only, not a full passage-graph pipeline).
    try:
        from continuum_memory.graph import expand_ppr

        ppr_expanded = expand_ppr(store, workspace_id, [m.id for m in merged], limit=20)
        for mem in ppr_expanded:
            if mem.id not in seen:
                seen.add(mem.id)
                merged.append(mem)
    except Exception:
        pass

    # Defense-in-depth: graph/PPR expansion can pull in edges that were not
    # scoped by org_id at the store layer (memory_edges are workspace-scoped
    # today). Strip any cross-org leakage before packing/ranking.
    if org_id is not None:
        merged = [m for m in merged if m.org_id == org_id]

    if _rir_disabled():
        return merged[: top_k * 2]

    # Dense sims for RIR: reuse dense path sims; fill gaps for graph neighbors
    sims = {mid: dense_sims[mid] for mid in dense_sims if mid in seen}
    missing = [m for m in merged if m.id not in sims]
    if missing:
        sims.update(_build_dense_sims(missing, query, store=store))

    scores = combined_rir_scores(merged, query, dense_sims=sims)
    ranked = sorted(merged, key=lambda m: scores.get(m.id, 0.0), reverse=True)
    return ranked[: top_k * 2]
