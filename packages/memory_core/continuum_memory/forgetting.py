from __future__ import annotations

from datetime import datetime, timezone

from continuum_memory.schemas import ForgetAuditEvent, MemoryStatus
from continuum_memory.store import MemoryStore


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class ForgettingEngine:
    """Expire, decay, and audit forgotten memories."""

    def __init__(
        self,
        store: MemoryStore,
        *,
        confidence_threshold: float = 0.15,
        decay_factor: float = 0.05,
    ) -> None:
        self.store = store
        self.confidence_threshold = confidence_threshold
        self.decay_factor = decay_factor

    def run_pass(self, workspace_id: str) -> list[ForgetAuditEvent]:
        events: list[ForgetAuditEvent] = []
        now = datetime.now(timezone.utc)
        active = self.store.list_by_workspace(workspace_id, MemoryStatus.ACTIVE)

        for mem in active:
            effective_to = _ensure_aware(mem.effective_to)
            if effective_to and effective_to < now:
                event = self.store.forget(mem.id, reason="expired_effective_to")
                if event:
                    events.append(event)
                continue

            last_accessed = _ensure_aware(mem.last_accessed_at) or now
            days_unused = (now - last_accessed).days
            if days_unused > 30:
                new_conf = max(0.0, mem.confidence - self.decay_factor * (days_unused / 30))
                self.store.update_confidence(mem.id, new_conf)
                if new_conf < self.confidence_threshold:
                    event = self.store.forget(mem.id, reason="confidence_decay")
                    if event:
                        events.append(event)

        return events
