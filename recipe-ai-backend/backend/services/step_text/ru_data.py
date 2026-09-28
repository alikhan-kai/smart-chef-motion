"""Russian vocabulary/declension tables used by ru.py.

These are hand-written, deliberately small dictionaries covering the common
cases (see REPORT.md for the rationale on why a full morphological analyzer
was not used). Unknown items fall back to a plain, still-grammatical form.
"""

from typing import Final

# heat_level enum value (from llm/prompts/recipe_schema.json) -> Russian
# adverbial phrase ("on medium heat").
HEAT_PHRASES: Final[dict[str, str]] = {
    "максимальный огонь": "на максимальном огне",
    "средний огонь": "на среднем огне",
    "малый огонь": "на малом огне",
    "минимальный огонь": "на минимальном огне",
}

# Accusative (duration) forms: (one, few, many).
MINUTE_FORMS: Final[tuple[str, str, str]] = ("минуту", "минуты", "минут")
SECOND_FORMS: Final[tuple[str, str, str]] = ("секунду", "секунды", "секунд")

# fat.unit enum value -> accusative noun forms (one, few, many) for
# "добавьте <N> <unit> <fat, genitive>". Units without a spelled-out form
# here (г, мл) are kept as the raw abbreviation.
FAT_UNIT_FORMS: Final[dict[str, tuple[str, str, str]]] = {
    "ст. л.": ("столовую ложку", "столовые ложки", "столовых ложек"),
    "ч. л.": ("чайную ложку", "чайные ложки", "чайных ложек"),
}

# fat.type (nominative, free text from the model) -> genitive, for common
# fats. Unknown types fall back to the raw (nominative) text, per spec.
FAT_GENITIVE: Final[dict[str, str]] = {
    "подсолнечное масло": "подсолнечного масла",
    "сливочное масло": "сливочного масла",
    "оливковое масло": "оливкового масла",
    "растительное масло": "растительного масла",
    "кунжутное масло": "кунжутного масла",
    "топлёное масло": "топлёного масла",
    "арахисовое масло": "арахисового масла",
    "кокосовое масло": "кокосового масла",
    "льняное масло": "льняного масла",
    "свиной жир": "свиного жира",
    "гусиный жир": "гусиного жира",
}

# ingredient.name (lowercased, nominative singular or plural as the model
# might write it) -> (one, few, many) forms, for countable ("шт") items
# whose name does not already appear (in some inflected form) in the step's
# action text and therefore needs to be rendered as a fresh trailing clause.
INGREDIENT_PLURAL_FORMS: Final[dict[str, tuple[str, str, str]]] = {
    "яйцо": ("яйцо", "яйца", "яиц"),
    "яйца": ("яйцо", "яйца", "яиц"),
    "помидор": ("помидор", "помидора", "помидоров"),
    "помидоры": ("помидор", "помидора", "помидоров"),
    "огурец": ("огурец", "огурца", "огурцов"),
    "огурцы": ("огурец", "огурца", "огурцов"),
    "перец": ("перец", "перца", "перцев"),
    "лимон": ("лимон", "лимона", "лимонов"),
    "лимоны": ("лимон", "лимона", "лимонов"),
    "луковица": ("луковица", "луковицы", "луковиц"),
    "картофелина": ("картофелина", "картофелины", "картофелин"),
    "морковь": ("морковь", "моркови", "моркови"),
}
