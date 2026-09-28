# AGENTS.md

## Project
Smart Chef: backend for an app that builds a recipe book from free-form user requests.
Flow: user request → LLM with web search → strict JSON recipe → programmatic assembly → recipe object.

## Stack
- Python 3.12, FastAPI, Pydantic v2, uvicorn
- OpenAI Python SDK (Responses API, `web_search` tool, structured outputs with strict json_schema)
- pytest, pytest-asyncio, httpx (tests), ruff (lint/format), mypy (types)
- Config via environment variables (`pydantic-settings`), `.env` for local only

## Layout
Two top-level packages. Inspect the existing repo first and follow its existing conventions (package manager, naming, Python version). Do not restructure existing files.

```
llm/                             # Everything about the model. No FastAPI imports here.
  prompts/
    recipe_system_prompt.md      # System prompt (Russian), loaded from file, never inlined
    recipe_schema.json           # Strict JSON schema in Responses API format, single source of truth
  recipe_generator.py            # generate_raw_recipe(): OpenAI call with web search + structured output
  schemas.py                     # Pydantic model mirroring the strict JSON schema (LLM output)
  config.py                      # OpenAI settings (OPENAI_API_KEY, OPENAI_MODEL, timeouts, TWO_STEP_MODE)
  errors.py                      # Domain exceptions (model-reported error, upstream failure, timeout, rate limit)
  tests/

backend/                         # FastAPI app. Imports from llm/, never the other way around.
  main.py                        # FastAPI app factory, router registration, exception handlers
  api/
    routes_create.py             # POST /recipes/create: accepts a user request, runs the whole pipeline
    routes_generate_raw.py       # POST /recipes/generate-raw: calls llm/, returns raw JSON
    routes_compose.py            # POST /recipes/compose: programmatic composition of the final recipe
  schemas/
    recipe.py                    # Final Recipe domain model
    requests.py                  # Request/response models for endpoints
  services/
    recipe_composer.py           # Turns LLM output into the final Recipe
    pipeline.py                  # create_recipe(): generate_raw → compose via function calls
  repositories/
    recipe_repo.py               # RecipeRepository protocol + InMemory implementation (stub)
  tests/
```

Dependency rule: `backend` may import from `llm`; `llm` must never import from `backend`.

## Commands
- Install: `uv sync` (or `pip install -e ".[dev]"`)
- Run: `uvicorn app.main:app --reload`
- Test: `pytest -q`
- Lint/format: `ruff check . && ruff format .`
- Types: `mypy app`

## Conventions
- Async everywhere (`async def` endpoints and service functions).
- Endpoints stay thin: validation and HTTP concerns only. Logic lives in `services/`.
- Endpoints call each other through **service functions**, never via HTTP to self.
- Full type hints; Pydantic models for every request, response, and LLM payload.
- The JSON schema in `prompts/recipe_schema.json` is the single source of truth. `schemas/llm_recipe.py` must match it exactly; add a test that fails if they diverge.
- The system prompt lives in `prompts/recipe_system_prompt.md`. Do not paraphrase or "improve" it in code.
- All user-facing recipe text is in **Russian**. Code, identifiers, comments, logs and docs are in English.
- Never hardcode secrets. Never log the API key or full user prompts at INFO level.

## LLM rules
- Use the OpenAI Responses API with the `web_search` tool and `text.format` = json_schema, strict.
- Model name comes from `OPENAI_MODEL` config. Do not hardcode it.
- Parse the model output with Pydantic; on validation failure retry once, then return a 502 with a clear error.
- If the model returns `error` (non-null), surface it as a 422 to the client with that message.
- Set explicit timeouts. Handle OpenAI errors (rate limit, timeout, API error) with distinct HTTP status codes.
- Keep an easily switchable fallback: two-step mode (step 1 search + plain recipe text, step 2 convert to strict JSON) behind a config flag `TWO_STEP_MODE`, in case the chosen model cannot combine web search and strict structured output.

## Testing rules
- Unit-test the assembler with fixtures (no network).
- Test the generator with a mocked OpenAI client; never call the real API in tests.
- Test endpoints with `httpx.AsyncClient` and dependency overrides.
- Every bug fix gets a regression test.

## Definition of done
- `ruff`, `mypy`, and `pytest` all pass.
- New behaviour has tests.
- README section updated when endpoints or config change.

## Do not
- Do not add a database, auth, or the recipe-book persistence layer yet.
- Do not change the recipe schema or system prompt without being asked.
- Do not add dependencies without stating why.

- `REPORT.md` is updated with a work log entry for every change, and the final report follows the required structure.