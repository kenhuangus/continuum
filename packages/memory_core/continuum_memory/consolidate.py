"""Heuristic episodic → semantic consolidation (reflection-style stub)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from continuum_memory.schemas import Memory, MemoryStatus, MemoryType
from continuum_memory.scoring import importance_score

logger = logging.getLogger("continuum.consolidate")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _heuristic_summary(contents: list[str]) -> str:
    return ("Distilled: " + "; ".join(contents[:5]))[:500]


def _llm_summary(client: Any, entity: str, contents: list[str]) -> str | None:
    if client is None:
        return None
    system = (
        "You consolidate episodic agent memories into one durable semantic fact. "
        "Return JSON only: {\"summary\": \"...\"} — concise, third-person, no questions."
    )
    user = (
        f"Entity: {entity}\n"
        f"Episodes:\n" + "\n".join(f"- {c}" for c in contents[:5])
    )
    try:
        result = client.chat_json(system, user)
    except Exception:
        logger.debug("consolidate LLM summary failed", exc_info=True)
        return None
    summary: Any = None
    if isinstance(result, dict):
        summary = result.get("summary") or result.get("content")
    elif isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            summary = first.get("summary") or first.get("content")
        elif isinstance(first, str):
            summary = first
    elif isinstance(result, str):
        summary = result
    if not summary:
        return None
    text = str(summary).strip()
    if not text:
        return None
    if not text.lower().startswith("distilled"):
        text = f"Distilled: {text}"
    return text[:500]


def consolidate_workspace(
    store,
    workspace_id: str,
    max_groups: int = 20,
    client=None,
) -> list[Memory]:
    """Group ACTIVE episodics by primary entity; distill groups with ≥2 into SEMANTIC.

    Does not delete source episodics; tags them with ``consolidated``.
    When ``client`` is present, uses LLM summarization (reflection-style stub);
    otherwise heuristic join. Not an async Letta sleep-time worker queue.
    """
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

        ranked = sorted(members, key=importance_score, reverse=True)
        contents = [m.content for m in ranked]
        used_llm = False
        summary = _llm_summary(client, entity, contents) if client is not None else None
        if summary:
            used_llm = True
        else:
            summary = _heuristic_summary(contents)

        org_id = members[0].org_id
        entities = [] if entity == "workspace" else [entity]
        tags = ["distilled"]
        if used_llm:
            tags.append("reflection")

        distilled = Memory(
            id=str(uuid.uuid4()),
            org_id=org_id,
            workspace_id=workspace_id,
            type=MemoryType.SEMANTIC,
            content=summary,
            entities=entities,
            confidence=0.85,
            utility=1.0,
            importance=max((importance_score(m) for m in ranked), default=0.7),
            status=MemoryStatus.ACTIVE,
            created_at=now,
            last_accessed_at=now,
            source={
                "kind": "consolidation",
                "path": "llm" if used_llm else "heuristic",
            },
            policy_tags=tags,
        )
        stored = store.remember(distilled)
        written.append(stored)

        for src in members:
            tags_src = list(src.policy_tags or [])
            if "consolidated" not in tags_src:
                tags_src.append("consolidated")
            if hasattr(store, "update_policy_tags"):
                store.update_policy_tags(src.id, tags_src)

    return written
