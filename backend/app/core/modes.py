"""
Meiko Agent Modes — mirrors the "modes" concept in Claude/DeepSeek-style
harnesses (e.g. Claude's "Extended Thinking" / DeepSeek's "Deep Think" /
tool-restricted vs. full-autonomy modes).

Each mode tunes: which tools are enabled, how many reasoning steps are
allowed, extra system-prompt guidance, and default temperature.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentMode:
    id: str
    name: str
    description: str
    icon: str
    tools: Optional[set[str]]  # None = all tools enabled
    max_steps: int
    temperature: float
    system_suffix: str


AGENT_MODES: dict[str, AgentMode] = {
    "chat": AgentMode(
        id="chat",
        name="Chat",
        description="Fast conversational assistant. Tools are off for quick, low-latency replies.",
        icon="message-circle",
        tools=set(),
        max_steps=1,
        temperature=0.8,
        system_suffix="Mode: CHAT. Answer directly and conversationally. Do not use tools unless explicitly necessary.",
    ),
    "research": AgentMode(
        id="research",
        name="Research",
        description="Deep web research mode: searches, reads sources, and synthesizes a cited answer.",
        icon="search",
        tools={"web_search", "fetch_url", "calculator", "remember", "recall_memories", "update_plan"},
        max_steps=10,
        temperature=0.4,
        system_suffix=(
            "Mode: RESEARCH. Proactively use web_search and fetch_url to verify facts and gather "
            "up-to-date information from multiple sources before answering. Cite sources with URLs "
            "in your final answer using markdown links."
        ),
    ),
    "code": AgentMode(
        id="code",
        name="Code",
        description="Software engineering mode: writes, runs, and debugs code in a sandboxed workspace.",
        icon="code",
        tools={"write_file", "read_file", "list_files", "run_python", "calculator", "web_search", "fetch_url", "make_zip", "remember", "recall_memories", "update_plan"},
        max_steps=14,
        temperature=0.2,
        system_suffix=(
            "Mode: CODE. You are acting as a coding agent, similar to Claude Code / DeepSeek Coder harnesses. "
            "Write clean, correct, well-commented code. Use write_file to persist files into the sandboxed "
            "workspace, run_python to execute and test Python code, and list_files/read_file to inspect the "
            "current project. When you finish a multi-file task, mention that the user can export the workspace "
            "as a zip with make_zip."
        ),
    ),
    "autonomous": AgentMode(
        id="autonomous",
        name="Autonomous",
        description="Full autonomy: plans multi-step tasks and uses every available tool to complete them.",
        icon="cpu",
        tools=None,
        max_steps=20,
        temperature=0.5,
        system_suffix=(
            "Mode: AUTONOMOUS. You may plan and execute multi-step tasks independently using any available "
            "tool (web_search, fetch_url, calculator, write_file/read_file/list_files, run_python, generate_image, "
            "make_document, make_zip, remember/recall_memories, and any connected plugins/connectors). Think in "
            "short internal steps, use tools proactively, and only stop once the task is genuinely complete."
        ),
    ),
    "creative": AgentMode(
        id="creative",
        name="Creative",
        description="Image generation & creative writing mode.",
        icon="image",
        tools={"generate_image", "make_document", "remember", "recall_memories", "update_plan"},
        max_steps=6,
        temperature=0.95,
        system_suffix=(
            "Mode: CREATIVE. Focus on imaginative, high-quality creative output. Use generate_image for any "
            "visual requests, and make_document if the user wants a formatted document of the result."
        ),
    ),
}


def get_mode(mode_id: str) -> AgentMode:
    return AGENT_MODES.get(mode_id, AGENT_MODES["autonomous"])


def list_modes() -> list[AgentMode]:
    return list(AGENT_MODES.values())
