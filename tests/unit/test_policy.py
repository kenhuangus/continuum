from __future__ import annotations

import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from continuum_memory.policy import (
    apply_policy_on_write,
    detect_policy_tags,
    filter_by_policy,
)
from continuum_memory.schemas import Memory, MemoryType
from continuum_memory.service import MemoryService

pytestmark = pytest.mark.unit


def _mem(content: str, **kwargs) -> Memory:
    now = datetime.now(timezone.utc)
    return Memory(
        id=str(uuid.uuid4()),
        org_id="org_demo",
        workspace_id="ws_pol",
        type=MemoryType.SEMANTIC,
        content=content,
        created_at=now,
        last_accessed_at=now,
        **kwargs,
    )


def test_detect_policy_tags_email_phone():
    tags = detect_policy_tags("Contact Jane at jane.doe@example.com or 415-555-0199")
    assert "pii" in tags
    assert "retention:short" in tags
    assert detect_policy_tags("No personal data here") == []


def test_apply_policy_sets_effective_to():
    mem = _mem("SSN on file 123-45-6789")
    apply_policy_on_write(mem)
    assert "pii" in mem.policy_tags
    assert mem.effective_to is not None


def test_filter_by_policy_excludes_pii(monkeypatch):
    a = _mem("safe fact about Acme VIP")
    b = _mem("email bob@acme.test", policy_tags=["pii"])
    monkeypatch.setenv("CONTINUUM_PACK_EXCLUDE_PII", "1")
    filtered = filter_by_policy([a, b])
    assert [m.id for m in filtered] == [a.id]
    monkeypatch.delenv("CONTINUUM_PACK_EXCLUDE_PII", raising=False)
    assert len(filter_by_policy([a, b])) == 2


def test_remember_applies_policy_tags():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        svc = MemoryService(db_path=db_path)
        stored = svc.remember(_mem("Reach out via ops@horizon.example"))
        assert "pii" in stored.policy_tags
        assert stored.effective_to is not None
    finally:
        Path(db_path).unlink(missing_ok=True)
