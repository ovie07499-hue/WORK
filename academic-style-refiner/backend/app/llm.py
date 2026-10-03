"""Thin async wrapper around the Claude API, plus an offline mock for development."""

import logging
import re
from typing import Protocol

import anthropic

from .config import Settings

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    """A request failed in a way the caller should surface to the user."""


class LLM(Protocol):
    async def complete(self, system: str, user: str, effort: str) -> str: ...


class ClaudeLLM:
    def __init__(self, settings: Settings):
        self._settings = settings
        # SDK retries 408/409/429/5xx and connection errors with exponential backoff.
        self._client = anthropic.AsyncAnthropic(max_retries=4, timeout=300.0)

    async def complete(self, system: str, user: str, effort: str) -> str:
        s = self._settings
        kwargs: dict = {}
        if s.enable_fallbacks:
            kwargs = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        try:
            response = await self._client.beta.messages.create(
                model=s.model,
                max_tokens=s.max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                thinking={"type": "adaptive"},
                output_config={"effort": effort},
                **kwargs,
            )
        except anthropic.AuthenticationError as e:
            raise LLMError("The server's Anthropic API key is missing or invalid.") from e
        except anthropic.RateLimitError as e:
            raise LLMError("The language model is rate-limited. Please retry shortly.") from e
        except anthropic.BadRequestError as e:
            log.warning("Bad request to Claude API: %s (request id %s)", e.message, e.request_id)
            raise LLMError("The language model rejected the request.") from e
        except anthropic.APIStatusError as e:
            log.warning("Claude API error %s (request id %s)", e.status_code, e.request_id)
            raise LLMError(f"The language model returned an error ({e.status_code}).") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("Could not reach the language model service.") from e

        if response.stop_reason == "refusal":
            raise LLMError("The language model declined to rewrite this passage.")
        if response.stop_reason == "max_tokens":
            raise LLMError("The rewrite was cut off before it finished.")
        return "".join(block.text for block in response.content if block.type == "text")


class MockLLM:
    """Deterministic stand-in that exercises the full pipeline without network access.

    It performs a handful of phrase substitutions so the UI has visible changes to show.
    """

    _SUBSTITUTIONS = (
        (r"\bIt is important to note that\s+(\w)", lambda m: m.group(1).upper()),
        (r"\bplays a crucial role in\b", "is central to"),
        (r"\bplays a pivotal role in\b", "shapes"),
        (r"\bIn order to\b", "To"),
        (r"\bin order to\b", "to"),
        (r"\bFurthermore,\s*", "Beyond this, "),
        (r"\bMoreover,\s*", "In addition, "),
        (r"\bAdditionally,\s*", "Equally, "),
        (r"\butilize[sd]?\b", "use"),
        (r"\bdelve into\b", "examine"),
        (r"\bshed light on\b", "clarify"),
        (r"\ba large number of\b", "many"),
        (r"\bdue to the fact that\b", "because"),
    )

    async def complete(self, system: str, user: str, effort: str) -> str:
        if "<draft>" in user:
            draft = _between(user, "draft")
            return f"<polished>{draft}</polished>"
        text = _between(user, "paragraph")
        for pattern, repl in self._SUBSTITUTIONS:
            text = re.sub(pattern, repl, text)
        return f"<rewrite>{text}</rewrite>"


def _between(text: str, tag: str) -> str:
    match = re.search(rf"<{tag}>\n?(.*?)\n?</{tag}>", text, re.DOTALL)
    return match.group(1) if match else ""


def make_llm(settings: Settings) -> LLM:
    return MockLLM() if settings.mock_llm else ClaudeLLM(settings)
