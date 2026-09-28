"""LangChain call: (optional) web search + strict structured output -> RawRecipe.

No FastAPI imports here. Raises domain exceptions from llm/errors.py and knows
nothing about HTTP.
"""

import json
from typing import Any

from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from llm.config import get_llm_settings
from llm.errors import ModelReportedError, ValidationFailedError
from llm.langchain_client import (
    PROMPTS_DIR,
    build_chat_model,
    load_prompt,
    load_response_format,
    output_text,
    translate_openai_errors,
)
from llm.schemas import RawRecipe

# The system prompt file is named web_search_prompt.md rather than
# recipe_system_prompt.md (see REPORT.md for why); content is loaded verbatim.
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "web_search_prompt.md"
SCHEMA_PATH = PROMPTS_DIR / "recipe_schema.json"

# We disable web search here to significantly speed up response times.
# Put {"type": "web_search"} back in to re-enable it.
_WEB_SEARCH_TOOLS: list[dict[str, Any]] = []

_TWO_STEP_PLAIN_TEXT_ADDENDUM = (
    "\n\nВАЖНО (переопределение для этого запроса): на этом шаге верни рецепт "
    "обычным читаемым текстом на русском языке, НЕ в формате JSON. "
    "JSON понадобится позже."
)

ChatRunnable = Runnable[LanguageModelInput, BaseMessage]


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


def _parse_raw_recipe(text: str) -> RawRecipe:
    data: Any = json.loads(text)
    return RawRecipe.model_validate(data)


def _with_tools(model: ChatOpenAI, **kwargs: Any) -> ChatRunnable:
    if _WEB_SEARCH_TOOLS:
        kwargs["tools"] = _WEB_SEARCH_TOOLS
    return model.bind(**kwargs)


async def _invoke(runnable: ChatRunnable, messages: list[BaseMessage]) -> str:
    return output_text(await runnable.ainvoke(messages))


async def _call_structured(model: ChatOpenAI, user_message: str) -> str:
    runnable = _with_tools(model, response_format=load_response_format(SCHEMA_PATH))
    messages: list[BaseMessage] = [
        SystemMessage(content=load_prompt(SYSTEM_PROMPT_PATH)),
        HumanMessage(content=user_message),
    ]
    return await _invoke(runnable, messages)


async def _call_plain_text(model: ChatOpenAI, user_message: str) -> str:
    runnable = _with_tools(model)
    messages: list[BaseMessage] = [
        SystemMessage(content=load_prompt(SYSTEM_PROMPT_PATH) + _TWO_STEP_PLAIN_TEXT_ADDENDUM),
        HumanMessage(content=user_message),
    ]
    return await _invoke(runnable, messages)


async def _call_convert_to_json(model: ChatOpenAI, plain_text_recipe: str) -> str:
    runnable = model.bind(response_format=load_response_format(SCHEMA_PATH))
    messages: list[BaseMessage] = [
        SystemMessage(content=load_prompt(SYSTEM_PROMPT_PATH)),
        HumanMessage(
            content=(
                "Преобразуй следующий рецепт в строгий JSON по схеме. "
                "Не выполняй новый поиск, используй только этот текст:\n\n"
                f"{plain_text_recipe}"
            )
        ),
    ]
    return await _invoke(runnable, messages)


async def generate_raw_recipe(
    prompt: str,
    allergies: str | None = None,
    preferred_units: str | None = None,
) -> RawRecipe:
    """Generate one strict-JSON recipe via LangChain ChatOpenAI (Responses API).

    Retries the full generation once if the model output fails schema validation.
    Raises ModelReportedError if the model reports a non-null `error`.
    """
    settings = get_llm_settings()
    model = build_chat_model(settings, settings.openai_model)
    user_message = _build_user_message(prompt, allergies, preferred_units)

    async def _run_once() -> str:
        if settings.two_step_mode:
            plain_text = await _call_plain_text(model, user_message)
            return await _call_convert_to_json(model, plain_text)
        return await _call_structured(model, user_message)

    with translate_openai_errors():
        try:
            raw_recipe = _parse_raw_recipe(await _run_once())
        except (json.JSONDecodeError, ValidationError):
            text = await _run_once()
            try:
                raw_recipe = _parse_raw_recipe(text)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValidationFailedError(
                    "Model output failed schema validation after retry"
                ) from exc

    if raw_recipe.error is not None:
        raise ModelReportedError(raw_recipe.error)

    return raw_recipe
