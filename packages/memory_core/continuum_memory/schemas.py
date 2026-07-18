from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    PROCEDURAL = "procedural"
    DECISION = "decision"
    ARTIFACT_REF = "artifact_ref"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FORGOTTEN = "forgotten"


class Memory(BaseModel):
    id: str
    org_id: str
    workspace_id: str
    type: MemoryType
    content: str
    entities: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    utility: float = 1.0
    importance: float | None = None
    status: MemoryStatus = MemoryStatus.ACTIVE
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    created_at: datetime
    last_accessed_at: datetime
    source: dict[str, Any] = Field(default_factory=dict)
    superseded_by: str | None = None
    supersedes: list[str] = Field(default_factory=list)
    slots: dict[str, Any] = Field(default_factory=dict)
    policy_tags: list[str] = Field(default_factory=list)
    version: int = 1

    @field_validator("supersedes", mode="before")
    @classmethod
    def _coerce_supersedes(cls, v: Any) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                import json

                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(x) for x in parsed]
                except json.JSONDecodeError:
                    pass
            return [s]
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]


class PackedContext(BaseModel):
    memories: list[Memory]
    token_estimate: int
    algorithm: str
    explanations: list[str] = Field(default_factory=list)
    explanation_details: list[dict[str, Any]] = Field(default_factory=list)
    query: str = ""
    budget_tokens: int = 0
    candidate_count: int = 0


class ForgetAuditEvent(BaseModel):
    id: str
    memory_id: str
    workspace_id: str
    reason: str
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)
