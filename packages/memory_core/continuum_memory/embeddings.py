from __future__ import annotations

import hashlib
import math
import os
import re
from functools import lru_cache
from typing import Sequence

EMBED_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t]


def local_embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic hashed bag-of-words / TF-style fixed-dim embedding (offline)."""
    vec = [0.0] * dim
    tokens = _tokenize(text)
    if not tokens:
        return vec
    # Simple TF with hashed feature indices
    counts: dict[str, int] = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    for token, tf in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        # log TF dampening
        vec[idx] += sign * (1.0 + math.log(tf))
    return _l2_normalize(vec)


def _l2_normalize(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm < 1e-12:
        return list(vec)
    return [v / norm for v in vec]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _api_embed(text: str) -> list[float] | None:
    """Qwen/DashScope OpenAI-compatible embeddings when API key present. Soft-fail."""
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        base_url = os.environ.get(
            "QWEN_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        model = os.environ.get("QWEN_EMBED_MODEL", "text-embedding-v3")
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.embeddings.create(model=model, input=text[:8000])
        vec = list(resp.data[0].embedding)
        return _l2_normalize(vec)
    except Exception:
        return None


@lru_cache(maxsize=2048)
def embed_text_cached(text: str) -> tuple[float, ...]:
    return tuple(embed_text(text))


def embed_text(text: str) -> list[float]:
    """Prefer API embeddings when key present; always soft-fail to local."""
    if os.environ.get("CONTINUUM_FORCE_LOCAL_EMBED", "").lower() in ("1", "true", "yes"):
        return local_embed(text)
    api_vec = _api_embed(text)
    if api_vec is not None:
        # Project / pad to EMBED_DIM for stable local cosine with cached locals
        if len(api_vec) == EMBED_DIM:
            return api_vec
        if len(api_vec) > EMBED_DIM:
            # Fold high dims into EMBED_DIM via hashing
            out = [0.0] * EMBED_DIM
            for i, v in enumerate(api_vec):
                out[i % EMBED_DIM] += v
            return _l2_normalize(out)
        out = list(api_vec) + [0.0] * (EMBED_DIM - len(api_vec))
        return _l2_normalize(out)
    return local_embed(text)


def embed_batch(texts: list[str]) -> list[list[float]]:
    return [embed_text(t) for t in texts]
