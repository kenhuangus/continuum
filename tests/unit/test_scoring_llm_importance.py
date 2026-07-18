from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.schemas import Memory, MemoryType
from continuum_memory.scoring import (
    maybe_assign_llm_importance,
    score_importance_with_llm,
)
from continuum_memory.service import MemoryService

pytestmark = pytest.mark.unit


class FakeImportanceClient:
    def __init__(self, value: float = 9.0) -> None:
        self.value = value
        self.calls = 0

    def chat_json(self, system: str, user: str):
        self.calls += 1
        return {"importance": self.value}


def test_score_importance_with_llm_normalizes():
    client = FakeImportanceClient(8)
    scored = score_importance_with_llm("Approved 12% discount for Acme.", client)
    assert scored == pytest.approx(0.8)
    assert client.calls == 1


def test_score_importance_with_llm_handles_failure():
    class Boom:
        def chat_json(self, system: str, user: str):
            raise RuntimeError("nope")

    assert score_importance_with_llm("x", Boom()) is None


def test_maybe_assign_llm_importance_respects_flag(monkeypatch):
    client = FakeImportanceClient(7)
    mem = Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id="ws",
        type=MemoryType.SEMANTIC,
        content="Acme is VIP.",
        created_at=datetime.now(timezone.utc),
        last_accessed_at=datetime.now(timezone.utc),
    )
    monkeypatch.delenv("CONTINUUM_LLM_IMPORTANCE", raising=False)
    maybe_assign_llm_importance(mem, client)
    assert mem.importance is None
    assert client.calls == 0

    monkeypatch.setenv("CONTINUUM_LLM_IMPORTANCE", "1")
    maybe_assign_llm_importance(mem, client)
    assert mem.importance == pytest.approx(0.7)
    assert mem.source.get("importance_source") == "llm"


def test_ingest_assigns_llm_importance(monkeypatch):
    monkeypatch.setenv("CONTINUUM_LLM_IMPORTANCE", "1")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        client = FakeImportanceClient(9)
        svc = MemoryService(db_path=db_path, client=client)
        written = svc.ingest_turn(
            "ws_imp",
            "s1",
            "Approved 15% discount for Globex.",
            "Recorded.",
        )
        assert written
        assert any(m.importance is not None for m in written)
        assert client.calls >= 1
    finally:
        Path(db_path).unlink(missing_ok=True)
        monkeypatch.delenv("CONTINUUM_LLM_IMPORTANCE", raising=False)
