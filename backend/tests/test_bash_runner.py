
from app.tools.bash_runner import BashRunTool


async def test_bash_run_echo(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.core import config as config_module

    config_module.get_settings.cache_clear()

    tool = BashRunTool(lambda: "session-1")
    result = await tool.run(command="echo hello_meiko")
    assert "hello_meiko" in result
    assert "exit_code=0" in result


async def test_bash_run_blocks_dangerous_command(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.core import config as config_module

    config_module.get_settings.cache_clear()

    tool = BashRunTool(lambda: "session-1")
    result = await tool.run(command="rm -rf /")
    assert "blocked" in result.lower()


async def test_bash_run_timeout_clamped(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app.core import config as config_module

    config_module.get_settings.cache_clear()

    tool = BashRunTool(lambda: "session-1")
    result = await tool.run(command="echo hi", timeout_seconds=999)
    assert "hi" in result
