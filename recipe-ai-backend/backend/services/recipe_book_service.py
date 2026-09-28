"""Recipe-book reads. Writing a recipe-book entry happens via
chat_service.confirm_recipe() - the recipe book is never written to
directly, only through confirming a chat version (see AGENTS.md: "only a
confirmed recipe goes into the recipe book").
"""

from backend.repositories.recipe_book_repo import RecipeBookRepository
from backend.schemas.chat import RecipeBookEntry


class RecipeNotFoundError(Exception):
    """No such recipe-book entry for this user (or it belongs to someone
    else - indistinguishable to the caller, same rule as ChatNotFoundError)."""


async def list_entries(book_repo: RecipeBookRepository, user_id: str) -> list[RecipeBookEntry]:
    return await book_repo.list_entries(user_id)


async def get_entry(
    book_repo: RecipeBookRepository, user_id: str, recipe_id: str
) -> RecipeBookEntry:
    entry = await book_repo.get_entry(user_id, recipe_id)
    if entry is None:
        raise RecipeNotFoundError(recipe_id)
    return entry
