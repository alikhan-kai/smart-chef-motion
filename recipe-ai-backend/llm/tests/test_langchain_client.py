"""Provider plumbing tests: model factory, schema adaptation, error mapping, config.

Builds real LangChain chat models to inspect request payloads, but never sends one.
"""

import json
from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage

from llm.config import LLMSettings
from llm.errors import UpstreamError, UpstreamRateLimitError, UpstreamTimeoutError
from llm.langchain_client import (
    PROMPTS_DIR,
    _type_lists_to_any_of,
    build_chat_model,
    load_json_schema,
    translate_provider_errors,
    with_json_schema,
    with_web_search,
)

RECIPE_SCHEMA_PATH = PROMPTS_DIR / "recipe_schema.json"


def _settings(**overrides: Any) -> LLMSettings:
    values: dict[str, Any] = {"llm_model": "test-model", **overrides}
    return LLMSettings(**values)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LLM_PROVIDER", "LLM_MODEL", "LLM_API_KEY", "OPENAI_API_KEY", "OPENAI_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_build_chat_model_uses_configured_provider_and_timeout() -> None:
    settings = _settings(llm_provider="anthropic", llm_api_key="key-1", llm_timeout_seconds=12)
    with patch("llm.langchain_client.init_chat_model") as init:
        build_chat_model(settings, "some-model")

    init.assert_called_once_with(
        "some-model", model_provider="anthropic", timeout=12, api_key="key-1"
    )


def test_openai_key_is_not_sent_to_other_providers() -> None:
    settings = _settings(llm_provider="anthropic", openai_api_key="sk-openai")
    with patch("llm.langchain_client.init_chat_model") as init:
        build_chat_model(settings, "some-model")

    assert "api_key" not in init.call_args.kwargs


def test_legacy_openai_env_names_still_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-legacy")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-legacy")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "33")
    settings = LLMSettings(_env_file=None)  # type: ignore[call-arg]

    assert settings.llm_provider == "openai"
    assert settings.llm_model == "gpt-legacy"
    assert settings.llm_timeout_seconds == 33
    key = settings.provider_api_key()
    assert key is not None and key.get_secret_value() == "sk-legacy"


def test_openai_gets_schema_file_unchanged_and_strict() -> None:
    settings = _settings(llm_provider="openai", llm_api_key="sk-test")
    model = build_chat_model(settings, "gpt-test")
    runnable = with_json_schema(model, "openai", load_json_schema(RECIPE_SCHEMA_PATH))
    payload = model._get_request_payload(  # type: ignore[attr-defined]
        [HumanMessage(content="борщ")],
        **runnable.first.kwargs,  # type: ignore[attr-defined]
    )
    source = json.loads(RECIPE_SCHEMA_PATH.read_text(encoding="utf-8"))["json_schema"]

    response_format = payload["response_format"]["json_schema"]
    assert response_format["name"] == source["name"]
    assert response_format["strict"] is True
    assert response_format["schema"] == source["schema"]


def test_web_search_tool_uses_provider_format() -> None:
    settings = _settings(llm_provider="openai", llm_api_key="sk-test")
    model = build_chat_model(settings, "gpt-test")

    bound = with_web_search(model, "openai")

    assert bound.kwargs["tools"] == [{"type": "web_search"}]  # type: ignore[attr-defined]


def test_web_search_unknown_provider_is_a_clear_error() -> None:
    with pytest.raises(UpstreamError, match="not configured"):
        with_web_search(object(), "some-new-provider")  # type: ignore[arg-type]


def test_type_lists_become_any_of_for_portable_providers() -> None:
    schema = {
        "type": "object",
        "properties": {
            "note": {"type": ["string", "null"], "description": "d"},
            "level": {"type": ["string", "null"], "enum": ["a", "b", None]},
        },
    }

    converted = _type_lists_to_any_of(schema)

    assert converted["properties"]["note"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "description": "d",
    }
    assert converted["properties"]["level"] == {
        "anyOf": [{"type": "string", "enum": ["a", "b"]}, {"type": "null"}]
    }


def test_schema_files_have_no_type_lists_after_conversion() -> None:
    def has_type_list(node: Any) -> bool:
        if isinstance(node, dict):
            if isinstance(node.get("type"), list):
                return True
            return any(has_type_list(v) for v in node.values())
        if isinstance(node, list):
            return any(has_type_list(v) for v in node)
        return False

    recipe_schema = load_json_schema(RECIPE_SCHEMA_PATH)
    assert has_type_list(recipe_schema)
    assert not has_type_list(_type_lists_to_any_of(recipe_schema))
    assert not has_type_list(
        _type_lists_to_any_of(load_json_schema(PROMPTS_DIR / "revise_schema.json"))
    )


def test_anthropic_accepts_converted_schemas() -> None:
    pytest.importorskip("langchain_anthropic")
    settings = _settings(llm_provider="anthropic", llm_api_key="test")
    model = build_chat_model(settings, "claude-test")
    for name in ("recipe_schema.json", "revise_schema.json"):
        runnable = with_json_schema(model, "anthropic", load_json_schema(PROMPTS_DIR / name))
        payload = model._get_request_payload(  # type: ignore[attr-defined]
            [HumanMessage(content="hi")],
            **runnable.first.kwargs,  # type: ignore[attr-defined]
        )
        assert payload["output_config"]["format"]["type"] == "json_schema"


class RateLimitError(Exception):
    pass


class APITimeoutError(Exception):
    pass


class DeadlineExceeded(Exception):
    pass


class APIStatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (APITimeoutError(), UpstreamTimeoutError),
        (DeadlineExceeded(), UpstreamTimeoutError),
        (TimeoutError(), UpstreamTimeoutError),
        (RateLimitError(), UpstreamRateLimitError),
        (APIStatusError(429), UpstreamRateLimitError),
        (APIStatusError(500), UpstreamError),
    ],
)
def test_provider_errors_map_to_domain_errors(raised: Exception, expected: type[Exception]) -> None:
    with pytest.raises(expected):
        with translate_provider_errors():
            raise raised


def test_unrelated_errors_propagate_unchanged() -> None:
    with pytest.raises(KeyError):
        with translate_provider_errors():
            raise KeyError("bug in our code")
