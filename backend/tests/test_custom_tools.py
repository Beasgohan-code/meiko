"""Tests for the 'tools generator' feature (tools/custom_tools.py) — turning
a plain-language tool description into a real, registered Tool without
writing/deploying Python by hand."""
from __future__ import annotations

import pytest


def test_validate_spec_rejects_bad_name():
    from app.tools.custom_tools import CustomToolValidationError, validate_spec

    with pytest.raises(CustomToolValidationError):
        validate_spec("Not-Valid", "desc", {}, "http", http_url_template="https://x.com")


def test_validate_spec_rejects_reserved_name():
    from app.tools.custom_tools import CustomToolValidationError, validate_spec

    with pytest.raises(CustomToolValidationError):
        validate_spec("web_search", "desc", {}, "http", http_url_template="https://x.com")


def test_validate_spec_rejects_missing_description():
    from app.tools.custom_tools import CustomToolValidationError, validate_spec

    with pytest.raises(CustomToolValidationError):
        validate_spec("my_tool", "  ", {}, "http", http_url_template="https://x.com")


def test_validate_spec_http_requires_url_template():
    from app.tools.custom_tools import CustomToolValidationError, validate_spec

    with pytest.raises(CustomToolValidationError):
        validate_spec("my_tool", "desc", {}, "http")


def test_validate_spec_http_rejects_relative_url():
    from app.tools.custom_tools import CustomToolValidationError, validate_spec

    with pytest.raises(CustomToolValidationError):
        validate_spec("my_tool", "desc", {}, "http", http_url_template="/relative/path")


def test_validate_spec_python_requires_body():
    from app.tools.custom_tools import CustomToolValidationError, validate_spec

    with pytest.raises(CustomToolValidationError):
        validate_spec("my_tool", "desc", {}, "python")


def test_validate_spec_ok_http():
    from app.tools.custom_tools import validate_spec

    spec = validate_spec(
        "get_joke", "Fetches a random joke", {}, "http", http_url_template="https://api.example.com/joke"
    )
    assert spec.name == "get_joke"
    assert spec.parameters == {"type": "object", "properties": {}, "required": []}


def test_save_list_get_delete_roundtrip():
    from app.tools.custom_tools import (
        delete_custom_tool,
        get_custom_tool_spec,
        list_custom_tool_specs,
        save_custom_tool,
        validate_spec,
    )

    spec = validate_spec("my_http_tool", "desc", {}, "http", http_url_template="https://api.example.com/{q}")
    save_custom_tool(spec)
    assert get_custom_tool_spec("my_http_tool") is not None
    assert any(s.name == "my_http_tool" for s in list_custom_tool_specs())
    assert delete_custom_tool("my_http_tool") is True
    assert get_custom_tool_spec("my_http_tool") is None
    assert delete_custom_tool("my_http_tool") is False


async def test_generated_python_tool_runs_and_returns_result():
    from app.tools.custom_tools import GeneratedPythonTool, validate_spec

    spec = validate_spec(
        "add_numbers", "Adds two numbers", {"properties": {"a": {"type": "number"}, "b": {"type": "number"}}},
        "python", python_body="result = str(a + b)",
    )
    tool = GeneratedPythonTool(spec, lambda: "custom-tool-test-session")
    result = await tool.run(a=2, b=3)
    assert result.strip() == "5"


async def test_generated_http_tool_calls_url_template(monkeypatch):
    from app.tools.custom_tools import GeneratedHttpTool, validate_spec

    spec = validate_spec(
        "echo_url", "Echoes a URL", {"properties": {"q": {"type": "string"}}}, "http",
        http_url_template="https://httpbin.org/get?q={q}",
    )
    tool = GeneratedHttpTool(spec)
    # Don't depend on real network in CI: just verify URL templating doesn't
    # crash on a missing arg and produces a sane error message instead.
    result = await tool.run()
    assert "missing argument" in result.lower()


def test_build_custom_tools_merges_http_and_python():
    from app.tools.custom_tools import build_custom_tools, save_custom_tool, validate_spec

    save_custom_tool(validate_spec("tool_a", "desc a", {}, "http", http_url_template="https://x.com/a"))
    save_custom_tool(validate_spec("tool_b", "desc b", {}, "python", python_body="result = 'ok'"))
    tools = build_custom_tools(lambda: "session-x")
    names = {t.name for t in tools}
    assert "tool_a" in names and "tool_b" in names


# ---------------- API routes ----------------
async def test_generate_tool_route(app_client):
    resp = await app_client.post(
        "/api/tools/generate",
        json={
            "name": "get_weather_custom",
            "description": "Custom weather lookup",
            "kind": "http",
            "http_url_template": "https://api.example.com/weather?city={city}",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "get_weather_custom"

    listing = await app_client.get("/api/tools/generated")
    assert any(t["name"] == "get_weather_custom" for t in listing.json())


async def test_generate_tool_route_rejects_reserved_name(app_client):
    resp = await app_client.post(
        "/api/tools/generate",
        json={"name": "run_bash", "description": "shadow attempt", "kind": "http", "http_url_template": "https://x.com"},
    )
    assert resp.status_code == 400


async def test_delete_generated_tool_route(app_client):
    await app_client.post(
        "/api/tools/generate",
        json={"name": "temp_tool", "description": "temp", "kind": "python", "python_body": "result='x'"},
    )
    resp = await app_client.delete("/api/tools/generated/temp_tool")
    assert resp.status_code == 200
    resp2 = await app_client.delete("/api/tools/generated/temp_tool")
    assert resp2.status_code == 404
