"""Generator tests with a mocked LangChain ChatOpenAI. Never calls the real API."""

import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import APITimeoutError, RateLimitError

from llm.errors import (
    ModelReportedError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
    ValidationFailedError,
)
from llm.langchain_client import load_response_format
from llm.recipe_generator import SCHEMA_PATH, generate_raw_recipe

VALID_RECIPE_JSON = {
    "error": None,
    "title": "Борщ",
    "servings": 4,
    "total_time_minutes": 90,
    "equipment": ["кастрюля"],
    "source_urls": ["https://example.com"],
    "notes": None,
    "ingredients": [
        {"id": "beef", "name": "говядина", "amount": 500, "unit": "г", "form": None},
    ],
    "steps": [
        {
            "step_number": 1,
            "header": None,
            "action": "Сварить бульон",
            "ingredients_used": ["beef"],
            "time_minutes": 60,
            "passive": False,
            "heat_level": "средний",
            "place": "кастрюля",
            "salt": True,
            "fat": None,
            "final_action": None,
        }
    ],
}

ERROR_RECIPE_JSON = {
    "error": "Запрос не про еду",
    "title": None,
    "servings": None,
    "total_time_minutes": None,
    "equipment": None,
    "source_urls": None,
    "notes": None,
    "ingredients": None,
    "steps": None,
}


def _reply(text: str) -> AIMessage:
    # Responses API replies arrive as a list of content blocks.
    return AIMessage(content=[{"type": "text", "text": text}])


def _patch_ainvoke(mock: AsyncMock) -> Any:
    return patch.object(ChatOpenAI, "ainvoke", mock)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.delenv("TWO_STEP_MODE", raising=False)


@pytest.mark.asyncio
async def test_generate_raw_recipe_success() -> None:
    mock = AsyncMock(return_value=_reply(json.dumps(VALID_RECIPE_JSON)))
    with _patch_ainvoke(mock):
        result = await generate_raw_recipe("борщ на говяжьем бульоне", allergies="орехи")

    assert result.title == "Борщ"
    assert result.error is None
    mock.assert_awaited_once()
    messages, *_ = mock.call_args.args
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert "Аллергии/ограничения: орехи" in messages[1].content
    assert mock.call_args.kwargs["response_format"] == load_response_format(SCHEMA_PATH)


@pytest.mark.asyncio
async def test_generate_raw_recipe_accepts_plain_string_content() -> None:
    mock = AsyncMock(return_value=AIMessage(content=json.dumps(VALID_RECIPE_JSON)))
    with _patch_ainvoke(mock):
        result = await generate_raw_recipe("борщ")

    assert result.title == "Борщ"


@pytest.mark.asyncio
async def test_generate_raw_recipe_model_reported_error() -> None:
    mock = AsyncMock(return_value=_reply(json.dumps(ERROR_RECIPE_JSON)))
    with _patch_ainvoke(mock):
        with pytest.raises(ModelReportedError) as exc_info:
            await generate_raw_recipe("это не рецепт")

    assert exc_info.value.message == "Запрос не про еду"


@pytest.mark.asyncio
async def test_generate_raw_recipe_retries_once_then_succeeds() -> None:
    mock = AsyncMock(side_effect=[_reply("not valid json"), _reply(json.dumps(VALID_RECIPE_JSON))])
    with _patch_ainvoke(mock):
        result = await generate_raw_recipe("борщ")

    assert result.title == "Борщ"
    assert mock.await_count == 2


@pytest.mark.asyncio
async def test_generate_raw_recipe_fails_after_retry() -> None:
    mock = AsyncMock(side_effect=[_reply("nope"), _reply("still nope")])
    with _patch_ainvoke(mock):
        with pytest.raises(ValidationFailedError):
            await generate_raw_recipe("борщ")

    assert mock.await_count == 2


@pytest.mark.asyncio
async def test_generate_raw_recipe_two_step_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWO_STEP_MODE", "true")
    mock = AsyncMock(
        side_effect=[_reply("Борщ: сварите бульон..."), _reply(json.dumps(VALID_RECIPE_JSON))]
    )
    with _patch_ainvoke(mock):
        result = await generate_raw_recipe("борщ")

    assert result.title == "Борщ"
    step1, step2 = mock.call_args_list
    assert "response_format" not in step1.kwargs
    assert "response_format" in step2.kwargs
    assert "tools" not in step2.kwargs
    assert "Борщ: сварите бульон..." in step2.args[0][1].content


@pytest.mark.asyncio
async def test_generate_raw_recipe_timeout_maps_to_domain_error() -> None:
    mock = AsyncMock(
        side_effect=APITimeoutError(request=SimpleNamespace())  # type: ignore[arg-type]
    )
    with _patch_ainvoke(mock):
        with pytest.raises(UpstreamTimeoutError):
            await generate_raw_recipe("борщ")


@pytest.mark.asyncio
async def test_generate_raw_recipe_rate_limit_maps_to_domain_error() -> None:
    fake_request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    fake_response = httpx2.Response(status_code=429, request=fake_request)
    mock = AsyncMock(
        side_effect=RateLimitError(message="rate limited", response=fake_response, body=None)
    )
    with _patch_ainvoke(mock):
        with pytest.raises(UpstreamRateLimitError):
            await generate_raw_recipe("борщ")


def test_schema_reaches_responses_api_as_strict_text_format() -> None:
    """langchain-openai must turn the schema file into a strict Responses API text.format."""
    model = ChatOpenAI(model="gpt-test", api_key="sk-test", use_responses_api=True)  # type: ignore[arg-type]
    payload = model._get_request_payload(
        [HumanMessage(content="борщ")],
        response_format=load_response_format(SCHEMA_PATH),
        tools=[{"type": "web_search"}],
    )
    source = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["json_schema"]

    assert payload["text"]["format"] == {
        "type": "json_schema",
        "name": source["name"],
        "strict": True,
        "schema": source["schema"],
    }
    assert payload["tools"] == [{"type": "web_search"}]
