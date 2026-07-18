"""Postgres-backed MemoryStore — requires the optional `sqlalchemy` dependency.

Mirrors the SQLite `MemoryStore` schema (memories, audit_log, memory_edges,
embed_cache) and behavior (near-dup skip on `remember`, org/workspace scoping,
JSON-as-text columns) so `create_store()` can swap backends transparently based
on `DATABASE_URL`.

Install: ``pip install sqlalchemy`` plus a Postgres driver, e.g.
``pip install "psycopg[binary]"`` or ``psycopg2-binary``.
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from continuum_memory.schemas import ForgetAuditEvent, Memory, MemoryStatus
from continuum_memory.store import (
    _NEAR_DUP_JACCARD,
    _dt_to_str,
    _jaccard,
    _normalize_content,
    _parse_supersedes,
    _serialize_supersedes,
    _str_to_dt,
    _utcnow,
    _word_tokens,
    row_to_memory,
)

try:
    from sqlalchemy import (
        Column,
        Float,
        Integer,
        MetaData,
        String,
        Table,
        Text,
        create_engine,
        insert,
        select,
        text,
        update,
    )

    _SQLALCHEMY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    _SQLALCHEMY_AVAILABLE = False


def _build_metadata() -> "MetaData":
    metadata = MetaData()

    Table(
        "memories",
        metadata,
        Column("id", String, primary_key=True),
        Column("org_id", String, nullable=False),
        Column("workspace_id", String, nullable=False),
        Column("type", String, nullable=False),
        Column("content", Text, nullable=False),
        Column("entities", Text, nullable=False, default="[]"),
        Column("confidence", Float, nullable=False, default=1.0),
        Column("utility", Float, nullable=False, default=1.0),
        Column("status", String, nullable=False, default="active"),
        Column("effective_from", Text, nullable=True),
        Column("effective_to", Text, nullable=True),
        Column("created_at", Text, nullable=False),
        Column("last_accessed_at", Text, nullable=False),
        Column("source", Text, nullable=False, default="{}"),
        Column("superseded_by", Text, nullable=True),
        Column("supersedes", Text, nullable=False, default="[]"),
        Column("slots", Text, nullable=False, default="{}"),
        Column("policy_tags", Text, nullable=False, default="[]"),
        Column("version", Integer, nullable=False, default=1),
        Column("importance", Float, nullable=True),
    )
    Table(
        "audit_log",
        metadata,
        Column("id", String, primary_key=True),
        Column("memory_id", String, nullable=False),
        Column("workspace_id", String, nullable=False),
        Column("reason", String, nullable=False),
        Column("timestamp", Text, nullable=False),
        Column("details", Text, nullable=False, default="{}"),
    )
    Table(
        "memory_edges",
        metadata,
        Column("id", String, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("src_id", String, nullable=False),
        Column("dst_id", String, nullable=False),
        Column("relation", String, nullable=False),
        Column("created_at", Text, nullable=False),
    )
    Table(
        "embed_cache",
        metadata,
        Column("memory_id", String, primary_key=True),
        Column("content_hash", String, nullable=False),
        Column("dim", Integer, nullable=False),
        Column("vector", Text, nullable=False),
        Column("updated_at", Text, nullable=False),
    )
    return metadata


class PostgresMemoryStore:
    """SQLAlchemy-backed store implementing `MemoryStoreProtocol` for Postgres.

    Same table shapes/semantics as `continuum_memory.store.MemoryStore`
    (JSON-ish columns are stored as TEXT and (de)serialized the same way via
    the shared `row_to_memory` helper), so both backends behave identically
    from `MemoryService`'s point of view.
    """

    def __init__(self, database_url: str) -> None:
        if not _SQLALCHEMY_AVAILABLE:
            raise NotImplementedError(
                "sqlalchemy is required for Postgres. pip install sqlalchemy "
                '"psycopg[binary]"'
            )
        self.database_url = database_url
        self._engine = create_engine(database_url, future=True)
        self._metadata = _build_metadata()
        self._memories = self._metadata.tables["memories"]
        self._audit_log = self._metadata.tables["audit_log"]
        self._memory_edges = self._metadata.tables["memory_edges"]
        self._embed_cache = self._metadata.tables["embed_cache"]
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        self._metadata.create_all(self._engine)

    @contextmanager
    def _conn(self) -> Iterator[Any]:
        with self._engine.begin() as conn:
            yield conn

    def _effective_at(self, mem: Memory, as_of) -> bool:
        if as_of is None:
            return True
        if mem.effective_from and mem.effective_from > as_of:
            return False
        if mem.effective_to and mem.effective_to < as_of:
            return False
        return True

    def _memory_values(self, memory: Memory) -> dict[str, Any]:
        return {
            "id": memory.id,
            "org_id": memory.org_id,
            "workspace_id": memory.workspace_id,
            "type": memory.type.value,
            "content": memory.content,
            "entities": json.dumps(memory.entities),
            "confidence": memory.confidence,
            "utility": memory.utility,
            "status": memory.status.value,
            "effective_from": _dt_to_str(memory.effective_from),
            "effective_to": _dt_to_str(memory.effective_to),
            "created_at": _dt_to_str(memory.created_at),
            "last_accessed_at": _dt_to_str(memory.last_accessed_at),
            "source": json.dumps(memory.source),
            "superseded_by": memory.superseded_by,
            "supersedes": _serialize_supersedes(memory.supersedes),
            "slots": json.dumps(memory.slots or {}),
            "policy_tags": json.dumps(memory.policy_tags),
            "version": memory.version,
            "importance": memory.importance,
        }

    def remember(self, memory: Memory) -> Memory:
        active = self.list_by_workspace(
            memory.workspace_id, MemoryStatus.ACTIVE, org_id=memory.org_id
        )
        norm = _normalize_content(memory.content)
        tokens = _word_tokens(memory.content)
        for existing in active:
            if existing.id == memory.id:
                continue
            existing_norm = _normalize_content(existing.content)
            if existing_norm == norm:
                return existing
            if _jaccard(tokens, _word_tokens(existing.content)) > _NEAR_DUP_JACCARD:
                return existing

        values = self._memory_values(memory)
        with self._conn() as conn:
            result = conn.execute(
                update(self._memories)
                .where(self._memories.c.id == memory.id)
                .values(**values)
            )
            if result.rowcount == 0:
                conn.execute(insert(self._memories).values(**values))
        return memory

    def upsert(self, memory: Memory) -> Memory:
        return self.remember(memory)

    def get(self, memory_id: str, *, org_id: str | None = None) -> Memory | None:
        with self._conn() as conn:
            row = conn.execute(
                select(self._memories).where(self._memories.c.id == memory_id)
            ).mappings().first()
        if not row:
            return None
        mem = row_to_memory(row)
        if org_id is not None and mem.org_id != org_id:
            return None
        return mem

    def list_by_workspace(
        self,
        workspace_id: str,
        status: MemoryStatus | None = None,
        *,
        as_of=None,
        org_id: str | None = None,
    ) -> list[Memory]:
        stmt = select(self._memories).where(
            self._memories.c.workspace_id == workspace_id
        )
        if status:
            stmt = stmt.where(self._memories.c.status == status.value)
        if org_id is not None:
            stmt = stmt.where(self._memories.c.org_id == org_id)
        stmt = stmt.order_by(self._memories.c.created_at.desc())
        with self._conn() as conn:
            rows = conn.execute(stmt).mappings().all()
        memories = [row_to_memory(r) for r in rows]
        if as_of is not None:
            memories = [m for m in memories if self._effective_at(m, as_of)]
        return memories

    def search(
        self,
        workspace_id: str,
        query: str = "",
        entities: list[str] | None = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        *,
        as_of=None,
        org_id: str | None = None,
    ) -> list[Memory]:
        memories = self.list_by_workspace(
            workspace_id, status, as_of=as_of, org_id=org_id
        )
        results: list[Memory] = []
        q_lower = query.lower()
        entity_set = {e.lower() for e in (entities or [])}

        for mem in memories:
            if query:
                haystack = f"{mem.content} {' '.join(mem.entities)}".lower()
                if q_lower not in haystack and not any(
                    term in haystack for term in q_lower.split()
                ):
                    continue
            if entity_set:
                mem_entities = {e.lower() for e in mem.entities}
                if not entity_set.intersection(mem_entities) and not any(
                    e.lower() in mem.content.lower() for e in entities or []
                ):
                    continue
            results.append(mem)
        return results

    def mark_superseded(self, old_id: str, new_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                update(self._memories)
                .where(self._memories.c.id == old_id)
                .values(status=MemoryStatus.SUPERSEDED.value, superseded_by=new_id)
            )
            row = conn.execute(
                select(self._memories.c.supersedes).where(
                    self._memories.c.id == new_id
                )
            ).mappings().first()
            existing = _parse_supersedes(row["supersedes"] if row else None)
            if old_id not in existing:
                existing.append(old_id)
            conn.execute(
                update(self._memories)
                .where(self._memories.c.id == new_id)
                .values(supersedes=_serialize_supersedes(existing))
            )

    def forget(
        self,
        memory_id: str,
        reason: str = "manual",
        *,
        workspace_id: str | None = None,
        org_id: str | None = None,
    ) -> ForgetAuditEvent | None:
        mem = self.get(memory_id)
        if not mem:
            return None
        if workspace_id is not None and mem.workspace_id != workspace_id:
            return None
        if org_id is not None and mem.org_id != org_id:
            return None
        with self._conn() as conn:
            conn.execute(
                update(self._memories)
                .where(self._memories.c.id == memory_id)
                .values(status=MemoryStatus.FORGOTTEN.value)
            )
        event = ForgetAuditEvent(
            id=str(uuid.uuid4()),
            memory_id=memory_id,
            workspace_id=mem.workspace_id,
            reason=reason,
            timestamp=_utcnow(),
            details={"content_preview": mem.content[:120]},
        )
        self.log_forget_event(event)
        return event

    def log_forget_event(self, event: ForgetAuditEvent) -> None:
        with self._conn() as conn:
            conn.execute(
                insert(self._audit_log).values(
                    id=event.id,
                    memory_id=event.memory_id,
                    workspace_id=event.workspace_id,
                    reason=event.reason,
                    timestamp=_dt_to_str(event.timestamp),
                    details=json.dumps(event.details),
                )
            )

    def get_audit_log(self, workspace_id: str) -> list[ForgetAuditEvent]:
        stmt = (
            select(self._audit_log)
            .where(self._audit_log.c.workspace_id == workspace_id)
            .order_by(self._audit_log.c.timestamp.desc())
        )
        with self._conn() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [
            ForgetAuditEvent(
                id=r["id"],
                memory_id=r["memory_id"],
                workspace_id=r["workspace_id"],
                reason=r["reason"],
                timestamp=_str_to_dt(r["timestamp"]) or _utcnow(),
                details=json.loads(r["details"]),
            )
            for r in rows
        ]

    def update_last_accessed(self, memory_id: str) -> None:
        with self._conn() as conn:
            conn.execute(
                update(self._memories)
                .where(self._memories.c.id == memory_id)
                .values(last_accessed_at=_dt_to_str(_utcnow()))
            )

    def update_confidence(self, memory_id: str, confidence: float) -> None:
        with self._conn() as conn:
            conn.execute(
                update(self._memories)
                .where(self._memories.c.id == memory_id)
                .values(confidence=confidence)
            )

    def update_utility(self, memory_id: str, utility: float) -> None:
        with self._conn() as conn:
            conn.execute(
                update(self._memories)
                .where(self._memories.c.id == memory_id)
                .values(utility=utility)
            )

    def update_policy_tags(self, memory_id: str, tags: list[str]) -> None:
        with self._conn() as conn:
            conn.execute(
                update(self._memories)
                .where(self._memories.c.id == memory_id)
                .values(policy_tags=json.dumps(list(tags or [])))
            )

    def add_edge(
        self,
        workspace_id: str,
        src_id: str,
        dst_id: str,
        relation: str,
    ) -> str:
        edge_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                insert(self._memory_edges).values(
                    id=edge_id,
                    workspace_id=workspace_id,
                    src_id=src_id,
                    dst_id=dst_id,
                    relation=relation,
                    created_at=_dt_to_str(_utcnow()),
                )
            )
        return edge_id

    def edges_for(self, workspace_id: str, memory_id: str) -> list[dict[str, Any]]:
        stmt = select(self._memory_edges).where(
            self._memory_edges.c.workspace_id == workspace_id,
            (self._memory_edges.c.src_id == memory_id)
            | (self._memory_edges.c.dst_id == memory_id),
        )
        with self._conn() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [
            {
                "id": r["id"],
                "workspace_id": r["workspace_id"],
                "src_id": r["src_id"],
                "dst_id": r["dst_id"],
                "relation": r["relation"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_many(self, ids: list[str]) -> list[Memory]:
        if not ids:
            return []
        stmt = select(self._memories).where(self._memories.c.id.in_(ids))
        with self._conn() as conn:
            rows = conn.execute(stmt).mappings().all()
        by_id = {r["id"]: row_to_memory(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def get_embed_cache(self, memory_id: str) -> tuple[str, list[float]] | None:
        stmt = select(self._embed_cache.c.content_hash, self._embed_cache.c.vector).where(
            self._embed_cache.c.memory_id == memory_id
        )
        with self._conn() as conn:
            row = conn.execute(stmt).mappings().first()
        if row is None:
            return None
        try:
            vector = json.loads(row["vector"])
            if not isinstance(vector, list):
                return None
            return row["content_hash"], [float(x) for x in vector]
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def put_embed_cache(
        self, memory_id: str, content_hash: str, vector: list[float]
    ) -> None:
        values = {
            "memory_id": memory_id,
            "content_hash": content_hash,
            "dim": len(vector),
            "vector": json.dumps(vector),
            "updated_at": _dt_to_str(_utcnow()),
        }
        with self._conn() as conn:
            result = conn.execute(
                update(self._embed_cache)
                .where(self._embed_cache.c.memory_id == memory_id)
                .values(**values)
            )
            if result.rowcount == 0:
                conn.execute(insert(self._embed_cache).values(**values))
