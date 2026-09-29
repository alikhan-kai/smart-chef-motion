"""Older recipe steps lack headers; new titles must survive the same paths."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.schemas.recipe import Recipe
from backend.services.recipe_composer import compose_recipe
from llm.schemas import RawRecipe, RawStep

HEADER_CASES = [
    ({}, None),
    ({"header": None}, None),
    ({"header": "Смешиваем ингредиенты"}, "Смешиваем ингредиенты"),
]


@pytest.fixture
def step_payload() -> dict[str, Any]:
    return {
        "step_number": 1,
        "action": "Перемешайте ингредиенты",
        "ingredients_used": [],
        "time_minutes": None,
        "passive": False,
        "heat_level": None,
        "place": "миска",
        "salt": False,
        "fat": None,
        "final_action": None,
    }


@pytest.mark.parametrize("header_fields,expected", HEADER_CASES)
def test_raw_step_header_compatibility(
    step_payload: dict[str, Any], header_fields: dict[str, str | None], expected: str | None
) -> None:
    step = RawStep.model_validate({**step_payload, **header_fields})
    assert step.header == expected
    assert step.model_dump()["header"] == expected


@pytest.mark.parametrize("header_fields,expected", HEADER_CASES)
async def test_composed_and_saved_recipe_header_compatibility(
    step_payload: dict[str, Any], header_fields: dict[str, str | None], expected: str | None
) -> None:
    raw = RawRecipe.model_validate(
        {
            "error": None,
            "title": "Салат",
            "servings": 1,
            "total_time_minutes": None,
            "equipment": None,
            "source_urls": None,
            "notes": None,
            "ingredients": [],
            "steps": [{**step_payload, **header_fields}],
        }
    )
    recipe = await compose_recipe(raw)
    assert recipe.steps[0].header == expected
    saved = recipe.model_dump(mode="json")
    if not header_fields:
        # Simulate a recipe persisted before the header feature existed.
        saved["steps"][0].pop("header")
    restored = Recipe.model_validate(saved)
    assert restored.steps[0].header == expected
    assert restored.steps[0].display_text == recipe.steps[0].display_text


@pytest.mark.parametrize("header_fields,expected", HEADER_CASES)
async def test_magazine_accepts_recipe_step_headers(
    step_payload: dict[str, Any], header_fields: dict[str, str | None], expected: str | None
) -> None:
    recipe = {
        "id": "header-compatibility",
        "language": "ru",
        "title": "Салат",
        "servings": 1,
        "total_time_minutes": None,
        "equipment": None,
        "source_urls": None,
        "notes": None,
        "ingredients": [],
        "steps": [{**step_payload, **header_fields, "display_text": "Перемешайте ингредиенты"}],
        "warnings": [],
    }
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        headers = {"X-User-Id": "header-compatibility"}
        created = await client.post("/recipe-magazines", json={"title": "Салаты"}, headers=headers)
        assert created.status_code == 201
        path = f"/recipe-magazines/{created.json()['id']}"
        updated = await client.put(path + "/items", json={"recipes": [recipe]}, headers=headers)
        assert updated.status_code == 200
        detail = await client.get(path, headers=headers)
        assert detail.status_code == 200
        assert detail.json()["items"][0]["recipe"]["steps"][0]["header"] == expected
