"""Lightweight memory graph: entity links and 1-hop expansion."""

from __future__ import annotations

from continuum_memory.schemas import Memory, MemoryStatus

RELATION_RELATED = "related_to"
RELATION_MENTIONS = "mentions_entity"
RELATION_SUPERSEDES = "supersedes"


def link_on_remember(store, memory: Memory, max_links: int = 5) -> list[str]:
    """Create related_to edges for shared entities; supersedes edges when listed.

    Returns list of created edge ids.
    """
    created: list[str] = []
    if not hasattr(store, "add_edge"):
        return created

    ws = memory.workspace_id
    mem_entities = {e.lower() for e in (memory.entities or []) if e}

    if mem_entities:
        try:
            others = store.list_by_workspace(ws, MemoryStatus.ACTIVE)
        except TypeError:
            others = store.list_by_workspace(ws, MemoryStatus.ACTIVE)
        linked = 0
        for other in others:
            if other.id == memory.id:
                continue
            other_ents = {e.lower() for e in (other.entities or []) if e}
            if not mem_entities.intersection(other_ents):
                continue
            eid = store.add_edge(ws, memory.id, other.id, RELATION_RELATED)
            if eid:
                created.append(eid)
            linked += 1
            if linked >= max_links:
                break

    for old_id in memory.supersedes or []:
        if not old_id:
            continue
        eid = store.add_edge(ws, memory.id, old_id, RELATION_SUPERSEDES)
        if eid:
            created.append(eid)

    return created


def expand_neighbors(
    store,
    workspace_id: str,
    seed_ids: list[str],
    limit: int = 20,
) -> list[Memory]:
    """1-hop ACTIVE neighbors via edges, excluding seeds."""
    if not seed_ids or not hasattr(store, "edges_for"):
        return []

    seed_set = set(seed_ids)
    neighbor_ids: list[str] = []
    seen: set[str] = set()

    for sid in seed_ids:
        try:
            edges = store.edges_for(workspace_id, sid)
        except Exception:
            continue
        for edge in edges:
            # edge may be dict or tuple
            if isinstance(edge, dict):
                src = edge.get("src_id")
                dst = edge.get("dst_id")
            else:
                # (id, workspace_id, src_id, dst_id, relation, created_at)
                src = edge[2] if len(edge) > 2 else None
                dst = edge[3] if len(edge) > 3 else None
            for nid in (src, dst):
                if not nid or nid in seed_set or nid in seen:
                    continue
                seen.add(nid)
                neighbor_ids.append(nid)
                if len(neighbor_ids) >= limit:
                    break
        if len(neighbor_ids) >= limit:
            break

    if not neighbor_ids:
        return []

    if hasattr(store, "get_many"):
        memories = store.get_many(neighbor_ids[:limit])
    else:
        memories = []
        for nid in neighbor_ids[:limit]:
            m = store.get(nid)
            if m:
                memories.append(m)

    return [m for m in memories if m.status == MemoryStatus.ACTIVE]
