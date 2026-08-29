"""
Planning / task-tracking tool — mirrors Claude Code's "TodoWrite" pattern.

Lets Meiko maintain a visible, structured checklist of steps for multi-step
tasks. Every call replaces the current plan and the harness emits a
`plan_update` event so clients (web/mobile/Telegram) can render a live
progress checklist instead of an opaque wall of text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .base import Tool

TaskStatus = Literal["pending", "in_progress", "done"]


@dataclass
class PlanState:
    """Mutable holder so the tool instance and the harness loop share state."""
    tasks: list[dict[str, Any]] = field(default_factory=list)


class UpdatePlanTool(Tool):
    name = "update_plan"
    description = (
        "Create or update your visible step-by-step plan for the current task. Call this at the "
        "start of any multi-step task to lay out your plan, and again whenever a step's status "
        "changes (mark it 'in_progress' when starting it, 'done' when finished). Always pass the "
        "FULL updated list of tasks, not just the changed one. Keep task text short (under 10 words)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "description": "The full, ordered list of tasks for this plan",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Short task description"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
                    },
                    "required": ["text", "status"],
                },
            }
        },
        "required": ["tasks"],
    }

    def __init__(self, state: PlanState):
        self._state = state

    async def run(self, tasks: list[dict[str, Any]], **_: Any) -> str:
        self._state.tasks = tasks
        done = sum(1 for t in tasks if t.get("status") == "done")
        return f"Plan updated: {done}/{len(tasks)} tasks done."
