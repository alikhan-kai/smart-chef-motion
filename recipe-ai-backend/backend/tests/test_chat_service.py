"""chat_service tests with in-memory repositories. generate_raw_recipe and
respond_to_message are mocked (monkeypatched at their call site in
backend.services.chat_service, same pattern as the existing endpoint tests);
everything else (compose_recipe, apply_operations, the repositories) is real.
"""

from unittest.mock import AsyncMock

import pytest

from backend.repositories.chat_repo import InMemoryChatRepository
from backend.repositories.recipe_book_repo import InMemoryRecipeBookRepository
from backend.services import chat_service
from llm.chat_schemas import (
    ChatResponse,
    Operation,
    RemoveIngredientOp,
    StepIngredientsUsedUpdate,
    UpdateStepOp,
)
from llm.schemas import RawIngredient, RawRecipe, RawStep

DRAFT_RECIPE = RawRecipe(
    error=None,
    title="Омлет",
    servings=2,
    total_time_minutes=None,
    equipment=["сковорода"],
    source_urls=[],
    notes=None,
    ingredients=[
        RawIngredient(id="eggs", name="яйца", amount=3, unit="шт", form=None),
        RawIngredient(id="salt1", name="соль", amount=None, unit="по вкусу", form=None),
    ],
    steps=[
        RawStep(
            step_number=1,
            action="Разбейте яйца в миску",
            ingredients_used=["eggs"],
            time_minutes=None,
            passive=False,
            heat_level=None,
            place="миска",
            salt=False,
            fat=None,
            final_action=None,
        ),
        RawStep(
            step_number=2,
            action="Посолите и взбейте",
            ingredients_used=["salt1"],
            time_minutes=1,
            passive=False,
            heat_level=None,
            place="миска",
            salt=True,
            fat=None,
            final_action=None,
        ),
    ],
)

REMOVE_SALT_OPS: list[Operation] = [
    UpdateStepOp(
        op="update_step",
        step_number=2,
        fields=[StepIngredientsUsedUpdate(field="ingredients_used", value=[])],
    ),
    RemoveIngredientOp(op="remove_ingredient", ingredient_id="salt1"),
]


def _chat_repo() -> InMemoryChatRepository:
    return InMemoryChatRepository()


def _book_repo() -> InMemoryRecipeBookRepository:
    return InMemoryRecipeBookRepository()


@pytest.fixture(autouse=True)
def _mock_generate_raw_recipe(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=DRAFT_RECIPE)
    monkeypatch.setattr("backend.services.chat_service.generate_raw_recipe", mock)
    return mock


async def _start_chat(chat_repo: InMemoryChatRepository, user_id: str = "u1") -> str:
    chat_id, _ = await chat_service.start_chat(chat_repo, user_id, "омлет")
    return chat_id


def _mock_respond(monkeypatch: pytest.MonkeyPatch, *responses: ChatResponse) -> AsyncMock:
    mock = AsyncMock(side_effect=list(responses))
    monkeypatch.setattr("backend.services.chat_service.respond_to_message", mock)
    return mock


# ---------------------------------------------------------------------------
# start_chat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_chat_creates_chat_with_draft_version_and_messages() -> None:
    chat_repo = _chat_repo()
    chat_id, version = await chat_service.start_chat(chat_repo, "u1", "омлет")

    assert version.version == 1
    assert version.recipe.title == "Омлет"
    assert version.confirmed is False

    chat = await chat_repo.get_chat("u1", chat_id)
    assert chat is not None
    assert len(chat.messages) == 2
    assert chat.messages[0].role == "user"
    assert chat.messages[0].content == "омлет"
    assert chat.messages[1].role == "assistant"
    assert chat.messages[1].version == 1
    assert len(chat.versions) == 1


# ---------------------------------------------------------------------------
# send_message: question
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_answer_case_no_new_version(monkeypatch: pytest.MonkeyPatch) -> None:
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo)
    _mock_respond(
        monkeypatch,
        ChatResponse(intent="answer", answer_text="Можно заменить сметаной.", operations=None),
    )

    result = await chat_service.send_message(chat_repo, "u1", chat_id, "чем заменить соль?")

    assert result.intent == "answer"
    assert result.version is None
    assert result.recipe is None
    chat = await chat_repo.get_chat("u1", chat_id)
    assert chat is not None
    assert len(chat.versions) == 1  # unchanged
    assert chat.messages[-1].intent == "answer"


# ---------------------------------------------------------------------------
# send_message: revision
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_revise_case_creates_new_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo)
    _mock_respond(
        monkeypatch,
        ChatResponse(intent="revise", answer_text="Убрал соль.", operations=REMOVE_SALT_OPS),
    )

    result = await chat_service.send_message(chat_repo, "u1", chat_id, "убери соль")

    assert result.intent == "revise"
    assert result.version == 2
    assert result.recipe is not None
    assert all(i.id != "salt1" for i in result.recipe.ingredients)
    assert result.change_log is not None
    assert len(result.change_log) == 2

    chat = await chat_repo.get_chat("u1", chat_id)
    assert chat is not None
    assert len(chat.versions) == 2
    assert chat.versions[1].operations == REMOVE_SALT_OPS
    assert chat.versions[1].summary == "Убрал соль."


@pytest.mark.asyncio
async def test_send_message_invalid_patch_then_retry_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo)
    bad_ops: list[Operation] = [
        RemoveIngredientOp(op="remove_ingredient", ingredient_id="does_not_exist")
    ]
    mock = _mock_respond(
        monkeypatch,
        ChatResponse(intent="revise", answer_text="Убрал соль.", operations=bad_ops),
        ChatResponse(
            intent="revise", answer_text="Убрал соль (исправлено).", operations=REMOVE_SALT_OPS
        ),
    )

    result = await chat_service.send_message(chat_repo, "u1", chat_id, "убери соль")

    assert result.intent == "revise"
    assert result.answer_text == "Убрал соль (исправлено)."
    assert mock.await_count == 2
    # the retry call received the patch error
    _, kwargs = mock.await_args_list[1]
    assert "does_not_exist" in kwargs["patch_error"]


@pytest.mark.asyncio
async def test_send_message_invalid_patch_retry_also_fails_raises_revision_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo)
    bad_ops: list[Operation] = [
        RemoveIngredientOp(op="remove_ingredient", ingredient_id="does_not_exist")
    ]
    _mock_respond(
        monkeypatch,
        ChatResponse(intent="revise", answer_text="A", operations=bad_ops),
        ChatResponse(intent="revise", answer_text="B", operations=bad_ops),
    )

    with pytest.raises(chat_service.RevisionFailedError):
        await chat_service.send_message(chat_repo, "u1", chat_id, "убери соль")

    chat = await chat_repo.get_chat("u1", chat_id)
    assert chat is not None
    assert len(chat.versions) == 1  # no bad version was ever saved


@pytest.mark.asyncio
async def test_send_message_retry_answers_instead_of_revising_raises_revision_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo)
    bad_ops: list[Operation] = [
        RemoveIngredientOp(op="remove_ingredient", ingredient_id="does_not_exist")
    ]
    _mock_respond(
        monkeypatch,
        ChatResponse(intent="revise", answer_text="A", operations=bad_ops),
        ChatResponse(intent="answer", answer_text="Не получилось.", operations=None),
    )

    with pytest.raises(chat_service.RevisionFailedError):
        await chat_service.send_message(chat_repo, "u1", chat_id, "убери соль")


@pytest.mark.asyncio
async def test_send_message_unknown_chat_raises_not_found() -> None:
    chat_repo = _chat_repo()
    with pytest.raises(chat_service.ChatNotFoundError):
        await chat_service.send_message(chat_repo, "u1", "does-not-exist", "hello")


@pytest.mark.asyncio
async def test_history_passed_to_respond_to_message_includes_prior_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo)
    mock = _mock_respond(
        monkeypatch, ChatResponse(intent="answer", answer_text="ok", operations=None)
    )

    await chat_service.send_message(chat_repo, "u1", chat_id, "вопрос")

    assert mock.await_args is not None
    args, _ = mock.await_args
    history = args[1]
    assert any(m.content == "омлет" for m in history)


# ---------------------------------------------------------------------------
# Fallback to full regeneration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fallback_to_full_regeneration_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REVISE_FALLBACK_TO_FULL_REGENERATION", "true")
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo)
    bad_ops: list[Operation] = [
        RemoveIngredientOp(op="remove_ingredient", ingredient_id="does_not_exist")
    ]
    _mock_respond(
        monkeypatch,
        ChatResponse(intent="revise", answer_text="A", operations=bad_ops),
        ChatResponse(intent="revise", answer_text="B", operations=bad_ops),
    )

    result = await chat_service.send_message(chat_repo, "u1", chat_id, "убери соль")

    assert result.intent == "revise"
    assert result.version == 2


# ---------------------------------------------------------------------------
# confirm_recipe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_recipe_creates_book_entry() -> None:
    chat_repo = _chat_repo()
    book_repo = _book_repo()
    chat_id = await _start_chat(chat_repo)

    entry = await chat_service.confirm_recipe(chat_repo, book_repo, "u1", chat_id, None)

    assert entry.chat_id == chat_id
    assert entry.version == 1
    assert entry.recipe.title == "Омлет"
    chat = await chat_repo.get_chat("u1", chat_id)
    assert chat is not None
    assert chat.versions[0].confirmed is True


@pytest.mark.asyncio
async def test_confirm_recipe_is_idempotent() -> None:
    chat_repo = _chat_repo()
    book_repo = _book_repo()
    chat_id = await _start_chat(chat_repo)

    entry1 = await chat_service.confirm_recipe(chat_repo, book_repo, "u1", chat_id, 1)
    entry2 = await chat_service.confirm_recipe(chat_repo, book_repo, "u1", chat_id, 1)

    assert entry1.id == entry2.id
    assert len(await book_repo.list_entries("u1")) == 1


@pytest.mark.asyncio
async def test_confirm_unknown_version_raises_version_not_found() -> None:
    chat_repo = _chat_repo()
    book_repo = _book_repo()
    chat_id = await _start_chat(chat_repo)

    with pytest.raises(chat_service.VersionNotFoundError):
        await chat_service.confirm_recipe(chat_repo, book_repo, "u1", chat_id, 99)


@pytest.mark.asyncio
async def test_reopen_confirmed_chat_and_revise_keeps_old_book_entry_and_adds_new_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_repo = _chat_repo()
    book_repo = _book_repo()
    chat_id = await _start_chat(chat_repo)

    entry_v1 = await chat_service.confirm_recipe(chat_repo, book_repo, "u1", chat_id, None)

    _mock_respond(
        monkeypatch,
        ChatResponse(intent="revise", answer_text="Убрал соль.", operations=REMOVE_SALT_OPS),
    )
    revise_result = await chat_service.send_message(chat_repo, "u1", chat_id, "убери соль")
    assert revise_result.version == 2

    # The v1 book entry must be untouched by the new draft.
    entries_after_revision = await book_repo.list_entries("u1")
    assert len(entries_after_revision) == 1
    assert entries_after_revision[0].id == entry_v1.id
    assert entries_after_revision[0].version == 1

    entry_v2 = await chat_service.confirm_recipe(chat_repo, book_repo, "u1", chat_id, 2)
    assert entry_v2.id != entry_v1.id
    assert entry_v2.version == 2

    entries_final = await book_repo.list_entries("u1")
    assert len(entries_final) == 2
    assert {e.version for e in entries_final} == {1, 2}


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_access_another_users_chat() -> None:
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo, user_id="owner")

    with pytest.raises(chat_service.ChatNotFoundError):
        await chat_service.get_chat(chat_repo, "someone-else", chat_id)


@pytest.mark.asyncio
async def test_user_cannot_send_message_to_another_users_chat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_repo = _chat_repo()
    chat_id = await _start_chat(chat_repo, user_id="owner")
    _mock_respond(monkeypatch, ChatResponse(intent="answer", answer_text="ok", operations=None))

    with pytest.raises(chat_service.ChatNotFoundError):
        await chat_service.send_message(chat_repo, "someone-else", chat_id, "hi")


@pytest.mark.asyncio
async def test_user_cannot_confirm_another_users_chat() -> None:
    chat_repo = _chat_repo()
    book_repo = _book_repo()
    chat_id = await _start_chat(chat_repo, user_id="owner")

    with pytest.raises(chat_service.ChatNotFoundError):
        await chat_service.confirm_recipe(chat_repo, book_repo, "someone-else", chat_id, None)


@pytest.mark.asyncio
async def test_list_chats_only_returns_own_chats() -> None:
    chat_repo = _chat_repo()
    await _start_chat(chat_repo, user_id="alice")
    await _start_chat(chat_repo, user_id="bob")

    alice_chats = await chat_service.list_chats(chat_repo, "alice")
    assert len(alice_chats) == 1
    bob_chats = await chat_service.list_chats(chat_repo, "bob")
    assert len(bob_chats) == 1
