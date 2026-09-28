from typing import Literal

from pydantic import BaseModel, ConfigDict

from llm.schemas import RawIngredient, RawStep

Language = Literal["ru", "en", "kk"]
"""The recipe's display language. See backend/services/step_text/language.py
for how this is detected; docs/recipe_contract.md documents its behavior."""


class ComposedStep(RawStep):
    """A RawStep enriched with a rendered display_text in the recipe's language."""

    model_config = ConfigDict(extra="forbid")

    display_text: str


class Recipe(BaseModel):
    """The final, composed recipe returned by POST /recipes/create and /recipes/compose."""

    id: str
    language: Language
    title: str | None
    servings: int | None
    equipment: list[str] | None
    source_urls: list[str] | None
    notes: str | None
    ingredients: list[RawIngredient]
    steps: list[ComposedStep]
    total_time_minutes: float | None
    warnings: list[str]
