from __future__ import annotations

import re
from typing import Any

from continuum_memory.schemas import Memory, MemoryStatus, MemoryType

_TOPIC_PATTERNS: list[tuple[str, str]] = [
    ("discount", r"\d+\s*%|\bdiscount\b"),
    ("vip", r"\bvip\b"),
    ("email", r"\bemail\b|\bcontact\b"),
    ("sla", r"\bsla\b|\buptime\b"),
    ("price", r"\bprice\b|\bpricing\b|\bcost\b"),
    ("owner", r"\bowner\b|\baccount\s+manager\b"),
    ("preference", r"\bprefer"),
]


def extract_slots(content: str, entities: list[str] | None = None) -> dict[str, Any]:
    """Domain-agnostic slot extraction for conflict detection."""
    slots: dict[str, Any] = {}
    text = content or ""

    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:discount)?", text, re.IGNORECASE)
    if m and re.search(r"discount|off|approved", text, re.IGNORECASE):
        slots["discount_pct"] = float(m.group(1))

    if re.search(r"\bvip\b", text, re.IGNORECASE):
        if re.search(r"\bnot\s+(?:a\s+)?vip\b|\bno\s+longer\s+vip\b", text, re.IGNORECASE):
            slots["vip"] = False
        else:
            slots["vip"] = True

    if re.search(r"prefers?\s+email|email\s+(?:communication|contact|preferred)", text, re.IGNORECASE):
        slots["contact_channel"] = "email"
    elif re.search(r"prefers?\s+phone|phone\s+(?:communication|contact|preferred)", text, re.IGNORECASE):
        slots["contact_channel"] = "phone"
    elif re.search(r"prefers?\s+slack|slack\s+(?:communication|contact)", text, re.IGNORECASE):
        slots["contact_channel"] = "slack"

    sla_pct = re.search(
        r"(?i)(?:uptime|availability|sla).{0,40}?(\d+(?:\.\d+)?)\s*%",
        text,
    )
    if sla_pct:
        slots["sla_pct"] = float(sla_pct.group(1))

    sla_hours = re.search(
        r"(?i)(?:response|sla|resolve|resolution).{0,40}?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b",
        text,
    )
    if sla_hours:
        slots["sla_hours"] = float(sla_hours.group(1))

    owner = re.search(
        r"(?i)(?:owner|account\s+manager|am)\s*(?:is|:)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        text,
    )
    if owner:
        slots["owner"] = owner.group(1)

    ents = entities or []
    if ents:
        slots["entity"] = ents[0]

    return slots


def _entity_keys(memory: Memory) -> set[str]:
    keys = {e.lower() for e in memory.entities}
    ent = (memory.slots or {}).get("entity")
    if ent:
        keys.add(str(ent).lower())
    return keys


def _topics(content: str) -> set[str]:
    return {
        name
        for name, pattern in _TOPIC_PATTERNS
        if re.search(pattern, content, re.IGNORECASE)
    }


def _slot_conflict(a: Memory, b: Memory) -> bool:
    """Same entity + same slot key with different values → conflict."""
    slots_a = a.slots or {}
    slots_b = b.slots or {}
    if not slots_a or not slots_b:
        return False
    keys_a = _entity_keys(a)
    keys_b = _entity_keys(b)
    if keys_a and keys_b and not keys_a.intersection(keys_b):
        return False
    skip = {"entity"}
    shared = (set(slots_a) & set(slots_b)) - skip
    for key in shared:
        if slots_a[key] != slots_b[key]:
            return True
    return False


def _substantive_slots(memory: Memory) -> dict[str, Any]:
    return {k: v for k, v in (memory.slots or {}).items() if k != "entity"}


def _conflicts(a: Memory, b: Memory) -> bool:
    """Slot conflict preferred; heuristic topic+entity fallback."""
    if a.type != b.type:
        return False
    if a.type not in (MemoryType.SEMANTIC, MemoryType.DECISION, MemoryType.PREFERENCE):
        return False
    if a.content.strip().lower() == b.content.strip().lower():
        return False

    if _slot_conflict(a, b):
        return True

    # Complementary structured facts (e.g. sla_pct vs sla_hours) must not
    # collide via coarse topic tags like "sla".
    slots_a = _substantive_slots(a)
    slots_b = _substantive_slots(b)
    if slots_a and slots_b:
        shared = set(slots_a) & set(slots_b)
        if not shared:
            return False
        if all(slots_a[k] == slots_b[k] for k in shared):
            return False

    keys_a = _entity_keys(a)
    keys_b = _entity_keys(b)
    if not keys_a.intersection(keys_b):
        return False
    topics_a = _topics(a.content)
    topics_b = _topics(b.content)
    if topics_a and topics_b:
        return bool(topics_a.intersection(topics_b))
    # No topics and no slot conflict: do not treat entity overlap alone as conflict
    # when either side already has structured slots.
    if slots_a or slots_b:
        return False
    return True


def _obsolescence_marker(memory: Memory) -> tuple[str, Any] | None:
    """If memory is an obsolescence marker (see extractor.py), return (slot, value)."""
    slots = memory.slots or {}
    slot_key = slots.get("obsolete_slot")
    if slot_key is None or "obsolete_value" not in slots:
        return None
    return str(slot_key), slots["obsolete_value"]


def apply_supersession(store, new_memories: list[Memory]) -> list[tuple[str, str]]:
    """Mark conflicting active memories as superseded. Returns (old_id, new_id) pairs."""
    pairs: list[tuple[str, str]] = []
    for new_mem in new_memories:
        marker = _obsolescence_marker(new_mem)
        if marker is not None:
            # Obsolescence marker: retire any ACTIVE memory that still carries the
            # stale slot value, but the marker itself never becomes a winning fact
            # for that slot (see extractor.has_obsolescence_cue).
            slot_key, stale_value = marker
            new_keys = _entity_keys(new_mem)
            existing = store.list_by_workspace(new_mem.workspace_id, MemoryStatus.ACTIVE)
            for old in existing:
                if old.id == new_mem.id:
                    continue
                if not old.slots:
                    old.slots = extract_slots(old.content, old.entities)
                if old.slots.get(slot_key) != stale_value:
                    continue
                old_keys = _entity_keys(old)
                if new_keys and old_keys and not new_keys.intersection(old_keys):
                    continue
                store.mark_superseded(old.id, new_mem.id)
                pairs.append((old.id, new_mem.id))
            continue
        if new_mem.type not in (MemoryType.SEMANTIC, MemoryType.DECISION, MemoryType.PREFERENCE):
            continue
        # Ensure slots populated
        if not new_mem.slots:
            new_mem.slots = extract_slots(new_mem.content, new_mem.entities)
            try:
                store.upsert(new_mem)
            except Exception:
                pass
        existing = store.list_by_workspace(new_mem.workspace_id, MemoryStatus.ACTIVE)
        for old in existing:
            if old.id == new_mem.id:
                continue
            if not old.slots:
                old.slots = extract_slots(old.content, old.entities)
            if _conflicts(old, new_mem):
                store.mark_superseded(old.id, new_mem.id)
                pairs.append((old.id, new_mem.id))
    return pairs
