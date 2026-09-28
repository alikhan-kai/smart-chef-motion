"""Generator tests with a mocked OpenAI client. Never calls the real API."""

import json
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx2
import pytest
from openai import APITimeoutError, RateLimitError

from llm.errors import (
    ModelReportedError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
    ValidationFailedError,
)
from llm.recipe_generator import generate_raw_recipe

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
            "action": "Сварить бульон",
            "ingredients_used": ["beef"],
            "time_minutes": 60,
            "passive": False,
            "heat_level": "средний огонь",
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


def _fake_response(output_text: str) -> SimpleNamespace:
    return SimpleNamespace(output_text=output_text)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")


def _patch_responses_create(side_effect: Callable[..., object]) -> AsyncMock:
    mock_create = AsyncMock(side_effect=side_effect)
    return mock_create


@pytest.mark.asyncio
async def test_generate_raw_recipe_success() -> None:
    mock_create = _patch_responses_create(
        lambda **_kwargs: _fake_response(json.dumps(VALID_RECIPE_JSON))
    )
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        result = await generate_raw_recipe("борщ на говяжьем бульоне")

    assert result.title == "Борщ"
    assert result.error is None
    mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_raw_recipe_model_reported_error() -> None:
    mock_create = _patch_responses_create(
        lambda **_kwargs: _fake_response(json.dumps(ERROR_RECIPE_JSON))
    )
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        with pytest.raises(ModelReportedError) as exc_info:
            await generate_raw_recipe("это не рецепт")

    assert exc_info.value.message == "Запрос не про еду"


@pytest.mark.asyncio
async def test_generate_raw_recipe_retries_once_then_succeeds() -> None:
    responses = [
        _fake_response("not valid json"),
        _fake_response(json.dumps(VALID_RECIPE_JSON)),
    ]
    mock_create = AsyncMock(side_effect=responses)
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        result = await generate_raw_recipe("борщ")

    assert result.title == "Борщ"
    assert mock_create.await_count == 2


@pytest.mark.asyncio
async def test_generate_raw_recipe_fails_after_retry() -> None:
    mock_create = AsyncMock(side_effect=[_fake_response("nope"), _fake_response("still nope")])
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        with pytest.raises(ValidationFailedError):
            await generate_raw_recipe("борщ")

    assert mock_create.await_count == 2


@pytest.mark.asyncio
async def test_generate_raw_recipe_timeout_maps_to_domain_error() -> None:
    mock_create = AsyncMock(
        side_effect=APITimeoutError(request=SimpleNamespace())  # type: ignore[arg-type]
    )
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        with pytest.raises(UpstreamTimeoutError):
            await generate_raw_recipe("борщ")


@pytest.mark.asyncio
async def test_generate_raw_recipe_rate_limit_maps_to_domain_error() -> None:
    fake_request = httpx2.Request("POST", "https://api.openai.com/v1/responses")
    fake_response = httpx2.Response(status_code=429, request=fake_request)
    mock_create = AsyncMock(
        side_effect=RateLimitError(message="rate limited", response=fake_response, body=None)
    )
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        with pytest.raises(UpstreamRateLimitError):
            await generate_raw_recipe("борщ")
