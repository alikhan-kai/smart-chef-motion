"""RecipeRepository protocol + in-memory stub.

Not wired into any endpoint yet; persistence is out of scope for this slice.
"""

import uuid
from typing import Protocol

from backend.schemas.recipe import Recipe


class RecipeRepository(Protocol):
    async def save(self, recipe: Recipe) -> str:
        """Persist a recipe and return its new id."""
        ...

    async def get(self, recipe_id: str) -> Recipe | None:
        """Fetch a recipe by id, or None if it does not exist."""
        ...


class InMemoryRecipeRepository:
    def __init__(self) -> None:
        self._recipes: dict[str, Recipe] = {}

    async def save(self, recipe: Recipe) -> str:
        recipe_id = str(uuid.uuid4())
        self._recipes[recipe_id] = recipe
        return recipe_id

    async def get(self, recipe_id: str) -> Recipe | None:
        return self._recipes.get(recipe_id)
