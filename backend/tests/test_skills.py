from app.tools.skills import SkillsInvokeTool, SkillsListTool, discover_skills


async def test_discover_skills_finds_shipped_skills():
    skills = discover_skills()
    ids = {s.id for s in skills}
    assert "pdf-report" in ids
    assert "webapp-scaffold" in ids
    assert "competitive-research" in ids
    for s in skills:
        assert s.name
        assert s.body


async def test_list_skills_tool_output():
    tool = SkillsListTool()
    result = await tool.run()
    assert "pdf-report" in result


async def test_use_skill_tool_loads_body():
    tool = SkillsInvokeTool()
    result = await tool.run(skill_id="pdf-report")
    assert "reportlab" in result.lower()


async def test_use_skill_tool_unknown_id():
    tool = SkillsInvokeTool()
    result = await tool.run(skill_id="totally-not-real")
    assert "no skill named" in result.lower()
