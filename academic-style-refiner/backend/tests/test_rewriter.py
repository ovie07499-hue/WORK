import asyncio

from app.config import Settings
from app.rewriter import Rewriter


class ScriptedLLM:
    """Returns queued responses in order and records the prompts it saw."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, system, user, effort):
        self.calls.append(user)
        return self.responses.pop(0)


SRC = "Results improved by 12% (Smith, 2020). It is important to note that costs fell."


def run(llm, **kw):
    return asyncio.run(Rewriter(llm, Settings(mock_llm=True)).refine(SRC, "moderate", **kw))


def test_two_passes_and_unmasking():
    llm = ScriptedLLM(
        [
            "<rewrite>Outcomes rose 12% ⟦P1⟧. Costs fell.</rewrite>",
            "<polished>Outcomes rose by 12% ⟦P1⟧, and costs fell.</polished>",
        ]
    )
    result = run(llm)
    assert result.text == "Outcomes rose by 12% (Smith, 2020), and costs fell."
    assert result.warnings == []
    assert "(Smith, 2020)" not in llm.calls[0]  # citation never sent to the model


def test_retry_then_keep_original_when_pass1_fails():
    llm = ScriptedLLM(["<rewrite>Outcomes rose.</rewrite>", "no tags at all"])
    result = run(llm)
    assert result.text == SRC
    assert "fidelity check" in result.warnings[0]
    assert "rejected because" in llm.calls[1]


def test_falls_back_to_draft_when_polish_fails():
    llm = ScriptedLLM(
        [
            "<rewrite>Outcomes rose 12% ⟦P1⟧. Costs fell.</rewrite>",
            "<polished>Outcomes rose 15% ⟦P1⟧.</polished>",
            "<polished>Outcomes rose.</polished>",
        ]
    )
    result = run(llm)
    assert result.text == "Outcomes rose 12% (Smith, 2020). Costs fell."
    assert "first-pass" in result.warnings[0]


def test_previous_version_is_masked_for_regeneration():
    llm = ScriptedLLM(
        [
            "<rewrite>Costs fell; outcomes rose 12% ⟦P1⟧.</rewrite>",
            "<polished>Costs fell, while outcomes rose 12% ⟦P1⟧.</polished>",
        ]
    )
    run(llm, previous="Outcomes rose 12% (Smith, 2020). Costs fell.")
    assert "<previous_version>\nOutcomes rose 12% ⟦P1⟧. Costs fell." in llm.calls[0]
