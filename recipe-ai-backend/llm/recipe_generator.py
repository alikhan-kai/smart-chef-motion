"""LangChain call: strict structured output (optionally after web search) -> RawRecipe.

Provider-agnostic: the model comes from init_chat_model() (see
llm/langchain_client.py). No FastAPI imports here. Raises domain exceptions from
llm/errors.py and knows nothing about HTTP.
"""

from typing import Any

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from llm.config import get_llm_settings
from llm.errors import ModelReportedError, ValidationFailedError
from llm.langchain_client import (
    PROMPTS_DIR,
    build_chat_model,
    load_json_schema,
    load_prompt,
    output_text,
    translate_provider_errors,
    with_json_schema,
    with_web_search,
)
from llm.schemas import RawRecipe

# The system prompt file is named web_search_prompt.md rather than
# recipe_system_prompt.md (see REPORT.md for why); content is loaded verbatim.
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "web_search_prompt.md"
SCHEMA_PATH = PROMPTS_DIR / "recipe_schema.json"

# We disable web search here to significantly speed up response times.
# Setting this to True runs the two-step flow with the provider's web search tool.
_USE_WEB_SEARCH = False

_TWO_STEP_PLAIN_TEXT_ADDENDUM = (
    "\n\nВАЖНО (переопределение для этого запроса): на этом шаге верни рецепт "
    "обычным читаемым текстом на русском языке, НЕ в формате JSON. "
    "JSON понадобится позже."
)


def _build_user_message(
    prompt: str,
    allergies: str | None,
    preferred_units: str | None,
) -> str:
    lines = [prompt]
    if allergies:
        lines.append(f"Аллергии/ограничения: {allergies}")
    if preferred_units:
        lines.append(f"Предпочитаемые единицы измерения: {preferred_units}")
    return "\n".join(lines)


async def _call_structured(model: BaseChatModel, provider: str, user_message: str) -> Any:
    runnable = with_json_schema(model, provider, load_json_schema(SCHEMA_PATH))
    messages: list[BaseMessage] = [
        SystemMessage(content=load_prompt(SYSTEM_PROMPT_PATH)),
        HumanMessage(content=user_message),
    ]
    return await runnable.ainvoke(messages)


async def _call_plain_text(model: BaseChatModel, provider: str, user_message: str) -> str:
    runnable = with_web_search(model, provider) if _USE_WEB_SEARCH else model
    messages: list[BaseMessage] = [
        SystemMessage(content=load_prompt(SYSTEM_PROMPT_PATH) + _TWO_STEP_PLAIN_TEXT_ADDENDUM),
        HumanMessage(content=user_message),
    ]
    return output_text(await runnable.ainvoke(messages))


async def _call_convert_to_json(model: BaseChatModel, provider: str, plain_text_recipe: str) -> Any:
    return await _call_structured(
        model,
        provider,
        "Преобразуй следующий рецепт в строгий JSON по схеме. "
        "Не выполняй новый поиск, используй только этот текст:\n\n"
        f"{plain_text_recipe}",
    )


async def generate_raw_recipe(
    prompt: str,
    allergies: str | None = None,
    preferred_units: str | None = None,
) -> RawRecipe:
    """Generate one strict-JSON recipe with the configured LangChain chat model.

    Retries the full generation once if the model output fails schema validation.
    Raises ModelReportedError if the model reports a non-null `error`.
    """
    settings = get_llm_settings()
    provider = settings.llm_provider
    model = build_chat_model(settings, settings.llm_model)
    user_message = _build_user_message(prompt, allergies, preferred_units)

    async def _run_once() -> RawRecipe:
        if settings.two_step_mode or _USE_WEB_SEARCH:
            plain_text = await _call_plain_text(model, provider, user_message)
            data = await _call_convert_to_json(model, provider, plain_text)
        else:
            data = await _call_structured(model, provider, user_message)
        return RawRecipe.model_validate(data)

    with translate_provider_errors():
        try:
            raw_recipe = await _run_once()
        except (OutputParserException, ValidationError):
            try:
                raw_recipe = await _run_once()
            except (OutputParserException, ValidationError) as exc:
                raise ValidationFailedError(
                    "Model output failed schema validation after retry"
                ) from exc

    if raw_recipe.error is not None:
        raise ModelReportedError(raw_recipe.error)

    return raw_recipe
