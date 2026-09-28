"""Language-neutral fallback renderer, for any recipe language other than
Russian.

Deliberately simple per spec: the step's action text followed by short,
UNINFLECTED parameter clauses, built from a small per-language Labels
dictionary. Adding a language is adding one Labels entry to LABELS below -
no renderer changes.
"""

from dataclasses import dataclass

from llm.schemas import RawStep

from .numbers import amount_already_mentioned, format_amount, strip_trailing_period


@dataclass(frozen=True)
class Labels:
    heat: dict[str, str]
    """heat_level enum value (Russian, from the schema) -> localized phrase,
    already including any preposition (e.g. "over medium heat")."""

    fat_unit: dict[str, str]
    """fat.unit enum value (Russian, from the schema) -> localized unit word."""

    minute_singular: str
    minute_plural: str
    second_singular: str
    second_plural: str
    time_prefix: str
    """Connector placed before a duration, e.g. "for"; "" if the language
    uses none."""

    salt_phrase: str
    fat_verb: str
    then_word: str
    unused_ingredient: str
    """format() template with a single {name} placeholder."""


EN = Labels(
    heat={
        "максимальный огонь": "over high heat",
        "средний огонь": "over medium heat",
        "малый огонь": "over low heat",
        "минимальный огонь": "over very low heat",
    },
    fat_unit={"ст. л.": "tbsp", "ч. л.": "tsp", "г": "g", "мл": "ml"},
    minute_singular="minute",
    minute_plural="minutes",
    second_singular="second",
    second_plural="seconds",
    time_prefix="for",
    salt_phrase="add salt",
    fat_verb="add",
    then_word="then",
    unused_ingredient="Ingredient '{name}' is not used in any step.",
)

KK = Labels(
    heat={
        "максимальный огонь": "ең жоғары от",
        "средний огонь": "орташа от",
        "малый огонь": "әлсіз от",
        "минимальный огонь": "ең әлсіз от",
    },
    fat_unit={"ст. л.": "ас қасық", "ч. л.": "шай қасық", "г": "г", "мл": "мл"},
    minute_singular="минут",
    minute_plural="минут",
    second_singular="секунд",
    second_plural="секунд",
    time_prefix="",
    salt_phrase="тұз қосыңыз",
    fat_verb="қосыңыз",
    then_word="содан кейін",
    unused_ingredient="«{name}» ингредиенті ешбір қадамда қолданылмайды.",
)

LABELS: dict[str, Labels] = {"en": EN, "kk": KK}


def _format_time_fallback(minutes: float, labels: Labels) -> str:
    total_seconds = round(minutes * 60)
    if total_seconds < 60:
        unit = labels.second_singular if total_seconds == 1 else labels.second_plural
        return f"{labels.time_prefix} {total_seconds} {unit}".strip()
    whole_minutes, seconds = divmod(total_seconds, 60)
    unit = labels.minute_singular if whole_minutes == 1 else labels.minute_plural
    result = f"{labels.time_prefix} {whole_minutes} {unit}".strip()
    if seconds:
        second_unit = labels.second_singular if seconds == 1 else labels.second_plural
        result += f" {seconds} {second_unit}"
    return result


def render_fallback(step: RawStep, language: str) -> str:
    labels = LABELS.get(language, LABELS["en"])
    action = strip_trailing_period(step.action)
    sentence = action

    clause_parts: list[str] = []
    heat_phrase = labels.heat.get(step.heat_level, step.heat_level) if step.heat_level else None
    if heat_phrase and heat_phrase.lower() not in action.lower():
        # The action itself sometimes already names the heat level - don't
        # repeat it (mirrors the same check in the Russian renderer).
        clause_parts.append(heat_phrase)
    if step.time_minutes is not None:
        clause_parts.append(_format_time_fallback(step.time_minutes, labels))
    if clause_parts:
        sentence += " " + " ".join(part for part in clause_parts if part)

    trailing: list[str] = []
    if step.fat is not None and not amount_already_mentioned(action, step.fat.amount):
        # If the action already states the amount itself, don't restate it.
        unit = labels.fat_unit.get(step.fat.unit, step.fat.unit)
        trailing.append(
            f"{labels.fat_verb} {format_amount(step.fat.amount)} {unit} {step.fat.type}"
        )
    if step.salt:
        trailing.append(labels.salt_phrase)
    if step.final_action:
        trailing.append(f"{labels.then_word} {step.final_action}")

    for clause in trailing:
        sentence += ", " + clause

    return sentence.rstrip(".") + "."


def unused_ingredient_warning(name: str, language: str) -> str:
    if language == "ru":
        return f"Ингредиент «{name}» не используется ни в одном шаге."
    labels = LABELS.get(language, LABELS["en"])
    return labels.unused_ingredient.format(name=name)
