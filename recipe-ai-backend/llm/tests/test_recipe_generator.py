"""Generator tests with a fake LangChain chat model. Never calls a real API."""

from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage

from llm.errors import (
    ModelReportedError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
    ValidationFailedError,
)
from llm.recipe_generator import generate_raw_recipe
from llm.tests.fake_chat_model import FakeChatModel

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


class RateLimitError(Exception):
    """Named like the OpenAI/Anthropic SDK error; matched by name, not import."""


class APITimeoutError(Exception):
    pass


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("TWO_STEP_MODE", raising=False)


def _use(model: FakeChatModel) -> Any:
    return patch("llm.recipe_generator.build_chat_model", return_value=model)


@pytest.mark.asyncio
async def test_generate_raw_recipe_success() -> None:
    model = FakeChatModel(structured=[VALID_RECIPE_JSON])
    with _use(model):
        result = await generate_raw_recipe("борщ на говяжьем бульоне", allergies="орехи")

    assert result.title == "Борщ"
    assert result.error is None
    model.structured.assert_awaited_once()
    messages = model.structured.call_args.args[0]
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert "Аллергии/ограничения: орехи" in messages[1].content
    assert model.structured_kwargs["method"] == "json_schema"
    assert model.tools is None


@pytest.mark.asyncio
async def test_generate_raw_recipe_passes_schema_file_as_json_schema() -> None:
    model = FakeChatModel(structured=[VALID_RECIPE_JSON])
    with _use(model):
        await generate_raw_recipe("борщ")

    assert model.schema is not None
    assert model.schema["title"] == "recipe"
    assert "steps" in model.schema["properties"]


@pytest.mark.asyncio
async def test_generate_raw_recipe_model_reported_error() -> None:
    model = FakeChatModel(structured=[ERROR_RECIPE_JSON])
    with _use(model):
        with pytest.raises(ModelReportedError) as exc_info:
            await generate_raw_recipe("это не рецепт")

    assert exc_info.value.message == "Запрос не про еду"


@pytest.mark.asyncio
async def test_generate_raw_recipe_retries_once_on_parser_error_then_succeeds() -> None:
    model = FakeChatModel(structured=[OutputParserException("bad json"), VALID_RECIPE_JSON])
    with _use(model):
        result = await generate_raw_recipe("борщ")

    assert result.title == "Борщ"
    assert model.structured.await_count == 2


@pytest.mark.asyncio
async def test_generate_raw_recipe_retries_once_on_schema_mismatch() -> None:
    model = FakeChatModel(structured=[{"title": "без остальных полей"}, VALID_RECIPE_JSON])
    with _use(model):
        result = await generate_raw_recipe("борщ")

    assert result.title == "Борщ"
    assert model.structured.await_count == 2


@pytest.mark.asyncio
async def test_generate_raw_recipe_fails_after_retry() -> None:
    model = FakeChatModel(structured=[OutputParserException("nope"), None])
    with _use(model):
        with pytest.raises(ValidationFailedError):
            await generate_raw_recipe("борщ")

    assert model.structured.await_count == 2


@pytest.mark.asyncio
async def test_generate_raw_recipe_two_step_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWO_STEP_MODE", "true")
    model = FakeChatModel(text=["Борщ: сварите бульон..."], structured=[VALID_RECIPE_JSON])
    with _use(model):
        result = await generate_raw_recipe("борщ")

    assert result.title == "Борщ"
    model.text.assert_awaited_once()
    step2_messages = model.structured.call_args.args[0]
    assert "Борщ: сварите бульон..." in step2_messages[1].content


@pytest.mark.asyncio
async def test_generate_raw_recipe_timeout_maps_to_domain_error() -> None:
    model = FakeChatModel(structured=[APITimeoutError("timed out")])
    with _use(model):
        with pytest.raises(UpstreamTimeoutError):
            await generate_raw_recipe("борщ")


@pytest.mark.asyncio
async def test_generate_raw_recipe_rate_limit_maps_to_domain_error() -> None:
    model = FakeChatModel(structured=[RateLimitError("429")])
    with _use(model):
        with pytest.raises(UpstreamRateLimitError):
            await generate_raw_recipe("борщ")
