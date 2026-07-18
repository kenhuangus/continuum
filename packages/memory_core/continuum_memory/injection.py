"""Adversarial memory-injection detection and sanitization.

Honest claim: regex/pattern quarantine for demo hardening — not a full LLM
guardrail product or research-grade prompt-injection detector.
"""

from __future__ import annotations

import os
import re

from continuum_memory.schemas import Memory

_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_prior", re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+instructions?")),
    ("disregard_prior", re.compile(r"(?i)disregard\s+(all\s+)?(previous|prior|above)")),
    ("system_spoof", re.compile(r"(?i)(?:^|\n)\s*system\s*:\s*")),
    ("role_hijack", re.compile(r"(?i)you\s+are\s+now\s+")),
    ("system_tag", re.compile(r"(?i)<\s*/?\s*system\s*>")),
    ("developer_mode", re.compile(r"(?i)developer\s+mode|jailbreak|dan\s+mode")),
    ("exfil_tools", re.compile(r"(?i)(?:reveal|dump|exfiltrate)\s+(?:your\s+)?(?:system\s+)?(?:prompt|tools|api\s*keys?)")),
    ("override_policy", re.compile(r"(?i)override\s+(?:all\s+)?(?:safety|policy|guardrails?)")),
]


def detect_injection(content: str) -> list[str]:
    """Return injection cue tag names found in content."""
    text = content or ""
    hits: list[str] = []
    for name, pat in _INJECTION_PATTERNS:
        if pat.search(text):
            hits.append(name)
    return hits


def sanitize_memory_content(text: str) -> str:
    """Redact injection-like spans; shared by agent pack formatting and pack path."""
    cleaned = text or ""
    for _name, pat in _INJECTION_PATTERNS:
        cleaned = pat.sub("[filtered]", cleaned)
    return cleaned


def tag_injection_on_write(memory: Memory) -> Memory:
    """Merge injection_risk / untrusted policy tags when cues are present."""
    hits = detect_injection(memory.content)
    if not hits:
        return memory
    tags = list(memory.policy_tags or [])
    for t in ("injection_risk", "untrusted"):
        if t not in tags:
            tags.append(t)
    memory.policy_tags = tags
    memory.source = {
        **(memory.source or {}),
        "injection_cues": hits,
    }
    # Soft-demote confidence so RIR does not prefer poisoned rows.
    memory.confidence = min(float(memory.confidence), 0.35)
    return memory


def pack_exclude_injection_enabled() -> bool:
    """Default ON — set CONTINUUM_PACK_EXCLUDE_INJECTION=0 to allow through (sanitized)."""
    raw = os.environ.get("CONTINUUM_PACK_EXCLUDE_INJECTION", "1").lower()
    return raw not in ("0", "false", "no", "off")


def filter_injection_memories(memories: list[Memory]) -> list[Memory]:
    """Drop or keep injection-tagged memories per env policy."""
    if not pack_exclude_injection_enabled():
        return list(memories)
    out: list[Memory] = []
    for mem in memories:
        tags = {str(t).lower() for t in (mem.policy_tags or [])}
        if "injection_risk" in tags or "untrusted" in tags:
            continue
        out.append(mem)
    return out
