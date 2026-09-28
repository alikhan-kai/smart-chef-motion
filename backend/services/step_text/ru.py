"""Full-quality Russian display_text renderer.

Design (see REPORT.md for the full rationale and target examples):
- Start from step.action verbatim - never rewritten or paraphrased.
- If a used ingredient has a known amount that is not already mentioned in
  the action text, mention it once. For piece-counted ("шт") ingredients we
  *know how to decline* (ru_data.INGREDIENT_PLURAL_FORMS), replace the
  ingredient's existing word occurrence in the action with our own
  correctly-agreeing "<amount> <form>" (never trust the action's own word
  form to already agree with the amount - real model output sometimes uses
  a generic singular regardless of count). Every other ingredient - unknown
  nouns, or non-piece amount+unit ones - gets a short trailing clause
  instead, built from our own declension tables, since we cannot safely
  edit words we don't have a declension table for.
- Heat level and time are adverbial: they attach directly to the action with
  a space, no comma (e.g. "Разогрейте сковороду на среднем огне 1 минуту").
- Fat, salt and final_action are separate imperative clauses, each
  comma-joined onto the sentence, in that order.
"""

import re

from llm.schemas import RawFat, RawIngredient, RawStep

from .numbers import amount_already_mentioned, format_amount, plural_form, strip_trailing_period
from .ru_data import (
    FAT_GENITIVE,
    FAT_UNIT_FORMS,
    HEAT_PHRASES,
    INGREDIENT_PLURAL_FORMS,
    MINUTE_FORMS,
    SECOND_FORMS,
)


def _is_piece_unit(unit: str) -> bool:
    return unit.strip().rstrip(".").lower() == "шт"


def _format_time(minutes: float) -> str:
    total_seconds = round(minutes * 60)
    if total_seconds < 60:
        return f"{total_seconds} {plural_form(total_seconds, SECOND_FORMS)}"
    whole_minutes, seconds = divmod(total_seconds, 60)
    result = f"{whole_minutes} {plural_form(whole_minutes, MINUTE_FORMS)}"
    if seconds:
        result += f" {seconds} {plural_form(seconds, SECOND_FORMS)}"
    return result


def _format_fat(fat: RawFat) -> str:
    amount_str = format_amount(fat.amount)
    if fat.unit in FAT_UNIT_FORMS:
        unit_phrase = plural_form(fat.amount, FAT_UNIT_FORMS[fat.unit])
    else:
        unit_phrase = fat.unit
    genitive_type = FAT_GENITIVE.get(fat.type, fat.type)
    return f"{amount_str} {unit_phrase} {genitive_type}"


def _name_stem(name: str) -> str:
    stem = name.strip().lower()
    stem_len = max(3, len(stem) - 2)
    return stem[:stem_len]


def _find_word_span(action: str, name: str) -> tuple[int, int] | None:
    """Find the full existing word in `action` derived from `name`'s stem.

    Matches on a stem (name minus its last ~2 letters) so that "яйца"
    matches whatever inflected form ("яйцо", "яйца", ...) the model already
    used, then extends to the whole word so that word can be replaced
    wholesale rather than merely prefixed (see module docstring for why).
    """
    stem = _name_stem(name)
    if not stem:
        return None
    match = re.search(rf"(?<!\w){re.escape(stem)}[а-яёА-ЯЁ]*", action, re.IGNORECASE)
    return (match.start(), match.end()) if match else None


def _shares_identity(name: str, other: str) -> bool:
    """True if two free-text names plausibly refer to the same item.

    Used to stop an ingredient that is *also* described by the step's own
    `fat` field (real model output sometimes lists a fat both as a regular
    ingredient and as the structured `fat` object) from being mentioned a
    second time via the ingredient-amount logic below.
    """
    a, b = name.strip().lower(), other.strip().lower()
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def _ingredient_trailing_phrase(ingredient: RawIngredient) -> str:
    assert ingredient.amount is not None
    amount_str = format_amount(ingredient.amount)
    if _is_piece_unit(ingredient.unit):
        key = ingredient.name.strip().lower()
        forms = INGREDIENT_PLURAL_FORMS.get(key)
        if forms is not None:
            return f"{amount_str} {plural_form(ingredient.amount, forms)}"
        # Fall back to "<name> <amount> шт." when we don't know how to
        # decline this ingredient's name, per the task's explicit fallback.
        return f"{ingredient.name} {amount_str} шт."
    return f"{amount_str} {ingredient.unit} {ingredient.name}"


def render_ru(step: RawStep, ingredients_by_id: dict[str, RawIngredient]) -> str:
    action = strip_trailing_period(step.action)
    replacements: list[tuple[int, int, str]] = []
    trailing_ingredient_phrases: list[str] = []

    for ingredient_id in step.ingredients_used:
        ingredient = ingredients_by_id[ingredient_id]
        if ingredient.amount is None:
            continue
        if step.fat is not None and _shares_identity(ingredient.name, step.fat.type):
            # Already covered by the fat clause below; avoid double-mention.
            continue
        if amount_already_mentioned(action, ingredient.amount):
            continue
        # In-place replacement ("3 яйца") is only attempted for piece counts
        # whose declension we actually know (ru_data.INGREDIENT_PLURAL_FORMS)
        # - never trust the action's own existing word form to already
        # agree with the amount. Everything else (unknown nouns, or
        # amount+unit ingredients that always need a spelled-out unit) gets
        # a trailing clause instead.
        forms = INGREDIENT_PLURAL_FORMS.get(ingredient.name.strip().lower())
        if _is_piece_unit(ingredient.unit) and forms is not None:
            span = _find_word_span(action, ingredient.name)
            if span is not None:
                noun_form = plural_form(ingredient.amount, forms)
                replacement = f"{format_amount(ingredient.amount)} {noun_form}"
                replacements.append((span[0], span[1], replacement))
                continue
        trailing_ingredient_phrases.append(_ingredient_trailing_phrase(ingredient))

    for start, end, replacement in sorted(replacements, key=lambda item: item[0], reverse=True):
        action = action[:start] + replacement + action[end:]

    sentence = action

    adverbial: list[str] = []
    heat_phrase = HEAT_PHRASES.get(step.heat_level, step.heat_level) if step.heat_level else None
    if heat_phrase and heat_phrase.lower() not in action.lower():
        # The action itself sometimes already names the heat level
        # ("Разогрейте сковороду на среднем огне") - don't repeat it.
        adverbial.append(heat_phrase)
    if step.time_minutes is not None:
        adverbial.append(_format_time(step.time_minutes))
    if adverbial:
        sentence += " " + " ".join(adverbial)

    clauses = list(trailing_ingredient_phrases)
    if step.fat is not None and not amount_already_mentioned(action, step.fat.amount):
        # If the action already states the amount itself (e.g. "Добавьте 2
        # ст. л. масла..."), don't restate it in a separate clause.
        clauses.append(f"добавьте {_format_fat(step.fat)}")
    if step.salt:
        clauses.append("посолите")
    if step.final_action:
        clauses.append(f"затем {step.final_action}")

    for clause in clauses:
        sentence += ", " + clause

    return sentence.rstrip(".") + "."
