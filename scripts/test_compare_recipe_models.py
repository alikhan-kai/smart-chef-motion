"""Offline benchmark checks; stdlib-only, no API credentials or network required."""

import asyncio
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scripts.compare_recipe_models import summarize, trial, usage_cost


class BenchmarkTests(unittest.IsolatedAsyncioTestCase):
    def test_cost_does_not_double_count_reasoning(self) -> None:
        usage = {
            "input_tokens": 2000,
            "input_tokens_details": {"cached_tokens": 1000},
            "output_tokens": 3000,
            "output_tokens_details": {"reasoning_tokens": 2000},
        }
        cost = usage_cost("gpt-4.1-mini", usage, 1)
        self.assertAlmostEqual(cost["recorded_token_cost_usd"], 0.0053)
        self.assertAlmostEqual(cost["fixed_search_content_allowance_usd"], 0.0032)
        self.assertAlmostEqual(cost["planning_cost_usd"], 0.0185)

    def test_missing_usage_is_not_projected_as_free(self) -> None:
        rows = [{"model": "gpt-6-luna", "seconds": 90, "technical_pass": False}]
        report = summarize(rows, 500)[0]
        self.assertEqual(report["attempts_without_usage"], 1)
        self.assertNotIn("projections", report)

    def test_dry_run_needs_no_sdk_or_key(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/compare_recipe_models.py", "--models", "gpt-6-luna"],
            capture_output=True, text=True, check=True, env={},
        )
        self.assertIn("Dry run only", result.stdout)

    async def test_success_uses_app_contract_and_captures_usage(self) -> None:
        usage = {"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500}
        response = SimpleNamespace(
            model="gpt-6-luna", status="completed", output_text='{"title": "Soup"}',
            usage=SimpleNamespace(model_dump=lambda: usage),
            output=[SimpleNamespace(type="web_search_call", action=SimpleNamespace(type="search"))],
        )
        create = AsyncMock(return_value=response)
        client = SimpleNamespace(responses=SimpleNamespace(create=create))
        validate = AsyncMock(return_value={"title": "Soup"})
        row = await trial(client, "gpt-6-luna", "soup", "system", {}, validate, 1, 6000, "low")
        self.assertTrue(row["technical_pass"])
        self.assertEqual(row["search_actions"], 1)
        self.assertEqual(row["usage"]["total_tokens"], 1500)
        self.assertEqual(create.call_args.kwargs["reasoning"], {"effort": "low"})
        self.assertEqual(create.call_args.kwargs["tools"], [{"type": "web_search"}])
        self.assertFalse(create.call_args.kwargs["store"])
        projection = summarize([row], 500)[0]["projections"][-1]
        self.assertEqual(projection["reported_input_tokens"], 500000)

    async def test_schema_failure_keeps_usage(self) -> None:
        response = SimpleNamespace(
            model="gpt-4o-mini", status="completed", output_text="bad JSON", output=[],
            usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 10, "output_tokens": 20}),
        )
        client = SimpleNamespace(responses=SimpleNamespace(create=AsyncMock(return_value=response)))
        row = await trial(
            client, "gpt-4o-mini", "soup", "system", {},
            AsyncMock(side_effect=ValueError("invalid")), 1, 6000, "default",
        )
        self.assertFalse(row["technical_pass"])
        self.assertIn("usage", row)
        self.assertEqual(row["error_type"], "ValueError")

    async def test_timeout_is_bounded_and_no_secret_error_body(self) -> None:
        async def slow(**kwargs: object) -> None:
            await asyncio.sleep(1)

        client = SimpleNamespace(responses=SimpleNamespace(create=slow))
        row = await trial(
            client, "gpt-6-luna", "soup", "system", {}, AsyncMock(), 0.01, 6000, "default"
        )
        self.assertEqual(row["error_type"], "TimeoutError")
        client.responses.create = AsyncMock(side_effect=ValueError("SECRET_SENTINEL"))
        row = await trial(
            client, "gpt-6-luna", "soup", "system", {}, AsyncMock(), 1, 6000, "default"
        )
        self.assertNotIn("SECRET_SENTINEL", str(row))


if __name__ == "__main__":
    unittest.main()
