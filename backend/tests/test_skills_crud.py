"""Tests for the write path added to the skills system: save_skill/delete_skill
and the /api/skills POST/PUT/DELETE routes that let the web/Android 'add a
skill' UI author a real SKILL.md without touching the filesystem directly.

Every test monkeypatches SKILLS_DIR to an isolated temp directory so these
never touch (or get confused by) the real shipped skills under backend/skills/.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_skills_dir(monkeypatch):
    tmp = Path(tempfile.mkdtemp(prefix="meiko_skills_test_"))
    from app.tools import skills as skills_module

    monkeypatch.setattr(skills_module, "SKILLS_DIR", tmp)
    # main.py imports discover_skills/get_skill/save_skill/delete_skill by
    # reference into its own module namespace, so they still resolve
    # SKILLS_DIR from skills_module correctly (they read the module-level
    # global at call time, not at import time) — no extra patching needed.
    yield tmp


def test_slugify_basic():
    from app.tools.skills import slugify

    assert slugify("My Cool Skill!") == "my-cool-skill"
    assert slugify("   ") == "skill"
    assert slugify("already-a-slug") == "already-a-slug"


def test_render_skill_md_roundtrips_through_load():
    from app.tools.skills import Skill, render_skill_md

    text = render_skill_md("Demo Skill", "Does a demo thing", ["demo", "example"], "Step 1. Do the thing.")
    tmp = Path(tempfile.mkdtemp()) / "demo-skill"
    tmp.mkdir()
    (tmp / "SKILL.md").write_text(text, encoding="utf-8")
    loaded = Skill.load(tmp / "SKILL.md")
    assert loaded is not None
    assert loaded.name == "Demo Skill"
    assert loaded.description == "Does a demo thing"
    assert loaded.triggers == ["demo", "example"]
    assert "Step 1" in loaded.body


def test_save_skill_creates_file_and_is_discoverable(isolated_skills_dir):
    from app.tools.skills import discover_skills, save_skill

    save_skill("Weekly Report", "Summarizes the week", ["weekly", "report"], "Do X then Y.")
    ids = {s.id for s in discover_skills()}
    assert "weekly-report" in ids


def test_save_skill_rejects_empty_name():
    from app.tools.skills import SkillValidationError, save_skill

    with pytest.raises(SkillValidationError):
        save_skill("", "desc", [], "body")


def test_save_skill_rejects_empty_body():
    from app.tools.skills import SkillValidationError, save_skill

    with pytest.raises(SkillValidationError):
        save_skill("Name", "desc", [], "   ")


def test_save_skill_with_explicit_id_overwrites(isolated_skills_dir):
    from app.tools.skills import get_skill, save_skill

    save_skill("First Version", "v1", [], "Body v1", skill_id="my-skill")
    save_skill("Second Version", "v2", [], "Body v2", skill_id="my-skill")
    skill = get_skill("my-skill")
    assert skill.name == "Second Version"
    assert skill.body == "Body v2"


def test_delete_skill_removes_directory(isolated_skills_dir):
    from app.tools.skills import delete_skill, get_skill, save_skill

    save_skill("Temp Skill", "temp", [], "Body", skill_id="temp-skill")
    assert get_skill("temp-skill") is not None
    assert delete_skill("temp-skill") is True
    assert get_skill("temp-skill") is None
    assert delete_skill("temp-skill") is False


def test_save_skill_rejects_path_traversal_id():
    from app.tools.skills import SkillValidationError, save_skill

    with pytest.raises(SkillValidationError):
        save_skill("Name", "desc", [], "body", skill_id="../../etc")


def test_delete_skill_rejects_path_traversal_id():
    from app.tools.skills import SkillValidationError, delete_skill

    with pytest.raises(SkillValidationError):
        delete_skill("../../etc")


# ---------------- API routes ----------------
async def test_create_skill_route(app_client, isolated_skills_dir):
    resp = await app_client.post(
        "/api/skills",
        json={"name": "My Skill", "description": "does a thing", "triggers": ["thing"], "body": "Steps..."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "my-skill"

    listing = await app_client.get("/api/skills")
    ids = {s["id"] for s in listing.json()}
    assert "my-skill" in ids


async def test_create_skill_route_rejects_empty_body(app_client, isolated_skills_dir):
    resp = await app_client.post("/api/skills", json={"name": "Bad", "body": "   "})
    assert resp.status_code == 400


async def test_update_skill_route(app_client, isolated_skills_dir):
    await app_client.post("/api/skills", json={"name": "Editable", "body": "v1", "skill_id": "editable"})
    resp = await app_client.put(
        "/api/skills/editable", json={"name": "Editable", "body": "v2", "skill_id": "editable"}
    )
    assert resp.status_code == 200
    detail = await app_client.get("/api/skills/editable")
    assert detail.json()["body"] == "v2"


async def test_update_skill_route_404_for_unknown(app_client, isolated_skills_dir):
    resp = await app_client.put("/api/skills/does-not-exist", json={"name": "X", "body": "y"})
    assert resp.status_code == 404


async def test_delete_skill_route(app_client, isolated_skills_dir):
    await app_client.post("/api/skills", json={"name": "Deleteme", "body": "v1", "skill_id": "deleteme"})
    resp = await app_client.delete("/api/skills/deleteme")
    assert resp.status_code == 200
    resp2 = await app_client.delete("/api/skills/deleteme")
    assert resp2.status_code == 404
