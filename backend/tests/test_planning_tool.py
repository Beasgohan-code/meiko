
from app.tools.planning import PlanState, UpdatePlanTool

async def test_update_plan_tool_stores_tasks_and_reports_progress():
    state = PlanState()
    tool = UpdatePlanTool(state)
    tasks = [
        {"text": "Search the web", "status": "done"},
        {"text": "Summarize findings", "status": "in_progress"},
        {"text": "Write final answer", "status": "pending"},
    ]
    result = await tool.run(tasks=tasks)
    assert state.tasks == tasks
    assert "1/3" in result


async def test_update_plan_tool_schema_has_required_fields():
    tool = UpdatePlanTool(PlanState())
    schema = tool.schema()
    assert schema["function"]["name"] == "update_plan"
    assert "tasks" in schema["function"]["parameters"]["properties"]
