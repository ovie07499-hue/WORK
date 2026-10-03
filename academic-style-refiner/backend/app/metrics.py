"""Readability and style metrics. Pure Python, no external NLP models."""

import math
import re
from collections import Counter

from pydantic import BaseModel

from .textutils import split_sentences, words

_STOPWORDS = frozenset(
    """a an the and or but if of in on at to for from by with as is are was were be been
    being this that these those it its which who whom whose than then there their they
    we our you your he she his her not no so such can could may might will would should
    must do does did have has had also into over under between within without about""".split()
)


def count_syllables(word: str) -> int:
    w = word.lower().strip("'’")
    if not w.isalpha():
        return 1
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|[^laeiouy]ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    groups = re.findall(r"[aeiouy]{1,2}", w)
    return max(1, len(groups))


def _mtld_pass(tokens: list[str], threshold: float) -> float:
    factors = 0.0
    types: set[str] = set()
    count = 0
    for token in tokens:
        count += 1
        types.add(token)
        if len(types) / count <= threshold:
            factors += 1
            types, count = set(), 0
    if count:
        ttr = len(types) / count
        factors += (1 - ttr) / (1 - threshold) if ttr < 1 else 0
    return len(tokens) / factors if factors else float(len(tokens))


def mtld(tokens: list[str], threshold: float = 0.72) -> float:
    """Measure of Textual Lexical Diversity (McCarthy & Jarvis, 2010), bidirectional."""
    if len(tokens) < 10:
        return 0.0
    return (_mtld_pass(tokens, threshold) + _mtld_pass(tokens[::-1], threshold)) / 2


def mattr(tokens: list[str], window: int = 50) -> float:
    """Moving-average type-token ratio."""
    if not tokens:
        return 0.0
    if len(tokens) <= window:
        return len(set(tokens)) / len(tokens)
    counts = Counter(tokens[:window])
    total = len(counts) / window
    for i in range(window, len(tokens)):
        out_tok, in_tok = tokens[i - window], tokens[i]
        counts[out_tok] -= 1
        if counts[out_tok] == 0:
            del counts[out_tok]
        counts[in_tok] += 1
        total += len(counts) / window
    return total / (len(tokens) - window + 1)


class TextMetrics(BaseModel):
    words: int
    sentences: int
    paragraphs: int
    reading_minutes: float
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    type_token_ratio: float
    mattr: float
    mtld: float
    mean_sentence_length: float
    sentence_length_sd: float
    # Coefficient of variation of sentence length (SD / mean): higher means more varied rhythm.
    sentence_length_variation: float
    sentence_length_histogram: dict[str, int]
    # Share of sentences whose first word is not shared with another sentence.
    opening_variety: float
    repeated_phrases: list[tuple[str, int]]


_BUCKETS = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 10_000)]


def analyze(text: str) -> TextMetrics:
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    sentences = [s for p in paragraphs for s in split_sentences(p)]
    tokens_raw = words(text)
    tokens = [t.lower() for t in tokens_raw]
    alpha = [t for t in tokens_raw if t[0].isalpha()]
    n_words = len(tokens)
    n_sent = max(1, len(sentences))

    lengths = [len(words(s)) for s in sentences] or [0]
    mean_len = sum(lengths) / len(lengths)
    sd = math.sqrt(sum((x - mean_len) ** 2 for x in lengths) / len(lengths)) if len(lengths) > 1 else 0.0

    if alpha:
        syll_per_word = sum(count_syllables(w) for w in alpha) / len(alpha)
        words_per_sent = n_words / n_sent
        fre = 206.835 - 1.015 * words_per_sent - 84.6 * syll_per_word
        fkg = 0.39 * words_per_sent + 11.8 * syll_per_word - 15.59
    else:
        fre = fkg = 0.0

    histogram = {
        (f"{lo}+" if hi > 1000 else f"{lo}-{hi}"): sum(lo <= n <= hi for n in lengths if n) for lo, hi in _BUCKETS
    }

    openers = [words(s)[0].lower() for s in sentences if words(s)]
    opener_counts = Counter(openers)
    opening_variety = sum(1 for o in openers if opener_counts[o] == 1) / len(openers) if openers else 0.0

    trigrams = Counter(
        " ".join(tokens[i : i + 3])
        for i in range(len(tokens) - 2)
        if not all(t in _STOPWORDS for t in tokens[i : i + 3])
    )
    repeated = [(g, c) for g, c in trigrams.most_common(8) if c >= 3]

    return TextMetrics(
        words=n_words,
        sentences=len(sentences),
        paragraphs=len(paragraphs),
        reading_minutes=round(n_words / 238, 1),
        flesch_reading_ease=round(fre, 1),
        flesch_kincaid_grade=round(fkg, 1),
        type_token_ratio=round(len(set(tokens)) / n_words, 3) if n_words else 0.0,
        mattr=round(mattr(tokens), 3),
        mtld=round(mtld(tokens), 1),
        mean_sentence_length=round(mean_len, 1),
        sentence_length_sd=round(sd, 1),
        sentence_length_variation=round(sd / mean_len, 3) if mean_len else 0.0,
        sentence_length_histogram=histogram,
        opening_variety=round(opening_variety, 3),
        repeated_phrases=repeated,
    )
