"""Unit tests for the patch engine: backend/services/recipe_patch.py.

Pure/deterministic, no mocking needed - every test builds a RawRecipe fixture
and a list of Operation objects and asserts on the resulting PatchResult.
"""

import pytest

from backend.services.recipe_patch import PatchError, apply_operations
from llm.chat_schemas import (
    AddIngredientOp,
    AddStepOp,
    IngredientAmountUpdate,
    IngredientNameUpdate,
    MetaNotesUpdate,
    MetaServingsUpdate,
    MetaTitleUpdate,
    RemoveIngredientOp,
    RemoveStepOp,
    StepActionUpdate,
    StepFatUpdate,
    StepFinalActionUpdate,
    StepHeatLevelUpdate,
    StepIngredientsUsedUpdate,
    StepSaltUpdate,
    UpdateIngredientOp,
    UpdateMetaOp,
    UpdateStepOp,
)
from llm.schemas import RawFat, RawIngredient, RawRecipe, RawStep


def _ingredient(id_: str, name: str, amount: float | None = 1, unit: str = "г") -> RawIngredient:
    return RawIngredient(id=id_, name=name, amount=amount, unit=unit, form=None)


def _ingredients(recipe: RawRecipe) -> list[RawIngredient]:
    assert recipe.ingredients is not None
    return recipe.ingredients


def _steps(recipe: RawRecipe) -> list[RawStep]:
    assert recipe.steps is not None
    return recipe.steps


def _step(
    step_number: int,
    action: str,
    ingredients_used: list[str] | None = None,
    **overrides: object,
) -> RawStep:
    defaults: dict[str, object] = {
        "step_number": step_number,
        "action": action,
        "ingredients_used": ingredients_used or [],
        "time_minutes": None,
        "passive": False,
        "heat_level": None,
        "place": "сковорода",
        "salt": False,
        "fat": None,
        "final_action": None,
    }
    defaults.update(overrides)
    return RawStep(**defaults)  # type: ignore[arg-type]


def _recipe(
    ingredients: list[RawIngredient], steps: list[RawStep], **overrides: object
) -> RawRecipe:
    defaults: dict[str, object] = {
        "error": None,
        "title": "Омлет",
        "servings": 2,
        "total_time_minutes": None,
        "equipment": ["сковорода"],
        "source_urls": [],
        "notes": None,
        "ingredients": ingredients,
        "steps": steps,
    }
    defaults.update(overrides)
    return RawRecipe(**defaults)  # type: ignore[arg-type]


BASE_RECIPE = _recipe(
    ingredients=[
        _ingredient("eggs", "яйца", amount=3, unit="шт"),
        _ingredient("milk", "молоко", amount=50, unit="мл"),
        _ingredient("salt1", "соль", amount=None, unit="по вкусу"),
    ],
    steps=[
        _step(1, "Взбить яйца с молоком", ingredients_used=["eggs", "milk"]),
        _step(2, "Посолить и вылить на сковороду", ingredients_used=["salt1"], salt=True),
        _step(3, "Жарить до готовности"),
    ],
)


# ---------------------------------------------------------------------------
# Input is never mutated
# ---------------------------------------------------------------------------


def test_apply_operations_does_not_mutate_input() -> None:
    original_dump = BASE_RECIPE.model_dump()
    apply_operations(
        BASE_RECIPE,
        [
            RemoveIngredientOp(op="remove_ingredient", ingredient_id="salt1"),
            UpdateStepOp(
                op="update_step",
                step_number=2,
                fields=[StepIngredientsUsedUpdate(field="ingredients_used", value=[])],
            ),
        ],
    )
    assert BASE_RECIPE.model_dump() == original_dump


# ---------------------------------------------------------------------------
# Each op type
# ---------------------------------------------------------------------------


def test_update_ingredient_changes_only_given_fields() -> None:
    result = apply_operations(
        BASE_RECIPE,
        [
            UpdateIngredientOp(
                op="update_ingredient",
                ingredient_id="eggs",
                fields=[IngredientAmountUpdate(field="amount", value=4)],
            )
        ],
    )
    eggs = next(i for i in _ingredients(result.recipe) if i.id == "eggs")
    assert eggs.amount == 4
    assert eggs.name == "яйца"  # untouched
    assert eggs.unit == "шт"  # untouched
    entry = next(e for e in result.change_log if e.kind == "ingredient_changed")
    assert entry.target == "eggs"
    assert entry.before.amount == 3
    assert entry.after.amount == 4


def test_add_ingredient() -> None:
    new_ingredient = _ingredient("pepper", "перец", amount=1, unit="шт")
    result = apply_operations(
        BASE_RECIPE, [AddIngredientOp(op="add_ingredient", ingredient=new_ingredient)]
    )
    ids = {i.id for i in _ingredients(result.recipe)}
    assert "pepper" in ids
    assert len(_ingredients(result.recipe)) == 4
    entry = next(e for e in result.change_log if e.kind == "ingredient_added")
    assert entry.target == "pepper"


def test_add_ingredient_duplicate_id_raises() -> None:
    dup = _ingredient("eggs", "яйца 2", amount=1, unit="шт")
    with pytest.raises(PatchError):
        apply_operations(BASE_RECIPE, [AddIngredientOp(op="add_ingredient", ingredient=dup)])


def test_remove_ingredient() -> None:
    result = apply_operations(
        BASE_RECIPE,
        [
            RemoveIngredientOp(op="remove_ingredient", ingredient_id="salt1"),
            UpdateStepOp(
                op="update_step",
                step_number=2,
                fields=[StepIngredientsUsedUpdate(field="ingredients_used", value=[])],
            ),
        ],
    )
    ids = {i.id for i in _ingredients(result.recipe)}
    assert "salt1" not in ids
    assert len(_ingredients(result.recipe)) == 2


def test_remove_ingredient_unknown_id_raises() -> None:
    with pytest.raises(PatchError):
        apply_operations(
            BASE_RECIPE,
            [RemoveIngredientOp(op="remove_ingredient", ingredient_id="does_not_exist")],
        )


def test_update_step_changes_only_given_fields() -> None:
    result = apply_operations(
        BASE_RECIPE,
        [
            UpdateStepOp(
                op="update_step",
                step_number=1,
                fields=[StepActionUpdate(field="action", value="Взбить яйца венчиком")],
            )
        ],
    )
    step1 = _steps(result.recipe)[0]
    assert step1.action == "Взбить яйца венчиком"
    assert step1.ingredients_used == ["eggs", "milk"]  # untouched


def test_update_step_unknown_number_raises() -> None:
    with pytest.raises(PatchError):
        apply_operations(
            BASE_RECIPE,
            [
                UpdateStepOp(
                    op="update_step",
                    step_number=99,
                    fields=[StepSaltUpdate(field="salt", value=True)],
                )
            ],
        )


def test_update_step_fat_field() -> None:
    result = apply_operations(
        BASE_RECIPE,
        [
            UpdateStepOp(
                op="update_step",
                step_number=3,
                fields=[
                    StepFatUpdate(
                        field="fat", value=RawFat(type="сливочное масло", amount=10, unit="г")
                    )
                ],
            )
        ],
    )
    step3 = _steps(result.recipe)[2]
    assert step3.fat is not None
    assert step3.fat.type == "сливочное масло"


def test_remove_step_and_renumbering() -> None:
    result = apply_operations(BASE_RECIPE, [RemoveStepOp(op="remove_step", step_number=2)])
    assert [s.step_number for s in _steps(result.recipe)] == [1, 2]
    assert [s.action for s in _steps(result.recipe)] == [
        "Взбить яйца с молоком",
        "Жарить до готовности",
    ]


def test_remove_step_unknown_number_raises() -> None:
    with pytest.raises(PatchError):
        apply_operations(BASE_RECIPE, [RemoveStepOp(op="remove_step", step_number=99)])


def test_update_removed_step_raises() -> None:
    with pytest.raises(PatchError):
        apply_operations(
            BASE_RECIPE,
            [
                RemoveStepOp(op="remove_step", step_number=2),
                UpdateStepOp(
                    op="update_step",
                    step_number=2,
                    fields=[StepSaltUpdate(field="salt", value=False)],
                ),
            ],
        )


def test_add_step_at_beginning() -> None:
    new_step = _step(999, "Разогреть сковороду")
    result = apply_operations(
        BASE_RECIPE, [AddStepOp(op="add_step", after_step_number=0, step=new_step)]
    )
    assert [s.step_number for s in _steps(result.recipe)] == [1, 2, 3, 4]
    assert _steps(result.recipe)[0].action == "Разогреть сковороду"
    assert _steps(result.recipe)[1].action == "Взбить яйца с молоком"


def test_add_step_in_middle() -> None:
    new_step = _step(999, "Добавить перец")
    result = apply_operations(
        BASE_RECIPE, [AddStepOp(op="add_step", after_step_number=1, step=new_step)]
    )
    actions = [s.action for s in _steps(result.recipe)]
    assert actions == [
        "Взбить яйца с молоком",
        "Добавить перец",
        "Посолить и вылить на сковороду",
        "Жарить до готовности",
    ]
    assert [s.step_number for s in _steps(result.recipe)] == [1, 2, 3, 4]


def test_add_step_ignores_models_own_step_number() -> None:
    new_step = _step(42, "Новый шаг")  # arbitrary step_number, must be ignored
    result = apply_operations(
        BASE_RECIPE, [AddStepOp(op="add_step", after_step_number=3, step=new_step)]
    )
    added = _steps(result.recipe)[-1]
    assert added.step_number == 4
    assert added.action == "Новый шаг"


def test_add_step_unknown_after_step_number_raises() -> None:
    new_step = _step(1, "X")
    with pytest.raises(PatchError):
        apply_operations(
            BASE_RECIPE, [AddStepOp(op="add_step", after_step_number=99, step=new_step)]
        )


def test_multiple_add_steps_after_same_anchor_keep_operation_order() -> None:
    step_a = _step(1, "Шаг A")
    step_b = _step(1, "Шаг B")
    result = apply_operations(
        BASE_RECIPE,
        [
            AddStepOp(op="add_step", after_step_number=0, step=step_a),
            AddStepOp(op="add_step", after_step_number=0, step=step_b),
        ],
    )
    assert [s.action for s in _steps(result.recipe)[:2]] == ["Шаг A", "Шаг B"]


def test_add_step_after_a_removed_step_still_anchors_correctly() -> None:
    new_step = _step(1, "Добавить специи")
    result = apply_operations(
        BASE_RECIPE,
        [
            RemoveStepOp(op="remove_step", step_number=2),
            AddStepOp(op="add_step", after_step_number=2, step=new_step),
        ],
    )
    actions = [s.action for s in _steps(result.recipe)]
    # step 2 was removed, but the new step still lands "after where step 2 was"
    assert actions == ["Взбить яйца с молоком", "Добавить специи", "Жарить до готовности"]


def test_update_meta_partial() -> None:
    result = apply_operations(
        BASE_RECIPE,
        [
            UpdateMetaOp(
                op="update_meta",
                fields=[
                    MetaTitleUpdate(field="title", value="Пышный омлет"),
                    MetaServingsUpdate(field="servings", value=4),
                ],
            )
        ],
    )
    assert result.recipe.title == "Пышный омлет"
    assert result.recipe.servings == 4
    assert result.recipe.equipment == ["сковорода"]  # untouched


def test_update_meta_can_set_notes_to_null() -> None:
    recipe = _recipe(
        ingredients=[_ingredient("a", "a")], steps=[_step(1, "Шаг", ["a"])], notes="старая заметка"
    )
    result = apply_operations(
        recipe,
        [UpdateMetaOp(op="update_meta", fields=[MetaNotesUpdate(field="notes", value=None)])],
    )
    assert result.recipe.notes is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_step_referencing_removed_ingredient_raises() -> None:
    # eggs is removed but step 1 still references it and is not updated.
    with pytest.raises(PatchError):
        apply_operations(
            BASE_RECIPE, [RemoveIngredientOp(op="remove_ingredient", ingredient_id="eggs")]
        )


def test_new_step_referencing_unknown_ingredient_raises() -> None:
    bad_step = _step(999, "Что-то", ingredients_used=["does_not_exist"])
    with pytest.raises(PatchError):
        apply_operations(
            BASE_RECIPE, [AddStepOp(op="add_step", after_step_number=0, step=bad_step)]
        )


def test_step_numbers_always_contiguous_after_combined_ops() -> None:
    new_step = _step(1, "Добавить зелень")
    result = apply_operations(
        BASE_RECIPE,
        [
            RemoveStepOp(op="remove_step", step_number=1),
            AddStepOp(op="add_step", after_step_number=3, step=new_step),
        ],
    )
    assert [s.step_number for s in _steps(result.recipe)] == [1, 2, 3]


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def test_unused_ingredient_warning_after_patch() -> None:
    result = apply_operations(
        BASE_RECIPE,
        [
            UpdateStepOp(
                op="update_step",
                step_number=2,
                fields=[StepIngredientsUsedUpdate(field="ingredients_used", value=[])],
            )
        ],
    )
    assert any("salt1" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Combined ops / ingredient rename cascading to steps
# ---------------------------------------------------------------------------


def test_ingredient_rename_and_step_cascade_combined() -> None:
    result = apply_operations(
        BASE_RECIPE,
        [
            UpdateIngredientOp(
                op="update_ingredient",
                ingredient_id="milk",
                fields=[IngredientNameUpdate(field="name", value="кокосовое молоко")],
            ),
            UpdateStepOp(
                op="update_step",
                step_number=1,
                fields=[StepActionUpdate(field="action", value="Взбить яйца с кокосовым молоком")],
            ),
            UpdateStepOp(
                op="update_step",
                step_number=3,
                fields=[StepFinalActionUpdate(field="final_action", value="снять с огня")],
            ),
            UpdateStepOp(
                op="update_step",
                step_number=2,
                fields=[StepHeatLevelUpdate(field="heat_level", value="средний огонь")],
            ),
        ],
    )
    milk = next(i for i in _ingredients(result.recipe) if i.id == "milk")
    assert milk.name == "кокосовое молоко"
    assert _steps(result.recipe)[0].action == "Взбить яйца с кокосовым молоком"
    assert _steps(result.recipe)[2].final_action == "снять с огня"
    assert _steps(result.recipe)[1].heat_level == "средний огонь"
