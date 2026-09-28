"""Provider-neutral stand-in for a LangChain chat model. Never calls a real API."""

from typing import Any
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage


class FakeChatModel:
    """Records how the llm package drives a chat model.

    `structured` results are returned (or raised) by the with_structured_output()
    runnable; `text` results by plain / bind_tools() calls.
    """

    def __init__(self, structured: list[Any] | None = None, text: list[str] | None = None):
        self.structured = AsyncMock(side_effect=list(structured or []))
        self.text = AsyncMock(
            side_effect=[AIMessage(content=[{"type": "text", "text": t}]) for t in text or []]
        )
        self.schema: dict[str, Any] | None = None
        self.structured_kwargs: dict[str, Any] = {}
        self.tools: list[Any] | None = None

    def with_structured_output(self, schema: dict[str, Any], **kwargs: Any) -> "FakeChatModel":
        self.schema = schema
        self.structured_kwargs = kwargs
        return _Runnable(self.structured)  # type: ignore[return-value]

    def bind_tools(self, tools: list[Any]) -> "_Runnable":
        self.tools = tools
        return _Runnable(self.text)

    async def ainvoke(self, messages: Any) -> Any:
        return await self.text(messages)


class _Runnable:
    def __init__(self, mock: AsyncMock) -> None:
        self._mock = mock

    async def ainvoke(self, messages: Any) -> Any:
        return await self._mock(messages)
