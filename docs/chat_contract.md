# Chat contract

This document is the reference for building Supabase persistence for the
chat layer (`ChatRepository`, `RecipeBookRepository`). It complements
[`recipe_contract.md`](recipe_contract.md), which documents `RawRecipe` and
`Recipe` themselves — read that one first if you haven't. Everything here
was verified against a real, live chat run (see REPORT.md, Verification) —
the JSON examples below are trimmed real output, not hand-written mocks.

> **The raw JSON of each version is the source of truth**, exactly as for a
> standalone recipe (see recipe_contract.md). `RecipeVersion.raw_recipe` is
> what revisions are computed from and validated against; `RecipeVersion.recipe`
> (the composed view, with `display_text`) is always regeneratable from it
> via `compose_recipe()`. Persist `raw_recipe`, `operations`, and
> `change_log` as first-class data — don't treat the composed `recipe` as
> the only thing worth storing.

## No LLM call in the patch path

Worth restating because it matters for how you think about consistency:
applying a revision (`backend/services/recipe_patch.py::apply_operations`)
is pure, deterministic, synchronous code with no I/O. The only LLM call in
`send_message()` is `respond_to_message()`, which turns free text into a
list of operations; everything after that (validating references, applying
them, renumbering, computing the diff) is ordinary application code you can
reason about and test without a model in the loop.

## User scoping (read before wiring auth)

**There is no real authentication in this codebase.** Every endpoint reads
a `user_id` from the `X-User-Id` request header and trusts it completely -
see `backend/api/deps.py::get_user_id()`. Every repository method that
reads a chat or recipe-book entry takes `user_id` and returns "not found"
(never a distinct "forbidden") when the resource exists but belongs to
someone else - this is deliberate: **existence is never revealed to a
non-owner**, so `GET /chats/{id}` on someone else's chat and `GET
/chats/{id}` on a nonexistent id both return a plain 404 with no way to
tell them apart.

**Before this goes anywhere near production, `X-User-Id` must be replaced
by real authentication** (e.g. a verified session or JWT whose subject
claim becomes `user_id`) - anyone can currently claim to be any user simply
by setting the header. This is called out again in REPORT.md's Open
issues; it is the single most important thing to fix before this is safe
to expose.

## Entities

### `ChatMessage`

One message in a chat's history (`backend/schemas/chat.py`).

```jsonc
{
  "id": "983f9598-a0c1-4c84-bc0c-9ad79fe23902",
  "role": "user",
  "content": "омлет с грибами и луком",
  "created_at": "2026-09-28T10:59:17.706610Z",
  "intent": null,
  "version": null
}
```
```jsonc
{
  "id": "1d43f436-7061-42a8-bd03-ad11984c9757",
  "role": "assistant",
  "content": "Черновик рецепта «Омлет с шампиньонами и луком» готов. Можете задать вопрос об этом рецепте или попросить внести изменения.",
  "created_at": "2026-09-28T10:59:17.706610Z",
  "intent": null,
  "version": 1
}
```

| Field | Type | Meaning |
|---|---|---|
| `id` | `string` (UUID4) | Generated when the message is appended. |
| `role` | `"user" \| "assistant"` | |
| `content` | `string` | The message text. For a user message, verbatim what they typed. For an assistant message, either the model's `answer_text` (question or revision summary) or the templated "draft ready" text for version 1. |
| `created_at` | `string` (ISO 8601, UTC) | |
| `intent` | `"answer" \| "revise" \| null` | Set only on assistant messages produced by `send_message()`; `null` for user messages and for the initial "draft ready" message (which isn't a response to a question). |
| `version` | `integer \| null` | Set on the assistant message that produced a `RecipeVersion` (the initial draft = 1, or a revision = its new version number); `null` for question answers. |

### `RecipeVersion`

One version of the recipe inside a chat. Version 1 is the initial draft
from `start_chat()`; each accepted revision creates version *n+1*.

```jsonc
{
  "version": 2,
  "raw_recipe": { "...": "full RawRecipe, see recipe_contract.md" },
  "recipe": { "...": "full composed Recipe, see recipe_contract.md" },
  "operations": [
    { "op": "remove_ingredient", "ingredient_id": "onion" },
    {
      "op": "update_step",
      "step_number": 1,
      "fields": [{ "field": "ingredients_used", "value": [] }]
    }
    // ... one entry per step that referenced "onion"
  ],
  "change_log": [
    {
      "kind": "ingredient_removed",
      "target": "onion",
      "before": { "id": "onion", "name": "репчатый лук", "amount": 1.0, "unit": "шт.", "form": "тонко нарезать" },
      "after": null
    },
    {
      "kind": "step_changed",
      "target": "1",
      "before": { "step_number": 1, "action": "Подготовьте ингредиенты: тонко нарежьте лук.", "ingredients_used": ["onion"], "...": "..." },
      "after": { "step_number": 1, "action": "Подготовьте ингредиенты.", "ingredients_used": [], "...": "..." }
    }
    // ... one entry per changed/added/removed ingredient or step
  ],
  "summary": "Убрал лук из рецепта и удалил упоминания о нём в шагах 1, 4, 5, 6, 11 и 14.",
  "created_at": "2026-09-28T11:00:05.716079Z",
  "confirmed": false
}
```

| Field | Type | Meaning |
|---|---|---|
| `version` | `integer` | 1, 2, 3, ... within this chat. |
| `raw_recipe` | `RawRecipe` | **Source of truth for this version.** Always has contiguous 1..N step numbering (normalized right after generation for v1, and after every patch for v2+) - the numbering the NEXT revision's `step_number`/`after_step_number` operations are resolved against. |
| `recipe` | `Recipe` | Composed view (see recipe_contract.md) - `display_text`, detected `language`, `warnings`. Always regeneratable: `compose_recipe(raw_recipe)`. Note `Recipe.id` is a fresh UUID assigned by `compose_recipe()` on every call - it is **not** a stable identifier for this version; use `(chat_id, version)` for that. |
| `operations` | `Operation[] \| null` | The operations that produced this version from the previous one (see "Operation format" below). `null` for version 1 - there is no previous version to patch. |
| `change_log` | `ChangeLogEntry[]` | Structured diff from the previous version - **this is what the frontend renders**, no separate diff computation needed. Empty for version 1. |
| `summary` | `string \| null` | The model's `answer_text` for the revision that produced this version, in the language of the user's request. `null` for version 1. |
| `created_at` | `string` (ISO 8601, UTC) | |
| `confirmed` | `boolean` | Set by `confirm_recipe()`. A version can be confirmed after later versions already exist (an old draft doesn't retroactively become "current" - see "Reopening a confirmed chat" below). |

**`ChangeLogEntry`** (`backend/services/recipe_patch.py`):

| Field | Type | Meaning |
|---|---|---|
| `kind` | `"ingredient_added" \| "ingredient_removed" \| "ingredient_changed" \| "step_added" \| "step_removed" \| "step_changed" \| "meta_changed"` | |
| `target` | `string \| null` | ingredient id, original step number (as a string), or meta field name. `null` for `step_added` (a new step has no prior number to reference). |
| `before` | ingredient / step / scalar / `null` | Omitted (`null`) for `*_added`. |
| `after` | ingredient / step / scalar / `null` | Omitted (`null`) for `*_removed`. |

### `Chat`

```jsonc
{
  "id": "ea439555-0fd1-4b98-a633-b392ccc49d3f",
  "user_id": "live-verify-user",
  "title": "Омлет с шампиньонами и луком",
  "created_at": "2026-09-28T10:59:17.706440Z",
  "updated_at": "2026-09-28T11:00:49.847657Z",
  "messages": [ "... ChatMessage[] ..." ],
  "versions": [ "... RecipeVersion[] ..." ]
}
```

`title` is set once, from version 1's `recipe.title`, and is **not**
updated automatically when a later revision changes the recipe's title via
`update_meta` - see REPORT.md's "Open questions for the product owner".

### `ChatSummary`

One row of `GET /chats` - everything above except the full `messages`/`versions` arrays:

```jsonc
{
  "id": "ea439555-0fd1-4b98-a633-b392ccc49d3f",
  "title": "Омлет с шампиньонами и луком",
  "created_at": "2026-09-28T10:59:17.706440Z",
  "updated_at": "2026-09-28T11:00:49.847657Z",
  "confirmed": true,
  "latest_version": 3
}
```
`confirmed` is true if **any** version of the chat has been confirmed
(there is no single "the chat's confirmation status" beyond that - a chat
can have version 1 confirmed and versions 2-3 as unconfirmed later drafts,
simultaneously; see "Reopening a confirmed chat").

### `RecipeBookEntry`

A confirmed recipe. One row per confirmed `(chat_id, version)` pair -
**never overwritten**, see "Reopening a confirmed chat" below.

```jsonc
{
  "id": "fc36066c-e90a-480a-9cc3-1b1ea4981e76",
  "user_id": "live-verify-user",
  "chat_id": "ea439555-0fd1-4b98-a633-b392ccc49d3f",
  "version": 3,
  "recipe": { "...": "full composed Recipe" },
  "confirmed_at": "2026-09-28T11:00:49.847657Z"
}
```

## Reopening a confirmed chat (the task's open question, answered)

**What happens if a user reopens a chat whose recipe is already confirmed
and asks for a change?** Implemented as the simplest safe behavior, fully
isolated in `chat_service.py` so it's easy to change later:

1. The revision creates a new draft version (`version = latest + 1`) exactly
   as it would for an unconfirmed chat. Nothing about a prior confirmation
   blocks or alters this.
2. The existing `RecipeBookEntry` for the previously confirmed version is
   left completely untouched - confirming is per-version, not per-chat.
3. Confirming the new version creates a **separate, new** `RecipeBookEntry`
   linked to the same `chat_id` (via `RecipeBookRepository.save_entry()`),
   it never overwrites or updates the earlier one.

This means a single chat can end up with multiple recipe-book entries over
time (e.g. versions 1 and 3 both confirmed, version 2 never was) - this is
intentional, not a bug: the user explicitly confirmed each one, and neither
confirmation should silently vanish the other from their recipe book. If
the product wants "at most one book entry per chat, always the latest
confirmed" instead, that's a different, deliberately NOT-implemented
policy - change `confirm_recipe()`'s book-entry creation (and probably add
a repository method to look up "the existing entry for this chat_id, if
any" instead of `find_entry(chat_id, version)`).

Verified live (see REPORT.md): confirmed version 1, revised twice to
version 3, confirmed version 3 - the book ended up with the version-1 entry
untouched and a new version-3 entry alongside it.

## Repository protocols

Both are `typing.Protocol`s (structural typing - a Supabase-backed class
doesn't need to inherit from anything, just implement the same async
methods) with an in-memory reference implementation. **Neither is a real
database** - see `backend/repositories/chat_repo.py` and
`recipe_book_repo.py`'s module docstrings: state lives in a plain dict on
the FastAPI `app.state`, one instance per running app process, lost on
restart.

### `ChatRepository` (`backend/repositories/chat_repo.py`)

| Method | Signature | Semantics |
|---|---|---|
| `create_chat` | `(user_id: str, title: str \| None) -> Chat` | New, empty chat (no messages, no versions yet). |
| `append_message` | `(chat_id: str, message: ChatMessage) -> None` | Also bumps `updated_at`. |
| `save_version` | `(chat_id: str, version: RecipeVersion) -> None` | Also bumps `updated_at`. Caller is responsible for version numbers being sequential - the repository does not compute or validate them. |
| `get_chat` | `(user_id: str, chat_id: str) -> Chat \| None` | `None` if the chat doesn't exist **or belongs to a different user** - the two cases are indistinguishable by design (see "User scoping"). |
| `list_chats` | `(user_id: str) -> list[ChatSummary]` | This user's chats only, newest-`updated_at`-first. |
| `get_latest_version` | `(chat_id: str) -> RecipeVersion \| None` | The chat's highest-numbered version. `None` only if the chat has no versions at all, which shouldn't happen once `start_chat()` has run - `chat_service.send_message()` treats it as "chat not found" if it ever does. |
| `mark_version_confirmed` | `(chat_id: str, version: int) -> None` | Idempotent - setting an already-`true` flag to `true` again is a no-op. |

### `RecipeBookRepository` (`backend/repositories/recipe_book_repo.py`)

| Method | Signature | Semantics |
|---|---|---|
| `save_entry` | `(user_id: str, chat_id: str, version: int, recipe: Recipe) -> RecipeBookEntry` | Creates and stores a new entry unconditionally - it does **not** itself enforce idempotency. `confirm_recipe()` in `chat_service.py` calls `find_entry()` first and only calls `save_entry()` if nothing was found; a Supabase implementation should either preserve that split or enforce a unique `(chat_id, version)` constraint and let the caller handle the conflict. |
| `list_entries` | `(user_id: str) -> list[RecipeBookEntry]` | This user's entries, newest-`confirmed_at`-first. |
| `get_entry` | `(user_id: str, recipe_id: str) -> RecipeBookEntry \| None` | `None` if it doesn't exist or belongs to someone else (same rule as `get_chat`). |
| `find_entry` | `(chat_id: str, version: int) -> RecipeBookEntry \| None` | Powers idempotent confirmation - look up whether this exact `(chat_id, version)` was already confirmed. |

## Endpoints

All require the `X-User-Id` header. Request/response Pydantic models are in
`backend/schemas/chat_requests.py` and `backend/schemas/chat.py`.

### `POST /chats`
Same body as `POST /recipes/create` (`prompt`, `allergies`, `preferred_units`).
Runs the full existing generate+compose pipeline, creates the chat, and
saves version 1.

Request:
```json
{"prompt": "омлет с грибами и луком", "allergies": null, "preferred_units": null}
```
Response (200):
```jsonc
{
  "chat_id": "ea439555-0fd1-4b98-a633-b392ccc49d3f",
  "version": 1,
  "recipe": { "...": "full composed Recipe" }
}
```

### `POST /chats/{chat_id}/messages`
Request:
```json
{"text": "убери лук из рецепта"}
```
Response when the model classified this as a question (200):
```json
{
  "intent": "answer",
  "answer_text": "По метаданным рецепта общее время — примерно 15 минут...",
  "version": null,
  "recipe": null,
  "change_log": null
}
```
Response when it classified this as a revision (200) - real output, one
ingredient removed and cascaded to six steps that referenced it:
```jsonc
{
  "intent": "revise",
  "answer_text": "Убрал лук из рецепта и удалил упоминания о нём в шагах 1, 4, 5, 6, 11 и 14.",
  "version": 2,
  "recipe": { "...": "full composed Recipe, onion gone" },
  "change_log": [ "... 7 entries: 1 ingredient_removed + 6 step_changed ..." ]
}
```
Errors: 404 unknown/other-user's `chat_id`; 502 if the patch is still
invalid after the one model retry (`REVISE_FALLBACK_TO_FULL_REGENERATION`
can change this to a full-regeneration fallback instead - see below); the
usual 422/502/504/429 for underlying model call failures.

### `POST /chats/{chat_id}/confirm`
Request:
```json
{"version": null}
```
`version: null` means "confirm the latest version". Response (200) is a
`RecipeBookEntry` (see above). Calling this again with the same `version`
(explicit or the same one that was latest) returns the **same** entry
(same `id`) - confirmed, no duplicate created. Errors: 404 unknown chat or
unknown version number within an existing chat.

### `GET /chats`
Response: `ChatSummary[]`, this user's chats only.

### `GET /chats/{chat_id}`
Response: full `Chat` (all messages, all versions). 404 if unknown or
another user's.

### `GET /recipe-book`
Response: `RecipeBookEntry[]`, this user's confirmed recipes only.

### `GET /recipe-book/{recipe_id}`
Response: one `RecipeBookEntry`. 404 if unknown or another user's.

## Operation format

Full type definitions: `llm/chat_schemas.py`. Applied by
`backend/services/recipe_patch.py::apply_operations()` - see that module's
docstring for the exact application order (all references resolved against
the pre-patch recipe first; fixed op-type order: remove_ingredient,
update_ingredient, add_ingredient, remove_step, update_step, add_step,
update_meta; steps renumbered 1..N last).

**Why `fields` is a list of `{field, value}` objects, not a partial JSON
object**: OpenAI's strict structured-output mode requires every property in
an object schema to be listed in `required` (nullable is fine, *optional*
is not) - there is no way to express "this key may or may not be present"
directly. A list of small, individually-typed `{field, value}` variants
(one Pydantic model per updatable field, combined via a
`Field(discriminator="field")` union) sidesteps that: the model includes
one list entry per field it actually wants to change, and omits the rest by
simply not including an entry for them - see REPORT.md for the full
verification story (including two things that looked supported on paper
but were rejected by a real live call: `oneOf` and the `discriminator`
keyword both 400 in practice; the checked-in schema uses `anyOf` with no
discriminator instead).

| `op` | Fields | Notes |
|---|---|---|
| `update_ingredient` | `ingredient_id`, `fields: IngredientFieldUpdate[]` | `fields` entries: `name` (string), `amount` (number\|null), `unit` (string), `form` (string\|null). |
| `add_ingredient` | `ingredient: Ingredient` | Full object; `id` must not collide with an existing one (`PatchError` if it does). |
| `remove_ingredient` | `ingredient_id` | `PatchError` if unknown, or if any surviving step still references it in `ingredients_used` (the model is instructed to also emit `update_step`/`remove_step` for every step that used it - see the example above, and `llm/prompts/revise_system_prompt.md`'s "СВЯЗАННЫЕ ИЗМЕНЕНИЯ" section). |
| `update_step` | `step_number`, `fields: StepFieldUpdate[]` | `step_number` in the numbering **before** this patch. `fields` entries: any of `action`, `ingredients_used`, `time_minutes`, `passive`, `heat_level`, `place`, `salt`, `fat`, `final_action`. |
| `add_step` | `after_step_number`, `step: Step` | `after_step_number` in the pre-patch numbering; `0` = insert first. `step.step_number` is ignored - final numbering is always assigned by renumbering. |
| `remove_step` | `step_number` | Pre-patch numbering. |
| `update_meta` | `fields: MetaFieldUpdate[]` | Entries: `title`, `servings`, `total_time_minutes`, `equipment`, `notes` - the same fields `Chat.title` is (NOT) synced from, see above. |

Real example (from the live run, the multi-part revision - "increase eggs
to 4, add cherry tomatoes, add a final step"), showing the model returning
exactly 3 operations for 3 independent requested changes, nothing else
touched:
```jsonc
[
  {
    "op": "update_ingredient",
    "ingredient_id": "eggs",
    "fields": [{ "field": "amount", "value": 4 }]
  },
  {
    "op": "add_ingredient",
    "ingredient": { "id": "cherry_tomatoes", "name": "помидоры черри", "amount": 100, "unit": "г", "form": null }
  },
  {
    "op": "add_step",
    "after_step_number": 14,
    "step": {
      "step_number": 15,
      "action": "Посыпьте омлет зеленью.",
      "ingredients_used": [], "time_minutes": null, "passive": false,
      "heat_level": null, "place": "тарелка", "salt": false, "fat": null, "final_action": null
    }
  }
]
```

## Language behavior

Same underlying rules as recipe_contract.md's "Language" section, extended
to chat:

- `answer_text` and any **new or changed** free text (new/changed
  ingredient `name`/`form`, step `action`/`final_action`, meta
  `title`/`notes`) follow the language of the **user's latest message in
  that turn**, not the chat's original language - verified live: a chat
  started in Russian got an English answer when the user switched to
  English mid-conversation (see REPORT.md, Verification step 5).
- Fields an operation does **not** touch are never translated or rewritten
  - they keep whatever language they were already in. A chat can end up
    with a recipe whose ingredient names are Russian but whose latest
    `answer_text` is English; this is expected, not a bug.
- `heat_level` and `fat.unit` values are the same fixed Russian schema
  strings in every operation, in every language, always - the model cannot
  produce anything else (strict enum, see recipe_contract.md).
- `Recipe.language` (on the composed view inside each `RecipeVersion`) is
  re-detected from that version's own `raw_recipe` content every time it's
  composed - it is not "the chat's language" as a single fixed property,
  and *can* change between versions if enough of the recipe's own text
  changes language (not observed in the live run's revisions, which all
  stayed Russian even when the *chat message* was in English - see
  REPORT.md for exactly what happened there).
