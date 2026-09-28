"""Pure, deterministic patch engine: apply_operations(recipe, operations) -> PatchResult.

No LLM call, no I/O. Operates on and returns llm.schemas.RawRecipe - "the
existing recipe JSON is modified" (task wording): revisions patch the raw
JSON, they never regenerate it.

Ordering (documented, since operations reference the recipe as it was
BEFORE the patch - see llm/prompts/revise_system_prompt.md, "НУМЕРАЦИЯ
ШАГОВ"):
1. All ingredient_id/step_number references in every operation are resolved
   against the ORIGINAL (pre-patch) recipe - built once, up front, before
   any operation is applied.
2. Operations are applied in a fixed order regardless of the order the
   model returned them in: remove_ingredient, update_ingredient,
   add_ingredient, remove_step, update_step, add_step, update_meta. This
   makes the result deterministic even for a list mixing several op types,
   and means e.g. a remove_ingredient + update_ingredient pair for the same
   id always fails predictably (removal wins, the update then targets a
   gone id and raises PatchError) rather than depending on list order.
3. Steps are renumbered 1..N, in final order, after every operation has
   been applied.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from llm.chat_schemas import Operation
from llm.schemas import RawIngredient, RawRecipe, RawStep


class PatchError(Exception):
    """A patch operation could not be applied (bad reference, resulting
    recipe invalid, etc). Callers retry the model once with this message."""


ChangeKind = Literal[
    "ingredient_added",
    "ingredient_removed",
    "ingredient_changed",
    "step_added",
    "step_removed",
    "step_changed",
    "meta_changed",
]


class ChangeLogEntry(BaseModel):
    """One entry in the structured diff returned to the frontend."""

    model_config = ConfigDict(extra="forbid")

    kind: ChangeKind
    target: str | None
    """ingredient id / original step number (as a string) / meta field name."""
    before: Any = None
    after: Any = None


class PatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe: RawRecipe
    change_log: list[ChangeLogEntry]
    warnings: list[str]
    """Ingredients that became unused by this patch (id/name), for immediate
    feedback; compose_recipe() recomputes localized warnings independently
    when the patched recipe is composed afterward."""


def renumber_steps(steps: list[RawStep]) -> list[RawStep]:
    """Renumber `steps` 1..N in place order, without touching any other field."""
    return [step.model_copy(update={"step_number": index}) for index, step in enumerate(steps, 1)]


def _apply_field_updates(data: dict[str, Any], fields: list[Any]) -> dict[str, Any]:
    updated = dict(data)
    for field_update in fields:
        updated[field_update.field] = field_update.value
    return updated


def apply_operations(recipe: RawRecipe, operations: list[Operation]) -> PatchResult:
    """Apply `operations` to a deep copy of `recipe`; never mutates `recipe`."""
    ingredients = [ingredient.model_copy(deep=True) for ingredient in (recipe.ingredients or [])]
    steps = [step.model_copy(deep=True) for step in (recipe.steps or [])]

    ingredients_by_id = {ingredient.id: ingredient for ingredient in ingredients}
    steps_by_number = {step.step_number: step for step in steps}
    original_step_numbers = set(steps_by_number)

    change_log: list[ChangeLogEntry] = []
    removed_step_numbers: set[int] = set()
    insertions_after: dict[int, list[RawStep]] = {}
    meta_updates: dict[str, Any] = {}

    def _by_op(op_name: str) -> list[Any]:
        return [op for op in operations if op.op == op_name]

    for op in _by_op("remove_ingredient"):
        if op.ingredient_id not in ingredients_by_id:
            raise PatchError(f"remove_ingredient: unknown ingredient_id '{op.ingredient_id}'")
        removed = ingredients_by_id.pop(op.ingredient_id)
        change_log.append(
            ChangeLogEntry(
                kind="ingredient_removed", target=op.ingredient_id, before=removed, after=None
            )
        )

    for op in _by_op("update_ingredient"):
        if op.ingredient_id not in ingredients_by_id:
            raise PatchError(f"update_ingredient: unknown ingredient_id '{op.ingredient_id}'")
        before = ingredients_by_id[op.ingredient_id]
        data = _apply_field_updates(before.model_dump(), op.fields)
        try:
            after = RawIngredient.model_validate(data)
        except ValidationError as exc:
            raise PatchError(
                f"update_ingredient: resulting ingredient '{op.ingredient_id}' is invalid: {exc}"
            ) from exc
        ingredients_by_id[op.ingredient_id] = after
        change_log.append(
            ChangeLogEntry(
                kind="ingredient_changed", target=op.ingredient_id, before=before, after=after
            )
        )

    for op in _by_op("add_ingredient"):
        if op.ingredient.id in ingredients_by_id:
            raise PatchError(f"add_ingredient: duplicate ingredient id '{op.ingredient.id}'")
        ingredients_by_id[op.ingredient.id] = op.ingredient
        change_log.append(
            ChangeLogEntry(
                kind="ingredient_added", target=op.ingredient.id, before=None, after=op.ingredient
            )
        )

    for op in _by_op("remove_step"):
        if op.step_number not in steps_by_number:
            raise PatchError(f"remove_step: unknown step_number {op.step_number}")
        removed_step_numbers.add(op.step_number)
        change_log.append(
            ChangeLogEntry(
                kind="step_removed",
                target=str(op.step_number),
                before=steps_by_number[op.step_number],
                after=None,
            )
        )

    for op in _by_op("update_step"):
        if op.step_number not in steps_by_number:
            raise PatchError(f"update_step: unknown step_number {op.step_number}")
        if op.step_number in removed_step_numbers:
            raise PatchError(f"update_step: step {op.step_number} was removed by this patch")
        step_before = steps_by_number[op.step_number]
        step_data = _apply_field_updates(step_before.model_dump(), op.fields)
        try:
            step_after = RawStep.model_validate(step_data)
        except ValidationError as exc:
            raise PatchError(
                f"update_step: resulting step {op.step_number} is invalid: {exc}"
            ) from exc
        steps_by_number[op.step_number] = step_after
        change_log.append(
            ChangeLogEntry(
                kind="step_changed",
                target=str(op.step_number),
                before=step_before,
                after=step_after,
            )
        )

    for op in _by_op("add_step"):
        if op.after_step_number != 0 and op.after_step_number not in original_step_numbers:
            raise PatchError(f"add_step: unknown after_step_number {op.after_step_number}")
        insertions_after.setdefault(op.after_step_number, []).append(op.step)
        change_log.append(
            ChangeLogEntry(kind="step_added", target=None, before=None, after=op.step)
        )

    for op in _by_op("update_meta"):
        for field_update in op.fields:
            meta_updates[field_update.field] = field_update.value
            change_log.append(
                ChangeLogEntry(
                    kind="meta_changed",
                    target=field_update.field,
                    before=getattr(recipe, field_update.field),
                    after=field_update.value,
                )
            )

    known_ops = {
        "remove_ingredient",
        "update_ingredient",
        "add_ingredient",
        "remove_step",
        "update_step",
        "add_step",
        "update_meta",
    }
    unknown = [op.op for op in operations if op.op not in known_ops]
    if unknown:  # pragma: no cover - guarded by the strict schema, kept for safety
        raise PatchError(f"unknown operation type(s): {unknown}")

    final_steps: list[RawStep] = list(insertions_after.get(0, []))
    for original_number in sorted(original_step_numbers):
        if original_number not in removed_step_numbers:
            final_steps.append(steps_by_number[original_number])
        final_steps.extend(insertions_after.get(original_number, []))
    final_steps = renumber_steps(final_steps)

    final_ingredients = list(ingredients_by_id.values())
    ingredient_ids = {ingredient.id for ingredient in final_ingredients}
    if len(ingredient_ids) != len(final_ingredients):
        raise PatchError("duplicate ingredient ids after patch")

    for step in final_steps:
        for used_id in step.ingredients_used:
            if used_id not in ingredient_ids:
                raise PatchError(
                    f"step {step.step_number} references unknown ingredient id '{used_id}'"
                )

    updated_fields: dict[str, Any] = {
        **meta_updates,
        "ingredients": final_ingredients,
        "steps": final_steps,
    }
    try:
        new_recipe = RawRecipe.model_validate({**recipe.model_dump(), **updated_fields})
    except ValidationError as exc:
        raise PatchError(f"patched recipe failed validation: {exc}") from exc

    used_ids = {used_id for step in final_steps for used_id in step.ingredients_used}
    warnings = [
        f"Ingredient '{ingredient.name}' (id={ingredient.id}) is unused after this revision"
        for ingredient in final_ingredients
        if ingredient.id not in used_ids
    ]

    return PatchResult(recipe=new_recipe, change_log=change_log, warnings=warnings)
