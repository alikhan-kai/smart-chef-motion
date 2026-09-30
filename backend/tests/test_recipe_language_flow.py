"""Regression coverage for the browser -> API -> model language contract.

Mock the OpenAI boundary only, so request parsing and service forwarding run.
"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app

ENGLISH_RECIPE = {
    "error": None,
    "title": "Boiled eggs",
    "servings": 1,
    "total_time_minutes": 10,
    "equipment": ["pot"],
    "source_urls": [],
    "notes": None,
    "ingredients": [{"id": "egg", "name": "egg", "amount": 1, "unit": "piece", "form": None}],
    "steps": [{
        "step_number": 1, "header": "Boil the egg", "action": "Boil the egg.",
        "ingredients_used": ["egg"], "time_minutes": 10, "passive": False,
        "heat_level": "средний огонь", "place": "кастрюля", "salt": False,
        "fat": None, "final_action": "Turn off the heat.",
    }],
}


@pytest.fixture(autouse=True)
def settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in {
        "OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-test",
        "SUPABASE_URL": "", "SUPABASE_SERVICE_KEY": "",
        "TWO_STEP_MODE": "false", "REVISE_USE_WEB_SEARCH": "false",
    }.items():
        monkeypatch.setenv(key, value)


def response(payload: object) -> SimpleNamespace:
    return SimpleNamespace(output_text=json.dumps(payload))


@pytest.mark.parametrize("endpoint", ["/chats", "/recipes/create", "/recipes/generate-raw"])
@pytest.mark.parametrize("two_step", [False, True])
async def test_english_generation_and_retry(
    endpoint: str, two_step: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWO_STEP_MODE", str(two_step).lower())
    attempts = [SimpleNamespace(output_text="invalid json"), response(ENGLISH_RECIPE)]
    if two_step:
        attempts = [
            SimpleNamespace(output_text="Boil the egg for 10 minutes."), attempts[0],
            SimpleNamespace(output_text="Boil the egg for 10 minutes."), attempts[1],
        ]
    create = AsyncMock(side_effect=attempts)
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as ac:
        with patch("openai.resources.responses.responses.AsyncResponses.create", create):
            result = await ac.post(
                endpoint, json={"prompt": "eggs", "language": "en"},
                headers={"X-User-Id": "language-test"},
            )
    assert result.status_code == 200, result.text
    recipe = result.json().get("recipe", result.json())
    assert recipe["steps"][0]["header"] == "Boil the egg"
    assert recipe["steps"][0]["action"] == "Boil the egg."
    if endpoint != "/recipes/generate-raw":
        assert recipe["language"] == "en"
    assert create.await_count == (4 if two_step else 2)
    for call in create.await_args_list:
        system_prompt = call.kwargs["input"][0]["content"]
        assert "OUTPUT LANGUAGE: English (en)" in system_prompt
        assert "обычным читаемым текстом на русском языке" not in system_prompt


async def test_revision_patch_retry_keeps_selected_language() -> None:
    invalid_patch = {
        "intent": "revise", "answer_text": "Updated.",
        "operations": [{"op": "remove_ingredient", "ingredient_id": "missing"}],
    }
    valid_patch = {
        "intent": "revise", "answer_text": "Updated servings.",
        "operations": [{"op": "update_meta", "fields": [{"field": "servings", "value": 2}]}],
    }
    create = AsyncMock(side_effect=[
        response(ENGLISH_RECIPE), response(invalid_patch), response(valid_patch),
    ])
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as ac:
        with patch("openai.resources.responses.responses.AsyncResponses.create", create):
            start = await ac.post("/chats", json={"prompt": "eggs", "language": "en"},
                                  headers={"X-User-Id": "language-test"})
            result = await ac.post(
                f"/chats/{start.json()['chat_id']}/messages",
                json={"text": "2", "language": "en"},
                headers={"X-User-Id": "language-test"},
            )
    assert result.status_code == 200, result.text
    assert result.json()["recipe"]["servings"] == 2
    assert create.await_count == 3
    for call in create.await_args_list:
        assert "OUTPUT LANGUAGE: English (en)" in call.kwargs["input"][0]["content"]


@pytest.mark.parametrize("language", ["ru", "kk", None])
async def test_optional_language_contract(language: str | None) -> None:
    create = AsyncMock(return_value=response(ENGLISH_RECIPE))
    payload = {"prompt": "eggs"}
    if language is not None:
        payload["language"] = language
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as ac:
        with patch("openai.resources.responses.responses.AsyncResponses.create", create):
            result = await ac.post("/chats", json=payload, headers={"X-User-Id": "language-test"})
    assert result.status_code == 200
    system_prompt = create.await_args.kwargs["input"][0]["content"]
    if language is None:
        assert "OUTPUT LANGUAGE:" not in system_prompt
    else:
        expected = {"ru": "Russian", "kk": "Kazakh"}[language]
        assert f"OUTPUT LANGUAGE: {expected} ({language})" in system_prompt


async def test_unsupported_language_is_rejected_before_model_call() -> None:
    create = AsyncMock()
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as ac:
        with patch("openai.resources.responses.responses.AsyncResponses.create", create):
            result = await ac.post("/chats", json={"prompt": "eggs", "language": "invalid"},
                                   headers={"X-User-Id": "language-test"})
    assert result.status_code == 422
    create.assert_not_called()
