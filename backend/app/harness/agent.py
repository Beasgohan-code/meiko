"""
Meiko Agent Harness — the autonomous reasoning loop.

This is the "brain loop": Meiko receives a user message, thinks (streams
tokens to the client), optionally calls tools (web search, fetch_url,
calculator, file ops, memory), observes results, and repeats until it
produces a final answer or hits MAX_AGENT_STEPS. Every step is emitted as
a structured event so the web/mobile/telegram clients can render live
"thinking" / "tool call" / "tool result" / "answer" states, much like
Claude/DeepSeek agent traces.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Optional

from ..core.config import Settings, get_settings
from ..core.modes import AgentMode, get_mode
from ..plugins.manager import get_connector_manager
from ..providers.base import ChatMessage, ProviderError
from ..providers.registry import build_provider
from ..tools.base import ToolRegistry
from ..tools.calculator import CalculatorTool
from ..tools.code_exec import RunPythonTool
from ..tools.documents import MakeDocumentTool, MakeZipTool
from ..tools.fetch_url import FetchUrlTool
from ..tools.files import ListFilesTool, ReadFileTool, WriteFileTool
from ..tools.image_gen import GenerateImageTool
from ..tools.memory_tool import RecallTool, RememberTool
from ..tools.web_search import WebSearchTool

MEIKO_SYSTEM_PROMPT = """You are Meiko, a friendly, sharp, and highly capable autonomous AI agent.
You can reason step by step, use tools (web_search, fetch_url, calculator, write_file, read_file,
list_files, run_python, generate_image, make_document, make_zip, remember, recall_memories, and any
enabled connector/plugin tools) when they help you give accurate, current, and useful answers, and
you always explain your reasoning clearly and concisely once you're done investigating.

Guidelines:
- Use web_search + fetch_url when asked about current events, facts you're unsure of, or anything
  time-sensitive. Don't guess when you can verify.
- Use calculator for precise math instead of computing in your head.
- Use write_file/read_file/list_files/run_python when the user wants you to produce or test code,
  documents, or when working on a multi-file task inside your sandboxed workspace.
- Use generate_image for any visual/image creation requests.
- Use make_document to hand back a clean .md/.py file instead of a huge chat wall, and make_zip to
  package multiple generated files into one downloadable archive when a task produced several files.
- Use remember to save durable facts about the user across sessions, and recall_memories to check
  what you already know about them at the start of a new task if relevant.
- Use any connector/plugin tools (e.g. GitHub, Wikipedia, weather) when they are the best source of truth.
- Be concise but thorough. Use markdown formatting (headings, code blocks, lists) when helpful.
- If a tool fails, explain what happened and try a reasonable alternative instead of giving up silently.
- You have a warm, upbeat, slightly playful personality, but you are always precise and honest.
"""


def build_default_registry(session_id: str, user_id: str, connector_secrets: Optional[dict[str, str]] = None) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(WebSearchTool())
    registry.register(FetchUrlTool())
    registry.register(CalculatorTool())
    registry.register(WriteFileTool(lambda: session_id))
    registry.register(ReadFileTool(lambda: session_id))
    registry.register(ListFilesTool(lambda: session_id))
    registry.register(RunPythonTool(lambda: session_id))
    registry.register(GenerateImageTool(lambda: session_id))
    registry.register(MakeDocumentTool(lambda: session_id))
    registry.register(MakeZipTool(lambda: session_id))
    registry.register(RememberTool(lambda: user_id))
    registry.register(RecallTool(lambda: user_id))

    # Merge in dynamic connectors/plugins (GitHub, Wikipedia, weather, custom...)
    try:
        manager = get_connector_manager()
        for tool in manager.build_tools(connector_secrets):
            registry.register(tool)
    except Exception as e:  # noqa: BLE001
        print(f"[MeikoAgent] connector load failed: {e}")

    return registry


@dataclass
class AgentEvent:
    type: str  # "token" | "tool_call" | "tool_result" | "step" | "final" | "error"
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        return f"data: {json.dumps({'type': self.type, **self.data}, ensure_ascii=False)}\n\n"


class MeikoAgent:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        provider_id: str = "nvidia",
        model: Optional[str] = None,
        api_key_override: Optional[str] = None,
        base_url_override: Optional[str] = None,
        persona_extra: Optional[str] = None,
        tools_enabled: Optional[set[str]] = None,
        mode_id: str = "autonomous",
        connector_secrets: Optional[dict[str, str]] = None,
    ):
        self.settings = settings or get_settings()
        self.provider = build_provider(
            provider_id,
            self.settings,
            override_api_key=api_key_override,
            override_base_url=base_url_override,
            override_model=model,
        )
        self.model = model
        self.persona_extra = persona_extra
        self.mode: AgentMode = get_mode(mode_id)
        # explicit tools_enabled overrides the mode's tool set if provided
        self.tools_enabled = tools_enabled if tools_enabled is not None else self.mode.tools
        self.connector_secrets = connector_secrets or {}

    async def run(
        self,
        session_id: str,
        user_id: str,
        history: list[ChatMessage],
        user_message: str,
        image_urls: Optional[list[str]] = None,
    ) -> AsyncIterator[AgentEvent]:
        registry = build_default_registry(session_id, user_id, self.connector_secrets)
        tool_schemas = registry.schemas(self.tools_enabled)

        system_prompt = MEIKO_SYSTEM_PROMPT + f"\n\n{self.mode.system_suffix}"
        if self.persona_extra:
            system_prompt += f"\n\nAdditional persona instructions from the user:\n{self.persona_extra}"

        messages: list[ChatMessage] = [ChatMessage(role="system", content=system_prompt)]
        messages.extend(history)
        messages.append(ChatMessage(role="user", content=user_message, image_urls=image_urls))

        step = 0
        max_steps = min(self.settings.MAX_AGENT_STEPS, self.mode.max_steps) if self.mode.id != "autonomous" else self.mode.max_steps
        temperature = self.mode.temperature

        while step < max_steps:
            step += 1
            yield AgentEvent(type="step", data={"step": step})

            assistant_text = ""
            collected_tool_calls: list[dict[str, Any]] = []
            finish_reason = None

            try:
                async for chunk in self.provider.chat_stream(
                    messages,
                    tools=tool_schemas if tool_schemas else None,
                    temperature=temperature,
                    max_tokens=self.settings.MAX_TOKENS,
                    model=self.model,
                ):
                    if chunk.delta:
                        assistant_text += chunk.delta
                        yield AgentEvent(type="token", data={"text": chunk.delta})
                    if chunk.tool_calls:
                        collected_tool_calls = chunk.tool_calls
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason
            except ProviderError as e:
                yield AgentEvent(type="error", data={"message": str(e)})
                return

            if collected_tool_calls:
                messages.append(ChatMessage(role="assistant", content=assistant_text, tool_calls=collected_tool_calls))

                for tc in collected_tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}") or "{}"
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}

                    yield AgentEvent(type="tool_call", data={"name": name, "arguments": args, "id": tc.get("id")})

                    tool = registry.get(name)
                    if tool is None:
                        result = f"Error: unknown tool '{name}'"
                    else:
                        try:
                            result = await tool.run(**args)
                        except Exception as e:  # noqa: BLE001
                            result = f"Error running tool '{name}': {e}"

                    yield AgentEvent(type="tool_result", data={"name": name, "result": result[:4000], "id": tc.get("id")})

                    messages.append(
                        ChatMessage(role="tool", content=result, tool_call_id=tc.get("id"), name=name)
                    )
                # loop again so the model can use tool results
                continue

            # No tool calls -> final answer
            yield AgentEvent(type="final", data={"text": assistant_text, "finish_reason": finish_reason})
            return

        yield AgentEvent(type="final", data={"text": "I reached my maximum reasoning steps for this turn. Here's what I have so far.", "finish_reason": "max_steps"})
