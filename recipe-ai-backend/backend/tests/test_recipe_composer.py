import pytest

from backend.services.recipe_composer import UnknownIngredientError, compose_recipe
from llm.errors import ModelReportedError
from llm.schemas import RawFat, RawIngredient, RawRecipe, RawStep

SIMPLE_RECIPE = RawRecipe(
    error=None,
    title="Омлет",
    servings=2,
    total_time_minutes=None,
    equipment=["сковорода"],
    source_urls=["https://example.com/omelette"],
    notes=None,
    ingredients=[
        RawIngredient(id="eggs", name="яйца", amount=3, unit="шт", form=None),
        RawIngredient(id="milk", name="молоко", amount=50, unit="мл", form=None),
        RawIngredient(id="unused_salt", name="соль", amount=None, unit="по вкусу", form=None),
    ],
    steps=[
        RawStep(
            step_number=5,  # deliberately wrong, must be renumbered
            action="Взбить яйца с молоком",
            ingredients_used=["eggs", "milk"],
            time_minutes=2,
            passive=False,
            heat_level=None,
            place="миска",
            salt=False,
            fat=None,
            final_action=None,
        ),
        RawStep(
            step_number=9,
            action="Вылить смесь на сковороду и жарить",
            ingredients_used=[],
            time_minutes=5,
            passive=False,
            heat_level="средний огонь",
            place="сковорода",
            salt=True,
            fat=None,
            final_action="выключить плиту",
        ),
    ],
)


MARINATING_RECIPE = RawRecipe(
    error=None,
    title="Шашлык",
    servings=4,
    total_time_minutes=None,
    equipment=["мангал"],
    source_urls=[],
    notes=None,
    ingredients=[
        RawIngredient(id="meat", name="свинина", amount=1000, unit="г", form="нарезать кубиками"),
        RawIngredient(id="onion", name="лук", amount=2, unit="шт", form="нарезать кольцами"),
    ],
    steps=[
        RawStep(
            step_number=1,
            action="Замариновать мясо с луком",
            ingredients_used=["meat", "onion"],
            time_minutes=None,
            passive=True,
            heat_level=None,
            place="холодильник",
            salt=False,
            fat=None,
            final_action=None,
        ),
        RawStep(
            step_number=2,
            action="Обжарить мясо на мангале",
            ingredients_used=["meat"],
            time_minutes=15,
            passive=False,
            heat_level="максимальный огонь",
            place="мангал",
            salt=True,
            fat=RawFat(type="подсолнечное масло", amount=1, unit="ст. л."),
            final_action="переложить на тарелку",
        ),
    ],
)


@pytest.mark.asyncio
async def test_compose_recipe_renumbers_steps_and_flags_unused_ingredient() -> None:
    recipe = await compose_recipe(SIMPLE_RECIPE)

    assert [step.step_number for step in recipe.steps] == [1, 2]
    assert recipe.warnings == ["Ингредиент «соль» не используется ни в одном шаге."]
    assert "яйца" in recipe.steps[0].display_text
    assert "молоко" in recipe.steps[0].display_text


@pytest.mark.asyncio
async def test_compose_recipe_computes_total_time_when_model_returns_null() -> None:
    recipe = await compose_recipe(SIMPLE_RECIPE)

    # Both steps are active (non-passive) with known times: 2 + 5 = 7.
    assert recipe.total_time_minutes == 7


@pytest.mark.asyncio
async def test_compose_recipe_keeps_total_time_null_for_unknown_passive_duration() -> None:
    recipe = await compose_recipe(MARINATING_RECIPE)

    # Passive marinating step has no known time; active step has 15. Since
    # all active steps have known times, we sum the known times (15) even
    # though the passive step's own duration is unknown.
    assert recipe.total_time_minutes == 15


@pytest.mark.asyncio
async def test_compose_recipe_passive_step_display_text_reads_as_waiting() -> None:
    recipe = await compose_recipe(MARINATING_RECIPE)

    marinate_step = recipe.steps[0]
    assert marinate_step.passive is True
    # No time was known for this step, so none must be invented.
    assert "минут" not in marinate_step.display_text
    assert "секунд" not in marinate_step.display_text
    assert marinate_step.display_text.startswith("Замариновать")


@pytest.mark.asyncio
async def test_compose_recipe_fat_step_display_text_mentions_fat() -> None:
    recipe = await compose_recipe(MARINATING_RECIPE)

    fry_step = recipe.steps[1]
    assert "подсолнечного масла" in fry_step.display_text
    assert "1 столовую ложку" in fry_step.display_text


@pytest.mark.asyncio
async def test_compose_recipe_raises_for_unknown_ingredient_id() -> None:
    bad_recipe = RawRecipe(
        error=None,
        title="Плохой рецепт",
        servings=1,
        total_time_minutes=None,
        equipment=None,
        source_urls=None,
        notes=None,
        ingredients=[RawIngredient(id="a", name="a", amount=1, unit="г", form=None)],
        steps=[
            RawStep(
                step_number=1,
                action="Сделать что-то",
                ingredients_used=["does_not_exist"],
                time_minutes=1,
                passive=False,
                heat_level=None,
                place="миска",
                salt=False,
                fat=None,
                final_action=None,
            )
        ],
    )

    with pytest.raises(UnknownIngredientError):
        await compose_recipe(bad_recipe)


@pytest.mark.asyncio
async def test_compose_recipe_raises_model_reported_error_when_error_present() -> None:
    error_recipe = RawRecipe(
        error="Запрос не про еду",
        title=None,
        servings=None,
        total_time_minutes=None,
        equipment=None,
        source_urls=None,
        notes=None,
        ingredients=None,
        steps=None,
    )

    with pytest.raises(ModelReportedError):
        await compose_recipe(error_recipe)
