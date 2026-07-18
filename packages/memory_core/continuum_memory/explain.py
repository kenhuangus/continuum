from __future__ import annotations

from continuum_memory.packer import memory_tokens
from continuum_memory.schemas import Memory, MemoryStatus, PackedContext


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


def explain_memory_inclusion(memory_id: str, packed: PackedContext) -> str:
    for line in packed.explanations:
        if memory_id[:8] in line or memory_id in line:
            return line
    return f"Memory {memory_id} was not included in pack (algorithm={packed.algorithm})"
