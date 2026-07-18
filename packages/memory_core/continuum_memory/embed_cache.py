"""Embedding cache helpers — soft-fail when store lacks cache methods."""

from __future__ import annotations

import hashlib

from continuum_memory.embeddings import embed_text
from continuum_memory.schemas import Memory


def content_hash(memory: Memory) -> str:
    entities = "\0".join(memory.entities or [])
    payload = f"{memory.content}\0{entities}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def get_or_embed(store, memory: Memory) -> list[float]:
    text = f"{memory.content} {' '.join(memory.entities)}"
    try:
        if store is None or not hasattr(store, "get_embed_cache"):
            return embed_text(text)
        h = content_hash(memory)
        hit = store.get_embed_cache(memory.id)
        if hit is not None:
            cached_hash, vector = hit
            if cached_hash == h and vector:
                return vector
        vec = embed_text(text)
        if hasattr(store, "put_embed_cache"):
            store.put_embed_cache(memory.id, h, vec)
        return vec
    except Exception:
        return embed_text(text)
