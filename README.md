# smart-chef-motion
Smart Chef - кулинарный ассистент, управляемый жестами через веб-камеру. Разработано для ADMIT HACKATHON (трек Motion).

## Backend

Backend for building a recipe book from free-form user requests: user request → LLM with web
search → strict JSON recipe → programmatic assembly → final recipe object.

### Setup

```bash
uv sync --extra dev
cp .env.example .env   # then fill in OPENAI_API_KEY
```

### Environment variables

| Variable                  | Required | Default | Description                                                |
|----------------------------|----------|---------|--------------------------------------------------------------|
| `OPENAI_API_KEY`           | yes      | —       | OpenAI API key.                                              |
| `OPENAI_MODEL`              | yes      | —       | Model name used for both generation steps.                   |
| `OPENAI_TIMEOUT_SECONDS`    | no       | `60`    | Timeout for OpenAI API calls.                                 |
| `TWO_STEP_MODE`             | no       | `false` | If true, splits generation into a plain-text web-search step followed by a JSON-conversion step, instead of one combined call. |
| `REVISE_MODEL`              | no       | `OPENAI_MODEL` | Model used for the chat/revision call (`respond_to_message`). |
| `REVISE_USE_WEB_SEARCH`     | no       | `false` | If true, the chat/revision call also gets the `web_search` tool. |
| `REVISE_HISTORY_MESSAGES`   | no       | `10`    | How many of a chat's most recent messages are sent as context to the model. |
| `REVISE_FALLBACK_TO_FULL_REGENERATION` | no | `false` | If true, a revision whose patch still fails after one model retry falls back to fully regenerating the recipe (via `generate_raw_recipe`) instead of returning `502`. |

### Run

```bash
uvicorn backend.main:app --reload
```

(Note: AGENTS.md's Commands section says `uvicorn app.main:app`, but the FastAPI package in
this repo is `backend/`, not `app/` — use `backend.main:app`.)

### Test / lint / type-check

```bash
pytest -q
ruff check . && ruff format .
mypy backend llm
```

### Endpoints

All three endpoints are public (no auth yet) for debugging.

#### `POST /recipes/create`

Runs the full pipeline: `generate_raw_recipe()` → `compose_recipe()`.

```bash
curl -X POST http://localhost:8000/recipes/create \
  -H "Content-Type: application/json" \
  -d '{"prompt": "борщ на говяжьем бульоне", "allergies": null, "preferred_units": null}'
```

Response: the final `Recipe` object (`title`, `servings`, `equipment`, `source_urls`, `notes`,
`ingredients`, `steps` with `display_text`, `total_time_minutes`, `warnings`).

#### `POST /recipes/generate-raw`

Calls the LLM only and returns the raw structured recipe JSON (matching
`llm/prompts/recipe_schema.json`).

```bash
curl -X POST http://localhost:8000/recipes/generate-raw \
  -H "Content-Type: application/json" \
  -d '{"prompt": "борщ на говяжьем бульоне", "allergies": "без лактозы", "preferred_units": null}'
```

- If the model reports a non-null `error`, responds `422` with that message.
- If the model output fails schema validation even after one retry, responds `502`.
- OpenAI timeouts respond `504`; rate limiting responds `429`.

#### `POST /recipes/compose`

Takes the raw recipe JSON (the body shape returned by `/recipes/generate-raw`) and returns the
composed final `Recipe`.

```bash
curl -X POST http://localhost:8000/recipes/compose \
  -H "Content-Type: application/json" \
  -d @raw_recipe.json
```

### Chat endpoints

Full contract, entity shapes, and request/response examples:
[`docs/chat_contract.md`](docs/chat_contract.md) (raw recipe/composed recipe shapes:
[`docs/recipe_contract.md`](docs/recipe_contract.md)). All chat/recipe-book endpoints
require an `X-User-Id` header — there is no real authentication yet (see the contract
doc and REPORT.md); a user can only ever see their own chats and recipe-book entries.

```bash
# Start a chat (runs the existing create pipeline, saves draft version 1)
curl -X POST http://localhost:8000/chats \
  -H "Content-Type: application/json" -H "X-User-Id: demo-user" \
  -d '{"prompt": "омлет с грибами и луком", "allergies": null, "preferred_units": null}'

# Ask a question or request a revision - the model classifies which
curl -X POST http://localhost:8000/chats/<chat_id>/messages \
  -H "Content-Type: application/json" -H "X-User-Id: demo-user" \
  -d '{"text": "убери лук из рецепта"}'

# Confirm a version into the recipe book (null = latest version)
curl -X POST http://localhost:8000/chats/<chat_id>/confirm \
  -H "Content-Type: application/json" -H "X-User-Id: demo-user" \
  -d '{"version": null}'

curl http://localhost:8000/chats -H "X-User-Id: demo-user"
curl http://localhost:8000/chats/<chat_id> -H "X-User-Id: demo-user"
curl http://localhost:8000/recipe-book -H "X-User-Id: demo-user"
curl http://localhost:8000/recipe-book/<recipe_id> -H "X-User-Id: demo-user"
```

- 404 for an unknown chat/recipe, or one that belongs to a different `X-User-Id`
  (existence is never revealed to a non-owner).
- 502 if a revision's patch still fails validation after one model retry
  (see `REVISE_FALLBACK_TO_FULL_REGENERATION` above).
- Chat/recipe-book state is **in-memory only** (per running process, lost on
  restart) — persistence is a follow-up, see `docs/chat_contract.md`.
