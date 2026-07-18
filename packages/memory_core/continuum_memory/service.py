from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from continuum_memory.extractor import extract_memories
from continuum_memory.forgetting import ForgettingEngine
from continuum_memory.packer import pack_context
from continuum_memory.retrieve import retrieve_candidates
from continuum_memory.schemas import Memory, MemoryStatus, PackedContext
from continuum_memory.store_base import create_store
from continuum_memory.supersession import apply_supersession, extract_slots
from continuum_memory.explain import (
    explain_pack,
    explain_pack_structured,
    explain_memory_inclusion,
    explain_memory_structured,
)
from continuum_memory.graph import link_on_remember
from continuum_memory.consolidate import consolidate_workspace
from continuum_memory.policy import apply_policy_on_write, filter_by_policy
from continuum_memory.scoring import maybe_assign_llm_importance

logger = logging.getLogger("continuum.pack")


class MemoryService:
    """Public facade for Continuum memory operations."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        client: Any | None = None,
        store: Any | None = None,
    ) -> None:
        if store is not None:
            self.store = store
        else:
            path = db_path or os.environ.get("CONTINUUM_DB_PATH", "data/continuum.db")
            self.store = create_store(str(path))
        self.client = client
        self.forgetting = ForgettingEngine(self.store)

    def remember(self, memory: Memory) -> Memory:
        if not memory.slots:
            memory.slots = extract_slots(memory.content, memory.entities)
        maybe_assign_llm_importance(memory, self.client)
        apply_policy_on_write(memory)
        stored = self.store.remember(memory)
        apply_supersession(self.store, [stored])
        fresh = self.store.get(stored.id) or stored
        try:
            link_on_remember(self.store, fresh)
        except Exception:
            logger.debug("link_on_remember failed for %s", fresh.id, exc_info=True)
        return fresh

    def ingest_turn(
        self,
        workspace_id: str,
        session_id: str,
        user_text: str,
        assistant_text: str | None = None,
        org_id: str = "org_demo",
    ) -> list[Memory]:
        extracted = extract_memories(
            user_text,
            assistant_text,
            org_id=org_id,
            workspace_id=workspace_id,
            session_id=session_id,
            client=self.client,
        )
        written: list[Memory] = []
        turn_injection = False
        try:
            from continuum_memory.injection import detect_injection

            turn_injection = bool(detect_injection(user_text or ""))
        except Exception:
            turn_injection = False
        for mem in extracted:
            mem.org_id = org_id
            mem.workspace_id = workspace_id
            mem.source.setdefault("session_id", session_id)
            if turn_injection:
                tags = list(mem.policy_tags or [])
                for t in ("injection_risk", "untrusted"):
                    if t not in tags:
                        tags.append(t)
                mem.policy_tags = tags
                mem.confidence = min(float(mem.confidence), 0.35)
                mem.source = {**(mem.source or {}), "turn_injection": True}
            if not mem.slots:
                mem.slots = extract_slots(mem.content, mem.entities)
            maybe_assign_llm_importance(mem, self.client)
            apply_policy_on_write(mem)
            stored = self.store.remember(mem)
            if stored.id == mem.id:
                written.append(stored)
        apply_supersession(self.store, written)
        for stored in written:
            # Refresh so supersedes edges reflect post-supersession state
            fresh = self.store.get(stored.id) or stored
            try:
                link_on_remember(self.store, fresh)
            except Exception:
                logger.debug(
                    "link_on_remember failed for %s", fresh.id, exc_info=True
                )
        return written

    def search(
        self,
        workspace_id: str,
        query: str = "",
        entities: list[str] | None = None,
        *,
        org_id: str | None = None,
    ) -> list[Memory]:
        try:
            return self.store.search(workspace_id, query, entities, org_id=org_id)
        except TypeError:
            return self.store.search(workspace_id, query, entities)

    def list_memories(
        self,
        workspace_id: str,
        status: MemoryStatus | None = None,
        *,
        as_of: datetime | None = None,
        org_id: str | None = None,
    ) -> list[Memory]:
        # Point-in-time: when as_of is set and caller asks for ACTIVE (or None),
        # include superseded facts still effective at that instant.
        list_status = status
        if as_of is not None and status in (None, MemoryStatus.ACTIVE):
            list_status = None
        try:
            items = self.store.list_by_workspace(
                workspace_id, list_status, as_of=as_of, org_id=org_id
            )
        except TypeError:
            try:
                items = self.store.list_by_workspace(
                    workspace_id, list_status, as_of=as_of
                )
            except TypeError:
                items = self.store.list_by_workspace(workspace_id, list_status)
        if as_of is not None:
            items = [m for m in items if m.status != MemoryStatus.FORGOTTEN]
            if status == MemoryStatus.ACTIVE:
                # Historically "true" at as_of — ACTIVE or SUPERSEDED with window
                items = [
                    m
                    for m in items
                    if m.status in (MemoryStatus.ACTIVE, MemoryStatus.SUPERSEDED)
                ]
        return items

    def forget(
        self,
        memory_id: str,
        reason: str = "manual",
        workspace_id: str | None = None,
        *,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Forget with optional workspace/org AuthZ. Returns status dict."""
        mem = self.store.get(memory_id)
        if not mem:
            return {"forgotten": False, "error": "not_found"}
        if workspace_id is not None and mem.workspace_id != workspace_id:
            return {"forgotten": False, "error": "not_found"}
        if org_id is not None and mem.org_id != org_id:
            return {"forgotten": False, "error": "not_found"}

        hitl_required = False
        if os.environ.get("CONTINUUM_HITL_FORGET", "").lower() in ("1", "true", "yes"):
            if mem.utility >= 0.9 and mem.confidence >= 0.85:
                hitl_required = True
                return {
                    "forgotten": False,
                    "hitl_required": True,
                    "id": memory_id,
                    "reason": "high_utility_confirm_required",
                }

        event = self.store.forget(memory_id, reason, workspace_id=workspace_id)
        if event is None:
            return {"forgotten": False, "error": "not_found"}
        return {
            "forgotten": True,
            "id": memory_id,
            "hitl_required": hitl_required,
            "audit_id": event.id,
        }

    def pack(
        self,
        workspace_id: str,
        query: str,
        budget_tokens: int = 1500,
        algorithm: str = "type_quota",
        *,
        as_of: datetime | None = None,
        retrieve_top_k: int = 50,
        org_id: str | None = None,
    ) -> PackedContext:
        # Hybrid retrieve-then-pack — never score entire workspace as only path
        candidates = retrieve_candidates(
            self.store,
            workspace_id,
            query,
            top_k=retrieve_top_k,
            as_of=as_of,
            org_id=org_id,
        )
        candidates = filter_by_policy(candidates)
        packed = pack_context(candidates, query, budget_tokens, algorithm)
        packed.candidate_count = len(candidates)

        for mem in packed.memories:
            self.store.update_last_accessed(mem.id)
            # Utility bump on successful pack use
            try:
                new_u = min(2.0, float(mem.utility) + 0.02)
                self.store.update_utility(mem.id, new_u)
            except Exception:
                pass

        packed.explanations = explain_pack(
            candidates, packed, query, budget_tokens, algorithm
        )
        packed.explanation_details = explain_pack_structured(
            candidates, packed, query, budget_tokens, algorithm
        )

        logger.info(
            "pack workspace=%s query_len=%d candidates=%d packed=%d tokens=%d/%d algorithm=%s",
            workspace_id,
            len(query or ""),
            len(candidates),
            len(packed.memories),
            packed.token_estimate,
            budget_tokens,
            algorithm,
        )
        return packed

    def run_forgetting_pass(
        self,
        workspace_id: str,
        *,
        org_id: str | None = None,
    ) -> list[dict]:
        try:
            events = self.forgetting.run_pass(workspace_id, org_id=org_id)
        except TypeError:
            events = self.forgetting.run_pass(workspace_id)
        return [e.model_dump(mode="json") for e in events]

    def explain(
        self,
        memory_id: str,
        workspace_id: str,
        query: str,
        budget_tokens: int = 1500,
        *,
        org_id: str | None = None,
        structured: bool = False,
    ) -> str | dict:
        packed = self.pack(workspace_id, query, budget_tokens, org_id=org_id)
        if structured:
            return explain_memory_structured(memory_id, packed, query=query)
        return explain_memory_inclusion(memory_id, packed)

    def get(
        self,
        memory_id: str,
        workspace_id: str | None = None,
        *,
        org_id: str | None = None,
    ) -> Memory | None:
        mem = self.store.get(memory_id)
        if mem is None:
            return None
        if workspace_id is not None and mem.workspace_id != workspace_id:
            return None
        if org_id is not None and mem.org_id != org_id:
            return None
        return mem

    def consolidate(
        self,
        workspace_id: str,
        max_groups: int = 20,
        *,
        org_id: str | None = None,
    ) -> list[Memory]:
        written = consolidate_workspace(
            self.store, workspace_id, max_groups=max_groups, client=self.client
        )
        if org_id is not None:
            written = [m for m in written if m.org_id == org_id]
        for mem in written:
            try:
                link_on_remember(self.store, mem)
            except Exception:
                logger.debug("link_on_remember failed for %s", mem.id, exc_info=True)
        return written

    def record_outcome(
        self,
        workspace_id: str,
        memory_ids: list[str],
        *,
        success: bool,
        note: str | None = None,
        org_id: str | None = None,
        delta_success: float = 0.15,
        delta_failure: float = 0.2,
    ) -> dict[str, Any]:
        """Labeled utility writeback from agent/user outcomes.

        Honest claim: explicit reinforcement stub — not offline RL / causal credit.
        """
        from continuum_memory.schemas import MemoryType
        import uuid
        from datetime import datetime, timezone

        updated: list[dict[str, Any]] = []
        for mid in memory_ids or []:
            mem = self.get(mid, workspace_id, org_id=org_id)
            if mem is None:
                continue
            old_u = float(mem.utility)
            if success:
                new_u = min(2.0, old_u + float(delta_success))
            else:
                new_u = max(0.1, old_u - float(delta_failure))
            try:
                self.store.update_utility(mem.id, new_u)
            except Exception:
                continue
            updated.append(
                {
                    "id": mem.id,
                    "utility_before": old_u,
                    "utility_after": new_u,
                    "success": success,
                }
            )

        procedural: Memory | None = None
        if note:
            now = datetime.now(timezone.utc)
            tag = "outcome:ok" if success else "outcome:fail"
            procedural = Memory(
                id=str(uuid.uuid4()),
                org_id=org_id or "org_demo",
                workspace_id=workspace_id,
                type=MemoryType.PROCEDURAL,
                content=f"Outcome {'success' if success else 'failure'} note: {note}",
                entities=[],
                confidence=0.7,
                utility=1.1 if success else 0.8,
                created_at=now,
                last_accessed_at=now,
                source={"source": "outcome_writeback", "success": success},
                policy_tags=[tag, "reflection"],
            )
            procedural = self.remember(procedural)

        return {
            "workspace_id": workspace_id,
            "success": success,
            "updated": updated,
            "procedural_id": procedural.id if procedural else None,
        }

    def consolidate_async(
        self,
        workspace_id: str,
        max_groups: int = 20,
        *,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Enqueue sleep-time consolidate job (in-process thread stub)."""
        from continuum_memory.sleep_worker import enqueue_consolidate

        def _fn() -> list[Memory]:
            return self.consolidate(workspace_id, max_groups=max_groups, org_id=org_id)

        return enqueue_consolidate(
            _fn,
            workspace_id=workspace_id,
            meta={"max_groups": max_groups, "org_id": org_id},
        )

    def workspace_stats(
        self,
        workspace_id: str,
        *,
        org_id: str | None = None,
    ) -> dict[str, Any]:
        """Counts by status/type plus entity + edge tallies for the console."""
        items = self.list_memories(workspace_id, None, org_id=org_id)
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        entities: set[str] = set()
        for m in items:
            st = m.status.value if hasattr(m.status, "value") else str(m.status)
            ty = m.type.value if hasattr(m.type, "value") else str(m.type)
            by_status[st] = by_status.get(st, 0) + 1
            by_type[ty] = by_type.get(ty, 0) + 1
            for e in m.entities or []:
                if e:
                    entities.add(e.lower())
        edge_count = 0
        if hasattr(self.store, "edges_for"):
            seen: set[str] = set()
            for m in items:
                try:
                    for edge in self.store.edges_for(workspace_id, m.id):
                        eid = edge.get("id") if isinstance(edge, dict) else None
                        if eid and eid not in seen:
                            seen.add(eid)
                            edge_count += 1
                except Exception:
                    continue
        return {
            "workspace_id": workspace_id,
            "total": len(items),
            "by_status": by_status,
            "by_type": by_type,
            "entity_count": len(entities),
            "edge_count": edge_count,
        }

    def workspace_graph(
        self,
        workspace_id: str,
        *,
        org_id: str | None = None,
        limit: int = 80,
    ) -> dict[str, Any]:
        """Nodes + edges for the Memory Graph inspector."""
        items = self.list_memories(workspace_id, None, org_id=org_id)[:limit]
        nodes = [
            {
                "id": m.id,
                "label": (m.content or "")[:72],
                "type": m.type.value if hasattr(m.type, "value") else str(m.type),
                "status": m.status.value if hasattr(m.status, "value") else str(m.status),
                "entities": m.entities or [],
                "supersedes": m.supersedes or [],
                "superseded_by": m.superseded_by,
                "policy_tags": m.policy_tags or [],
            }
            for m in items
        ]
        id_set = {n["id"] for n in nodes}
        edges: list[dict[str, Any]] = []
        seen_e: set[str] = set()
        if hasattr(self.store, "edges_for"):
            for m in items:
                try:
                    for edge in self.store.edges_for(workspace_id, m.id):
                        if not isinstance(edge, dict):
                            continue
                        eid = edge.get("id") or f"{edge.get('src_id')}-{edge.get('dst_id')}-{edge.get('relation')}"
                        if eid in seen_e:
                            continue
                        src, dst = edge.get("src_id"), edge.get("dst_id")
                        if src in id_set and dst in id_set:
                            seen_e.add(eid)
                            edges.append(
                                {
                                    "id": eid,
                                    "src": src,
                                    "dst": dst,
                                    "relation": edge.get("relation") or "related_to",
                                }
                            )
                except Exception:
                    continue
        # Synthesize supersedes edges from memory fields when store has none.
        for m in items:
            for old in m.supersedes or []:
                if old in id_set:
                    eid = f"supersedes:{m.id}:{old}"
                    if eid not in seen_e:
                        seen_e.add(eid)
                        edges.append(
                            {"id": eid, "src": m.id, "dst": old, "relation": "supersedes"}
                        )
        return {"workspace_id": workspace_id, "nodes": nodes, "edges": edges}
