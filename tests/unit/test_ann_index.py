from __future__ import annotations

import pytest

from continuum_memory.ann_index import ANNIndex, ann_search
from continuum_memory.embeddings import cosine_similarity, local_embed

pytestmark = pytest.mark.unit


def _unit_vector(dim: int, hot_index: int) -> list[float]:
    vec = [0.0] * dim
    vec[hot_index] = 1.0
    return vec


def test_brute_force_path_returns_exact_top_match():
    ids = ["a", "b", "c"]
    vectors = [_unit_vector(4, 0), _unit_vector(4, 1), _unit_vector(4, 2)]
    query = _unit_vector(4, 0)
    results = ann_search(ids, vectors, query, top_k=3)
    assert results[0][0] == "a"
    assert results[0][1] == pytest.approx(1.0)


def test_search_ranking_matches_brute_force_cosine_for_small_n():
    ids = [f"m{i}" for i in range(10)]
    vectors = [local_embed(f"document number {i} about topic {i % 3}") for i in range(10)]
    query_vec = local_embed("topic 1 document")

    index = ANNIndex(ids, vectors)
    ann_ranked = index.search(query_vec, top_k=10)
    expected_sims = {ids[i]: cosine_similarity(vectors[i], query_vec) for i in range(10)}

    # All ids present (top_k == n) with sims matching a direct brute-force
    # cosine computation, and the returned order is non-increasing by sim —
    # order-independent so it can't spuriously fail on exact tie-break ties.
    assert {mid for mid, _ in ann_ranked} == set(ids)
    for mid, sim in ann_ranked:
        assert sim == pytest.approx(expected_sims[mid], abs=1e-9)
    sims_in_order = [sim for _, sim in ann_ranked]
    assert sims_in_order == sorted(sims_in_order, reverse=True)


def test_empty_index_returns_empty_results():
    index = ANNIndex([], [])
    assert index.search([1.0, 0.0], top_k=5) == []


def test_top_k_respected():
    ids = [f"m{i}" for i in range(20)]
    vectors = [local_embed(f"unrelated filler content {i}") for i in range(20)]
    index = ANNIndex(ids, vectors)
    results = index.search(local_embed("query text"), top_k=5)
    assert len(results) <= 5


def test_ivf_lite_path_used_above_threshold_still_finds_exact_self_match():
    """Above BRUTE_FORCE_THRESHOLD the numpy IVF-lite path activates. Requesting
    top_k == n forces the centroid shortlist to eventually cover every node
    (disjoint cluster partitions sum to n), so this stays an exact check
    regardless of how the coarse clustering happens to partition the space."""
    pytest.importorskip("numpy", reason="numpy optional for IVF-lite path")
    from continuum_memory import ann_index as ann_index_mod

    n = ann_index_mod.BRUTE_FORCE_THRESHOLD + 20
    ids = [f"m{i}" for i in range(n)]
    vectors = [local_embed(f"unique document content number {i} lorem ipsum {i * 7}") for i in range(n)]
    target_index = 7
    target_query = list(vectors[target_index])

    index = ANNIndex(ids, vectors)
    results = index.search(target_query, top_k=n)
    result_ids = [mid for mid, _ in results]

    assert ids[target_index] in result_ids
    assert results[0][0] == ids[target_index]
    assert results[0][1] == pytest.approx(1.0, abs=1e-6)
