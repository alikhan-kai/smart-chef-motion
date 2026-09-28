"""Provider-agnostic LangChain plumbing for the llm package.

The chat model is created with init_chat_model(), so switching provider is a
config change (LLM_PROVIDER / LLM_MODEL) plus installing the matching
langchain-<provider> package. Nothing here imports a provider SDK.

Provider-specific knobs are kept in the two small tables below and nowhere else.
No FastAPI imports here.
"""

import json
from collections.abc import Generator
from contextlib import contextmanager
from functools import cache
from pathlib import Path
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import BaseMessage
from langchain_core.runnables import Runnable

from llm.config import LLMSettings
from llm.errors import LLMError, UpstreamError, UpstreamRateLimitError, UpstreamTimeoutError

PROMPTS_DIR = Path(__file__).parent / "prompts"

# Extra with_structured_output() kwargs per provider. method="json_schema" (native
# structured output) is supported by all of openai, anthropic and google_genai;
# only OpenAI takes an explicit strict flag.
_STRUCTURED_OUTPUT_KWARGS: dict[str, dict[str, Any]] = {
    "openai": {"strict": True},
}

# Server-side web search tool, in each provider's own format.
_WEB_SEARCH_TOOLS: dict[str, dict[str, Any]] = {
    "openai": {"type": "web_search"},
    "anthropic": {"type": "web_search_20250305", "name": "web_search", "max_uses": 5},
    "google_genai": {"google_search": {}},
}

StructuredRunnable = Runnable[LanguageModelInput, Any]
TextRunnable = Runnable[LanguageModelInput, BaseMessage]


def build_chat_model(settings: LLMSettings, model: str) -> BaseChatModel:
    """Chat model for the configured provider with an explicit timeout."""
    kwargs: dict[str, Any] = {"timeout": settings.llm_timeout_seconds}
    api_key = settings.provider_api_key()
    if api_key is not None:
        kwargs["api_key"] = api_key.get_secret_value()
    chat_model: BaseChatModel = init_chat_model(
        model, model_provider=settings.llm_provider, **kwargs
    )
    return chat_model


def _type_lists_to_any_of(node: Any) -> Any:
    """Rewrite OpenAI-style nullable types ({"type": ["string", "null"]}) as anyOf.

    Both forms are valid JSON Schema, but some providers (e.g. Anthropic) only
    accept the anyOf form. `enum` nulls go to the {"type": "null"} branch.
    """
    if isinstance(node, list):
        return [_type_lists_to_any_of(item) for item in node]
    if not isinstance(node, dict):
        return node
    node = {key: _type_lists_to_any_of(value) for key, value in node.items()}
    types = node.get("type")
    if not isinstance(types, list):
        return node

    rest = {key: value for key, value in node.items() if key not in ("type", "description")}
    branches: list[dict[str, Any]] = []
    for type_name in types:
        if type_name == "null":
            branches.append({"type": "null"})
            continue
        branch = {"type": type_name, **rest}
        if "enum" in branch:
            branch["enum"] = [value for value in branch["enum"] if value is not None]
        branches.append(branch)
    wrapper: dict[str, Any] = {"anyOf": branches}
    if "description" in node:
        wrapper["description"] = node["description"]
    return wrapper


def with_json_schema(
    model: BaseChatModel, provider: str, schema: dict[str, Any]
) -> StructuredRunnable:
    """Model that returns a dict matching `schema` via native structured output.

    OpenAI gets the schema file content unchanged; other providers get the
    equivalent anyOf form for nullable fields.
    """
    if provider != "openai":
        schema = _type_lists_to_any_of(schema)
    return model.with_structured_output(
        schema, method="json_schema", **_STRUCTURED_OUTPUT_KWARGS.get(provider, {})
    )


def with_web_search(model: BaseChatModel, provider: str) -> TextRunnable:
    """Model with the provider's server-side web search tool bound (plain text output)."""
    tool = _WEB_SEARCH_TOOLS.get(provider)
    if tool is None:
        raise UpstreamError(f"Web search is not configured for LLM provider '{provider}'")
    return model.bind_tools([tool])


@cache
def load_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"System prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


@cache
def load_json_schema(path: Path) -> dict[str, Any]:
    """Load a schema file as a plain JSON Schema for with_structured_output().

    The files use OpenAI's nested {"type": "json_schema", "json_schema": {"name",
    "strict", "schema"}} shape. The provider-neutral form is the inner JSON Schema
    with the name as its title; each LangChain integration converts that into its
    own wire format. The file itself stays the single source of truth.
    """
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")
    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    source = raw["json_schema"] if "json_schema" in raw else raw
    return {"title": source["name"], **source["schema"]}


def output_text(message: BaseMessage) -> str:
    """Concatenated text blocks of a model reply (some providers return a block list)."""
    return str(message.text)


def _error_names(exc: BaseException) -> list[str]:
    return [cls.__name__ for cls in type(exc).__mro__]


def _status_code(exc: BaseException) -> int | None:
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None


def _is_provider_error(names: list[str], status: int | None) -> bool:
    markers = ("APIError", "APIConnectionError", "APIStatusError", "GoogleAPIError", "HTTPError")
    return status is not None or any(name in markers for name in names)


@contextmanager
def translate_provider_errors() -> Generator[None]:
    """Map provider SDK exceptions (re-raised as-is by LangChain) to domain errors.

    Classified by exception class name / status code so no provider SDK has to be
    imported: OpenAI and Anthropic SDKs share APITimeoutError / RateLimitError /
    APIError names, Google uses DeadlineExceeded / ResourceExhausted / code 429.
    Anything that doesn't look like a provider error propagates unchanged.
    """
    try:
        yield
    except LLMError:
        raise
    except Exception as exc:
        names = _error_names(exc)
        status = _status_code(exc)
        if isinstance(exc, TimeoutError) or any(
            "Timeout" in name or name == "DeadlineExceeded" for name in names
        ):
            raise UpstreamTimeoutError("LLM request timed out") from exc
        if status == 429 or any(n in ("RateLimitError", "ResourceExhausted") for n in names):
            raise UpstreamRateLimitError("LLM rate limit exceeded") from exc
        if _is_provider_error(names, status):
            raise UpstreamError(f"LLM API error: {exc}") from exc
        raise
