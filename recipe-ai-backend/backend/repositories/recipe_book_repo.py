"""RecipeBookRepository protocol + in-memory implementation.

See backend/repositories/chat_repo.py's module docstring for the same
"not a real database, scoped by user_id" caveats - they apply here too.
"""

import uuid
from datetime import UTC, datetime
from typing import Protocol

from backend.schemas.chat import RecipeBookEntry
from backend.schemas.recipe import Recipe


class RecipeBookRepository(Protocol):
    async def save_entry(
        self, user_id: str, chat_id: str, version: int, recipe: Recipe
    ) -> RecipeBookEntry:
        """Create and store a new recipe-book entry. Does not itself
        enforce idempotency - see backend/services/chat_service.py's
        confirm_recipe(), which checks find_entry() first."""
        ...

    async def list_entries(self, user_id: str) -> list[RecipeBookEntry]:
        """This user's confirmed recipes, newest first."""
        ...

    async def get_entry(self, user_id: str, recipe_id: str) -> RecipeBookEntry | None:
        """One entry by its own id, or None if it doesn't exist OR belongs
        to a different user."""
        ...

    async def find_entry(self, chat_id: str, version: int) -> RecipeBookEntry | None:
        """The existing entry for this (chat_id, version), if that exact
        version was already confirmed - used to make confirm_recipe()
        idempotent."""
        ...


class InMemoryRecipeBookRepository:
    """Process-memory RecipeBookRepository. See InMemoryChatRepository's
    docstring for why this is scoped per FastAPI app instance."""

    def __init__(self) -> None:
        self._entries: dict[str, RecipeBookEntry] = {}

    async def save_entry(
        self, user_id: str, chat_id: str, version: int, recipe: Recipe
    ) -> RecipeBookEntry:
        entry = RecipeBookEntry(
            id=str(uuid.uuid4()),
            user_id=user_id,
            chat_id=chat_id,
            version=version,
            recipe=recipe,
            confirmed_at=datetime.now(UTC),
        )
        self._entries[entry.id] = entry
        return entry

    async def list_entries(self, user_id: str) -> list[RecipeBookEntry]:
        entries = [entry for entry in self._entries.values() if entry.user_id == user_id]
        entries.sort(key=lambda entry: entry.confirmed_at, reverse=True)
        return entries

    async def get_entry(self, user_id: str, recipe_id: str) -> RecipeBookEntry | None:
        entry = self._entries.get(recipe_id)
        if entry is None or entry.user_id != user_id:
            return None
        return entry

    async def find_entry(self, chat_id: str, version: int) -> RecipeBookEntry | None:
        for entry in self._entries.values():
            if entry.chat_id == chat_id and entry.version == version:
                return entry
        return None
