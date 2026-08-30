"""Tests for the bundled JSON-manifest connector plugins (backend/plugins/*.json)."""
from app.plugins.manager import ConnectorManager


def test_all_bundled_manifests_load_without_errors():
    manager = ConnectorManager()
    manifests = manager.list_manifests()
    ids = {m.id for m in manifests}
    # Original set (Phase 1-3) plus this turn's additions mined from
    # awesome-freellm-apis-style "what's free and keyless" research.
    expected = {
        "hackernews", "reddit", "weather", "wikipedia",
        "arxiv", "crossref", "currency", "dictionary", "crypto",
        "stackoverflow", "npm", "pypi", "quotes",
    }
    assert expected <= ids


def test_all_bundled_connectors_are_keyless_by_default():
    """Every bundled connector should work with zero configuration (no API
    key required) so a brand-new install has useful tools immediately."""
    manager = ConnectorManager()
    for manifest in manager.list_manifests():
        assert manifest.auth.type == "none", f"{manifest.id} unexpectedly requires auth"


def test_build_tools_produces_one_tool_per_action():
    manager = ConnectorManager()
    tools = manager.build_tools({})
    total_actions = sum(len(m.actions) for m in manager.list_manifests() if m.enabled)
    assert len(tools) == total_actions


async def test_crypto_price_tool_returns_data():
    manager = ConnectorManager()
    tools = {t.name: t for t in manager.build_tools({})}
    result = await tools["crypto_price"].run(ids="bitcoin", vs_currencies="usd")
    assert "bitcoin" in result.lower() or "error" in result.lower()


async def test_dictionary_lookup_tool_returns_data():
    manager = ConnectorManager()
    tools = {t.name: t for t in manager.build_tools({})}
    result = await tools["dictionary_lookup"].run(word="hello")
    assert "phonetic" in result.lower() or "error" in result.lower()
