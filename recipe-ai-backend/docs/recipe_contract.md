# Recipe contract

This document is the reference for building persistence (Supabase or
otherwise) on top of this backend. It describes the exact JSON shape of the
two recipe objects that flow through the system:

- **`RawRecipe`** (`llm/schemas.py`, mirroring `llm/prompts/recipe_schema.json`)
  — what the LLM returns. **This is the source of truth.**
- **`Recipe`** (`backend/schemas/recipe.py`) — what `/recipes/create` and
  `/recipes/compose` return: a `RawRecipe` plus rendered `display_text` per
  step, a generated `id`, a detected `language`, and `warnings`.

> **`display_text` is a derived, regeneratable view.** Every string in it is
> either copied verbatim from `RawRecipe` free-text fields or built
> deterministically from other `RawRecipe` fields (see "How `display_text`
> is built" below). Given the same `RawRecipe`, `compose_recipe()` always
> produces the same `display_text` for every step. If the rendering
> template changes later, `display_text` can be regenerated from the stored
> `RawRecipe` alone — **persist the `RawRecipe` fields, not just the
> rendered text**, if you want that flexibility.

## `RawRecipe` — raw LLM output

Source: `llm/schemas.py`, kept in parity with `llm/prompts/recipe_schema.json`
(enforced by `llm/tests/test_schema_parity.py` — the two must never diverge).

All top-level fields are nullable. A non-null `error` means every other
field is `null` (the model could not produce a recipe); see "Error case"
below.

```jsonc
{
  "error": null,
  "title": "Омлет с зелёным перцем",
  "servings": 2,
  "total_time_minutes": 8.5,
  "equipment": ["сковорода", "миска", "венчик"],
  "source_urls": ["https://example.com/omelette-recipe"],
  "notes": null,
  "ingredients": [
    {
      "id": "eggs",
      "name": "яйца",
      "amount": 3,
      "unit": "шт",
      "form": null
    },
    {
      "id": "pepper",
      "name": "зелёный перец",
      "amount": 50,
      "unit": "г",
      "form": "нарезать кубиками"
    },
    {
      "id": "salt",
      "name": "соль",
      "amount": null,
      "unit": "по вкусу",
      "form": null
    }
  ],
  "steps": [
    {
      "step_number": 1,
      "action": "Разогрейте сковороду",
      "ingredients_used": [],
      "time_minutes": 1,
      "passive": false,
      "heat_level": "средний огонь",
      "place": "сковорода",
      "salt": false,
      "fat": { "type": "подсолнечное масло", "amount": 1, "unit": "ст. л." },
      "final_action": null
    },
    {
      "step_number": 2,
      "action": "Обжарьте зелёный перец",
      "ingredients_used": ["pepper"],
      "time_minutes": 0.33,
      "passive": false,
      "heat_level": "максимальный огонь",
      "place": "сковорода",
      "salt": false,
      "fat": null,
      "final_action": "переложите в миску"
    },
    {
      "step_number": 3,
      "action": "Разбейте яйца в миску",
      "ingredients_used": ["eggs"],
      "time_minutes": null,
      "passive": false,
      "heat_level": null,
      "place": "миска",
      "salt": false,
      "fat": null,
      "final_action": null
    }
  ]
}
```

### Field reference

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `error` | `string` | yes | Non-null only when the request is not food-related or no reliable recipe was found. When non-null, every other top-level field is `null`. Always in the language the model was instructed in for errors — see "Language" below (in practice this is Russian per the current system prompt; not composer-controlled). |
| `title` | `string` | yes | Recipe title, free text, in the recipe's language. |
| `servings` | `integer` | yes | Number of servings. |
| `total_time_minutes` | `number` | yes | Total time including passive waiting, if the model could determine it. `compose_recipe()` fills this in when null and every active (non-passive) step has a known `time_minutes` — see "Total time" below. |
| `equipment` | `string[]` | yes (array or items) | Free-text equipment names. |
| `source_urls` | `string[]` | yes (array or items) | URLs the model's web search used. |
| `notes` | `string` | yes | Free text, e.g. allergy substitutions the model made. |
| `ingredients` | array of `Ingredient` | yes (array); never null in practice once `error` is null (composer treats it as `[]`) | See below. |
| `steps` | array of `Step` | yes (array); never null in practice once `error` is null (composer treats it as `[]`) | See below. |

**`Ingredient`** (all fields required when present):

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `id` | `string` | no | Stable id referenced by `Step.ingredients_used`. Composer raises `UnknownIngredientError` (422) if a step references an id not in `ingredients`. |
| `name` | `string` | no | Free text, in the recipe's language. |
| `amount` | `number` | yes | `null` means "to taste" / unspecified (see `unit`). |
| `unit` | `string` | no | **Not a fixed enum** — free text from the model. Defaults to grams (`г`) / milliliters (`мл`) per the system prompt; `"по вкусу"` ("to taste") when `amount` is null; the user's own units if they asked for them (e.g. cups, spoons). The composer only special-cases the literal `"шт"` (piece-count items, e.g. eggs) for Russian pluralization — see "How `display_text` is built". |
| `form` | `string` | yes | Prep form, e.g. `"нарезать кубиками"` ("diced"). |

**`Step`** (all fields required when present):

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `step_number` | `integer` | no | Model's own numbering; **overwritten by the composer** to a clean 1..N sequence in array order. Don't rely on the model's original numbers. |
| `action` | `string` | no | One imperative sentence, free text, in the recipe's language. **The composer never rewrites or paraphrases this.** |
| `ingredients_used` | `string[]` | no (array; may be empty) | Ids into `RawRecipe.ingredients`. |
| `time_minutes` | `number` | yes | Duration in minutes (fractional allowed, e.g. `0.33` ≈ 20 seconds). `null` if unknown or if this is passive waiting with no known duration. |
| `passive` | `boolean` | no | `true` for unattended waiting (marinating, resting, cooling) with no active work. |
| `heat_level` | `string` enum | yes | **Fixed schema enum, always in Russian, never translated by the model**: `"максимальный огонь"`, `"средний огонь"`, `"малый огонь"`, `"минимальный огонь"`, or `null` if the step has nothing to do with heat. |
| `place` | `string` | no | Where the step happens, e.g. `"сковорода"`, `"миска"`. **Not currently rendered into `display_text`** (see below) — kept in the JSON for structural/UI use. |
| `salt` | `boolean` | no | `true` only if salt is added in this exact step. |
| `fat` | `Fat` object | yes | See below. `null` if no fat is added in this step. |
| `final_action` | `string` | yes | What to do at the end of the step, e.g. `"переложите в миску"`. Free text, in the recipe's language. |

**`Fat`** (all fields required):

| Field | Type | Meaning |
|---|---|---|
| `type` | `string` | Free text, e.g. `"подсолнечное масло"`. In the recipe's language. |
| `amount` | `number` | Required (not nullable). |
| `unit` | `string` enum | **Fixed schema enum, always in Russian, never translated by the model**: `"ст. л."`, `"ч. л."`, `"г"`, `"мл"`. |

### Error case

```jsonc
{
  "error": "Запрос не про еду",
  "title": null, "servings": null, "total_time_minutes": null,
  "equipment": null, "source_urls": null, "notes": null,
  "ingredients": null, "steps": null
}
```
`compose_recipe()` raises `ModelReportedError` (mapped to HTTP 422) instead of
returning a `Recipe` when it sees a non-null `error`. Nothing is persisted.

## Language

**Free text** (`title`, `notes`, `Ingredient.name`, `Ingredient.form`,
`Step.action`, `Step.final_action`, `Fat.type`) is written by the model **in
the language of the user's original request** — see
`llm/prompts/web_search_prompt.md`, rule 3: *"ВСЕ текстовые значения в
ответе должны быть на языке на которым задал запрос пользователь"* ("ALL
text values in the response must be in the language the user used for their
request"). The composer never translates, paraphrases, or otherwise alters
these fields.

**Fixed schema strings** (`Step.heat_level`, `Fat.unit`) are **not**
translated by the model — they are strict JSON-schema enums with exactly
four/four Russian-language values respectively (see tables above), and
`text.format` strict mode means the model literally cannot emit anything
else. `llm/schemas.py`'s `HeatLevel`/`FatUnit` `Literal` types enforce the
same constraint on the Python side.

`Ingredient.unit` is **not** a fixed enum (plain `string` in the schema), so
in principle it is subject to the "all text in the user's language" rule
too; in practice the system prompt's own default (`г`/`мл`) is written in
Russian abbreviation form, and what a model asked in English or Kazakh
actually emits for this field is model-dependent and was not verified live
for every language in this change (see REPORT.md, Verification section).
The composer treats `Ingredient.unit` as opaque free text and does not
translate it; it special-cases only the literal `"шт"` value (regardless of
trailing period) for Russian piece-count pluralization.

### `Recipe.language`

`RawRecipe`/`recipe_schema.json` carry **no language field** — adding one
would require changing the schema file, which this task explicitly leaves
untouched. `Recipe.language` is therefore **detected** by the composer, not
read from the model output:

- `backend/services/step_text/language.py`: `detect_recipe_language(raw)`
  concatenates `title`, `notes`, and every step's `action`/`final_action`,
  then classifies the script:
  - Cyrillic text containing any Kazakh-specific letter
    (`Ә ә Ғ ғ Қ қ Ң ң Ө ө Ұ ұ Ү ү Һ һ І і`) → `"kk"`.
  - Any other Cyrillic → `"ru"`.
  - Anything else (Latin, empty, or an unrecognized script) → `"en"`.
- **Limits, stated plainly**: this is a script classifier, not a language
  identifier. It cannot distinguish Russian from other Cyrillic languages
  that don't use the Kazakh-specific letters (Ukrainian, Belarusian, ...).
  A non-Cyrillic, non-Latin script (Arabic, Chinese, ...) is bucketed into
  `"en"` even though it plainly isn't English — this only selects which
  renderer runs (the full-quality Russian one, or the uninflected
  fallback), it is not a claim of linguistic accuracy. No dependency was
  added for this; it was judged unnecessary for a three-way script split.
- `Recipe.language` is typed `Literal["ru", "en", "kk"]` in
  `backend/schemas/recipe.py` — currently a closed set matching what
  detection can produce.

## How `display_text` is built

Implementation: `backend/services/step_text/` (`ru.py` for Russian,
`labels.py` for the fallback, `numbers.py`/`ru_data.py` for the Russian
number/case helpers, `language.py` for detection). All pure functions, no
I/O, no LLM call — this whole package only formats fields already present
in `RawStep`.

**Russian** (`language == "ru"`, full quality):
1. Strip a pre-existing trailing period from `Step.action` (real model
   output sometimes writes a fully-punctuated sentence there even though
   more clauses follow — without this, output had a stray mid-sentence
   period, found via a live call, see REPORT.md). Otherwise `action` is
   never rewritten or paraphrased.
2. For each id in `ingredients_used` with a known `amount`: skip it if it's
   also described by the step's own `fat` field (same name/type — real
   output sometimes lists a fat both ways), or if its amount already
   appears in `action`. Otherwise mention it once:
   - If the unit is `"шт"` (piece count) **and** the ingredient's name is in
     the hand-written declension table (`ru_data.INGREDIENT_PLURAL_FORMS`),
     find its existing word in `action` and **replace that word in place**
     with our own correctly-agreeing `"<amount> <form>"` (e.g. `"яйцо"` →
     `"2 яйца"`). This never trusts the action's own word to already agree
     with the amount — live testing found the model sometimes writes a
     generic singular regardless of count, which a naive "insert the digit
     before the existing word" approach would render as ungrammatical
     `"2 яйцо"`.
   - Everything else (unit not `"шт"`, or a noun outside that table) gets a
     short trailing clause instead: `"<amount> <unit> <name>"` for
     amount+unit ingredients, `"<amount> <form> "` (from the same table) or
     `"<name> <amount> шт."` (unknown noun, the task's documented fallback)
     for piece counts we couldn't locate/match inline.
3. `heat_level`, if present, attaches as `"на среднем огне"`-style
   adverbial — *unless* that exact phrase is already inside `action`
   (the model sometimes states it directly, e.g. `"Разогрейте сковороду на
   среднем огне."` — found via live testing; without this check it
   duplicated). `time_minutes`, if present, is appended right after (same
   adverbial, no comma): `"на среднем огне 1 минуту"`.
4. `fat`, if present **and its amount isn't already stated in `action`**,
   appends `", добавьте <amount> <unit> <type, genitive>"`. `salt`, if
   `true`, appends `", посолите"`. `final_action`, if present, appends
   `", затем <final_action>"`.
5. `Step.place` is **not** rendered into `display_text` — it's structural
   data (available on the `Step` object itself), and the target wording
   the composer was built against never repeats it separately from the
   action.

**Any other language** (`language != "ru"`, e.g. `"en"`, `"kk"`): the
fallback in `labels.py`. Same action-first structure (including the
trailing-period strip and the heat-already-in-action / fat-amount-already-
in-action checks from steps 1/3/4 above), but every parameter clause is
uninflected and comes from a small per-`Labels` dictionary (heat phrase,
minute/second words, salt phrase, fat verb+unit words, "then" word). No
ingredient-amount mention is attempted in the fallback (the task scoped
that logic to the Russian renderer only). Adding a new language is adding
one `Labels` entry to `labels.LABELS` — no renderer code changes.

**Known limitations, stated for the colleague building persistence** (all
confirmed against real model output during this change — see REPORT.md,
Verification):
- The Russian renderer does not attempt full noun case declension for
  arbitrary ingredient names (e.g. turning `"мука"` into genitive `"муки"`
  after an amount+unit). It has a table for common piece-counted items
  (`INGREDIENT_PLURAL_FORMS`) and common fats (`FAT_GENITIVE`); anything
  outside those tables is rendered in its original (nominative) form. This
  is a deliberate scope decision, not an oversight.
- "Already mentioned" detection for amounts (ingredient and fat) is a
  decimal-substring match against the schema's own numeric notation (e.g.
  `"2"`). It does not recognize other notations the model may use in free
  text, such as fractions (`"1/2 teaspoon"` vs. a schema `amount` of
  `0.5`) — in that case the trailing clause restates the amount in decimal
  form alongside the action's own fraction wording. Recognizing arbitrary
  numeral notation across languages was judged out of scope.
- Amount-mention deduplication runs **per step**, not across the whole
  recipe. If the same ingredient id appears in `ingredients_used` on
  multiple steps, its amount may be (correctly, non-duplicated) mentioned
  once on *each* of those steps, since `render_step_display_text()` has no
  memory of other steps. Never duplicated *within* one step.

## `Recipe` — composed output

Source: `backend/schemas/recipe.py`. Returned by `POST /recipes/create` and
`POST /recipes/compose`.

```jsonc
{
  "id": "3f29a9d2-0c1e-4b3a-9e77-1a2b3c4d5e6f",
  "language": "ru",
  "title": "Омлет с зелёным перцем",
  "servings": 2,
  "equipment": ["сковорода", "миска", "венчик"],
  "source_urls": ["https://example.com/omelette-recipe"],
  "notes": null,
  "ingredients": [
    { "id": "eggs", "name": "яйца", "amount": 3, "unit": "шт", "form": null },
    { "id": "pepper", "name": "зелёный перец", "amount": 50, "unit": "г", "form": "нарезать кубиками" },
    { "id": "salt", "name": "соль", "amount": null, "unit": "по вкусу", "form": null }
  ],
  "steps": [
    {
      "step_number": 1,
      "action": "Разогрейте сковороду",
      "ingredients_used": [],
      "time_minutes": 1,
      "passive": false,
      "heat_level": "средний огонь",
      "place": "сковорода",
      "salt": false,
      "fat": { "type": "подсолнечное масло", "amount": 1, "unit": "ст. л." },
      "final_action": null,
      "display_text": "Разогрейте сковороду на среднем огне 1 минуту, добавьте 1 столовую ложку подсолнечного масла."
    },
    {
      "step_number": 2,
      "action": "Обжарьте зелёный перец",
      "ingredients_used": ["pepper"],
      "time_minutes": 0.33,
      "passive": false,
      "heat_level": "максимальный огонь",
      "place": "сковорода",
      "salt": false,
      "fat": null,
      "final_action": "переложите в миску",
      "display_text": "Обжарьте зелёный перец на максимальном огне 20 секунд, затем переложите в миску."
    },
    {
      "step_number": 3,
      "action": "Разбейте яйца в миску",
      "ingredients_used": ["eggs"],
      "time_minutes": null,
      "passive": false,
      "heat_level": null,
      "place": "миска",
      "salt": false,
      "fat": null,
      "final_action": null,
      "display_text": "Разбейте 3 яйца в миску."
    }
  ],
  "total_time_minutes": 8.5,
  "warnings": []
}
```

(`total_time_minutes` here is `8.5` because the model provided it directly
on `RawRecipe` — see the field reference below; it is copied through
as-is and not recomputed in that case, even though step 3 in this example
has an unknown `time_minutes`.)

### Field reference

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `id` | `string` (UUID4) | no | **Generated by the composer** (`uuid.uuid4()`), not by a persistence layer. See "`id` generation" below for why, and the coordination note for `RecipeRepository`. |
| `language` | `"ru" \| "en" \| "kk"` | no | Detected by the composer; see "Language" above. |
| `title` | `string` | yes | Copied from `RawRecipe.title`. |
| `servings` | `integer` | yes | Copied from `RawRecipe.servings`. |
| `equipment` | `string[]` | yes | Copied from `RawRecipe.equipment`. |
| `source_urls` | `string[]` | yes | Copied from `RawRecipe.source_urls`. |
| `notes` | `string` | yes | Copied from `RawRecipe.notes`. |
| `ingredients` | `Ingredient[]` | no (`[]` if the model returned `null`) | Copied as-is from `RawRecipe.ingredients` — same shape as the `Ingredient` table above. |
| `steps` | `ComposedStep[]` | no (`[]` if the model returned `null`) | Every `RawRecipe` step field, **plus** `display_text`. `step_number` is renumbered 1..N by the composer, overwriting the model's own numbering. |
| `total_time_minutes` | `number` | yes | `RawRecipe.total_time_minutes` if the model provided it; otherwise computed by summing known `time_minutes` across all steps, but **only** if every non-passive (`passive == false`) step has a known `time_minutes` (an active step with an unknown duration makes the sum meaningless; a passive step's unknown duration does not block the sum, it just can't be added to it). Unchanged from the pre-existing composer logic — not part of this change. |
| `warnings` | `string[]` | no (`[]` if none) | Currently the only warning is "this ingredient id is never used in any step", localized via the same label-dictionary approach as `display_text` (Russian and English implemented; Kazakh included too — see `step_text/labels.py`). |

### `id` generation — decision for the colleague

**Chosen: the composer generates `id` (`uuid.uuid4()`), it is never `null`.**
Rationale: `/recipes/compose` and `/recipes/create` return a complete,
self-identifying `Recipe` with no persistence step in between right now: a
caller can already reference a specific composed recipe (e.g. for logging,
caching, or client-side dedup) before any database write happens. Leaving
`id` nullable for "the persistence layer to fill in" would mean every
non-persisted `Recipe` (which is *all* of them today — there is no
persistence yet) has `id: null`, which is a worse default for API
consumers than a real, always-present id.

**Action needed for the colleague wiring Supabase persistence**
(`backend/repositories/recipe_repo.py` was intentionally left untouched by
this change — method signatures were not part of this task):
`InMemoryRecipeRepository.save()` currently **mints its own new
`uuid.uuid4()`** and ignores whatever `id` is already on the `Recipe` it's
given, then returns that new id. Once `Recipe.id` is always populated by
the composer, `save()` should almost certainly key storage on
`recipe.id` (and `save()`'s return value should just be `recipe.id`, not a
fresh one) — otherwise a `Recipe`'s `id` field and its actual storage key
can silently diverge. This is a real behavior gap, not just a style nit:
please reconcile it when Supabase persistence lands.

## Endpoints touched by this document

- `POST /recipes/generate-raw` → `RawRecipe` (unchanged by this task).
- `POST /recipes/compose` → takes a `RawRecipe` body, returns `Recipe`.
  **No LLM call happens in this path** — composition is fully programmatic.
- `POST /recipes/create` → runs the LLM call then composition, returns
  `Recipe`.

## The chat layer (built on top of this document)

A later change added a chat layer (`POST /chats`, `/chats/{id}/messages`,
`/chats/{id}/confirm`, `/chats/{id}`, `GET /chats`, `GET /recipe-book*`) on
top of everything documented above — see **`docs/chat_contract.md`** for
its full contract. It doesn't change anything in this document: a chat's
`RecipeVersion.raw_recipe`/`RecipeVersion.recipe` are exactly the
`RawRecipe`/`Recipe` shapes described here, one `Recipe` per version.
Two things worth knowing when reading both documents together:

- **`RecipeBookRepository` (`backend/repositories/recipe_book_repo.py`) is
  the repository that's actually wired in** (via `POST
  /chats/{id}/confirm`) for saving confirmed recipes. The
  `RecipeRepository`/`InMemoryRecipeRepository` described in the "`id`
  generation" section above (`backend/repositories/recipe_repo.py`) predates
  the chat layer, was never wired into any endpoint, and is now superseded
  by it — it is dead code at this point. It was left in place (not part of
  this task's scope to remove), but flagged here and in REPORT.md so it
  isn't mistaken for the live persistence seam.
- Every `Recipe` embedded in a `RecipeVersion` gets a **fresh** `id` from
  `compose_recipe()` each time it's composed (version 1 at chat start,
  again on every revision) — it is not a stable identifier for that
  version. Use `(chat_id, version)` for that instead; see chat_contract.md.
