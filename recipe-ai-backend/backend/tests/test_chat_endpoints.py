"""Endpoint tests for the chat/recipe-book routes, via httpx.AsyncClient.

generate_raw_recipe and respond_to_message are monkeypatched at their
chat_service call site (same pattern as backend/tests/test_endpoints.py);
no real OpenAI calls. Each test gets its own app (and therefore its own
in-memory repositories - see backend/main.py's create_app()).
"""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from llm.chat_schemas import ChatResponse
from llm.schemas import RawIngredient, RawRecipe, RawStep

DRAFT_RECIPE = RawRecipe(
    error=None,
    title="Омлет",
    servings=2,
    total_time_minutes=None,
    equipment=["сковорода"],
    source_urls=[],
    notes=None,
    ingredients=[RawIngredient(id="eggs", name="яйца", amount=3, unit="шт", form=None)],
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
        )
    ],
)

ANSWER_RESPONSE = {"intent": "answer", "answer_text": "Ответ на вопрос.", "operations": None}

REVISE_RESPONSE = {
    "intent": "revise",
    "answer_text": "Добавил щепотку перца.",
    "operations": [
        {
            "op": "add_ingredient",
            "ingredient": {
                "id": "pepper",
                "name": "перец",
                "amount": 1,
                "unit": "щепотка",
                "form": None,
            },
        }
    ],
}


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _headers(user_id: str = "u1") -> dict[str, str]:
    return {"X-User-Id": user_id}


async def _start_chat(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, user_id: str = "u1"
) -> str:
    monkeypatch.setattr(
        "backend.services.chat_service.generate_raw_recipe", AsyncMock(return_value=DRAFT_RECIPE)
    )
    response = await client.post("/chats", json={"prompt": "омлет"}, headers=_headers(user_id))
    assert response.status_code == 200
    return str(response.json()["chat_id"])


# ---------------------------------------------------------------------------
# POST /chats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_chat_endpoint_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch)
    assert chat_id

    response = await client.get(f"/chats/{chat_id}", headers=_headers())
    body = response.json()
    assert response.status_code == 200
    assert body["versions"][0]["recipe"]["title"] == "Омлет"


@pytest.mark.asyncio
async def test_start_chat_endpoint_missing_user_id_header(client: AsyncClient) -> None:
    response = await client.post("/chats", json={"prompt": "омлет"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /chats/{chat_id}/messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_endpoint_answer(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch)
    monkeypatch.setattr(
        "backend.services.chat_service.respond_to_message",
        AsyncMock(return_value=ChatResponse.model_validate(ANSWER_RESPONSE)),
    )

    response = await client.post(
        f"/chats/{chat_id}/messages", json={"text": "вопрос?"}, headers=_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "answer"
    assert body["version"] is None


@pytest.mark.asyncio
async def test_send_message_endpoint_revise(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch)
    monkeypatch.setattr(
        "backend.services.chat_service.respond_to_message",
        AsyncMock(return_value=ChatResponse.model_validate(REVISE_RESPONSE)),
    )

    response = await client.post(
        f"/chats/{chat_id}/messages", json={"text": "добавь перец"}, headers=_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "revise"
    assert body["version"] == 2
    assert body["recipe"]["ingredients"][-1]["id"] == "pepper"
    assert len(body["change_log"]) == 1


@pytest.mark.asyncio
async def test_send_message_endpoint_unknown_chat_returns_404(client: AsyncClient) -> None:
    response = await client.post(
        "/chats/does-not-exist/messages", json={"text": "hi"}, headers=_headers()
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /chats/{chat_id}/confirm
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_endpoint_defaults_to_latest_version(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch)

    response = await client.post(
        f"/chats/{chat_id}/confirm", json={"version": None}, headers=_headers()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["chat_id"] == chat_id
    assert body["version"] == 1
    assert body["recipe"]["title"] == "Омлет"


@pytest.mark.asyncio
async def test_confirm_endpoint_is_idempotent(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch)

    first = await client.post(f"/chats/{chat_id}/confirm", json={"version": 1}, headers=_headers())
    second = await client.post(f"/chats/{chat_id}/confirm", json={"version": 1}, headers=_headers())

    assert first.json()["id"] == second.json()["id"]

    book = await client.get("/recipe-book", headers=_headers())
    assert len(book.json()) == 1


@pytest.mark.asyncio
async def test_confirm_endpoint_unknown_version_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch)
    response = await client.post(
        f"/chats/{chat_id}/confirm", json={"version": 99}, headers=_headers()
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /chats, GET /chats/{chat_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_chats_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    await _start_chat(client, monkeypatch)
    response = await client.get("/chats", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["confirmed"] is False


@pytest.mark.asyncio
async def test_get_chat_endpoint_another_users_chat_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch, user_id="owner")

    response = await client.get(f"/chats/{chat_id}", headers=_headers("someone-else"))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_chats_endpoint_only_shows_own_chats(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _start_chat(client, monkeypatch, user_id="owner")

    response = await client.get("/chats", headers=_headers("someone-else"))

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# GET /recipe-book, GET /recipe-book/{recipe_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recipe_book_list_and_get_endpoints(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch)
    await client.post(f"/chats/{chat_id}/confirm", json={"version": None}, headers=_headers())

    list_response = await client.get("/recipe-book", headers=_headers())
    assert list_response.status_code == 200
    entries = list_response.json()
    assert len(entries) == 1
    recipe_id = entries[0]["id"]

    get_response = await client.get(f"/recipe-book/{recipe_id}", headers=_headers())
    assert get_response.status_code == 200
    assert get_response.json()["recipe"]["title"] == "Омлет"


@pytest.mark.asyncio
async def test_recipe_book_get_endpoint_another_users_recipe_returns_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chat_id = await _start_chat(client, monkeypatch, user_id="owner")
    confirm_response = await client.post(
        f"/chats/{chat_id}/confirm", json={"version": None}, headers=_headers("owner")
    )
    recipe_id = confirm_response.json()["id"]

    response = await client.get(f"/recipe-book/{recipe_id}", headers=_headers("someone-else"))

    assert response.status_code == 404
