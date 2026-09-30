# OpenAI API usage and cost logs

Every paid Responses API attempt emits one JSON log event. Initial generation,
two-step generation, chat revision, validation retries, and upstream failures
are all recorded separately. Events with the same `workflow_id` belong to one
user-level generation or chat workflow.

Example:

```json
{"event":"openai_usage","workflow_id":"...","operation":"recipe.structured.attempt_1","model":"gpt-5","input_tokens":3210,"cached_input_tokens":0,"output_tokens":840,"reasoning_tokens":400,"total_tokens":4050,"web_search_actions":1,"estimated_cost_usd":0.0224125,"elapsed_ms":8421}
```

No prompt, recipe text, API key, or exception body is logged. A failed call has
an `openai_request_error` event with the exception type and `usage_available` set
to false. A failed request can still be billable even when the API returns no
usage, so the OpenAI billing dashboard is authoritative.

## Pricing configuration

The default estimate is for standard GPT-5 pricing checked on 2026-09-30. Set
all of these values together whenever the production model or official pricing
changes:

```env
OPENAI_PRICING_MODEL=gpt-5
OPENAI_INPUT_COST_PER_MILLION_USD=1.25
OPENAI_CACHED_INPUT_COST_PER_MILLION_USD=0.125
OPENAI_OUTPUT_COST_PER_MILLION_USD=10.0
OPENAI_WEB_SEARCH_COST_PER_CALL_USD=0.01
```

If the response model does not equal `OPENAI_PRICING_MODEL`, token and search
usage is still logged but `estimated_cost_usd` is `null`, preventing an estimate
with the wrong rate.

## Reading the logs

With Docker Compose:

```bash
docker compose logs -f backend | grep '"event":"openai_'
```

Each retry is a real paid attempt and therefore appears as a separate event.
Sum `estimated_cost_usd` by `workflow_id` to estimate the cost of one user-level
request, or aggregate it over a time window to monitor spend rate.
