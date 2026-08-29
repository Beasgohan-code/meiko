"""
Meiko Skills — reusable, markdown-defined agent capabilities (inspired by
Anthropic's "Agent Skills" pattern). A Skill is a folder under
`backend/skills/<skill_id>/SKILL.md` with YAML frontmatter:

---
name: pdf-report
description: Generate a polished PDF report from data using reportlab.
triggers: [pdf, report, invoice]
---
<full markdown instructions the agent should follow, code snippets, examples>

Unlike connectors (which call external HTTP APIs), skills are packaged
*procedural knowledge* — step-by-step instructions, code templates, and
domain playbooks the agent loads into context only when relevant, so the
system prompt doesn't get bloated with things unrelated to the current task.

Flow: the harness always exposes `list_skills` (cheap, just names+descriptions)
and `use_skill` (loads the full SKILL.md body for one skill on demand) as
tools, so the model can discover and pull in exactly the playbook it needs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .base import Tool

SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


@dataclass
class Skill:
    id: str
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    body: str = ""

    @staticmethod
    def load(path: Path) -> Optional["Skill"]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        match = _FRONTMATTER_RE.match(text)
        if not match:
            return None
        frontmatter_raw, body = match.group(1), match.group(2)
        meta: dict[str, Any] = {}
        for line in frontmatter_raw.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "triggers":
                # supports either `triggers: [a, b, c]` or a YAML list below
                cleaned = value.strip("[]")
                meta[key] = [t.strip().strip('"\'') for t in cleaned.split(",") if t.strip()]
            else:
                meta[key] = value.strip('"\'')
        return Skill(
            id=path.parent.name,
            name=meta.get("name", path.parent.name),
            description=meta.get("description", ""),
            triggers=meta.get("triggers", []),
            body=body.strip(),
        )


def discover_skills() -> list[Skill]:
    skills: list[Skill] = []
    if not SKILLS_DIR.exists():
        return skills
    for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        skill = Skill.load(skill_file)
        if skill:
            skills.append(skill)
    return skills


def get_skill(skill_id: str) -> Optional[Skill]:
    for s in discover_skills():
        if s.id == skill_id:
            return s
    return None


class SkillsListTool(Tool):
    name = "list_skills"
    description = (
        "List all available Skills — reusable playbooks/procedures Meiko has for specific kinds of tasks "
        "(e.g. generating a PDF report, scaffolding a web app, doing a competitive analysis). Call this "
        "first when a user's request sounds like it matches a specialized workflow, then call use_skill "
        "with the matching id to load full instructions."
    )
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self, **_: Any) -> str:
        skills = discover_skills()
        if not skills:
            return "No skills are currently installed."
        lines = [f"- {s.id}: {s.description} (triggers: {', '.join(s.triggers) or 'none'})" for s in skills]
        return "Available skills:\n" + "\n".join(lines)


class SkillsInvokeTool(Tool):
    name = "use_skill"
    description = (
        "Load the full instructions/playbook for a specific skill by id (see list_skills for available ids). "
        "This returns detailed step-by-step guidance and any code templates you should follow for this task."
    )
    parameters = {
        "type": "object",
        "properties": {"skill_id": {"type": "string", "description": "The id of the skill to load, e.g. 'pdf-report'"}},
        "required": ["skill_id"],
    }

    async def run(self, skill_id: str, **_: Any) -> str:
        skill = get_skill(skill_id)
        if not skill:
            available = ", ".join(s.id for s in discover_skills()) or "(none installed)"
            return f"No skill named '{skill_id}' found. Available: {available}"
        return f"# Skill: {skill.name}\n\n{skill.body}"
