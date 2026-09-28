from fastapi import APIRouter, Depends

from backend.api.deps import get_chat_repository, get_recipe_book_repository, get_user_id
from backend.repositories.chat_repo import ChatRepository
from backend.repositories.recipe_book_repo import RecipeBookRepository
from backend.schemas.chat import Chat, ChatSummary, RecipeBookEntry
from backend.schemas.chat_requests import (
    ConfirmRequest,
    SendMessageRequest,
    SendMessageResponse,
    StartChatRequest,
    StartChatResponse,
)
from backend.services import chat_service

router = APIRouter()


@router.post("/chats", response_model=StartChatResponse)
async def start_chat_endpoint(
    body: StartChatRequest,
    user_id: str = Depends(get_user_id),
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> StartChatResponse:
    chat_id, version = await chat_service.start_chat(
        chat_repo, user_id, body.prompt, body.allergies, body.preferred_units
    )
    return StartChatResponse(chat_id=chat_id, version=version.version, recipe=version.recipe)


@router.post("/chats/{chat_id}/messages", response_model=SendMessageResponse)
async def send_message_endpoint(
    chat_id: str,
    body: SendMessageRequest,
    user_id: str = Depends(get_user_id),
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> SendMessageResponse:
    return await chat_service.send_message(chat_repo, user_id, chat_id, body.text)


@router.post("/chats/{chat_id}/confirm", response_model=RecipeBookEntry)
async def confirm_recipe_endpoint(
    chat_id: str,
    body: ConfirmRequest,
    user_id: str = Depends(get_user_id),
    chat_repo: ChatRepository = Depends(get_chat_repository),
    book_repo: RecipeBookRepository = Depends(get_recipe_book_repository),
) -> RecipeBookEntry:
    return await chat_service.confirm_recipe(chat_repo, book_repo, user_id, chat_id, body.version)


@router.get("/chats", response_model=list[ChatSummary])
async def list_chats_endpoint(
    user_id: str = Depends(get_user_id),
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> list[ChatSummary]:
    return await chat_service.list_chats(chat_repo, user_id)


@router.get("/chats/{chat_id}", response_model=Chat)
async def get_chat_endpoint(
    chat_id: str,
    user_id: str = Depends(get_user_id),
    chat_repo: ChatRepository = Depends(get_chat_repository),
) -> Chat:
    return await chat_service.get_chat(chat_repo, user_id, chat_id)
