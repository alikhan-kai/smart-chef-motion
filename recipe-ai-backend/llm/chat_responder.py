"""LangChain call for the chat/revision turn -> ChatResponse.

Provider-agnostic: the model comes from init_chat_model() (see
llm/langchain_client.py). No FastAPI imports here. Mirrors
llm/recipe_generator.py's structure and error handling (single retry on
validation failure, same domain exceptions) but is a separate
function/prompt/schema: generate_raw_recipe is unchanged and this never
touches web_search_prompt.md/recipe_schema.json.
"""

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from llm.chat_schemas import ChatResponse, HistoryMessage
from llm.config import LLMSettings, get_llm_settings
from llm.errors import ValidationFailedError
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

SYSTEM_PROMPT_PATH = PROMPTS_DIR / "revise_system_prompt.md"
SCHEMA_PATH = PROMPTS_DIR / "revise_schema.json"

_WEB_SEARCH_STEP_ADDENDUM = (
    "\n\nВАЖНО (переопределение для этого шага): найди в интернете сведения, нужные "
    "для ответа на последнее сообщение пользователя, и кратко изложи их обычным "
    "текстом на русском языке, НЕ в формате JSON. JSON понадобится позже."
)


def _build_messages(
    settings: LLMSettings,
    current_recipe: RawRecipe,
    history: list[HistoryMessage],
    user_message: str,
    patch_error: str | None,
    system_addendum: str = "",
    search_notes: str | None = None,
) -> list[BaseMessage]:
    truncated_history = history[-settings.revise_history_messages :]

    system_content = (
        load_prompt(SYSTEM_PROMPT_PATH)
        + "\n\n# ТЕКУЩИЙ РЕЦЕПТ (JSON)\n"
        + current_recipe.model_dump_json()
        + system_addendum
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
    if search_notes:
        latest_user_content = (
            f"{latest_user_content}\n\n# РЕЗУЛЬТАТЫ ПОИСКА В ИНТЕРНЕТЕ\n{search_notes}"
        )
    messages.append(HumanMessage(content=latest_user_content))
    return messages


async def _search_notes(
    model: BaseChatModel,
    settings: LLMSettings,
    current_recipe: RawRecipe,
    history: list[HistoryMessage],
    user_message: str,
) -> str:
    runnable = with_web_search(model, settings.llm_provider)
    messages = _build_messages(
        settings, current_recipe, history, user_message, None, _WEB_SEARCH_STEP_ADDENDUM
    )
    return output_text(await runnable.ainvoke(messages))


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

    With `REVISE_USE_WEB_SEARCH` on, a first call with the provider's web
    search tool collects notes as plain text, and the structured call gets
    them appended (tools + strict schema in one call is not portable).

    Retries the structured call once (like generate_raw_recipe) if the output
    fails schema validation. Raises the same llm/errors.py domain exceptions
    for upstream failures. Unlike generate_raw_recipe, there is no
    model-reported `error` field in this schema - an off-topic or unclear
    message is expected to come back as intent="answer" with an explanatory
    answer_text, not a hard error.
    """
    settings = get_llm_settings()
    model = build_chat_model(settings, settings.revise_model or settings.llm_model)
    runnable = with_json_schema(model, settings.llm_provider, load_json_schema(SCHEMA_PATH))

    with translate_provider_errors():
        search_notes = None
        if settings.revise_use_web_search:
            search_notes = await _search_notes(
                model, settings, current_recipe, history, user_message
            )
        messages = _build_messages(
            settings,
            current_recipe,
            history,
            user_message,
            patch_error,
            search_notes=search_notes,
        )
        try:
            return ChatResponse.model_validate(await runnable.ainvoke(messages))
        except (OutputParserException, ValidationError):
            try:
                return ChatResponse.model_validate(await runnable.ainvoke(messages))
            except (OutputParserException, ValidationError) as exc:
                raise ValidationFailedError(
                    "Chat model output failed schema validation after retry"
                ) from exc
