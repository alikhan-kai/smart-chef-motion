"""Shared FastAPI dependencies for the chat/recipe-book endpoints.

Unlike the pre-existing /recipes/* endpoints (which call services as plain
functions - see AGENTS.md/REPORT.md), the chat layer needs shared, mutable,
per-app-instance state (the in-memory repositories - a chat created by one
request must be readable by a later one), so it uses FastAPI's `Depends()` +
`app.state` here. This is a deliberately new, narrowly-scoped pattern for
this one concern; it does not change how /recipes/* is wired.

Auth is explicitly out of scope for this task (see AGENTS.md): `X-User-Id`
is trusted as given, with no verification whatsoever. A real deployment
MUST replace get_user_id() with real authentication (e.g. a verified JWT)
before this is safe to expose - see docs/chat_contract.md, "User scoping".
"""

from fastapi import Header, Request

from backend.repositories.chat_repo import ChatRepository
from backend.repositories.recipe_book_repo import RecipeBookRepository
from backend.repositories.recipe_magazine_repo import RecipeMagazineRepository


def get_user_id(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    return x_user_id


def get_chat_repository(request: Request) -> ChatRepository:
    repo: ChatRepository = request.app.state.chat_repository
    return repo


def get_recipe_book_repository(request: Request) -> RecipeBookRepository:
    repo: RecipeBookRepository = request.app.state.recipe_book_repository
    return repo


def get_recipe_magazine_repository(request: Request) -> RecipeMagazineRepository:
    repo: RecipeMagazineRepository = request.app.state.recipe_magazine_repository
    return repo
