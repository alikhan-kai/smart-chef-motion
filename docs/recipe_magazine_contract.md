# Recipe magazine contract

This document is the reference for the recipe-magazine feature: a
shareable collection of recipes a user assembles from their own recipe
book (`backend/schemas/chat.py::RecipeBookEntry` - the user's full
confirmed-recipe *history*), gives a title/description/cover, and can
publish to an in-app market. **Not to be confused with the recipe book**:
the recipe book is the user's private history; a magazine is a curated,
optionally-public subset of it. See `backend/schemas/recipe_magazine.py`'s
module docstring for why a magazine's items are *snapshots* (a copy of the
`Recipe` at the moment it was added), not live references back into the
owner's recipe book.

## User scoping (same caveat as the chat/recipe-book contract)

**There is no real authentication.** `X-User-Id` is trusted as given (see
`backend/api/deps.py::get_user_id()`). A private magazine returns 404 (not
403) to anyone but its owner - existence is never revealed to a non-owner,
same rule as the rest of the app. A **public** magazine, by design, is
readable in full (including its recipes) by any `user_id`, including an
anonymous-looking one - that is the entire point of sharing it. View
counting (below) is likewise keyed only by whatever `user_id` the caller
sends, so it inherits the same trust assumption.

## Persistence

Backed by Supabase Postgres when `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` are
set (see `backend/config.py`); otherwise `backend/main.py` falls back to
in-memory repositories (this is what the test suite uses). Run once, by
hand, in the Supabase SQL editor:

```sql
create table recipe_book_entries (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    chat_id text not null,
    version int not null,
    recipe jsonb not null,
    confirmed_at timestamptz not null default now(),
    unique (chat_id, version)
);
create index on recipe_book_entries (user_id);

create table recipe_magazines (
    id uuid primary key default gen_random_uuid(),
    user_id text not null,
    title text not null,
    description text,
    cover_image bytea,
    cover_content_type text,
    is_public boolean not null default false,
    view_count int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index on recipe_magazines (user_id);
create index on recipe_magazines (is_public, view_count desc);

create table recipe_magazine_items (
    id uuid primary key default gen_random_uuid(),
    magazine_id uuid not null references recipe_magazines(id) on delete cascade,
    recipe jsonb not null,
    position int not null default 0,
    source_magazine_title text
);
create index on recipe_magazine_items (magazine_id);

create table recipe_magazine_views (
    magazine_id uuid not null references recipe_magazines(id) on delete cascade,
    viewer_user_id text not null,
    viewed_at timestamptz not null default now(),
    primary key (magazine_id, viewer_user_id)
);

-- Atomic view-count increment, called once per new (magazine, viewer) pair
-- (see SupabaseRecipeMagazineRepository.record_view).
create or replace function increment_magazine_view_count(magazine_id_input uuid)
returns void as $$
    update recipe_magazines set view_count = view_count + 1 where id = magazine_id_input;
$$ language sql;
```

`recipe_magazine_items.recipe` is a full `Recipe` JSON snapshot (see the
"snapshot, not reference" note above) - it is **not** a foreign key to
`recipe_book_entries`, precisely so that a shared magazine never needs to
read another user's recipe-book row. `source_magazine_title` is set only
when an item was saved from another magazine on the market (see
`save_market_item_to_my_magazine()`) - it is never cleared or overwritten
by later re-saves (the original author's magazine title is preserved even
through a chain of re-shares), which is the whole point: a saver can browse
and reuse anything public, but the UI must never show it as if the saver
created it themselves.

## Endpoints

All under `/recipe-magazines`, all requiring `X-User-Id` except the public
market listing and cover fetch:

| Method & path | Purpose |
|---|---|
| `POST /recipe-magazines` | Create a new, empty, private magazine. |
| `GET /recipe-magazines` | The caller's own magazines (drafts + published). |
| `GET /recipe-magazines/market?q=&sort=&limit=&offset=` | Published magazines only; `q` does an `ILIKE` on title+description (narrows the pool, doesn't change order). `sort` is `popular` (default, `view_count desc`) or `latest` (`created_at desc`). |
| `PATCH /recipe-magazines/{id}` | Update title/description (owner only). |
| `PUT /recipe-magazines/{id}/items` | Replace the full recipe list, by posting full `Recipe` objects directly (owner only) - see `SetMagazineItemsRequest`'s docstring for why this isn't `recipe_entry_ids`. |
| `PUT /recipe-magazines/{id}/cover` | Multipart upload; stored as raw bytes + content-type (owner only). |
| `GET /recipe-magazines/{id}/cover` | Raw image bytes, no auth needed. |
| `POST /recipe-magazines/{id}/share` / `.../unpublish` | Toggle `is_public` (owner only). |
| `DELETE /recipe-magazines/{id}` | Owner delete. |
| `GET /recipe-magazines/{id}` | Full detail (with recipes); 404 if private and not owned by caller. Records a view (deduped per viewer). |
| `POST /recipe-magazines/{id}/items/{item_id}/save` | Saves one recipe from a magazine visible to the caller (their own, or any public one) into a magazine the caller owns (`target_magazine_id` in the body); the saved item always carries `source_magazine_title`. |
