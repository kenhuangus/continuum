"""Heuristic episodic → semantic consolidation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from continuum_memory.schemas import Memory, MemoryStatus, MemoryType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def consolidate_workspace(
    store,
    workspace_id: str,
    max_groups: int = 20,
    client=None,
) -> list[Memory]:
    """Group ACTIVE episodics by primary entity; distill groups with ≥2 into SEMANTIC.

    Does not delete source episodics; tags them with ``consolidated``.
    ``client`` is reserved for future LLM summarization (unused in heuristic path).
    """
    _ = client  # heuristic only for P0
    try:
        active = store.list_by_workspace(workspace_id, MemoryStatus.ACTIVE)
    except TypeError:
        active = store.list_by_workspace(workspace_id, MemoryStatus.ACTIVE)

    episodics = [m for m in active if m.type == MemoryType.EPISODIC]
    groups: dict[str, list[Memory]] = {}
    for mem in episodics:
        key = mem.entities[0] if mem.entities else "workspace"
        groups.setdefault(key, []).append(mem)

    written: list[Memory] = []
    now = _utcnow()

    for entity, members in groups.items():
        if len(written) >= max_groups:
            break
        if len(members) < 2:
            continue

        contents = [m.content for m in members]
        summary = ("Distilled: " + "; ".join(contents[:5]))[:500]
        org_id = members[0].org_id
        entities = [] if entity == "workspace" else [entity]

        distilled = Memory(
            id=str(uuid.uuid4()),
            org_id=org_id,
            workspace_id=workspace_id,
            type=MemoryType.SEMANTIC,
            content=summary,
            entities=entities,
            confidence=0.85,
            utility=1.0,
            status=MemoryStatus.ACTIVE,
            created_at=now,
            last_accessed_at=now,
            source={"kind": "consolidation"},
            policy_tags=["distilled"],
        )
        stored = store.remember(distilled)
        written.append(stored)

        for src in members:
            tags = list(src.policy_tags or [])
            if "consolidated" not in tags:
                tags.append("consolidated")
            if hasattr(store, "update_policy_tags"):
                store.update_policy_tags(src.id, tags)

    return written
