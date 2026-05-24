"""Unit tests for WBSGenerator's parser robustness fixes."""
import pytest
from dataclasses import dataclass

from app.services.wbs_generator import (
    WBSGenerator,
    WBSRequest,
    _coerce_int_list,
)
from app.services.ai_copilot import ChatResult


@dataclass
class _StubCopilot:
    """Returns a canned chat response so the generator can be tested
    without any LLM."""

    text: str
    provider: str = "openrouter"
    model: str = "stub-model"

    async def chat(self, messages, **_kwargs):
        return ChatResult(text=self.text, provider=self.provider, model=self.model)


def test_coerce_int_list_handles_strings_and_floats():
    # The bug: previous filter `isinstance(d, int)` dropped these silently.
    assert _coerce_int_list(["0", "1", 2]) == [0, 1, 2]
    assert _coerce_int_list([1.0, 2.0]) == [1, 2]
    assert _coerce_int_list(["x", None, 3]) == [3]
    assert _coerce_int_list(None) == []
    assert _coerce_int_list("not-a-list") == []


@pytest.mark.asyncio
async def test_wbs_handles_null_milestones():
    """Previously crashed with TypeError on `for m in None`."""
    response = '{"tasks": [{"title": "A"}], "milestones": null}'
    gen = WBSGenerator(_StubCopilot(text=response))
    result = await gen.generate(WBSRequest(goal="x"))
    assert [t.title for t in result.tasks] == ["A"]
    assert result.milestones == []
    assert result.provider == "openrouter"


@pytest.mark.asyncio
async def test_wbs_skips_whitespace_only_titles():
    """Previously persisted Task(title='') after the strip step."""
    response = (
        '{"tasks": ['
        '{"title": "Real"},'
        '{"title": "   "},'
        '{"title": ""}'
        ']}'
    )
    gen = WBSGenerator(_StubCopilot(text=response))
    result = await gen.generate(WBSRequest(goal="x"))
    assert [t.title for t in result.tasks] == ["Real"]


@pytest.mark.asyncio
async def test_wbs_persists_stringified_depends_on():
    """LLMs that emit string indices used to lose the dependency graph."""
    response = (
        '{"tasks": ['
        '{"title": "A"},'
        '{"title": "B", "depends_on": ["0"]},'
        '{"title": "C", "depends_on": [0, "1"]}'
        ']}'
    )
    gen = WBSGenerator(_StubCopilot(text=response))
    result = await gen.generate(WBSRequest(goal="x"))
    assert result.tasks[1].depends_on == [0]
    assert result.tasks[2].depends_on == [0, 1]


@pytest.mark.asyncio
async def test_wbs_drops_out_of_range_and_self_referential_deps():
    response = (
        '{"tasks": ['
        '{"title": "A", "depends_on": [5]},'    # out of bounds
        '{"title": "B", "depends_on": [1]},'    # self-reference
        '{"title": "C", "depends_on": [0]}'     # valid
        ']}'
    )
    gen = WBSGenerator(_StubCopilot(text=response))
    result = await gen.generate(WBSRequest(goal="x"))
    assert result.tasks[0].depends_on == []
    assert result.tasks[1].depends_on == []
    assert result.tasks[2].depends_on == [0]


@pytest.mark.asyncio
async def test_wbs_fallback_reports_fallback_model_not_llm_model():
    """When the LLM response can't be parsed and we fall back to the static
    template, the response must not claim the cloud LLM produced it."""
    gen = WBSGenerator(_StubCopilot(text="not-json", model="claude-opus-4.7"))
    result = await gen.generate(WBSRequest(goal="x"))
    assert result.provider == "fallback-template"
    assert result.model == "fallback-v1"
    assert len(result.tasks) >= 1  # came from FALLBACK_WBS


@pytest.mark.asyncio
async def test_wbs_clamps_milestone_offset_to_deadline():
    response = (
        '{"tasks": [{"title": "A"}],'
        ' "milestones": [{"name": "M", "target_offset_days": 999}]}'
    )
    gen = WBSGenerator(_StubCopilot(text=response))
    result = await gen.generate(WBSRequest(goal="x", deadline_days=14))
    assert result.milestones[0].target_offset_days == 14
