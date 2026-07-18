"""Pure-Python Okapi BM25 (Robertson & Sparck Jones 1976/1994) — no hard deps.

Used as the primary sparse-retrieval scorer in `retrieve.sparse_retrieve`.
This is an in-process scorer over the candidate memory set passed at call
time (no persisted inverted index) — appropriate for the workspace sizes
Continuum targets today; a real inverted index would be the next step for
larger corpora.
"""

from __future__ import annotations

import math
import re
from typing import Sequence

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t]


class BM25:
    """Okapi BM25 scorer over a fixed corpus of raw-text documents."""

    def __init__(
        self,
        documents: Sequence[str],
        k1: float = DEFAULT_K1,
        b: float = DEFAULT_B,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[list[str]] = [tokenize(d) for d in documents]
        self.doc_len: list[int] = [len(toks) for toks in self.doc_tokens]
        self.n = len(self.doc_tokens)
        self.avgdl = (sum(self.doc_len) / self.n) if self.n else 0.0

        self._term_counts: list[dict[str, int]] = []
        df: dict[str, int] = {}
        for toks in self.doc_tokens:
            counts: dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self._term_counts.append(counts)
            for term in counts:
                df[term] = df.get(term, 0) + 1

        self.idf: dict[str, float] = {
            term: math.log(1.0 + (self.n - d + 0.5) / (d + 0.5)) for term, d in df.items()
        }

    def _idf(self, term: str) -> float:
        # Unseen query terms get a small positive idf so multi-term queries
        # still discriminate rather than contributing exactly zero.
        return self.idf.get(term, math.log(1.0 + (self.n + 0.5) / 0.5) if self.n else 0.0)

    def score_doc(self, query_tokens: Sequence[str], doc_index: int) -> float:
        if self.n == 0 or not query_tokens:
            return 0.0
        counts = self._term_counts[doc_index]
        dl = self.doc_len[doc_index]
        denom_norm = self.k1 * (1 - self.b + self.b * (dl / self.avgdl if self.avgdl else 1.0))
        score = 0.0
        for term in query_tokens:
            f = counts.get(term, 0)
            if f == 0:
                continue
            score += self._idf(term) * (f * (self.k1 + 1)) / (f + denom_norm)
        return score

    def scores(self, query: str) -> list[float]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return [0.0] * self.n
        return [self.score_doc(q_tokens, i) for i in range(self.n)]


def bm25_scores(
    documents: Sequence[str],
    query: str,
    k1: float = DEFAULT_K1,
    b: float = DEFAULT_B,
) -> list[float]:
    """Convenience: build a one-shot BM25 index and score `query` against it."""
    return BM25(documents, k1=k1, b=b).scores(query)
