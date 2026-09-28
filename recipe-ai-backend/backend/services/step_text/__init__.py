"""Renders a RawStep's display_text in the recipe's detected language.

Public surface: render_step_display_text(), detect_recipe_language(),
unused_ingredient_warning(), and the Language type. Everything else here is
an implementation detail split across small modules (numbers/ru_data/ru for
the full-quality Russian renderer, labels for the language-neutral fallback,
language for detection) so each piece can be reworked independently.

No LLM call happens anywhere in this package - it only formats text that is
already present in the RawRecipe/RawStep produced by llm/.
"""

from backend.schemas.recipe import Language
from llm.schemas import RawIngredient, RawStep

from .labels import render_fallback, unused_ingredient_warning
from .language import detect_recipe_language
from .ru import render_ru

__all__ = [
    "Language",
    "detect_recipe_language",
    "render_step_display_text",
    "unused_ingredient_warning",
]


def render_step_display_text(
    step: RawStep,
    ingredients_by_id: dict[str, RawIngredient],
    language: Language,
) -> str:
    """Render a single natural-language sentence describing this step.

    Russian gets the full-quality renderer (number agreement, cases, time
    formatting). Every other language gets the language-neutral fallback:
    the step's own action text plus simple, uninflected parameter clauses
    built from a small per-language label dictionary.
    """
    if language == "ru":
        return render_ru(step, ingredients_by_id)
    return render_fallback(step, language)
