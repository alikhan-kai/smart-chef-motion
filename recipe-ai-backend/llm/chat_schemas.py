"""Pydantic models for the chat/revision LLM call, mirroring
llm/prompts/revise_schema.json exactly (parity enforced by
llm/tests/test_chat_schema_parity.py, same approach as
llm/tests/test_schema_parity.py for the recipe schema).

Strict structured outputs (OpenAI Responses API, text.format json_schema,
strict=true) cannot express a partial object with optional keys: every
property listed in an object schema must be listed in "required" (nullable
is fine, "optional" is not) - see REPORT.md for the verification against
current docs. So a `fields` partial update is expressed as a LIST of small
{field, value} objects, one typed variant per updatable field, combined
with Pydantic's discriminated union (`field` is a single-value Literal in
each variant, which anyOf-of-objects-with-a-tag-enum expresses cleanly in
strict mode). Each entity here (Ingredient/Step/Meta) has a small, fixed
field set, which is what makes this approach practical rather than clumsy.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from llm.schemas import FatUnit, HeatLevel, RawFat, RawIngredient, RawStep

# --- Ingredient field updates -----------------------------------------------


class IngredientNameUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["name"]
    value: str


class IngredientAmountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["amount"]
    value: float | None


class IngredientUnitUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["unit"]
    value: str


class IngredientFormUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["form"]
    value: str | None


IngredientFieldUpdate = Annotated[
    IngredientNameUpdate | IngredientAmountUpdate | IngredientUnitUpdate | IngredientFormUpdate,
    Field(discriminator="field"),
]

# --- Step field updates ------------------------------------------------------


class StepActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["action"]
    value: str


class StepIngredientsUsedUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["ingredients_used"]
    value: list[str]


class StepTimeMinutesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["time_minutes"]
    value: float | None


class StepPassiveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["passive"]
    value: bool


class StepHeatLevelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["heat_level"]
    value: HeatLevel | None


class StepPlaceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["place"]
    value: str


class StepSaltUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["salt"]
    value: bool


class StepFatUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["fat"]
    value: RawFat | None


class StepFinalActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["final_action"]
    value: str | None


StepFieldUpdate = Annotated[
    StepActionUpdate
    | StepIngredientsUsedUpdate
    | StepTimeMinutesUpdate
    | StepPassiveUpdate
    | StepHeatLevelUpdate
    | StepPlaceUpdate
    | StepSaltUpdate
    | StepFatUpdate
    | StepFinalActionUpdate,
    Field(discriminator="field"),
]

# --- Recipe-meta field updates ----------------------------------------------


class MetaTitleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["title"]
    value: str | None


class MetaServingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["servings"]
    value: int | None


class MetaTotalTimeMinutesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["total_time_minutes"]
    value: float | None


class MetaEquipmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["equipment"]
    value: list[str] | None


class MetaNotesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Literal["notes"]
    value: str | None


MetaFieldUpdate = Annotated[
    MetaTitleUpdate
    | MetaServingsUpdate
    | MetaTotalTimeMinutesUpdate
    | MetaEquipmentUpdate
    | MetaNotesUpdate,
    Field(discriminator="field"),
]

# --- Operations ---------------------------------------------------------------


class UpdateIngredientOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["update_ingredient"]
    ingredient_id: str
    fields: list[IngredientFieldUpdate]


class AddIngredientOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["add_ingredient"]
    ingredient: RawIngredient


class RemoveIngredientOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["remove_ingredient"]
    ingredient_id: str


class UpdateStepOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["update_step"]
    step_number: int
    fields: list[StepFieldUpdate]


class AddStepOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["add_step"]
    after_step_number: int
    """0 = insert at the beginning. Refers to the ORIGINAL (pre-patch)
    numbering - see backend/services/recipe_patch.py."""
    step: RawStep
    """step.step_number is ignored by the patch engine; steps are always
    renumbered 1..N after all operations are applied."""


class RemoveStepOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["remove_step"]
    step_number: int


class UpdateMetaOp(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: Literal["update_meta"]
    fields: list[MetaFieldUpdate]


Operation = Annotated[
    UpdateIngredientOp
    | AddIngredientOp
    | RemoveIngredientOp
    | UpdateStepOp
    | AddStepOp
    | RemoveStepOp
    | UpdateMetaOp,
    Field(discriminator="op"),
]

# --- Top-level chat response --------------------------------------------------


class ChatResponse(BaseModel):
    """LLM output for llm.chat_responder.respond_to_message()."""

    model_config = ConfigDict(extra="forbid")

    intent: Literal["answer", "revise"]
    answer_text: str
    operations: list[Operation] | None


class HistoryMessage(BaseModel):
    """One prior chat message, passed as context. Not part of the strict
    schema - this is an *input* shape, not model output."""

    role: Literal["user", "assistant"]
    content: str


__all__ = [
    "ChatResponse",
    "FatUnit",
    "HeatLevel",
    "HistoryMessage",
    "IngredientFieldUpdate",
    "MetaFieldUpdate",
    "Operation",
    "StepFieldUpdate",
]
