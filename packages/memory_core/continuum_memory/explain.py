from __future__ import annotations

import re

from continuum_memory.packer import memory_tokens
from continuum_memory.schemas import Memory, MemoryStatus, PackedContext
from continuum_memory.scoring import score_breakdown

_CAPWORD_RE = re.compile(r"\b[A-Z][a-zA-Z0-9]+\b")
_CONTRADICTION_CUES = re.compile(
    r"(?i)\b(?:not|never|no longer|obsolete|outdated|incorrect|false|ignore previous|"
    r"disregard|instead of)\b"
)
_DIGIT_RE = re.compile(r"\d+(?:\.\d+)?")


def cite_overlap(query: str, content: str) -> float:
    """Lexical token overlap (Jaccard) as a lightweight faithfulness signal.

    Honest claim: sparse cite-overlap — not NLI/entailment faithfulness.
    """
    q_terms = {t for t in (query or "").lower().split() if t}
    c_terms = {t for t in (content or "").lower().split() if t}
    if not q_terms or not c_terms:
        return 0.0
    inter = len(q_terms & c_terms)
    union = len(q_terms | c_terms)
    return float(inter) / float(union) if union else 0.0


def _entity_coverage(query: str, content: str, entities: list[str] | None) -> float:
    """Fraction of query entities / CapWords attested in content."""
    cand: set[str] = set()
    for e in entities or []:
        if e and str(e).strip():
            cand.add(str(e).strip().lower())
    for m in _CAPWORD_RE.findall(query or ""):
        if m.lower() not in {"what", "when", "where", "which", "who", "how", "the"}:
            cand.add(m.lower())
    if not cand:
        return 0.5  # neutral when no entities to check
    hay = (content or "").lower()
    hits = sum(1 for e in cand if e in hay)
    return float(hits) / float(len(cand))


def _contradiction_penalty(query: str, content: str) -> float:
    """Soft penalty for negation/obsolescence cues and digit clashes vs query."""
    text = content or ""
    penalty = 0.0
    if _CONTRADICTION_CUES.search(text):
        penalty += 0.25
    q_digits = set(_DIGIT_RE.findall(query or ""))
    c_digits = set(_DIGIT_RE.findall(text))
    if q_digits and c_digits and q_digits.isdisjoint(c_digits):
        # Query asks about a number the memory does not share — mild mismatch signal
        penalty += 0.15
    return min(0.6, penalty)


def faithfulness_score(
    query: str,
    content: str,
    *,
    entities: list[str] | None = None,
) -> dict:
    """Heuristic grounding score beyond pure Jaccard.

    score ≈ 0.5*cite_overlap + 0.4*entity_coverage − contradiction_penalty (clipped).
    Honest claim: heuristic critic — not NLI/entailment faithfulness.
    """
    overlap = cite_overlap(query, content)
    coverage = _entity_coverage(query, content, entities)
    penalty = _contradiction_penalty(query, content)
    raw = 0.5 * overlap + 0.4 * coverage - penalty
    score = max(0.0, min(1.0, raw))
    return {
        "score": score,
        "cite_overlap": overlap,
        "entity_coverage": coverage,
        "contradiction_penalty": penalty,
    }


def explain_pack(
    all_memories: list[Memory],
    packed: PackedContext,
    query: str,
    budget_tokens: int,
    algorithm: str,
) -> list[str]:
    """Explain why memories were included or excluded from a pack."""
    included_ids = {m.id for m in packed.memories}
    lines = list(packed.explanations)

    for mem in all_memories:
        if mem.id in included_ids:
            continue
        if mem.status != MemoryStatus.ACTIVE:
            lines.append(f"Excluded [{mem.id[:8]}]: status={mem.status.value}")
            continue
        cost = memory_tokens(mem)
        lines.append(
            f"Excluded [{mem.id[:8]}] ({mem.type.value}): not selected by {algorithm} "
            f"(cost={cost}, budget={budget_tokens})"
        )

    return lines


def explain_pack_structured(
    all_memories: list[Memory],
    packed: PackedContext,
    query: str,
    budget_tokens: int,
    algorithm: str,
) -> list[dict]:
    """Structured pack explanations with score breakdown + cite_overlap."""
    included_ids = {m.id for m in packed.memories}
    details: list[dict] = []

    for mem in packed.memories:
        try:
            bd = score_breakdown(mem, query, peers=list(all_memories) or None)
        except Exception:
            bd = {}
        faith = faithfulness_score(query, mem.content, entities=mem.entities)
        details.append(
            {
                "id": mem.id,
                "included": True,
                "type": mem.type.value,
                "tokens": memory_tokens(mem),
                "cite_overlap": faith["cite_overlap"],
                "faithfulness": faith,
                "recency": bd.get("recency"),
                "importance": bd.get("importance"),
                "relevance": bd.get("relevance"),
                "combined": bd.get("combined"),
                "reason": f"selected by {algorithm}",
            }
        )

    for mem in all_memories:
        if mem.id in included_ids:
            continue
        reason = (
            f"status={mem.status.value}"
            if mem.status != MemoryStatus.ACTIVE
            else f"not selected by {algorithm}"
        )
        faith = faithfulness_score(query, mem.content, entities=mem.entities)
        details.append(
            {
                "id": mem.id,
                "included": False,
                "type": mem.type.value,
                "tokens": memory_tokens(mem),
                "cite_overlap": faith["cite_overlap"],
                "faithfulness": faith,
                "budget_tokens": budget_tokens,
                "reason": reason,
            }
        )
    return details


def explain_memory_inclusion(memory_id: str, packed: PackedContext) -> str:
    for line in packed.explanations:
        if memory_id[:8] in line or memory_id in line:
            return line
    for detail in packed.explanation_details or []:
        if detail.get("id") == memory_id or str(detail.get("id", "")).startswith(
            memory_id[:8]
        ):
            status = "Included" if detail.get("included") else "Excluded"
            return (
                f"{status} [{memory_id[:8]}]: {detail.get('reason', '')} "
                f"(cite_overlap={detail.get('cite_overlap', 0):.2f})"
            )
    return f"Memory {memory_id} was not included in pack (algorithm={packed.algorithm})"


def explain_memory_structured(
    memory_id: str,
    packed: PackedContext,
    query: str = "",
) -> dict:
    """Structured single-memory explain for HTTP/MCP."""
    for detail in packed.explanation_details or []:
        did = str(detail.get("id", ""))
        if did == memory_id or did.startswith(memory_id[:8]) or memory_id.startswith(
            did[:8]
        ):
            faith = detail.get("faithfulness") or {
                "score": float(detail.get("cite_overlap") or 0.0),
                "cite_overlap": float(detail.get("cite_overlap") or 0.0),
            }
            return {
                "explanation": explain_memory_inclusion(memory_id, packed),
                "details": detail,
                "cite_overlap": float(detail.get("cite_overlap") or 0.0),
                "faithfulness": faith,
                "algorithm": packed.algorithm,
                "query": query or packed.query,
            }
    # Fallback: compute overlap against packed contents if id missing from details
    for mem in packed.memories:
        if mem.id == memory_id:
            faith = faithfulness_score(query or packed.query, mem.content, entities=mem.entities)
            return {
                "explanation": explain_memory_inclusion(memory_id, packed),
                "details": {
                    "id": mem.id,
                    "included": True,
                    "cite_overlap": faith["cite_overlap"],
                    "faithfulness": faith,
                },
                "cite_overlap": faith["cite_overlap"],
                "faithfulness": faith,
                "algorithm": packed.algorithm,
                "query": query or packed.query,
            }
    return {
        "explanation": explain_memory_inclusion(memory_id, packed),
        "details": {"id": memory_id, "included": False},
        "cite_overlap": 0.0,
        "faithfulness": {"score": 0.0, "cite_overlap": 0.0},
        "algorithm": packed.algorithm,
        "query": query or packed.query,
    }
