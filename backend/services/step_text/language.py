"""Deterministic, script-based recipe language detection.

No dependency was added for this (see REPORT.md): the schema carries no
language field, and script-based detection is enough to route between the
full-quality Russian renderer and the language-neutral fallback.
"""

import re

from backend.schemas.recipe import Language
from llm.schemas import RawRecipe

_KAZAKH_ONLY_CHARS = set("ӘәҒғҚқҢңӨөҰұҮүҺһІі")
_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def detect_language(text: str) -> Language:
    """Cyrillic text with Kazakh-specific letters -> "kk"; other Cyrillic ->
    "ru"; anything else -> "en" (the catch-all fallback rendering path).

    Limits (deliberate, script-based only, no lexical analysis):
    - Cannot distinguish Russian from other Cyrillic languages that don't
      use the Kazakh-specific letters (e.g. Ukrainian, Belarusian).
    - Any non-Cyrillic, non-Latin script (Arabic, Chinese, ...) is bucketed
      into "en" even though it plainly is not English - it merely selects
      the uninflected fallback renderer, not a claim of accurate detection.
    """
    if any(ch in _KAZAKH_ONLY_CHARS for ch in text):
        return "kk"
    if _CYRILLIC_RE.search(text):
        return "ru"
    return "en"


def detect_recipe_language(raw: RawRecipe) -> Language:
    """Detect the recipe's language from its own text content.

    There is no language field on RawRecipe/RawRecipe request (recipe_schema.json
    was not changed to add one, per the task) and /recipes/compose receives
    only a RawRecipe body with no access to the original user prompt, so
    detection runs over the recipe's own free-text fields: title, notes, and
    every step's action/final_action.
    """
    fragments = [raw.title or "", raw.notes or ""]
    for step in raw.steps or []:
        fragments.append(step.action)
        if step.final_action:
            fragments.append(step.final_action)
    return detect_language(" ".join(fragments))
