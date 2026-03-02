"""Layer 6b: Settings loading tests."""

import os

from src.config.settings import Settings


def test_loads_from_env():
    """All fields are loaded from the current .env."""
    s = Settings()
    assert s.vllm_base_url
    assert s.vllm_model_name
    assert s.vllm_api_key
    assert isinstance(s.app_port, int)
    assert isinstance(s.chat_history_max_tokens, int)


def test_bool_coercion():
    s = Settings()
    assert isinstance(s.langfuse_enabled, bool)
    assert isinstance(s.chat_history_enabled, bool)


def test_int_coercion():
    s = Settings()
    assert isinstance(s.app_port, int)
    assert isinstance(s.langfuse_prompt_cache_ttl, int)


def test_extra_ignored():
    """Extra env vars don't raise errors (extra='ignore')."""
    os.environ["SOME_RANDOM_VAR_FOR_TEST"] = "hello"
    try:
        s = Settings()
        assert s.vllm_base_url  # loads fine
    finally:
        os.environ.pop("SOME_RANDOM_VAR_FOR_TEST", None)
