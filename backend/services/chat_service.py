"""Chat orchestration: start_chat, send_message, confirm_recipe, list_chats,
get_chat. Calls into llm/ (generate_raw_recipe, respond_to_message) and the
other backend/services/ (compose_recipe, apply_operations); talks to
persistence only through the ChatRepository/RecipeBookRepository protocols
passed in by the caller (see backend/api/deps.py for how routes obtain the
concrete in-memory instances).

Open-question behavior (documented per the task, not decided silently): if a
chat's recipe is already confirmed and the user asks for another revision,
that revision creates a new draft version as usual; the existing recipe-book
entry for the previously confirmed version is left untouched, and confirming
the new version creates a SEPARATE new recipe-book entry linked to the same
chat_id (never overwrites). This is the "simplest safe behavior" the task
asked for; see docs/chat_contract.md and REPORT.md's Open issues.
"""

import uuid
from datetime import UTC, datetime

from backend.repositories.chat_repo import ChatRepository
from backend.repositories.recipe_book_repo import RecipeBookRepository
from backend.schemas.chat import Chat, ChatMessage, ChatSummary, RecipeBookEntry, RecipeVersion
from backend.schemas.chat_requests import SendMessageResponse
from backend.services.recipe_composer import compose_recipe
from backend.services.recipe_patch import (
    PatchError,
    PatchResult,
    apply_operations,
    renumber_steps,
)
from llm.chat_responder import respond_to_message
from llm.chat_schemas import HistoryMessage
from llm.config import get_llm_settings
from llm.language import OutputLanguage
from llm.recipe_generator import generate_raw_recipe
from llm.schemas import RawRecipe


class ChatServiceError(Exception):
    """Base class for chat-service errors."""


class ChatNotFoundError(ChatServiceError):
    """No such chat for this user (or it belongs to someone else - the two
    are deliberately indistinguishable to the caller, see docs/chat_contract.md)."""


class VersionNotFoundError(ChatServiceError):
    """The chat exists, but not the requested version number."""


class RevisionFailedError(ChatServiceError):
    """A revision's patch failed to apply even after the one model retry,
    and REVISE_FALLBACK_TO_FULL_REGENERATION is off (or also failed)."""


class InvalidStateError(ChatServiceError):
    """Reserved for a genuine invalid state transition (-> HTTP 409). No
    code path currently raises this - see REPORT.md, Open issues: nothing
    in this design has an invalid-transition case yet (every chat always
    has >=1 version from start_chat(), confirming is idempotent by
    (chat_id, version), etc). Kept registered in backend/main.py's
    exception handlers for forward compatibility."""


_DRAFT_READY_TEXT = {
    "ru": (
        "Черновик рецепта «{title}» готов. Можете задать вопрос об этом рецепте "
        "или попросить внести изменения."
    ),
    "en": 'Draft recipe "{title}" is ready. You can ask a question about it or request changes.',
    "kk": "«{title}» рецептінің жобасы дайын. Сұрақ қоя аласыз немесе өзгерту сұрай аласыз.",
}
_UNTITLED = {"ru": "рецепт", "en": "recipe", "kk": "рецепт"}


def _draft_ready_message(title: str | None, language: str) -> str:
    template = _DRAFT_READY_TEXT.get(language, _DRAFT_READY_TEXT["en"])
    return template.format(title=title or _UNTITLED.get(language, _UNTITLED["en"]))


def _normalize_step_numbers(raw: RawRecipe) -> RawRecipe:
    """Renumber a freshly generated raw recipe's steps 1..N.

    generate_raw_recipe() does not itself guarantee contiguous numbering
    (the model's own step_number values are whatever it wrote). Chat
    revisions always reference "the current recipe's step numbering", so
    every version stored for a chat is normalized to clean 1..N numbering
    up front - see backend/services/recipe_patch.py's module docstring for
    the same invariant maintained after every patch.
    """
    if raw.steps is None:
        return raw
    return raw.model_copy(update={"steps": renumber_steps(raw.steps)})


def _build_fallback_prompt(current_recipe: RawRecipe, user_message: str) -> str:
    return (
        "Вот текущий рецепт в формате JSON и просьба пользователя об изменении. "
        "Сгенерируй заново полный рецепт, учитывая эту просьбу и сохраняя то, "
        "что пользователь не просил менять.\n\n"
        f"Текущий рецепт: {current_recipe.model_dump_json()}\n\n"
        f"Просьба пользователя: {user_message}"
    )


async def start_chat(
    chat_repo: ChatRepository,
    user_id: str,
    prompt: str,
    allergies: str | None = None,
    preferred_units: str | None = None,
    language: OutputLanguage | None = None,
) -> tuple[str, RecipeVersion]:
    raw_recipe = await generate_raw_recipe(prompt, allergies, preferred_units, language=language)
    raw_recipe = _normalize_step_numbers(raw_recipe)
    recipe = await compose_recipe(raw_recipe)

    chat = await chat_repo.create_chat(user_id, title=recipe.title)
    now = datetime.now(UTC)

    await chat_repo.append_message(
        chat.id,
        ChatMessage(id=str(uuid.uuid4()), role="user", content=prompt, created_at=now),
    )

    version = RecipeVersion(
        version=1,
        raw_recipe=raw_recipe,
        recipe=recipe,
        operations=None,
        change_log=[],
        summary=None,
        created_at=now,
        confirmed=False,
    )
    await chat_repo.save_version(chat.id, version)

    await chat_repo.append_message(
        chat.id,
        ChatMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content=_draft_ready_message(recipe.title, recipe.language),
            intent=None,
            version=1,
            created_at=now,
        ),
    )

    return chat.id, version


async def send_message(
    chat_repo: ChatRepository,
    user_id: str,
    chat_id: str,
    text: str,
    language: OutputLanguage | None = None,
) -> SendMessageResponse:
    chat = await chat_repo.get_chat(user_id, chat_id)
    if chat is None:
        raise ChatNotFoundError(chat_id)

    latest = await chat_repo.get_latest_version(chat_id)
    if latest is None:  # pragma: no cover - cannot happen, start_chat() always saves version 1
        raise ChatNotFoundError(chat_id)

    history = [
        HistoryMessage(role=message.role, content=message.content) for message in chat.messages
    ]

    now = datetime.now(UTC)
    await chat_repo.append_message(
        chat_id, ChatMessage(id=str(uuid.uuid4()), role="user", content=text, created_at=now)
    )

    response = await respond_to_message(latest.raw_recipe, history, text, language=language)

    if response.intent == "answer":
        await chat_repo.append_message(
            chat_id,
            ChatMessage(
                id=str(uuid.uuid4()),
                role="assistant",
                content=response.answer_text,
                intent="answer",
                version=None,
                created_at=datetime.now(UTC),
            ),
        )
        return SendMessageResponse(intent="answer", answer_text=response.answer_text)

    # intent == "revise"
    operations = response.operations or []
    try:
        patch_result = apply_operations(latest.raw_recipe, operations)
    except PatchError as first_error:
        retry_response = await respond_to_message(
            latest.raw_recipe, history, text, patch_error=str(first_error), language=language
        )
        if retry_response.intent != "revise" or not retry_response.operations:
            raise RevisionFailedError(
                f"Model could not produce a valid patch: {first_error}"
            ) from first_error
        try:
            patch_result = apply_operations(latest.raw_recipe, retry_response.operations)
            response = retry_response
        except PatchError as second_error:
            settings = get_llm_settings()
            if not settings.revise_fallback_to_full_regeneration:
                raise RevisionFailedError(
                    f"Patch still invalid after retry: {second_error}"
                ) from second_error
            fallback_prompt = _build_fallback_prompt(latest.raw_recipe, text)
            new_raw = await generate_raw_recipe(fallback_prompt, language=language)
            new_raw = _normalize_step_numbers(new_raw)
            patch_result = PatchResult(recipe=new_raw, change_log=[], warnings=[])
            response = retry_response

    new_version_number = latest.version + 1
    composed = await compose_recipe(patch_result.recipe)

    version = RecipeVersion(
        version=new_version_number,
        raw_recipe=patch_result.recipe,
        recipe=composed,
        operations=response.operations,
        change_log=patch_result.change_log,
        summary=response.answer_text,
        created_at=datetime.now(UTC),
        confirmed=False,
    )
    await chat_repo.save_version(chat_id, version)
    await chat_repo.append_message(
        chat_id,
        ChatMessage(
            id=str(uuid.uuid4()),
            role="assistant",
            content=response.answer_text,
            intent="revise",
            version=new_version_number,
            created_at=datetime.now(UTC),
        ),
    )

    return SendMessageResponse(
        intent="revise",
        answer_text=response.answer_text,
        version=new_version_number,
        recipe=composed,
        change_log=patch_result.change_log,
    )


async def confirm_recipe(
    chat_repo: ChatRepository,
    book_repo: RecipeBookRepository,
    user_id: str,
    chat_id: str,
    version: int | None,
) -> RecipeBookEntry:
    chat = await chat_repo.get_chat(user_id, chat_id)
    if chat is None:
        raise ChatNotFoundError(chat_id)

    target_version_number = (
        version if version is not None else (chat.versions[-1].version if chat.versions else None)
    )
    version_obj = next((v for v in chat.versions if v.version == target_version_number), None)
    if version_obj is None:
        raise VersionNotFoundError(f"chat {chat_id} has no version {target_version_number}")

    existing = await book_repo.find_entry(chat_id, version_obj.version)
    if existing is not None:
        return existing  # idempotent: confirming an already-confirmed version is a no-op

    entry = await book_repo.save_entry(user_id, chat_id, version_obj.version, version_obj.recipe)
    await chat_repo.mark_version_confirmed(chat_id, version_obj.version)
    return entry


async def list_chats(chat_repo: ChatRepository, user_id: str) -> list[ChatSummary]:
    return await chat_repo.list_chats(user_id)


async def get_chat(chat_repo: ChatRepository, user_id: str, chat_id: str) -> Chat:
    chat = await chat_repo.get_chat(user_id, chat_id)
    if chat is None:
        raise ChatNotFoundError(chat_id)
    return chat
