"""Split a document into blocks (headings, paragraphs, lists, references) and
split over-long paragraphs into sentence-aligned segments for rewriting."""

import re
from dataclasses import dataclass
from typing import Literal

from .textutils import split_sentences, word_count

BlockKind = Literal["heading", "paragraph", "list", "reference"]

_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*•▪◦]|\d{1,3}[.)]|[a-z][.)]|\([a-z0-9]{1,3}\))\s+")
_MD_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S")
_NUMBERED_HEADING_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?|[IVXLC]+\.)\s+[A-Z]")
_REFERENCES_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\d+(?:\.\d+)*\.?\s*)?"
    r"(references|bibliography|works cited|literature cited|sources)\s*:?\s*$",
    re.IGNORECASE,
)


@dataclass
class Block:
    id: int
    kind: BlockKind
    text: str

    @property
    def rewritable(self) -> bool:
        return self.kind in ("paragraph", "list")


def _is_heading(text: str) -> bool:
    if "\n" in text:
        return False
    if _MD_HEADING_RE.match(text):
        return True
    n = word_count(text)
    if n == 0 or n > 14:
        return False
    if text.rstrip().endswith((".", "?", "!", ";", ",")):
        return False
    return bool(_NUMBERED_HEADING_RE.match(text)) or n <= 10


def _raw_blocks(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    if re.search(r"\n\s*\n", text):
        return [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    # No blank lines: treat each non-empty line as its own block.
    return [line.strip() for line in text.split("\n") if line.strip()]


def split_document(text: str) -> list[Block]:
    blocks: list[Block] = []
    in_references = False
    for raw in _raw_blocks(text):
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
        is_list = len(lines) > 1 and sum(bool(_LIST_ITEM_RE.match(ln)) for ln in lines) >= len(lines) / 2
        if is_list:
            body = "\n".join(lines)
        else:
            # Re-flow hard-wrapped lines into a single paragraph.
            body = " ".join(lines)

        if _REFERENCES_HEADING_RE.match(body):
            in_references = True
            kind: BlockKind = "heading"
        elif in_references:
            kind = "reference"
        elif is_list:
            kind = "list"
        elif _is_heading(body):
            kind = "heading"
        else:
            kind = "paragraph"
        blocks.append(Block(id=len(blocks), kind=kind, text=body))
    return blocks


def segment(text: str, max_words: int) -> list[str]:
    """Split a long paragraph into consecutive sentence groups of at most ~max_words."""
    if word_count(text) <= max_words or "\n" in text:
        return [text]
    sentences = split_sentences(text)
    total = sum(word_count(s) for s in sentences)
    # Aim for evenly sized segments rather than one full segment and a stub.
    n_segments = -(-total // max_words)
    target = total / n_segments
    segments: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        n = word_count(sentence)
        if current and current_words + n / 2 > target and len(segments) < n_segments - 1:
            segments.append(" ".join(current))
            current, current_words = [], 0
        current.append(sentence)
        current_words += n
    if current:
        segments.append(" ".join(current))
    return segments
