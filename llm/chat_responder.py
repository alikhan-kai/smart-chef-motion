"""OpenAI call for the chat/revision turn -> ChatResponse.

No FastAPI imports here. Mirrors llm/recipe_generator.py's structure and
error handling (single retry on validation failure, same domain exceptions)
but is a separate function/prompt/schema, per the task: generate_raw_recipe
is unchanged and this never touches web_search_prompt.md/recipe_schema.json.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError
from openai.types.responses.response_format_text_json_schema_config_param import (
    ResponseFormatTextJSONSchemaConfigParam,
)
from openai.types.responses.response_input_param import ResponseInputParam
from openai.types.responses.response_text_config_param import ResponseTextConfigParam
from openai.types.responses.web_search_tool_param import WebSearchToolParam
from pydantic import ValidationError

from llm.chat_schemas import ChatResponse, HistoryMessage
from llm.config import get_llm_settings
from llm.errors import (
    UpstreamError,
    UpstreamRateLimitError,
    UpstreamTimeoutError,
    ValidationFailedError,
)
from llm.language import OutputLanguage, language_instruction
from llm.schemas import RawRecipe
from llm.usage_logging import call_with_usage_logging

PROMPTS_DIR = Path(__file__).parent / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "revise_system_prompt.md"
SCHEMA_PATH = PROMPTS_DIR / "revise_schema.json"

_WEB_SEARCH_TOOLS: list[WebSearchToolParam] = [{"type": "web_search"}]


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    if not SYSTEM_PROMPT_PATH.exists():
        raise FileNotFoundError(f"System prompt file not found: {SYSTEM_PROMPT_PATH}")
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _load_schema_format() -> ResponseFormatTextJSONSchemaConfigParam:
    """Load revise_schema.json and adapt it into the Responses API text.format shape.

    Same nested-to-flat adaptation as llm/recipe_generator.py's
    _load_schema_format() (duplicated rather than imported - see REPORT.md:
    AGENTS.md says not to restructure existing code, so recipe_generator.py
    is left untouched rather than extracting a shared helper).
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


def _build_input(
    current_recipe: RawRecipe,
    history: list[HistoryMessage],
    user_message: str,
    patch_error: str | None,
    language: OutputLanguage | None = None,
) -> ResponseInputParam:
    settings = get_llm_settings()
    truncated_history = history[-settings.revise_history_messages :]

    system_content = (
        _load_system_prompt() + language_instruction(language)
        + "\n\n# ТЕКУЩИЙ РЕЦЕПТ (JSON)\n" + current_recipe.model_dump_json()
    )
    messages: ResponseInputParam = [{"role": "system", "content": system_content}]
    for message in truncated_history:
        messages.append({"role": message.role, "content": message.content})

    latest_user_content = user_message
    if patch_error:
        latest_user_content = (
            f"{user_message}\n\n"
            "# ОШИБКА ПРИМЕНЕНИЯ ПРЕДЫДУЩЕГО ПАТЧА\n"
            "Твой предыдущий набор operations не удалось применить со следующей ошибкой. "
            "Исправь operations так, чтобы ошибка не повторилась; при необходимости верни "
            "меньше операций или сошлись на другие/существующие id и номера шагов:\n"
            f"{patch_error}"
        )
    messages.append({"role": "user", "content": latest_user_content})
    return messages


def _parse_chat_response(output_text: str) -> ChatResponse:
    data: Any = json.loads(output_text)
    return ChatResponse.model_validate(data)


async def _call(
    client: AsyncOpenAI,
    model: str,
    input_messages: ResponseInputParam,
    workflow_id: str,
    attempt: int,
) -> str:
    text_config: ResponseTextConfigParam = {"format": _load_schema_format()}
    settings = get_llm_settings()
    if settings.revise_use_web_search:
        response = await call_with_usage_logging(
            lambda: client.responses.create(
                model=model,
                input=input_messages,
                tools=_WEB_SEARCH_TOOLS,
                text=text_config,
            ),
            operation=f"chat.response.attempt_{attempt}",
            workflow_id=workflow_id,
            model=model,
        )
    else:
        response = await call_with_usage_logging(
            lambda: client.responses.create(
                model=model, input=input_messages, text=text_config
            ),
            operation=f"chat.response.attempt_{attempt}",
            workflow_id=workflow_id,
            model=model,
        )
    return response.output_text


async def respond_to_message(
    current_recipe: RawRecipe,
    history: list[HistoryMessage],
    user_message: str,
    patch_error: str | None = None,
    language: OutputLanguage | None = None,
) -> ChatResponse:
    """One chat turn: classify the message as a question or a revision request.

    `history` is the chat's messages so far (any length); only the last
    `REVISE_HISTORY_MESSAGES` (default 10) are actually sent as context.

    `patch_error` is set only for the one backend-level retry after a
    previously returned patch failed to apply (see
    backend/services/chat_service.py) - it is appended to the user message
    so the model can see what went wrong and correct its operations.

    Retries the OpenAI call once (like generate_raw_recipe) if the output
    fails schema validation. Raises the same llm/errors.py domain exceptions
    for upstream failures. Unlike generate_raw_recipe, there is no
    model-reported `error` field in this schema - an off-topic or unclear
    message is expected to come back as intent="answer" with an explanatory
    answer_text, not a hard error.
    """
    settings = get_llm_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    model = settings.revise_model or settings.openai_model
    input_messages = _build_input(current_recipe, history, user_message, patch_error, language)
    workflow_id = uuid4().hex
    attempt = 1

    try:
        try:
            output_text = await _call(
                client, model, input_messages, workflow_id, attempt
            )
            return _parse_chat_response(output_text)
        except (json.JSONDecodeError, ValidationError):
            attempt += 1
            output_text = await _call(
                client, model, input_messages, workflow_id, attempt
            )
            try:
                return _parse_chat_response(output_text)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValidationFailedError(
                    "Chat model output failed schema validation after retry"
                ) from exc
    except APITimeoutError as exc:
        raise UpstreamTimeoutError("OpenAI request timed out") from exc
    except RateLimitError as exc:
        raise UpstreamRateLimitError("OpenAI rate limit exceeded") from exc
    except (APIConnectionError, APIError) as exc:
        raise UpstreamError(f"OpenAI API error: {exc}") from exc
