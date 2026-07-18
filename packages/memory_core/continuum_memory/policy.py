"""Heuristic policy stubs for PII tagging and short retention.

Honest claim: regex/heuristic stubs for governance demos — not GDPR/DSAR product
compliance, not a full policy engine.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone

from continuum_memory.schemas import Memory

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)"
)
_SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")

DEFAULT_SHORT_RETENTION_DAYS = 7


def detect_policy_tags(content: str) -> list[str]:
    """Detect heuristic policy tags from content."""
    tags: list[str] = []
    text = content or ""
    if _EMAIL_RE.search(text) or _PHONE_RE.search(text) or _SSN_RE.search(text):
        tags.append("pii")
        tags.append("retention:short")
    return tags


def merge_policy_tags(existing: list[str] | None, detected: list[str]) -> list[str]:
    out: list[str] = []
    for t in list(existing or []) + list(detected or []):
        if t and t not in out:
            out.append(t)
    return out


def apply_policy_on_write(
    memory: Memory,
    *,
    short_retention_days: int = DEFAULT_SHORT_RETENTION_DAYS,
    now: datetime | None = None,
) -> Memory:
    """Merge detected tags; set effective_to for retention:short when unset."""
    detected = detect_policy_tags(memory.content)
    memory.policy_tags = merge_policy_tags(memory.policy_tags, detected)
    if "retention:short" in memory.policy_tags and memory.effective_to is None:
        base = now or datetime.now(timezone.utc)
        if base.tzinfo is None:
            base = base.replace(tzinfo=timezone.utc)
        memory.effective_to = base + timedelta(days=int(short_retention_days))
        memory.source = {
            **(memory.source or {}),
            "policy_retention_days": int(short_retention_days),
        }
    # Adversarial injection cues → policy tags (Loop 5)
    try:
        from continuum_memory.injection import tag_injection_on_write

        tag_injection_on_write(memory)
    except Exception:
        pass
    return memory


def pack_exclude_pii_enabled() -> bool:
    return os.environ.get("CONTINUUM_PACK_EXCLUDE_PII", "").lower() in (
        "1",
        "true",
        "yes",
    )


def filter_by_policy(
    memories: list[Memory],
    *,
    exclude_tags: list[str] | None = None,
) -> list[Memory]:
    """Drop memories that carry any excluded policy tag."""
    if exclude_tags is None:
        exclude_tags = ["pii"] if pack_exclude_pii_enabled() else []
        # Injection quarantine defaults ON via CONTINUUM_PACK_EXCLUDE_INJECTION
        try:
            from continuum_memory.injection import pack_exclude_injection_enabled

            if pack_exclude_injection_enabled():
                exclude_tags = list(exclude_tags) + ["injection_risk", "untrusted"]
        except Exception:
            pass
    if not exclude_tags:
        return list(memories)
    excluded = {t.lower() for t in exclude_tags}
    out: list[Memory] = []
    for mem in memories:
        tags = {str(t).lower() for t in (mem.policy_tags or [])}
        if tags & excluded:
            continue
        out.append(mem)
    return out
