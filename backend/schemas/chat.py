"""Entity shapes for the chat layer: Chat, ChatMessage, RecipeVersion,
RecipeBookEntry. See docs/chat_contract.md for the full field reference.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.schemas.recipe import Recipe
from backend.services.recipe_patch import ChangeLogEntry
from llm.chat_schemas import Operation
from llm.schemas import RawRecipe


class ChatMessage(BaseModel):
    """One message in a chat's history."""

    model_config = ConfigDict(extra="forbid")

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    intent: Literal["answer", "revise"] | None = None
    """Set on assistant messages produced by send_message(); null for the
    user's own messages and for the initial "draft ready" assistant message."""
    version: int | None = None
    """Set on assistant messages that produced a new RecipeVersion (the
    initial draft, or a revision); null for question answers."""


class RecipeVersion(BaseModel):
    """One version of the recipe inside a chat. Version 1 is the initial
    draft from start_chat(); each accepted revision creates version n+1."""

    model_config = ConfigDict(extra="forbid")

    version: int
    raw_recipe: RawRecipe
    """Source of truth for this version - see docs/recipe_contract.md.
    Steps are always renumbered 1..N (see backend/services/chat_service.py),
    so operations on the NEXT revision can reference this numbering."""
    recipe: Recipe
    """Composed view (display_text, language, warnings) - always
    regeneratable from raw_recipe via compose_recipe()."""
    operations: list[Operation] | None = None
    """The operations that produced this version from the previous one.
    Null for version 1 (there is no previous version to patch)."""
    change_log: list[ChangeLogEntry] = []
    """Structured diff from the previous version. Empty for version 1."""
    summary: str | None = None
    """The model's answer_text for the revision that produced this version.
    Null for version 1."""
    created_at: datetime
    confirmed: bool = False


class Chat(BaseModel):
    """A full chat: messages and every recipe version, in order."""

    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessage]
    versions: list[RecipeVersion]


class ChatSummary(BaseModel):
    """One row in a user's chat list (GET /chats)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime
    confirmed: bool
    """True if at least one version of this chat has been confirmed into
    the recipe book."""
    latest_version: int


class RecipeBookEntry(BaseModel):
    """A confirmed recipe, saved to the user's recipe book."""

    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str
    chat_id: str
    version: int
    recipe: Recipe
    confirmed_at: datetime
