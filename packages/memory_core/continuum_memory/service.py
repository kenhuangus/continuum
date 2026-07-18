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
from continuum_memory.explain import explain_pack, explain_memory_inclusion

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
        stored = self.store.remember(memory)
        apply_supersession(self.store, [stored])
        return stored

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
        for mem in extracted:
            mem.org_id = org_id
            mem.workspace_id = workspace_id
            mem.source.setdefault("session_id", session_id)
            if not mem.slots:
                mem.slots = extract_slots(mem.content, mem.entities)
            stored = self.store.remember(mem)
            if stored.id == mem.id:
                written.append(stored)
        apply_supersession(self.store, written)
        return written

    def search(
        self,
        workspace_id: str,
        query: str = "",
        entities: list[str] | None = None,
    ) -> list[Memory]:
        return self.store.search(workspace_id, query, entities)

    def list_memories(
        self,
        workspace_id: str,
        status: MemoryStatus | None = None,
        *,
        as_of: datetime | None = None,
    ) -> list[Memory]:
        try:
            return self.store.list_by_workspace(workspace_id, status, as_of=as_of)
        except TypeError:
            return self.store.list_by_workspace(workspace_id, status)

    def forget(
        self,
        memory_id: str,
        reason: str = "manual",
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Forget with optional workspace AuthZ. Returns status dict."""
        mem = self.store.get(memory_id)
        if not mem:
            return {"forgotten": False, "error": "not_found"}
        if workspace_id is not None and mem.workspace_id != workspace_id:
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
    ) -> PackedContext:
        # Hybrid retrieve-then-pack — never score entire workspace as only path
        candidates = retrieve_candidates(
            self.store,
            workspace_id,
            query,
            top_k=retrieve_top_k,
            as_of=as_of,
        )
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

    def run_forgetting_pass(self, workspace_id: str) -> list[dict]:
        events = self.forgetting.run_pass(workspace_id)
        return [e.model_dump(mode="json") for e in events]

    def explain(
        self,
        memory_id: str,
        workspace_id: str,
        query: str,
        budget_tokens: int = 1500,
    ) -> str:
        packed = self.pack(workspace_id, query, budget_tokens)
        return explain_memory_inclusion(memory_id, packed)

    def get(self, memory_id: str, workspace_id: str | None = None) -> Memory | None:
        mem = self.store.get(memory_id)
        if mem is None:
            return None
        if workspace_id is not None and mem.workspace_id != workspace_id:
            return None
        return mem
