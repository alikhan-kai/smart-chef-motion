"""Endpoint tests with httpx.AsyncClient. No real OpenAI calls."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from llm.errors import ModelReportedError, UpstreamTimeoutError
from llm.schemas import RawIngredient, RawRecipe, RawStep

VALID_RAW_RECIPE = RawRecipe(
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
            action="Взбить яйца",
            ingredients_used=["eggs"],
            time_minutes=2,
            passive=False,
            heat_level=None,
            place="миска",
            salt=False,
            fat=None,
            final_action=None,
        )
    ],
)


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_generate_raw_endpoint_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = AsyncMock(return_value=VALID_RAW_RECIPE)
    monkeypatch.setattr("backend.api.routes_generate_raw.generate_raw_recipe", mock)

    payload = {"prompt": "омлет", "allergies": None, "preferred_units": None}
    response = await client.post("/recipes/generate-raw", json=payload)

    assert response.status_code == 200
    assert response.json()["title"] == "Омлет"
    mock.assert_awaited_once_with("омлет", None, None, language=None)


@pytest.mark.asyncio
async def test_generate_raw_endpoint_model_reported_error_maps_to_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = AsyncMock(side_effect=ModelReportedError("Запрос не про еду"))
    monkeypatch.setattr("backend.api.routes_generate_raw.generate_raw_recipe", mock)

    response = await client.post("/recipes/generate-raw", json={"prompt": "не рецепт"})

    assert response.status_code == 422
    assert response.json()["detail"] == "Запрос не про еду"


@pytest.mark.asyncio
async def test_generate_raw_endpoint_timeout_maps_to_504(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = AsyncMock(side_effect=UpstreamTimeoutError("timed out"))
    monkeypatch.setattr("backend.api.routes_generate_raw.generate_raw_recipe", mock)

    response = await client.post("/recipes/generate-raw", json={"prompt": "борщ"})

    assert response.status_code == 504


@pytest.mark.asyncio
async def test_compose_endpoint_success(client: AsyncClient) -> None:
    response = await client.post("/recipes/compose", json=VALID_RAW_RECIPE.model_dump())

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Омлет"
    assert body["steps"][0]["display_text"]


@pytest.mark.asyncio
async def test_create_endpoint_success(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock = AsyncMock(return_value=VALID_RAW_RECIPE)
    monkeypatch.setattr("backend.services.pipeline.generate_raw_recipe", mock)

    response = await client.post("/recipes/create", json={"prompt": "омлет"})

    assert response.status_code == 200
    assert response.json()["title"] == "Омлет"
