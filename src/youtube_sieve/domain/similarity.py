"""Text similarity for ranking videos and channels from their metadata.

The YouTube Data API has no related-videos endpoint, so similarity is computed here (DC-3):

1. Each document's fields (for example title, tags, description) are tokenised and combined
   into weighted term counts, so a word in a heavier field counts for more.
2. Counts are dampened with log(1 + count) and multiplied by a smoothed inverse document
   frequency, idf(t) = ln((1 + n) / (1 + df(t))) + 1, so words shared by many documents matter
   less than rare ones.
3. Vectors are scaled to unit length, and documents are compared by cosine similarity.

Everything is pure Python with sparse dictionaries; cost grows linearly with the number of
words. No I/O happens here.
"""

from __future__ import annotations

import math
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from youtube_sieve.domain.errors import InvalidDocumentError, InvalidSimilarityConfigError

SparseVector = dict[str, float]

DEFAULT_FIELD_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {"title": 3.0, "tags": 2.0, "description": 1.0}
)
# Titles are at most 100 characters and tags 500, so in practice this bounds descriptions.
DEFAULT_MAX_FIELD_CHARS = 1000
DEFAULT_MIN_TOKEN_LENGTH = 2
DEFAULT_STOP_WORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "i", "in",
        "is", "it", "its", "my", "of", "on", "or", "that", "the", "this", "to", "was",
        "what", "when", "why", "with", "you", "your",
    }
)  # fmt: skip
SCORE_MIN = 0.0
SCORE_MAX = 1.0
_MARK_CATEGORY_PREFIX = "M"  # Unicode combining marks: Mn, Mc, Me


@dataclass(frozen=True)
class SimilarityConfig:
    """Tunable settings for tokenisation and weighting. Validated on creation."""

    field_weights: Mapping[str, float] = DEFAULT_FIELD_WEIGHTS
    max_field_chars: int = DEFAULT_MAX_FIELD_CHARS
    stop_words: frozenset[str] = DEFAULT_STOP_WORDS
    min_token_length: int = DEFAULT_MIN_TOKEN_LENGTH

    def __post_init__(self) -> None:
        weights = dict(self.field_weights)
        if not weights:
            raise InvalidSimilarityConfigError("field_weights must name at least one field")
        for name, weight in weights.items():
            if not math.isfinite(weight) or weight < 0:
                raise InvalidSimilarityConfigError(
                    f"weight for field '{name}' must be a finite number >= 0, got {weight}"
                )
        if not any(weight > 0 for weight in weights.values()):
            raise InvalidSimilarityConfigError("at least one field weight must be above 0")
        if self.max_field_chars < 1:
            raise InvalidSimilarityConfigError("max_field_chars must be at least 1")
        if self.min_token_length < 1:
            raise InvalidSimilarityConfigError("min_token_length must be at least 1")
        object.__setattr__(self, "field_weights", MappingProxyType(weights))
        object.__setattr__(self, "stop_words", frozenset(w.casefold() for w in self.stop_words))


DEFAULT_CONFIG = SimilarityConfig()


@dataclass(frozen=True)
class Document:
    """A text item to compare, such as a video's title, tags and description."""

    id: str
    fields: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidDocumentError(f"document id must be non-empty text, got {self.id!r}")


@dataclass(frozen=True, order=True)
class ScoredDocument:
    id: str
    score: float


def _is_word_char(char: str) -> bool:
    # Combining marks are part of words in many scripts (e.g. Devanagari vowel signs),
    # but str.isalnum() and the regex \w class treat them as separators.
    return char.isalnum() or unicodedata.category(char).startswith(_MARK_CATEGORY_PREFIX)


def _words(text: str) -> Iterable[str]:
    start = None
    for index, char in enumerate(text):
        if _is_word_char(char):
            if start is None:
                start = index
        elif start is not None:
            yield text[start:index]
            start = None
    if start is not None:
        yield text[start:]


def tokenize(text: str, config: SimilarityConfig = DEFAULT_CONFIG) -> list[str]:
    """Split text into case-folded words, dropping stop words and very short words."""
    tokens = []
    for word in _words(text):
        token = word.casefold()
        if len(token) >= config.min_token_length and token not in config.stop_words:
            tokens.append(token)
    return tokens


def _weighted_counts(document: Document, config: SimilarityConfig) -> dict[str, float]:
    counts: dict[str, float] = defaultdict(float)
    for name, weight in config.field_weights.items():
        if weight <= 0:
            continue
        text = (document.fields.get(name) or "")[: config.max_field_chars]
        for token in tokenize(text, config):
            counts[token] += weight
    return counts


def _unit(vector: SparseVector) -> SparseVector:
    norm = math.sqrt(sum(weight * weight for weight in vector.values()))
    return {term: weight / norm for term, weight in vector.items()} if norm else {}


def build_vectors(
    documents: Sequence[Document], config: SimilarityConfig = DEFAULT_CONFIG
) -> dict[str, SparseVector]:
    """Unit-length TF-IDF vectors for each document, keyed by document id.

    Document frequencies are computed over `documents` only. Ids should be unique; when they
    are not, the last document with an id wins.
    """
    counts = {document.id: _weighted_counts(document, config) for document in documents}
    total = len(counts)
    frequency = Counter(term for terms in counts.values() for term in terms)
    idf = {term: math.log((1 + total) / (1 + df)) + 1 for term, df in frequency.items()}
    return {
        doc_id: _unit({term: math.log1p(count) * idf[term] for term, count in terms.items()})
        for doc_id, terms in counts.items()
    }


def cosine(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    """Cosine similarity of two sparse vectors; 0.0 if either has no weight."""
    if len(a) > len(b):
        a, b = b, a
    dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
    norm = math.sqrt(sum(w * w for w in a.values())) * math.sqrt(sum(w * w for w in b.values()))
    return dot / norm if norm else 0.0


def rank_by_similarity(
    query: Document,
    candidates: Iterable[Document],
    config: SimilarityConfig = DEFAULT_CONFIG,
) -> list[ScoredDocument]:
    """Score every candidate against the query, best first.

    The query itself (same id) and repeated candidate ids (after the first) are excluded.
    Scores are in [0, 1]; equal scores are ordered by id, so results are deterministic.
    """
    unique: dict[str, Document] = {}
    for candidate in candidates:
        if candidate.id != query.id and candidate.id not in unique:
            unique[candidate.id] = candidate
    if not unique:
        return []
    vectors = build_vectors([query, *unique.values()], config)
    query_vector = vectors[query.id]
    scored = [
        ScoredDocument(
            doc_id, min(SCORE_MAX, max(SCORE_MIN, cosine(query_vector, vectors[doc_id])))
        )
        for doc_id in unique
    ]
    return sorted(scored, key=lambda result: (-result.score, result.id))
