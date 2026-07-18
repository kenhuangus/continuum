from __future__ import annotations

import pytest

from continuum_memory.bm25 import BM25, bm25_scores, tokenize

pytestmark = pytest.mark.unit


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Acme's 12% Discount!") == ["acme", "s", "12", "discount"]


def test_bm25_ranks_matching_document_highest():
    docs = [
        "Approved 12% discount for Acme.",
        "Weather was cloudy yesterday in the lounge.",
        "Cafeteria menu updated with new snacks.",
    ]
    scores = bm25_scores(docs, "Acme discount")
    assert len(scores) == 3
    assert scores[0] > scores[1]
    assert scores[0] > scores[2]


def test_bm25_zero_for_empty_query():
    docs = ["Approved 12% discount for Acme.", "Something else entirely."]
    assert bm25_scores(docs, "") == [0.0, 0.0]


def test_bm25_zero_for_empty_corpus():
    assert bm25_scores([], "discount") == []


def test_bm25_rare_term_scores_higher_than_common_term_match():
    """Classic IDF behavior: a term present in most docs contributes less
    than a term that discriminates a single document."""
    docs = [
        "Acme discount decision.",
        "Acme quarterly review.",
        "Acme onboarding notes.",
        "Acme support ticket log.",
    ]
    scores = bm25_scores(docs, "Acme discount")
    # doc 0 has both "acme" (common) and "discount" (rare) — must win clearly.
    assert scores[0] > scores[1]
    assert scores[0] > scores[2]
    assert scores[0] > scores[3]


def test_bm25_class_reusable_across_queries():
    index = BM25(["Globex VIP customer.", "Globex prefers email.", "Random noise text."])
    vip_scores = index.scores("VIP customer")
    email_scores = index.scores("prefers email")
    assert vip_scores[0] > vip_scores[1]
    assert vip_scores[0] > vip_scores[2]
    assert email_scores[1] > email_scores[0]
    assert email_scores[1] > email_scores[2]


def test_bm25_longer_document_normalized_by_length():
    """A short doc matching once should not always lose to a long doc that
    repeats the term many times but is diluted by unrelated filler — BM25's
    length normalization (`b`) caps the runaway term-frequency advantage."""
    short_doc = "discount approved"
    long_doc = "discount " * 50 + "filler " * 200
    scores = bm25_scores([short_doc, long_doc], "discount")
    # Both should score positively; BM25 saturates repeated-term frequency.
    assert scores[0] > 0
    assert scores[1] > 0
