import json
import logging
from types import SimpleNamespace

import pytest

from llm.config import LLMSettings
from llm.usage_logging import call_with_usage_logging, log_response_usage


def _settings(pricing_model: str = "gpt-6-luna") -> LLMSettings:
    return LLMSettings(
        openai_api_key="sk-test",
        openai_model="gpt-6-luna",
        openai_pricing_model=pricing_model,
    )


def _response() -> SimpleNamespace:
    return SimpleNamespace(
        id="resp_test",
        status="completed",
        usage=SimpleNamespace(
            input_tokens=1000,
            output_tokens=100,
            total_tokens=1100,
            input_tokens_details=SimpleNamespace(
                cached_tokens=200,
                cache_write_tokens=100,
            ),
            output_tokens_details=SimpleNamespace(reasoning_tokens=40),
        ),
        output=[
            SimpleNamespace(
                type="web_search_call",
                action=SimpleNamespace(type="search"),
            )
        ],
    )


def test_usage_log_includes_tokens_search_and_estimated_cost(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error.openai_usage"):
        log_response_usage(
            _response(),
            operation="recipe.structured.attempt_1",
            workflow_id="workflow-1",
            model="gpt-6-luna",
            elapsed_ms=250,
            settings=_settings(),
        )

    event = json.loads(caplog.records[-1].message)
    assert event["input_tokens"] == 1000
    assert event["cached_input_tokens"] == 200
    assert event["cache_write_tokens"] == 100
    assert event["output_tokens"] == 100
    assert event["reasoning_tokens"] == 40
    assert event["web_search_actions"] == 1
    assert event["estimated_cost_usd"] == 0.0101345
    assert "prompt" not in event


def test_cost_is_omitted_when_model_does_not_match_pricing_model(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error.openai_usage"):
        log_response_usage(
            _response(),
            operation="chat.response.attempt_1",
            workflow_id="workflow-2",
            model="gpt-6-sol",
            elapsed_ms=100,
            settings=_settings(pricing_model="gpt-6-luna"),
        )

    event = json.loads(caplog.records[-1].message)
    assert event["estimated_cost_usd"] is None


@pytest.mark.asyncio
async def test_failed_attempt_logs_error_without_sensitive_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fail() -> object:
        raise RuntimeError("secret response body")

    with (
        caplog.at_level(logging.WARNING, logger="uvicorn.error.openai_usage"),
        pytest.raises(RuntimeError),
    ):
        await call_with_usage_logging(
            fail,
            operation="recipe.structured.attempt_1",
            workflow_id="workflow-3",
            model="gpt-6-luna",
        )

    event = json.loads(caplog.records[-1].message)
    assert event["error_type"] == "RuntimeError"
    assert event["usage_available"] is False
    assert "secret response body" not in caplog.records[-1].message
