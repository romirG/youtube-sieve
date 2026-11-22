"""Unit tests for youtube_sieve.domain.similarity."""

import math

import pytest

from youtube_sieve.domain.errors import DomainError, InvalidSimilarityConfigError
from youtube_sieve.domain.similarity import (
    DEFAULT_CONFIG,
    Document,
    ScoredDocument,
    SimilarityConfig,
    build_vectors,
    cosine,
    rank_by_similarity,
    tokenize,
)


def doc(doc_id: str, title: str = "", tags: str = "", description: str = "") -> Document:
    return Document(doc_id, {"title": title, "tags": tags, "description": description})


def ids(results: list[ScoredDocument]) -> list[str]:
    return [r.id for r in results]


# --- Tokenisation ---------------------------------------------------------------------------


def test_tokenize_case_folds_and_splits_on_punctuation():
    assert tokenize("Learn PYTHON: Decorators, Generators!") == [
        "learn",
        "python",
        "decorators",
        "generators",
    ]


def test_tokenize_removes_default_stop_words():
    assert tokenize("The basics of the Python language") == ["basics", "python", "language"]


def test_tokenize_drops_tokens_shorter_than_minimum():
    assert tokenize("a b cc ddd") == ["cc", "ddd"]


def test_tokenize_splits_underscores_and_keeps_digits():
    assert tokenize("python_3 tutorial 2026") == ["python", "tutorial", "2026"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Café Crème", ["café", "crème"]),
        ("STRASSE straße", ["strasse", "strasse"]),
        ("पायथन ट्यूटोरियल", ["पायथन", "ट्यूटोरियल"]),
    ],
)
def test_tokenize_handles_unicode(text, expected):
    assert tokenize(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "!!! ... ???", "the of and"])
def test_tokenize_returns_empty_list_when_nothing_usable(text):
    assert tokenize(text) == []


def test_tokenize_respects_custom_configuration():
    config = SimilarityConfig(
        field_weights={"title": 1.0}, stop_words=frozenset({"python"}), min_token_length=1
    )
    assert tokenize("a python b", config) == ["a", "b"]


# --- Cosine ---------------------------------------------------------------------------------


def test_cosine_of_identical_vectors_is_one():
    v = {"python": 0.6, "tutorial": 0.8}
    assert cosine(v, v) == pytest.approx(1.0)


def test_cosine_of_disjoint_vectors_is_zero():
    assert cosine({"python": 1.0}, {"cooking": 1.0}) == 0.0


def test_cosine_is_symmetric_and_scale_invariant():
    a, b = {"x": 1.0, "y": 2.0}, {"x": 3.0, "z": 4.0}
    assert cosine(a, b) == pytest.approx(cosine(b, a))
    assert cosine(a, b) == pytest.approx(cosine({k: 10 * v for k, v in a.items()}, b))


@pytest.mark.parametrize(
    "pair", [({}, {"x": 1.0}), ({"x": 1.0}, {}), ({}, {}), ({"x": 0.0}, {"x": 1.0})]
)
def test_cosine_with_empty_or_zero_vector_is_zero(pair):
    assert cosine(*pair) == 0.0


def test_cosine_matches_hand_computation():
    a, b = {"x": 1.0, "y": 1.0}, {"x": 1.0}
    assert cosine(a, b) == pytest.approx(1 / math.sqrt(2))


# --- Vectors --------------------------------------------------------------------------------


def test_vectors_are_unit_length():
    vectors = build_vectors([doc("a", "python decorators"), doc("b", "python generators")])
    for vector in vectors.values():
        assert math.sqrt(sum(w * w for w in vector.values())) == pytest.approx(1.0)


def test_document_without_usable_words_gets_empty_vector():
    vectors = build_vectors([doc("a", "python"), doc("b", "!!!")])
    assert vectors["b"] == {}


def test_rare_terms_weigh_more_than_common_terms():
    docs = [
        doc("a", "python tutorial"),
        doc("b", "python decorators"),
        doc("c", "python generators"),
    ]
    vector = build_vectors(docs)["b"]
    assert vector["decorators"] > vector["python"]


def test_fields_missing_from_weights_are_ignored():
    config = SimilarityConfig(field_weights={"title": 1.0})
    vectors = build_vectors([doc("a", "python", description="cooking")], config)
    assert set(vectors["a"]) == {"python"}


def test_zero_weight_field_is_ignored():
    config = SimilarityConfig(field_weights={"title": 1.0, "description": 0.0})
    vectors = build_vectors([doc("a", "python", description="cooking")], config)
    assert set(vectors["a"]) == {"python"}


def test_text_beyond_field_limit_is_ignored():
    config = SimilarityConfig(field_weights={"description": 1.0}, max_field_chars=20)
    description = "python tutorial " + "x" * 10 + " cooking"
    vectors = build_vectors([doc("a", description=description)], config)
    assert "cooking" not in vectors["a"] and "python" in vectors["a"]


# --- Ranking --------------------------------------------------------------------------------


def test_more_similar_candidate_ranks_first():
    query = doc("q", "python decorators explained")
    candidates = [
        doc("cook", "pasta cooking basics"),
        doc("deco", "python decorators deep dive"),
        doc("gen", "python generators"),
    ]
    assert ids(rank_by_similarity(query, candidates)) == ["deco", "gen", "cook"]


def test_rare_shared_term_beats_common_shared_term():
    query = doc("q", "python metaclasses")
    candidates = [
        doc("common", "python basics"),
        doc("rare", "metaclasses overview"),
        doc("other1", "python loops"),
        doc("other2", "python lists"),
    ]
    assert ids(rank_by_similarity(query, candidates))[0] == "rare"


def test_match_in_heavier_field_beats_match_in_lighter_field():
    query = doc("q", "kubernetes")
    candidates = [
        doc("in_description", "cluster guide", description="kubernetes"),
        doc("in_title", "kubernetes", description="cluster guide"),
    ]
    assert ids(rank_by_similarity(query, candidates)) == ["in_title", "in_description"]


def test_scores_are_between_zero_and_one():
    query = doc("q", "python decorators", "python", "learn python decorators today")
    candidates = [doc(str(i), "python decorators " * i) for i in range(1, 6)]
    candidates.append(doc("same", "python decorators", "python", "learn python decorators today"))
    for result in rank_by_similarity(query, candidates):
        assert 0.0 <= result.score <= 1.0


def test_identical_content_scores_one():
    query = doc("q", "python decorators")
    (result,) = rank_by_similarity(query, [doc("twin", "python decorators")])
    assert result.score == pytest.approx(1.0)


def test_unrelated_candidates_score_zero():
    results = rank_by_similarity(doc("q", "python"), [doc("a", "cooking"), doc("b", "gardening")])
    assert [r.score for r in results] == [0.0, 0.0]


def test_ties_are_broken_by_id():
    results = rank_by_similarity(
        doc("q", "python"), [doc("c", "java"), doc("a", "go"), doc("b", "rust")]
    )
    assert ids(results) == ["a", "b", "c"]


def test_ranking_is_deterministic_regardless_of_input_order():
    query = doc("q", "python decorators")
    candidates = [doc("a", "python"), doc("b", "decorators"), doc("c", "python decorators")]
    assert rank_by_similarity(query, candidates) == rank_by_similarity(query, candidates[::-1])


def test_query_itself_is_excluded_from_results():
    query = doc("q", "python")
    assert ids(rank_by_similarity(query, [doc("q", "python"), doc("a", "python")])) == ["a"]


def test_duplicate_candidates_keep_first_occurrence():
    query = doc("q", "python")
    results = rank_by_similarity(query, [doc("a", "python"), doc("a", "cooking")])
    assert len(results) == 1 and results[0].score > 0


def test_no_candidates_gives_empty_result():
    assert rank_by_similarity(doc("q", "python"), []) == []


def test_query_without_usable_words_scores_everything_zero():
    results = rank_by_similarity(doc("q", "!!! the"), [doc("a", "python"), doc("b", "java")])
    assert [r.score for r in results] == [0.0, 0.0]


def test_accepts_any_iterable_of_candidates():
    candidates = (doc(x, "python") for x in "ab")
    assert ids(rank_by_similarity(doc("q", "python"), candidates)) == ["a", "b"]


def test_large_candidate_set_is_ranked_completely():
    query = doc("q", "python decorators")
    candidates = [doc(f"v{i:04d}", f"topic{i} python") for i in range(2000)]
    candidates.append(doc("best", "python decorators"))
    results = rank_by_similarity(query, candidates)
    assert len(results) == 2001 and results[0].id == "best"


# --- Validation -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"field_weights": {}},
        {"field_weights": {"title": 0.0}},
        {"field_weights": {"title": -1.0}},
        {"field_weights": {"title": math.inf}},
        {"field_weights": {"title": math.nan}},
        {"field_weights": {"title": 1.0}, "max_field_chars": 0},
        {"field_weights": {"title": 1.0}, "min_token_length": 0},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(InvalidSimilarityConfigError):
        SimilarityConfig(**kwargs)


def test_configuration_error_is_a_domain_and_value_error():
    assert issubclass(InvalidSimilarityConfigError, DomainError)
    assert issubclass(InvalidSimilarityConfigError, ValueError)


@pytest.mark.parametrize("bad_id", ["", "   ", None, 7])
def test_document_requires_non_empty_text_id(bad_id):
    with pytest.raises(ValueError):
        Document(bad_id, {"title": "python"})


def test_default_configuration_weights_title_over_tags_over_description():
    weights = DEFAULT_CONFIG.field_weights
    assert weights["title"] > weights["tags"] > weights["description"] > 0
