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


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "skill"


class SkillValidationError(ValueError):
    pass


def render_skill_md(name: str, description: str, triggers: list[str], body: str) -> str:
    """Build a SKILL.md file's exact on-disk text from structured fields —
    the inverse of `Skill.load`'s frontmatter parser."""
    triggers_line = "[" + ", ".join(t.strip() for t in triggers if t.strip()) + "]"
    frontmatter = f"---\nname: {name}\ndescription: {description}\ntriggers: {triggers_line}\n---\n\n"
    return frontmatter + body.strip() + "\n"


def save_skill(
    name: str,
    description: str,
    triggers: list[str],
    body: str,
    skill_id: Optional[str] = None,
) -> Skill:
    """Create a new user-authored skill, or overwrite an existing one when
    `skill_id` is given (used for editing). Lets the 'add a skill' UI in
    the web/Android apps write a real SKILL.md without the user touching
    the filesystem — same format the built-in skills ship in, so the
    agent's `list_skills`/`use_skill` tools pick it up identically."""
    if not name.strip():
        raise SkillValidationError("Skill name is required")
    if not body.strip():
        raise SkillValidationError("Skill instructions (body) cannot be empty")

    resolved_id = skill_id or slugify(name)
    if not re.fullmatch(r"[a-z0-9-]+", resolved_id):
        raise SkillValidationError("Skill id may only contain lowercase letters, numbers, and hyphens")

    skill_dir = (SKILLS_DIR / resolved_id).resolve()
    if SKILLS_DIR.resolve() not in skill_dir.parents and skill_dir != SKILLS_DIR.resolve():
        raise SkillValidationError("Invalid skill id")

    skill_dir.mkdir(parents=True, exist_ok=True)
    content = render_skill_md(name, description, triggers, body)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return Skill(id=resolved_id, name=name, description=description, triggers=triggers, body=body.strip())


def delete_skill(skill_id: str) -> bool:
    """Remove a user-authored skill folder. Returns False if it didn't exist."""
    if not re.fullmatch(r"[a-z0-9-]+", skill_id):
        raise SkillValidationError("Invalid skill id")
    skill_dir = (SKILLS_DIR / skill_id).resolve()
    if SKILLS_DIR.resolve() not in skill_dir.parents:
        raise SkillValidationError("Invalid skill id")
    if not skill_dir.exists():
        return False
    import shutil

    shutil.rmtree(skill_dir)
    return True


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
