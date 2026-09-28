"""Pydantic models mirroring llm/prompts/recipe_schema.json exactly."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

HeatLevel = Literal["сильный", "средний", "слабый", "минимальный"]

FatUnit = Literal["ст. л.", "ч. л.", "г", "мл"]


class RawFat(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    amount: float
    unit: FatUnit


class RawIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    amount: float | None
    unit: str
    form: str | None


class RawStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_number: int
    header: str | None
    action: str
    ingredients_used: list[str]
    time_minutes: float | None
    passive: bool
    heat_level: HeatLevel | None
    place: str
    salt: bool
    fat: RawFat | None
    final_action: str | None


class RawRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: str | None
    title: str | None
    servings: int | None
    total_time_minutes: float | None
    equipment: list[str] | None
    source_urls: list[str] | None
    notes: str | None
    ingredients: list[RawIngredient] | None
    steps: list[RawStep] | None
