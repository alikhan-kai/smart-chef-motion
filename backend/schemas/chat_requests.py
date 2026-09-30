"""Request/response models for the chat endpoints (backend/api/routes_chats.py,
routes_recipe_book.py). See docs/chat_contract.md for full examples.
"""

from typing import Literal

from pydantic import BaseModel

from backend.schemas.recipe import Recipe
from backend.schemas.requests import RecipeRequest
from backend.services.recipe_patch import ChangeLogEntry
from llm.language import OutputLanguage

# POST /chats reuses RecipeRequest (prompt, allergies, preferred_units) - same
# body shape as POST /recipes/create.
StartChatRequest = RecipeRequest


class StartChatResponse(BaseModel):
    chat_id: str
    version: int
    recipe: Recipe


class SendMessageRequest(BaseModel):
    text: str
    language: OutputLanguage | None = None


class SendMessageResponse(BaseModel):
    intent: Literal["answer", "revise"]
    answer_text: str
    version: int | None = None
    """Set only when intent == "revise": the new version's number."""
    recipe: Recipe | None = None
    """Set only when intent == "revise": the newly composed recipe."""
    change_log: list[ChangeLogEntry] | None = None
    """Set only when intent == "revise": the structured diff from the
    previous version - this is the diff the frontend renders, no separate
    diff computation needed."""


class ConfirmRequest(BaseModel):
    version: int | None = None
    """null means "confirm the latest version"."""
