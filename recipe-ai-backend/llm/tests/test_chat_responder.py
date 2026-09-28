"""respond_to_message() tests with a mocked OpenAI client. Never calls the real API."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from openai import APITimeoutError

from llm.chat_responder import respond_to_message
from llm.chat_schemas import HistoryMessage
from llm.errors import UpstreamTimeoutError, ValidationFailedError
from llm.schemas import RawIngredient, RawRecipe, RawStep

CURRENT_RECIPE = RawRecipe(
    error=None,
    title="Омлет",
    servings=2,
    total_time_minutes=None,
    equipment=["сковорода"],
    source_urls=[],
    notes=None,
    ingredients=[
        RawIngredient(id="eggs", name="яйца", amount=3, unit="шт", form=None),
        RawIngredient(id="salt1", name="соль", amount=None, unit="по вкусу", form=None),
    ],
    steps=[
        RawStep(
            step_number=1,
            action="Разбейте яйца в миску",
            ingredients_used=["eggs"],
            time_minutes=None,
            passive=False,
            heat_level=None,
            place="миска",
            salt=False,
            fat=None,
            final_action=None,
        ),
        RawStep(
            step_number=2,
            action="Посолите и взбейте",
            ingredients_used=["salt1"],
            time_minutes=1,
            passive=False,
            heat_level=None,
            place="миска",
            salt=True,
            fat=None,
            final_action=None,
        ),
    ],
)

ANSWER_JSON = {
    "intent": "answer",
    "answer_text": "Соль можно не добавлять, если следите за натрием.",
    "operations": None,
}

REVISE_JSON = {
    "intent": "revise",
    "answer_text": "Удалил соль из рецепта.",
    "operations": [
        {
            "op": "update_step",
            "step_number": 2,
            "fields": [
                {"field": "ingredients_used", "value": []},
                {"field": "salt", "value": False},
            ],
        },
        {"op": "remove_ingredient", "ingredient_id": "salt1"},
    ],
}


def _fake_response(output_text: str) -> SimpleNamespace:
    return SimpleNamespace(output_text=output_text)


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")


@pytest.mark.asyncio
async def test_respond_to_message_answer_case() -> None:
    mock_create = AsyncMock(return_value=_fake_response(json.dumps(ANSWER_JSON)))
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        result = await respond_to_message(CURRENT_RECIPE, [], "нужно ли солить?")

    assert result.intent == "answer"
    assert result.operations is None
    assert result.answer_text == ANSWER_JSON["answer_text"]
    mock_create.assert_awaited_once()


@pytest.mark.asyncio
async def test_respond_to_message_revise_case() -> None:
    mock_create = AsyncMock(return_value=_fake_response(json.dumps(REVISE_JSON)))
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        result = await respond_to_message(CURRENT_RECIPE, [], "убери соль")

    assert result.intent == "revise"
    assert result.operations is not None
    assert len(result.operations) == 2
    assert result.operations[0].op == "update_step"
    assert result.operations[1].op == "remove_ingredient"


@pytest.mark.asyncio
async def test_respond_to_message_web_search_off_by_default() -> None:
    mock_create = AsyncMock(return_value=_fake_response(json.dumps(ANSWER_JSON)))
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        await respond_to_message(CURRENT_RECIPE, [], "привет")

    _, kwargs = mock_create.call_args
    assert "tools" not in kwargs


@pytest.mark.asyncio
async def test_respond_to_message_web_search_enabled_via_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REVISE_USE_WEB_SEARCH", "true")
    mock_create = AsyncMock(return_value=_fake_response(json.dumps(ANSWER_JSON)))
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        await respond_to_message(CURRENT_RECIPE, [], "привет")

    _, kwargs = mock_create.call_args
    assert kwargs["tools"] == [{"type": "web_search"}]


@pytest.mark.asyncio
async def test_respond_to_message_retries_once_on_invalid_json_then_succeeds() -> None:
    responses = [_fake_response("not valid json"), _fake_response(json.dumps(ANSWER_JSON))]
    mock_create = AsyncMock(side_effect=responses)
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        result = await respond_to_message(CURRENT_RECIPE, [], "привет")

    assert result.intent == "answer"
    assert mock_create.await_count == 2


@pytest.mark.asyncio
async def test_respond_to_message_fails_after_retry() -> None:
    mock_create = AsyncMock(side_effect=[_fake_response("nope"), _fake_response("still nope")])
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        with pytest.raises(ValidationFailedError):
            await respond_to_message(CURRENT_RECIPE, [], "привет")

    assert mock_create.await_count == 2


@pytest.mark.asyncio
async def test_respond_to_message_timeout_maps_to_domain_error() -> None:
    mock_create = AsyncMock(
        side_effect=APITimeoutError(request=SimpleNamespace())  # type: ignore[arg-type]
    )
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        with pytest.raises(UpstreamTimeoutError):
            await respond_to_message(CURRENT_RECIPE, [], "привет")


@pytest.mark.asyncio
async def test_respond_to_message_truncates_history_to_configured_n(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REVISE_HISTORY_MESSAGES", "2")
    history = [
        HistoryMessage(role="user", content="сообщение 1"),
        HistoryMessage(role="assistant", content="сообщение 2"),
        HistoryMessage(role="user", content="сообщение 3"),
        HistoryMessage(role="assistant", content="сообщение 4"),
    ]
    mock_create = AsyncMock(return_value=_fake_response(json.dumps(ANSWER_JSON)))
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        await respond_to_message(CURRENT_RECIPE, history, "последнее сообщение")

    _, kwargs = mock_create.call_args
    input_messages = kwargs["input"]
    # system message + last 2 history messages + the new user message = 4
    assert len(input_messages) == 4
    contents = [m["content"] for m in input_messages]
    assert "сообщение 1" not in contents
    assert "сообщение 2" not in contents
    assert "сообщение 3" in contents
    assert "сообщение 4" in contents
    assert contents[-1] == "последнее сообщение"


@pytest.mark.asyncio
async def test_respond_to_message_includes_patch_error_in_retry_prompt() -> None:
    mock_create = AsyncMock(return_value=_fake_response(json.dumps(REVISE_JSON)))
    with patch("openai.resources.responses.responses.AsyncResponses.create", mock_create):
        await respond_to_message(
            CURRENT_RECIPE, [], "убери соль", patch_error="unknown ingredient id 'xyz'"
        )

    _, kwargs = mock_create.call_args
    last_message = kwargs["input"][-1]["content"]
    assert "unknown ingredient id 'xyz'" in last_message
    assert "убери соль" in last_message
