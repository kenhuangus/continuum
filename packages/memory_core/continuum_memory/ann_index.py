"""Approximate nearest-neighbor shortlist for dense retrieval.

Honest scope: this is a lightweight numpy IVF-*lite* index (coarse centroids +
shortlist scan), **not** a production ANN library. It exists so
`dense_retrieve_with_sims` scales past a full O(N) brute-force cosine scan on
larger workspaces, while staying correct-by-construction on the small
workspaces this project is evaluated against today.

Dependency posture (see docs/research/LOOP3_NOTES.md §2 + evals/README.md):
- No hard new dependency. `numpy` is used opportunistically for the coarse
  centroid path; if unavailable, everything falls back to a pure-Python
  brute-force cosine scan (still exact, just O(N)).
- `faiss` is used opportunistically (IndexFlatIP) when importable, purely as
  a performance optimization on larger corpora — never required.
- All vectors are assumed L2-normalized (as `embeddings.embed_text` already
  guarantees), so similarity is a plain dot product — consistent with
  `embeddings.cosine_similarity`.
"""

from __future__ import annotations

import math
from typing import Sequence

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover - optional dependency
    np = None  # type: ignore[assignment]
    _HAS_NUMPY = False

try:
    import faiss  # type: ignore

    _HAS_FAISS = _HAS_NUMPY  # faiss path needs numpy arrays too
except ImportError:  # pragma: no cover - optional dependency
    faiss = None  # type: ignore[assignment]
    _HAS_FAISS = False

# Brute-force is exact and fast enough below this size; IVF-lite only kicks
# in above it (design notes §2).
BRUTE_FORCE_THRESHOLD = 256


def _cosine_py(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def _brute_force_py(
    ids: list[str], vectors: list[list[float]], query: Sequence[float], top_k: int
) -> list[tuple[str, float]]:
    scored = [(ids[i], _cosine_py(vectors[i], query)) for i in range(len(ids))]
    scored.sort(key=lambda p: p[1], reverse=True)
    return scored[:top_k]


class ANNIndex:
    """Shortlist index: brute-force cosine, or numpy IVF-lite above threshold."""

    def __init__(
        self,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
        n_centroids: int | None = None,
    ) -> None:
        self.ids: list[str] = list(ids)
        self.n = len(self.ids)
        self._vectors: list[list[float]] = [list(v) for v in vectors]

        self._faiss_index = None
        self._np_vectors = None
        self._centroids = None
        self._assignments = None

        if self.n == 0:
            return

        use_ivf = _HAS_NUMPY and self.n > BRUTE_FORCE_THRESHOLD
        if _HAS_FAISS and use_ivf:
            try:
                dim = len(self._vectors[0])
                arr = np.asarray(self._vectors, dtype="float32")
                index = faiss.IndexFlatIP(dim)
                index.add(arr)
                self._faiss_index = index
            except Exception:
                self._faiss_index = None

        if self._faiss_index is None and _HAS_NUMPY:
            self._np_vectors = np.asarray(self._vectors, dtype="float64")
            if use_ivf:
                self._build_centroids(n_centroids)

    def _build_centroids(self, n_centroids: int | None) -> None:
        k = n_centroids or max(1, int(math.sqrt(self.n)))
        k = max(1, min(k, self.n))
        seed_idx = [int(i * self.n / k) for i in range(k)]
        centroids = self._np_vectors[seed_idx].copy()
        for _ in range(5):
            sims = self._np_vectors @ centroids.T
            assign = sims.argmax(axis=1)
            for c in range(k):
                members = self._np_vectors[assign == c]
                if len(members) > 0:
                    centroids[c] = members.mean(axis=0)
        final_sims = self._np_vectors @ centroids.T
        self._assignments = final_sims.argmax(axis=1)
        self._centroids = centroids

    def search(
        self,
        query_vector: Sequence[float],
        top_k: int = 50,
        shortlist_mult: int = 8,
    ) -> list[tuple[str, float]]:
        """Return up to `top_k` (id, similarity) pairs, best first."""
        if self.n == 0:
            return []

        if self._faiss_index is not None:
            q = np.asarray([query_vector], dtype="float32")
            k = min(top_k, self.n)
            sims, idxs = self._faiss_index.search(q, k)
            return [
                (self.ids[i], float(s)) for s, i in zip(sims[0], idxs[0]) if i >= 0
            ]

        if self._np_vectors is not None:
            q = np.asarray(query_vector, dtype="float64")
            if self._centroids is not None and self._assignments is not None:
                centroid_sims = self._centroids @ q
                centroid_order = centroid_sims.argsort()[::-1]
                shortlist_size = min(self.n, max(top_k * shortlist_mult, top_k))
                shortlist: list[int] = []
                for c in centroid_order:
                    members = [i for i in range(self.n) if self._assignments[i] == c]
                    shortlist.extend(members)
                    if len(shortlist) >= shortlist_size:
                        break
                sims = self._np_vectors[shortlist] @ q
                pairs = sorted(
                    zip(shortlist, sims.tolist()), key=lambda p: p[1], reverse=True
                )[:top_k]
                return [(self.ids[i], float(s)) for i, s in pairs]

            sims = self._np_vectors @ q
            order = sims.argsort()[::-1][:top_k]
            return [(self.ids[i], float(sims[i])) for i in order]

        return _brute_force_py(self.ids, self._vectors, query_vector, top_k)


def ann_search(
    ids: Sequence[str],
    vectors: Sequence[Sequence[float]],
    query_vector: Sequence[float],
    top_k: int = 50,
) -> list[tuple[str, float]]:
    """One-shot convenience wrapper around `ANNIndex`."""
    return ANNIndex(ids, vectors).search(query_vector, top_k=top_k)
