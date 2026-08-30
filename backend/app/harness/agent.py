"""
Meiko Agent Harness — the autonomous reasoning loop.

This is the "brain loop": Meiko receives a user message, thinks (streams
tokens to the client), optionally calls tools (web search, fetch_url,
calculator, file ops, memory, planning), observes results, and repeats
until it produces a final answer or hits MAX_AGENT_STEPS. Every step is
emitted as a structured event so the web/mobile/telegram clients can render
live "thinking" / "tool call" / "tool result" / "plan" / "answer" states,
much like Claude/DeepSeek agent traces.

Advanced features:
  - Provider fallback chain: if the primary provider/model fails (rate
    limited, retired model, connection error), automatically retries with
    the next configured fallback provider before giving up.
  - Live plan tracking: the `update_plan` tool lets the model maintain a
    visible checklist, surfaced via `plan_update` events.
  - Citation collection: URLs seen in web_search/fetch_url tool results are
    tracked and emitted as a `citations` event alongside the final answer.
  - Usage metrics: step count, tool-call count, elapsed time, per attempt.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from ..core.config import Settings, get_settings
from ..core.logging import get_logger
from ..core.modes import AgentMode, get_mode
from ..plugins.manager import get_connector_manager
from ..providers.base import ChatMessage, ProviderError
from ..providers.registry import build_provider, fallback_chain
from ..tools.base import ToolRegistry
from ..tools.bash_runner import BashRunTool
from ..tools.calculator import CalculatorTool
from ..tools.code_exec import RunPythonTool
from ..tools.documents import MakeDocumentTool, MakeZipTool
from ..tools.fetch_url import FetchUrlTool
from ..tools.files import ListFilesTool, ReadFileTool, WriteFileTool
from ..tools.github_tools import build_github_tools
from ..tools.image_gen import GenerateImageTool
from ..tools.memory_tool import RecallTool, RememberTool
from ..tools.planning import PlanState, UpdatePlanTool
from ..tools.skills import SkillsInvokeTool, SkillsListTool
from ..tools.web_search import WebSearchTool

logger = get_logger("meiko.harness")

MEIKO_SYSTEM_PROMPT = """You are Meiko, a friendly, sharp, and highly capable autonomous AI agent.
You can reason step by step, use tools (web_search, fetch_url, calculator, write_file, read_file,
list_files, run_python, generate_image, make_document, make_zip, remember, recall_memories,
update_plan, and any enabled connector/plugin tools) when they help you give accurate, current, and
useful answers, and you always explain your reasoning clearly and concisely once you're done
investigating.

Guidelines:
- For any task with 3+ distinct steps, call update_plan FIRST to lay out your plan, then keep it
  updated as you complete each step (mark 'in_progress' then 'done'). Skip this for simple one-shot
  questions.
- Use web_search + fetch_url when asked about current events, facts you're unsure of, or anything
  time-sensitive. Don't guess when you can verify. Cite sources with markdown links in your answer.
- Use calculator for precise math instead of computing in your head.
- Use write_file/read_file/list_files/run_python when the user wants you to produce or test code,
  documents, or when working on a multi-file task inside your sandboxed workspace.
- Use generate_image for any visual/image creation requests.
- Use make_document to hand back a clean .md/.py file instead of a huge chat wall, and make_zip to
  package multiple generated files into one downloadable archive when a task produced several files.
- Use remember to save durable facts about the user across sessions, and recall_memories to check
  what you already know about them at the start of a new task if relevant.
- Use any connector/plugin tools (e.g. GitHub, Wikipedia, weather) when they are the best source of truth.
- Use run_bash for shell/CLI needs (git, installing a small package, running scripts, checking tool
  versions) that write_file/run_python don't directly cover. It's sandboxed to your session workspace.
- Call list_skills when a request sounds like it matches a specialized playbook (e.g. PDF reports, web app
  scaffolding, competitive research), then use_skill to load the full instructions before proceeding.
- Be concise but thorough. Use markdown formatting (headings, code blocks, lists) when helpful.
- If a tool fails, explain what happened and try a reasonable alternative instead of giving up silently.
- You have a warm, upbeat, slightly playful personality, but you are always precise and honest.
"""

URL_RE = re.compile(r"https?://[^\s\"'\)>\]]+")


def build_default_registry(
    session_id: str,
    user_id: str,
    connector_secrets: Optional[dict[str, str]] = None,
    plan_state: Optional[PlanState] = None,
) -> ToolRegistry:
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
    registry.register(UpdatePlanTool(plan_state or PlanState()))
    registry.register(BashRunTool(lambda: session_id))
    registry.register(SkillsListTool())
    registry.register(SkillsInvokeTool())

    def _github_token() -> Optional[str]:
        secrets = connector_secrets or {}
        return secrets.get("github") or os.environ.get("GITHUB_TOKEN")

    for tool in build_github_tools(_github_token):
        registry.register(tool)

    # Merge in dynamic connectors/plugins (GitHub, Wikipedia, weather, custom...)
    try:
        manager = get_connector_manager()
        for tool in manager.build_tools(connector_secrets):
            registry.register(tool)
    except Exception as e:  # noqa: BLE001
        logger.warning("connector load failed: %s", e)

    return registry


@dataclass
class AgentEvent:
    type: str  # "token" | "tool_call" | "tool_result" | "step" | "plan_update" | "citations" | "final" | "error" | "provider_switch"
    data: dict[str, Any] = field(default_factory=dict)

    def to_sse(self) -> str:
        return f"data: {json.dumps({'type': self.type, **self.data}, ensure_ascii=False)}\n\n"


@dataclass
class RunStats:
    steps: int = 0
    tool_calls: int = 0
    provider_switches: int = 0
    started_at: float = field(default_factory=time.time)

    def elapsed(self) -> float:
        return round(time.time() - self.started_at, 2)


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
        provider_api_keys: Optional[dict[str, str]] = None,
        enable_fallback: bool = True,
    ):
        self.settings = settings or get_settings()
        self.provider_id = provider_id
        self.model = model
        self.api_key_override = api_key_override
        self.base_url_override = base_url_override
        self.provider_api_keys = provider_api_keys or {}
        self.enable_fallback = enable_fallback

        self.provider = build_provider(
            provider_id,
            self.settings,
            override_api_key=api_key_override,
            override_base_url=base_url_override,
            override_model=model,
        )
        self.persona_extra = persona_extra
        self.mode: AgentMode = get_mode(mode_id)
        # explicit tools_enabled overrides the mode's tool set if provided
        self.tools_enabled = tools_enabled if tools_enabled is not None else self.mode.tools
        self.connector_secrets = connector_secrets or {}

    def _build_fallback_providers(self):
        """Yield (provider_id, provider_instance) for the primary plus any
        configured fallback providers the user has keys for."""
        yield self.provider_id, self.provider
        if not self.enable_fallback:
            return
        for fb_id in fallback_chain(self.provider_id):
            key = self.provider_api_keys.get(fb_id)
            env_configured = fb_id in ("ollama",)  # no key required
            if not key and not env_configured:
                continue
            try:
                yield fb_id, build_provider(fb_id, self.settings, override_api_key=key)
            except Exception:  # noqa: BLE001
                continue

    async def run(
        self,
        session_id: str,
        user_id: str,
        history: list[ChatMessage],
        user_message: str,
        image_urls: Optional[list[str]] = None,
    ) -> AsyncIterator[AgentEvent]:
        stats = RunStats()
        plan_state = PlanState()
        citations: dict[str, str] = {}  # url -> first-seen context (tool name)

        registry = build_default_registry(session_id, user_id, self.connector_secrets, plan_state)
        tool_schemas = registry.schemas(self.tools_enabled)

        system_prompt = MEIKO_SYSTEM_PROMPT + f"\n\n{self.mode.system_suffix}"
        if self.persona_extra:
            system_prompt += f"\n\nAdditional persona instructions from the user:\n{self.persona_extra}"

        messages: list[ChatMessage] = [ChatMessage(role="system", content=system_prompt)]
        messages.extend(history)
        messages.append(ChatMessage(role="user", content=user_message, image_urls=image_urls))

        step = 0
        max_steps = self.mode.max_steps if self.mode.id == "autonomous" else min(self.settings.MAX_AGENT_STEPS, self.mode.max_steps)
        temperature = self.mode.temperature

        providers = list(self._build_fallback_providers())
        active_idx = 0

        while step < max_steps:
            step += 1
            stats.steps = step
            yield AgentEvent(type="step", data={"step": step, "max_steps": max_steps})

            assistant_text = ""
            collected_tool_calls: list[dict[str, Any]] = []
            finish_reason = None
            last_error: Optional[str] = None

            # Try the active provider, then fall back through the chain on failure.
            succeeded = False
            while active_idx < len(providers):
                pid, provider = providers[active_idx]
                try:
                    async for chunk in provider.chat_stream(
                        messages,
                        tools=tool_schemas if tool_schemas else None,
                        temperature=temperature,
                        max_tokens=self.settings.MAX_TOKENS,
                        model=self.model if pid == self.provider_id else None,
                    ):
                        if chunk.delta:
                            assistant_text += chunk.delta
                            yield AgentEvent(type="token", data={"text": chunk.delta})
                        if chunk.tool_calls:
                            collected_tool_calls = chunk.tool_calls
                        if chunk.finish_reason:
                            finish_reason = chunk.finish_reason
                    succeeded = True
                    break
                except ProviderError as e:
                    last_error = str(e)
                    logger.warning("provider %s failed (attempt idx=%s): %s", pid, active_idx, last_error)
                    active_idx += 1
                    stats.provider_switches += 1
                    if active_idx < len(providers):
                        next_pid = providers[active_idx][0]
                        yield AgentEvent(type="provider_switch", data={"from": pid, "to": next_pid, "reason": last_error[:200]})
                        assistant_text = ""  # discard partial output from failed provider
                    continue

            if not succeeded:
                yield AgentEvent(type="error", data={"message": last_error or "All configured providers failed."})
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

                    stats.tool_calls += 1
                    yield AgentEvent(type="tool_call", data={"name": name, "arguments": args, "id": tc.get("id")})

                    tool = registry.get(name)
                    if tool is None:
                        result = f"Error: unknown tool '{name}'"
                    else:
                        try:
                            result = await tool.run(**args)
                        except Exception as e:  # noqa: BLE001
                            result = f"Error running tool '{name}': {e}"
                            logger.warning("tool %s raised: %s", name, e)

                    if name in ("web_search", "fetch_url") or name.startswith(("github_", "wikipedia_", "reddit_", "hackernews_", "get_weather")):
                        for url in URL_RE.findall(result)[:8]:
                            citations.setdefault(url.rstrip(".,)"), name)

                    if name == "update_plan":
                        yield AgentEvent(type="plan_update", data={"tasks": plan_state.tasks})

                    yield AgentEvent(type="tool_result", data={"name": name, "result": result[:4000], "id": tc.get("id")})

                    messages.append(
                        ChatMessage(role="tool", content=result, tool_call_id=tc.get("id"), name=name)
                    )
                # loop again so the model can use tool results
                continue

            # No tool calls -> final answer
            if citations:
                yield AgentEvent(type="citations", data={"sources": [{"url": u, "via": v} for u, v in citations.items()]})
            yield AgentEvent(
                type="final",
                data={
                    "text": assistant_text,
                    "finish_reason": finish_reason,
                    "stats": {
                        "steps": stats.steps,
                        "tool_calls": stats.tool_calls,
                        "elapsed_seconds": stats.elapsed(),
                        "provider_switches": stats.provider_switches,
                        "provider": providers[active_idx][0],
                        "model": self.model if providers[active_idx][0] == self.provider_id else None,
                    },
                },
            )
            return

        if citations:
            yield AgentEvent(type="citations", data={"sources": [{"url": u, "via": v} for u, v in citations.items()]})
        yield AgentEvent(
            type="final",
            data={
                "text": "I reached my maximum reasoning steps for this turn. Here's what I have so far.",
                "finish_reason": "max_steps",
                "stats": {
                    "steps": stats.steps,
                    "tool_calls": stats.tool_calls,
                    "elapsed_seconds": stats.elapsed(),
                    "provider_switches": stats.provider_switches,
                    "provider": providers[active_idx][0] if active_idx < len(providers) else self.provider_id,
                    "model": self.model,
                },
            },
        )
