"""Endpoint tests for the recipe-magazine routes, via httpx.AsyncClient.
Each test gets its own app (and therefore its own in-memory repositories -
see backend/main.py's create_app()), same pattern as test_chat_endpoints.py.

Magazine items are set by posting full Recipe payloads directly (see
SetMagazineItemsRequest's docstring for why).
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.main import create_app
from backend.schemas.recipe import Recipe


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _headers(user_id: str) -> dict[str, str]:
    return {"X-User-Id": user_id}


def _recipe(title: str) -> Recipe:
    return Recipe(
        id=title,
        language="ru",
        title=title,
        servings=2,
        equipment=None,
        source_urls=None,
        notes=None,
        ingredients=[],
        steps=[],
        total_time_minutes=None,
        warnings=[],
    )


async def test_create_add_items_share_and_market_search(client: AsyncClient) -> None:
    create_response = await client.post(
        "/recipe-magazines",
        json={"title": "Обеды", "description": "Домашняя кухня"},
        headers=_headers("owner"),
    )
    assert create_response.status_code == 201
    magazine_id = create_response.json()["id"]
    assert create_response.json()["is_public"] is False

    items_response = await client.put(
        f"/recipe-magazines/{magazine_id}/items",
        json={"recipes": [_recipe("Борщ").model_dump(mode="json")]},
        headers=_headers("owner"),
    )
    assert items_response.status_code == 200
    assert items_response.json()["recipe_count"] == 1

    share_response = await client.post(
        f"/recipe-magazines/{magazine_id}/share", headers=_headers("owner")
    )
    assert share_response.status_code == 200
    assert share_response.json()["is_public"] is True

    # Not visible in the market for someone else without a matching search term...
    miss = await client.get("/recipe-magazines/market", params={"q": "завтрак"})
    assert miss.json() == []

    # ...but is with one that matches the title.
    hit = await client.get("/recipe-magazines/market", params={"q": "обед"})
    assert [row["id"] for row in hit.json()] == [magazine_id]

    # Another user can open it and sees the full recipe.
    detail = await client.get(f"/recipe-magazines/{magazine_id}", headers=_headers("viewer"))
    assert detail.status_code == 200
    assert detail.json()["items"][0]["recipe"]["title"] == "Борщ"


async def test_view_count_dedups_and_owner_is_scoped(client: AsyncClient) -> None:
    create_response = await client.post(
        "/recipe-magazines", json={"title": "Book", "description": None}, headers=_headers("owner")
    )
    magazine_id = create_response.json()["id"]
    await client.post(f"/recipe-magazines/{magazine_id}/share", headers=_headers("owner"))

    await client.get(f"/recipe-magazines/{magazine_id}", headers=_headers("viewer"))
    await client.get(f"/recipe-magazines/{magazine_id}", headers=_headers("viewer"))
    second_viewer = await client.get(
        f"/recipe-magazines/{magazine_id}", headers=_headers("viewer-2")
    )
    assert second_viewer.json()["view_count"] == 2

    # A non-owner can't PATCH/delete/unpublish someone else's magazine - 404, not 403.
    forbidden_patch = await client.patch(
        f"/recipe-magazines/{magazine_id}",
        json={"title": "Hacked", "description": None},
        headers=_headers("intruder"),
    )
    assert forbidden_patch.status_code == 404


async def test_save_market_item_into_viewers_own_magazine_with_attribution(
    client: AsyncClient,
) -> None:
    create_response = await client.post(
        "/recipe-magazines",
        json={"title": "Дедушкин журнал", "description": None},
        headers=_headers("owner"),
    )
    magazine_id = create_response.json()["id"]
    await client.put(
        f"/recipe-magazines/{magazine_id}/items",
        json={"recipes": [_recipe("Плов").model_dump(mode="json")]},
        headers=_headers("owner"),
    )
    await client.post(f"/recipe-magazines/{magazine_id}/share", headers=_headers("owner"))

    detail = await client.get(f"/recipe-magazines/{magazine_id}", headers=_headers("viewer"))
    item_id = detail.json()["items"][0]["id"]

    my_magazine_response = await client.post(
        "/recipe-magazines", json={"title": "Мой", "description": None}, headers=_headers("viewer")
    )
    my_magazine_id = my_magazine_response.json()["id"]

    save_response = await client.post(
        f"/recipe-magazines/{magazine_id}/items/{item_id}/save",
        json={"target_magazine_id": my_magazine_id},
        headers=_headers("viewer"),
    )
    assert save_response.status_code == 200
    assert save_response.json()["recipe_count"] == 1

    my_detail = await client.get(f"/recipe-magazines/{my_magazine_id}", headers=_headers("viewer"))
    saved_item = my_detail.json()["items"][0]
    assert saved_item["recipe"]["title"] == "Плов"
    assert saved_item["source_magazine_title"] == "Дедушкин журнал"

    # A viewer can't save into a magazine they don't own - 404, not 403.
    forbidden = await client.post(
        f"/recipe-magazines/{magazine_id}/items/{item_id}/save",
        json={"target_magazine_id": magazine_id},
        headers=_headers("viewer"),
    )
    assert forbidden.status_code == 404


async def test_cover_upload_and_fetch(client: AsyncClient) -> None:
    create_response = await client.post(
        "/recipe-magazines", json={"title": "Book", "description": None}, headers=_headers("owner")
    )
    magazine_id = create_response.json()["id"]

    upload_response = await client.put(
        f"/recipe-magazines/{magazine_id}/cover",
        files={"cover": ("cover.png", b"\x89PNG\r\n fake bytes", "image/png")},
        headers=_headers("owner"),
    )
    assert upload_response.status_code == 204

    cover_response = await client.get(f"/recipe-magazines/{magazine_id}/cover")
    assert cover_response.status_code == 200
    assert cover_response.headers["content-type"] == "image/png"
    assert cover_response.content == b"\x89PNG\r\n fake bytes"
