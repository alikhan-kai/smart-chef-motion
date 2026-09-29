"""Unit tests for recipe_magazine_service, against the in-memory repos
(no network - see AGENTS.md testing rules)."""

import pytest

from backend.repositories.recipe_magazine_repo import InMemoryRecipeMagazineRepository
from backend.schemas.recipe import Recipe
from backend.services import recipe_magazine_service
from backend.services.recipe_magazine_service import MagazineNotFoundError, RecipeEntryNotFoundError


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


@pytest.fixture
def magazine_repo() -> InMemoryRecipeMagazineRepository:
    return InMemoryRecipeMagazineRepository()


async def test_create_update_share_unpublish_delete(
    magazine_repo: InMemoryRecipeMagazineRepository,
) -> None:
    summary = await recipe_magazine_service.create_magazine(
        magazine_repo, "u1", "Ужины на неделю", "Простые рецепты"
    )
    assert summary.is_public is False
    assert summary.view_count == 0

    updated = await recipe_magazine_service.update_magazine(
        magazine_repo, "u1", summary.id, "Новое название", None
    )
    assert updated.title == "Новое название"
    assert updated.description == "Простые рецепты"

    shared = await recipe_magazine_service.share_magazine(magazine_repo, "u1", summary.id)
    assert shared.is_public is True

    unpublished = await recipe_magazine_service.unpublish_magazine(magazine_repo, "u1", summary.id)
    assert unpublished.is_public is False

    await recipe_magazine_service.delete_magazine(magazine_repo, "u1", summary.id)
    with pytest.raises(MagazineNotFoundError):
        await recipe_magazine_service.update_magazine(magazine_repo, "u1", summary.id, "x", None)


async def test_other_user_cannot_touch_someone_elses_magazine(
    magazine_repo: InMemoryRecipeMagazineRepository,
) -> None:
    summary = await recipe_magazine_service.create_magazine(magazine_repo, "owner", "Book", None)

    with pytest.raises(MagazineNotFoundError):
        await recipe_magazine_service.update_magazine(
            magazine_repo, "intruder", summary.id, "Hacked", None
        )
    with pytest.raises(MagazineNotFoundError):
        await recipe_magazine_service.delete_magazine(magazine_repo, "intruder", summary.id)
    with pytest.raises(MagazineNotFoundError):
        await recipe_magazine_service.share_magazine(magazine_repo, "intruder", summary.id)

    # A private magazine is invisible to a non-owner too - not found, never forbidden.
    with pytest.raises(MagazineNotFoundError):
        await recipe_magazine_service.get_magazine_detail(magazine_repo, "intruder", summary.id)


async def test_set_items_replaces_the_full_recipe_list(
    magazine_repo: InMemoryRecipeMagazineRepository,
) -> None:
    summary = await recipe_magazine_service.create_magazine(magazine_repo, "u1", "Book", None)

    updated = await recipe_magazine_service.set_magazine_items(
        magazine_repo, "u1", summary.id, [_recipe("Омлет")]
    )
    assert updated.recipe_count == 1

    replaced = await recipe_magazine_service.set_magazine_items(
        magazine_repo, "u1", summary.id, [_recipe("Плов"), _recipe("Борщ")]
    )
    assert replaced.recipe_count == 2

    with pytest.raises(MagazineNotFoundError):
        await recipe_magazine_service.set_magazine_items(
            magazine_repo, "intruder", summary.id, [_recipe("Плов")]
        )


async def test_view_count_dedups_per_viewer_and_market_search_and_ordering(
    magazine_repo: InMemoryRecipeMagazineRepository,
) -> None:
    popular = await recipe_magazine_service.create_magazine(
        magazine_repo, "u1", "Завтраки быстро", "Овсянка и омлет"
    )
    niche = await recipe_magazine_service.create_magazine(
        magazine_repo, "u2", "Веганские супы", "Без мяса"
    )
    await recipe_magazine_service.share_magazine(magazine_repo, "u1", popular.id)
    await recipe_magazine_service.share_magazine(magazine_repo, "u2", niche.id)

    # Two different viewers open `popular`, one opens it twice - dedup means +2, not +3.
    await recipe_magazine_service.get_magazine_detail(magazine_repo, "viewer-a", popular.id)
    await recipe_magazine_service.get_magazine_detail(magazine_repo, "viewer-a", popular.id)
    await recipe_magazine_service.get_magazine_detail(magazine_repo, "viewer-b", popular.id)

    market = await recipe_magazine_service.list_market(magazine_repo, None, "popular", 20, 0)
    assert [row.id for row in market] == [popular.id, niche.id]
    assert next(row for row in market if row.id == popular.id).view_count == 2

    search_results = await recipe_magazine_service.list_market(
        magazine_repo, "веган", "popular", 20, 0
    )
    assert [row.id for row in search_results] == [niche.id]

    # "latest" ignores view_count entirely - niche was created after popular.
    latest = await recipe_magazine_service.list_market(magazine_repo, None, "latest", 20, 0)
    assert [row.id for row in latest] == [niche.id, popular.id]


async def test_save_market_item_carries_attribution_and_stays_scoped(
    magazine_repo: InMemoryRecipeMagazineRepository,
) -> None:
    owner_summary = await recipe_magazine_service.create_magazine(
        magazine_repo, "owner", "Бабушкины супы", None
    )
    await recipe_magazine_service.set_magazine_items(
        magazine_repo, "owner", owner_summary.id, [_recipe("Борщ")]
    )
    await recipe_magazine_service.share_magazine(magazine_repo, "owner", owner_summary.id)

    detail = await recipe_magazine_service.get_magazine_detail(
        magazine_repo, "viewer", owner_summary.id
    )
    item_id = detail.items[0].id

    my_magazine = await recipe_magazine_service.create_magazine(
        magazine_repo, "viewer", "Мои", None
    )

    updated = await recipe_magazine_service.save_market_item_to_my_magazine(
        magazine_repo, "viewer", owner_summary.id, item_id, my_magazine.id
    )
    assert updated.recipe_count == 1

    my_detail = await recipe_magazine_service.get_magazine_detail(
        magazine_repo, "viewer", my_magazine.id
    )
    saved_item = my_detail.items[0]
    assert saved_item.recipe.title == "Борщ"
    # Never indistinguishable from something the viewer made themselves.
    assert saved_item.source_magazine_title == "Бабушкины супы"

    # The original magazine is untouched by the save.
    original_detail = await recipe_magazine_service.get_magazine_detail(
        magazine_repo, "owner", owner_summary.id
    )
    assert len(original_detail.items) == 1
    assert original_detail.items[0].source_magazine_title is None

    with pytest.raises(RecipeEntryNotFoundError):
        await recipe_magazine_service.save_market_item_to_my_magazine(
            magazine_repo, "viewer", owner_summary.id, "no-such-item", my_magazine.id
        )

    # Can't save into a magazine that isn't the caller's own.
    with pytest.raises(MagazineNotFoundError):
        await recipe_magazine_service.save_market_item_to_my_magazine(
            magazine_repo, "viewer", owner_summary.id, item_id, owner_summary.id
        )


async def test_saving_a_reshared_item_preserves_original_attribution(
    magazine_repo: InMemoryRecipeMagazineRepository,
) -> None:
    original = await recipe_magazine_service.create_magazine(
        magazine_repo, "author", "Оригинальный журнал", None
    )
    await recipe_magazine_service.set_magazine_items(
        magazine_repo, "author", original.id, [_recipe("Плов")]
    )
    await recipe_magazine_service.share_magazine(magazine_repo, "author", original.id)

    reshared_by = await recipe_magazine_service.create_magazine(
        magazine_repo, "reshared", "Пересобранный журнал", None
    )
    original_detail = await recipe_magazine_service.get_magazine_detail(
        magazine_repo, "reshared", original.id
    )
    await recipe_magazine_service.save_market_item_to_my_magazine(
        magazine_repo, "reshared", original.id, original_detail.items[0].id, reshared_by.id
    )
    await recipe_magazine_service.share_magazine(magazine_repo, "reshared", reshared_by.id)

    final_magazine = await recipe_magazine_service.create_magazine(
        magazine_repo, "final-saver", "У меня", None
    )
    reshared_detail = await recipe_magazine_service.get_magazine_detail(
        magazine_repo, "final-saver", reshared_by.id
    )
    await recipe_magazine_service.save_market_item_to_my_magazine(
        magazine_repo,
        "final-saver",
        reshared_by.id,
        reshared_detail.items[0].id,
        final_magazine.id,
    )

    final_detail = await recipe_magazine_service.get_magazine_detail(
        magazine_repo, "final-saver", final_magazine.id
    )
    # Attributes back to the true original author's magazine, not the
    # intermediate re-sharer's magazine.
    assert final_detail.items[0].source_magazine_title == "Оригинальный журнал"
