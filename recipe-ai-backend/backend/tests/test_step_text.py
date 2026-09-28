"""Tests for backend.services.step_text: number/plural helpers, the
full-quality Russian renderer, the language-neutral fallback renderer, and
language detection. See REPORT.md for the target-example rationale.
"""

from backend.services.step_text.labels import render_fallback, unused_ingredient_warning
from backend.services.step_text.language import detect_language, detect_recipe_language
from backend.services.step_text.numbers import format_amount, plural_form
from backend.services.step_text.ru import render_ru
from llm.schemas import RawFat, RawIngredient, RawRecipe, RawStep


def _step(**overrides: object) -> RawStep:
    defaults: dict[str, object] = {
        "step_number": 1,
        "action": "Сделайте шаг",
        "ingredients_used": [],
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


# ---------------------------------------------------------------------------
# numbers.py
# ---------------------------------------------------------------------------


def test_format_amount_strips_trailing_zero() -> None:
    assert format_amount(3) == "3"
    assert format_amount(3.0) == "3"
    assert format_amount(1.5) == "1.5"


def test_plural_form_one_few_many() -> None:
    forms = ("минуту", "минуты", "минут")
    assert plural_form(1, forms) == "минуту"
    assert plural_form(2, forms) == "минуты"
    assert plural_form(3, forms) == "минуты"
    assert plural_form(4, forms) == "минуты"
    assert plural_form(5, forms) == "минут"
    assert plural_form(11, forms) == "минут"
    assert plural_form(12, forms) == "минут"
    assert plural_form(14, forms) == "минут"
    assert plural_form(21, forms) == "минуту"
    assert plural_form(61, forms) == "минуту"


def test_plural_form_fractional_uses_few_slot() -> None:
    forms = ("литр", "литра", "литров")
    assert plural_form(1.5, forms) == "литра"


# ---------------------------------------------------------------------------
# render_ru: the task's four Russian target examples, verbatim.
# ---------------------------------------------------------------------------


def test_ru_target_example_heat_time_fat() -> None:
    step = _step(
        action="Разогрейте сковороду",
        heat_level="средний огонь",
        time_minutes=1,
        place="сковорода",
        fat=RawFat(type="подсолнечное масло", amount=1, unit="ст. л."),
    )
    assert render_ru(step, {}) == (
        "Разогрейте сковороду на среднем огне 1 минуту, "
        "добавьте 1 столовую ложку подсолнечного масла."
    )


def test_ru_target_example_heat_time_final_action() -> None:
    step = _step(
        action="Обжарьте зелёный перец",
        heat_level="максимальный огонь",
        time_minutes=0.33,
        final_action="переложите в миску",
    )
    assert render_ru(step, {}) == (
        "Обжарьте зелёный перец на максимальном огне 20 секунд, затем переложите в миску."
    )


def test_ru_target_example_ingredient_amount_inserted() -> None:
    eggs = RawIngredient(id="eggs", name="яйца", amount=3, unit="шт", form=None)
    step = _step(action="Разбейте яйца в миску", ingredients_used=["eggs"], place="миска")
    assert render_ru(step, {"eggs": eggs}) == "Разбейте 3 яйца в миску."


def test_ru_target_example_passive_no_time() -> None:
    step = _step(action="Оставьте мариноваться", passive=True, place="холодильник")
    assert render_ru(step, {}) == "Оставьте мариноваться."


# ---------------------------------------------------------------------------
# render_ru: edge cases
# ---------------------------------------------------------------------------


def test_ru_all_optional_fields_null() -> None:
    step = _step(action="Перемешайте всё")
    assert render_ru(step, {}) == "Перемешайте всё."


def test_ru_fat_unknown_type_falls_back_to_raw_text() -> None:
    step = _step(
        action="Добавьте жир",
        fat=RawFat(type="странное масло", amount=2, unit="ст. л."),
    )
    # Unit still declines (known table); the unfamiliar fat type is kept
    # verbatim (nominative), per the documented fallback rule.
    assert render_ru(step, {}) == "Добавьте жир, добавьте 2 столовые ложки странное масло."


def test_ru_time_0_33_minutes_is_20_seconds() -> None:
    step = _step(action="Обжарьте лук", time_minutes=0.33)
    assert render_ru(step, {}) == "Обжарьте лук 20 секунд."


def test_ru_time_1_minute() -> None:
    step = _step(action="Варите суп", time_minutes=1)
    assert render_ru(step, {}) == "Варите суп 1 минуту."


def test_ru_time_1_5_minutes_is_minute_plus_seconds() -> None:
    step = _step(action="Жарьте котлеты", time_minutes=1.5)
    assert render_ru(step, {}) == "Жарьте котлеты 1 минуту 30 секунд."


def test_ru_time_61_minutes() -> None:
    step = _step(action="Запекайте в духовке", time_minutes=61)
    assert render_ru(step, {}) == "Запекайте в духовке 61 минуту."


def test_ru_passive_step_with_known_time_still_renders_it() -> None:
    step = _step(action="Дайте тесту отдохнуть", passive=True, time_minutes=5)
    assert render_ru(step, {}) == "Дайте тесту отдохнуть 5 минут."


def test_ru_ingredient_not_mentioned_in_action_known_noun() -> None:
    tomatoes = RawIngredient(id="t", name="помидоры", amount=2, unit="шт", form=None)
    step = _step(action="Нарежьте кубиками", ingredients_used=["t"])
    assert render_ru(step, {"t": tomatoes}) == "Нарежьте кубиками, 2 помидора."


def test_ru_ingredient_not_mentioned_in_action_unknown_noun_falls_back() -> None:
    mystery = RawIngredient(id="m", name="дуриан", amount=3, unit="шт", form=None)
    step = _step(action="Нарежьте кубиками", ingredients_used=["m"])
    assert render_ru(step, {"m": mystery}) == "Нарежьте кубиками, дуриан 3 шт."


def test_ru_ingredient_amount_already_in_action_is_not_repeated() -> None:
    eggs = RawIngredient(id="eggs", name="яйца", amount=3, unit="шт", form=None)
    step = _step(action="Разбейте 3 яйца в миску", ingredients_used=["eggs"])
    assert render_ru(step, {"eggs": eggs}) == "Разбейте 3 яйца в миску."


# ---------------------------------------------------------------------------
# Regressions found via a live model call (see REPORT.md, Verification):
# real output surfaced these classes of bug that the four hand-written
# target examples didn't happen to exercise.
# ---------------------------------------------------------------------------


def test_ru_action_already_states_heat_is_not_duplicated() -> None:
    # Real output: "Разогрейте сковороду на среднем огне." + heat_level
    # "средний огонь" used to render as "...на среднем огне. на среднем
    # огне 1 минуту." (duplicated phrase, stray mid-sentence period).
    step = _step(
        action="Разогрейте сковороду на среднем огне.",
        heat_level="средний огонь",
        time_minutes=1,
    )
    assert render_ru(step, {}) == "Разогрейте сковороду на среднем огне 1 минуту."


def test_ru_action_with_trailing_period_gets_no_double_punctuation() -> None:
    step = _step(action="Нарежьте лук кольцами.")
    assert render_ru(step, {}) == "Нарежьте лук кольцами."


def test_ru_ingredient_matching_fat_type_is_not_double_mentioned() -> None:
    # Real output: the model sometimes lists a fat both as a regular
    # ingredient (ingredients_used) *and* as the structured `fat` field,
    # which used to produce a malformed extra mention like
    # "Растопите 15 сливочное масло..., добавьте 15 г сливочного масла.".
    butter = RawIngredient(id="b", name="сливочное масло", amount=15, unit="г", form=None)
    step = _step(
        action="Растопите сливочное масло на сковороде",
        ingredients_used=["b"],
        fat=RawFat(type="сливочное масло", amount=15, unit="г"),
    )
    assert render_ru(step, {"b": butter}) == (
        "Растопите сливочное масло на сковороде, добавьте 15 г сливочного масла."
    )


def test_ru_fat_amount_already_in_action_is_not_repeated() -> None:
    step = _step(
        action="Добавьте 2 ст. л. масла в сковороду",
        fat=RawFat(type="растительное масло", amount=2, unit="ст. л."),
    )
    assert render_ru(step, {}) == "Добавьте 2 ст. л. масла в сковороду."


def test_ru_ingredient_word_form_disagreeing_with_amount_is_corrected() -> None:
    # Real output: action used generic singular "яйцо" while amount=2; bare
    # digit-prefix insertion used to produce ungrammatical "2 яйцо" instead
    # of correcting the noun's form to "2 яйца".
    eggs = RawIngredient(id="eggs", name="яйца", amount=2, unit="шт", form=None)
    step = _step(action="Взбейте яйцо с молоком венчиком", ingredients_used=["eggs"])
    assert render_ru(step, {"eggs": eggs}) == "Взбейте 2 яйца с молоком венчиком."


def test_en_fallback_action_already_states_heat_is_not_duplicated() -> None:
    step = _step(
        action="Add oil to the wok over high heat.",
        heat_level="максимальный огонь",
    )
    assert render_fallback(step, "en") == "Add oil to the wok over high heat."


def test_en_fallback_fat_amount_already_in_action_is_not_repeated() -> None:
    step = _step(
        action="Add 2 tablespoons vegetable oil to the pan",
        fat=RawFat(type="vegetable oil", amount=2, unit="ст. л."),
    )
    assert render_fallback(step, "en") == "Add 2 tablespoons vegetable oil to the pan."


def test_ru_ingredient_with_no_amount_is_skipped() -> None:
    salt = RawIngredient(id="s", name="соль", amount=None, unit="по вкусу", form=None)
    step = _step(action="Посолите блюдо", ingredients_used=["s"])
    assert render_ru(step, {"s": salt}) == "Посолите блюдо."


# ---------------------------------------------------------------------------
# Language-neutral fallback (English target example + Kazakh)
# ---------------------------------------------------------------------------


def test_en_target_example_heat_and_time() -> None:
    step = _step(action="Heat the pan", heat_level="средний огонь", time_minutes=1)
    assert render_fallback(step, "en") == "Heat the pan over medium heat for 1 minute."


def test_en_fallback_fat_salt_final_action() -> None:
    step = _step(
        action="Season the meat",
        fat=RawFat(type="butter", amount=1, unit="ст. л."),
        salt=True,
        final_action="serve immediately",
    )
    assert render_fallback(step, "en") == (
        "Season the meat, add 1 tbsp butter, add salt, then serve immediately."
    )


def test_en_fallback_all_optional_fields_null() -> None:
    step = _step(action="Stir well")
    assert render_fallback(step, "en") == "Stir well."


def test_kk_fallback_includes_heat_and_salt_labels() -> None:
    step = _step(action="Табаны қыздырыңыз", heat_level="максимальный огонь", salt=True)
    text = render_fallback(step, "kk")
    assert text.startswith("Табаны қыздырыңыз")
    assert "ең жоғары от" in text
    assert "тұз қосыңыз" in text


def test_unused_ingredient_warning_per_language() -> None:
    assert unused_ingredient_warning("соль", "ru") == (
        "Ингредиент «соль» не используется ни в одном шаге."
    )
    assert unused_ingredient_warning("salt", "en") == "Ingredient 'salt' is not used in any step."
    assert "тұз" in unused_ingredient_warning("тұз", "kk")


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def test_detect_language_russian() -> None:
    assert detect_language("Разогрейте сковороду на среднем огне") == "ru"


def test_detect_language_kazakh() -> None:
    assert detect_language("Қуырылған ет дайындаңыз") == "kk"


def test_detect_language_english() -> None:
    assert detect_language("Heat the pan over medium heat") == "en"


def test_detect_language_empty_defaults_to_english_fallback() -> None:
    assert detect_language("") == "en"


def test_detect_recipe_language_uses_title_and_steps() -> None:
    raw = RawRecipe(
        error=None,
        title="Omelette",
        servings=2,
        total_time_minutes=None,
        equipment=None,
        source_urls=None,
        notes=None,
        ingredients=[],
        steps=[_step(action="Heat the pan")],
    )
    assert detect_recipe_language(raw) == "en"


def test_detect_recipe_language_russian_recipe() -> None:
    raw = RawRecipe(
        error=None,
        title="Омлет",
        servings=2,
        total_time_minutes=None,
        equipment=None,
        source_urls=None,
        notes=None,
        ingredients=[],
        steps=[_step(action="Разогрейте сковороду")],
    )
    assert detect_recipe_language(raw) == "ru"
