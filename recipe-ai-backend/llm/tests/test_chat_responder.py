"""respond_to_message() tests with a fake LangChain chat model. Never calls a real API."""

from typing import Any
from unittest.mock import patch

import pytest
from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from llm.chat_responder import respond_to_message
from llm.chat_schemas import HistoryMessage
from llm.errors import UpstreamTimeoutError, ValidationFailedError
from llm.schemas import RawIngredient, RawRecipe, RawStep
from llm.tests.fake_chat_model import FakeChatModel

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
            header=None,
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
            header=None,
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


class APITimeoutError(Exception):
    """Named like the OpenAI/Anthropic SDK error; matched by name, not import."""


@pytest.fixture(autouse=True)
def _configure_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.delenv("REVISE_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("REVISE_HISTORY_MESSAGES", raising=False)


def _use(model: FakeChatModel) -> Any:
    return patch("llm.chat_responder.build_chat_model", return_value=model)


@pytest.mark.asyncio
async def test_respond_to_message_answer_case() -> None:
    model = FakeChatModel(structured=[ANSWER_JSON])
    with _use(model):
        result = await respond_to_message(CURRENT_RECIPE, [], "нужно ли солить?")

    assert result.intent == "answer"
    assert result.operations is None
    assert result.answer_text == ANSWER_JSON["answer_text"]
    model.structured.assert_awaited_once()
    assert model.schema is not None and model.schema["title"] == "chat_response"


@pytest.mark.asyncio
async def test_respond_to_message_revise_case() -> None:
    model = FakeChatModel(structured=[REVISE_JSON])
    with _use(model):
        result = await respond_to_message(CURRENT_RECIPE, [], "убери соль")

    assert result.intent == "revise"
    assert result.operations is not None
    assert len(result.operations) == 2
    assert result.operations[0].op == "update_step"
    assert result.operations[1].op == "remove_ingredient"


@pytest.mark.asyncio
async def test_respond_to_message_web_search_off_by_default() -> None:
    model = FakeChatModel(structured=[ANSWER_JSON])
    with _use(model):
        await respond_to_message(CURRENT_RECIPE, [], "привет")

    assert model.tools is None
    model.text.assert_not_awaited()


@pytest.mark.asyncio
async def test_respond_to_message_web_search_enabled_via_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REVISE_USE_WEB_SEARCH", "true")
    model = FakeChatModel(text=["Соль: до 5 г в день."], structured=[ANSWER_JSON])
    with _use(model):
        await respond_to_message(CURRENT_RECIPE, [], "сколько соли можно?")

    assert model.tools == [{"type": "web_search"}]
    model.text.assert_awaited_once()
    structured_messages = model.structured.call_args.args[0]
    assert "Соль: до 5 г в день." in structured_messages[-1].content


@pytest.mark.asyncio
async def test_respond_to_message_retries_once_on_invalid_output_then_succeeds() -> None:
    model = FakeChatModel(structured=[OutputParserException("bad json"), ANSWER_JSON])
    with _use(model):
        result = await respond_to_message(CURRENT_RECIPE, [], "привет")

    assert result.intent == "answer"
    assert model.structured.await_count == 2


@pytest.mark.asyncio
async def test_respond_to_message_fails_after_retry() -> None:
    model = FakeChatModel(structured=[OutputParserException("nope"), {"intent": "???"}])
    with _use(model):
        with pytest.raises(ValidationFailedError):
            await respond_to_message(CURRENT_RECIPE, [], "привет")

    assert model.structured.await_count == 2


@pytest.mark.asyncio
async def test_respond_to_message_timeout_maps_to_domain_error() -> None:
    model = FakeChatModel(structured=[APITimeoutError("timed out")])
    with _use(model):
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
    model = FakeChatModel(structured=[ANSWER_JSON])
    with _use(model):
        await respond_to_message(CURRENT_RECIPE, history, "последнее сообщение")

    input_messages = model.structured.call_args.args[0]
    # system message + last 2 history messages + the new user message = 4
    assert len(input_messages) == 4
    assert isinstance(input_messages[0], SystemMessage)
    assert isinstance(input_messages[1], HumanMessage)
    assert isinstance(input_messages[2], AIMessage)
    contents = [m.content for m in input_messages]
    assert "сообщение 1" not in contents
    assert "сообщение 2" not in contents
    assert "сообщение 3" in contents
    assert "сообщение 4" in contents
    assert contents[-1] == "последнее сообщение"


@pytest.mark.asyncio
async def test_respond_to_message_includes_patch_error_in_retry_prompt() -> None:
    model = FakeChatModel(structured=[REVISE_JSON])
    with _use(model):
        await respond_to_message(
            CURRENT_RECIPE, [], "убери соль", patch_error="unknown ingredient id 'xyz'"
        )

    last_message = model.structured.call_args.args[0][-1].content
    assert "unknown ingredient id 'xyz'" in last_message
    assert "убери соль" in last_message
