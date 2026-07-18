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


def _str_to_dt(s: str | None) -> datetime | None:
    if s is None:
        return None
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
                    version INTEGER NOT NULL DEFAULT 1
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

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        keys = row.keys()
        slots_raw = row["slots"] if "slots" in keys else "{}"
        return Memory(
            id=row["id"],
            org_id=row["org_id"],
            workspace_id=row["workspace_id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            entities=json.loads(row["entities"]),
            confidence=row["confidence"],
            utility=row["utility"],
            status=MemoryStatus(row["status"]),
            effective_from=_str_to_dt(row["effective_from"]),
            effective_to=_str_to_dt(row["effective_to"]),
            created_at=_str_to_dt(row["created_at"]) or _utcnow(),
            last_accessed_at=_str_to_dt(row["last_accessed_at"]) or _utcnow(),
            source=json.loads(row["source"]),
            superseded_by=row["superseded_by"],
            supersedes=_parse_supersedes(row["supersedes"]),
            slots=json.loads(slots_raw or "{}"),
            policy_tags=json.loads(row["policy_tags"]),
            version=row["version"],
        )

    def _effective_at(self, mem: Memory, as_of: datetime | None) -> bool:
        if as_of is None:
            return True
        if mem.effective_from and mem.effective_from > as_of:
            return False
        if mem.effective_to and mem.effective_to < as_of:
            return False
        return True

    def remember(self, memory: Memory) -> Memory:
        active = self.list_by_workspace(memory.workspace_id, MemoryStatus.ACTIVE)
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
                    supersedes, slots, policy_tags, version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
        return memory

    def upsert(self, memory: Memory) -> Memory:
        return self.remember(memory)

    def get(self, memory_id: str) -> Memory | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
        return self._row_to_memory(row) if row else None

    def list_by_workspace(
        self,
        workspace_id: str,
        status: MemoryStatus | None = None,
        *,
        as_of: datetime | None = None,
    ) -> list[Memory]:
        with self._conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE workspace_id = ? AND status = ? "
                    "ORDER BY created_at DESC",
                    (workspace_id, status.value),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM memories WHERE workspace_id = ? ORDER BY created_at DESC",
                    (workspace_id,),
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
    ) -> list[Memory]:
        memories = self.list_by_workspace(workspace_id, status, as_of=as_of)
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
    ) -> ForgetAuditEvent | None:
        mem = self.get(memory_id)
        if not mem:
            return None
        if workspace_id is not None and mem.workspace_id != workspace_id:
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
