"""Tests for the arena.ai/menus.ai-style live command runner
(core/run_console.py) and its /api/console/* HTTP surface + WebSocket."""
from __future__ import annotations

import asyncio

import pytest


async def test_run_manager_bash_basic_output():
    from app.core.run_console import get_run_manager

    manager = get_run_manager()
    run = await manager.start("test-session-1", "echo hello-console", kind="bash", timeout_seconds=5)
    assert run.status == "running" or run.status == "exited"

    # give the pump loop a moment to finish
    result = await manager.get_output(run.id, wait_for="exit", wait_timeout=5)
    assert result["status"] == "exited"
    assert result["exit_code"] == 0
    assert "hello-console" in result["output"]


async def test_run_manager_python_kind():
    from app.core.run_console import get_run_manager

    manager = get_run_manager()
    run = await manager.start("test-session-2", "print('py-console-ok')", kind="python", timeout_seconds=5)
    result = await manager.get_output(run.id, wait_for="exit", wait_timeout=5)
    assert result["exit_code"] == 0
    assert "py-console-ok" in result["output"]


async def test_run_manager_blocks_dangerous_command():
    from app.core.run_console import get_run_manager

    manager = get_run_manager()
    with pytest.raises(PermissionError):
        await manager.start("test-session-3", "rm -rf /", kind="bash")


async def test_run_manager_incremental_cursor():
    from app.core.run_console import get_run_manager

    manager = get_run_manager()
    run = await manager.start("test-session-4", "echo one; sleep 0.2; echo two", kind="bash", timeout_seconds=5)
    await manager.get_output(run.id, wait_for="exit", wait_timeout=5)
    first, cursor1 = run.slice_since(0)
    assert "one" in first and "two" in first
    second, cursor2 = run.slice_since(cursor1)
    assert second == ""  # nothing new after consuming everything
    assert cursor2 == cursor1


async def test_run_manager_stop_kills_running_process():
    from app.core.run_console import get_run_manager

    manager = get_run_manager()
    run = await manager.start("test-session-5", "sleep 30", kind="bash", timeout_seconds=60)
    await asyncio.sleep(0.2)
    stopped = await manager.stop(run.id)
    assert stopped is True
    await asyncio.sleep(0.2)
    assert run.status in ("killed",)


async def test_run_manager_timeout():
    from app.core.run_console import get_run_manager

    manager = get_run_manager()
    run = await manager.start("test-session-6", "sleep 5", kind="bash", timeout_seconds=1)
    result = await manager.get_output(run.id, wait_for="exit", wait_timeout=5)
    assert result["status"] == "timeout"


async def test_run_manager_unknown_run_id_raises():
    from app.core.run_console import get_run_manager

    manager = get_run_manager()
    with pytest.raises(KeyError):
        await manager.get_output("does-not-exist")


# ---------------- API routes ----------------
async def test_console_run_and_poll_output(app_client):
    resp = await app_client.post(
        "/api/console/run", json={"session_id": "api-test-1", "command": "echo api-hello", "kind": "bash"}
    )
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    poll = await app_client.get(f"/api/console/{run_id}/output", params={"wait_for": "exit", "wait_timeout": 5})
    assert poll.status_code == 200
    data = poll.json()
    assert data["status"] == "exited"
    assert "api-hello" in data["output"]


async def test_console_run_rejects_dangerous_command(app_client):
    resp = await app_client.post(
        "/api/console/run", json={"session_id": "api-test-2", "command": "rm -rf /", "kind": "bash"}
    )
    assert resp.status_code == 400


async def test_console_list_runs_for_session(app_client):
    await app_client.post("/api/console/run", json={"session_id": "api-test-3", "command": "echo x", "kind": "bash"})
    resp = await app_client.get("/api/console/api-test-3/runs")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_console_output_404_for_unknown_run(app_client):
    resp = await app_client.get("/api/console/not-a-real-run/output")
    assert resp.status_code == 404


async def test_console_stop_running_run(app_client):
    start = await app_client.post(
        "/api/console/run", json={"session_id": "api-test-4", "command": "sleep 30", "kind": "bash", "timeout_seconds": 60}
    )
    run_id = start.json()["run_id"]
    await asyncio.sleep(0.2)
    stop = await app_client.post(f"/api/console/{run_id}/stop")
    assert stop.status_code == 200


async def test_console_stop_404_for_finished_or_unknown_run(app_client):
    resp = await app_client.post("/api/console/not-a-real-run/stop")
    assert resp.status_code == 404
