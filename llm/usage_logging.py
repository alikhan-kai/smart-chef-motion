"""Structured per-attempt OpenAI usage and estimated-cost logging."""

import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from llm.config import LLMSettings, get_llm_settings

# This child inherits Uvicorn's configured stderr handler in production.
logger = logging.getLogger("uvicorn.error.openai_usage")

T = TypeVar("T")


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _web_search_actions(response: Any) -> int:
    count = 0
    for item in _value(response, "output", []) or []:
        if _value(item, "type") != "web_search_call":
            continue
        if _value(_value(item, "action"), "type") == "search":
            count += 1
    return count


def _estimated_cost(
    *,
    settings: LLMSettings,
    model: str,
    input_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
    output_tokens: int,
    web_search_actions: int,
) -> float | None:
    if model != settings.openai_pricing_model:
        return None
    uncached_tokens = max(0, input_tokens - cached_tokens - cache_write_tokens)
    token_cost = (
        uncached_tokens * settings.openai_input_cost_per_million_usd
        + cached_tokens * settings.openai_cached_input_cost_per_million_usd
        + cache_write_tokens * settings.openai_cache_write_cost_per_million_usd
        + output_tokens * settings.openai_output_cost_per_million_usd
    ) / 1_000_000
    search_cost = web_search_actions * settings.openai_web_search_cost_per_call_usd
    return round(token_cost + search_cost, 8)


def log_response_usage(
    response: Any,
    *,
    operation: str,
    workflow_id: str,
    model: str,
    elapsed_ms: int,
    settings: LLMSettings | None = None,
) -> None:
    """Log one completed paid attempt without prompts or credentials."""
    settings = settings or get_llm_settings()
    usage = _value(response, "usage")
    usage_available = usage is not None
    input_tokens = int(_value(usage, "input_tokens", 0) or 0)
    output_tokens = int(_value(usage, "output_tokens", 0) or 0)
    total_tokens = int(_value(usage, "total_tokens", input_tokens + output_tokens) or 0)
    input_details = _value(usage, "input_tokens_details")
    output_details = _value(usage, "output_tokens_details")
    cached_tokens = int(_value(input_details, "cached_tokens", 0) or 0)
    cache_write_tokens = int(_value(input_details, "cache_write_tokens", 0) or 0)
    reasoning_tokens = int(_value(output_details, "reasoning_tokens", 0) or 0)
    search_actions = _web_search_actions(response)
    estimated_cost = None
    if usage_available:
        estimated_cost = _estimated_cost(
            settings=settings,
            model=model,
            input_tokens=input_tokens,
            cached_tokens=cached_tokens,
            cache_write_tokens=cache_write_tokens,
            output_tokens=output_tokens,
            web_search_actions=search_actions,
        )

    event = {
        "event": "openai_usage",
        "workflow_id": workflow_id,
        "operation": operation,
        "model": model,
        "response_id": _value(response, "id"),
        "status": _value(response, "status", "completed"),
        "elapsed_ms": elapsed_ms,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "cache_write_tokens": cache_write_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
        "web_search_actions": search_actions,
        "usage_available": usage_available,
        "estimated_cost_usd": estimated_cost,
        "pricing_model": settings.openai_pricing_model,
    }
    logger.info(json.dumps(event, separators=(",", ":"), sort_keys=True))


async def call_with_usage_logging(
    call: Callable[[], Awaitable[T]],
    *,
    operation: str,
    workflow_id: str,
    model: str,
) -> T:
    """Execute one API attempt and emit success/error telemetry."""
    started = time.monotonic()
    try:
        response = await call()
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        event = {
            "event": "openai_request_error",
            "workflow_id": workflow_id,
            "operation": operation,
            "model": model,
            "elapsed_ms": elapsed_ms,
            "error_type": type(exc).__name__,
            "usage_available": False,
        }
        logger.warning(json.dumps(event, separators=(",", ":"), sort_keys=True))
        raise

    elapsed_ms = round((time.monotonic() - started) * 1000)
    log_response_usage(
        response,
        operation=operation,
        workflow_id=workflow_id,
        model=model,
        elapsed_ms=elapsed_ms,
    )
    return response
