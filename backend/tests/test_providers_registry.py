from app.providers.gemini import GeminiProvider
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.providers.registry import build_provider, fallback_chain, list_provider_meta


def test_provider_catalog_has_required_fields():
    metas = list_provider_meta()
    assert len(metas) >= 5
    for m in metas:
        assert m.id
        assert m.display_name
        assert m.default_base_url
        assert m.default_model


def test_build_provider_gemini_returns_gemini_class(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    provider = build_provider("gemini", get_settings(), override_api_key="fake-key")
    assert isinstance(provider, GeminiProvider)


def test_build_provider_nvidia_returns_openai_compatible(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    provider = build_provider("nvidia", get_settings(), override_api_key="fake-key")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert "integrate.api.nvidia.com" in provider.base_url


def test_build_provider_unknown_raises():
    from app.core.config import get_settings

    import pytest

    with pytest.raises(ValueError):
        build_provider("totally-not-a-real-provider", get_settings())


def test_fallback_chain_never_includes_self():
    for provider_id in ("nvidia", "gemini", "groq", "openrouter", "cerebras"):
        chain = fallback_chain(provider_id)
        assert provider_id not in chain


def test_fallback_chain_ollama_is_terminal():
    assert fallback_chain("ollama") == []
