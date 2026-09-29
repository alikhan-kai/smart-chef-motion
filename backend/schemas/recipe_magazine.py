"""Entity/request shapes for the recipe-magazine feature: a shareable
collection of recipes, distinct from the recipe *book* (RecipeBookEntry in
backend/schemas/chat.py), which is the user's full confirmed-recipe
history. See docs/recipe_magazine_contract.md for the full field reference.

A magazine's items are a *snapshot* of each selected recipe (copied at the
moment it's added), not a live reference back into the owner's recipe book.
This sidesteps a real access-control problem: recipe_book_entries are scoped
by owner (see RecipeBookRepository.get_entry), but a shared magazine must be
readable by *other* users - snapshotting avoids needing any "read someone
else's recipe book entry" backdoor.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from backend.schemas.recipe import Recipe


class RecipeMagazineItem(BaseModel):
    """One recipe inside a magazine - a snapshot, not a live reference."""

    model_config = ConfigDict(extra="forbid")

    id: str
    recipe: Recipe
    position: int
    source_magazine_title: str | None = None
    """Set when this item was saved from another user's shared magazine
    (see save_market_item_to_my_magazine()) - the title of that magazine at
    the moment it was saved, so the item is never displayed as if it were
    the saver's own creation. None for items added the normal way, from the
    owner's own recipe history."""


class RecipeMagazineSummary(BaseModel):
    """One row in a magazine listing (mine, or the market)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    user_id: str
    title: str
    description: str | None
    has_cover: bool
    is_public: bool
    view_count: int
    recipe_count: int
    created_at: datetime
    updated_at: datetime


class RecipeMagazineDetail(RecipeMagazineSummary):
    """Full magazine, including its recipes."""

    items: list[RecipeMagazineItem]


class RecipeMagazineCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str | None = None


class RecipeMagazineUpdateRequest(BaseModel):
    """All fields optional - only the ones provided are changed."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None


class SetMagazineItemsRequest(BaseModel):
    """Replaces a magazine's full recipe list, in order.

    Takes full `Recipe` objects rather than `recipe_entry_ids` referencing
    backend/schemas/chat.py's RecipeBookEntry: in practice, the frontend's
    "recipe history" (js/ui.js's history sidebar) is sourced from a Supabase
    `ai_requests` table the frontend queries directly, not from this
    backend's recipe-book endpoints - see REPORT.md's "Marketplace
    redesign + a cross-file X-User-Id bug fix" entry for how that was
    discovered. Accepting recipes directly here means the frontend can
    build a magazine out of whatever it already shows as "history",
    regardless of which of the two (overlapping, currently inconsistent)
    storage paths that recipe actually came from."""

    model_config = ConfigDict(extra="forbid")

    recipes: list[Recipe]


class SaveMarketItemRequest(BaseModel):
    """Saves one item from a magazine visible to the caller (their own, or
    any public one) into one of the caller's own magazines, with
    attribution - see RecipeMagazineItem.source_magazine_title."""

    model_config = ConfigDict(extra="forbid")

    target_magazine_id: str
