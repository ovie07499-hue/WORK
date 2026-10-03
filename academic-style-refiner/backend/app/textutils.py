"""Tokenisation helpers shared by the chunker and the metrics."""

import re

_ABBREVIATIONS = {
    "al",
    "e.g",
    "i.e",
    "etc",
    "cf",
    "vs",
    "fig",
    "figs",
    "eq",
    "eqs",
    "no",
    "nos",
    "vol",
    "pp",
    "p",
    "ch",
    "sec",
    "dr",
    "prof",
    "mr",
    "mrs",
    "ms",
    "st",
    "jr",
    "sr",
    "approx",
    "ca",
    "resp",
    "ref",
    "refs",
    "tab",
    "u.s",
    "u.k",
    "inc",
    "ltd",
    "co",
}

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?…])([\"”’)\]]*)(\s+)(?=[\"“‘(\[⟦]*[A-Z0-9⟦])")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+(?:['’-][A-Za-zÀ-ÖØ-öø-ÿ]+)*|\d+(?:[.,]\d+)*")


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, without breaking on common academic abbreviations."""
    text = " ".join(text.split())
    if not text:
        return []
    pieces: list[str] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        candidate = text[start : match.start(2)]
        last_word = re.search(r"([A-Za-z.]+)\.[\"”’)\]]*$", candidate)
        if last_word and last_word.group(1).lower().rstrip(".") in _ABBREVIATIONS:
            continue
        # Single capital initial ("J. Smith") is not a sentence end.
        if re.search(r"(?:^|\s)[A-Z]\.$", candidate):
            continue
        pieces.append(candidate)
        start = match.end()
    tail = text[start:].strip()
    if tail:
        pieces.append(tail)
    return pieces


def words(text: str) -> list[str]:
    return _WORD_RE.findall(text)


def word_count(text: str) -> int:
    return len(words(text))
