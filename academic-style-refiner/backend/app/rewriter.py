"""Two-stage rewriting of a single paragraph, with fidelity checks between stages."""

import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from . import prompts
from .chunker import segment
from .config import Settings
from .llm import LLM
from .protect import Masked, check_fidelity, mask, unmask

log = logging.getLogger(__name__)

StageCallback = Callable[[str], Awaitable[None]]

_MAX_ATTEMPTS = 2


@dataclass
class RefineResult:
    text: str
    warnings: list[str] = field(default_factory=list)


def _extract(raw: str, tag: str) -> str | None:
    match = re.search(rf"<{tag}>(.*?)</{tag}>", raw, re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def _normalise(text: str, keep_lines: bool) -> str:
    if keep_lines:
        return "\n".join(" ".join(line.split()) for line in text.split("\n") if line.strip())
    return " ".join(text.split())


def _mask_with(text: str, spans: dict[str, str]) -> str:
    """Mask `text` using an existing token->span mapping (for earlier rewrites of the same source)."""
    for token, span in sorted(spans.items(), key=lambda kv: -len(kv[1])):
        text = text.replace(span, token)
    return text


class Rewriter:
    def __init__(self, llm: LLM, settings: Settings):
        self._llm = llm
        self._settings = settings

    async def _attempt(
        self,
        system: str,
        user: str,
        tag: str,
        effort: str,
        source: Masked,
        keep_lines: bool,
    ) -> tuple[str | None, str | None]:
        """Run up to _MAX_ATTEMPTS calls; return (validated output, last problem)."""
        problem: str | None = None
        for _ in range(_MAX_ATTEMPTS):
            message = user + (prompts.RETRY_NOTE.format(problem=problem) if problem else "")
            raw = await self._llm.complete(system, message, effort)
            out = _extract(raw, tag)
            if not out:
                problem = f"the answer was not wrapped in <{tag}></{tag}> tags"
                continue
            out = _normalise(out, keep_lines)
            problem = check_fidelity(source, out)
            if problem is None:
                return out, None
        return None, problem

    async def _refine_segment(
        self,
        segment_text: str,
        intensity: prompts.Intensity,
        context_before: str | None,
        context_after: str | None,
        previous: str | None,
        on_stage: StageCallback | None,
    ) -> RefineResult:
        s = self._settings
        keep_lines = "\n" in segment_text
        source = mask(segment_text)
        masked_previous = _mask_with(previous, source.spans) if previous else None

        if on_stage:
            await on_stage("rewrite")
        draft, problem = await self._attempt(
            prompts.PASS1_SYSTEM,
            prompts.build_pass1_message(source.text, intensity, context_before, context_after, masked_previous),
            "rewrite",
            s.pass1_effort,
            source,
            keep_lines,
        )
        if draft is None:
            log.info("Pass 1 failed validation: %s", problem)
            return RefineResult(
                segment_text,
                [f"Kept the original text because the rewrite failed a fidelity check ({problem})."],
            )

        if on_stage:
            await on_stage("polish")
        polished, problem = await self._attempt(
            prompts.PASS2_SYSTEM,
            prompts.build_pass2_message(source.text, draft, context_before, context_after),
            "polished",
            s.pass2_effort,
            source,
            keep_lines,
        )
        if polished is None:
            log.info("Pass 2 failed validation: %s", problem)
            return RefineResult(
                unmask(draft, source.spans),
                [f"Used the first-pass rewrite because the polish failed a fidelity check ({problem})."],
            )
        return RefineResult(unmask(polished, source.spans))

    async def refine(
        self,
        text: str,
        intensity: prompts.Intensity,
        context_before: str | None = None,
        context_after: str | None = None,
        previous: str | None = None,
        on_stage: StageCallback | None = None,
    ) -> RefineResult:
        """Rewrite one paragraph (or list). Long paragraphs are rewritten segment by segment,
        each segment seeing the already-rewritten text before it as context."""
        segments = segment(text, self._settings.max_chunk_words)
        if len(segments) == 1:
            return await self._refine_segment(text, intensity, context_before, context_after, previous, on_stage)

        outputs: list[str] = []
        warnings: list[str] = []
        for i, seg in enumerate(segments):
            before = " ".join(outputs) if outputs else context_before
            after = segments[i + 1] if i + 1 < len(segments) else context_after
            # A previous version can't be aligned to segments, so only the first segment sees it.
            result = await self._refine_segment(seg, intensity, before, after, previous if i == 0 else None, on_stage)
            outputs.append(result.text)
            warnings.extend(result.warnings)
        return RefineResult(" ".join(outputs), warnings)
