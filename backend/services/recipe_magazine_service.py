"""Recipe-magazine orchestration: create/update/share/unpublish/delete,
listing (mine + market), viewing, and saving a recipe found on the market
into one of the caller's own magazines.

Talks to persistence only through the RecipeMagazineRepository protocol
passed in by the caller (same pattern as chat_service.py) - see
backend/api/deps.py for how routes obtain the concrete instance.
"""

from backend.repositories.recipe_magazine_repo import MagazineSort, RecipeMagazineRepository
from backend.schemas.recipe import Recipe
from backend.schemas.recipe_magazine import RecipeMagazineDetail, RecipeMagazineSummary


class MagazineNotFoundError(Exception):
    """No such magazine for this viewer - either it doesn't exist, or it's
    private and belongs to someone else (indistinguishable to the caller,
    same rule as ChatNotFoundError/RecipeNotFoundError)."""


class RecipeEntryNotFoundError(Exception):
    """The item_id given to save_market_item_to_my_magazine() isn't one of
    the source magazine's items."""


async def create_magazine(
    magazine_repo: RecipeMagazineRepository,
    user_id: str,
    title: str,
    description: str | None,
) -> RecipeMagazineSummary:
    return await magazine_repo.create(user_id, title, description)


async def update_magazine(
    magazine_repo: RecipeMagazineRepository,
    user_id: str,
    magazine_id: str,
    title: str | None,
    description: str | None,
) -> RecipeMagazineSummary:
    summary = await magazine_repo.update(magazine_id, user_id, title, description)
    if summary is None:
        raise MagazineNotFoundError(magazine_id)
    return summary


async def set_magazine_items(
    magazine_repo: RecipeMagazineRepository,
    user_id: str,
    magazine_id: str,
    recipes: list[Recipe],
) -> RecipeMagazineSummary:
    summary = await magazine_repo.set_items(magazine_id, user_id, recipes)
    if summary is None:
        raise MagazineNotFoundError(magazine_id)
    return summary


async def set_magazine_cover(
    magazine_repo: RecipeMagazineRepository,
    user_id: str,
    magazine_id: str,
    content: bytes,
    content_type: str,
) -> None:
    updated = await magazine_repo.set_cover(magazine_id, user_id, content, content_type)
    if not updated:
        raise MagazineNotFoundError(magazine_id)


async def get_magazine_cover(
    magazine_repo: RecipeMagazineRepository, magazine_id: str
) -> tuple[bytes, str]:
    cover = await magazine_repo.get_cover(magazine_id)
    if cover is None:
        raise MagazineNotFoundError(magazine_id)
    return cover


async def share_magazine(
    magazine_repo: RecipeMagazineRepository, user_id: str, magazine_id: str
) -> RecipeMagazineSummary:
    return await _set_public(magazine_repo, user_id, magazine_id, is_public=True)


async def unpublish_magazine(
    magazine_repo: RecipeMagazineRepository, user_id: str, magazine_id: str
) -> RecipeMagazineSummary:
    return await _set_public(magazine_repo, user_id, magazine_id, is_public=False)


async def _set_public(
    magazine_repo: RecipeMagazineRepository, user_id: str, magazine_id: str, is_public: bool
) -> RecipeMagazineSummary:
    summary = await magazine_repo.set_public(magazine_id, user_id, is_public)
    if summary is None:
        raise MagazineNotFoundError(magazine_id)
    return summary


async def delete_magazine(
    magazine_repo: RecipeMagazineRepository, user_id: str, magazine_id: str
) -> None:
    deleted = await magazine_repo.delete(magazine_id, user_id)
    if not deleted:
        raise MagazineNotFoundError(magazine_id)


async def list_my_magazines(
    magazine_repo: RecipeMagazineRepository, user_id: str
) -> list[RecipeMagazineSummary]:
    return await magazine_repo.list_mine(user_id)


async def list_market(
    magazine_repo: RecipeMagazineRepository,
    query: str | None,
    sort: MagazineSort,
    limit: int,
    offset: int,
) -> list[RecipeMagazineSummary]:
    return await magazine_repo.list_market(query, sort, limit, offset)


async def get_magazine_detail(
    magazine_repo: RecipeMagazineRepository,
    viewer_user_id: str,
    magazine_id: str,
) -> RecipeMagazineDetail:
    detail = await magazine_repo.get_detail(magazine_id, viewer_user_id)
    if detail is None:
        raise MagazineNotFoundError(magazine_id)
    await magazine_repo.record_view(magazine_id, viewer_user_id)
    # Re-fetch so a first-time view's count is reflected in the response
    # (record_view() may have just incremented it).
    return await magazine_repo.get_detail(magazine_id, viewer_user_id) or detail


async def save_market_item_to_my_magazine(
    magazine_repo: RecipeMagazineRepository,
    viewer_user_id: str,
    source_magazine_id: str,
    item_id: str,
    target_magazine_id: str,
) -> RecipeMagazineSummary:
    """Saves one recipe from a magazine visible to viewer_user_id (their
    own, or any public one) into a magazine viewer_user_id owns. The saved
    item always carries `source_magazine_title` (the source's title at this
    moment) - see RecipeMagazineItem's docstring: a saver can browse and
    reuse anything on the market, but the result is never indistinguishable
    from something they created themselves."""
    source = await magazine_repo.get_detail(source_magazine_id, viewer_user_id)
    if source is None:
        raise MagazineNotFoundError(source_magazine_id)

    item = next((candidate for candidate in source.items if candidate.id == item_id), None)
    if item is None:
        raise RecipeEntryNotFoundError(item_id)

    # If this item was itself saved from somewhere else, keep pointing at
    # that original source rather than at `source` (which didn't create it
    # either) - attribution should never launder back to "no attribution".
    attribution = item.source_magazine_title or source.title

    summary = await magazine_repo.append_item(
        target_magazine_id, viewer_user_id, item.recipe, attribution
    )
    if summary is None:
        raise MagazineNotFoundError(target_magazine_id)
    return summary
