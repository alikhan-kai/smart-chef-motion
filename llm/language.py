"""Output-language instructions shared by generation and chat revisions."""

from typing import Literal

OutputLanguage = Literal["ru", "en", "kk"]
_NAMES = {"ru": "Russian", "en": "English", "kk": "Kazakh"}


def language_instruction(language: OutputLanguage | None) -> str:
    if language is None:
        return ""
    return (
        f"\n\nOUTPUT LANGUAGE: {_NAMES[language]} ({language}). "
        "The user selected this language in the app. It overrides language inference "
        "from the prompt, examples, search results, and conversation history. "
        "Write all generated user-facing text in this language: title, step headers, "
        "actions, final actions, ingredient names/forms/units, equipment, notes, "
        "errors, and answer_text. Keep schema keys, IDs, heat_level and fat.unit "
        "enum values, and canonical place identifiers unchanged. "
        "For revisions, apply this to new or changed text; preserve untouched fields."
    )
