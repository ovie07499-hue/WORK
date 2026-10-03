"""Shield material that must survive rewriting verbatim, and verify that it did.

Citations, references, URLs, DOIs, inline maths and direct quotations are replaced by
opaque tokens (⟦P1⟧, ⟦P2⟧, ...) before the text is sent to the model, then restored
afterwards. The model never sees - and so cannot alter - the protected content.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

TOKEN_RE = re.compile(r"⟦P(\d+)⟧")

# Order matters: earlier patterns win where matches overlap.
_PROTECTED_PATTERNS = [
    # URLs and DOIs
    r"https?://[^\s<>()\[\]]+[^\s<>()\[\].,;:]",
    r"\bwww\.[^\s<>()\[\]]+[^\s<>()\[\].,;:]",
    r"\b(?:doi:\s*)?10\.\d{4,9}/[^\s<>]+[^\s<>.,;:)]",
    # Inline maths: $...$, \(...\)
    r"\$[^$\n]{1,300}\$",
    r"\\\([^\n]{1,300}?\\\)",
    # Parenthetical citations containing a year: (Smith, 2020), (Lee et al., 2019a; Kim 2021, p. 4)
    r"\((?=[^()]{0,250}\b(?:1[6-9]|20)\d{2}[a-z]?\b)[^()\n]{1,250}\)",
    # Numeric citations: [3], [3, 7], [3-5], [12–14]
    r"\[\d{1,4}(?:\s*[-–—,]\s*\d{1,4})*\]",
    # Direct quotations (straight or curly double quotes)
    r"“[^”\n]{1,400}”",
    r"\"[^\"\n]{1,400}\"",
]
_PROTECTED_RE = re.compile("|".join(f"(?:{p})" for p in _PROTECTED_PATTERNS))

# Numbers as written in the source: 12, 3.5, 1,200, 45%, 0.05
_NUMBER_RE = re.compile(r"(?<![\w⟦])\d+(?:[.,]\d+)*%?")


@dataclass
class Masked:
    text: str
    spans: dict[str, str] = field(default_factory=dict)


def mask(text: str) -> Masked:
    """Replace protected spans with numbered tokens."""
    spans: dict[str, str] = {}

    def _sub(match: re.Match[str]) -> str:
        token = f"⟦P{len(spans) + 1}⟧"
        spans[token] = match.group(0)
        return token

    return Masked(_PROTECTED_RE.sub(_sub, text), spans)


def unmask(text: str, spans: dict[str, str]) -> str:
    return TOKEN_RE.sub(lambda m: spans.get(m.group(0), m.group(0)), text)


def numbers_in(text: str) -> set[str]:
    return {n.rstrip(".,") for n in _NUMBER_RE.findall(text)}


def check_fidelity(masked_source: Masked, masked_output: str) -> str | None:
    """Return a description of the problem if the output lost protected content, else None."""
    expected = Counter(masked_source.spans)
    found = Counter(m.group(0) for m in TOKEN_RE.finditer(masked_output))
    missing = sorted(set(expected) - set(found))
    if missing:
        return f"the protected tokens {', '.join(missing)} were missing"
    duplicated = sorted(t for t, n in found.items() if n > 1)
    if duplicated:
        return f"the protected tokens {', '.join(duplicated)} appeared more than once"
    unknown = sorted(set(found) - set(expected))
    if unknown:
        return f"the output contained tokens that are not in the source: {', '.join(unknown)}"
    lost_numbers = numbers_in(masked_source.text) - numbers_in(masked_output)
    if lost_numbers:
        return f"these numbers from the source were missing or altered: {', '.join(sorted(lost_numbers))}"
    return None
