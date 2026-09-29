"""RecipeMagazineRepository protocol + in-memory implementation.

See backend/repositories/chat_repo.py's module docstring for the same
"not a real database (InMemory), scoped by user_id" caveats - they apply
here too, with one addition: a magazine that is_public is readable by ANY
user_id (not just its owner) - that is the entire point of sharing it. See
backend/schemas/recipe_magazine.py for why items are snapshots, not live
references into the owner's recipe book.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

from postgrest import APIError
from postgrest.types import CountMethod
from supabase import Client

from backend.schemas.recipe import Recipe
from backend.schemas.recipe_magazine import (
    RecipeMagazineDetail,
    RecipeMagazineItem,
    RecipeMagazineSummary,
)

MagazineSort = Literal["popular", "latest"]


class RecipeMagazineRepository(Protocol):
    async def create(
        self, user_id: str, title: str, description: str | None
    ) -> RecipeMagazineSummary:
        """Create a new, empty, private magazine."""
        ...

    async def update(
        self,
        magazine_id: str,
        user_id: str,
        title: str | None,
        description: str | None,
    ) -> RecipeMagazineSummary | None:
        """Update title/description (only the given fields). None if the
        magazine doesn't exist or isn't owned by user_id."""
        ...

    async def set_items(
        self, magazine_id: str, user_id: str, recipes: list[Recipe]
    ) -> RecipeMagazineSummary | None:
        """Replace the magazine's full recipe list, in the given order.
        None if the magazine doesn't exist or isn't owned by user_id."""
        ...

    async def append_item(
        self,
        magazine_id: str,
        user_id: str,
        recipe: Recipe,
        source_magazine_title: str | None,
    ) -> RecipeMagazineSummary | None:
        """Appends one recipe to the end of the magazine's item list
        (unlike set_items(), this does not touch existing items). None if
        the magazine doesn't exist or isn't owned by user_id."""
        ...

    async def set_cover(
        self, magazine_id: str, user_id: str, content: bytes, content_type: str
    ) -> bool:
        """True if the magazine exists and is owned by user_id."""
        ...

    async def get_cover(self, magazine_id: str) -> tuple[bytes, str] | None:
        """Raw cover bytes + content type, or None if there is no cover
        (or no such magazine)."""
        ...

    async def set_public(
        self, magazine_id: str, user_id: str, is_public: bool
    ) -> RecipeMagazineSummary | None:
        """Share (True) or unpublish (False). None if the magazine doesn't
        exist or isn't owned by user_id."""
        ...

    async def delete(self, magazine_id: str, user_id: str) -> bool:
        """True if a magazine owned by user_id was deleted."""
        ...

    async def get_detail(
        self, magazine_id: str, viewer_user_id: str
    ) -> RecipeMagazineDetail | None:
        """Full magazine with its items. None if it doesn't exist, or is
        private and viewer_user_id isn't the owner (same "not found, never
        forbidden" rule as the rest of the app)."""
        ...

    async def list_mine(self, user_id: str) -> list[RecipeMagazineSummary]:
        """This user's own magazines (draft + published), newest first."""
        ...

    async def list_market(
        self, query: str | None, sort: MagazineSort, limit: int, offset: int
    ) -> list[RecipeMagazineSummary]:
        """Published magazines only. When query is given, only those whose
        title or description ILIKE-match it (search narrows the pool, it
        doesn't change the order). `sort` picks the order: "popular" is
        view_count descending, "latest" is created_at descending."""
        ...

    async def record_view(self, magazine_id: str, viewer_user_id: str) -> None:
        """Increments view_count the first time this viewer_user_id opens
        this magazine; a no-op on every later view from the same viewer."""
        ...


class InMemoryRecipeMagazineRepository:
    """Process-memory RecipeMagazineRepository. See InMemoryChatRepository's
    docstring for why this is scoped per FastAPI app instance."""

    def __init__(self) -> None:
        self._magazines: dict[str, dict[str, Any]] = {}
        self._covers: dict[str, tuple[bytes, str]] = {}
        self._views: set[tuple[str, str]] = set()  # (magazine_id, viewer_user_id)

    def _summary(self, row: dict[str, Any]) -> RecipeMagazineSummary:
        return RecipeMagazineSummary(
            id=row["id"],
            user_id=row["user_id"],
            title=row["title"],
            description=row["description"],
            has_cover=row["id"] in self._covers,
            is_public=row["is_public"],
            view_count=row["view_count"],
            recipe_count=len(row["items"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def create(
        self, user_id: str, title: str, description: str | None
    ) -> RecipeMagazineSummary:
        now = datetime.now(UTC)
        row: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "title": title,
            "description": description,
            "is_public": False,
            "view_count": 0,
            "created_at": now,
            "updated_at": now,
            "items": [],  # list[RecipeMagazineItem]
        }
        self._magazines[row["id"]] = row
        return self._summary(row)

    def _owned(self, magazine_id: str, user_id: str) -> dict[str, Any] | None:
        row = self._magazines.get(magazine_id)
        if row is None or row["user_id"] != user_id:
            return None
        return row

    async def update(
        self,
        magazine_id: str,
        user_id: str,
        title: str | None,
        description: str | None,
    ) -> RecipeMagazineSummary | None:
        row = self._owned(magazine_id, user_id)
        if row is None:
            return None
        if title is not None:
            row["title"] = title
        if description is not None:
            row["description"] = description
        row["updated_at"] = datetime.now(UTC)
        return self._summary(row)

    async def set_items(
        self, magazine_id: str, user_id: str, recipes: list[Recipe]
    ) -> RecipeMagazineSummary | None:
        row = self._owned(magazine_id, user_id)
        if row is None:
            return None
        row["items"] = [
            RecipeMagazineItem(id=str(uuid.uuid4()), recipe=recipe, position=position)
            for position, recipe in enumerate(recipes)
        ]
        row["updated_at"] = datetime.now(UTC)
        return self._summary(row)

    async def append_item(
        self,
        magazine_id: str,
        user_id: str,
        recipe: Recipe,
        source_magazine_title: str | None,
    ) -> RecipeMagazineSummary | None:
        row = self._owned(magazine_id, user_id)
        if row is None:
            return None
        row["items"].append(
            RecipeMagazineItem(
                id=str(uuid.uuid4()),
                recipe=recipe,
                position=len(row["items"]),
                source_magazine_title=source_magazine_title,
            )
        )
        row["updated_at"] = datetime.now(UTC)
        return self._summary(row)

    async def set_cover(
        self, magazine_id: str, user_id: str, content: bytes, content_type: str
    ) -> bool:
        row = self._owned(magazine_id, user_id)
        if row is None:
            return False
        self._covers[magazine_id] = (content, content_type)
        row["updated_at"] = datetime.now(UTC)
        return True

    async def get_cover(self, magazine_id: str) -> tuple[bytes, str] | None:
        return self._covers.get(magazine_id)

    async def set_public(
        self, magazine_id: str, user_id: str, is_public: bool
    ) -> RecipeMagazineSummary | None:
        row = self._owned(magazine_id, user_id)
        if row is None:
            return None
        row["is_public"] = is_public
        row["updated_at"] = datetime.now(UTC)
        return self._summary(row)

    async def delete(self, magazine_id: str, user_id: str) -> bool:
        row = self._owned(magazine_id, user_id)
        if row is None:
            return False
        del self._magazines[magazine_id]
        self._covers.pop(magazine_id, None)
        return True

    async def get_detail(
        self, magazine_id: str, viewer_user_id: str
    ) -> RecipeMagazineDetail | None:
        row = self._magazines.get(magazine_id)
        if row is None:
            return None
        if not row["is_public"] and row["user_id"] != viewer_user_id:
            return None
        return RecipeMagazineDetail(**self._summary(row).model_dump(), items=row["items"])

    async def list_mine(self, user_id: str) -> list[RecipeMagazineSummary]:
        rows = [row for row in self._magazines.values() if row["user_id"] == user_id]
        rows.sort(key=lambda row: row["updated_at"], reverse=True)
        return [self._summary(row) for row in rows]

    async def list_market(
        self, query: str | None, sort: MagazineSort, limit: int, offset: int
    ) -> list[RecipeMagazineSummary]:
        rows = [row for row in self._magazines.values() if row["is_public"]]
        if query:
            needle = query.casefold()
            rows = [
                row
                for row in rows
                if needle in row["title"].casefold()
                or (row["description"] is not None and needle in row["description"].casefold())
            ]
        if sort == "latest":
            rows.sort(key=lambda row: row["created_at"], reverse=True)
        else:
            rows.sort(key=lambda row: row["view_count"], reverse=True)
        return [self._summary(row) for row in rows[offset : offset + limit]]

    async def record_view(self, magazine_id: str, viewer_user_id: str) -> None:
        key = (magazine_id, viewer_user_id)
        if key in self._views:
            return
        row = self._magazines.get(magazine_id)
        if row is None:
            return
        self._views.add(key)
        row["view_count"] += 1


def _row_to_summary(row: dict[str, Any]) -> RecipeMagazineSummary:
    return RecipeMagazineSummary(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        description=row["description"],
        has_cover=row["cover_image"] is not None,
        is_public=row["is_public"],
        view_count=row["view_count"],
        recipe_count=row["recipe_count"] if "recipe_count" in row else 0,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SupabaseRecipeMagazineRepository:
    """RecipeMagazineRepository backed by the `recipe_magazines` /
    `recipe_magazine_items` / `recipe_magazine_views` tables (see
    docs/recipe_magazine_contract.md for the schema). Uses supabase-py's
    synchronous client under `asyncio.to_thread`, same approach as
    SupabaseRecipeBookRepository."""

    def __init__(self, client: Client) -> None:
        self._client = client

    async def create(
        self, user_id: str, title: str, description: str | None
    ) -> RecipeMagazineSummary:
        def _insert() -> dict[str, Any]:
            response = (
                self._client.table("recipe_magazines")
                .insert({"user_id": user_id, "title": title, "description": description})
                .execute()
            )
            return cast(dict[str, Any], response.data[0])

        row = await asyncio.to_thread(_insert)
        row["recipe_count"] = 0
        return _row_to_summary(row)

    async def _get_owned_row(self, magazine_id: str, user_id: str) -> dict[str, Any] | None:
        def _select() -> dict[str, Any] | None:
            response = (
                self._client.table("recipe_magazines")
                .select("*")
                .eq("id", magazine_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            rows = cast(list[dict[str, Any]], response.data)
            return rows[0] if rows else None

        return await asyncio.to_thread(_select)

    async def _count_items(self, magazine_id: str) -> int:
        def _count() -> int:
            response = (
                self._client.table("recipe_magazine_items")
                .select("id", count=CountMethod.exact)
                .eq("magazine_id", magazine_id)
                .execute()
            )
            return response.count or 0

        return await asyncio.to_thread(_count)

    async def update(
        self,
        magazine_id: str,
        user_id: str,
        title: str | None,
        description: str | None,
    ) -> RecipeMagazineSummary | None:
        if await self._get_owned_row(magazine_id, user_id) is None:
            return None

        fields: dict[str, Any] = {"updated_at": datetime.now(UTC).isoformat()}
        if title is not None:
            fields["title"] = title
        if description is not None:
            fields["description"] = description

        def _update() -> dict[str, Any]:
            response = (
                self._client.table("recipe_magazines")
                .update(fields)
                .eq("id", magazine_id)
                .execute()
            )
            return cast(dict[str, Any], response.data[0])

        row = await asyncio.to_thread(_update)
        row["recipe_count"] = await self._count_items(magazine_id)
        return _row_to_summary(row)

    async def set_items(
        self, magazine_id: str, user_id: str, recipes: list[Recipe]
    ) -> RecipeMagazineSummary | None:
        owned_row = await self._get_owned_row(magazine_id, user_id)
        if owned_row is None:
            return None

        def _replace() -> None:
            self._client.table("recipe_magazine_items").delete().eq(
                "magazine_id", magazine_id
            ).execute()
            if recipes:
                self._client.table("recipe_magazine_items").insert(
                    [
                        {
                            "magazine_id": magazine_id,
                            "recipe": recipe.model_dump(mode="json"),
                            "position": position,
                        }
                        for position, recipe in enumerate(recipes)
                    ]
                ).execute()

        await asyncio.to_thread(_replace)

        def _touch() -> dict[str, Any]:
            response = (
                self._client.table("recipe_magazines")
                .update({"updated_at": datetime.now(UTC).isoformat()})
                .eq("id", magazine_id)
                .execute()
            )
            return cast(dict[str, Any], response.data[0])

        row = await asyncio.to_thread(_touch)
        row["recipe_count"] = len(recipes)
        return _row_to_summary(row)

    async def append_item(
        self,
        magazine_id: str,
        user_id: str,
        recipe: Recipe,
        source_magazine_title: str | None,
    ) -> RecipeMagazineSummary | None:
        if await self._get_owned_row(magazine_id, user_id) is None:
            return None

        def _append() -> None:
            next_position = (
                self._client.table("recipe_magazine_items")
                .select("id", count=CountMethod.exact)
                .eq("magazine_id", magazine_id)
                .execute()
                .count
                or 0
            )
            self._client.table("recipe_magazine_items").insert(
                {
                    "magazine_id": magazine_id,
                    "recipe": recipe.model_dump(mode="json"),
                    "position": next_position,
                    "source_magazine_title": source_magazine_title,
                }
            ).execute()

        await asyncio.to_thread(_append)

        def _touch() -> dict[str, Any]:
            response = (
                self._client.table("recipe_magazines")
                .update({"updated_at": datetime.now(UTC).isoformat()})
                .eq("id", magazine_id)
                .execute()
            )
            return cast(dict[str, Any], response.data[0])

        row = await asyncio.to_thread(_touch)
        row["recipe_count"] = await self._count_items(magazine_id)
        return _row_to_summary(row)

    async def set_cover(
        self, magazine_id: str, user_id: str, content: bytes, content_type: str
    ) -> bool:
        if await self._get_owned_row(magazine_id, user_id) is None:
            return False

        def _update() -> None:
            self._client.table("recipe_magazines").update(
                {
                    "cover_image": "\\x" + content.hex(),
                    "cover_content_type": content_type,
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            ).eq("id", magazine_id).execute()

        await asyncio.to_thread(_update)
        return True

    async def get_cover(self, magazine_id: str) -> tuple[bytes, str] | None:
        def _select() -> dict[str, Any] | None:
            response = (
                self._client.table("recipe_magazines")
                .select("cover_image,cover_content_type")
                .eq("id", magazine_id)
                .limit(1)
                .execute()
            )
            rows = cast(list[dict[str, Any]], response.data)
            return rows[0] if rows else None

        row = await asyncio.to_thread(_select)
        if row is None or row["cover_image"] is None:
            return None
        hex_value = row["cover_image"].removeprefix("\\x")
        return bytes.fromhex(hex_value), row["cover_content_type"]

    async def set_public(
        self, magazine_id: str, user_id: str, is_public: bool
    ) -> RecipeMagazineSummary | None:
        if await self._get_owned_row(magazine_id, user_id) is None:
            return None

        def _update() -> dict[str, Any]:
            response = (
                self._client.table("recipe_magazines")
                .update({"is_public": is_public, "updated_at": datetime.now(UTC).isoformat()})
                .eq("id", magazine_id)
                .execute()
            )
            return cast(dict[str, Any], response.data[0])

        row = await asyncio.to_thread(_update)
        row["recipe_count"] = await self._count_items(magazine_id)
        return _row_to_summary(row)

    async def delete(self, magazine_id: str, user_id: str) -> bool:
        if await self._get_owned_row(magazine_id, user_id) is None:
            return False

        def _delete() -> None:
            self._client.table("recipe_magazines").delete().eq("id", magazine_id).execute()

        await asyncio.to_thread(_delete)
        return True

    async def get_detail(
        self, magazine_id: str, viewer_user_id: str
    ) -> RecipeMagazineDetail | None:
        def _select_magazine() -> dict[str, Any] | None:
            response = (
                self._client.table("recipe_magazines")
                .select("*")
                .eq("id", magazine_id)
                .limit(1)
                .execute()
            )
            rows = cast(list[dict[str, Any]], response.data)
            return rows[0] if rows else None

        row = await asyncio.to_thread(_select_magazine)
        if row is None:
            return None
        if not row["is_public"] and row["user_id"] != viewer_user_id:
            return None

        def _select_items() -> list[dict[str, Any]]:
            response = (
                self._client.table("recipe_magazine_items")
                .select("*")
                .eq("magazine_id", magazine_id)
                .order("position")
                .execute()
            )
            return cast(list[dict[str, Any]], response.data)

        item_rows = await asyncio.to_thread(_select_items)
        items = [
            RecipeMagazineItem(
                id=item_row["id"],
                recipe=Recipe.model_validate(item_row["recipe"]),
                position=item_row["position"],
                source_magazine_title=item_row.get("source_magazine_title"),
            )
            for item_row in item_rows
        ]
        row["recipe_count"] = len(items)
        return RecipeMagazineDetail(**_row_to_summary(row).model_dump(), items=items)

    async def list_mine(self, user_id: str) -> list[RecipeMagazineSummary]:
        def _select() -> list[dict[str, Any]]:
            response = (
                self._client.table("recipe_magazines")
                .select("*")
                .eq("user_id", user_id)
                .order("updated_at", desc=True)
                .execute()
            )
            return cast(list[dict[str, Any]], response.data)

        rows = await asyncio.to_thread(_select)
        summaries = []
        for row in rows:
            row["recipe_count"] = await self._count_items(row["id"])
            summaries.append(_row_to_summary(row))
        return summaries

    async def list_market(
        self, query: str | None, sort: MagazineSort, limit: int, offset: int
    ) -> list[RecipeMagazineSummary]:
        order_column = "created_at" if sort == "latest" else "view_count"

        def _select() -> list[dict[str, Any]]:
            builder = self._client.table("recipe_magazines").select("*").eq("is_public", True)
            if query:
                escaped = query.replace("%", r"\%").replace(",", r"\,")
                builder = builder.or_(f"title.ilike.%{escaped}%,description.ilike.%{escaped}%")
            response = (
                builder.order(order_column, desc=True).range(offset, offset + limit - 1).execute()
            )
            return cast(list[dict[str, Any]], response.data)

        rows = await asyncio.to_thread(_select)
        summaries = []
        for row in rows:
            row["recipe_count"] = await self._count_items(row["id"])
            summaries.append(_row_to_summary(row))
        return summaries

    async def record_view(self, magazine_id: str, viewer_user_id: str) -> None:
        def _record() -> bool:
            try:
                self._client.table("recipe_magazine_views").insert(
                    {"magazine_id": magazine_id, "viewer_user_id": viewer_user_id}
                ).execute()
                return True
            except APIError as exc:
                if exc.code == "23505":  # unique_violation: already viewed by this user
                    return False
                raise

        inserted = await asyncio.to_thread(_record)
        if not inserted:
            return

        def _increment() -> None:
            self._client.rpc(
                "increment_magazine_view_count", {"magazine_id_input": magazine_id}
            ).execute()

        await asyncio.to_thread(_increment)
