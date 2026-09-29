"""RecipeBookRepository protocol + in-memory implementation.

See backend/repositories/chat_repo.py's module docstring for the same
"not a real database, scoped by user_id" caveats - they apply here too.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from supabase import Client

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


def _row_to_entry(row: dict[str, Any]) -> RecipeBookEntry:
    return RecipeBookEntry(
        id=row["id"],
        user_id=row["user_id"],
        chat_id=row["chat_id"],
        version=row["version"],
        recipe=Recipe.model_validate(row["recipe"]),
        confirmed_at=row["confirmed_at"],
    )


class SupabaseRecipeBookRepository:
    """RecipeBookRepository backed by the `recipe_book_entries` table (see
    docs/recipe_magazine_contract.md for the schema). Uses supabase-py's
    synchronous client under `asyncio.to_thread` so the class can present
    the same `async def` interface as InMemoryRecipeBookRepository."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def save_entry(
        self, user_id: str, chat_id: str, version: int, recipe: Recipe
    ) -> RecipeBookEntry:
        def _insert() -> dict[str, Any]:
            response = (
                self._client.table("recipe_book_entries")
                .insert(
                    {
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "version": version,
                        "recipe": recipe.model_dump(mode="json"),
                    }
                )
                .execute()
            )
            return cast(dict[str, Any], response.data[0])

        row = await asyncio.to_thread(_insert)
        return _row_to_entry(row)

    async def list_entries(self, user_id: str) -> list[RecipeBookEntry]:
        def _select() -> list[dict[str, Any]]:
            response = (
                self._client.table("recipe_book_entries")
                .select("*")
                .eq("user_id", user_id)
                .order("confirmed_at", desc=True)
                .execute()
            )
            return cast(list[dict[str, Any]], response.data)

        rows = await asyncio.to_thread(_select)
        return [_row_to_entry(row) for row in rows]

    async def get_entry(self, user_id: str, recipe_id: str) -> RecipeBookEntry | None:
        def _select() -> dict[str, Any] | None:
            response = (
                self._client.table("recipe_book_entries")
                .select("*")
                .eq("id", recipe_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = cast(list[dict[str, Any]], response.data)
            return rows[0] if rows else None

        row = await asyncio.to_thread(_select)
        return _row_to_entry(row) if row is not None else None

    async def find_entry(self, chat_id: str, version: int) -> RecipeBookEntry | None:
        def _select() -> dict[str, Any] | None:
            response = (
                self._client.table("recipe_book_entries")
                .select("*")
                .eq("chat_id", chat_id)
                .eq("version", version)
                .limit(1)
                .execute()
            )
            rows = cast(list[dict[str, Any]], response.data)
            return rows[0] if rows else None

        row = await asyncio.to_thread(_select)
        return _row_to_entry(row) if row is not None else None
