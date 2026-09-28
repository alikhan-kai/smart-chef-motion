"""OpenAI call: web search + strict structured output -> RawRecipe.

No FastAPI imports here. Raises domain exceptions from llm/errors.py and knows
nothing about HTTP.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from openai.types.responses.response_format_text_json_schema_config_param import (
    ResponseFormatTextJSONSchemaConfigParam,
)
from openai.types.responses.response_input_param import ResponseInputParam
from openai.types.responses.response_text_config_param import ResponseTextConfigParam
from openai.types.responses.web_search_tool_param import WebSearchToolParam
from pydantic import ValidationError

from llm.config import get_llm_settings
from llm.errors import (
    ModelReportedError,
    UpstreamError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
    ValidationFailedError,
)
from llm.schemas import RawRecipe

PROMPTS_DIR = Path(__file__).parent / "prompts"

# The system prompt file is named web_search_prompt.md rather than
# recipe_system_prompt.md (see REPORT.md for why); content is loaded verbatim.
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "web_search_prompt.md"
SCHEMA_PATH = PROMPTS_DIR / "recipe_schema.json"

# We disable web search here to significantly speed up response times.
_WEB_SEARCH_TOOLS: list = []

_TWO_STEP_PLAIN_TEXT_ADDENDUM = (
    "\n\nВАЖНО (переопределение для этого запроса): на этом шаге верни рецепт "
    "обычным читаемым текстом на русском языке, НЕ в формате JSON. "
    "JSON понадобится позже."
)


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(f"System prompt file not found: {SYSTEM_PROMPT_PATH}")
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _load_schema_format() -> ResponseFormatTextJSONSchemaConfigParam:
    """Load recipe_schema.json and adapt it into the Responses API text.format shape.

    The file itself uses a nested {"type", "json_schema": {"name", "strict", "schema"}}
    shape (Chat Completions' response_format). The Responses API's text.format instead
    needs a flat {"type", "name", "schema", "strict"} object (verified against the
    installed openai SDK's ResponseFormatTextJSONSchemaConfigParam and current OpenAI
    docs). We adapt here rather than editing the file, since the file's content is the
    single source of truth and must not be modified.
    """
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")
    raw: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    source = raw["json_schema"] if "json_schema" in raw else raw
    return {
        "type": "json_schema",
        "name": source["name"],
        "schema": source["schema"],
        "strict": source.get("strict", True),
    }


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


def _parse_raw_recipe(output_text: str) -> RawRecipe:
    data: Any = json.loads(output_text)
    return RawRecipe.model_validate(data)


async def _call_structured(client: AsyncOpenAI, model: str, user_message: str) -> str:
    input_messages: ResponseInputParam = [
        {"role": "system", "content": _load_system_prompt()},
        {"role": "user", "content": user_message},
    ]
    text_config: ResponseTextConfigParam = {"format": _load_schema_format()}
    response = await client.responses.create(
        model=model,
        input=input_messages,
        tools=_WEB_SEARCH_TOOLS,
        text=text_config,
    )
    return response.output_text


async def _call_plain_text(client: AsyncOpenAI, model: str, user_message: str) -> str:
    input_messages: ResponseInputParam = [
        {
            "role": "system",
            "content": _load_system_prompt() + _TWO_STEP_PLAIN_TEXT_ADDENDUM,
        },
        {"role": "user", "content": user_message},
    ]
    response = await client.responses.create(
        model=model,
        input=input_messages,
        tools=_WEB_SEARCH_TOOLS,
    )
    return response.output_text


async def _call_convert_to_json(client: AsyncOpenAI, model: str, plain_text_recipe: str) -> str:
    input_messages: ResponseInputParam = [
        {"role": "system", "content": _load_system_prompt()},
        {
            "role": "user",
            "content": (
                "Преобразуй следующий рецепт в строгий JSON по схеме. "
                "Не выполняй новый поиск, используй только этот текст:\n\n"
                f"{plain_text_recipe}"
            ),
        },
    ]
    text_config: ResponseTextConfigParam = {"format": _load_schema_format()}
    response = await client.responses.create(
        model=model,
        input=input_messages,
        text=text_config,
    )
    return response.output_text


async def generate_raw_recipe(
    prompt: str,
    allergies: str | None = None,
    preferred_units: str | None = None,
) -> RawRecipe:
    """Generate one strict-JSON recipe via OpenAI web search + structured output.

    Retries the full generation once if the model output fails schema validation.
    Raises ModelReportedError if the model reports a non-null `error`.
    """
    settings = get_llm_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    user_message = _build_user_message(prompt, allergies, preferred_units)
    model = settings.openai_model

    async def _run_once() -> str:
        if settings.two_step_mode:
            plain_text = await _call_plain_text(client, model, user_message)
            return await _call_convert_to_json(client, model, plain_text)
        return await _call_structured(client, model, user_message)

    try:
        try:
            output_text = await _run_once()
            raw_recipe = _parse_raw_recipe(output_text)
        except (json.JSONDecodeError, ValidationError):
            output_text = await _run_once()
            try:
                raw_recipe = _parse_raw_recipe(output_text)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValidationFailedError(
                    "Model output failed schema validation after retry"
                ) from exc
    except APITimeoutError as exc:
        raise UpstreamTimeoutError("OpenAI request timed out") from exc
    except RateLimitError as exc:
        raise UpstreamRateLimitError("OpenAI rate limit exceeded") from exc
    except (APIConnectionError, APIError) as exc:
        raise UpstreamError(f"OpenAI API error: {exc}") from exc

    if raw_recipe.error is not None:
        raise ModelReportedError(raw_recipe.error)

    return raw_recipe
