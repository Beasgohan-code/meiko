from app.providers.gemini import GeminiProvider
from app.providers.openai_compatible import OpenAICompatibleProvider
from app.providers.registry import build_provider, fallback_chain, list_provider_meta


def test_provider_catalog_has_required_fields():
    metas = list_provider_meta()
    assert len(metas) >= 5
    for m in metas:
        assert m.id
        assert m.display_name
        # The generic "custom" entry deliberately ships no default base_url
        # / model (the whole point is the user supplies an arbitrary
        # OpenAI-compatible endpoint at runtime) — every other provider
        # must have real defaults.
        if m.id == "custom":
            continue
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


def test_new_free_providers_registered():
    ids = {m.id for m in list_provider_meta()}
    for expected in ("modelscope", "cloudflare", "llm7", "ovhcloud", "sambanova", "cohere"):
        assert expected in ids


def test_build_provider_new_free_providers_return_openai_compatible():
    from app.core.config import get_settings

    get_settings.cache_clear()
    for provider_id in ("modelscope", "llm7", "ovhcloud", "sambanova", "cohere"):
        provider = build_provider(provider_id, get_settings(), override_api_key="fake-key")
        assert isinstance(provider, OpenAICompatibleProvider)


def test_cloudflare_account_id_token_split():
    from app.core.config import get_settings

    get_settings.cache_clear()
    provider = build_provider("cloudflare", get_settings(), override_api_key="myaccount:mytoken")
    assert isinstance(provider, OpenAICompatibleProvider)
    assert "myaccount" in provider.base_url
    assert provider.config.api_key == "mytoken"


# ---------------- Generic "custom" OpenAI-compatible provider (Phase 10) ----------------
def test_custom_provider_registered_in_catalog():
    ids = {m.id for m in list_provider_meta()}
    assert "custom" in ids


def test_build_provider_custom_requires_base_url():
    from app.core.config import get_settings

    import pytest

    get_settings.cache_clear()
    with pytest.raises(ValueError):
        build_provider("custom", get_settings(), override_api_key="fake-key", override_model="some-model")


def test_build_provider_custom_requires_model():
    from app.core.config import get_settings

    import pytest

    get_settings.cache_clear()
    with pytest.raises(ValueError):
        build_provider(
            "custom", get_settings(), override_api_key="fake-key",
            override_base_url="https://my-endpoint.example.com/v1",
        )


def test_build_provider_custom_with_full_override_works():
    from app.core.config import get_settings

    get_settings.cache_clear()
    provider = build_provider(
        "custom",
        get_settings(),
        override_api_key="fake-key",
        override_base_url="https://my-endpoint.example.com/v1",
        override_model="my-custom-model",
    )
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.base_url == "https://my-endpoint.example.com/v1"
    assert provider.config.model == "my-custom-model"
    assert provider.config.api_key == "fake-key"


def test_custom_provider_not_in_any_fallback_chain():
    # "custom" is user-specific/arbitrary and must never be silently tried
    # as a fallback for someone else's request.
    for provider_id in ("nvidia", "gemini", "groq"):
        assert "custom" not in fallback_chain(provider_id)
    assert fallback_chain("custom") == []
