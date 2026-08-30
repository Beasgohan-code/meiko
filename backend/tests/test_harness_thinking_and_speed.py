"""
Tests for the DeepSeek-harness/Claude-Extended-Thinking-inspired "thinking"
trace and the Groq-inspired tokens/sec run-telemetry readout (Phase 7,
part 2). These stream chain-of-thought reasoning tokens as their own
`thinking` AgentEvent, separate from the final answer, and surface a
tokens_per_second estimate in the `final` event's stats block.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Optional
from unittest.mock import patch

import pytest

from app.harness.agent import MeikoAgent
from app.providers.base import ChatMessage, LLMProvider, ProviderConfig, StreamChunk


class FakeReasoningProvider(LLMProvider):
    """A stub provider that streams a short reasoning trace followed by a
    plain-text answer, mimicking DeepSeek-R1/QwQ-style reasoning models."""

    id = "fake-reasoning"
    display_name = "Fake Reasoning Model"
    requires_key = False

    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        *,
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(reasoning_delta="Let me think step by step... ")
        yield StreamChunk(reasoning_delta="the user wants a simple answer.")
        yield StreamChunk(delta="The answer is 42.")
        yield StreamChunk(delta=" Hope that helps!")
        yield StreamChunk(delta="", finish_reason="stop")

    async def list_models(self) -> list[str]:
        return []



@pytest.fixture
def agent_with_fake_provider():
    with patch("app.harness.agent.build_provider") as mock_build:
        mock_build.return_value = FakeReasoningProvider(ProviderConfig())
        agent = MeikoAgent(provider_id="fake-reasoning", mode_id="chat", enable_fallback=False)
        yield agent


async def _collect(agent: MeikoAgent, message: str = "What is the answer?"):
    events = []
    async for event in agent.run("test-session", "test-user", [], message):
        events.append(event)
    return events


async def test_reasoning_tokens_emitted_as_thinking_events(agent_with_fake_provider):
    events = await _collect(agent_with_fake_provider)
    thinking_events = [e for e in events if e.type == "thinking"]
    assert len(thinking_events) == 2
    combined = "".join(e.data["text"] for e in thinking_events)
    assert "step by step" in combined
    assert "simple answer" in combined


async def test_final_answer_excludes_reasoning_text(agent_with_fake_provider):
    events = await _collect(agent_with_fake_provider)
    final = next(e for e in events if e.type == "final")
    assert final.data["text"] == "The answer is 42. Hope that helps!"
    assert "step by step" not in final.data["text"]


async def test_final_stats_flags_reasoning_and_reports_tokens_per_second(agent_with_fake_provider):
    events = await _collect(agent_with_fake_provider)
    final = next(e for e in events if e.type == "final")
    stats = final.data["stats"]
    assert stats["reasoning"] is True
    # tokens_per_second may be None on an extremely fast in-memory stub run (elapsed ~0), or a
    # small positive float -- either is valid, but the key must always be present.
    assert "tokens_per_second" in stats
    if stats["tokens_per_second"] is not None:
        assert stats["tokens_per_second"] > 0


async def test_no_thinking_events_when_provider_has_no_reasoning():
    class PlainProvider(LLMProvider):
        id = "fake-plain"
        display_name = "Fake Plain Model"
        requires_key = False

        async def chat_stream(self, messages, *, tools=None, temperature=0.7, max_tokens=4096, model=None):
            yield StreamChunk(delta="Just a normal answer.")
            yield StreamChunk(delta="", finish_reason="stop")

        async def list_models(self) -> list[str]:
            return []

    with patch("app.harness.agent.build_provider") as mock_build:
        mock_build.return_value = PlainProvider(ProviderConfig())
        agent = MeikoAgent(provider_id="fake-plain", mode_id="chat", enable_fallback=False)
        events = await _collect(agent)

    assert not [e for e in events if e.type == "thinking"]
    final = next(e for e in events if e.type == "final")
    assert final.data["stats"]["reasoning"] is False
