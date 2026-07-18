from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from continuum_memory.schemas import ForgetAuditEvent, Memory, MemoryStatus, MemoryType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dt_to_str(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _str_to_dt(s: str | datetime | None) -> datetime | None:
    if s is None:
        return None
    if isinstance(s, datetime):
        return s
    return datetime.fromisoformat(s)


def _normalize_content(text: str) -> str:
    return " ".join(text.lower().split())


def _word_tokens(text: str) -> set[str]:
    return set(_normalize_content(text).split()) - {""}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


_NEAR_DUP_JACCARD = 0.9


def _parse_supersedes(raw: Any) -> list[str]:
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    s = str(raw).strip()
    if not s:
        return []
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x) for x in parsed]
        except json.JSONDecodeError:
            pass
    return [s]


def _serialize_supersedes(ids: list[str] | None) -> str:
    return json.dumps(list(ids or []))


def row_to_memory(row: Any) -> Memory:
    """Convert any mapping-like DB row (sqlite3.Row or SQLAlchemy RowMapping) to a Memory.

    Shared by `MemoryStore` (SQLite) and `PostgresMemoryStore` (SQLAlchemy) so both
    backends stay in lockstep on (de)serialization of JSON-ish columns.
    """
    keys = row.keys()
    slots_raw = row["slots"] if "slots" in keys else "{}"
    importance = row["importance"] if "importance" in keys else None
    entities_raw = row["entities"]
    entities = json.loads(entities_raw) if isinstance(entities_raw, str) else list(entities_raw or [])
    source_raw = row["source"]
    source = json.loads(source_raw) if isinstance(source_raw, str) else dict(source_raw or {})
    policy_tags_raw = row["policy_tags"]
    policy_tags = (
        json.loads(policy_tags_raw) if isinstance(policy_tags_raw, str) else list(policy_tags_raw or [])
    )
    slots = json.loads(slots_raw) if isinstance(slots_raw, str) else dict(slots_raw or {})
    return Memory(
        id=row["id"],
        org_id=row["org_id"],
        workspace_id=row["workspace_id"],
        type=MemoryType(row["type"]),
        content=row["content"],
        entities=entities,
        confidence=row["confidence"],
        utility=row["utility"],
        importance=importance,
        status=MemoryStatus(row["status"]),
        effective_from=_str_to_dt(row["effective_from"]),
        effective_to=_str_to_dt(row["effective_to"]),
        created_at=_str_to_dt(row["created_at"]) or _utcnow(),
        last_accessed_at=_str_to_dt(row["last_accessed_at"]) or _utcnow(),
        source=source,
        superseded_by=row["superseded_by"],
        supersedes=_parse_supersedes(row["supersedes"]),
        slots=slots,
        policy_tags=policy_tags,
        version=row["version"],
    )


class MemoryStore:
    """SQLite-backed memory store implementing MemoryStoreProtocol."""

    def __init__(self, db_path: str | Path = "data/continuum.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    entities TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    utility REAL NOT NULL DEFAULT 1.0,
                    status TEXT NOT NULL DEFAULT 'active',
                    effective_from TEXT,
                    effective_to TEXT,
                    created_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '{}',
                    superseded_by TEXT,
                    supersedes TEXT NOT NULL DEFAULT '[]',
                    slots TEXT NOT NULL DEFAULT '{}',
                    policy_tags TEXT NOT NULL DEFAULT '[]',
                    version INTEGER NOT NULL DEFAULT 1,
                    importance REAL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_workspace
                    ON memories(workspace_id, status);
                CREATE INDEX IF NOT EXISTS idx_memories_entities
                    ON memories(workspace_id);

                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '{}'
                );
                """
            )
            # Migrate older DBs missing slots / with nullable supersedes
            cols = {
                r[1]
                for r in conn.execute("PRAGMA table_info(memories)").fetchall()
            }
            if "slots" not in cols:
                conn.execute(
                    "ALTER TABLE memories ADD COLUMN slots TEXT NOT NULL DEFAULT '{}'"
                )
            if "importance" not in cols:
                conn.execute(
                    "ALTER TABLE memories ADD COLUMN importance REAL"
                )

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_edges (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    src_id TEXT NOT NULL,
                    dst_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_edges_src
                    ON memory_edges(workspace_id, src_id);
                CREATE INDEX IF NOT EXISTS idx_edges_dst
                    ON memory_edges(workspace_id, dst_id);

                CREATE TABLE IF NOT EXISTS embed_cache (
                    memory_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    dim INT NOT NULL,
                    vector TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        return row_to_memory(row)

    def _effective_at(self, mem: Memory, as_of: datetime | None) -> bool:
        if as_of is None:
            return True
        if mem.effective_from and mem.effective_from > as_of:
            return False
        if mem.effective_to and mem.effective_to < as_of:
            return False
        return True

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
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, org_id, workspace_id, type, content, entities,
                    confidence, utility, status, effective_from, effective_to,
                    created_at, last_accessed_at, source, superseded_by,
                    supersedes, slots, policy_tags, version, importance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.org_id,
                    memory.workspace_id,
                    memory.type.value,
                    memory.content,
                    json.dumps(memory.entities),
                    memory.confidence,
                    memory.utility,
                    memory.status.value,
                    _dt_to_str(memory.effective_from),
                    _dt_to_str(memory.effective_to),
                    _dt_to_str(memory.created_at),
                    _dt_to_str(memory.last_accessed_at),
                    json.dumps(memory.source),
                    memory.superseded_by,
                    _serialize_supersedes(memory.supersedes),
                    json.dumps(memory.slots or {}),
                    json.dumps(memory.policy_tags),
                    memory.version,
                    memory.importance,
                ),
            )
        return memory

    def upsert(self, memory: Memory) -> Memory:
        return self.remember(memory)

    def get(self, memory_id: str, *, org_id: str | None = None) -> Memory | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
        if not row:
            return None
        mem = self._row_to_memory(row)
        if org_id is not None and mem.org_id != org_id:
            return None
        return mem

    def list_by_workspace(
        self,
        workspace_id: str,
        status: MemoryStatus | None = None,
        *,
        as_of: datetime | None = None,
        org_id: str | None = None,
    ) -> list[Memory]:
        with self._conn() as conn:
            clauses = ["workspace_id = ?"]
            params: list[Any] = [workspace_id]
            if status:
                clauses.append("status = ?")
                params.append(status.value)
            if org_id is not None:
                clauses.append("org_id = ?")
                params.append(org_id)
            where = " AND ".join(clauses)
            rows = conn.execute(
                f"SELECT * FROM memories WHERE {where} ORDER BY created_at DESC",
                params,
            ).fetchall()
        memories = [self._row_to_memory(r) for r in rows]
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
        as_of: datetime | None = None,
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
                "UPDATE memories SET status = ?, superseded_by = ? WHERE id = ?",
                (MemoryStatus.SUPERSEDED.value, new_id, old_id),
            )
            row = conn.execute(
                "SELECT supersedes FROM memories WHERE id = ?", (new_id,)
            ).fetchone()
            existing = _parse_supersedes(row["supersedes"] if row else None)
            if old_id not in existing:
                existing.append(old_id)
            conn.execute(
                "UPDATE memories SET supersedes = ? WHERE id = ?",
                (_serialize_supersedes(existing), new_id),
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
                "UPDATE memories SET status = ? WHERE id = ?",
                (MemoryStatus.FORGOTTEN.value, memory_id),
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
                """
                INSERT INTO audit_log (id, memory_id, workspace_id, reason, timestamp, details)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.memory_id,
                    event.workspace_id,
                    event.reason,
                    _dt_to_str(event.timestamp),
                    json.dumps(event.details),
                ),
            )

    def get_audit_log(self, workspace_id: str) -> list[ForgetAuditEvent]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE workspace_id = ? ORDER BY timestamp DESC",
                (workspace_id,),
            ).fetchall()
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
        now = _utcnow()
        with self._conn() as conn:
            conn.execute(
                "UPDATE memories SET last_accessed_at = ? WHERE id = ?",
                (_dt_to_str(now), memory_id),
            )

    def update_confidence(self, memory_id: str, confidence: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE memories SET confidence = ? WHERE id = ?",
                (confidence, memory_id),
            )

    def update_utility(self, memory_id: str, utility: float) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE memories SET utility = ? WHERE id = ?",
                (utility, memory_id),
            )

    def update_policy_tags(self, memory_id: str, tags: list[str]) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE memories SET policy_tags = ? WHERE id = ?",
                (json.dumps(list(tags or [])), memory_id),
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
                """
                INSERT INTO memory_edges (id, workspace_id, src_id, dst_id, relation, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edge_id,
                    workspace_id,
                    src_id,
                    dst_id,
                    relation,
                    _dt_to_str(_utcnow()),
                ),
            )
        return edge_id

    def edges_for(self, workspace_id: str, memory_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, workspace_id, src_id, dst_id, relation, created_at
                FROM memory_edges
                WHERE workspace_id = ? AND (src_id = ? OR dst_id = ?)
                """,
                (workspace_id, memory_id, memory_id),
            ).fetchall()
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
        placeholders = ",".join("?" for _ in ids)
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM memories WHERE id IN ({placeholders})",
                list(ids),
            ).fetchall()
        by_id = {r["id"]: self._row_to_memory(r) for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def get_embed_cache(self, memory_id: str) -> tuple[str, list[float]] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT content_hash, vector FROM embed_cache WHERE memory_id = ?",
                (memory_id,),
            ).fetchone()
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
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO embed_cache (memory_id, content_hash, dim, vector, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    dim = excluded.dim,
                    vector = excluded.vector,
                    updated_at = excluded.updated_at
                """,
                (
                    memory_id,
                    content_hash,
                    len(vector),
                    json.dumps(vector),
                    _dt_to_str(_utcnow()),
                ),
            )
