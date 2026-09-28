"""ChatRepository protocol + in-memory implementation.

Not backed by any real database (see AGENTS.md / REPORT.md: Supabase
persistence is a colleague's follow-up, out of scope here). Every method is
scoped by `user_id` where it reads/lists chats, so a user can never see or
touch another user's chat - see docs/chat_contract.md, "User scoping", for
the full rule (and why this is *not* real authentication).
"""

import uuid
from datetime import UTC, datetime
from typing import Protocol

from backend.schemas.chat import Chat, ChatMessage, ChatSummary, RecipeVersion


class ChatRepository(Protocol):
    async def create_chat(self, user_id: str, title: str | None) -> Chat:
        """Create a new, empty (no messages, no versions) chat for user_id."""
        ...

    async def append_message(self, chat_id: str, message: ChatMessage) -> None:
        """Append a message to an existing chat. Also bumps updated_at."""
        ...

    async def save_version(self, chat_id: str, version: RecipeVersion) -> None:
        """Append a new recipe version to an existing chat. Also bumps updated_at."""
        ...

    async def get_chat(self, user_id: str, chat_id: str) -> Chat | None:
        """Full chat (messages + versions), or None if it doesn't exist OR
        belongs to a different user (the caller cannot distinguish the two -
        see docs/chat_contract.md)."""
        ...

    async def list_chats(self, user_id: str) -> list[ChatSummary]:
        """This user's chats, newest-updated first."""
        ...

    async def get_latest_version(self, chat_id: str) -> RecipeVersion | None:
        """The chat's highest-numbered version, or None if it has none yet
        (should not happen once start_chat() has run)."""
        ...

    async def mark_version_confirmed(self, chat_id: str, version: int) -> None:
        """Flip a version's `confirmed` flag. Idempotent."""
        ...


class InMemoryChatRepository:
    """Process-memory ChatRepository. One instance per FastAPI app instance
    (see backend/main.py) - this gives each test its own isolated store
    (create_app() is called fresh per test) while sharing state across
    requests within one running app, which chats need (a chat created in
    one request must be readable in a later one)."""

    def __init__(self) -> None:
        self._chats: dict[str, Chat] = {}
        self._owners: dict[str, str] = {}  # chat_id -> user_id

    async def create_chat(self, user_id: str, title: str | None) -> Chat:
        now = datetime.now(UTC)
        chat = Chat(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            created_at=now,
            updated_at=now,
            messages=[],
            versions=[],
        )
        self._chats[chat.id] = chat
        self._owners[chat.id] = user_id
        return chat

    async def append_message(self, chat_id: str, message: ChatMessage) -> None:
        chat = self._chats[chat_id]
        chat.messages.append(message)
        chat.updated_at = datetime.now(UTC)

    async def save_version(self, chat_id: str, version: RecipeVersion) -> None:
        chat = self._chats[chat_id]
        chat.versions.append(version)
        chat.updated_at = datetime.now(UTC)

    async def get_chat(self, user_id: str, chat_id: str) -> Chat | None:
        chat = self._chats.get(chat_id)
        if chat is None or chat.user_id != user_id:
            return None
        return chat

    async def list_chats(self, user_id: str) -> list[ChatSummary]:
        chats = [chat for chat in self._chats.values() if chat.user_id == user_id]
        chats.sort(key=lambda chat: chat.updated_at, reverse=True)
        return [
            ChatSummary(
                id=chat.id,
                title=chat.title,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
                confirmed=any(version.confirmed for version in chat.versions),
                latest_version=chat.versions[-1].version if chat.versions else 0,
            )
            for chat in chats
        ]

    async def get_latest_version(self, chat_id: str) -> RecipeVersion | None:
        chat = self._chats.get(chat_id)
        if chat is None or not chat.versions:
            return None
        return chat.versions[-1]

    async def mark_version_confirmed(self, chat_id: str, version: int) -> None:
        chat = self._chats[chat_id]
        for stored_version in chat.versions:
            if stored_version.version == version:
                stored_version.confirmed = True
                return
