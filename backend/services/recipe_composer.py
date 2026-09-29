"""Programmatic composition of a RawRecipe into the final Recipe.

No LLM call happens here or anywhere in this module: the model has already
produced the RawRecipe (llm.schemas) via llm/recipe_generator.py, and
compose_recipe() only assembles/validates/renders it. All display-text
rendering lives in backend.services.step_text, so it can be reworked
independently of this composition logic.
"""

import uuid

from backend.schemas.recipe import ComposedStep, Recipe
from backend.services.step_text import (
    detect_recipe_language,
    render_step_display_text,
    unused_ingredient_warning,
)
from llm.errors import ModelReportedError
from llm.schemas import RawRecipe, RawStep


class CompositionError(Exception):
    """Base class for errors raised while composing a Recipe from a RawRecipe."""


class UnknownIngredientError(CompositionError):
    """A step references an ingredient id that is not present in ingredients."""


def _compute_total_time_minutes(model_total: float | None, steps: list[RawStep]) -> float | None:
    if model_total is not None:
        return model_total

    active_steps = [step for step in steps if not step.passive]
    if any(step.time_minutes is None for step in active_steps):
        return None

    total = sum(step.time_minutes for step in steps if step.time_minutes is not None)
    return round(total, 2)


async def compose_recipe(raw: RawRecipe) -> Recipe:
    if raw.error is not None:
        raise ModelReportedError(raw.error)

    ingredients = raw.ingredients or []
    steps = raw.steps or []

    ingredients_by_id = {ingredient.id: ingredient for ingredient in ingredients}
    # LLMs occasionally hallucinate and put the ingredient 'name' in ingredients_used instead of 'id'
    ingredients_by_name = {ingredient.name.lower(): ingredient.id for ingredient in ingredients}

    used_ids: set[str] = set()
    for step in steps:
        corrected_used_ids = []
        for ingredient_ref in step.ingredients_used:
            if ingredient_ref in ingredients_by_id:
                corrected_used_ids.append(ingredient_ref)
                used_ids.add(ingredient_ref)
            elif ingredient_ref.lower() in ingredients_by_name:
                actual_id = ingredients_by_name[ingredient_ref.lower()]
                corrected_used_ids.append(actual_id)
                used_ids.add(actual_id)
            else:
                raise UnknownIngredientError(
                    f"Step {step.step_number} references unknown ingredient id '{ingredient_ref}'"
                )
        step.ingredients_used = corrected_used_ids

    language = detect_recipe_language(raw)

    warnings = [
        unused_ingredient_warning(ingredient.name, language)
        for ingredient in ingredients
        if ingredient.id not in used_ids
    ]

    composed_steps = [
        ComposedStep(
            **{**step.model_dump(), "step_number": index},
            display_text=render_step_display_text(step, ingredients_by_id, language),
        )
        for index, step in enumerate(steps, start=1)
    ]

    total_time_minutes = _compute_total_time_minutes(raw.total_time_minutes, steps)

    return Recipe(
        id=str(uuid.uuid4()),
        language=language,
        title=raw.title,
        servings=raw.servings,
        equipment=raw.equipment,
        source_urls=raw.source_urls,
        notes=raw.notes,
        ingredients=ingredients,
        steps=composed_steps,
        total_time_minutes=total_time_minutes,
        warnings=warnings,
    )
