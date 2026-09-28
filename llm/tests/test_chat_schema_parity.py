"""Fails if llm/chat_schemas.py diverges from llm/prompts/revise_schema.json.

Unlike test_schema_parity.py (which does a field-set/enum comparison against
a hand-written schema file), revise_schema.json was generated FROM
chat_schemas.py in the first place (see REPORT.md for why: OpenAI's
Responses API rejects the "oneOf"+"discriminator" shape Pydantic's own
strict-schema generator emits for a Union[...,  Field(discriminator=...)] -
confirmed with a real API call - so the checked-in file is that generator's
output with oneOf -> anyOf and the discriminator keyword stripped). That
means an exact regenerate-and-compare is the correct, and strongest
possible, parity check here.
"""

import json
from pathlib import Path
from typing import Any

from openai.lib._pydantic import to_strict_json_schema

from llm.chat_schemas import ChatResponse

SCHEMA_PATH = Path(__file__).parent.parent / "prompts" / "revise_schema.json"


def _strip_for_openai_strict_mode(node: Any) -> None:
    """Same transform used to originally generate revise_schema.json:
    oneOf -> anyOf (OpenAI's strict mode rejects "oneOf"), drop the
    "discriminator" keyword (not a JSON Schema keyword OpenAI recognizes),
    and drop "title"/"description" (cosmetic, Pydantic-added noise)."""
    if isinstance(node, dict):
        if "oneOf" in node:
            node["anyOf"] = node.pop("oneOf")
        node.pop("discriminator", None)
        node.pop("title", None)
        node.pop("description", None)
        for value in list(node.values()):
            _strip_for_openai_strict_mode(value)
    elif isinstance(node, list):
        for value in node:
            _strip_for_openai_strict_mode(value)


def _regenerate_schema() -> dict[str, Any]:
    schema = to_strict_json_schema(ChatResponse)
    _strip_for_openai_strict_mode(schema)
    return schema


def _load_checked_in_schema() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return raw["json_schema"]["schema"]  # type: ignore[no-any-return]


def test_revise_schema_matches_chat_schemas() -> None:
    assert _load_checked_in_schema() == _regenerate_schema()


def test_revise_schema_is_flat_responses_api_format() -> None:
    raw = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert raw["type"] == "json_schema"
    assert raw["json_schema"]["name"] == "chat_response"
    assert raw["json_schema"]["strict"] is True


def test_revise_schema_never_uses_oneOf_or_discriminator() -> None:
    # Both are rejected by the real API in strict mode (verified with a live
    # call - see REPORT.md); guard against a future regeneration reintroducing
    # them if openai's strict-schema generator changes its output shape.
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    assert "oneOf" not in text
    assert "discriminator" not in text


def test_revise_schema_ingredient_step_fat_match_recipe_schema() -> None:
    """Direct cross-file check that the reused Ingredient/Step/Fat shapes
    (required fields) are identical between recipe_schema.json and
    revise_schema.json - both are ultimately derived from llm/schemas.py,
    but this compares the two files directly rather than only transitively
    through their shared Pydantic source."""
    recipe_schema_path = SCHEMA_PATH.parent / "recipe_schema.json"
    recipe_raw = json.loads(recipe_schema_path.read_text(encoding="utf-8"))
    recipe_schema = recipe_raw["json_schema"]["schema"]

    revise_defs = _load_checked_in_schema()["$defs"]

    ingredient_required = recipe_schema["properties"]["ingredients"]["items"]["required"]
    assert set(revise_defs["RawIngredient"]["required"]) == set(ingredient_required)

    step_schema = recipe_schema["properties"]["steps"]["items"]
    assert set(revise_defs["RawStep"]["required"]) == set(step_schema["required"])

    fat_schema = step_schema["properties"]["fat"]
    assert set(revise_defs["RawFat"]["required"]) == set(fat_schema["required"])

    # Literal type aliases (HeatLevel, FatUnit) are inlined by Pydantic's
    # schema generator, not emitted as their own named $defs entry.
    heat_values = {v for v in step_schema["properties"]["heat_level"]["enum"] if v is not None}
    heat_level_prop = revise_defs["RawStep"]["properties"]["heat_level"]
    inlined_heat_values = {v for branch in heat_level_prop["anyOf"] for v in branch.get("enum", [])}
    assert inlined_heat_values == heat_values

    fat_unit_values = set(fat_schema["properties"]["unit"]["enum"])
    assert set(revise_defs["RawFat"]["properties"]["unit"]["enum"]) == fat_unit_values
