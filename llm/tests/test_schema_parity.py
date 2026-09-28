"""Fails if llm/schemas.py diverges from llm/prompts/recipe_schema.json.

recipe_schema.json is the single source of truth; this test compares required
field sets and enum values rather than doing a byte-for-byte JSON Schema diff,
since Pydantic's generated JSON Schema representation (anyOf/const, etc.) is
not textually identical to the strict json_schema-tool format used by the
Responses API.
"""

import json
from pathlib import Path
from typing import Any

from llm.schemas import RawFat, RawIngredient, RawRecipe, RawStep

SCHEMA_PATH = Path(__file__).parent.parent / "prompts" / "recipe_schema.json"


def _load_schema() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return raw["json_schema"]["schema"] if "json_schema" in raw else raw["schema"]  # type: ignore[no-any-return]


def test_top_level_required_fields_match_raw_recipe() -> None:
    schema = _load_schema()
    assert set(schema["required"]) == set(RawRecipe.model_fields.keys())
    assert set(schema["properties"].keys()) == set(RawRecipe.model_fields.keys())


def test_ingredient_required_fields_match_raw_ingredient() -> None:
    schema = _load_schema()
    ingredient_schema = schema["properties"]["ingredients"]["items"]
    assert set(ingredient_schema["required"]) == set(RawIngredient.model_fields.keys())


def test_step_required_fields_match_raw_step() -> None:
    schema = _load_schema()
    step_schema = schema["properties"]["steps"]["items"]
    assert set(step_schema["required"]) == set(RawStep.model_fields.keys())


def test_fat_required_fields_match_raw_fat() -> None:
    schema = _load_schema()
    fat_schema = schema["properties"]["steps"]["items"]["properties"]["fat"]
    assert set(fat_schema["required"]) == set(RawFat.model_fields.keys())


def test_heat_level_enum_matches() -> None:
    schema = _load_schema()
    heat_level_schema = schema["properties"]["steps"]["items"]["properties"]["heat_level"]
    schema_values = {v for v in heat_level_schema["enum"] if v is not None}

    model_values = set(RawStep.model_fields["heat_level"].annotation.__args__[0].__args__)  # type: ignore[union-attr]
    assert schema_values == model_values


def test_fat_unit_enum_matches() -> None:
    schema = _load_schema()
    fat_schema = schema["properties"]["steps"]["items"]["properties"]["fat"]
    unit_schema = fat_schema["properties"]["unit"]

    model_values = set(RawFat.model_fields["unit"].annotation.__args__)  # type: ignore[union-attr]
    assert set(unit_schema["enum"]) == model_values
