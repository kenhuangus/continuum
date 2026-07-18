from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from continuum_memory.schemas import ForgetAuditEvent, Memory, MemoryStatus


@runtime_checkable
class MemoryStoreProtocol(Protocol):
    """Store interface used by MemoryService (SQLite today; Postgres optional).

    ``org_id`` kwargs are optional and default to ``None`` (no org filter) for
    backward compatibility with existing single-tenant callers/tests. When a
    caller passes ``org_id``, implementations MUST scope results to that org
    in addition to ``workspace_id`` — tenants may reuse the same
    ``workspace_id`` string, so ``workspace_id`` alone is not a safe isolation
    boundary in multi-tenant deployments.
    """

    def remember(self, memory: Memory) -> Memory: ...

    def upsert(self, memory: Memory) -> Memory: ...

    def get(self, memory_id: str, *, org_id: str | None = None) -> Memory | None: ...

    def list_by_workspace(
        self,
        workspace_id: str,
        status: MemoryStatus | None = None,
        *,
        as_of: datetime | None = None,
        org_id: str | None = None,
    ) -> list[Memory]: ...

    def search(
        self,
        workspace_id: str,
        query: str = "",
        entities: list[str] | None = None,
        status: MemoryStatus = MemoryStatus.ACTIVE,
        *,
        as_of: datetime | None = None,
        org_id: str | None = None,
    ) -> list[Memory]: ...

    def mark_superseded(self, old_id: str, new_id: str) -> None: ...

    def forget(
        self,
        memory_id: str,
        reason: str = "manual",
        *,
        workspace_id: str | None = None,
        org_id: str | None = None,
    ) -> ForgetAuditEvent | None: ...

    def log_forget_event(self, event: ForgetAuditEvent) -> None: ...

    def get_audit_log(self, workspace_id: str) -> list[ForgetAuditEvent]: ...

    def update_last_accessed(self, memory_id: str) -> None: ...

    def update_confidence(self, memory_id: str, confidence: float) -> None: ...

    def update_utility(self, memory_id: str, utility: float) -> None: ...


def create_store(db_path_or_url: str | None = None):
    """Factory: SQLite by default; Postgres when DATABASE_URL / path starts with postgres."""
    import os
    from pathlib import Path

    url = db_path_or_url or os.environ.get("DATABASE_URL") or os.environ.get(
        "CONTINUUM_DB_PATH", "data/continuum.db"
    )
    url_str = str(url)
    if url_str.startswith("postgres://") or url_str.startswith("postgresql://"):
        try:
            from continuum_memory.store_postgres import PostgresMemoryStore

            return PostgresMemoryStore(url_str)
        except Exception as exc:  # pragma: no cover - optional path
            raise NotImplementedError(
                f"Postgres store unavailable ({exc}). Install sqlalchemy or use SQLite."
            ) from exc

    from continuum_memory.store import MemoryStore

    return MemoryStore(Path(url_str) if not isinstance(url, Path) else url)
