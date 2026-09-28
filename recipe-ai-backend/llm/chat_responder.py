"""LangChain call for the chat/revision turn -> ChatResponse.

No FastAPI imports here. Mirrors llm/recipe_generator.py's structure and
error handling (single retry on validation failure, same domain exceptions)
but is a separate function/prompt/schema: generate_raw_recipe is unchanged
and this never touches web_search_prompt.md/recipe_schema.json.
"""

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from llm.chat_schemas import ChatResponse, HistoryMessage
from llm.config import get_llm_settings
from llm.errors import ValidationFailedError
from llm.langchain_client import (
    PROMPTS_DIR,
    build_chat_model,
    load_prompt,
    load_response_format,
    output_text,
    translate_openai_errors,
)
from llm.schemas import RawRecipe

SYSTEM_PROMPT_PATH = PROMPTS_DIR / "revise_system_prompt.md"
SCHEMA_PATH = PROMPTS_DIR / "revise_schema.json"

_WEB_SEARCH_TOOLS: list[dict[str, Any]] = [{"type": "web_search"}]


def _build_messages(
    current_recipe: RawRecipe,
    history: list[HistoryMessage],
    user_message: str,
    patch_error: str | None,
) -> list[BaseMessage]:
    settings = get_llm_settings()
    truncated_history = history[-settings.revise_history_messages :]

    system_content = (
        load_prompt(SYSTEM_PROMPT_PATH)
        + "\n\n# ТЕКУЩИЙ РЕЦЕПТ (JSON)\n"
        + current_recipe.model_dump_json()
    )
    messages: list[BaseMessage] = [SystemMessage(content=system_content)]
    for message in truncated_history:
        if message.role == "user":
            messages.append(HumanMessage(content=message.content))
        else:
            messages.append(AIMessage(content=message.content))

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
    messages.append(HumanMessage(content=latest_user_content))
    return messages


def _parse_chat_response(text: str) -> ChatResponse:
    data: Any = json.loads(text)
    return ChatResponse.model_validate(data)


async def respond_to_message(
    current_recipe: RawRecipe,
    history: list[HistoryMessage],
    user_message: str,
    patch_error: str | None = None,
) -> ChatResponse:
    """One chat turn: classify the message as a question or a revision request.

    `history` is the chat's messages so far (any length); only the last
    `REVISE_HISTORY_MESSAGES` (default 10) are actually sent as context.

    `patch_error` is set only for the one backend-level retry after a
    previously returned patch failed to apply (see
    backend/services/chat_service.py) - it is appended to the user message
    so the model can see what went wrong and correct its operations.

    Retries the model call once (like generate_raw_recipe) if the output
    fails schema validation. Raises the same llm/errors.py domain exceptions
    for upstream failures. Unlike generate_raw_recipe, there is no
    model-reported `error` field in this schema - an off-topic or unclear
    message is expected to come back as intent="answer" with an explanatory
    answer_text, not a hard error.
    """
    settings = get_llm_settings()
    model = build_chat_model(settings, settings.revise_model or settings.openai_model)
    bind_kwargs: dict[str, Any] = {"response_format": load_response_format(SCHEMA_PATH)}
    if settings.revise_use_web_search:
        bind_kwargs["tools"] = _WEB_SEARCH_TOOLS
    runnable = model.bind(**bind_kwargs)
    messages = _build_messages(current_recipe, history, user_message, patch_error)

    with translate_openai_errors():
        try:
            return _parse_chat_response(output_text(await runnable.ainvoke(messages)))
        except (json.JSONDecodeError, ValidationError):
            text = output_text(await runnable.ainvoke(messages))
            try:
                return _parse_chat_response(text)
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValidationFailedError(
                    "Chat model output failed schema validation after retry"
                ) from exc
