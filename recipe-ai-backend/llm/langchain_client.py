"""Shared LangChain plumbing for the llm package.

ChatOpenAI factory (Responses API), prompt/schema loading, output text
extraction and translation of OpenAI SDK errors into llm/errors.py domain
exceptions. No FastAPI imports here.
"""

import json
from collections.abc import Iterator
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from pydantic import SecretStr

from llm.config import LLMSettings
from llm.errors import UpstreamError, UpstreamRateLimitError, UpstreamTimeoutError

PROMPTS_DIR = Path(__file__).parent / "prompts"


def build_chat_model(settings: LLMSettings, model: str) -> ChatOpenAI:
    """ChatOpenAI bound to the OpenAI Responses API with an explicit timeout."""
    return ChatOpenAI(
        model=model,
        api_key=SecretStr(settings.openai_api_key),
        timeout=settings.openai_timeout_seconds,
        use_responses_api=True,
    )


@cache
def load_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"System prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


@cache
def load_response_format(path: Path) -> dict[str, Any]:
    """Load a strict JSON schema file as a `response_format` for ChatOpenAI.

    The files use the nested {"type": "json_schema", "json_schema": {...}} shape,
    which langchain-openai accepts as-is and converts into the Responses API
    `text.format` (flat {"type", "name", "schema", "strict"}) itself, so the file
    content is passed through unchanged.
    """
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def output_text(message: BaseMessage) -> str:
    """Concatenated text blocks of a model reply (Responses API returns a block list)."""
    return str(message.text)


@contextmanager
def translate_openai_errors() -> Iterator[None]:
    """Map OpenAI SDK exceptions (re-raised as-is by langchain-openai) to domain errors."""
    try:
        yield
    except APITimeoutError as exc:
        raise UpstreamTimeoutError("OpenAI request timed out") from exc
    except RateLimitError as exc:
        raise UpstreamRateLimitError("OpenAI rate limit exceeded") from exc
    except (APIConnectionError, APIError) as exc:
        raise UpstreamError(f"OpenAI API error: {exc}") from exc
