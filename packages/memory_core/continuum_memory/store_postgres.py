"""Optional Postgres store — requires sqlalchemy. Falls back via create_store()."""

from __future__ import annotations

from continuum_memory.store import MemoryStore


class PostgresMemoryStore(MemoryStore):
    """Minimal Postgres-backed store.

    For hackathon scope we keep the same MemoryStoreProtocol surface.
    Full SQLAlchemy ORM is optional; this raises clearly if SQLAlchemy is missing.
    """

    def __init__(self, database_url: str) -> None:
        try:
            from sqlalchemy import create_engine, text
        except ImportError as exc:
            raise NotImplementedError(
                "sqlalchemy is required for Postgres. pip install sqlalchemy"
            ) from exc

        self.database_url = database_url
        self._engine = create_engine(database_url)
        # Ensure connectivity; schema bootstrap is intentionally minimal.
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        raise NotImplementedError(
            "PostgresMemoryStore schema/ops not fully shipped yet. "
            "Use SQLite (CONTINUUM_DB_PATH) for the working path; "
            "MemoryStoreProtocol + create_store() are ready for a full impl."
        )
