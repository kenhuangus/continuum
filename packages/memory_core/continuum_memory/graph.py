"""Lightweight memory graph: entity links and 1-hop expansion."""

from __future__ import annotations

from typing import Any

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


def _edge_endpoints(edge: Any) -> tuple[str | None, str | None]:
    if isinstance(edge, dict):
        return edge.get("src_id"), edge.get("dst_id")
    # (id, workspace_id, src_id, dst_id, relation, created_at)
    src = edge[2] if len(edge) > 2 else None
    dst = edge[3] if len(edge) > 3 else None
    return src, dst


def _collect_subgraph(
    store,
    workspace_id: str,
    seed_ids: list[str],
    max_hops: int = 3,
    max_nodes: int = 200,
) -> dict[str, set[str]]:
    """Bounded BFS from `seed_ids` building an undirected adjacency map.

    Avoids requiring a "list all edges in workspace" store method — we only
    ever expand outward from seeds, which is all PPR over a memory graph needs.
    """
    adjacency: dict[str, set[str]] = {}
    visited: set[str] = {s for s in seed_ids if s}
    frontier = list(visited)
    hop = 0
    while frontier and hop < max_hops and len(visited) < max_nodes:
        next_frontier: list[str] = []
        for node in frontier:
            try:
                edges = store.edges_for(workspace_id, node)
            except Exception:
                continue
            for edge in edges:
                src, dst = _edge_endpoints(edge)
                if not src or not dst:
                    continue
                adjacency.setdefault(src, set()).add(dst)
                adjacency.setdefault(dst, set()).add(src)
                for nid in (src, dst):
                    if nid not in visited:
                        visited.add(nid)
                        next_frontier.append(nid)
            if len(visited) >= max_nodes:
                break
        frontier = next_frontier
        hop += 1
    return adjacency


def personalized_pagerank(
    store,
    workspace_id: str,
    seed_ids: list[str],
    damping: float = 0.85,
    iters: int = 20,
    max_hops: int = 3,
    max_nodes: int = 200,
) -> dict[str, float]:
    """Personalized PageRank restarting to `seed_ids` over the undirected
    memory-edge graph (`related_to` + `supersedes`).

    HippoRAG-*inspired* multi-hop retrieval (Gutiérrez et al. 2024) — this is
    PPR over Continuum's lightweight entity/supersedes edge graph, **not** the
    full HippoRAG passage-graph + OpenIE pipeline. See
    docs/research/LOOP3_NOTES.md §2 for the honest scope statement.
    """
    if not seed_ids or not hasattr(store, "edges_for"):
        return {}
    seeds = [s for s in seed_ids if s]
    if not seeds:
        return {}

    adjacency = _collect_subgraph(store, workspace_id, seeds, max_hops=max_hops, max_nodes=max_nodes)
    nodes: set[str] = set(seeds)
    for src, dsts in adjacency.items():
        nodes.add(src)
        nodes.update(dsts)
    if len(nodes) <= 1:
        return {n: 1.0 for n in nodes}

    node_list = list(nodes)
    n = len(node_list)
    idx = {nid: i for i, nid in enumerate(node_list)}
    seed_set = set(seeds)
    restart_mass = 1.0 / len(seed_set)
    restart = [restart_mass if nid in seed_set else 0.0 for nid in node_list]

    scores = list(restart)
    for _ in range(max(1, iters)):
        new_scores = [(1.0 - damping) * restart[i] for i in range(n)]
        for i, nid in enumerate(node_list):
            neighbors = adjacency.get(nid)
            if not neighbors:
                continue
            share = damping * scores[i] / len(neighbors)
            for nb in neighbors:
                j = idx.get(nb)
                if j is not None:
                    new_scores[j] += share
        scores = new_scores

    return {node_list[i]: scores[i] for i in range(n)}


def expand_ppr(
    store,
    workspace_id: str,
    seed_ids: list[str],
    limit: int = 20,
    damping: float = 0.85,
    iters: int = 20,
) -> list[Memory]:
    """Top ACTIVE nodes by personalized-PageRank mass, excluding the seeds."""
    scores = personalized_pagerank(store, workspace_id, seed_ids, damping=damping, iters=iters)
    if not scores:
        return []
    seed_set = set(seed_ids)
    ranked_ids = sorted(
        (nid for nid in scores if nid not in seed_set),
        key=lambda nid: scores[nid],
        reverse=True,
    )[:limit]
    if not ranked_ids:
        return []

    if hasattr(store, "get_many"):
        memories = store.get_many(ranked_ids)
    else:
        memories = []
        for nid in ranked_ids:
            m = store.get(nid)
            if m:
                memories.append(m)

    by_id = {m.id: m for m in memories}
    ordered = [by_id[nid] for nid in ranked_ids if nid in by_id]
    return [m for m in ordered if m.status == MemoryStatus.ACTIVE]
