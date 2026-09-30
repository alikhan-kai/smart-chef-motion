"""Opt-in, paid, single-attempt recipe benchmark; never changes app configuration.

Run inside the backend container via stdin so its installed packages/prompts are used.
Without --run-paid this prints the plan and exits before loading credentials or SDKs.
Prices: standard short-context USD, checked 2026-09-29 against official model pages.
https://developers.openai.com/api/docs/pricing
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import tempfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

# Input, cached input, output prices per million tokens. Not a model selection default.
RATES = {
    "gpt-4o-mini": (0.15, 0.075, 0.60),
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
    "gpt-6-luna": (0.10, 0.01, 0.50),
}
PROMPTS = [
    "Приготовь куриный суп на 2 порции. "
    "Укажи количества, время и понятные шаги.",
    "Рецепт ужина на 2 порции за 30 минут: "
    "без мяса, рыбы и молочных продуктов. "
    "Есть нут, рис, помидоры и лук. Ответь на русском.",
    "Яблочный пирог на 4 порции без духовки: "
    "есть только сковорода и плита. "
    "Укажи количества и объясни, как проверить готовность. "
    "Ответь на русском.",
]
COST_NOTE = (
    "Planning estimates, not an invoice. Recorded input/output usage plus observed search "
    "action fees. A separate 8,000-input-token/search allowance is added for 4o-mini and "
    "4.1-mini; this can overcount if search content is already included in reported usage. "
    "Luna's separately billed search content, if not in usage, is unmeasured. "
    "Timed-out/failed requests may incur charges without returned usage. "
    "No taxes, regional surcharges or cache-write charges are estimated. "
    "Reasoning tokens are already part of output_tokens: do not add them twice."
)


def usage_cost(model: str, usage: dict[str, Any], searches: int) -> dict[str, float]:
    """Keep billing components separate instead of pretending we know the invoice."""
    inp, cached_rate, out = RATES[model]
    cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
    tokens = (
        max(0, usage["input_tokens"] - cached) * inp
        + cached * cached_rate
        + usage["output_tokens"] * out
    ) / 1_000_000
    allowance = searches * 8000 * inp / 1_000_000 if model != "gpt-6-luna" else 0.0
    return {
        "recorded_token_cost_usd": tokens,
        "search_action_fee_usd": searches * 0.01,
        "fixed_search_content_allowance_usd": allowance,
        "planning_cost_usd": tokens + searches * 0.01 + allowance,
    }


async def trial(
    client: Any,
    model: str,
    prompt: str,
    system: str,
    schema: dict[str, Any],
    validate: Callable[[str], Awaitable[dict[str, Any]]],
    timeout: float,
    max_output: int,
    luna_effort: str,
) -> dict[str, Any]:
    row: dict[str, Any] = {"model": model, "prompt": prompt, "technical_pass": False}
    start = time.monotonic()
    options: dict[str, Any] = {}
    if model == "gpt-6-luna" and luna_effort != "default":
        options["reasoning"] = {"effort": luna_effort}
    row["reasoning_effort"] = luna_effort if model == "gpt-6-luna" else "not_set"
    try:
        async with asyncio.timeout(timeout):
            response = await client.responses.create(
                model=model,
                input=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                tools=[{"type": "web_search"}],
                text={"format": schema},
                max_output_tokens=max_output,
                store=False,
                service_tier="default",
                **options,
            )
            row["response_model"] = response.model
            row["status"] = response.status
            row["output_text"] = response.output_text
            searches = sum(
                1 for item in response.output
                if item.type == "web_search_call"
                and getattr(getattr(item, "action", None), "type", None) == "search"
            )
            row["search_actions"] = searches
            if response.usage is not None:
                row["usage"] = response.usage.model_dump()
                row["cost"] = usage_cost(model, row["usage"], searches)
            if response.status == "completed":
                row["recipe"] = await validate(response.output_text)
                row["technical_pass"] = True
            else:
                row["incomplete_reason"] = getattr(response.incomplete_details, "reason", None)
    except Exception as exc:
        # Never print exception bodies: authentication errors can echo key fragments.
        row["error_type"] = type(exc).__name__
        row["http_status"] = getattr(exc, "status_code", None)
    row["seconds"] = round(time.monotonic() - start, 2)
    return row


def summarize(rows: list[dict[str, Any]], generations: int) -> list[dict[str, Any]]:
    result = []
    for model in dict.fromkeys(row["model"] for row in rows):
        group = [r for r in rows if r["model"] == model]
        measured = [r for r in group if "usage" in r and "cost" in r]
        summary: dict[str, Any] = {
            "model": model,
            "technical_passes": sum(r["technical_pass"] for r in group),
            "attempts": len(group),
            "median_seconds_all_attempts": round(statistics.median(r["seconds"] for r in group), 2),
            "attempts_without_usage": len(group) - len(measured),
        }
        if measured:
            avg_in = statistics.mean(r["usage"]["input_tokens"] for r in measured)
            avg_out = statistics.mean(r["usage"]["output_tokens"] for r in measured)
            avg_cost = statistics.mean(r["cost"]["planning_cost_usd"] for r in measured)
            summary.update(
                mean_input_tokens=round(avg_in),
                mean_output_tokens_including_reasoning=round(avg_out),
                mean_planning_cost_usd=round(avg_cost, 6),
                projections=[
                    {
                        "generation_attempts": n,
                        "reported_input_tokens": round(avg_in * n),
                        "reported_output_tokens": round(avg_out * n),
                        "planning_cost_usd": round(avg_cost * n, 2),
                    }
                    for n in sorted({100, 500, generations})
                ],
            )
        result.append(summary)
    return result


async def run(args: argparse.Namespace) -> None:
    # These imports and credentials are intentionally deferred until explicit opt-in.
    from openai import AsyncOpenAI

    from backend.services.recipe_composer import compose_recipe
    from llm.recipe_generator import _load_schema_format, _load_system_prompt
    from llm.schemas import RawRecipe

    async def validate(text: str) -> dict[str, Any]:
        raw = RawRecipe.model_validate_json(text)
        recipe = await compose_recipe(raw)
        if not recipe.title or not recipe.ingredients or not recipe.steps:
            raise ValueError("Empty recipe")
        return recipe.model_dump(mode="json")

    folder = Path(tempfile.mkdtemp(prefix="smartchef-benchmark-"))
    rows: list[dict[str, Any]] = []
    print(f"Reports: {folder}", flush=True)
    async with AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"], timeout=args.timeout, max_retries=0
    ) as client:
        for case, prompt in enumerate(PROMPTS[: args.cases], 1):
            for repeat in range(args.repeats):
                # Rotate model order to reduce systematic first-request/cache bias.
                shift = (case - 1 + repeat) % len(args.models)
                order = args.models[shift:] + args.models[:shift]
                for model in order:
                    row = await trial(
                        client, model, prompt, _load_system_prompt(),
                        dict(_load_schema_format()), validate, args.timeout,
                        args.max_output_tokens, args.luna_effort,
                    )
                    row.update(case=case, repeat=repeat + 1)
                    rows.append(row)
                    (folder / "results.json").write_text(
                        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    print(
                        f"{model} case={case} pass={row['technical_pass']} "
                        f"seconds={row['seconds']} "
                        f"tokens={row.get('usage', {}).get('total_tokens', '?')} "
                        f"error={row.get('error_type', row.get('incomplete_reason', '-'))}",
                        flush=True,
                    )
    report = {
        "settings": vars(args), "cost_note": COST_NOTE,
        "scope": "Initial recipe generation only; no chat edits, app retries, database or proxy.",
        "summary": summarize(rows, args.generations),
    }
    (folder / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    review = [
        "# Quality review\n",
        "Score each answer 0–2 for: request constraints, plausible quantities/servings, "
        "complete usable steps, consistent timing/equipment, and clear language. "
        "Flag unsafe cooking instructions separately; never trade safety for a score. "
        "Check sources manually. JSON validation is NOT a quality/safety grade.\n",
    ]
    for index, row in enumerate(rows, 1):
        review.append(
            f"## Sample {index} / case {row['case']}\n\n{row['prompt']}\n\n"
            f"Technical pass: {row['technical_pass']}\n\n"
            f"```json\n{row.get('output_text', '(no output)')}\n```\n"
        )
    review.append("## Model key — inspect after scoring\n")
    review.extend(f"- Sample {i}: {r['model']}\n" for i, r in enumerate(rows, 1))
    (folder / "quality.md").write_text("\n".join(review), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    print(f"Review recipes in {folder}/quality.md; measurements in summary.json and results.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True, choices=tuple(RATES))
    parser.add_argument("--run-paid", action="store_true", help="Explicitly enable paid requests")
    parser.add_argument("--cases", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--repeats", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--generations", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--max-output-tokens", type=int, default=6000)
    parser.add_argument(
        "--luna-effort", choices=("default", "none", "low", "medium"), default="default"
    )
    args = parser.parse_args()
    if args.generations <= 0 or args.timeout <= 0 or args.max_output_tokens <= 0:
        parser.error("Generations, timeout and output-token cap must be positive")
    if len(args.models) != len(set(args.models)):
        parser.error("Do not repeat model names")
    print(f"Plan: {len(args.models) * args.cases * args.repeats} paid requests, no retries.")
    print("Same app prompt/schema/search; single-step only; bounded output and wait time.")
    if not args.run_paid:
        print("Dry run only. Add --run-paid to execute. Website and .env stay unchanged.")
        return
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY must already be set; no .env files are read by this script")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
